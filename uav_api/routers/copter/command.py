from argparse import Namespace
from fastapi import APIRouter, Depends, HTTPException, Query
from uav_api.vehicles.copter import Copter
from uav_api.classes.responses import UavResponse
from uav_api.routers.dependencies import get_copter_instance, get_args

router = APIRouter(
    prefix = "/command",
    tags = ["command"],
)

@router.get("/arm", tags=["command"], response_model=UavResponse)
def arm(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.change_mode("GUIDED")
        uav.wait_ready_to_arm()
        uav.arm_vehicle()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ARM_COMMAND FAIL: {e}")
    result = "Armed vehicle" if uav.armed() else "Disarmed vehicle"
    return {"device": "uav", "id": str(args.sysid),"result": result}

@router.get("/takeoff", tags=["command"], response_model=UavResponse)
def takeoff(alt: int = Query(15, gt=0, le=500), uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.user_takeoff(alt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TAKEOFFF_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Takeoff successful! Vehicle at {alt} meters"}

@router.get("/brake", tags=["command"], summary="Stops the copter immediately (BRAKE mode)", response_model=UavResponse)
def brake(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    if not uav.change_mode("BRAKE"):
        raise HTTPException(status_code=500, detail="BRAKE_COMMAND FAIL: could not switch to BRAKE mode")
    return {"device": "uav", "id": str(args.sysid), "result": "Copter braking. Use /command/guided to enable movement commands again"}

@router.get("/guided", tags=["command"], summary="Switches to GUIDED mode, enabling movement commands", response_model=UavResponse)
def guided(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    if not uav.change_mode("GUIDED"):
        raise HTTPException(status_code=500, detail="GUIDED_COMMAND FAIL: could not switch to GUIDED mode")
    return {"device": "uav", "id": str(args.sysid), "result": "Copter in GUIDED mode"}

@router.get("/land", tags=["command"], response_model=UavResponse)
def land(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.land_and_disarm()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LAND_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Landed at home successfully"}

@router.get("/rtl", tags=["command"], response_model=UavResponse)
def rlt(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.do_RTL()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RTL_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Landed at home successfully"}

@router.get("/set_air_speed", tags=["command"], description="Changes copter air speed to specified amount (m/s)", response_model=UavResponse)
def set_air_speed(new_v: int = Query(..., ge=0, le=50), uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.change_air_speed(new_v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_AIR_SPEED FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Air speed set to {new_v}m/s"}

@router.get("/set_ground_speed", tags=["command"], description="Changes copter ground speed to specified amount (m/s)", response_model=UavResponse)
def set_ground_speed(new_v: int = Query(..., ge=0, le=50), uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.change_ground_speed(new_v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_GROUND_SPEED FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Ground speed set to {new_v}m/s"}

@router.get("/set_climb_speed", tags=["command"], description="Changes copter climb speed to specified amount (m/s)", response_model=UavResponse)
def set_climb_speed(new_v: int = Query(..., ge=0, le=50), uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.change_climb_speed(new_v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_CLIMB_SPEED FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Climb speed set to {new_v}m/s"}

@router.get("/set_descent_speed", tags=["command"], description="Changes copter descent speed to specified amount (m/s)", response_model=UavResponse)
def set_descent_speed(new_v: int = Query(..., ge=0, le=50), uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.change_descent_speed(new_v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_DESCENT_SPEED FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Descent speed set to {new_v}m/s"}

@router.get("/set_sim_speedup", tags=["command"], description="Changes copter simulation speedup factor", response_model=UavResponse)
def set_sim_speedup(sim_factor: float = Query(..., gt=0), uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.set_parameter("SIM_SPEEDUP", sim_factor)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CHANGE_SIM_SPEEDUP FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Simulation speedup set to {sim_factor}x"}

@router.get("/set_home", tags=["command"], description="Changes the copter HOME location", response_model=UavResponse)
def set_home(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.set_home()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SET_HOME_LOCATION FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Home location set successfully!"}