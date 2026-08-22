from pydantic import BaseModel, Field

class Gps_pos(BaseModel):
    """Absolute GPS target. Altitude is meters above HOME (MAV_FRAME_GLOBAL_RELATIVE_ALT), not MSL."""
    lat: float = Field(ge=-90, le=90, description="Target latitude in degrees.", examples=[-15.840081])
    long: float = Field(ge=-180, le=180, description="Target longitude in degrees. Requests spell it 'long'; telemetry responses spell it 'lon'.", examples=[-47.926642])
    alt: float = Field(ge=0, le=10000, description="Target altitude in meters above HOME.", examples=[20.0])
    look_at_target: bool = Field(False, description="If true, yaw the vehicle to face the target while moving (ignored in plane mode).")

# Local_pos, Local_velocity and Body_pos stay unbounded: NED/body offsets and
# velocities are signed by definition, and no universal magnitude limit is
# correct here.

class Local_pos(BaseModel):
    """Position in the local NED frame (meters, origin at HOME). go_to_ned treats it as an absolute target; drive treats it as an offset from the current position."""
    x: float = Field(description="North coordinate in meters.", examples=[10.0])
    y: float = Field(description="East coordinate in meters.", examples=[0.0])
    z: float = Field(description="Down coordinate in meters — negative above HOME (z = -20 is 20 m of altitude).", examples=[-20.0])
    look_at_target: bool = Field(False, description="If true, yaw the vehicle to face the target while moving.")

class Body_pos(BaseModel):
    """Offset in the body FRD frame (meters), relative to the vehicle's current position AND heading: front=5 with heading 90° moves 5 m east. Field names differ from NED on purpose so a body-frame request can never be mistaken for an NED one."""
    front: float = Field(description="Meters forward along the vehicle's current heading.", examples=[5.0])
    right: float = Field(description="Meters to the vehicle's right.", examples=[0.0])
    down: float = Field(description="Meters down — negative to climb, same sign convention as NED z.", examples=[0.0])
    look_at_target: bool = Field(False, description="If true, yaw the vehicle to face the target while moving.")

class Local_velocity(BaseModel):
    """Velocity setpoint in NED axes (m/s). Field names differ from Local_pos on purpose — copying a position into a velocity call fails with 422 instead of silently misbehaving."""
    vx: float = Field(description="North velocity in m/s.", examples=[2.0])
    vy: float = Field(description="East velocity in m/s.", examples=[0.0])
    vz: float = Field(description="Down velocity in m/s — positive descends, negative climbs.", examples=[0.0])
    look_at_target: bool = Field(False, description="If true, yaw the vehicle to face the direction of travel.")
