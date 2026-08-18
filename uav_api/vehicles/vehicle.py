import copy
import math
import os
import queue
import sys
import threading
import time
import logging

from contextlib import contextmanager

from pymavlink import mavwp
from MAVProxy.modules.lib import mp_util
from pymavlink import mavutil
from pymavlink.rotmat import Vector3
from pymavlink.mavutil import location

from uav_api.classes.movement import Local_pos


########################################################################################################################
# Exceptions ###########################################################################################################
########################################################################################################################
class ErrorException(Exception):
    """Base class for other exceptions"""
    pass


class TimeoutException(ErrorException):
    pass


class LinkDownException(ErrorException):
    """Thrown when the MAVLink receiver has stopped and no more messages can arrive."""
    pass


class WaitModeTimeout(TimeoutException):
    """Thrown when fails to achieve given mode change."""
    pass


class WaitAltitudeTimout(TimeoutException):
    """Thrown when fails to achieve given altitude range."""
    pass


class WaitGroundSpeedTimeout(TimeoutException):
    """Thrown when fails to achieve given ground speed range."""
    pass


class WaitAirspeedTimeout(TimeoutException):
    """Thrown when fails to achieve given air speed range."""
    pass


class WaitRollTimeout(TimeoutException):
    """Thrown when fails to achieve given roll in degrees."""
    pass


class WaitPitchTimeout(TimeoutException):
    """Thrown when fails to achieve given pitch in degrees."""
    pass


class WaitHeadingTimeout(TimeoutException):
    """Thrown when fails to achieve given heading."""
    pass


class WaitDistanceTimeout(TimeoutException):
    """Thrown when fails to attain distance"""
    pass


class WaitLocationTimeout(TimeoutException):
    """Thrown when fails to attain location"""
    pass


class WaitWaypointTimeout(TimeoutException):
    """Thrown when fails to attain waypoint ranges"""
    pass


class SetRCTimeout(TimeoutException):
    """Thrown when fails to send RC commands"""
    pass


class MsgRcvTimeoutException(TimeoutException):
    """Thrown when fails to receive an expected message"""
    pass


class NotAchievedException(ErrorException):
    """Thrown when fails to achieve a goal"""
    pass


class YawSpeedNotAchievedException(NotAchievedException):
    """Thrown when fails to achieve given yaw speed."""
    pass


class SpeedVectorNotAchievedException(NotAchievedException):
    """Thrown when fails to achieve given speed vector."""
    pass


class PreconditionFailedException(ErrorException):
    """Thrown when a precondition for a command is not met"""
    pass


class ArmedAtEndOfTestException(ErrorException):
    """Created when test left vehicle armed"""
    pass


class MovementException(ErrorException):
    """Thrown when movement assumptions are violated"""
    pass


########################################################################################################################
# Receive plumbing #####################################################################################################
########################################################################################################################

# Sentinel pushed into every subscription queue when the receiver stops, so
# blocked waiters unblock immediately instead of running out their timeouts.
_STOP = object()


class Subscription:
    """A per-waiter queue of MAVLink messages, fed by the receiver thread.

    Created only through Vehicle.subscribe(). Receives every message matching
    (types, predicate) parsed AFTER registration — which is why waiters must
    subscribe BEFORE sending the request whose response they wait for.
    """

    def __init__(self, types=None, predicate=None, maxsize=512):
        self.types = frozenset(types) if types is not None else None
        self.predicate = predicate  # runs on the receiver thread; keep it trivial
        self._q = queue.Queue(maxsize)
        self.dropped = 0

    def get(self, timeout=10.0):
        """Block until the next matching message arrives.

        Raises TimeoutException on timeout and LinkDownException if the
        receiver has stopped."""
        try:
            m = self._q.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutException(
                "Timed out waiting %.1fs for %s" % (timeout, self._describe()))
        if m is _STOP:
            raise LinkDownException("MAVLink receiver stopped")
        return m

    def wait_for(self, predicate=None, timeout=10.0):
        """Block until a message satisfying predicate arrives (any message if
        predicate is None)."""
        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutException(
                    "Timed out waiting %.1fs for %s" % (timeout, self._describe()))
            m = self.get(timeout=remaining)
            if predicate is None or predicate(m):
                return m

    def clear(self):
        """Discard everything queued so far (e.g. between retries)."""
        while True:
            try:
                self._q.get_nowait()
            except queue.Empty:
                return

    def _describe(self):
        if self.types is None:
            return "any message"
        return "/".join(sorted(self.types))

    # Called from the receiver thread only.
    def _offer(self, m):
        try:
            self._q.put_nowait(m)
        except queue.Full:
            # Drop-oldest: waiters want the latest/next message, never deep history.
            try:
                self._q.get_nowait()
            except queue.Empty:
                pass
            try:
                self._q.put_nowait(m)
            except queue.Full:
                pass
            self.dropped += 1


class _LockedSender:
    """Proxy that serializes every call on `target` behind `lock`.

    pymavlink has no internal locking: concurrent *_send calls corrupt the tx
    buffer and sequence counter. All sends must go through this proxy."""

    def __init__(self, target, lock):
        self._target = target
        self._lock = lock

    def __getattr__(self, name):
        attr = getattr(self._target, name)
        if not callable(attr):
            return attr

        def locked_call(*args, **kwargs):
            with self._lock:
                return attr(*args, **kwargs)

        return locked_call


