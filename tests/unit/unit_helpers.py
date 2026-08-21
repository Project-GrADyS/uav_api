"""
Shared constants and helpers for the unit-test layer.

Kept out of tests/unit/conftest.py because test modules cannot `from conftest
import ...` here: when the whole suite runs, the name `conftest` is already
bound to tests/conftest.py in sys.modules.

Telemetry constants are attribute-bearing objects with numeric fields in raw
MAVLink units (lat in 1e7 degrees, alt in mm, vel in cm/s, hdg in
centidegrees): the handlers do the unit conversion arithmetic, which is
asserted exactly in copter_telemetry_unit_test.py. Values are chosen so the
converted results are exact in binary floating point.
"""

from types import SimpleNamespace

# parse_args default sysid — every response envelope carries it as a string.
SYSID = "10"

GENERAL = SimpleNamespace(airspeed=12.5, groundspeed=11.0, heading=90, throttle=55, alt=1042.5)
GPS = SimpleNamespace(
    lat=-158400810, lon=-479266420, alt=1042000, relative_alt=15000,
    vx=120, vy=-40, vz=10, hdg=9000,
)
RAW_GPS = SimpleNamespace(
    lat=-158400810, lon=-479266420, alt=1042000,
    vel=250, cog=4500, satellites_visible=12,
)
NED = SimpleNamespace(x=1.5, y=-2.5, z=-15.0, vx=0.25, vy=0.5, vz=-0.75)
NED_POSITION = SimpleNamespace(x=1.0, y=2.0, z=-15.0)
COMPASS = SimpleNamespace(calibration_status=1, autosaved=1, fitness=[0.25, 0.5, 0.75])
SYS_STATUS = SimpleNamespace(to_dict=lambda: {"onboard_control_sensors_health": 12345})
HOME = {"latitude": -158400810, "longitude": -479266420, "altitude": 1042000,
        "x": 1.0, "y": 2.0, "z": 3.0}
BATTERY = {"voltage": 12.6, "current": 5.0, "remaining": 87}
SENSORS = {"gps": "enabled and healthy"}
ERRORS = {"errors_count1": 0}


def assert_envelope(body, result_contains=None):
    assert body["device"] == "uav"
    assert body["id"] == SYSID
    if result_contains is not None:
        assert result_contains in body["result"]
