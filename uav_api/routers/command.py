from argparse import Namespace
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from uav_api.copter import Copter
from uav_api.router_dependencies import get_copter_instance, get_args

command_router = APIRouter(
    prefix = "/command",
    tags = ["command"],
)

class Movement(BaseModel):
    lat: float
    long: float
    alt: int

@command_router.get("/arm", tags=["command"],
    operation_id="arm",
    summary="Arm the vehicle",
    description="Switches to GUIDED mode, waits until the vehicle is ready to arm, then arms the motors. MUST be called before takeoff. The vehicle must have a valid GPS fix and pass all pre-arm checks. Returns the armed state.")
def arm(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.change_mode("GUIDED")
        uav.wait_ready_to_arm()
        uav.arm_vehicle()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ARM_COMMAND FAIL: {e}")
    result = "Armed vehicle" if uav.armed() else "Disarmed vehicle"
    return {"device": "uav", "id": str(args.sysid),"result": result}

@command_router.get("/takeoff", tags=["command"],
    operation_id="takeoff",
    summary="Take off to altitude",
    description="Commands the vehicle to take off vertically to the specified altitude in meters (default: 15m). Blocks until the target altitude is reached. The vehicle must be armed first (call 'arm' before this). Parameter 'alt' is altitude in meters above the launch point.")
def takeoff(alt: int = 15, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.user_takeoff(alt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TAKEOFFF_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Takeoff successful! Vehicle at {alt} meters"}

@command_router.get("/land", tags=["command"],
    operation_id="land",
    summary="Land and disarm",
    description="Commands the vehicle to land vertically at its current position and automatically disarms after touchdown. Blocks until landing is complete. Use 'rtl' instead if you want the vehicle to return to its launch point before landing.")
def land(timeout=60, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.land_and_disarm()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LAND_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Landed at home successfully"}

@command_router.get("/rtl", tags=["command"],
    operation_id="rtl",
    summary="Return to launch and land",
    description="Commands the vehicle to fly back to its HOME/launch position and land there. Blocks until the vehicle has returned and landed. Use this for safe recall. Use 'land' instead if you want to land at the current position.")
def rlt(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.do_RTL()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RTL_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Landed at home successfully"}

@command_router.get("/set_air_speed", tags=["command"],
    operation_id="set_air_speed",
    summary="Set airspeed",
    description="Sets the vehicle's target airspeed in meters per second. This affects how fast the vehicle flies through the air during navigation commands. Parameter 'new_v' is speed in m/s.")
def set_air_speed(new_v: int, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.change_air_speed(new_v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_AIR_SPEED FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Air speed set to {new_v}m/s"}

@command_router.get("/set_ground_speed", tags=["command"],
    operation_id="set_ground_speed",
    summary="Set ground speed",
    description="Sets the vehicle's target ground speed in meters per second. This is the primary speed setting that affects go_to and drive commands. Parameter 'new_v' is speed in m/s.")
def set_ground_speed(new_v: int, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.change_ground_speed(new_v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_GROUND_SPEED FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Ground speed set to {new_v}m/s"}

@command_router.get("/set_climb_speed", tags=["command"],
    operation_id="set_climb_speed",
    summary="Set climb speed",
    description="Sets the vehicle's vertical climb speed in meters per second. Affects how fast the vehicle ascends during altitude changes. Parameter 'new_v' is speed in m/s.")
def set_climb_speed(new_v: int, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.change_climb_speed(new_v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_CLIMB_SPEED FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Climb speed set to {new_v}m/s"}

@command_router.get("/set_descent_speed", tags=["command"],
    operation_id="set_descent_speed",
    summary="Set descent speed",
    description="Sets the vehicle's vertical descent speed in meters per second. Affects how fast the vehicle descends during altitude changes. Parameter 'new_v' is speed in m/s.")
def set_descent_speed(new_v: int, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.change_descent_speed(new_v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_DESCENT_SPEED FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Descent speed set to {new_v}m/s"}

@command_router.get("/set_sim_speedup", tags=["command"],
    operation_id="set_sim_speedup",
    summary="Set simulation speed multiplier",
    description="Sets the SITL simulation time multiplier. Only works in simulated mode. A value of 5 means the simulation runs 5x faster than real time. Parameter 'sim_factor' is the multiplier (e.g., 1.0 = real time, 10.0 = 10x speed).")
def set_sim_speedup(sim_factor: float, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.set_parameter("SIM_SPEEDUP", sim_factor)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_SIM_SPEEDUP FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Simulation speedup set to {sim_factor}x"}

@command_router.get("/set_home", tags=["command"],
    operation_id="set_home",
    summary="Set current position as HOME",
    description="Redefines the HOME position to the vehicle's current GPS location. HOME is the origin (0,0,0) of the NED coordinate frame and the destination for RTL commands. Use this to update the return-to-launch point.")
def set_home(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.set_home()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SET_HOME_LOCATION FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Home location set successfully!"}
