"""
Integration tests for the telemetry router.

Uses the shared SITL session from conftest.py (session-scoped).
The drone is already armed and hovering at ~15m altitude.

Run:
    pytest tests/telemetry_test.py -v -s --timeout=120
"""

from conftest import get


# ── tests (run in order, share the same SITL session) ────────────────────────


class TestGeneral:
    def test_general(self, api_server):
        """GET /telemetry/general → basic flight info."""
        r = get("/telemetry/general")
        assert r.status_code == 200
        info = r.json()["info"]
        for key in ("airspeed", "groundspeed", "heading", "throttle", "alt"):
            assert key in info, f"Missing key: {key}"
        assert abs(info["alt"] - 15) <= 5, f"Expected alt ~15, got {info['alt']}"


class TestGps:
    def test_gps(self, api_server):
        """GET /telemetry/gps → GPS position, velocity, heading."""
        r = get("/telemetry/gps")
        assert r.status_code == 200
        info = r.json()["info"]

        pos = info["position"]
        for key in ("lat", "lon", "alt", "relative_alt"):
            assert key in pos, f"Missing key: {key}"
        assert -90 <= pos["lat"] <= 90, f"lat out of range: {pos['lat']}"
        assert pos["lat"] != 0, "lat should not be zero"
        assert pos["lon"] != 0, "lon should not be zero"
        assert abs(pos["relative_alt"] - 15) <= 5, (
            f"Expected relative_alt ~15, got {pos['relative_alt']}"
        )

        vel = info["velocity"]
        for key in ("vx", "vy", "vz"):
            assert key in vel, f"Missing key: {key}"

        assert "heading" in info


class TestGpsRaw:
    def test_gps_raw(self, api_server):
        """GET /telemetry/gps_raw → raw GPS data."""
        r = get("/telemetry/gps_raw")
        assert r.status_code == 200
        info = r.json()["info"]

        pos = info["position"]
        for key in ("lat", "lon", "alt"):
            assert key in pos, f"Missing key: {key}"

        vel = info["velocity"]
        for key in ("ground_speed", "speed_direction"):
            assert key in vel, f"Missing key: {key}"

        assert "satelites" in info


class TestNed:
    def test_ned(self, api_server):
        """GET /telemetry/ned → NED position and velocity."""
        r = get("/telemetry/ned")
        assert r.status_code == 200
        info = r.json()["info"]

        pos = info["position"]
        for key in ("x", "y", "z"):
            assert key in pos, f"Missing key: {key}"
        assert abs(pos["z"] - (-15)) <= 5, (
            f"Expected z ~-15 (NED), got {pos['z']}"
        )

        vel = info["velocity"]
        for key in ("vx", "vy", "vz"):
            assert key in vel, f"Missing key: {key}"


class TestCompass:
    def test_compass(self, api_server):
        """GET /telemetry/compass → compass calibration info."""
        r = get("/telemetry/compass")
        assert r.status_code == 200
        info = r.json()["info"]
        assert "calibration_status" in info
        assert isinstance(info["autosaved"], bool)
        fitness = info["fitness"]
        for key in ("x", "y", "z"):
            assert key in fitness, f"Missing key: {key}"


class TestSysStatus:
    def test_sys_status(self, api_server):
        """GET /telemetry/sys_status → system status dict."""
        r = get("/telemetry/sys_status")
        assert r.status_code == 200
        assert isinstance(r.json()["status"], dict)


class TestSensorStatus:
    def test_sensor_status(self, api_server):
        """GET /telemetry/sensor_status → sensor status dict."""
        r = get("/telemetry/sensor_status")
        assert r.status_code == 200
        assert isinstance(r.json()["status"], dict)


class TestBatteryInfo:
    def test_battery_info(self, api_server):
        """GET /telemetry/battery_info → battery info dict."""
        r = get("/telemetry/battery_info")
        assert r.status_code == 200
        assert isinstance(r.json()["info"], dict)


class TestErrorInfo:
    def test_error_info(self, api_server):
        """GET /telemetry/error_info → error info dict."""
        r = get("/telemetry/error_info")
        assert r.status_code == 200
        assert isinstance(r.json()["info"], dict)


class TestHomeInfo:
    def test_home_info(self, api_server):
        """GET /telemetry/home_info → home position info."""
        r = get("/telemetry/home_info")
        assert r.status_code == 200
        body = r.json()
        for key in ("lat", "lon", "altitude", "x", "y", "z"):
            assert key in body, f"Missing key: {key}"
        assert -90 <= body["lat"] <= 90, f"lat out of range: {body['lat']}"
        assert body["lat"] != 0, "lat should not be zero"
        assert body["lon"] != 0, "lon should not be zero"
