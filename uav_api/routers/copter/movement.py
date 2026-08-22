import math

from argparse import Namespace
from fastapi import APIRouter, Depends, HTTPException, Query
from uav_api.vehicles.copter import Copter
from uav_api.routers.dependencies import get_copter_instance, get_args
from uav_api.classes.movement import Body_pos, Gps_pos, Local_pos, Local_velocity
from uav_api.classes.responses import COMMAND_FAILED, UavResponse

router = APIRouter(
    prefix = "/movement",
    tags = ["movement"],
)

def _body_frd_to_ned_target(current, heading_deg: float, front: float, right: float, down: float) -> Local_pos:
    """Rotate a body-FRD offset by the vehicle heading into an absolute NED target.

    ArduPilot resolves a BODY_FRD setpoint against attitude at receipt time, so
    the caller must sample heading *before* sending the setpoint."""
    yaw = math.radians(heading_deg)
    north = front * math.cos(yaw) - right * math.sin(yaw)
    east = front * math.sin(yaw) + right * math.cos(yaw)
    return Local_pos(x=current.x + north, y=current.y + east, z=current.z + down)

@router.post("/go_to_gps/", tags=["movement"], summary="Moves the copter to specified GPS position", response_model=UavResponse, responses=COMMAND_FAILED)
def go_to_gps(pos: Gps_pos, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    """Returns as soon as the setpoint is sent; use /movement/go_to_gps_wait to
    block until arrival. Altitude is meters above HOME. Requires GUIDED mode."""
    try:
        uav.go_to_gps(pos.lat, pos.long, pos.alt, pos.look_at_target)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GO_TO FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Going to coord ({pos.lat}, {pos.long}, {pos.alt})"}

@router.post("/go_to_gps_wait", tags=["movement"], summary="Moves and waits for the copter to get to specified GPS position", response_model=UavResponse, responses=COMMAND_FAILED)
def go_to_gps_wait(pos: Gps_pos, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    """Blocks until the vehicle reaches the target position, or fails with 500
    after a 60 s timeout. Requires GUIDED mode."""
    try:
        uav.go_to_gps(pos.lat, pos.long, pos.alt, pos.look_at_target)
        target_loc = uav.mav_location(pos.lat, pos.long, pos.alt)
        uav.wait_location(target_loc, timeout=60)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GO_TO FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Arrived at coord ({pos.lat}, {pos.long}, {pos.alt})"}

@router.post("/go_to_ned", tags=["movement"], summary="Moves to specified NED position", response_model=UavResponse, responses=COMMAND_FAILED)
def go_to_ned(pos: Local_pos, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    """The target is absolute in the NED frame (origin at HOME); remember z is
    negative above HOME. Returns as soon as the setpoint is sent; use
    /movement/go_to_ned_wait to block until arrival. Requires GUIDED mode."""
    try:
        uav.go_to_ned(pos.x, pos.y, pos.z, look_at_target=pos.look_at_target)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GO_TO FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Going to NED coord ({pos.x}, {pos.y}, {pos.z})"}

@router.post("/go_to_ned_wait", tags=["movement"], summary="Moves and waits for the copter to get to specified NED position", response_model=UavResponse, responses=COMMAND_FAILED)
def go_to_ned_wait(pos: Local_pos, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    """Blocks until the vehicle reaches the absolute NED target. Requires
    GUIDED mode."""
    try:
        uav.go_to_ned(pos.x, pos.y, pos.z, look_at_target=pos.look_at_target)
        uav.wait_ned_position(pos)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GO_TO FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Arrived at NED coord ({pos.x}, {pos.y}, {pos.z})"}

@router.post("/drive", tags=["movement"], summary="Drives copter the specified amount in meters", response_model=UavResponse, responses=COMMAND_FAILED)
def drive(pos: Local_pos, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    """The request body is an offset from the current position along the NED axes (not
    an absolute target). Returns as soon as the setpoint is sent; use
    /movement/drive_wait to block until arrival. Requires GUIDED mode."""
    try:
        uav.drive_ned(pos.x, pos.y, pos.z, look_at_target=pos.look_at_target)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DRIVE FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Copter is driving"}

@router.post("/drive_wait", tags=["movement"], summary="Drives and waits copter the specified amount in meters", response_model=UavResponse, responses=COMMAND_FAILED)
def drive_wait(pos: Local_pos, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    """Offset variant of go_to_ned_wait: blocks until the vehicle has moved by
    the requested NED offset from where it was when the request arrived.
    Requires GUIDED mode."""
    try:
        current_pos = uav.get_ned_position()
        uav.drive_ned(pos.x, pos.y, pos.z, look_at_target=pos.look_at_target)
        target_pos = Local_pos(x=current_pos.x + pos.x, y=current_pos.y + pos.y, z=current_pos.z + pos.z)
        uav.wait_ned_position(target_pos)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DRIVE FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Copter arrived at ({target_pos.x}, {target_pos.y}, {target_pos.z})"}

@router.post("/drive_body", tags=["movement"], summary="Drives copter the specified amount in meters in the body FRD frame (front/right/down)", response_model=UavResponse, responses=COMMAND_FAILED)
def drive_body(pos: Body_pos, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    """The offset is relative to the vehicle's current position and heading:
    the same request moves the vehicle in a different world direction
    depending on where it points. Returns as soon as the setpoint is sent; use
    /movement/drive_body_wait to block until arrival. Requires GUIDED mode."""
    try:
        uav.drive_body_frd(pos.front, pos.right, pos.down, look_at_target=pos.look_at_target)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DRIVE FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "Copter is driving"}

@router.post("/drive_body_wait", tags=["movement"], summary="Drives and waits copter the specified amount in meters in the body FRD frame (front/right/down)", response_model=UavResponse, responses=COMMAND_FAILED)
def drive_body_wait(pos: Body_pos, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    """Blocks until the vehicle has moved by the requested body-frame offset.
    The arrival target is computed from the heading sampled at send time, so a
    vehicle yawing rapidly when the command lands can settle slightly off.
    Requires GUIDED mode."""
    try:
        # Sample position and heading before sending the setpoint: the frame is
        # fixed by the vehicle's attitude at receipt, and with look_at_target
        # the vehicle starts yawing immediately after.
        current_pos = uav.get_ned_position()
        heading = uav.get_general_info().heading
        target_pos = _body_frd_to_ned_target(current_pos, heading, pos.front, pos.right, pos.down)
        uav.drive_body_frd(pos.front, pos.right, pos.down, look_at_target=pos.look_at_target)
        uav.wait_ned_position(target_pos)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DRIVE FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Copter arrived at ({target_pos.x}, {target_pos.y}, {target_pos.z})"}

@router.post("/travel_at_ned", tags=["movement"], summary="Travels at specified NED velocity", response_model=UavResponse, responses=COMMAND_FAILED)
def travel_at_ned(vel: Local_velocity, uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    """The velocity setpoint is sent once; ArduPilot stops the vehicle after
    GUID_TIMEOUT (3s) unless the caller re-sends this request periodically."""
    try:
        uav.travel_at_ned(vel.vx, vel.vy, vel.vz, look_at_target=vel.look_at_target)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TRAVEL FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Travelling at NED velocity ({vel.vx}, {vel.vy}, {vel.vz})"}

@router.get("/set_heading", tags=["movement"], summary="Sets the copter heading to specified angle in degrees", response_model=UavResponse, responses=COMMAND_FAILED)
def set_heading(heading: float = Query(..., ge=0, le=360, description="Absolute target heading in degrees (0 = North); the vehicle turns clockwise."), uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.set_heading(heading)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SET_HEADING FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Heading set to {heading} degrees"}

@router.get("/set_yaw_rate", tags=["movement"], summary="Spins the copter at specified yaw rate in degrees/s", response_model=UavResponse, responses=COMMAND_FAILED)
def set_yaw_rate(yaw_rate: float = Query(..., description="Yaw rate in degrees per second; positive spins clockwise, negative counter-clockwise."), uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        uav.set_yaw_rate(yaw_rate)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SET_YAW_RATE FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": f"Yaw rate set to {yaw_rate} deg/s"}
