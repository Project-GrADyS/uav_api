"""Unit tests for the copter telemetry router.

The MAVLink-unit conversions (lat/1e7 to degrees, alt/1000 to metres,
vel/100 to m/s, hdg/100 to degrees) are real handler logic the SITL suite
can only bound-check — here they are asserted exactly.
"""

from unit_helpers import (
    BATTERY, COMPASS, ERRORS, GENERAL, HOME, NED, SENSORS, assert_envelope,
)


def test_general(copter_client):
    r = copter_client.get("/telemetry/general")
    assert r.status_code == 200
    body = r.json()
    assert_envelope(body)
    assert body["info"] == {
        "airspeed": GENERAL.airspeed,
        "groundspeed": GENERAL.groundspeed,
        "heading": GENERAL.heading,
        "throttle": GENERAL.throttle,
        "alt": GENERAL.alt,
    }


def test_gps_conversions(copter_client):
    r = copter_client.get("/telemetry/gps")
    assert r.status_code == 200
    info = r.json()["info"]
    assert info["position"] == {
        "lat": -15.840081,
        "lon": -47.926642,
        "alt": 1042.0,
        "relative_alt": 15.0,
    }
    assert info["velocity"] == {"vx": 1.2, "vy": -0.4, "vz": 0.1}
    assert info["heading"] == 90.0


def test_gps_raw_conversions(copter_client):
    r = copter_client.get("/telemetry/gps_raw")
    assert r.status_code == 200
    info = r.json()["info"]
    assert info["position"] == {"lat": -15.840081, "lon": -47.926642, "alt": 1042.0}
    assert info["velocity"] == {"ground_speed": 2.5, "speed_direction": 45.0}
    assert info["satelites"] == 12


def test_ned(copter_client):
    r = copter_client.get("/telemetry/ned")
    assert r.status_code == 200
    info = r.json()["info"]
    assert info["position"] == {"x": NED.x, "y": NED.y, "z": NED.z}
    assert info["velocity"] == {"vx": NED.vx, "vy": NED.vy, "vz": NED.vz}


def test_compass(copter_client):
    r = copter_client.get("/telemetry/compass")
    assert r.status_code == 200
    info = r.json()["info"]
    assert info["calibration_status"] == COMPASS.calibration_status
    assert info["autosaved"] is True
    assert info["fitness"] == {"x": 0.25, "y": 0.5, "z": 0.75}


def test_compass_without_calibration_report_is_404(copter_client, fake_copter):
    fake_copter.get_compass_info.return_value = None
    r = copter_client.get("/telemetry/compass")
    assert r.status_code == 404


def test_sys_status(copter_client):
    r = copter_client.get("/telemetry/sys_status")
    assert r.status_code == 200
    assert r.json()["status"] == {"onboard_control_sensors_health": 12345}


def test_sensor_status(copter_client):
    r = copter_client.get("/telemetry/sensor_status")
    assert r.status_code == 200
    assert r.json()["status"] == SENSORS


def test_battery_info(copter_client):
    r = copter_client.get("/telemetry/battery_info")
    assert r.status_code == 200
    assert r.json()["info"] == BATTERY


def test_error_info(copter_client):
    r = copter_client.get("/telemetry/error_info")
    assert r.status_code == 200
    assert r.json()["info"] == ERRORS


def test_home_info_conversions(copter_client):
    r = copter_client.get("/telemetry/home_info")
    assert r.status_code == 200
    body = r.json()
    assert body["lat"] == -15.840081
    assert body["lon"] == -47.926642
    assert body["altitude"] == 1042.0
    assert (body["x"], body["y"], body["z"]) == (HOME["x"], HOME["y"], HOME["z"])


def test_telemetry_failure_is_500(copter_client, fake_copter):
    fake_copter.get_general_info.side_effect = Exception("no heartbeat")
    r = copter_client.get("/telemetry/general")
    assert r.status_code == 500
    assert "GET_GENERAL_INFO FAIL" in r.json()["detail"]
