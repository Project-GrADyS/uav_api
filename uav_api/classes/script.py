from pydantic import BaseModel, Field

class Script(BaseModel):
    script_name: str = Field(description="Script filename. Directory components are stripped and '.py' is appended when missing, so 'my_mission' targets 'my_mission.py'.", examples=["my_mission.py"])
