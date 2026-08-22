from argparse import Namespace
from fastapi import APIRouter, Depends, HTTPException, Query
from uav_api.vehicles.plane import Plane
from uav_api.classes.responses import COMMAND_FAILED, UavResponse
from uav_api.routers.dependencies import get_plane_instance, get_args

router = APIRouter(
    prefix="/command",
    tags=["command"],
)


@router.get("/arm", tags=["command"], summary="Switches to GUIDED, waits ready-to-arm, and arms the plane", response_model=UavResponse, responses=COMMAND_FAILED)
def arm(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    """Blocks until pre-arm checks pass (requires GPS lock outdoors) before
    arming."""
    try:
        uav.change_mode("GUIDED")
        uav.wait_ready_to_arm()
        uav.arm_vehicle()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ARM_COMMAND FAIL: {e}")
    result = "Armed vehicle" if uav.armed() else "Disarmed vehicle"
    return {"device": "uav", "id": str(args.sysid), "result": result}


@router.get("/disarm", tags=["command"], summary="Disarms the plane", response_model=UavResponse, responses=COMMAND_FAILED)
def disarm(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    try:
        uav.disarm_vehicle()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DISARM_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Disarmed vehicle"}


@router.get("/takeoff", tags=["command"], summary="Takes off to the specified altitude (fixed-wing or VTOL)", response_model=UavResponse, responses=COMMAND_FAILED)
def takeoff(alt: float = Query(..., gt=0, le=1000, description="Target altitude in meters above HOME."),
            pitch_deg: float = Query(15, description="Requested climb pitch in degrees. Currently a no-op for fixed-wing (ArduPlane derives climb attitude from TKOFF_LVL_PITCH/PTCH_LIM_MAX_DEG); kept for API stability."),
            vtol: bool = Query(False, description="If true, performs a QuadPlane VTOL takeoff (MAV_CMD_NAV_VTOL_TAKEOFF) instead of a fixed-wing one."),
            uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    """Fixed-wing: enters TAKEOFF mode, blocks until the altitude is reached
    (up to 120 s), then returns to GUIDED."""
    try:
        uav.takeoff(alt, pitch_deg=pitch_deg, vtol=vtol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TAKEOFF_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid),
            "result": f"Takeoff successful! Vehicle at {alt} meters"}


@router.get("/land", tags=["command"], summary="Switches to LAND mode (assumes a runway-aligned approach is already arranged)", response_model=UavResponse, responses=COMMAND_FAILED)
def land(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    """Unlike copter, this is not 'land here': naive callers will not get a
    controlled landing. Use /command/land_at to land at a chosen point."""
    try:
        uav.land()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LAND_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Landed successfully"}


@router.get("/land_at", tags=["command"], summary="Uploads a simple landing mission at the given point and starts it in AUTO mode (returns immediately)", response_model=UavResponse, responses=COMMAND_FAILED)
def land_at(lat: float = Query(..., ge=-90, le=90, description="Landing point latitude in degrees."),
            long: float = Query(..., ge=-180, le=180, description="Landing point longitude in degrees."),
            alt: float = Query(0, ge=0, le=10000, description="Landing point altitude in meters above HOME."),
            vtol: bool = Query(False, description="If true, uses MAV_CMD_NAV_VTOL_LAND (QuadPlane) instead of MAV_CMD_NAV_LAND."),
            uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    """Returns immediately after switching to AUTO; poll telemetry to track
    the landing."""
    try:
        uav.land_at(lat, long, alt, vtol=vtol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LAND_AT_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid),
            "result": f"Landing mission started for coord ({lat}, {long})"}


@router.get("/rtl", tags=["command"], summary="Switches to RTL and returns when plane is near home", response_model=UavResponse, responses=COMMAND_FAILED)
def rtl(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    """Blocks until the plane is near HOME but does NOT wait for disarm — a
    fixed-wing plane loiters at home unless a landing is in the mission."""
    try:
        uav.do_RTL()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RTL_COMMAND FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Returned to launch"}


@router.get("/set_home", tags=["command"], summary="Sets the HOME position to the vehicle's current position", response_model=UavResponse, responses=COMMAND_FAILED)
def set_home(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    try:
        uav.set_home()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SET_HOME_LOCATION FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Home location set successfully!"}
