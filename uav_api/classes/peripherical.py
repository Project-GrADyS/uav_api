from pydantic import BaseModel, Field


class Servo_output(BaseModel):
    channel: int = Field(ge=1, le=16)
    pwm: int = Field(ge=800, le=2200)
