from pydantic import BaseModel, Field

class Gps_pos(BaseModel):
    lat: float = Field(ge=-90, le=90)
    long: float = Field(ge=-180, le=180)
    alt: float = Field(ge=0, le=10000)
    look_at_target: bool = False

# Local_pos, Local_velocity and Body_pos stay unbounded: NED/body offsets and
# velocities are signed by definition, and no universal magnitude limit is
# correct here.

class Local_pos(BaseModel):
    x: float
    y: float
    z: float
    look_at_target: bool = False

class Body_pos(BaseModel):
    front: float
    right: float
    down: float
    look_at_target: bool = False

class Local_velocity(BaseModel):
    vx: float
    vy: float
    vz: float
    look_at_target: bool = False
