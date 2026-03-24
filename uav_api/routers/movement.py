from argparse import Namespace
from time import sleep
from fastapi import APIRouter, Depends, HTTPException
from uav_api.copter import Copter
from uav_api.router_dependencies import get_copter_instance, get_args
from uav_api.classes.movement import Gps_pos, Local_pos, Local_velocity

movement_router = APIRouter(
    prefix = "/movement",
    tags = ["movement"],
)

@movement_router.post("/go_to_gps/", tags=["movement"],
    operation_id="go_to_gps",
    summary="Fly to GPS coordinates (non-blocking)",
    description="Commands the vehicle to fly to the specified GPS position (latitude, longitude, altitude). Returns immediately after sending the command — does NOT wait for arrival. Use 'go_to_gps_wait' if you need to wait until the vehicle arrives. Coordinates: lat/long in decimal degrees, alt in meters above sea level. Set look_at_target=true to yaw toward the destination.")
def go_to_gps(pos: Gps_pos, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.go_to_gps(pos.lat, pos.long, pos.alt, pos.look_at_target)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GO_TO FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Going to coord ({pos.lat}, {pos.long}, {pos.alt})"}

@movement_router.post("/go_to_gps_wait", tags=["movement"],
    operation_id="go_to_gps_wait",
    summary="Fly to GPS coordinates and wait for arrival",
    description="Commands the vehicle to fly to the specified GPS position and blocks until arrival (timeout: 60s). Use this when you need to execute sequential waypoints — the tool returns only after the vehicle reaches the target (within ~10m). Coordinates: lat/long in decimal degrees, alt in meters above sea level.")
def go_to_gps_wait(pos: Gps_pos, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.go_to_gps(pos.lat, pos.long, pos.alt, pos.look_at_target)
        target_loc = uav.mav_location(pos.lat, pos.long, pos.alt)
        uav.wait_location(target_loc, timeout=60)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GO_TO FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Arrived at coord ({pos.lat}, {pos.long}, {pos.alt})"}

@movement_router.post("/go_to_ned", tags=["movement"],
    operation_id="go_to_ned",
    summary="Fly to NED position (non-blocking)",
    description="Commands the vehicle to fly to an absolute position in the NED (North-East-Down) coordinate frame, relative to HOME. Returns immediately — does NOT wait for arrival. Use 'go_to_ned_wait' to wait. Axes: x=North(+)/South(-), y=East(+)/West(-), z=Down(+)/Up(-), all in meters. Set look_at_target=true to yaw toward the destination.")
def go_to_ned(pos: Local_pos, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.go_to_ned(pos.x, pos.y, pos.z, look_at_target=pos.look_at_target)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GO_TO FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Going to NED coord ({pos.x}, {pos.y}, {pos.z})"}

@movement_router.post("/go_to_ned_wait", tags=["movement"],
    operation_id="go_to_ned_wait",
    summary="Fly to NED position and wait for arrival",
    description="Commands the vehicle to fly to an absolute NED position and blocks until arrival (timeout: 60s). Use for sequential waypoint navigation in local coordinates. Axes: x=North(+)/South(-), y=East(+)/West(-), z=Down(+)/Up(-), all in meters.")
def go_to_ned_wait(pos: Local_pos, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.go_to_ned(pos.x, pos.y, pos.z, look_at_target=pos.look_at_target)
        uav.wait_ned_position(pos)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GO_TO FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Arrived at NED coord ({pos.x}, {pos.y}, {pos.z})"}

@movement_router.post("/drive", tags=["movement"],
    operation_id="drive",
    summary="Move by relative offset (non-blocking)",
    description="Commands the vehicle to move by a relative offset from its CURRENT position in the NED frame. Returns immediately — does NOT wait for arrival. Unlike go_to_ned which uses absolute positions from HOME, drive moves relative to where the vehicle is right now. Axes: x=North(+)/South(-), y=East(+)/West(-), z=Down(+)/Up(-), all in meters.")
def drive(pos: Local_pos, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.drive_ned(pos.x, pos.y, pos.z, look_at_target=pos.look_at_target)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DRIVE FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Copter is driving"}

@movement_router.post("/drive_wait", tags=["movement"],
    operation_id="drive_wait",
    summary="Move by relative offset and wait",
    description="Commands the vehicle to move by a relative offset from its current position and blocks until arrival (timeout: 60s). Use for precise relative movements like 'move 10 meters north'. Axes: x=North(+)/South(-), y=East(+)/West(-), z=Down(+)/Up(-), all in meters.")
def drive_wait(pos: Local_pos, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        current_pos = uav.get_ned_position()
        uav.drive_ned(pos.x, pos.y, pos.z, look_at_target=pos.look_at_target)
        target_pos = Local_pos(x=current_pos.x + pos.x, y=current_pos.y + pos.y, z=current_pos.z + pos.z)
        uav.wait_ned_position(target_pos)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DRIVE FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Copter arrived at ({target_pos.x}, {target_pos.y}, {target_pos.z})"}

@movement_router.post("/travel_at_ned", tags=["movement"],
    operation_id="travel_at_ned",
    summary="Set continuous velocity",
    description="Commands the vehicle to travel at a constant velocity in the NED frame. The vehicle will keep moving at this velocity until a new command is issued or 'stop' is called. This is velocity-based, not position-based — there is no arrival. Axes: vx=North(+)/South(-), vy=East(+)/West(-), vz=Down(+)/Up(-), all in m/s. Set look_at_target=true to yaw in the direction of travel.")
def travel_at_ned(vel: Local_velocity, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.travel_at_ned(vel.vx, vel.vy, vel.vz, look_at_target=vel.look_at_target)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TRAVEL FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Travelling at NED velocity ({vel.vx}, {vel.vy}, {vel.vz})"}

@movement_router.get("/stop", tags=["movement"],
    operation_id="stop",
    summary="Stop all movement immediately",
    description="Immediately halts the vehicle at its current position. Cancels any ongoing movement command (go_to, drive, travel_at). The vehicle will hold its current position until a new movement command is issued or 'resume' is called.")
def stop(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.stop()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STOP FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Copter has stopped"}

@movement_router.get("/resume", tags=["movement"],
    operation_id="resume",
    summary="Resume previous movement",
    description="Resumes the last movement command that was interrupted by 'stop'. Only useful after a 'stop' command was issued.")
def resume(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.resume()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RESUME FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Copter has resumed movement"}
