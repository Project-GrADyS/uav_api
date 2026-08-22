from argparse import Namespace
from fastapi import APIRouter, Depends, HTTPException, Query
from uav_api.vehicles.copter import Copter
from uav_api.classes.responses import COMMAND_FAILED, UavResponse
from uav_api.routers.dependencies import get_copter_instance, get_args

router = APIRouter(
    prefix = "/command",
    tags = ["command"],
)

@router.get("/arm", tags=["command"], summary="Arms the copter", response_model=UavResponse, responses=COMMAND_FAILED)
def arm(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    """Switches to GUIDED mode, blocks until the vehicle is ready to arm
    (pre-arm checks pass — requires GPS lock outdoors), then arms. If arming
    hangs, check /telemetry/gps_raw: 'satelites' should be at least 6."""
    try:
        uav.change_mode("GUIDED")
        uav.wait_ready_to_arm()
        uav.arm_vehicle()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ARM_COMMAND FAIL: {e}")
    result = "Armed vehicle" if uav.armed() else "Disarmed vehicle"
    return {"device": "uav", "id": str(args.sysid),"result": result}

@router.get("/takeoff", tags=["command"], summary="Takes off to the specified altitude", response_model=UavResponse, responses=COMMAND_FAILED)
def takeoff(alt: int = Query(15, gt=0, le=500, description="Target altitude in meters above HOME."), uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    """Blocks until the vehicle reaches the target altitude. The vehicle must
    be armed and in GUIDED mode (see /command/arm)."""
    try:
        uav.user_takeoff(alt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TAKEOFFF_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Takeoff successful! Vehicle at {alt} meters"}

@router.get("/brake", tags=["command"], summary="Stops the copter immediately (BRAKE mode)", response_model=UavResponse, responses=COMMAND_FAILED)
def brake(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    """Leaves GUIDED mode: movement commands are rejected until /command/guided
    is called again."""
    if not uav.change_mode("BRAKE"):
        raise HTTPException(status_code=500, detail="BRAKE_COMMAND FAIL: could not switch to BRAKE mode")
    return {"device": "uav", "id": str(args.sysid), "result": "Copter braking. Use /command/guided to enable movement commands again"}

@router.get("/guided", tags=["command"], summary="Switches to GUIDED mode, enabling movement commands", response_model=UavResponse, responses=COMMAND_FAILED)
def guided(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    if not uav.change_mode("GUIDED"):
        raise HTTPException(status_code=500, detail="GUIDED_COMMAND FAIL: could not switch to GUIDED mode")
    return {"device": "uav", "id": str(args.sysid), "result": "Copter in GUIDED mode"}

@router.get("/land", tags=["command"], summary="Lands the copter at its current position", response_model=UavResponse, responses=COMMAND_FAILED)
def land(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    """Switches to LAND mode and blocks until the vehicle touches down and
    disarms."""
    try:
        uav.land_and_disarm()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LAND_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Landed at home successfully"}

@router.get("/rtl", tags=["command"], summary="Returns to the HOME position and lands (RTL mode)", response_model=UavResponse, responses=COMMAND_FAILED)
def rlt(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    """Blocks until the vehicle has landed at HOME and disarmed."""
    try:
        uav.do_RTL()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RTL_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Landed at home successfully"}

@router.get("/set_air_speed", tags=["command"], summary="Changes copter air speed", response_model=UavResponse, responses=COMMAND_FAILED)
def set_air_speed(new_v: int = Query(..., ge=0, le=50, description="New air speed in m/s."), uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.change_air_speed(new_v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_AIR_SPEED FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Air speed set to {new_v}m/s"}

@router.get("/set_ground_speed", tags=["command"], summary="Changes copter ground speed", response_model=UavResponse, responses=COMMAND_FAILED)
def set_ground_speed(new_v: int = Query(..., ge=0, le=50, description="New ground speed in m/s."), uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.change_ground_speed(new_v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_GROUND_SPEED FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Ground speed set to {new_v}m/s"}

@router.get("/set_climb_speed", tags=["command"], summary="Changes copter climb speed", response_model=UavResponse, responses=COMMAND_FAILED)
def set_climb_speed(new_v: int = Query(..., ge=0, le=50, description="New climb speed in m/s."), uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.change_climb_speed(new_v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_CLIMB_SPEED FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Climb speed set to {new_v}m/s"}

@router.get("/set_descent_speed", tags=["command"], summary="Changes copter descent speed", response_model=UavResponse, responses=COMMAND_FAILED)
def set_descent_speed(new_v: int = Query(..., ge=0, le=50, description="New descent speed in m/s."), uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.change_descent_speed(new_v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_DESCENT_SPEED FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Descent speed set to {new_v}m/s"}

@router.get("/set_sim_speedup", tags=["command"], summary="Changes the simulation speedup factor (SITL only)", response_model=UavResponse, responses=COMMAND_FAILED)
def set_sim_speedup(sim_factor: float = Query(..., gt=0, description="Simulation time multiplier (SIM_SPEEDUP parameter). Values above ~10 introduce MAVLink timing artifacts."), uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    """Only meaningful when the API was started with --simulated; on a real
    vehicle the SIM_SPEEDUP parameter does not exist."""
    try:
        uav.set_parameter("SIM_SPEEDUP", sim_factor)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_SIM_SPEEDUP FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Simulation speedup set to {sim_factor}x"}

@router.get("/set_home", tags=["command"], summary="Sets the HOME location to the copter's current position", response_model=UavResponse, responses=COMMAND_FAILED)
def set_home(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    """HOME is the origin of the NED frame and the RTL destination."""
    try:
        uav.set_home()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SET_HOME_LOCATION FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Home location set successfully!"}
