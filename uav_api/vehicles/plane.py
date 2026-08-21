import math
import time

from pymavlink import mavutil

from uav_api.vehicles.vehicle import (  # noqa: F401 -- exceptions re-exported for backwards compatibility
    Vehicle,
    ErrorException,
    TimeoutException,
    LinkDownException,
    WaitModeTimeout,
    WaitAltitudeTimout,
    WaitGroundSpeedTimeout,
    WaitAirspeedTimeout,
    WaitHeadingTimeout,
    WaitDistanceTimeout,
    WaitLocationTimeout,
    WaitWaypointTimeout,
    MsgRcvTimeoutException,
    NotAchievedException,
    PreconditionFailedException,
    MovementException,
)


class Plane(Vehicle):
    """ArduPilot Plane class.

    Mirrors the structure of uav_api.copter.Copter but targets ArduPlane (fixed-wing
    and QuadPlane / VTOL hybrids) running in GUIDED mode.

    Heavily based on ArduPilot's autotest harness for ArduPlane:
    https://github.com/ArduPilot/ardupilot/blob/master/Tools/autotest/arduplane.py
    Test-only scaffolding has been removed; only commands and waits useful for
    real-world GUIDED operation are kept.
    """

    LAND_MIN_ALT = 2
    LAND_TIMEOUT = 120

    def __init__(self, default_stream_rate=5, sysid=1):
        super().__init__(default_stream_rate=default_stream_rate, sysid=sysid, logger_name="PLANE")

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
    # Waits (plane-tuned defaults) #########################################################################################
    ########################################################################################################################
    def wait_location(self, loc, accuracy=50.0, timeout=180,
                      target_altitude=None, height_accuracy=-1, **kwargs):
        """Wait for the plane to arrive at a location. Default accuracy is wider
        than Copter's because fixed-wing approach radii are larger."""
        return super().wait_location(loc, accuracy=accuracy, timeout=timeout,
                                     target_altitude=target_altitude,
                                     height_accuracy=height_accuracy, **kwargs)

    def wait_for_alt(self, alt_min=30, timeout=60, max_err=5):
        """Wait for minimum (relative) altitude to be reached."""
        return super().wait_for_alt(alt_min=alt_min, timeout=timeout, max_err=max_err)

    def wait_landed_and_disarmed(self, min_alt=2, timeout=120):
        """Wait until the plane is below `min_alt` AGL and disarmed."""
        return super().wait_landed_and_disarmed(min_alt=min_alt, timeout=timeout,
                                                disarm_timeout=timeout)

    ########################################################################################################################
    # Mission helpers ######################################################################################################
    ########################################################################################################################
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

    def land_at(self, lat, long, alt=0, vtol=False):
        """Upload a simple mission that lands at (lat, long) and execute it in AUTO.

        Mission: seq 0 = home (seeded by init_wp), seq 1 = NAV_LAND (or
        NAV_VTOL_LAND if vtol=True) at the target point. Returns as soon as the
        mode switch to AUTO succeeds — does NOT wait for the landing to
        complete; poll telemetry to track the landing.
        """
        self.init_wp()
        self.add_wp_land(lat, long, alt, vtol=vtol)
        self.send_all_waypoints()
        if not self.change_mode("AUTO"):
            raise Exception("Failed to switch to AUTO mode")

    def do_land_start(self, timeout=10):
        """Jump to the next DO_LAND_START item in the uploaded mission and begin
        the auto-landing sequence. Fire-and-forget; pair with
        wait_landed_and_disarmed() if you need to block until touchdown."""
        self.run_cmd(mavutil.mavlink.MAV_CMD_DO_LAND_START,
                     0, 0, 0, 0, 0, 0, 0, timeout=timeout)

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
            m = self.wait_message('GLOBAL_POSITION_INT', timeout=5)
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
                       accuracy: float = 120.0, height_accuracy: float = 10.0,
                       timeout: int = 180):
        """go_to_gps() + block until the plane arrives at the target.

        accuracy defaults to 2x the default WP_LOITER_RAD (60 m): on arrival a
        fixed-wing loiters around the target, so its distance to it never
        drops below the loiter radius plus the entry overshoot — 50 m was
        unreachable and timed out on every call.
        """
        self.go_to_gps(lat, long, alt)
        # wait_location's height check compares absolute (AMSL) altitude,
        # while alt is home-relative (MAV_FRAME_GLOBAL_RELATIVE_ALT).
        target_alt_amsl = self.get_home_position()["altitude"] / 1000.0 + alt
        self.wait_location(self.mav_location(lat, long, alt),
                           accuracy=accuracy,
                           target_altitude=target_alt_amsl,
                           height_accuracy=height_accuracy,
                           timeout=timeout)

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

        self.tx.set_attitude_target_send(
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
            try:
                msg = self.wait_message('VFR_HUD', timeout=5)
            except TimeoutException:
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
            try:
                msg = self.wait_message('VFR_HUD', timeout=5)
            except TimeoutException:
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
            try:
                msg = self.wait_message('VFR_HUD', timeout=5)
            except TimeoutException:
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
    def get_airspeed(self):
        return self.get_last_message("VFR_HUD").airspeed

    def get_groundspeed(self):
        return self.get_last_message("VFR_HUD").groundspeed

    def get_heading(self):
        return self.get_last_message("VFR_HUD").heading
