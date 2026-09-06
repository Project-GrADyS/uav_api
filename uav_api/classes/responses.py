"""Response models for every JSON endpoint.

The canonical envelope is UavResponse: device/id/result on every response.
Telemetry payload nesting mirrors the wire format exactly — consumers (and
the integration tests) read paths like info.position.relative_alt, so the
models document the contract rather than reshape it.
"""

from typing import Literal

from pydantic import BaseModel, Field


class UavResponse(BaseModel):
    device: Literal["uav"] = Field("uav", description="Device class emitting the response; always 'uav'.")
    id: str = Field(description="MAVLink system id of the vehicle, as configured with --sysid.")
    result: str = Field(description="Human-readable outcome of the operation.")


# --- errors ---

class ErrorResponse(BaseModel):
    """Body of every non-2xx response, matching FastAPI's HTTPException."""
    detail: str = Field(description="Error message, prefixed with the operation that failed (e.g. 'ARM_COMMAND FAIL: <cause>').")


def error_responses(codes: dict) -> dict:
    """Build a FastAPI `responses=` mapping from {status_code: description}."""
    return {code: {"model": ErrorResponse, "description": description} for code, description in codes.items()}


# Every handler wraps the vehicle call in try/except and re-raises as HTTP 500.
COMMAND_FAILED = error_responses({500: "The underlying MAVLink command failed or timed out; detail carries the cause."})


# --- telemetry payloads ---

class GeneralInfo(BaseModel):
    """VFR_HUD fields."""
    airspeed: float = Field(description="Airspeed in m/s.")
    groundspeed: float = Field(description="Ground speed in m/s.")
    heading: float = Field(description="Heading in degrees (0-360, 0 = North).")
    throttle: float = Field(description="Throttle in percent (0-100).")
    alt: float = Field(description="Altitude in meters (MSL).")


class GeneralTelemetryResponse(UavResponse):
    info: GeneralInfo


class GpsPosition(BaseModel):
    lat: float = Field(description="Latitude in degrees.")
    lon: float = Field(description="Longitude in degrees.")
    alt: float = Field(description="Altitude in meters (MSL).")
    relative_alt: float = Field(description="Altitude in meters above HOME (not above ground level).")


class NedVelocity(BaseModel):
    vx: float = Field(description="North velocity in m/s.")
    vy: float = Field(description="East velocity in m/s.")
    vz: float = Field(description="Down velocity in m/s (positive = descending).")


class GpsInfo(BaseModel):
    position: GpsPosition
    velocity: NedVelocity
    heading: float = Field(description="Heading in degrees (0-360, 0 = North).")


class GpsTelemetryResponse(UavResponse):
    info: GpsInfo


class RawGpsPosition(BaseModel):
    lat: float = Field(description="Latitude in degrees.")
    lon: float = Field(description="Longitude in degrees.")
    alt: float = Field(description="Altitude in meters (MSL).")


class RawGpsVelocity(BaseModel):
    ground_speed: float = Field(description="GPS ground speed in m/s.")
    speed_direction: float = Field(description="Course over ground in degrees.")


class RawGpsInfo(BaseModel):
    position: RawGpsPosition
    velocity: RawGpsVelocity
    # Misspelling preserved: it is the wire contract consumers already parse.
    satelites: int = Field(description="Number of visible satellites. The field name spelling is intentional wire contract.")


class RawGpsTelemetryResponse(UavResponse):
    info: RawGpsInfo


class NedPosition(BaseModel):
    x: float = Field(description="North position in meters, relative to HOME.")
    y: float = Field(description="East position in meters, relative to HOME.")
    z: float = Field(description="Down position in meters — negative above HOME (a vehicle 20 m above HOME reports z = -20).")


class NedInfo(BaseModel):
    position: NedPosition
    velocity: NedVelocity


class NedTelemetryResponse(UavResponse):
    info: NedInfo


class CompassFitness(BaseModel):
    x: float = Field(description="Calibration fitness for the X axis (RMS field error; lower is better).")
    y: float = Field(description="Calibration fitness for the Y axis (RMS field error; lower is better).")
    z: float = Field(description="Calibration fitness for the Z axis (RMS field error; lower is better).")


class CompassInfo(BaseModel):
    calibration_status: int = Field(description="MAG_CAL_STATUS enum value of the last calibration report.")
    autosaved: bool = Field(description="Whether the calibration was automatically saved.")
    fitness: CompassFitness


