import os
import re
import tempfile
import subprocess
from argparse import Namespace

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from uav_api.copter import Copter
from uav_api.classes.peripherical import Servo_output
from uav_api.router_dependencies import get_copter_instance, get_args

peripherical_router = APIRouter(
    prefix="/peripherical",
    tags=["peripherical"],
)

ALLOWED_COMMANDS = {"fswebcam", "rpicam-still", "libcamera-still"}

def _build_cmd(command: str, resolution: str, capture_time: int, focus_distance: float, output_path: str) -> list[str]:
    """Build the capture command list for the given tool."""
    match = re.match(r"^(\d+)x(\d+)$", resolution)
    if not match:
        raise ValueError(f"Invalid resolution format: {resolution}. Expected WIDTHxHEIGHT.")
    w, h = match.group(1), match.group(2)

    if command == "fswebcam":
        cmd = ["fswebcam", "-r", resolution, "--no-banner"]
        if capture_time > 0:
            cmd += ["-D", str(capture_time / 1000)]
        cmd.append(output_path)
    elif command in ("rpicam-still", "libcamera-still"):
        t_ms = str(capture_time) if capture_time > 0 else "1"
        cmd = [command, "--width", w, "--height", h, "--shutter", t_ms, "-o", output_path]
        if focus_distance is not None:
            cmd.append("--autofocus-mode", "manual", "--lens-position",str(1/focus_distance))
    else:
        raise ValueError(f"Unknown command: {command}")
    return cmd


@peripherical_router.get("/take_photo", tags=["peripherical"],
                          summary="Takes a photo using a whitelisted camera CLI tool")
def take_photo(
    command: str = Query(..., description="Camera tool to use. Allowed: fswebcam, rpicam-still, libcamera-still"),
    resolution: str = Query("1280x720", description="Capture resolution (WIDTHxHEIGHT)"),
    capture_time: int = Query(150, ge=0, description="Capture delay / warm-up in milliseconds"),
    focus_distance: int = Query(None, description="If provided, turns off autofocus and uses the parameter valua as the focal distance. (Currently only works with libcamera-still)")
):
    if command not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=400,
            detail=f"Command '{command}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}")

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        cmd = _build_cmd(command, resolution, capture_time, focus_distance, tmp_path)
        result = subprocess.run(cmd, capture_output=True, timeout=30)

        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            detail = result.stderr.decode(errors="replace") if result.stderr else "Command produced no output file"
            raise HTTPException(status_code=500, detail=f"TAKE_PHOTO_FAIL: {detail}")

        return FileResponse(
            path=tmp_path,
            media_type="image/jpeg",
            filename="photo.jpg",
            background=BackgroundTask(os.unlink, tmp_path),
        )
    except subprocess.TimeoutExpired:
        os.unlink(tmp_path)
        raise HTTPException(status_code=504, detail="TAKE_PHOTO_TIMEOUT: Command timed out after 30s")
    except HTTPException:
        raise
    except ValueError as e:
        os.unlink(tmp_path)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=f"TAKE_PHOTO_FAIL: {e}")


@peripherical_router.post("/servo_output", tags=["peripherical"],
                           summary="Sends a PWM signal to a servo motor")
def servo_output(servo: Servo_output,
                 uav: Copter = Depends(get_copter_instance),
                 args: Namespace = Depends(get_args)):
    try:
        uav.set_servo(servo.channel, servo.pwm)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SERVO_OUTPUT FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid),
            "result": f"Servo {servo.channel} set to {servo.pwm} PWM"}
