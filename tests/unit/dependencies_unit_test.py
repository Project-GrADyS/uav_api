"""Unit tests for the vehicle singletons' construction in
routers/dependencies.py: the stream rate reaches the vehicle as an int.
No MAVLink connection is made."""

import pytest

from uav_api.routers import dependencies


class FakeVehicle:
    def __init__(self, sysid, default_stream_rate):
        self.sysid = sysid
        self.streamrate = default_stream_rate

    def connect(self, connection_string):
        self.connection_string = connection_string


@pytest.fixture(autouse=True)
def fake_vehicles(monkeypatch):
    monkeypatch.setattr(dependencies, "Copter", FakeVehicle)
    monkeypatch.setattr(dependencies, "Plane", FakeVehicle)
    monkeypatch.setattr(dependencies, "copter", None)
    monkeypatch.setattr(dependencies, "plane", None)


@pytest.mark.parametrize("init", [dependencies.init_copter, dependencies.init_plane])
def test_config_string_rate_is_coerced(init):
    vehicle = init("3", "udpin:127.0.0.1:17171", "30")
    assert vehicle.streamrate == 30
    assert vehicle.sysid == 3


@pytest.mark.parametrize("init", [dependencies.init_copter, dependencies.init_plane])
def test_default_rate_is_five(init):
    assert init(1, "udpin:127.0.0.1:17171").streamrate == 5


@pytest.mark.parametrize("init", [dependencies.init_copter, dependencies.init_plane])
@pytest.mark.parametrize("rate", ["0", -2])
def test_non_positive_rate_is_rejected(init, rate):
    with pytest.raises(ValueError, match="mavlink_streamrate"):
        init(1, "udpin:127.0.0.1:17171", rate)
