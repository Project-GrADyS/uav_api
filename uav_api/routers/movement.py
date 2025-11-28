from time import sleep
from fastapi import APIRouter, Depends, HTTPException
from uav_api.copter import Copter
from uav_api.copter_connection import get_copter_instance
from uav_api.classes.pos import GPS_pos, Local_pos

movement_router = APIRouter(
    prefix = "/movement",
    tags = ["movement"],
)

@movement_router.post("/go_to_gps/", tags=["movement"], summary="Moves the copter to specified GPS position")
def go_to_gps(pos: GPS_pos, uav: Copter = Depends(get_copter_instance)):
    try:
        uav.go_to_gps(pos.lat, pos.long, pos.alt)
        #uav.ensure_moving()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GO_TO FAIL: {e}")
    return {"result": f"Going to coord ({pos.lat}, {pos.long}, {pos.alt})"}

@movement_router.post("/go_to_gps_wait", tags=["movement"], summary="Moves and waits for the copter to get to specified GPS position")
def go_to_gps_wait(pos: GPS_pos, uav: Copter = Depends(get_copter_instance)):
    try:
        uav.go_to_gps(pos.lat, pos.long, pos.alt)
        #uav.ensure_moving()
        target_loc = uav.mav_location(pos.lat, pos.long, pos.alt)
        uav.wait_location(target_loc, timeout=60)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GO_TO FAIL: {e}")
    return {"result": f"Arrived at coord ({pos.lat}, {pos.long}, {pos.alt})"}

@movement_router.post("/go_to_ned", tags=["movement"], summary="Moves to specified NED position")
def go_to_ned(pos: Local_pos, uav: Copter = Depends(get_copter_instance)):
    try:
        uav.go_to_ned(pos.x, pos.y, pos.z) 
        #uav.ensure_moving()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GO_TO FAIL: {e}")
    return {"result": f"Going to NED coord ({pos.x}, {pos.y}, {pos.z})"}

@movement_router.post("/go_to_ned_wait", tags=["movement"], summary="Moves and waits for the copter to get to specified NED position")
def go_to_ned_wait(pos: Local_pos, uav: Copter = Depends(get_copter_instance)):
    try:
        uav.go_to_ned(pos.x, pos.y, pos.z)
        #uav.ensure_moving()
        uav.wait_ned_position(pos)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GO_TO FAIL: {e}")
    return {"result": f"Arrived at NED coord ({pos.x}, {pos.y}, {pos.z})"}

@movement_router.post("/drive", tags=["movement"], summary="Drives copter the specified amount in meters")
def drive(pos: Local_pos, uav: Copter = Depends(get_copter_instance)):
    try:
        pos.z = -pos.z # from NEU to NED
        uav.drive_ned(pos.x, pos.y, pos.z)
        #uav.ensure_moving()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DRIVE FAIL: {e}")
    return {"result": "Copter is driving"}

@movement_router.post("/drive_wait", tags=["movement"], summary="Drives and waits copter the specified amount in meters")
def drive_wait(pos: Local_pos, uav: Copter = Depends(get_copter_instance)):
    try:
        pos.z = -pos.z # from NEU to NED
        current_pos = uav.get_ned_position()
        uav.drive_ned(pos.x, pos.y, pos.z)
        #uav.ensure_moving()
        target_pos = Local_pos(x=current_pos.x + pos.x, y=current_pos.y + pos.y, z=current_pos.z + pos.z)
        uav.wait_ned_position(target_pos)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DRIVE FAIL: {e}")
    return {"result": f"Copter arrived at ({target_pos.x}, {target_pos.y}, {target_pos.z})"}

@movement_router.get("/stop", tags=["movement"])
def stop(uav: Copter = Depends(get_copter_instance)):
    try:
        uav.stop()
        #uav.ensure_holding()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STOP FAIL: {e}")
    return {"result": "Copter has stopped"}

@movement_router.get("/resume", tags=["movement"])
def resume(uav: Copter = Depends(get_copter_instance)):
    try:
        uav.resume()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RESUME FAIL: {e}")
    return {"result": "Copter has resumed movement"}