########################################################################################################################
# Vehicle ##############################################################################################################
########################################################################################################################
class Vehicle:
    """Base class for ArduPilot vehicles (Copter, Plane).

    Owns the MAVLink connection with a single-consumer receive model: exactly
    one thread (the receiver, started by connect()) ever reads the connection.
    Everything else consumes either the latest-by-type cache (latest(),
    pymavlink's mav.messages — written only by the receiver, so always
    race-free) or a Subscription queue fed by the receiver's dispatch, waking
    the instant a matching message is parsed.

    All sends go through self.tx (dialect-level *_send) or self.txc
    (mavfile-level helpers), which serialize on one lock.
    """

    # Overridable per-vehicle constants
    LAND_MIN_ALT = 6
    LAND_TIMEOUT = 60

    def __init__(self, default_stream_rate=5, sysid=1, logger_name="VEHICLE"):
        self.mav = None
        self.tx = None
        self.txc = None
        self.streamrate = default_stream_rate
        self.target_system = sysid
        self.target_component = 1
        self.heartbeat_interval_ms = 1000
        self.last_heartbeat_time_ms = None
        self.last_heartbeat_time_wc_s = 0
        self.total_waiting_to_arm_time = 0
        self.waiting_to_arm_count = 0
        self.wploader = mavwp.MAVWPLoader()
        self.wp_received = {}
        self.wp_requested = {}
        self.wp_expected_count = 0
        self.logger = logging.getLogger(logger_name)

        self._subs = []
        self._sub_lock = threading.Lock()
        self._send_lock = threading.RLock()
        self._mission_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._rx_thread = None
        self._last_rx_monotonic = None

    ####################################################################################################################
    # Distance / coordinate helpers ####################################################################################
    ####################################################################################################################
    @staticmethod
    def get_distance(loc1, loc2):
        """Get ground distance between two locations."""
        return Vehicle.get_distance_accurate(loc1, loc2)

    @staticmethod
    def get_distance_accurate(loc1, loc2):
        """Get ground distance between two locations."""
        try:
            lon1 = loc1.lng
            lon2 = loc2.lng
        except AttributeError:
            lon1 = loc1.lon
            lon2 = loc2.lon
        return mp_util.gps_distance(loc1.lat, lon1, loc2.lat, lon2)

    @staticmethod
    def get_latlon_attr(loc, attrs):
        """return any found latitude attribute from loc"""
        ret = None
        for attr in attrs:
            if hasattr(loc, attr):
                ret = getattr(loc, attr)
                break
        if ret is None:
            raise ValueError("None of %s in loc(%s)" % (str(attrs), str(loc)))
        return ret

    @staticmethod
    def get_lat_attr(loc):
        return Vehicle.get_latlon_attr(loc, ["lat", "latitude"])

    @staticmethod
    def get_lon_attr(loc):
        return Vehicle.get_latlon_attr(loc, ["lng", "lon", "longitude"])

    @staticmethod
    def get_distance_int(loc1, loc2):
        """Get ground distance between two locations in the normal "int" form
        - lat/lon multiplied by 1e7"""
        loc1_lat = Vehicle.get_lat_attr(loc1)
        loc2_lat = Vehicle.get_lat_attr(loc2)
        loc1_lon = Vehicle.get_lon_attr(loc1)
        loc2_lon = Vehicle.get_lon_attr(loc2)
        return Vehicle.get_distance_accurate(
            mavutil.location(loc1_lat * 1e-7, loc1_lon * 1e-7),
            mavutil.location(loc2_lat * 1e-7, loc2_lon * 1e-7))

    def progress(self, text):
        """Utility to print message with current time."""
        self.logger.info(text)

    def longitude_scale(self, lat):
        ret = math.cos(lat * (math.radians(1)))
        self.logger.debug("scale=%f" % ret)
        return ret

    def mav_location(self, lat: float, long: float, alt: float):
        return mavutil.location(lat, long, alt, 0)

    ####################################################################################################################
    # Connection / receiver thread #####################################################################################
    ####################################################################################################################
    def connect(self, connection_string='udpin:0.0.0.0:14550'):
        """Open the MAVLink connection, enforce MAVLink2, start the single
        receiver thread and set a default streamrate."""
        os.environ['MAVLINK20'] = '1'
        self.mav = mavutil.mavlink_connection(
            connection_string,
            retries=1000,
            robust_parsing=True,
            source_system=250,
            source_component=250,
            autoreconnect=True,
            dialect="ardupilotmega",
        )
        self.tx = _LockedSender(self.mav.mav, self._send_lock)
        self.txc = _LockedSender(self.mav, self._send_lock)
        self._start_receiver()
        try:
            self.set_streamrate(self.streamrate)
        except Exception:
            self.close()
            raise

    def _start_receiver(self):
        self._stop_event.clear()
        self._rx_thread = threading.Thread(
            target=self._rx_loop, name="mavlink-rx", daemon=True)
        self._rx_thread.start()

    def close(self, join_timeout=2.0):
        """Stop the receiver thread, unblock every waiter and close the link."""
        self._stop_event.set()
        if self._rx_thread is not None and self._rx_thread.is_alive():
            self._rx_thread.join(join_timeout)
        with self._sub_lock:
            subs = list(self._subs)
        for sub in subs:
            sub._offer(_STOP)
        if self.mav is not None:
            self.mav.close()

    def link_healthy(self, max_silence=5.0):
        """True if the receiver thread is alive and has parsed a message recently."""
        if self._rx_thread is None or not self._rx_thread.is_alive():
            return False
        if self._last_rx_monotonic is None:
            return False
        return time.monotonic() - self._last_rx_monotonic <= max_silence

    def _rx_loop(self):
        """The ONLY line of execution that reads the MAVLink connection.

        Parses every incoming message (keeping pymavlink's mav.messages,
        flightmode, motors_armed() etc. consistent, since no other thread
        parses) and dispatches it to registered subscriptions."""
        while not self._stop_event.is_set():
            try:
                # The timeout only bounds idle iterations (shutdown/heartbeat
                # cadence); select() wakes immediately when data arrives.
                m = self.mav.recv_match(blocking=True, timeout=0.25)
                if m is not None:
                    self._last_rx_monotonic = time.monotonic()
                    if m.get_type() != 'BAD_DATA':
                        self._dispatch(m)
                self._maybe_send_heartbeat()
            except Exception:
                if self._stop_event.is_set():
                    break
                self.logger.exception("MAVLink receiver iteration failed")
                time.sleep(0.5)
        with self._sub_lock:
            subs = list(self._subs)
        for sub in subs:
            sub._offer(_STOP)

    def _dispatch(self, m):
        if m.get_type() == 'STATUSTEXT':
            self.progress("AP: %s" % m.text)
        mtype = m.get_type()
        with self._sub_lock:
            subs = list(self._subs)
        for sub in subs:
            if sub.types is not None and mtype not in sub.types:
                continue
            if sub.predicate is not None:
                try:
                    if not sub.predicate(m):
                        continue
                except Exception:
                    self.logger.exception("subscription predicate failed")
                    continue
            sub._offer(m)

    def _maybe_send_heartbeat(self, force=False):
        """Send our GCS heartbeat when due. Runs on the receiver thread each
        loop iteration (<=0.25s granularity), so heartbeats keep flowing even
        when the link is quiet."""
        if self.heartbeat_interval_ms is None and not force:
            return
        x = self.mav.messages.get("SYSTEM_TIME", None)
        now_wc = time.time()
        if (force or
                x is None or
                self.last_heartbeat_time_ms is None or
                self.last_heartbeat_time_ms < x.time_boot_ms or
                x.time_boot_ms - self.last_heartbeat_time_ms > self.heartbeat_interval_ms or
                now_wc - self.last_heartbeat_time_wc_s > 1):
            if x is not None:
                self.last_heartbeat_time_ms = x.time_boot_ms
            self.last_heartbeat_time_wc_s = now_wc
            self.tx.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                                   mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                                   0,
                                   0,
                                   0)

    ####################################################################################################################
    # Receive primitives ###############################################################################################
    ####################################################################################################################
    @contextmanager
    def subscribe(self, types=None, predicate=None, maxsize=512):
        """Register a Subscription and always unregister it on exit.

        INVARIANT: for request/response flows, subscribe BEFORE sending the
        request — the subscription only sees messages parsed after
        registration, so subscribing first is what makes lost responses
        impossible."""
        if self._stop_event.is_set():
            raise LinkDownException("MAVLink receiver stopped")
        sub = Subscription(types=types, predicate=predicate, maxsize=maxsize)
        with self._sub_lock:
            self._subs.append(sub)
        try:
            yield sub
        finally:
            with self._sub_lock:
                try:
                    self._subs.remove(sub)
                except ValueError:
                    pass

    def latest(self, mtype, max_age=None):
        """Latest-by-type cache read; O(1), never blocks.

        Returns None if the type was never seen or (when max_age is given) the
        cached message is older than max_age seconds."""
        if self.mav is None:
            return None
        m = self.mav.messages.get(mtype, None)
        if m is None:
            return None
        if max_age is not None and time.time() - m._timestamp > max_age:
            return None
        return m

    def wait_message(self, types, timeout=10.0, predicate=None, allow_cached_age=None):
        """Return a message of one of `types`.

        With allow_cached_age set, a cached message younger than that many
        seconds is returned immediately (telemetry reads: effectively O(1)).
        Otherwise blocks until the NEXT matching message is parsed — which also
        paces polling loops at the stream rate instead of hot-spinning."""
        if isinstance(types, str):
            types = (types,)
        if self._rx_thread is None or not self._rx_thread.is_alive():
            raise LinkDownException("MAVLink receiver is not running")
        with self.subscribe(types=set(types), predicate=predicate) as sub:
            if allow_cached_age is not None:
                for t in types:
                    m = self.latest(t, max_age=allow_cached_age)
                    if m is not None and (predicate is None or predicate(m)):
                        return m
            return sub.get(timeout=timeout)

    def location(self, relative_alt=False, timeout=5):
        """Current vehicle location, replacing mavutil.mavfile.location() with
        a cache/subscription implementation (and, unlike it, a timeout).

        Waits for a FRESH GLOBAL_POSITION_INT so callers polling in a loop are
        paced at the stream rate."""
        fix = self.wait_message(
            'GPS_RAW_INT',
            timeout=timeout,
            predicate=lambda m: m.fix_type >= 3 and m.lat != 0,
            allow_cached_age=2.0)
        if fix is None:
            raise TimeoutException("Did not get GPS fix")
        m = self.wait_message('GLOBAL_POSITION_INT', timeout=timeout)
        hud = self.latest('VFR_HUD')
        if hud is None:
            hud = self.wait_message('VFR_HUD', timeout=timeout)
        if relative_alt:
            alt = m.relative_alt * 0.001
        else:
            alt = m.alt * 0.001
        return mavutil.location(m.lat * 1.0e-7, m.lon * 1.0e-7, alt, hud.heading)

    def waypoint_current(self, timeout=5):
        """Current mission waypoint sequence number."""
        m = self.wait_message('MISSION_CURRENT', timeout=timeout, allow_cached_age=2.0)
        return m.seq

    def wait_heartbeat(self, drain_mav=None, quiet=False, timeout=10, **x):
        """Wait for a heartbeat from our target system; raises TimeoutException.

        drain_mav is accepted for backwards compatibility and ignored — the
        receiver thread drains continuously."""
        return self.wait_message(
            'HEARTBEAT',
            timeout=timeout,
            predicate=lambda m: m.get_srcSystem() == self.target_system)

    ####################################################################################################################
    # Streamrate / message intervals ###################################################################################
    ####################################################################################################################
    def set_streamrate(self, streamrate, timeout=20):
        """set MAV_DATA_STREAM_ALL; timeout is wallclock time"""
        tstart = time.time()
        with self.subscribe(types={'SYSTEM_TIME'}) as sub:
            while True:
                if time.time() - tstart > timeout:
                    raise TimeoutException("Failed to set streamrate")
                self.tx.request_data_stream_send(
                    self.target_system,
                    self.target_component,
                    mavutil.mavlink.MAV_DATA_STREAM_ALL,
                    streamrate,
                    1)
                try:
                    sub.get(timeout=1)
                    break
                except TimeoutException:
                    continue

    def rate_to_interval_us(self, rate):
        return 1 / float(rate) * 1000000.0

    def set_message_rate_hz(self, id, rate_hz):
        """set a message rate in Hz; 0 for original, -1 to disable"""
        if isinstance(id, str):
            id = eval("mavutil.mavlink.MAVLINK_MSG_ID_%s" % id)
        if rate_hz == 0 or rate_hz == -1:
            set_interval = rate_hz
        else:
            set_interval = self.rate_to_interval_us(rate_hz)
        self.run_cmd(mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                     id,
                     set_interval,
                     0,
                     0,
                     0,
                     0,
                     0)

    def send_get_message_interval(self, victim_message_id, timeout=5):
        with self.subscribe(types={'MESSAGE_INTERVAL'}) as sub:
            self.tx.command_long_send(
                1,
                1,
                mavutil.mavlink.MAV_CMD_GET_MESSAGE_INTERVAL,
                1,  # confirmation
                float(victim_message_id),
                0,
                0,
                0,
                0,
                0,
                0)
            m = sub.get(timeout=timeout)
        return self.rate_to_interval_us(m.interval_us)

    ####################################################################################################################
    # Parameters #######################################################################################################
    ####################################################################################################################
    def send_set_parameter_direct(self, name, value):
        self.tx.param_set_send(self.target_system,
                               1,
                               name.encode('ascii'),
                               value,
                               mavutil.mavlink.MAV_PARAM_TYPE_REAL32)

    def send_set_parameter(self, name, value, verbose=False):
        if verbose:
            self.progress("Send set param for (%s) (%f)" % (name, value))
        return self.send_set_parameter_direct(name, value)

    def set_parameter(self, name, value, **kwargs):
        self.set_parameters({name: value}, **kwargs)

    def set_parameters(self, parameters, add_to_context=True, epsilon_pct=0.00001, retries=None, verbose=True):
        """Set parameters from vehicle."""
        want = copy.copy(parameters)
        self.progress("set_parameters: (%s)" % str(want))
        if len(want) == 0:
            return

        if retries is None:
            # we can easily fill ArduPilot's param-set/param-get queue
            # which is quite short.  So we retry *a lot*.
            retries = (len(want) + 1) * 5

        original_values = {}
        autopilot_values = {}
        with self.subscribe(types={'PARAM_VALUE'}) as sub:
            for i in range(retries):
                received = set()
                for (name, value) in want.items():
                    self.progress("%s want=%f autopilot=%s" % (name, value, autopilot_values.get(name, 'None')))
                    if name not in autopilot_values:
                        self.send_get_parameter_direct(name)
                        self.progress("Requesting (%s) (retry=%u)" % (name, i))
                        continue
                    delta = abs(autopilot_values[name] - value)
                    if delta <= epsilon_pct * 0.01 * abs(value):
                        # correct value
                        self.progress("%s is now %f" % (name, autopilot_values[name]))
                        received.add(name)
                        continue
                    self.progress("Sending set (%s) to (%f) (old=%f)" % (name, value, original_values[name]))
                    self.send_set_parameter_direct(name, value)
                for name in received:
                    del want[name]
                if len(want):
                    self.wait_heartbeat()
                while True:
                    try:
                        m = sub._q.get_nowait()
                    except queue.Empty:
                        break
                    if m is _STOP:
                        raise LinkDownException("MAVLink receiver stopped")
                    if m.param_id in want:
                        self.progress("Received wanted PARAM_VALUE %s=%f" %
                                      (str(m.param_id), m.param_value))
                        autopilot_values[m.param_id] = m.param_value
                        if m.param_id not in original_values:
                            original_values[m.param_id] = m.param_value

        if len(want) == 0:
            return
        raise ValueError("Failed to set parameters (%s)" % want)

    @staticmethod
    def should_fetch_all_for_parameter_change(param_name):
        return False  # FIXME: if we allow MAVProxy then allow this

    def get_parameter(self, *args, **kwargs):
        return self.get_parameter_direct(*args, **kwargs)

    def send_get_parameter_direct(self, name):
        encname = name
        if sys.version_info.major >= 3 and not isinstance(encname, bytes):
            encname = bytes(encname, 'ascii')
        self.tx.param_request_read_send(self.target_system,
                                        1,
                                        encname,
                                        -1)

    def get_parameter_direct(self, name, attempts=1, timeout=60, verbose=True, timeout_in_wallclock=False):
        while attempts > 0:
            attempts -= 1
            if verbose:
                self.progress("Sending param_request_read for (%s)" % name)
            with self.subscribe(types={'PARAM_VALUE'},
                                predicate=lambda m: m.param_id == name) as sub:
                tstart = time.time()
                self.send_get_parameter_direct(name)
                remaining = timeout - (time.time() - tstart)
                while remaining > 0:
                    try:
                        m = sub.get(timeout=remaining)
                    except TimeoutException:
                        break
                    delta_time = time.time() - tstart
                    if verbose:
                        self.progress("get_parameter(%s): %s" % (name, str(m),))
                    if delta_time > 5:
                        self.progress("Long time to get parameter: %fs" % (delta_time,))
                    return m.param_value
        raise NotAchievedException("Failed to retrieve parameter (%s)" % name)

    ####################################################################################################################
    # COMMAND_LONG / COMMAND_INT #######################################################################################
    ####################################################################################################################
    def send_cmd(self,
                 command,
                 p1,
                 p2,
                 p3,
                 p4,
                 p5,
                 p6,
                 p7,
                 target_sysid=None,
                 target_compid=None,
                 ):
        """Send a MAVLink command long."""
        if target_sysid is None:
            target_sysid = self.target_system
        if target_compid is None:
            target_compid = 1
        try:
            command_name = mavutil.mavlink.enums["MAV_CMD"][command].name
        except KeyError:
            command_name = "UNKNOWN=%u" % command
        self.progress("Sending COMMAND_LONG to (%u,%u) (%s) (p1=%f p2=%f p3=%f p4=%f p5=%f p6=%f  p7=%f)" %
                      (
                          target_sysid,
                          target_compid,
                          command_name,
                          p1,
                          p2,
                          p3,
                          p4,
                          p5,
                          p6,
                          p7))
        self.tx.command_long_send(target_sysid,
                                  target_compid,
                                  command,
                                  1,  # confirmation
                                  p1,
                                  p2,
                                  p3,
                                  p4,
                                  p5,
                                  p6,
                                  p7)

    def send_cmd_int(self, command, p1, p2, p3, p4, x, y, z,
                     frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                     target_sysid=None, target_compid=None,
                     current=0, autocontinue=0):
        """Send a COMMAND_INT (fire-and-forget).

        COMMAND_INT carries lat/lon as scaled int32 and a frame field; this is the
        correct envelope for DO_REPOSITION and NAV_LOITER_* on ArduPlane.
        x/y should already be scaled int32 (lat * 1e7, lon * 1e7) when sending GPS
        commands; z is altitude in meters.
        """
        if target_sysid is None:
            target_sysid = self.target_system
        if target_compid is None:
            target_compid = 1
        try:
            command_name = mavutil.mavlink.enums["MAV_CMD"][command].name
        except KeyError:
            command_name = "UNKNOWN=%u" % command
        self.progress("Sending COMMAND_INT to (%u,%u) (%s) frame=%u (p1=%f p2=%f p3=%f p4=%f x=%d y=%d z=%f)" %
                      (target_sysid, target_compid, command_name, frame, p1, p2, p3, p4, x, y, z))
        self.tx.command_int_send(target_sysid, target_compid, frame, command,
                                 current, autocontinue, p1, p2, p3, p4, x, y, z)

    def run_cmd(self,
                command,
                p1,
                p2,
                p3,
                p4,
                p5,
                p6,
                p7,
                want_result=mavutil.mavlink.MAV_RESULT_ACCEPTED,
                target_sysid=None,
                target_compid=None,
                timeout=10,
                quiet=False):
        """Send a COMMAND_LONG and block until a matching COMMAND_ACK arrives.

        The COMMAND_ACK subscription is registered before the send, so the ack
        cannot be lost no matter what else is running concurrently, and the
        waiter wakes the instant the receiver parses it."""
        with self.subscribe(types={'COMMAND_ACK'},
                            predicate=lambda m: m.command == command) as sub:
            tstart = time.time()
            self.send_cmd(command,
                          p1,
                          p2,
                          p3,
                          p4,
                          p5,
                          p6,
                          p7,
                          target_sysid=target_sysid,
                          target_compid=target_compid,
                          )
            self._wait_ack(sub, command, want_result, timeout, tstart, quiet)

    def run_cmd_int(self, command, p1, p2, p3, p4, x, y, z,
                    frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    want_result=mavutil.mavlink.MAV_RESULT_ACCEPTED,
                    target_sysid=None, target_compid=None,
                    timeout=10, quiet=False):
        """Send a COMMAND_INT and block for ACK."""
        with self.subscribe(types={'COMMAND_ACK'},
                            predicate=lambda m: m.command == command) as sub:
            tstart = time.time()
            self.send_cmd_int(command, p1, p2, p3, p4, x, y, z,
                              frame=frame,
                              target_sysid=target_sysid, target_compid=target_compid)
            self._wait_ack(sub, command, want_result, timeout, tstart, quiet)

    def _wait_ack(self, sub, command, want_result, timeout, tstart, quiet):
        try:
            m = sub.get(timeout=timeout)
        except TimeoutException:
            raise TimeoutException("Did not get good COMMAND_ACK within %fs" % timeout)
        if not quiet:
            self.progress("ACK received: %s (%fs)" % (str(m), time.time() - tstart))
        if m.result != want_result:
            raise ValueError("Expected %s got %s" % (
                mavutil.mavlink.enums["MAV_RESULT"][want_result].name,
                mavutil.mavlink.enums["MAV_RESULT"][m.result].name))

    ####################################################################################################################
    # Mode handling ####################################################################################################
    ####################################################################################################################
    def run_cmd_do_set_mode(self,
                            mode,
                            timeout=30,
                            want_result=mavutil.mavlink.MAV_RESULT_ACCEPTED):
        base_mode = mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
        custom_mode = self.get_mode_from_mode_mapping(mode)
        self.run_cmd(mavutil.mavlink.MAV_CMD_DO_SET_MODE,
                     base_mode,
                     custom_mode,
                     0,
                     0,
                     0,
                     0,
                     0,
                     want_result=want_result,
                     timeout=timeout
                     )

    def do_set_mode_via_command_long(self, mode, timeout=30):
        """Set mode with a command long message."""
        tstart = time.time()
        want_custom_mode = self.get_mode_from_mode_mapping(mode)
        while True:
            remaining = timeout - (time.time() - tstart)
            if remaining <= 0:
                raise TimeoutException("Failed to change mode")
            # Subscribe before the command so the confirming heartbeat can't slip by.
            with self.subscribe(
                    types={'HEARTBEAT'},
                    predicate=lambda m: m.get_srcSystem() == self.target_system) as sub:
                self.run_cmd_do_set_mode(mode, timeout=10)
                try:
                    m = sub.wait_for(
                        predicate=lambda m: m.custom_mode == want_custom_mode,
                        timeout=min(5, max(remaining, 0.1)))
                except TimeoutException:
                    continue
                self.progress("Got mode=%u want=%u" % (m.custom_mode, want_custom_mode))
                return

    def change_mode(self, mode, timeout=60):
        """change vehicle flightmode"""
        try:
            self.wait_heartbeat()
            self.progress("Changing mode to %s" % mode)
            self.do_set_mode_via_command_long(mode)
        except Exception:
            return False
        return True

    def mode_is(self, mode, cached=False, drain_mav=None):
        if not cached:
            self.wait_heartbeat()
        try:
            return self.get_mode_from_mode_mapping(self.mav.flightmode) == self.get_mode_from_mode_mapping(mode)
        except Exception:
            pass
        # assume this is a number....
        return self.mav.messages['HEARTBEAT'].custom_mode == mode

    def wait_mode(self, mode, timeout=60):
        """Wait for mode to change."""
        self.progress("Waiting for mode %s" % mode)
        tstart = time.time()
        while not self.mode_is(mode):
            custom_num = self.mav.messages['HEARTBEAT'].custom_mode
            self.progress("mav.flightmode=%s Want=%s custom=%u" % (
                self.mav.flightmode, mode, custom_num))
            if (timeout is not None and
                    time.time() > tstart + timeout):
                raise WaitModeTimeout("Did not change mode")
        self.progress("Got mode %s" % mode)

    def get_mode_from_mode_mapping(self, mode):
        """Validate and return the mode number from a string or int."""
        mode_map = self.mav.mode_mapping()
        if mode_map is None:
            mav_type = self.mav.messages['HEARTBEAT'].type
            mav_autopilot = self.mav.messages['HEARTBEAT'].autopilot
            raise ErrorException("No mode map for (mav_type=%s mav_autopilot=%s)" % (mav_type, mav_autopilot))
        if isinstance(mode, str):
            if mode in mode_map:
                return mode_map.get(mode)
        if mode in mode_map.values():
            return mode
        self.progress("Available modes '%s'" % mode_map)
        raise ErrorException("Unknown mode '%s'" % mode)

    ####################################################################################################################
    # Home position ####################################################################################################
    ####################################################################################################################
    def distance_to_home(self, use_cached_home=False):
        m = self.mav.messages.get("HOME_POSITION", None)
        if use_cached_home is False or m is None:
            m = self.poll_home_position(quiet=True)
        here = self.wait_message('GLOBAL_POSITION_INT', timeout=5, allow_cached_age=1.0)
        return self.get_distance_int(m, here)

    def poll_home_position(self, quiet=True, timeout=30):
        old = self.mav.messages.get("HOME_POSITION", None)
        tstart = time.time()
        while True:
            if time.time() - tstart > timeout:
                raise NotAchievedException("Failed to poll home position")
            if not quiet:
                self.progress("Sending MAV_CMD_GET_HOME_POSITION")
            try:
                self.run_cmd(
                    mavutil.mavlink.MAV_CMD_GET_HOME_POSITION,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    quiet=quiet)
            except ValueError:
                continue
            m = self.mav.messages.get("HOME_POSITION", None)
            if m is None:
                continue
            if old is None:
                break
            if m._timestamp != old._timestamp:
                break
        self.progress("Polled home position (%s)" % str(m))
        return m

    def home_position_as_mav_location(self):
        m = self.poll_home_position()
        return mavutil.location(m.latitude * 1.0e-7, m.longitude * 1.0e-7, m.altitude * 1.0e-3, 0)

    def request_home_message(self, message_id=None, timeout=5):
        """Request the HOME_POSITION message from the vehicle."""
        self.progress("Requesting HOME_POSITION")
        self.tx.command_long_send(
            self.target_system,
            self.target_component,
            mavutil.mavlink.MAV_CMD_GET_HOME_POSITION,
            0,
            0, 0, 0, 0, 0, 0, 0)

    def get_home_position(self, timeout=10):
        """Get home position as sent by the vehicle."""
        with self.subscribe(types={'HOME_POSITION'}) as sub:
            self.request_home_message()
            try:
                home_message = sub.get(timeout=timeout)
            except TimeoutException:
                # A recent cached copy is as good as a fresh one here.
                home_message = self.latest('HOME_POSITION')
                if home_message is None:
                    raise TimeoutException("Failed to get HOME_POSITION message")
        return home_message.to_dict()

    def set_home(self, timeout=30):
        """Set the home position to the vehicle's current position.

        Right after boot ArduPilot rejects this (MAV_RESULT_FAILED) until the
        EKF origin is set, so retry until accepted or timeout."""
        tstart = time.time()
        while True:
            try:
                self.run_cmd(mavutil.mavlink.MAV_CMD_DO_SET_HOME,
                             1, 0, 0, 0, 0, 0, 0, timeout=10)
                return
            except ValueError:
                if time.time() - tstart > timeout:
                    raise
                self.wait_heartbeat()  # ~1 Hz pacing until the autopilot is ready

    ####################################################################################################################
    # Wait helpers #####################################################################################################
    ####################################################################################################################
    def wait_altitude(self, altitude_min, altitude_max, relative=False, timeout=30, **kwargs):
        """Wait for a given altitude range."""
        assert altitude_min <= altitude_max, "Minimum altitude should be less than maximum altitude."

        def get_altitude(alt_relative=False, timeout2=30):
            # Fresh wait: paces the loop at the stream rate, no hot spin.
            try:
                msg = self.wait_message('GLOBAL_POSITION_INT', timeout=timeout2)
            except TimeoutException:
                raise MsgRcvTimeoutException("Failed to get Global Position")
            if alt_relative:
                return msg.relative_alt / 1000.0  # mm -> m
            return msg.alt / 1000.0  # mm -> m

        def validator(value2, target2=None):
            return altitude_min <= value2 <= altitude_max

        self.wait_and_maintain(value_name="Altitude", target=altitude_min,
                               current_value_getter=lambda: get_altitude(relative, timeout),
                               accuracy=(altitude_max - altitude_min),
                               validator=lambda value2, target2: validator(value2, target2), timeout=timeout, **kwargs)

    def wait_location(self,
                      loc,
                      accuracy=5.0,
                      timeout=30,
                      target_altitude=None,
                      height_accuracy=-1,
                      **kwargs):
        """Wait for arrival at a location."""

        def get_distance_to_loc():
            return self.get_distance(self.location(), loc)

        def validator(value2, empty=None):
            if value2 <= accuracy:
                if target_altitude is not None:
                    height_delta = math.fabs(self.location().alt - target_altitude)
                    if height_accuracy != -1 and height_delta > height_accuracy:
                        return False
                return True
            else:
                return False

        debug_text = "Distance to Location (%.4f, %.4f) " % (loc.lat, loc.lng)
        if target_altitude is not None:
            debug_text += ",at altitude %.1f height_accuracy=%.1f, d" % (target_altitude, height_accuracy)
        self.wait_and_maintain(value_name=debug_text, target=0, current_value_getter=lambda: get_distance_to_loc(),
                               accuracy=accuracy, validator=lambda value2, target2: validator(value2, None),
                               timeout=timeout, **kwargs)

    def wait_distance_to_home(self, distance_min, distance_max, timeout=10, use_cached_home=True, **kwargs):
        """Wait for distance to home to be within specified bounds."""
        assert distance_min <= distance_max, "Distance min should be less than distance max."

        def get_distance():
            return self.distance_to_home(use_cached_home)

        def validator(value2, target2=None):
            return distance_min <= value2 <= distance_max

        self.wait_and_maintain(value_name="Distance to home", target=distance_min,
                               current_value_getter=lambda: get_distance(),
                               validator=lambda value2, target2: validator(value2, target2),
                               accuracy=(distance_max - distance_min), timeout=timeout, **kwargs)

    def wait_and_maintain(self, value_name, target, current_value_getter, validator=None, accuracy=0.3, timeout=30,
                          **kwargs):
        tstart = time.time()
        achieving_duration_start = None
        if type(target) is Vector3:
            sum_of_achieved_values = Vector3()
            last_value = Vector3()
        else:
            sum_of_achieved_values = 0.0
            last_value = 0.0
        count_of_achieved_values = 0
        called_function = kwargs.get("called_function", None)
        minimum_duration = kwargs.get("minimum_duration", 0)
        if type(target) is Vector3:
            self.progress("Waiting for %s=(%s) with accuracy %.02f" % (value_name, str(target), accuracy))
        else:
            self.progress("Waiting for %s=%.02f with accuracy %.02f" % (value_name, target, accuracy))
        last_print_time = 0
        while time.time() < tstart + timeout:  # if we failed to received message with the getter the sim time isn't updated
            last_value = current_value_getter()
            if called_function is not None:
                called_function(last_value, target)
            if time.time() - last_print_time > 1:
                if type(target) is Vector3:
                    self.progress("%s=(%s) (want (%s) +- %f)" %
                                  (value_name, str(last_value), str(target), accuracy))
                else:
                    self.progress("%s=%0.2f (want %f +- %f)" %
                                  (value_name, last_value, target, accuracy))
                last_print_time = time.time()
            if validator is not None:
                is_value_valid = validator(last_value, target)
            else:
                is_value_valid = math.fabs(last_value - target) <= accuracy
            if is_value_valid:
                sum_of_achieved_values += last_value
                count_of_achieved_values += 1.0
                if achieving_duration_start is None:
                    achieving_duration_start = time.time()
                if time.time() - achieving_duration_start >= minimum_duration:
                    if type(target) is Vector3:
                        self.progress("Attained %s=%s" % (
                            value_name, str(sum_of_achieved_values * (1.0 / count_of_achieved_values))))
                    else:
                        self.progress(
                            "Attained %s=%f" % (value_name, sum_of_achieved_values / count_of_achieved_values))
                    return True
            else:
                achieving_duration_start = None
                if type(target) is Vector3:
                    sum_of_achieved_values.zero()
                else:
                    sum_of_achieved_values = 0.0
                count_of_achieved_values = 0
        raise TimeoutException("Failed to attain %s want %s, reached %s" % (value_name, str(target), str(
            sum_of_achieved_values * (1.0 / count_of_achieved_values)) if count_of_achieved_values != 0 else str(
            last_value)))

    def wait_for_alt(self, alt_min=30, timeout=30, max_err=5):
        """Wait for minimum altitude to be reached."""
        self.wait_altitude(alt_min - 1,
                           (alt_min + max_err),
                           relative=True,
                           timeout=timeout)

    ####################################################################################################################
    # Health / prearm ##################################################################################################
    ####################################################################################################################
    def wait_prearm_sys_status_healthy(self, timeout=60):
        tstart = time.time()
        while True:
            t2 = time.time()
            if t2 - tstart > timeout:
                self.progress("Prearm bit never went true.  Attempting arm to elicit reason from autopilot")
                self.arm_vehicle()
                raise TimeoutException("Prearm bit never went true")
            if self.sensor_has_state(mavutil.mavlink.MAV_SYS_STATUS_PREARM_CHECK, True, True, True):
                break

    @staticmethod
    def _check_sensor_state(m, sensor, present=True, enabled=True, healthy=True, do_assert=False):
        reported_present = m.onboard_control_sensors_present & sensor
        reported_enabled = m.onboard_control_sensors_enabled & sensor
        reported_healthy = m.onboard_control_sensors_health & sensor
        if present and not reported_present:
            if do_assert:
                raise NotAchievedException("Sensor not present")
            return False
        if not present and reported_present:
            if do_assert:
                raise NotAchievedException("Sensor present when it shouldn't be")
            return False
        if enabled and not reported_enabled:
            if do_assert:
                raise NotAchievedException("Sensor not enabled")
            return False
        if not enabled and reported_enabled:
            if do_assert:
                raise NotAchievedException("Sensor enabled when it shouldn't be")
            return False
        if healthy and not reported_healthy:
            if do_assert:
                raise NotAchievedException("Sensor not healthy")
            return False
        if not healthy and reported_healthy:
            if do_assert:
                raise NotAchievedException("Sensor healthy when it shouldn't be")
            return False
        return True

    def sensor_has_state(self, sensor, present=True, enabled=True, healthy=True, do_assert=False, verbose=False):
        # Fresh wait: callers loop on this, and the fresh SYS_STATUS paces them.
        try:
            m = self.wait_message('SYS_STATUS', timeout=5)
        except TimeoutException:
            raise TimeoutException("Did not receive SYS_STATUS")
        if verbose:
            self.progress("Status: %s" % str(mavutil.dump_message_verbose(sys.stdout, m)))
        return self._check_sensor_state(m, sensor, present, enabled, healthy, do_assert)

    def sensor_has_state_cached(self, sensor, present=True, enabled=True, healthy=True, max_age=5.0):
        """Non-blocking sensor_has_state from the cache; safe to call from the
        event loop. Returns None when no recent SYS_STATUS is available."""
        m = self.latest('SYS_STATUS', max_age=max_age)
        if m is None:
            return None
        return self._check_sensor_state(m, sensor, present, enabled, healthy, do_assert=False)

    def wait_ready_to_arm(self, timeout=120, require_absolute=True, check_prearm_bit=True):
        # wait for EKF checks to pass
        self.progress("Waiting for ready to arm")
        start = time.time()
        self.wait_ekf_happy(timeout=timeout, require_absolute=require_absolute)
        if require_absolute:
            self.wait_gps_sys_status_not_present_or_enabled_and_healthy()
        armable_time = time.time() - start
        if require_absolute:
            m = self.poll_home_position()
            if m is None:
                raise NotAchievedException("Did not receive a home position")
        if check_prearm_bit:
            self.wait_prearm_sys_status_healthy(timeout=timeout)
        self.progress("Took %u seconds to become armable" % armable_time)
        self.total_waiting_to_arm_time += armable_time
        self.waiting_to_arm_count += 1

    def wait_ekf_happy(self, timeout=30, require_absolute=True):
        """Wait for EKF to be happy"""

        """ if using SITL estimates directly """
        if (int(self.get_parameter('AHRS_EKF_TYPE')) == 10):
            return True

        # all of these must be set for arming to happen:
        required_value = (mavutil.mavlink.EKF_ATTITUDE |
                          mavutil.mavlink.ESTIMATOR_VELOCITY_HORIZ |
                          mavutil.mavlink.ESTIMATOR_VELOCITY_VERT |
                          mavutil.mavlink.ESTIMATOR_POS_HORIZ_REL |
                          mavutil.mavlink.ESTIMATOR_PRED_POS_HORIZ_REL)
        # none of these bits must be set for arming to happen:
        error_bits = (mavutil.mavlink.ESTIMATOR_CONST_POS_MODE |
                      mavutil.mavlink.ESTIMATOR_ACCEL_ERROR)
        if require_absolute:
            required_value |= (mavutil.mavlink.ESTIMATOR_POS_HORIZ_ABS |
                               mavutil.mavlink.ESTIMATOR_POS_VERT_ABS |
                               mavutil.mavlink.ESTIMATOR_PRED_POS_HORIZ_ABS)
            error_bits |= mavutil.mavlink.ESTIMATOR_GPS_GLITCH
        self.wait_ekf_flags(required_value, error_bits, timeout=timeout)

    def wait_ekf_flags(self, required_value, error_bits, timeout=30):
        self.progress("Waiting for EKF value %u" % required_value)
        last_print_time = 0
        tstart = time.time()
        with self.subscribe(types={'EKF_STATUS_REPORT'}) as sub:
            while timeout is None or time.time() < tstart + timeout:
                remaining = None if timeout is None else timeout - (time.time() - tstart)
                try:
                    m = sub.get(timeout=remaining if remaining is not None else 10)
                except TimeoutException:
                    continue
                current = m.flags
                errors = current & error_bits
                everything_ok = (errors == 0 and
                                 current & required_value == required_value)
                if everything_ok or time.time() - last_print_time > 1:
                    self.progress("Wait EKF.flags: required:%u current:%u errors=%u" %
                                  (required_value, current, errors))
                    last_print_time = time.time()
                if everything_ok:
                    self.progress("EKF Flags OK")
                    return True
        raise TimeoutException("Failed to get EKF.flags=%u" %
                               required_value)

    def wait_gps_sys_status_not_present_or_enabled_and_healthy(self, timeout=30):
        self.progress("Waiting for GPS health")
        tstart = time.time()
        with self.subscribe(types={'SYS_STATUS'}) as sub:
            while True:
                now = time.time()
                if now - tstart > timeout:
                    raise TimeoutException("GPS status bits did not become good")
                try:
                    m = sub.get(timeout=1)
                except TimeoutException:
                    continue
                if (not (m.onboard_control_sensors_present & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_GPS)):
                    self.progress("GPS not present")
                    if now > 20:
                        # it's had long enough to be detected....
                        return
                    continue
                if (not (m.onboard_control_sensors_enabled & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_GPS)):
                    self.progress("GPS not enabled")
                    continue
                if (not (m.onboard_control_sensors_health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_GPS)):
                    self.progress("GPS not healthy")
                    continue
                self.progress("GPS healthy")
                return

    ####################################################################################################################
    # Arming ###########################################################################################################
    ####################################################################################################################
    def armed(self):
        """Return true if vehicle is armed and safetyoff"""
        return self.mav.motors_armed()

    def arm_vehicle(self, timeout=20):
        """Arm vehicle with mavlink arm message."""
        self.progress("Arm motors with MAVLink cmd")
        self.run_cmd(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                     1,  # ARM
                     0,
                     0,
                     0,
                     0,
                     0,
                     0,
                     timeout=timeout)
        try:
            self.wait_armed()
        except TimeoutException:
            raise TimeoutException("Failed to ARM with mavlink")

    def wait_armed(self, timeout=20):
        tstart = time.time()
        while time.time() - tstart < timeout:
            self.wait_heartbeat()
            if self.mav.motors_armed():
                self.progress("Motors ARMED")
                return
        raise TimeoutException("Did not become armed")

    def disarm_vehicle(self, timeout=60, force=False):
        """Disarm vehicle with mavlink disarm message."""
        self.progress("Disarm motors with MAVLink cmd")
        p2 = 0
        if force:
            p2 = 21196  # magic force disarm value
        self.run_cmd(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                     0,  # DISARM
                     p2,
                     0,
                     0,
                     0,
                     0,
                     0,
                     timeout=timeout)
        return self.wait_disarmed()

    def wait_disarmed_default_wait_time(self):
        return 30

    def wait_disarmed(self, timeout=None, tstart=None):
        if timeout is None:
            timeout = self.wait_disarmed_default_wait_time()
        self.progress("Waiting for DISARM")
        if tstart is None:
            tstart = time.time()
        last_print_time = 0
        while True:
            now = time.time()
            delta = now - tstart
            if delta > timeout:
                raise TimeoutException("Failed to DISARM within %fs" %
                                       (timeout,))
            if now - last_print_time > 1:
                self.progress("Waiting for disarm (%.2fs so far of allowed %.2f)" % (delta, timeout))
                last_print_time = now
            self.wait_heartbeat(quiet=True)
            if not self.mav.motors_armed():
                self.progress("DISARMED after %.2f seconds (allowed=%.2f)" %
                              (delta, timeout))
                return True

    def wait_landed_and_disarmed(self, min_alt=None, timeout=None, disarm_timeout=None):
        """Wait to be landed and disarmed"""
        if min_alt is None:
            min_alt = self.LAND_MIN_ALT
        if timeout is None:
            timeout = self.LAND_TIMEOUT
        m = self.wait_message('GLOBAL_POSITION_INT', timeout=5, allow_cached_age=1.0)
        alt = m.relative_alt / 1000.0  # mm -> m
        if alt > min_alt:
            self.wait_for_alt(min_alt, timeout=timeout)
        self.wait_disarmed(timeout=disarm_timeout)

    ####################################################################################################################
    # Mission ##########################################################################################################
    ####################################################################################################################
    def wait_waypoint(self,
                      wpnum_start,
                      wpnum_end,
                      allow_skip=True,
                      max_dist=2,
                      timeout=400):
        """Wait for waypoint ranges."""
        tstart = time.time()
        # this message arrives after we set the current WP
        start_wp = self.waypoint_current()
        current_wp = start_wp
        mode = self.mav.flightmode

        self.progress("wait for waypoint ranges start=%u end=%u"
                      % (wpnum_start, wpnum_end))

        last_wp_msg = 0
        while time.time() < tstart + timeout:
            seq = self.waypoint_current()
            m = self.wait_message('NAV_CONTROLLER_OUTPUT', timeout=5)
            wp_dist = m.wp_dist
            m = self.wait_message('VFR_HUD', timeout=5)

            # if we changed mode, fail
            if self.mav.flightmode != mode:
                raise WaitWaypointTimeout('Exited %s mode' % mode)

            if time.time() - last_wp_msg > 1:
                self.progress("WP %u (wp_dist=%u Alt=%.02f), current_wp: %u,"
                              "wpnum_end: %u" %
                              (seq, wp_dist, m.alt, current_wp, wpnum_end))
                last_wp_msg = time.time()
            if seq == current_wp + 1 or (seq > current_wp + 1 and allow_skip):
                self.progress("test: Starting new waypoint %u" % seq)
                tstart = time.time()
                current_wp = seq
            if current_wp == wpnum_end and wp_dist < max_dist:
                self.progress("Reached final waypoint %u" % seq)
                return True
            if seq >= 255:
                self.progress("Reached final waypoint %u" % seq)
                return True
            if seq > current_wp + 1:
                raise WaitWaypointTimeout(("Skipped waypoint! Got wp %u expected %u"
                                           % (seq, current_wp + 1)))
        raise WaitWaypointTimeout("Timed out waiting for waypoint %u of %u" %
                                  (wpnum_end, wpnum_end))

    def send_all_waypoints(self, timeout=60):
        """send all waypoints to vehicle"""
        with self._mission_lock:
            # Subscribe before clear/count so no MISSION_REQUEST can slip by.
            with self.subscribe(types={'MISSION_REQUEST', 'WAYPOINT_REQUEST'}) as sub:
                self.txc.waypoint_clear_all_send()
                self.progress("Sending %d waypoints" % self.wploader.count())
                if self.wploader.count() == 0:
                    return
                self.txc.waypoint_count_send(self.wploader.count())
                tstart = time.time()
                while True:
                    now = time.time()
                    if now - tstart > timeout:
                        self.progress("Failed to send Mission")
                        return
                    try:
                        msg = sub.get(timeout=3)
                    except TimeoutException:
                        continue
                    if msg.seq >= self.wploader.count():
                        self.progress("Request for bad waypoint %u (max %u)" % (msg.seq, self.wploader.count()))
                        return
                    wp = self.wploader.wp(msg.seq)
                    wp_send = self.wp_to_mission_item_int(wp)

                    self.tx.send(wp_send)
                    self.progress("Sent waypoint %u : %s" % (msg.seq, self.wploader.wp(msg.seq)))
                    if msg.seq == self.wploader.count() - 1:
                        self.progress("Sent all %u waypoints" % self.wploader.count())
                        return

    def get_all_waypoints(self, timeout=30):
        with self._mission_lock:
            self.progress("Requesting Mission item count")
            with self.subscribe(types={'WAYPOINT_COUNT', 'MISSION_COUNT',
                                       'WAYPOINT', 'MISSION_ITEM', 'MISSION_ITEM_INT'}) as sub:
                self.txc.waypoint_request_list_send()
                tstart = time.time()
                while True:
                    now = time.time()
                    if now - tstart > timeout:
                        self.progress("Failed to get Mission total item")
                        return
                    try:
                        msg = sub.get(timeout=3)
                    except TimeoutException:
                        continue
                    if msg.get_type() not in ('WAYPOINT_COUNT', 'MISSION_COUNT'):
                        continue
                    self.wp_expected_count = msg.count
                    self.progress("Got %s waypoints to get" % msg.count)
                    self.wploader.clear()
                    break
                for seq in self.missing_wps_to_request():
                    self.wp_requested[seq] = time.time()
                    self.progress("Requesting waypoint %d" % seq)
                    self.tx.mission_request_int_send(self.target_system, self.target_component, seq)
                    tstart = time.time()
                    while True:
                        now = time.time()
                        if now - tstart > timeout:
                            self.progress("Failed to get Waypoint %d" % seq)
                            return
                        try:
                            msg = sub.get(timeout=3)
                        except TimeoutException:
                            continue
                        if msg.get_type() not in ('WAYPOINT', 'MISSION_ITEM', 'MISSION_ITEM_INT'):
                            continue
                        if msg.get_type() == 'MISSION_ITEM_INT':
                            if getattr(msg, 'mission_type', 0) != 0:
                                # this is not a mission item, likely fence
                                return
                            # our internal structure assumes MISSION_ITEM
                            msg = self.wp_from_mission_item_int(msg)
                        if msg.seq < self.wploader.count():
                            return
                        if msg.seq + 1 > self.wp_expected_count:
                            self.progress("Unexpected waypoint number %u - expected %u" % (msg.seq, self.wploader.count()))
                        self.wp_received[msg.seq] = msg

                        next_seq = self.wploader.count()
                        while next_seq in self.wp_received:
                            m = self.wp_received.pop(next_seq)
                            self.wploader.add(m)
                            next_seq += 1
                        if self.wploader.count() != self.wp_expected_count:
                            self.progress("m.seq=%u expected_count=%u" % (msg.seq, self.wp_expected_count))
                            break
                        if self.wploader.count() == self.wp_expected_count:
                            self.progress("Got all Waypoints")
                            break
            for i in range(self.wploader.count()):
                w = self.wploader.wp(i)
                self.logger.debug("%u %u %.10f %.10f %f p1=%.1f p2=%.1f p3=%.1f p4=%.1f cur=%u auto=%u" % (
                    w.command, w.frame, w.x, w.y, w.z,
                    w.param1, w.param2, w.param3, w.param4,
                    w.current, w.autocontinue))

            self.wp_requested = {}
            self.wp_received = {}
            return self.wploader.count()

    def missing_wps_to_request(self):
        ret = []
        tnow = time.time()
        next_seq = self.wploader.count()
        for i in range(2 * self.wp_expected_count):
            seq = next_seq + i
            if seq + 1 > self.wp_expected_count:
                continue
            if seq in self.wp_requested and tnow - self.wp_requested[seq] < 2:
                continue
            ret.append(seq)
        return ret

    def wp_to_mission_item_int(self, wp):
        """convert a MISSION_ITEM to a MISSION_ITEM_INT. We always send as MISSION_ITEM_INT
           to give cm level accuracy"""
        if wp.get_type() == 'MISSION_ITEM_INT':
            return wp
        wp_int = mavutil.mavlink.MAVLink_mission_item_int_message(wp.target_system,
                                                                  wp.target_component,
                                                                  wp.seq,
                                                                  wp.frame,
                                                                  wp.command,
                                                                  wp.current,
                                                                  wp.autocontinue,
                                                                  wp.param1,
                                                                  wp.param2,
                                                                  wp.param3,
                                                                  wp.param4,
                                                                  int(wp.x * 1.0e7),
                                                                  int(wp.y * 1.0e7),
                                                                  wp.z)
        return wp_int

    def wp_from_mission_item_int(self, wp):
        '''convert a MISSION_ITEM_INT to a MISSION_ITEM'''
        wp2 = mavutil.mavlink.MAVLink_mission_item_message(wp.target_system,
                                                           wp.target_component,
                                                           wp.seq,
                                                           wp.frame,
                                                           wp.command,
                                                           wp.current,
                                                           wp.autocontinue,
                                                           wp.param1,
                                                           wp.param2,
                                                           wp.param3,
                                                           wp.param4,
                                                           wp.x * 1.0e-7,
                                                           wp.y * 1.0e-7,
                                                           wp.z)
        # preserve srcSystem as that is used for naming waypoint file
        wp2._header.srcSystem = wp.get_srcSystem()
        wp2._header.srcComponent = wp.get_srcComponent()
        return wp2

    def init_wp(self):
        last_home = self.home_position_as_mav_location()
        self.wploader.clear()
        self.wploader.target_system = self.target_system
        self.wploader.target_component = self.target_system
        self.add_waypoint(last_home.lat, last_home.lng, last_home.alt)

    def add_waypoint(self, lat, lon, alt):
        self.wploader.add_latlonalt(lat, lon, alt, terrain_alt=False)

    def add_wp_rtl(self):
        p = mavutil.mavlink.MAVLink_mission_item_message(self.target_system,
                                                         self.target_component,
                                                         0,
                                                         mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                                                         mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                                                         0, 0, 0, 0, 0, 0,
                                                         0, 0, 0)
        self.wploader.add(p)

    def wp_mission_start(self):
        # As we don't have RC radio here, we trigger mission start with MAVLink.
        self.run_cmd(mavutil.mavlink.MAV_CMD_MISSION_START,
                     0,
                     0,
                     0,
                     0,
                     0,
                     0,
                     0,
                     target_sysid=self.target_system,
                     target_compid=self.target_system,
                     )

    def wp_clear(self):
        self.run_cmd(mavutil.mavlink.MAV_CMD_MISSION_CLEAR_ALL,
                     0,
                     0,
                     0,
                     0,
                     0,
                     0,
                     0,
                     target_sysid=self.target_system,
                     target_compid=self.target_system
                     )

    ####################################################################################################################
    # GUIDED-mode movement (shared) ####################################################################################
    ####################################################################################################################
    def go_to_ned(self, north: float, east: float, down: float, look_at_target=False):
        self.progress(f"Moving to ned position (north={north}, east={east}, down={down})")

        self.tx.set_position_target_local_ned_send(
            0,  # timestamp
            self.target_system,  # target system_id
            self.target_component,  # target component_id
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,  # coordinate frame
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_VX_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_VY_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_VZ_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_AX_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_AY_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_AZ_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_FORCE_SET |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_IGNORE |
            (mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE if look_at_target else 0),
            float(north),  # north offset to origin(home) (m)
            float(east),  # east offset to origin(home) (m)
            float(down),  # down offset to origin(home) (m)
            0,  # x velocity (m/s)
            0,  # y velocity (m/s)
            0,  # z velocity (m/s)
            0,  # x acceleration (m/s^2)
            0,  # y acceleration (m/s^2)
            0,  # z acceleration (m/s^2)
            0,  # yaw heading (radians)
            0,  # yaw_rate (rad/s)
        )

    ####################################################################################################################
    # Speed control ####################################################################################################
    ####################################################################################################################
    def change_ground_speed(self, new_v):
        """Change groundspeed (m/s); doesn't affect vertical speed."""
        self.send_cmd(
            mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,  # command
            mavutil.mavlink.SPEED_TYPE_GROUNDSPEED,  # speed type
            new_v,  # new velocity (m/s)
            -1,  # new throttle value, -1 remains it the same
            0,
            0,
            0,
            0,
            target_sysid=self.target_system,
            target_compid=self.target_component
        )

    def change_climb_speed(self, new_v):
        self.send_cmd(
            mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,  # command
            mavutil.mavlink.SPEED_TYPE_CLIMB_SPEED,  # speed type
            new_v,  # new velocity (m/s)
            -1,  # new throttle value, -1 remains it the same
            0,
            0,
            0,
            0,
            target_sysid=self.target_system,
            target_compid=self.target_component
        )

    def change_descent_speed(self, new_v):
        self.send_cmd(
            mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,  # command
            mavutil.mavlink.SPEED_TYPE_DESCENT_SPEED,  # speed type
            new_v,  # new velocity (m/s)
            -1,  # new throttle value, -1 remains it the same
            0,
            0,
            0,
            0,
            target_sysid=self.target_system,
            target_compid=self.target_component
        )

    def change_air_speed(self, new_v):
        self.send_cmd(
            mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,  # command
            mavutil.mavlink.SPEED_TYPE_AIRSPEED,  # speed type
            new_v,  # new velocity (m/s)
            -1,  # new throttle value, -1 remains it the same
            0,
            0,
            0,
            0,
            target_sysid=self.target_system,
            target_compid=self.target_component
        )

    ####################################################################################################################
    # Telemetry getters ################################################################################################
    ####################################################################################################################
    def get_current_target(self, timeout=10):
        """Get and print POSITION_TARGET_GLOBAL_INT msg send by the drone.
           those message are always in MAV_FRAME_GLOBAL_INT frame."""
        msg = self.wait_message('POSITION_TARGET_GLOBAL_INT', timeout=timeout)
        self.progress("Received local target: %s" % str(msg))
        return location(msg.lat_int * 1.0e-7, msg.lon_int * 1.0e-7, msg.alt, msg.yaw)

    def get_ned_position(self, timeout=10, allow_cached_age=2.0):
        """Latest LOCAL_POSITION_NED as a Local_pos.

        Pass allow_cached_age=None to wait for a fresh message (paces polling
        loops at the stream rate)."""
        try:
            msg = self.wait_message('LOCAL_POSITION_NED', timeout=timeout,
                                    allow_cached_age=allow_cached_age)
        except TimeoutException:
            raise TimeoutException("Failed to get LOCAL_POSITION_NED")
        self.progress("Received local position: %s" % str(msg))
        return Local_pos(x=msg.x, y=msg.y, z=msg.z)

    def get_message(self, msg_type, timeout=10):
        """Get most recent message of the given type sent by the vehicle."""
        try:
            msg = self.wait_message(msg_type, timeout=timeout, allow_cached_age=2.0)
        except TimeoutException:
            raise TimeoutException("Failed to get %s message" % msg_type)
        self.progress("Message %s received: %s" % (msg_type, msg))
        return msg

    def get_last_message(self, msg_type):
        message = self.mav.messages[msg_type]
        timestamp = self.mav.time_since(msg_type)
        self.progress("Message %s received (%s): %s" % (msg_type, timestamp, message))
        return message

    def get_raw_status_message(self, timeout=5):
        return self.get_message("SYS_STATUS", timeout=timeout)

    def get_sensor_status(self, timeout=5, sensor_dict=None):
        if sensor_dict is None:
            sensor_dict = {
                "gyro": mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_GYRO,
                "accelerometer": mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_ACCEL,
                "gps": mavutil.mavlink.MAV_SYS_STATUS_SENSOR_GPS,
                "altitude_control": mavutil.mavlink.MAV_SYS_STATUS_SENSOR_Z_ALTITUDE_CONTROL,
                "position_control": mavutil.mavlink.MAV_SYS_STATUS_SENSOR_XY_POSITION_CONTROL,
                "radio_receiver": mavutil.mavlink.MAV_SYS_STATUS_SENSOR_RC_RECEIVER,
                "motor_output": mavutil.mavlink.MAV_SYS_STATUS_SENSOR_MOTOR_OUTPUTS,
                "battery": mavutil.mavlink.MAV_SYS_STATUS_SENSOR_BATTERY,
                "pre_arm_check": mavutil.mavlink.MAV_SYS_STATUS_PREARM_CHECK,
            }
        sys_msg = self.get_message("SYS_STATUS", timeout)
        s_data = {}
        for key, value in sensor_dict.items():
            s_data[key] = {
                "present": bool(sys_msg.onboard_control_sensors_present & value),
                "enabled": bool(sys_msg.onboard_control_sensors_enabled & value),
                "health": bool(sys_msg.onboard_control_sensors_health & value),
            }
        return s_data

    def get_battery_info(self, timeout=5):
        sys_msg = self.get_last_message("SYS_STATUS")
        return {
            "voltage": sys_msg.voltage_battery,
            "current": sys_msg.current_battery,
            "battery_remaining": sys_msg.battery_remaining
        }

    def get_error_info(self, timeout=5):
        sys_msg = self.get_last_message("SYS_STATUS")
        autopilot_errors = [sys_msg.errors_count1, sys_msg.errors_count2, sys_msg.errors_count3, sys_msg.errors_count4]
        autopilot_errors = [err for err in autopilot_errors if err != 0]
        return {
            "communication_drop_rate": sys_msg.drop_rate_comm,
            "communication_errors": sys_msg.errors_comm,
            "autopilot_errors": autopilot_errors
        }

    def get_gps_info(self, timeout=5):
        return self.get_last_message("GLOBAL_POSITION_INT")

    def get_raw_gps(self, timeout=5):
        return self.get_last_message("GPS_RAW_INT")

    def get_ned_info(self, timeout=5):
        return self.get_last_message("LOCAL_POSITION_NED")

    def get_general_info(self, timeout=5):
        return self.get_last_message("VFR_HUD")

    def get_compass_info(self, timeout=5):
        # MAG_CAL_REPORT is only emitted during a compass calibration, so it
        # is normally absent (always, in SITL).
        if "MAG_CAL_REPORT" not in self.mav.messages:
            return None
        return self.get_last_message("MAG_CAL_REPORT")

    ####################################################################################################################
    # Misc #############################################################################################################
    ####################################################################################################################
    def set_servo(self, channel, pwm):
        """Send a PWM signal to a servo on the given channel."""
        self.run_cmd(
            mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
            channel,  # p1: servo channel (1-based)
            pwm,      # p2: PWM value in microseconds
            0, 0, 0, 0, 0,
        )

    def set_sim_speedup(self, value, timeout=10):
        """SITL only: set SIM_SPEEDUP for faster-than-realtime simulation."""
        self.progress("Setting parameter SIM_SPEEDUP to %s" % (value))
        self.txc.param_set_send(
            b"SIM_SPEEDUP",  # parameter name
            value,
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32
        )
