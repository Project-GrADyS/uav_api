from argparse import Namespace
from fastapi import APIRouter, Depends, HTTPException
from uav_api.vehicles.plane import Plane
from uav_api.routers.router_dependencies import get_plane_instance, get_args
from uav_api.classes.movement import Gps_pos

plane_movement_router = APIRouter(
    prefix="/movement",
    tags=["movement"],
)


@plane_movement_router.post("/go_to_gps", tags=["movement"], summary="Sends the plane to the specified GPS position (fire-and-forget DO_REPOSITION)")
def go_to_gps(pos: Gps_pos,
              uav: Plane = Depends(get_plane_instance),
              args: Namespace = Depends(get_args)):
    try:
        uav.go_to_gps(pos.lat, pos.long, pos.alt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GO_TO FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid),
            "result": f"Going to coord ({pos.lat}, {pos.long}, {pos.alt})"}


@plane_movement_router.post("/go_to_gps_wait", tags=["movement"], summary="Sends the plane to the specified GPS position and blocks until arrival")
def go_to_gps_wait(pos: Gps_pos,
                   uav: Plane = Depends(get_plane_instance),
                   args: Namespace = Depends(get_args)):
    try:
        uav.go_to_gps_wait(pos.lat, pos.long, pos.alt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GO_TO FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid),
            "result": f"Arrived at coord ({pos.lat}, {pos.long}, {pos.alt})"}


@plane_movement_router.post("/land_at", tags=["movement"], summary="Flies to the specified GPS position then switches to LAND")
def land_at(pos: Gps_pos,
            uav: Plane = Depends(get_plane_instance),
            args: Namespace = Depends(get_args)):
    try:
        uav.land_at(pos.lat, pos.long, pos.alt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LAND_AT FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid),
            "result": f"Landed at coord ({pos.lat}, {pos.long}, {pos.alt})"}


@plane_movement_router.get("/stop", tags=["movement"], summary="Closest analog of stop for fixed-wing: enter LOITER at current position")
def stop(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    try:
        uav.stop()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STOP FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Plane is loitering"}
