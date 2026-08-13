"""
Integration tests for the telemetry router.

Own SITL instance (port 8005, sysid 5), armed and hovering at ~15 m.

Frame conventions asserted here (see docs/coordinate-frames.md):
    /telemetry/general alt  → AMSL metres (VFR_HUD), NOT height above home
    /telemetry/gps relative_alt → metres above home
    /telemetry/ned z        → metres, Down-positive (hover at 15 m → z ≈ -15)
"""

from conftest import make_api_fixture

api = make_api_fixture(port=8005, sysid=5, flying=True)


class TestGeneral:
    def test_general(self, api):
        """GET /telemetry/general → basic flight info."""
        r = api.get("/telemetry/general")
        assert r.status_code == 200
        info = r.json()["info"]
        for key in ("airspeed", "groundspeed", "heading", "throttle", "alt"):
            assert key in info, f"Missing key: {key}"

        # alt is AMSL — cross-check against the GPS AMSL altitude
        r = api.get("/telemetry/gps")
        assert r.status_code == 200
        gps_alt = r.json()["info"]["position"]["alt"]
        assert abs(info["alt"] - gps_alt) <= 5, (
            f"general alt (AMSL) {info['alt']} inconsistent with gps alt {gps_alt}"
        )


class TestGps:
    def test_gps(self, api):
        """GET /telemetry/gps → GPS position, velocity, heading."""
        r = api.get("/telemetry/gps")
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
    def test_gps_raw(self, api):
        """GET /telemetry/gps_raw → raw GPS data."""
        r = api.get("/telemetry/gps_raw")
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
    def test_ned(self, api):
        """GET /telemetry/ned → NED position and velocity."""
        r = api.get("/telemetry/ned")
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
    def test_compass(self, api):
        """GET /telemetry/compass → calibration info, or 404 when no
        calibration ever ran (always the case in SITL)."""
        r = api.get("/telemetry/compass")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            info = r.json()["info"]
            assert "calibration_status" in info
            assert isinstance(info["autosaved"], bool)
            fitness = info["fitness"]
            for key in ("x", "y", "z"):
                assert key in fitness, f"Missing key: {key}"
        else:
            assert "calibration" in r.json()["detail"].lower()


class TestSysStatus:
    def test_sys_status(self, api):
        """GET /telemetry/sys_status → system status dict."""
        r = api.get("/telemetry/sys_status")
        assert r.status_code == 200
        assert isinstance(r.json()["status"], dict)


class TestSensorStatus:
    def test_sensor_status(self, api):
        """GET /telemetry/sensor_status → sensor status dict."""
        r = api.get("/telemetry/sensor_status")
        assert r.status_code == 200
        assert isinstance(r.json()["status"], dict)


class TestBatteryInfo:
    def test_battery_info(self, api):
        """GET /telemetry/battery_info → battery info dict."""
        r = api.get("/telemetry/battery_info")
        assert r.status_code == 200
        assert isinstance(r.json()["info"], dict)


class TestErrorInfo:
    def test_error_info(self, api):
        """GET /telemetry/error_info → error info dict."""
        r = api.get("/telemetry/error_info")
        assert r.status_code == 200
        assert isinstance(r.json()["info"], dict)


class TestHomeInfo:
    def test_home_info(self, api):
        """GET /telemetry/home_info → home position info."""
        r = api.get("/telemetry/home_info")
        assert r.status_code == 200
        body = r.json()
        for key in ("lat", "lon", "altitude", "x", "y", "z"):
            assert key in body, f"Missing key: {key}"
        assert -90 <= body["lat"] <= 90, f"lat out of range: {body['lat']}"
        assert body["lat"] != 0, "lat should not be zero"
        assert body["lon"] != 0, "lon should not be zero"