class CompassTelemetryResponse(UavResponse):
    info: CompassInfo


class SysStatusResponse(UavResponse):
    status: dict = Field(description="Raw MAVLink SYS_STATUS message as returned by pymavlink's to_dict(); values keep MAVLink's native units (mV, cA, c%).")


class SensorState(BaseModel):
    present: bool = Field(description="Sensor is present on the vehicle.")
    enabled: bool = Field(description="Sensor is enabled.")
    health: bool = Field(description="Sensor reports healthy.")


class SensorStatusResponse(UavResponse):
    status: dict[str, SensorState] = Field(description="Per-sensor flags keyed by sensor name: gyro, accelerometer, gps, altitude_control, position_control, radio_receiver, motor_output, battery, pre_arm_check.")


class BatteryInfo(BaseModel):
    """SYS_STATUS battery fields, unscaled (MAVLink native units)."""
    voltage: float = Field(description="Battery voltage in millivolts (SYS_STATUS.voltage_battery).")
    current: float = Field(description="Battery current in centiamperes, i.e. units of 10 mA; -1 if not measured.")
    battery_remaining: float = Field(description="Remaining battery in percent; -1 if not estimated.")


class BatteryInfoResponse(UavResponse):
    info: BatteryInfo


class ErrorInfo(BaseModel):
    communication_drop_rate: float = Field(description="MAVLink communication drop rate in c% (units of 1/100 percent).")
    communication_errors: float = Field(description="Count of corrupted packets on the MAVLink link (SYS_STATUS.errors_comm).")
    autopilot_errors: list[int] = Field(description="Non-zero autopilot-specific error counters (SYS_STATUS.errors_count1-4).")


class ErrorInfoResponse(UavResponse):
    info: ErrorInfo


class HomeInfoResponse(UavResponse):
    # Flat on the envelope, as always: home_info predates the info nesting.
    lat: float = Field(description="HOME latitude in degrees.")
    lon: float = Field(description="HOME longitude in degrees.")
    altitude: float = Field(description="HOME altitude in meters (MSL).")
    x: float = Field(description="HOME North position in meters in the local NED frame.")
    y: float = Field(description="HOME East position in meters in the local NED frame.")
    z: float = Field(description="HOME Down position in meters in the local NED frame.")


# --- mission ---

class MissionResponse(UavResponse):
    # The numeric codes (42-52) predate the result envelope. Deprecated:
    # they will be removed together with the unversioned route aliases.
    type: int = Field(json_schema_extra={"deprecated": True}, description="Legacy numeric message code (42-52). Deprecated; will be removed together with the unversioned route aliases.")


class UploadScriptResponse(MissionResponse):
    info: str = Field(description="Confirmation message with the sanitized filename and the path it was saved to.")


class ListScriptsResponse(MissionResponse):
    scripts: list[str] = Field(description="Filenames of the uploaded .py scripts in the scripts directory.")


class ExecuteScriptResponse(MissionResponse):
    script: str = Field(description="Filename of the script that was started (with its .py suffix).")


class RunningScriptEntry(BaseModel):
    script: str = Field(description="Script filename.")
    session: str = Field(description="tmux session name hosting the script (attach with 'tmux attach -t <session>').")
    started_at: str = Field(description="Start timestamp, formatted YYYYMMDD_HHMMSS.")
    out_log: str = Field(description="Path (on the vehicle) of the file capturing the script's stdout.")
    err_log: str = Field(description="Path (on the vehicle) of the file capturing the script's stderr.")


class RunningScriptsResponse(MissionResponse):
    scripts: list[RunningScriptEntry]


class StopScriptResponse(MissionResponse):
    script: str = Field(description="Filename of the script that was stopped.")
    info: str = Field(description="Stop confirmation message.")


class ClearScriptsResponse(MissionResponse):
    info: str = Field(description="Summary of how many script files were removed.")
    removed: list[str] = Field(description="Filenames of the removed script files.")


class ScriptLogResponse(UavResponse):
    # Deliberately extends UavResponse, not MissionResponse: the numeric `type`
    # codes are deprecated, so this endpoint does not mint a new one.
    script: str = Field(description="Filename of the script whose log was read (with its .py suffix).")
    stream: Literal["out", "err"] = Field(description="Which stream was read: 'out' for stdout, 'err' for stderr.")
    lines: list[str] = Field(description="Last `tail` lines of the log file, oldest first, without trailing newlines.")
