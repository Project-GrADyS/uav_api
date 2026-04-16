from pydantic import BaseModel


class Servo_output(BaseModel):
    channel: int
    pwm: int
