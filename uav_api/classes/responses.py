"""Response models for every JSON endpoint.

The canonical envelope is UavResponse: device/id/result on every response.
Telemetry payload nesting mirrors the wire format exactly — consumers (and
the integration tests) read paths like info.position.relative_alt, so the
models document the contract rather than reshape it.
"""

from typing import Literal

from pydantic import BaseModel, Field


class UavResponse(BaseModel):
    device: Literal["uav"] = "uav"
    id: str
    result: str


# --- telemetry payloads ---

class GeneralInfo(BaseModel):
    airspeed: float
    groundspeed: float
    heading: float
    throttle: float
    alt: float


class GeneralTelemetryResponse(UavResponse):
    info: GeneralInfo


class GpsPosition(BaseModel):
    lat: float
    lon: float
    alt: float
    relative_alt: float


class NedVelocity(BaseModel):
    vx: float
    vy: float
    vz: float


class GpsInfo(BaseModel):
    position: GpsPosition
    velocity: NedVelocity
    heading: float


class GpsTelemetryResponse(UavResponse):
    info: GpsInfo


class RawGpsPosition(BaseModel):
    lat: float
    lon: float
    alt: float


class RawGpsVelocity(BaseModel):
    ground_speed: float
    speed_direction: float


class RawGpsInfo(BaseModel):
    position: RawGpsPosition
    velocity: RawGpsVelocity
    # Misspelling preserved: it is the wire contract consumers already parse.
    satelites: int


class RawGpsTelemetryResponse(UavResponse):
    info: RawGpsInfo


class NedPosition(BaseModel):
    x: float
    y: float
    z: float


class NedInfo(BaseModel):
    position: NedPosition
    velocity: NedVelocity


class NedTelemetryResponse(UavResponse):
    info: NedInfo


class CompassFitness(BaseModel):
    x: float
    y: float
    z: float


class CompassInfo(BaseModel):
    calibration_status: int
    autosaved: bool
    fitness: CompassFitness


class CompassTelemetryResponse(UavResponse):
    info: CompassInfo


class SysStatusResponse(UavResponse):
    status: dict


class SensorStatusResponse(UavResponse):
    status: dict


class BatteryInfoResponse(UavResponse):
    info: dict


class ErrorInfoResponse(UavResponse):
    info: dict


class HomeInfoResponse(UavResponse):
    # Flat on the envelope, as always: home_info predates the info nesting.
    lat: float
    lon: float
    altitude: float
    x: float
    y: float
    z: float


# --- mission ---

class MissionResponse(UavResponse):
    # The numeric codes (42-52) predate the result envelope. Deprecated:
    # they will be removed together with the unversioned route aliases.
    type: int = Field(json_schema_extra={"deprecated": True})


class UploadScriptResponse(MissionResponse):
    info: str


class ListScriptsResponse(MissionResponse):
    scripts: list[str]


class ExecuteScriptResponse(MissionResponse):
    script: str


class RunningScriptEntry(BaseModel):
    script: str
    session: str
    started_at: str
    out_log: str
    err_log: str


class RunningScriptsResponse(MissionResponse):
    scripts: list[RunningScriptEntry]


class StopScriptResponse(MissionResponse):
    script: str
    info: str


class ClearScriptsResponse(MissionResponse):
    info: str
    removed: list[str]
