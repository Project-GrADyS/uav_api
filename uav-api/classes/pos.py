from pydantic import BaseModel

class GPS_pos(BaseModel):
    lat: float
    long: float
    alt: float

class Local_pos(BaseModel):
    x: float
    y: float
    z: float