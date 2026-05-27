import copy
import math
import os
import sys
import time
import logging
import asyncio

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


class MsgRcvTimeoutException(TimeoutException):
    """Thrown when fails to receive an expected message"""
    pass


class NotAchievedException(ErrorException):
    """Thrown when fails to achieve a goal"""
    pass


class PreconditionFailedException(ErrorException):
    """Thrown when a precondition for a command is not met"""
    pass


class MovementException(ErrorException):
    """Thrown when movement assumptions are violated"""
    pass


########################################################################################################################
# Plane ################################################################################################################
########################################################################################################################
class Plane:
    """ArduPilot Plane class.

    Mirrors the structure of uav_api.copter.Copter but targets ArduPlane (fixed-wing
    and QuadPlane / VTOL hybrids) running in GUIDED mode.

    Heavily based on ArduPilot's autotest harness for ArduPlane:
    https://github.com/ArduPilot/ardupilot/blob/master/Tools/autotest/arduplane.py
    Test-only scaffolding has been removed; only commands and waits useful for
    real-world GUIDED operation are kept.
    """

    def __init__(self, default_stream_rate=5, sysid=1):
        self.wp_received = {}
        self.mav = None
        self.streamrate = default_stream_rate
        self.target_system = sysid
        self.target_component = 1
        self.heartbeat_interval_ms = 1000
        self.last_heartbeat_time_ms = None
        self.last_heartbeat_time_wc_s = 0
        self.in_drain_mav = False
        self.total_waiting_to_arm_time = 0
        self.waiting_to_arm_count = 0
        self.wploader = mavwp.MAVWPLoader()
        self.wp_requested = {}
        self.wp_expected_count = 0
        self.logger = logging.getLogger("PLANE")

    ########################################################################################################################
    # Distance / coordinate helpers ########################################################################################
    ########################################################################################################################
    @staticmethod
    def get_distance(loc1, loc2):
        """Get ground distance between two locations."""
        return Plane.get_distance_accurate(loc1, loc2)

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
        return Plane.get_latlon_attr(loc, ["lat", "latitude"])

    @staticmethod
    def get_lon_attr(loc):
        return Plane.get_latlon_attr(loc, ["lng", "lon", "longitude"])

    @staticmethod
    def get_distance_int(loc1, loc2):
        loc1_lat = Plane.get_lat_attr(loc1)
        loc2_lat = Plane.get_lat_attr(loc2)
        loc1_lon = Plane.get_lon_attr(loc1)
        loc2_lon = Plane.get_lon_attr(loc2)
        return Plane.get_distance_accurate(
            mavutil.location(loc1_lat * 1e-7, loc1_lon * 1e-7),
            mavutil.location(loc2_lat * 1e-7, loc2_lon * 1e-7))

    def progress(self, text):
        self.logger.info(text)

    def longitude_scale(self, lat):
        ret = math.cos(lat * (math.radians(1)))
        self.logger.debug("scale=%f" % ret)
        return ret

    def mav_location(self, lat: float, long: float, alt: float):
        return mavutil.location(lat, long, alt, 0)

    @staticmethod
    def euler_to_quaternion(roll_rad, pitch_rad, yaw_rad):
        """Convert Euler angles (radians, ZYX/Tait-Bryan) to a [w, x, y, z] quaternion."""
        cy = math.cos(yaw_rad * 0.5)
        sy = math.sin(yaw_rad * 0.5)
        cp = math.cos(pitch_rad * 0.5)
        sp = math.sin(pitch_rad * 0.5)
        cr = math.cos(roll_rad * 0.5)
        sr = math.sin(roll_rad * 0.5)
        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy
        return [w, x, y, z]

    ########################################################################################################################
    # Connection ###########################################################################################################
    ########################################################################################################################
    def connect(self, connection_string='udpin:0.0.0.0:14550'):
        """Open the MAVLink connection, enforce MAVLink2, set a default streamrate,
        and install heartbeat / message hooks."""
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
        self.set_streamrate(self.streamrate)
        self.mav.message_hooks.append(self.message_hook)
        self.mav.idle_hooks.append(self.idle_hook)

    def set_streamrate(self, streamrate, timeout=20):
        tstart = time.time()
        while True:
            if time.time() - tstart > timeout:
                raise TimeoutException("Failed to set streamrate")
            self.mav.mav.request_data_stream_send(
                self.target_system,
                self.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                streamrate,
                1)
            m = self.mav.recv_match(type='SYSTEM_TIME', blocking=True, timeout=1)
            if m is not None:
                break

    def rate_to_interval_us(self, rate):
        return 1 / float(rate) * 1000000.0

    def set_message_rate_hz(self, id, rate_hz):
        """Set a message rate in Hz; 0 = original, -1 = disable."""
        if type(id) == str:
            id = eval("mavutil.mavlink.MAVLINK_MSG_ID_%s" % id)
        if rate_hz == 0 or rate_hz == -1:
            set_interval = rate_hz
        else:
            set_interval = self.rate_to_interval_us(rate_hz)
        self.run_cmd(mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                     id, set_interval, 0, 0, 0, 0, 0)

    ########################################################################################################################
    # Parameters ###########################################################################################################
    ########################################################################################################################
    def send_set_parameter_direct(self, name, value):
        self.mav.mav.param_set_send(self.target_system, 1, name.encode('ascii'),
                                    value, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)

    def send_set_parameter(self, name, value, verbose=False):
        if verbose:
            self.progress("Send set param for (%s) (%f)" % (name, value))
        return self.send_set_parameter_direct(name, value)

    def set_parameter(self, name, value, **kwargs):
        self.set_parameters({name: value}, **kwargs)

    def set_parameters(self, parameters, add_to_context=True, epsilon_pct=0.00001, retries=None, verbose=True):
        want = copy.copy(parameters)
        self.progress("set_parameters: (%s)" % str(want))
        self.drain_mav()
        if len(want) == 0:
            return
        if retries is None:
            retries = (len(want) + 1) * 5

        param_value_messages = []

        def add_param_value(mav, m):
            if m.get_type() != "PARAM_VALUE":
                return
            param_value_messages.append(m)

        self.install_message_hook(add_param_value)

        original_values = {}
        autopilot_values = {}
        for i in range(retries):
            self.drain_mav(quiet=True)
            received = set()
            for (name, value) in want.items():
                self.progress("%s want=%f autopilot=%s" % (name, value, autopilot_values.get(name, 'None')))
                if name not in autopilot_values:
                    self.send_get_parameter_direct(name)
                    self.progress("Requesting (%s) (retry=%u)" % (name, i))
                    continue
                delta = abs(autopilot_values[name] - value)
                if delta <= epsilon_pct * 0.01 * abs(value):
                    self.progress("%s is now %f" % (name, autopilot_values[name]))
                    received.add(name)
                    continue
                self.progress("Sending set (%s) to (%f) (old=%f)" % (name, value, original_values[name]))
                self.send_set_parameter_direct(name, value)
            for name in received:
                del want[name]
            if len(want):
                self.wait_heartbeat()
            for m in param_value_messages:
                if m.param_id in want:
                    self.progress("Received wanted PARAM_VALUE %s=%f" % (str(m.param_id), m.param_value))
                    autopilot_values[m.param_id] = m.param_value
                    if m.param_id not in original_values:
                        original_values[m.param_id] = m.param_value
            param_value_messages = []

        self.remove_message_hook(add_param_value)
        if len(want) == 0:
            return
        raise ValueError("Failed to set parameters (%s)" % want)

    def get_parameter(self, *args, **kwargs):
        return self.get_parameter_direct(*args, **kwargs)

    def send_get_parameter_direct(self, name):
        encname = name
        if sys.version_info.major >= 3 and type(encname) != bytes:
            encname = bytes(encname, 'ascii')
        self.mav.mav.param_request_read_send(self.target_system, 1, encname, -1)

    def get_parameter_direct(self, name, attempts=1, timeout=60, verbose=True):
        while attempts > 0:
            attempts -= 1
            if verbose:
                self.progress("Sending param_request_read for (%s)" % name)
            self.drain_mav(quiet=True)
            tstart = time.time()
            self.send_get_parameter_direct(name)
            while True:
                now = time.time()
                delta_time = now - tstart
                if delta_time > timeout:
                    break
                m = self.mav.recv_match(type='PARAM_VALUE', blocking=True, timeout=0.1)
                if verbose:
                    self.progress("get_parameter(%s): %s" % (name, str(m)))
                if m is None:
                    continue
                if m.param_id == name:
                    return m.param_value
        raise NotAchievedException("Failed to retrieve parameter (%s)" % name)

    ########################################################################################################################
    # Heartbeat / hooks / draining #########################################################################################
    ########################################################################################################################
    def idle_hook(self, mav):
        if self.in_drain_mav:
            return

    def message_hook(self, mav, msg):
        if msg.get_type() == 'STATUSTEXT':
            self.progress("AP: %s" % msg.text)
        self.idle_hook(mav)
        self.do_heartbeats()

    def install_message_hook(self, hook):
        self.mav.message_hooks.append(hook)

    def remove_message_hook(self, hook):
        if self.mav is None:
            return
        oldlen = len(self.mav.message_hooks)
        self.mav.message_hooks = list(filter(lambda x: x != hook, self.mav.message_hooks))
        if len(self.mav.message_hooks) == oldlen:
            raise NotAchievedException("Failed to remove hook")

    def do_heartbeats(self, force=False):
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
            self.mav.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                                        mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                                        0, 0, 0)

    def drain_mav_unparsed(self, mav=None, quiet=True, freshen_sim_time=False):
        if mav is None:
            mav = self.mav
        self.in_drain_mav = True
        count = 0
        tstart = time.time()
        while True:
            this = self.mav.recv(1000000)
            if len(this) == 0:
                break
            count += len(this)
        if quiet:
            return
        tdelta = time.time() - tstart
        rate = "instantly" if tdelta == 0 else "%f/s" % (count / float(tdelta),)
        self.progress("Drained %u bytes from mav (%s). Unparsed." % (count, rate))
        self.in_drain_mav = False

    def drain_mav(self, mav=None, unparsed=False, quiet=True):
        if unparsed:
            return self.drain_mav_unparsed(quiet=quiet, mav=mav)
        if mav is None:
            mav = self.mav
        count = 0
        tstart = time.time()
        while mav.recv_match(blocking=False) is not None:
            count += 1
        if quiet:
            return
        tdelta = time.time() - tstart
        rate = "instantly" if tdelta == 0 else "%f/s" % (count / float(tdelta),)
        self.progress("Drained %u messages from mav (%s)" % (count, rate))

    ########################################################################################################################
    # COMMAND_LONG / COMMAND_INT ###########################################################################################
    ########################################################################################################################
    def send_cmd(self, command, p1, p2, p3, p4, p5, p6, p7,
                 target_sysid=None, target_compid=None):
        """Send a COMMAND_LONG (fire-and-forget)."""
        if target_sysid is None:
            target_sysid = self.target_system
        if target_compid is None:
            target_compid = 1
        try:
            command_name = mavutil.mavlink.enums["MAV_CMD"][command].name
        except KeyError:
            command_name = "UNKNOWN=%u" % command
        self.progress("Sending COMMAND_LONG to (%u,%u) (%s) (p1=%f p2=%f p3=%f p4=%f p5=%f p6=%f p7=%f)" %
                      (target_sysid, target_compid, command_name, p1, p2, p3, p4, p5, p6, p7))
        self.mav.mav.command_long_send(target_sysid, target_compid, command, 1,
                                       p1, p2, p3, p4, p5, p6, p7)

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
        self.mav.mav.command_int_send(target_sysid, target_compid, frame, command,
                                      current, autocontinue, p1, p2, p3, p4, x, y, z)

    def run_cmd(self, command, p1, p2, p3, p4, p5, p6, p7,
                want_result=mavutil.mavlink.MAV_RESULT_ACCEPTED,
                target_sysid=None, target_compid=None,
                timeout=10, quiet=False):
        """Send a COMMAND_LONG and block until a matching COMMAND_ACK arrives."""
        self.drain_mav_unparsed()
        self.send_cmd(command, p1, p2, p3, p4, p5, p6, p7,
                      target_sysid=target_sysid, target_compid=target_compid)
        self.run_cmd_get_ack(command, want_result, timeout, quiet=quiet)

    def run_cmd_int(self, command, p1, p2, p3, p4, x, y, z,
                    frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    want_result=mavutil.mavlink.MAV_RESULT_ACCEPTED,
                    target_sysid=None, target_compid=None,
                    timeout=10, quiet=False):
        """Send a COMMAND_INT and block for ACK."""
        self.drain_mav_unparsed()
        self.send_cmd_int(command, p1, p2, p3, p4, x, y, z,
                          frame=frame,
                          target_sysid=target_sysid, target_compid=target_compid)
        self.run_cmd_get_ack(command, want_result, timeout, quiet=quiet)

    def run_cmd_get_ack(self, command, want_result, timeout, quiet=False):
        tstart = time.time()
        while True:
            delta_time = time.time() - tstart
            if delta_time > timeout:
                raise TimeoutException("Did not get good COMMAND_ACK within %fs" % timeout)
            m = self.mav.recv_match(type='COMMAND_ACK', blocking=True, timeout=0.1)
            if m is None:
                continue
            if not quiet:
                self.progress("ACK received: %s (%fs)" % (str(m), delta_time))
            if m.command == command:
                if m.result != want_result:
                    raise ValueError("Expected %s got %s" % (
                        mavutil.mavlink.enums["MAV_RESULT"][want_result].name,
                        mavutil.mavlink.enums["MAV_RESULT"][m.result].name))
                break

    ########################################################################################################################
    # Mode handling ########################################################################################################
    ########################################################################################################################
    def run_cmd_do_set_mode(self, mode, timeout=30,
                            want_result=mavutil.mavlink.MAV_RESULT_ACCEPTED):
        base_mode = mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
        custom_mode = self.get_mode_from_mode_mapping(mode)
        self.run_cmd(mavutil.mavlink.MAV_CMD_DO_SET_MODE,
                     base_mode, custom_mode, 0, 0, 0, 0, 0,
                     want_result=want_result, timeout=timeout)

    def do_set_mode_via_command_long(self, mode, timeout=30):
        tstart = time.time()
        want_custom_mode = self.get_mode_from_mode_mapping(mode)
        while True:
            remaining = timeout - (time.time() - tstart)
            if remaining <= 0:
                raise TimeoutException("Failed to change mode")
            self.run_cmd_do_set_mode(mode, timeout=10)
            m = self.mav.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
            if m is None:
                raise ErrorException("Heartbeat not received")
            self.progress("Got mode=%u want=%u" % (m.custom_mode, want_custom_mode))
            if m.custom_mode == want_custom_mode:
                return

    def change_mode(self, mode, timeout=60):
        """Change plane flight mode. Returns True on success, False on failure."""
        try:
            self.wait_heartbeat()
            self.progress("Changing mode to %s" % mode)
            self.do_set_mode_via_command_long(mode)
        except Exception:
            return False
        return True

    def mode_is(self, mode, cached=False, drain_mav=True):
        if not cached:
            self.wait_heartbeat(drain_mav=drain_mav)
        try:
            return self.get_mode_from_mode_mapping(self.mav.flightmode) == self.get_mode_from_mode_mapping(mode)
        except Exception:
            pass
        return self.mav.messages['HEARTBEAT'].custom_mode == mode

    def wait_mode(self, mode, timeout=60):
        self.progress("Waiting for mode %s" % mode)
        tstart = time.time()
        while not self.mode_is(mode, drain_mav=False):
            custom_num = self.mav.messages['HEARTBEAT'].custom_mode
            self.progress("mav.flightmode=%s Want=%s custom=%u" %
                          (self.mav.flightmode, mode, custom_num))
            if timeout is not None and time.time() > tstart + timeout:
                raise WaitModeTimeout("Did not change mode")
        self.progress("Got mode %s" % mode)

    def get_mode_from_mode_mapping(self, mode):
        """Resolve a mode name or number to its numeric value.

        Uses pymavlink's vehicle-aware mode_mapping(), which after heartbeat-based
        detection returns the ArduPlane mode set (MANUAL, FBWA, FBWB, CRUISE,
        AUTOTUNE, AUTO, RTL, LOITER, TAKEOFF, GUIDED, QSTABILIZE, QHOVER, QLOITER,
        QLAND, QRTL, QAUTOTUNE, QACRO, THERMAL, ...).
        """
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

    ########################################################################################################################
    # Home position ########################################################################################################
    ########################################################################################################################
    def distance_to_home(self, use_cached_home=False):
        m = self.mav.messages.get("HOME_POSITION", None)
        if use_cached_home is False or m is None:
            m = self.poll_home_position(quiet=True)
        here = self.mav.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
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
                self.run_cmd(mavutil.mavlink.MAV_CMD_GET_HOME_POSITION,
                             0, 0, 0, 0, 0, 0, 0, quiet=quiet)
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
        return mavutil.location(m.latitude * 1.0e-7, m.longitude * 1.0e-7,
                                m.altitude * 1.0e-3, 0)

    def request_home_message(self, message_id=None, timeout=5):
        self.progress("Requesting HOME_POSITION")
        self.mav.mav.command_long_send(
            self.target_system, self.target_component,
            mavutil.mavlink.MAV_CMD_GET_HOME_POSITION,
            0, 0, 0, 0, 0, 0, 0, 0)

    def get_home_position(self, timeout=10):
        self.request_home_message()
        home_message = self.get_message("HOME_POSITION", timeout=timeout)
        return home_message.to_dict()

    def set_home(self, timeout=10):
        """Set the home position to the vehicle's current position."""
        self.run_cmd(mavutil.mavlink.MAV_CMD_DO_SET_HOME,
                     1, 0, 0, 0, 0, 0, 0, timeout=timeout)

    ########################################################################################################################
    # Wait helpers #########################################################################################################
    ########################################################################################################################
    def wait_altitude(self, altitude_min, altitude_max, relative=False, timeout=30, **kwargs):
        assert altitude_min <= altitude_max, "Minimum altitude should be less than maximum altitude."

        def get_altitude(alt_relative=False, timeout2=30):
            msg = self.mav.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=timeout2)
            if msg:
                if alt_relative:
                    return msg.relative_alt / 1000.0
                return msg.alt / 1000.0
            raise MsgRcvTimeoutException("Failed to get Global Position")

        def validator(value2, target2=None):
            return altitude_min <= value2 <= altitude_max

        self.wait_and_maintain(value_name="Altitude", target=altitude_min,
                               current_value_getter=lambda: get_altitude(relative, timeout),
                               accuracy=(altitude_max - altitude_min),
                               validator=lambda v, t: validator(v, t),
                               timeout=timeout, **kwargs)

    def wait_location(self, loc, accuracy=50.0, timeout=180,
                      target_altitude=None, height_accuracy=-1, **kwargs):
        """Wait for the plane to arrive at a location. Default accuracy is wider
        than Copter's because fixed-wing approach radii are larger."""

        def get_distance_to_loc():
            return self.get_distance(self.mav.location(), loc)

        def validator(value2, empty=None):
            if value2 <= accuracy:
                if target_altitude is not None:
                    height_delta = math.fabs(self.mav.location().alt - target_altitude)
                    if height_accuracy != -1 and height_delta > height_accuracy:
                        return False
                return True
            return False

        debug_text = "Distance to Location (%.4f, %.4f) " % (loc.lat, loc.lng)
        if target_altitude is not None:
            debug_text += ",at altitude %.1f height_accuracy=%.1f, d" % (target_altitude, height_accuracy)
        self.wait_and_maintain(value_name=debug_text, target=0,
                               current_value_getter=lambda: get_distance_to_loc(),
                               accuracy=accuracy,
                               validator=lambda v, t: validator(v, None),
                               timeout=timeout, **kwargs)

    def wait_distance_to_home(self, distance_min, distance_max, timeout=10, use_cached_home=True, **kwargs):
        assert distance_min <= distance_max

        def get_distance():
            return self.distance_to_home(use_cached_home)

        def validator(v, t=None):
            return distance_min <= v <= distance_max

        self.wait_and_maintain(value_name="Distance to home", target=distance_min,
                               current_value_getter=lambda: get_distance(),
                               validator=lambda v, t: validator(v, t),
                               accuracy=(distance_max - distance_min), timeout=timeout, **kwargs)

    def wait_and_maintain(self, value_name, target, current_value_getter,
                          validator=None, accuracy=0.3, timeout=30, **kwargs):
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
        while time.time() < tstart + timeout:
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
                        self.progress("Attained %s=%f" % (value_name, sum_of_achieved_values / count_of_achieved_values))
                    return True
            else:
                achieving_duration_start = None
                if type(target) is Vector3:
                    sum_of_achieved_values.zero()
                else:
                    sum_of_achieved_values = 0.0
                count_of_achieved_values = 0
        raise TimeoutException("Failed to attain %s want %s, reached %s" % (
            value_name, str(target),
            str(sum_of_achieved_values * (1.0 / count_of_achieved_values))
            if count_of_achieved_values != 0 else str(last_value)))

    def wait_for_alt(self, alt_min=30, timeout=60, max_err=5):
        """Wait for minimum (relative) altitude to be reached."""
        self.wait_altitude(alt_min - 1, alt_min + max_err,
                           relative=True, timeout=timeout)

    def wait_heartbeat(self, drain_mav=True, quiet=False, *args, **x):
        if drain_mav:
            self.drain_mav(quiet=quiet)
        orig_timeout = x.get("timeout", 10)
        x["timeout"] = 1
        tstart = time.time()
        while True:
            if time.time() - tstart > orig_timeout:
                raise TimeoutException("Did not receive heartbeat")
            m = self.mav.wait_heartbeat(*args, **x)
            if m is None:
                continue
            if m.get_srcSystem() == self.target_system:
                break

    def wait_ekf_happy(self, timeout=30, require_absolute=True):
        if int(self.get_parameter('AHRS_EKF_TYPE')) == 10:
            return True
        required_value = (mavutil.mavlink.EKF_ATTITUDE |
                          mavutil.mavlink.ESTIMATOR_VELOCITY_HORIZ |
                          mavutil.mavlink.ESTIMATOR_VELOCITY_VERT |
                          mavutil.mavlink.ESTIMATOR_POS_HORIZ_REL |
                          mavutil.mavlink.ESTIMATOR_PRED_POS_HORIZ_REL)
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
        self.drain_mav_unparsed()
        last_print_time = 0
        tstart = time.time()
        while timeout is None or time.time() < tstart + timeout:
            m = self.mav.recv_match(type='EKF_STATUS_REPORT', blocking=True, timeout=timeout)
            if m is None:
                continue
            current = m.flags
            errors = current & error_bits
            everything_ok = (errors == 0 and current & required_value == required_value)
            if everything_ok or time.time() - last_print_time > 1:
                self.progress("Wait EKF.flags: required:%u current:%u errors=%u" %
                              (required_value, current, errors))
                last_print_time = time.time()
            if everything_ok:
                self.progress("EKF Flags OK")
                return True
        raise TimeoutException("Failed to get EKF.flags=%u" % required_value)

    def wait_gps_sys_status_not_present_or_enabled_and_healthy(self, timeout=30):
        self.progress("Waiting for GPS health")
        tstart = time.time()
        while True:
            now = time.time()
            if now - tstart > timeout:
                raise TimeoutException("GPS status bits did not become good")
            m = self.mav.recv_match(type='SYS_STATUS', blocking=True, timeout=1)
            if m is None:
                continue
            if not (m.onboard_control_sensors_present & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_GPS):
                self.progress("GPS not present")
                if now > 20:
                    return
                continue
            if not (m.onboard_control_sensors_enabled & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_GPS):
                self.progress("GPS not enabled")
                continue
            if not (m.onboard_control_sensors_health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_GPS):
                self.progress("GPS not healthy")
                continue
            self.progress("GPS healthy")
            return

    def wait_prearm_sys_status_healthy(self, timeout=60):
        tstart = time.time()
        while True:
            if time.time() - tstart > timeout:
                self.progress("Prearm bit never went true. Attempting arm to elicit reason from autopilot")
                self.arm_vehicle()
                raise TimeoutException("Prearm bit never went true")
            if self.sensor_has_state(mavutil.mavlink.MAV_SYS_STATUS_PREARM_CHECK, True, True, True):
                break

    def sensor_has_state(self, sensor, present=True, enabled=True, healthy=True, do_assert=False, verbose=False):
        m = self.mav.recv_match(type='SYS_STATUS', blocking=True, timeout=5)
        if m is None:
            raise TimeoutException("Did not receive SYS_STATUS")
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

    def wait_ready_to_arm(self, timeout=120, require_absolute=True, check_prearm_bit=True):
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

    ########################################################################################################################
    # Mission helpers ######################################################################################################
    ########################################################################################################################
    def wait_waypoint(self, wpnum_start, wpnum_end, allow_skip=True, max_dist=2, timeout=400):
        tstart = time.time()
        start_wp = self.mav.waypoint_current()
        current_wp = start_wp
        mode = self.mav.flightmode
        self.progress("wait for waypoint ranges start=%u end=%u" % (wpnum_start, wpnum_end))
        last_wp_msg = 0
        while time.time() < tstart + timeout:
            seq = self.mav.waypoint_current()
            m = self.mav.recv_match(type='NAV_CONTROLLER_OUTPUT', blocking=True)
            wp_dist = m.wp_dist
            m = self.mav.recv_match(type='VFR_HUD', blocking=True)
            if self.mav.flightmode != mode:
                raise WaitWaypointTimeout('Exited %s mode' % mode)
            if time.time() - last_wp_msg > 1:
                self.progress("WP %u (wp_dist=%u Alt=%.02f), current_wp: %u, wpnum_end: %u" %
                              (seq, wp_dist, m.alt, current_wp, wpnum_end))
                last_wp_msg = time.time()
            if seq == current_wp + 1 or (seq > current_wp + 1 and allow_skip):
                self.progress("Starting new waypoint %u" % seq)
                tstart = time.time()
                current_wp = seq
            if current_wp == wpnum_end and wp_dist < max_dist:
                self.progress("Reached final waypoint %u" % seq)
                return True
            if seq >= 255:
                self.progress("Reached final waypoint %u" % seq)
                return True
            if seq > current_wp + 1:
                raise WaitWaypointTimeout("Skipped waypoint! Got wp %u expected %u" % (seq, current_wp + 1))
        raise WaitWaypointTimeout("Timed out waiting for waypoint %u of %u" % (wpnum_end, wpnum_end))

    def send_all_waypoints(self, timeout=60):
        self.mav.waypoint_clear_all_send()
        self.progress("Sending %d waypoints" % self.wploader.count())
        if self.wploader.count() == 0:
            return
        self.mav.waypoint_count_send(self.wploader.count())
        tstart = time.time()
        while True:
            now = time.time()
            if now - tstart > timeout:
                self.progress("Failed to send Mission")
                return
            msg = self.mav.recv_match(type=["MISSION_REQUEST", "WAYPOINT_REQUEST"], blocking=True, timeout=3)
            if msg is None:
                continue
            if msg.seq >= self.wploader.count():
                self.progress("Request for bad waypoint %u (max %u)" % (msg.seq, self.wploader.count()))
                return
            wp = self.wploader.wp(msg.seq)
            wp_send = self.wp_to_mission_item_int(wp)
            self.mav.mav.send(wp_send)
            self.progress("Sent waypoint %u : %s" % (msg.seq, self.wploader.wp(msg.seq)))
            if msg.seq == self.wploader.count() - 1:
                self.progress("Sent all %u waypoints" % self.wploader.count())
                return

    def get_all_waypoints(self, timeout=30):
        self.progress("Requesting Mission item count")
        self.mav.waypoint_request_list_send()
        tstart = time.time()
        while True:
            now = time.time()
            if now - tstart > timeout:
                self.progress("Failed to get Mission total item")
                return
            msg = self.mav.recv_match(type=['WAYPOINT_COUNT', 'MISSION_COUNT'], blocking=True, timeout=3)
            if msg is None:
                continue
            self.wp_expected_count = msg.count
            self.progress("Got %s waypoints to get" % msg.count)
            self.wploader.clear()
            break
        for seq in self.missing_wps_to_request():
            self.wp_requested[seq] = time.time()
            self.progress("Requesting waypoint %d" % seq)
            self.mav.mav.mission_request_int_send(self.target_system, self.target_component, seq)
            tstart = time.time()
            while True:
                now = time.time()
                if now - tstart > timeout:
                    self.progress("Failed to get Waypoint %d" % seq)
                    return
                msg = self.mav.recv_match(type=['WAYPOINT', 'MISSION_ITEM', 'MISSION_ITEM_INT'],
                                          blocking=True, timeout=3)
                if msg is None:
                    continue
                if msg.get_type() == 'MISSION_ITEM_INT':
                    if getattr(msg, 'mission_type', 0) != 0:
                        return
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
        if wp.get_type() == 'MISSION_ITEM_INT':
            return wp
        return mavutil.mavlink.MAVLink_mission_item_int_message(
            wp.target_system, wp.target_component, wp.seq, wp.frame, wp.command,
            wp.current, wp.autocontinue, wp.param1, wp.param2, wp.param3, wp.param4,
            int(wp.x * 1.0e7), int(wp.y * 1.0e7), wp.z)

    def wp_from_mission_item_int(self, wp):
        wp2 = mavutil.mavlink.MAVLink_mission_item_message(
            wp.target_system, wp.target_component, wp.seq, wp.frame, wp.command,
            wp.current, wp.autocontinue, wp.param1, wp.param2, wp.param3, wp.param4,
            wp.x * 1.0e-7, wp.y * 1.0e-7, wp.z)
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

    def add_wp_takeoff(self, lat, lon, alt, pitch_deg=15, vtol=False):
        """Insert a takeoff waypoint at position 1 in the mission.

        For a QuadPlane VTOL takeoff set vtol=True (uses MAV_CMD_NAV_VTOL_TAKEOFF);
        otherwise a fixed-wing takeoff (MAV_CMD_NAV_TAKEOFF) is used with the given
        initial pitch.
        """
        command = (mavutil.mavlink.MAV_CMD_NAV_VTOL_TAKEOFF if vtol
                   else mavutil.mavlink.MAV_CMD_NAV_TAKEOFF)
        p1 = 0 if vtol else pitch_deg
        p = mavutil.mavlink.MAVLink_mission_item_message(
            self.target_system, self.target_component, 0,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, command,
            0, 0, p1, 0, 0, 0, lat, lon, alt)
        self.wploader.insert(1, p)

    def add_wp_land(self, lat, lon, alt=0, vtol=False):
        """Append a landing waypoint to the mission.

        For QuadPlane VTOL landing set vtol=True (MAV_CMD_NAV_VTOL_LAND); otherwise
        a fixed-wing landing waypoint is added (MAV_CMD_NAV_LAND).
        """
        command = (mavutil.mavlink.MAV_CMD_NAV_VTOL_LAND if vtol
                   else mavutil.mavlink.MAV_CMD_NAV_LAND)
        p = mavutil.mavlink.MAVLink_mission_item_message(
            self.target_system, self.target_component, 0,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, command,
            0, 0, 0, 0, 0, 0, lat, lon, alt)
        self.wploader.add(p)

    def add_wp_rtl(self):
        p = mavutil.mavlink.MAVLink_mission_item_message(
            self.target_system, self.target_component, 0,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
            mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
            0, 0, 0, 0, 0, 0, 0, 0, 0)
        self.wploader.add(p)

    def wp_mission_start(self):
        self.run_cmd(mavutil.mavlink.MAV_CMD_MISSION_START,
                     0, 0, 0, 0, 0, 0, 0,
                     target_sysid=self.target_system,
                     target_compid=self.target_system)

    def wp_clear(self):
        self.run_cmd(mavutil.mavlink.MAV_CMD_MISSION_CLEAR_ALL,
                     0, 0, 0, 0, 0, 0, 0,
                     target_sysid=self.target_system,
                     target_compid=self.target_system)

    ########################################################################################################################
    # Arming ###############################################################################################################
    ########################################################################################################################
    def armed(self):
        return self.mav.motors_armed()

    def arm_vehicle(self, timeout=20):
        """Arm the plane via MAVLink. Must be ready to arm; for fixed-wing this
        usually means GPS lock + EKF happy + safety switch off + throttle low."""
        self.progress("Arm motors with MAVLink cmd")
        self.drain_mav()
        self.run_cmd(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                     1, 0, 0, 0, 0, 0, 0, timeout=timeout)
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
        self.progress("Disarm motors with MAVLink cmd")
        self.drain_mav_unparsed()
        p2 = 21196 if force else 0
        self.run_cmd(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                     0, p2, 0, 0, 0, 0, 0, timeout=timeout)
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
                raise TimeoutException("Failed to DISARM within %fs" % timeout)
            if now - last_print_time > 1:
                self.progress("Waiting for disarm (%.2fs so far of allowed %.2f)" % (delta, timeout))
                last_print_time = now
            self.wait_heartbeat(quiet=True)
            if not self.mav.motors_armed():
                self.progress("DISARMED after %.2f seconds (allowed=%.2f)" % (delta, timeout))
                return True

    ########################################################################################################################
    # Takeoff / Land / RTL #################################################################################################
    ########################################################################################################################
    def takeoff(self, alt, pitch_deg=15, vtol=False, timeout=120):
        """Takeoff to the specified relative altitude.

        Fixed-wing (vtol=False): ArduPlane does NOT accept MAV_CMD_NAV_TAKEOFF
        as a runtime GUIDED command. The canonical sequence is to set TKOFF_ALT,
        switch to TAKEOFF mode (vehicle must already be armed; SITL auto-applies
        throttle), wait for altitude, then switch back to GUIDED so subsequent
        /movement commands work.

        VTOL (vtol=True): MAV_CMD_NAV_VTOL_TAKEOFF works in GUIDED for QuadPlane.

        pitch_deg is currently a no-op for fixed-wing — ArduPlane drives climb
        attitude from the TKOFF_LVL_PITCH / PTCH_LIM_MAX_DEG params, not from
        the NAV_TAKEOFF p1 value. Kept in the signature for API stability.
        """
        if vtol:
            self.run_cmd(mavutil.mavlink.MAV_CMD_NAV_VTOL_TAKEOFF,
                         0, 0, 0, 0, 0, 0, alt, timeout=timeout)
            self.wait_for_alt(alt, timeout=timeout)
        else:
            self.set_parameter("TKOFF_ALT", float(alt))
            self.change_mode("TAKEOFF")
            self.wait_for_alt(alt, timeout=timeout)
            self.change_mode("GUIDED")

    def land(self, timeout=120):
        """Switch to LAND mode and wait for the plane to land and disarm.

        For fixed-wing this assumes a landing approach has been pre-arranged in
        the mission (LAND mode follows the DO_LAND_START / NAV_LAND sequence). For
        a glide-down-here behaviour on a QuadPlane use qland() instead.
        """
        self.progress("STARTING LANDING")
        self.change_mode("LAND")
        self.wait_landed_and_disarmed(timeout=timeout)

    def qland(self, timeout=120):
        """QuadPlane vertical descent in place (QLAND mode)."""
        self.progress("STARTING QLAND")
        self.change_mode("QLAND")
        self.wait_landed_and_disarmed(timeout=timeout)

    def land_at(self, lat, long, alt, accuracy=80, timeout=180):
        """Fly to (lat, long, alt) using DO_REPOSITION, then switch to LAND once
        the plane is within `accuracy` metres of the target.

        Composite helper: there is no single MAVLink command for "land at this
        point" on fixed-wing. For QuadPlane, callers can fly_to + qland() instead
        if they need a vertical touchdown at a precise point.
        """
        self.go_to_gps(lat, long, alt)
        self.wait_location(self.mav_location(lat, long, alt),
                           accuracy=accuracy, timeout=timeout)
        self.land(timeout=timeout)

    def do_land_start(self, timeout=10):
        """Jump to the next DO_LAND_START item in the uploaded mission and begin
        the auto-landing sequence. Fire-and-forget; pair with
        wait_landed_and_disarmed() if you need to block until touchdown."""
        self.run_cmd(mavutil.mavlink.MAV_CMD_DO_LAND_START,
                     0, 0, 0, 0, 0, 0, 0, timeout=timeout)

    def wait_landed_and_disarmed(self, min_alt=2, timeout=120):
        """Wait until the plane is below `min_alt` AGL and disarmed."""
        m = self.mav.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
        alt = m.relative_alt / 1000.0
        if alt > min_alt:
            self.wait_for_alt(min_alt, timeout=timeout)
        self.wait_disarmed(timeout=timeout)

    def do_RTL(self, distance_max=120, check_alt=False, timeout=250):
        """Switch to RTL and wait until the plane is near home.

        Unlike Copter.do_RTL(), this does NOT wait for disarm — by default a
        fixed-wing plane loiters at the home location indefinitely after RTL
        unless a landing waypoint is present. Set check_alt=True only if you
        expect the plane to descend (mission has a landing).
        """
        self.change_mode("RTL")
        self.wait_rtl_complete(check_alt=check_alt,
                               distance_max=distance_max, timeout=timeout)

    def qrtl(self, timeout=250):
        """QuadPlane return-to-launch with vertical landing at home."""
        self.change_mode("QRTL")
        self.wait_landed_and_disarmed(timeout=timeout)

    def wait_rtl_complete(self, check_alt=False, distance_max=120, timeout=250):
        """Wait for the plane to approach home. If check_alt is True, also wait
        for low altitude + disarm (only meaningful when an auto-landing exists)."""
        self.progress("Waiting RTL to reach Home")
        tstart = time.time()
        while time.time() < tstart + timeout:
            m = self.mav.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
            alt = m.relative_alt / 1000.0
            home_distance = self.distance_to_home(use_cached_home=True)
            distance_valid = home_distance < distance_max
            self.progress("Alt: %.02f  HomeDist: %.02f" % (alt, home_distance))
            if check_alt:
                if distance_valid and alt <= 1 and not self.armed():
                    return
            else:
                if distance_valid:
                    self.progress("Plane is over home")
                    return
        raise TimeoutException("RTL did not complete in %fs" % timeout)

    ########################################################################################################################
    # GUIDED-mode movement #################################################################################################
    ########################################################################################################################
    def go_to_gps(self, lat: float, long: float, alt: float,
                  ground_speed: float = 0.0, yaw: float = float('nan')):
        """Send the plane to a GPS waypoint in GUIDED mode using DO_REPOSITION.

        ground_speed=0 means "keep current ground-speed setting". yaw=NaN means
        "no yaw preference". On arrival the plane loiters at the target.
        """
        self.progress("Moving to gps position (lat=%f, long=%f, alt=%f)" % (lat, long, alt))
        self.send_cmd_int(
            mavutil.mavlink.MAV_CMD_DO_REPOSITION,
            ground_speed,                                              # p1: ground speed (m/s); 0 = no change
            mavutil.mavlink.MAV_DO_REPOSITION_FLAGS_CHANGE_MODE,        # p2: bitmask
            0,                                                          # p3: loiter radius (0 = WP_LOITER_RAD)
            yaw,                                                        # p4: yaw (NaN = no change)
            int(lat * 1.0e7),                                           # x: latitude (degE7)
            int(long * 1.0e7),                                          # y: longitude (degE7)
            alt,                                                        # z: altitude (m, frame-relative)
            frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
        )

    def go_to_gps_wait(self, lat: float, long: float, alt: float,
                       accuracy: float = 50.0, height_accuracy: float = 10.0,
                       timeout: int = 180):
        """go_to_gps() + block until the plane arrives at the target."""
        self.go_to_gps(lat, long, alt)
        self.wait_location(self.mav_location(lat, long, alt),
                           accuracy=accuracy,
                           target_altitude=alt,
                           height_accuracy=height_accuracy,
                           timeout=timeout)

    def go_to_ned(self, north: float, east: float, down: float, look_at_target: bool = False):
        """Send a local-NED position target. Kept for API parity with Copter; on
        fixed-wing ArduPlane the autopilot will treat the target as a point to
        fly toward but exact behaviour depends on parameters. For predictable
        results prefer go_to_gps()."""
        self.progress("Moving to ned position (north=%f, east=%f, down=%f)" % (north, east, down))
        self.mav.mav.set_position_target_local_ned_send(
            0,
            self.target_system,
            self.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_VX_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_VY_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_VZ_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_AX_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_AY_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_AZ_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_FORCE_SET |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_IGNORE |
            (mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE if look_at_target else 0),
            float(north), float(east), float(down),
            0, 0, 0,
            0, 0, 0,
            0, 0)

    def set_attitude(self, roll: float, pitch: float, yaw: float,
                     throttle: float, body_rates: bool = False):
        """Send a SET_ATTITUDE_TARGET in GUIDED mode.

        roll/pitch/yaw are in degrees; throttle is 0.0..1.0. If body_rates is
        True the autopilot will treat the supplied yaw as a body yaw rate
        (deg/s) instead of an absolute heading. Useful for aerobatics or
        protocols that command bank angles directly.
        """
        self.progress("set_attitude roll=%.1f pitch=%.1f yaw=%.1f throttle=%.2f body_rates=%s" %
                      (roll, pitch, yaw, throttle, body_rates))
        roll_rad = math.radians(roll)
        pitch_rad = math.radians(pitch)
        yaw_rad = math.radians(yaw)
        q = self.euler_to_quaternion(roll_rad, pitch_rad, yaw_rad)

        # type_mask: bit 0 = ignore body roll rate, bit 1 = body pitch, bit 2 = body yaw
        # bit 6 = ignore attitude (quaternion). We want to use attitude.
        if body_rates:
            # use body yaw rate (yaw arg interpreted as deg/s), ignore body roll/pitch rates
            type_mask = (1 << 0) | (1 << 1)  # ignore body roll & pitch rates
            body_yaw_rate = math.radians(yaw)
        else:
            type_mask = (1 << 0) | (1 << 1) | (1 << 2)  # ignore all body rates
            body_yaw_rate = 0.0

        self.mav.mav.set_attitude_target_send(
            0,
            self.target_system,
            self.target_component,
            type_mask,
            q,
            0.0,            # body roll rate (ignored)
            0.0,            # body pitch rate (ignored)
            body_yaw_rate,
            float(throttle),
        )

    def stop(self):
        """Closest analog of "stop" for fixed-wing: enter LOITER mode at the
        current position. The plane will circle in place at its loiter radius."""
        self.progress("Stopping (LOITER at current position)")
        self.change_mode("LOITER")

    ########################################################################################################################
    # Loiter ###############################################################################################################
    ########################################################################################################################
    def loiter(self):
        """Enter LOITER mode at the current position."""
        self.change_mode("LOITER")

    def loiter_at(self, lat: float, long: float, alt: float, radius: float = None):
        """Loiter at a specific GPS point. Uses DO_REPOSITION (GUIDED) which
        causes the plane to circle the target at arrival. If radius is given,
        WP_LOITER_RAD is updated first so the loiter circle has the requested
        radius (a negative value loiters counter-clockwise per ArduPlane convention)."""
        if radius is not None:
            self.set_parameter("WP_LOITER_RAD", float(radius))
        self.go_to_gps(lat, long, alt)

    def loiter_unlim(self, lat: float, long: float, alt: float, radius: float = 50.0):
        """Direct MAV_CMD_NAV_LOITER_UNLIM command at a target point. This is
        typically a mission item; ArduPilot also accepts it as a COMMAND_INT in
        AUTO mode contexts. p3 carries the loiter radius (negative = CCW)."""
        self.send_cmd_int(
            mavutil.mavlink.MAV_CMD_NAV_LOITER_UNLIM,
            0,                            # p1: empty
            0,                            # p2: empty
            float(radius),                # p3: radius (m, negative = CCW)
            float('nan'),                 # p4: yaw (NaN = no change)
            int(lat * 1.0e7),
            int(long * 1.0e7),
            alt,
            frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
        )

    def loiter_turns(self, lat: float, long: float, alt: float,
                     turns: float = 3.0, radius: float = 50.0):
        """MAV_CMD_NAV_LOITER_TURNS: orbit the target `turns` times at the given
        radius. Like loiter_unlim, typically used as a mission item."""
        self.send_cmd_int(
            mavutil.mavlink.MAV_CMD_NAV_LOITER_TURNS,
            float(turns),                 # p1: number of turns
            0,                            # p2: heading required (0 = no)
            float(radius),                # p3: radius (m, negative = CCW)
            float('nan'),                 # p4: xtrack location (NaN = default)
            int(lat * 1.0e7),
            int(long * 1.0e7),
            alt,
            frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
        )

    def qloiter(self):
        """QuadPlane position-hold loiter."""
        self.change_mode("QLOITER")

    def qhover(self):
        """QuadPlane altitude-hold hover."""
        self.change_mode("QHOVER")

    ########################################################################################################################
    # Speed control ########################################################################################################
    ########################################################################################################################
    def change_air_speed(self, new_v):
        """Primary speed control for fixed-wing — set target airspeed (m/s)."""
        self.send_cmd(
            mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,
            mavutil.mavlink.SPEED_TYPE_AIRSPEED,
            new_v, -1, 0, 0, 0, 0,
            target_sysid=self.target_system,
            target_compid=self.target_component)

    def change_ground_speed(self, new_v):
        self.send_cmd(
            mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,
            mavutil.mavlink.SPEED_TYPE_GROUNDSPEED,
            new_v, -1, 0, 0, 0, 0,
            target_sysid=self.target_system,
            target_compid=self.target_component)

    def change_climb_speed(self, new_v):
        self.send_cmd(
            mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,
            mavutil.mavlink.SPEED_TYPE_CLIMB_SPEED,
            new_v, -1, 0, 0, 0, 0,
            target_sysid=self.target_system,
            target_compid=self.target_component)

    def change_descent_speed(self, new_v):
        self.send_cmd(
            mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,
            mavutil.mavlink.SPEED_TYPE_DESCENT_SPEED,
            new_v, -1, 0, 0, 0, 0,
            target_sysid=self.target_system,
            target_compid=self.target_component)

    def change_throttle(self, throttle_pct):
        """Override throttle (percent 0..100). Slot uses DO_CHANGE_SPEED's
        throttle field (p3); p2 (speed) is left at -1."""
        self.send_cmd(
            mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,
            mavutil.mavlink.SPEED_TYPE_THROTTLE,
            -1, throttle_pct, 0, 0, 0, 0,
            target_sysid=self.target_system,
            target_compid=self.target_component)

    ########################################################################################################################
    # Telemetry waits ######################################################################################################
    ########################################################################################################################
    def wait_airspeed(self, speed_min, speed_max, timeout=60, **kwargs):
        assert speed_min <= speed_max

        def get_airspeed():
            msg = self.mav.recv_match(type='VFR_HUD', blocking=True, timeout=5)
            if msg is None:
                raise MsgRcvTimeoutException("Failed to get VFR_HUD")
            return msg.airspeed

        def validator(v, t=None):
            return speed_min <= v <= speed_max

        try:
            self.wait_and_maintain(value_name="Airspeed", target=speed_min,
                                   current_value_getter=lambda: get_airspeed(),
                                   validator=lambda v, t: validator(v, t),
                                   accuracy=(speed_max - speed_min),
                                   timeout=timeout, **kwargs)
        except TimeoutException:
            raise WaitAirspeedTimeout("Failed to attain airspeed")

    def wait_groundspeed(self, speed_min, speed_max, timeout=60, **kwargs):
        assert speed_min <= speed_max

        def get_groundspeed():
            msg = self.mav.recv_match(type='VFR_HUD', blocking=True, timeout=5)
            if msg is None:
                raise MsgRcvTimeoutException("Failed to get VFR_HUD")
            return msg.groundspeed

        def validator(v, t=None):
            return speed_min <= v <= speed_max

        try:
            self.wait_and_maintain(value_name="Groundspeed", target=speed_min,
                                   current_value_getter=lambda: get_groundspeed(),
                                   validator=lambda v, t: validator(v, t),
                                   accuracy=(speed_max - speed_min),
                                   timeout=timeout, **kwargs)
        except TimeoutException:
            raise WaitGroundSpeedTimeout("Failed to attain groundspeed")

    def wait_heading(self, heading, accuracy=10, timeout=60, **kwargs):
        def get_heading():
            msg = self.mav.recv_match(type='VFR_HUD', blocking=True, timeout=5)
            if msg is None:
                raise MsgRcvTimeoutException("Failed to get VFR_HUD")
            return msg.heading

        def validator(v, t=None):
            delta = (v - heading) % 360
            if delta > 180:
                delta -= 360
            return abs(delta) <= accuracy

        try:
            self.wait_and_maintain(value_name="Heading", target=heading,
                                   current_value_getter=lambda: get_heading(),
                                   validator=lambda v, t: validator(v, t),
                                   accuracy=accuracy, timeout=timeout, **kwargs)
        except TimeoutException:
            raise WaitHeadingTimeout("Failed to attain heading")

    ########################################################################################################################
    # Telemetry getters ####################################################################################################
    ########################################################################################################################
    def get_current_target(self, timeout=10):
        """Latest POSITION_TARGET_GLOBAL_INT seen from the autopilot."""
        tstart = time.time()
        while True:
            if time.time() - tstart > timeout:
                raise TimeoutException("Failed to get POSITION_TARGET_GLOBAL_INT")
            msg = self.mav.recv_match(type='POSITION_TARGET_GLOBAL_INT', blocking=True, timeout=2)
            if msg is not None:
                self.progress("Received target: %s" % str(msg))
                return location(msg.lat_int * 1.0e-7, msg.lon_int * 1.0e-7, msg.alt, msg.yaw)

    def get_ned_position(self, timeout=10):
        tstart = time.time()
        last_pos = None
        while True:
            if time.time() - tstart > timeout:
                raise TimeoutException("Failed to get LOCAL_POSITION_NED")
            msg = self.mav.recv_match(type='LOCAL_POSITION_NED', blocking=False)
            if last_pos is None and msg is None:
                continue
            if msg is None:
                return Local_pos(x=last_pos.x, y=last_pos.y, z=last_pos.z)
            last_pos = msg

    def get_message(self, msg_type, timeout=10):
        tstart = time.time()
        last_msg = None
        while True:
            if time.time() - tstart > timeout:
                raise TimeoutException("Failed to get %s message" % msg_type)
            msg = self.mav.recv_match(type=msg_type, blocking=False)
            if last_msg is None and msg is None:
                continue
            if msg is None:
                return last_msg
            last_msg = msg

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
            "battery_remaining": sys_msg.battery_remaining,
        }

    def get_error_info(self, timeout=5):
        sys_msg = self.get_last_message("SYS_STATUS")
        autopilot_errors = [sys_msg.errors_count1, sys_msg.errors_count2,
                            sys_msg.errors_count3, sys_msg.errors_count4]
        autopilot_errors = [err for err in autopilot_errors if err != 0]
        return {
            "communication_drop_rate": sys_msg.drop_rate_comm,
            "communication_errors": sys_msg.errors_comm,
            "autopilot_errors": autopilot_errors,
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
        return self.get_last_message("MAG_CAL_REPORT")

    def get_airspeed(self):
        return self.get_last_message("VFR_HUD").airspeed

    def get_groundspeed(self):
        return self.get_last_message("VFR_HUD").groundspeed

    def get_heading(self):
        return self.get_last_message("VFR_HUD").heading

    ########################################################################################################################
    # Misc #################################################################################################################
    ########################################################################################################################
    def set_servo(self, channel, pwm):
        """Send a PWM signal to a servo on the given channel."""
        self.run_cmd(mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
                     channel, pwm, 0, 0, 0, 0, 0)

    def set_sim_speedup(self, value, timeout=10):
        """SITL only: set SIM_SPEEDUP for faster-than-realtime simulation."""
        self.progress("Setting parameter SIM_SPEEDUP to %s" % value)
        self.mav.param_set_send(b"SIM_SPEEDUP", value,
                                mavutil.mavlink.MAV_PARAM_TYPE_REAL32)

    async def run_drain_mav_loop(self, interval=0.1):
        """Async coroutine — drains the MAVLink receive buffer continuously.
        Start as an asyncio task during FastAPI lifespan startup."""
        while True:
            self.drain_mav()
            await asyncio.sleep(interval)
