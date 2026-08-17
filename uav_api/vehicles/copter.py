import math
import time

from pymavlink import mavutil

from uav_api.classes.movement import Local_pos
from uav_api.vehicles.vehicle import (  # noqa: F401 -- exceptions re-exported for backwards compatibility
    Vehicle,
    ErrorException,
    TimeoutException,
    LinkDownException,
    WaitModeTimeout,
    WaitAltitudeTimout,
    WaitGroundSpeedTimeout,
    WaitRollTimeout,
    WaitPitchTimeout,
    WaitHeadingTimeout,
    WaitDistanceTimeout,
    WaitLocationTimeout,
    WaitWaypointTimeout,
    SetRCTimeout,
    MsgRcvTimeoutException,
    NotAchievedException,
    YawSpeedNotAchievedException,
    SpeedVectorNotAchievedException,
    PreconditionFailedException,
    ArmedAtEndOfTestException,
    MovementException,
)


class Copter(Vehicle):
    """ArduPilot Copter class.

    This class is a generic class that show some example on how to use Pymavlink to connect and control ArduPilot Copter drone.
    This is heavily based on ArduPilot Autotest framework : https://github.com/ArduPilot/ardupilot/tree/master/Tools/autotest. You can find there more utilities functions."""

    LAND_MIN_ALT = 6
    LAND_TIMEOUT = 60

    def __init__(self, default_stream_rate=5, sysid=1):
        super().__init__(default_stream_rate=default_stream_rate, sysid=sysid, logger_name="COPTER")

    ########################################################################################################################
    # Command functions ####################################################################################################
    ########################################################################################################################
    def user_takeoff(self, alt_min=30):
        """takeoff using mavlink takeoff command"""
        self.run_cmd(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                     0,  # param1
                     0,  # param2
                     0,  # param3
                     0,  # param4
                     0,  # param5
                     0,  # param6
                     alt_min  # param7
                     )
        self.progress("Ran command")
        self.wait_for_alt(alt_min)

    def land_and_disarm(self, timeout=60):
        """Land the quad."""
        self.progress("STARTING LANDING")
        self.change_mode("LAND")
        self.wait_landed_and_disarmed(timeout=timeout)

    # enter RTL mode and wait for the vehicle to disarm
    def do_RTL(self, distance_min=None, check_alt=True, distance_max=10, timeout=250):
        """Enter RTL mode and wait for the vehicle to disarm at Home."""
        self.change_mode("RTL")
        self.wait_rtl_complete(check_alt=check_alt, distance_max=distance_max, timeout=timeout)

    def wait_rtl_complete(self, check_alt=True, distance_max=10, timeout=250):
        """Wait for RTL to reach home and disarm"""
        self.progress("Waiting RTL to reach Home and disarm")
        tstart = time.time()
        while time.time() < tstart + timeout:
            m = self.wait_message('GLOBAL_POSITION_INT', timeout=5)
            alt = m.relative_alt / 1000.0  # mm -> m
            home_distance = self.distance_to_home(use_cached_home=True)
            home = ""
            alt_valid = alt <= 1
            distance_valid = home_distance < distance_max
            if check_alt:
                if alt_valid and distance_valid:
                    home = "HOME"
            else:
                if distance_valid:
                    home = "HOME"
            self.progress("Alt: %.02f  HomeDist: %.02f %s" %
                          (alt, home_distance, home))

            # our post-condition is that we are disarmed:
            if not self.armed():
                if home == "":
                    raise Exception("Did not get home")
                # success!
                return

        raise Exception("Did not get home and disarm")

    def add_wp_takeoff(self, lat, lon, alt):
        p = mavutil.mavlink.MAVLink_mission_item_message(self.target_system,
                                                         self.target_component,
                                                         0,
                                                         mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                                                         mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                                                         0, 0, 0, 0, 0, 0,
                                                         lat, lon, alt)
        self.wploader.insert(1, p)

    def ensure_moving(self, amount=5, timeout=10):
        current_pos = self.location()

        def travelled_distance():
            self.logger.debug("current_pos %s" % current_pos)
            new_location = self.location()
            self.logger.debug("new_location %s" % new_location)
            z_distance = abs(new_location.alt - current_pos.alt)
            self.logger.debug("z_distance %s" % z_distance)
            xy_distance = self.get_distance(current_pos, new_location)
            self.logger.debug("xy_distance %s" % xy_distance)
            return xy_distance + z_distance

        def moving_validator(value, target):
            return value >= target

        try:
            self.wait_and_maintain(value_name="Moving", target=3, validator=moving_validator,
                                   current_value_getter=lambda: travelled_distance(), timeout=timeout)
        except TimeoutException:
            raise TimeoutException("No movement registred")

    def ensure_holding(self, timeout=10):

        def travelled_distance():
            last_pos = self.location()
            time.sleep(1)
            current_pos = self.location()
            d = self.get_distance(last_pos, current_pos)
            return d

        try:
            self.wait_and_maintain(value_name="Holding", target=0,
                                   current_value_getter=lambda: travelled_distance(), timeout=timeout)
        except TimeoutException:
            raise TimeoutException("Moviment registred")

    ########################################################################################################################
    # Movement #############################################################################################################
    ########################################################################################################################
    def go_to_gps(self, lat: float, long: float, alt: int, look_at_target=False):
        self.progress(f"Moving to gps position (lat={lat}, long={long}, alt={alt})")

        self.tx.set_position_target_global_int_send(
            0,  # timestamp
            self.target_system,  # target system_id
            self.target_component,  # target component_id
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_VX_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_VY_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_VZ_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_AX_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_AY_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_AZ_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_FORCE_SET |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_IGNORE |
            (mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE if look_at_target else 0),
            int(lat * 1.0e7),  # lat
            int(long * 1.0e7),  # lon
            alt,  # alt
            0,  # vx
            0,  # vy
            0,  # vz
            0,  # afx
            0,  # afy
            0,  # afz
            0,  # yaw
            0,  # yawrate
        )

    def travel_at_ned(self, vx: float, vy: float, vz: float, look_at_target=False):
        self.progress(f"Moving at NED velocity (vx={vx}, vy={vy}, vz={vz})")

        self.tx.set_position_target_local_ned_send(
            0,  # timestamp
            self.target_system,  # target system_id
            self.target_component,  # target component_id
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,  # coordinate frame
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_X_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_Y_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_Z_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_AX_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_AY_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_AZ_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_FORCE_SET |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_IGNORE |
            (mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE if look_at_target else 0),
            0,  # north offset to origin(home) (m)
            0,  # east offset to origin(home) (m)
            0,  # down offset to origin(home) (m)
            float(vx),  # x velocity (m/s)
            float(vy),  # y velocity (m/s)
            float(vz),  # z velocity (m/s)
            0,  # x acceleration (m/s^2)
            0,  # y acceleration (m/s^2)
            0,  # z acceleration (m/s^2)
            0,  # yaw heading (radians)
            0,  # yaw_rate (rad/s)
        )

    def set_heading(self, heading: float):
        self.progress(f"Setting heading to {heading} degrees")
        self.run_cmd(
            mavutil.mavlink.MAV_CMD_CONDITION_YAW,
            heading,  # p1: target angle (degrees)
            0,        # p2: angular speed (deg/s, 0 = default)
            1,        # p3: direction (1 = CW, -1 = CCW, 0 = shortest)
            0,        # p4: 0 = absolute angle, 1 = relative offset
            0, 0, 0
        )

    def set_yaw_rate(self, yaw_rate: float):
        self.progress(f"Setting yaw rate to {yaw_rate} deg/s")
        self.tx.set_position_target_local_ned_send(
            0,
            self.target_system,
            self.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_X_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_Y_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_Z_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_AX_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_AY_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_AZ_IGNORE |
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_IGNORE,
            0, 0, 0,
            0, 0, 0,
            0, 0, 0,
            0,
            math.radians(yaw_rate),
        )

    def wait_ned_position(self, target: Local_pos, timeout=60):

        def ned_distance():
            # Fresh wait paces the loop at the stream rate.
            pos1 = self.get_ned_position(allow_cached_age=None)
            pos2 = target
            x_distance = abs(pos1.x - pos2.x)
            y_distance = abs(pos1.y - pos2.y)
            z_distance = abs(pos1.z - pos2.z)
            return (x_distance + y_distance + z_distance) / 3

        self.wait_and_maintain(
            value_name="NED Position",
            target=0,
            current_value_getter=lambda: ned_distance(),
            validator=None,
            timeout=timeout,
            accuracy=1
        )

    def drive_ned(self, north: float, east: float, down: float, look_at_target: bool = False, timeout=60):
        self.tx.set_position_target_local_ned_send(
            0,  # timestamp
            self.target_system,  # target system_id
            self.target_component,  # target component_id
            mavutil.mavlink.MAV_FRAME_LOCAL_OFFSET_NED,  # coordinate frame
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
