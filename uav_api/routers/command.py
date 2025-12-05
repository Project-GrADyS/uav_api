from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from uav_api.copter import Copter
from uav_api.copter_connection import get_copter_instance

command_router = APIRouter(
    prefix = "/command",
    tags = ["command"],
)

class Movement(BaseModel):
    lat: float
    long: float
    alt: int

@command_router.get("/arm", tags=["command"])
def arm(uav: Copter = Depends(get_copter_instance)):
    try:
        uav.change_mode("GUIDED")
        uav.wait_ready_to_arm()
        uav.arm_vehicle()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ARM_COMMAND FAIL: {e}")
    result = "Armed vehicle" if uav.armed() else "Disarmed vehicle"
    return {"result": result}

@command_router.get("/takeoff", tags=["command"])
def takeoff(alt: int = 15, uav: Copter = Depends(get_copter_instance)):
    try:
        uav.user_takeoff(alt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TAKEOFFF_COMMAND FAIL: {e}")
    return {"result": f"Takeoff successful! Vehicle at {alt} meters"}

@command_router.get("/land", tags=["command"])
def land(timeout=60, uav: Copter = Depends(get_copter_instance)):
    try:
        uav.land_and_disarm()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LAND_COMMAND FAIL: {e}")
    return {"result": "Landed at home successfully"}

@command_router.get("/rtl", tags=["command"])
def rlt(uav: Copter = Depends(get_copter_instance)):
    try:
        uav.do_RTL()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RTL_COMMAND FAIL: {e}")
    return {"result": "Landed at home successfully"}

@command_router.get("/set_air_speed", tags=["command"], description=f"Changes copter air speed to specified amount (m/s)")
def set_air_speed(new_v: int, uav: Copter = Depends(get_copter_instance)):
    try:
        uav.change_air_speed(new_v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_AIR_SPEED FAIL: {e}")
    return {"result": f"Air speed set to {new_v}m/s"}

@command_router.get("/set_ground_speed", tags=["command"], description=f"Changes copter ground speed to specified amount (m/s)")
def set_ground_speed(new_v: int, uav: Copter = Depends(get_copter_instance)):
    try:
        uav.change_ground_speed(new_v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_GROUND_SPEED FAIL: {e}")
    return {"result": f"Ground speed set to {new_v}m/s"}

@command_router.get("/set_climb_speed", tags=["command"], description=f"Changes copter climb speed to specified amount (m/s)")
def set_climb_speed(new_v: int, uav: Copter = Depends(get_copter_instance)):
    try:
        uav.change_climb_speed(new_v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_CLIMB_SPEED FAIL: {e}")
    return {"result": f"Climb speed set to {new_v}m/s"}

@command_router.get("/set_descent_speed", tags=["command"], description=f"Changes copter descent speed to specified amount (m/s)")
def set_descent_speed(new_v: int, uav: Copter = Depends(get_copter_instance)):
    try:
        uav.change_descent_speed(new_v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_DESCENT_SPEED FAIL: {e}")
    return {"result": f"Descent speed set to {new_v}m/s"}

@command_router.get("/set_sim_speedup", tags=["command"], description=f"Changes copter simulation speedup factor")
def set_sim_speedup(sim_factor: float, uav: Copter = Depends(get_copter_instance)):
    try:
        uav.set_parameter("SIM_SPEEDUP", sim_factor)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_SIM_SPEEDUP FAIL: {e}")
    return {"result": f"Simulation speedup set to {sim_factor}x"}

@command_router.get("/set_home", tags=["command"], description="Changes the copter HOME location")
def set_home(uav: Copter = Depends(get_copter_instance)):
    try:
        uav.set_home()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SET_HOME_LOCATION FAIL: {e}")
    return {"result": f"Home location set successfully!"}