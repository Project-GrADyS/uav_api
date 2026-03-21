from pydantic import BaseModel

class Gps_pos(BaseModel):
    lat: float
    long: float
    alt: float
    look_at_target: bool = False

class Local_pos(BaseModel):
    x: float
    y: float
    z: float
    look_at_target: bool = False

class Local_velocity(BaseModel):
    vx: float
    vy: float
    vz: float
    look_at_target: bool = False