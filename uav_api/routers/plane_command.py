from argparse import Namespace
from fastapi import APIRouter, Depends, HTTPException
from uav_api.plane import Plane
from uav_api.router_dependencies import get_plane_instance, get_args

plane_command_router = APIRouter(
    prefix="/command",
    tags=["command"],
)


@plane_command_router.get("/arm", tags=["command"], summary="Switches to GUIDED, waits ready-to-arm, and arms the plane")
def arm(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    try:
        uav.change_mode("GUIDED")
        uav.wait_ready_to_arm()
        uav.arm_vehicle()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ARM_COMMAND FAIL: {e}")
    result = "Armed vehicle" if uav.armed() else "Disarmed vehicle"
    return {"device": "uav", "id": str(args.sysid), "result": result}


@plane_command_router.get("/disarm", tags=["command"], summary="Disarms the plane")
def disarm(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    try:
        uav.disarm_vehicle()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DISARM_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Disarmed vehicle"}


@plane_command_router.get("/takeoff", tags=["command"], summary="Takes off to the specified altitude (fixed-wing or VTOL)")
def takeoff(alt: float, pitch_deg: float = 15, vtol: bool = False,
            uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    try:
        uav.takeoff(alt, pitch_deg=pitch_deg, vtol=vtol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TAKEOFF_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid),
            "result": f"Takeoff successful! Vehicle at {alt} meters"}


@plane_command_router.get("/land", tags=["command"], summary="Switches to LAND mode (assumes a runway-aligned approach is already arranged)")
def land(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    try:
        uav.land()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LAND_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Landed successfully"}


@plane_command_router.get("/rtl", tags=["command"], summary="Switches to RTL and returns when plane is near home")
def rtl(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    try:
        uav.do_RTL()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RTL_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Returned to launch"}


@plane_command_router.get("/set_home", tags=["command"], summary="Sets the HOME position to the vehicle's current position")
def set_home(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    try:
        uav.set_home()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SET_HOME_LOCATION FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Home location set successfully!"}
