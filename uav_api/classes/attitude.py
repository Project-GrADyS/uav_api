from pydantic import BaseModel


class Attitude_target(BaseModel):
    roll: float       # degrees
    pitch: float      # degrees
    yaw: float        # degrees
    throttle: float   # 0.0 - 1.0
    body_rates: bool = False
