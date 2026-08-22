from argparse import Namespace
from fastapi import APIRouter, Depends, HTTPException
from uav_api.vehicles.plane import Plane
from uav_api.routers.dependencies import get_plane_instance, get_args
from uav_api.classes.movement import Gps_pos
from uav_api.classes.responses import COMMAND_FAILED, UavResponse

router = APIRouter(
    prefix="/movement",
    tags=["movement"],
)


@router.post("/go_to_gps", tags=["movement"], summary="Sends the plane to the specified GPS position (fire-and-forget DO_REPOSITION)", response_model=UavResponse, responses=COMMAND_FAILED)
def go_to_gps(pos: Gps_pos,
              uav: Plane = Depends(get_plane_instance),
              args: Namespace = Depends(get_args)):
    """Returns as soon as the command is sent; use /movement/go_to_gps_wait to
    block until arrival. Altitude is meters above HOME. The look_at_target
    field is ignored in plane mode."""
    try:
        uav.go_to_gps(pos.lat, pos.long, pos.alt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GO_TO FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid),
            "result": f"Going to coord ({pos.lat}, {pos.long}, {pos.alt})"}


@router.post("/go_to_gps_wait", tags=["movement"], summary="Sends the plane to the specified GPS position and blocks until arrival", response_model=UavResponse, responses=COMMAND_FAILED)
def go_to_gps_wait(pos: Gps_pos,
                   uav: Plane = Depends(get_plane_instance),
                   args: Namespace = Depends(get_args)):
    """Blocks until the plane reaches the target, or fails with 500 after an
    internal 180 s timeout. The look_at_target field is ignored in plane
    mode."""
    try:
        uav.go_to_gps_wait(pos.lat, pos.long, pos.alt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GO_TO FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid),
            "result": f"Arrived at coord ({pos.lat}, {pos.long}, {pos.alt})"}


@router.get("/stop", tags=["movement"], summary="Closest analog of stop for fixed-wing: enter LOITER at current position", response_model=UavResponse, responses=COMMAND_FAILED)
def stop(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    """A fixed-wing plane cannot hover; LOITER orbits the current position."""
    try:
        uav.stop()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STOP FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Plane is loitering"}
