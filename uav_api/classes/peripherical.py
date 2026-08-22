from pydantic import BaseModel, Field


class Servo_output(BaseModel):
    channel: int = Field(ge=1, le=16, description="Servo output channel number (1-16).", examples=[9])
    pwm: int = Field(ge=800, le=2200, description="PWM pulse width in microseconds (800-2200; ~1500 is typically neutral).", examples=[1500])
