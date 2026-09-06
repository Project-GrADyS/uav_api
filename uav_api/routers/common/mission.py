import logging
import shlex
import shutil
import time
import subprocess
import os

from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from uav_api.routers.dependencies import get_args, get_scripts_table
from uav_api.classes.script import Script
from uav_api.classes.responses import (
    error_responses,
    ClearScriptsResponse,
    ExecuteScriptResponse,
    ListScriptsResponse,
    RunningScriptsResponse,
    ScriptLogResponse,
    StopScriptResponse,
    UploadScriptResponse,
)

router = APIRouter(
    prefix = "/mission",
    tags = ["mission"],
)

@router.post("/upload-script", tags=["mission"], summary="Uploads a mission script (.py file) to the UAV scripts directory", response_model=UploadScriptResponse, responses=error_responses({400: "The uploaded file is not a .py or .sh file.", 500: "The file could not be saved to the scripts directory."}))
def upload_script(file: UploadFile = File(..., description="Script file to upload. Only .py and .sh files are accepted; any directory components in the filename are stripped."), args = Depends(get_args)):
    """Saves the file into the scripts directory (--scripts_path,
    default <root_dir>/scripts), overwriting any existing file with the same
    name. Run it afterwards with /mission/execute-script/."""
    # 1. Validate file extension
    if not (file.filename.endswith(".py") or file.filename.endswith(".sh")):
        raise HTTPException(status_code=400, detail="Only .py and .sh files are allowed.")

    # 2. Sanitize the filename
    # Path(file.filename).name extracts only the filename, 
    # preventing directory traversal attacks (e.g., ../../etc/passwd)
    safe_filename = Path(file.filename).name
    target_path = Path(args.scripts_path).expanduser() / safe_filename

    try:
        # 3. Save the file
        with target_path.open("wb") as buffer:
            # shutil.copyfileobj is efficient for small to medium files
            shutil.copyfileobj(file.file, buffer)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")
    finally:
        # Always close the SpooledTemporaryFile
        file.file.close()

    return {"device": "uav", "id": str(args.sysid), "result": "success", "type": 44, "info": f"Mission File '{safe_filename}' saved at {target_path} successfully."}

@router.get("/list-scripts", tags=["mission"], summary="Lists all uploaded mission scripts", response_model=ListScriptsResponse, responses=error_responses({500: "The scripts directory could not be read."}))
def list_scripts(args = Depends(get_args)):
    """Lists the .py files in the scripts directory (uploaded .sh files are
    not included)."""
    try:
        scripts = [f.name for f in (Path(args.scripts_path).expanduser()).glob("*.py") if f.is_file()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not list scripts: {e}")

    return {"device": "uav", "id": str(args.sysid), "result": "success", "type": 42, "scripts": scripts}

@router.post("/execute-script/", tags=["mission"], summary="Executes a specified mission script", response_model=ExecuteScriptResponse, responses=error_responses({400: "The script is already running.", 404: "The script was not found in the scripts directory.", 500: "tmux failed to start the session.", 503: "tmux is not installed on the vehicle."}))
def execute_script(script: Script, args = Depends(get_args), scripts_table = Depends(get_scripts_table)):
    """Starts the script in a detached tmux session using the interpreter from
    --python_path. Returns immediately; poll /mission/running-scripts for
    status. stdout/stderr are captured to timestamped files under
    --script_logs (paths reported by /mission/running-scripts)."""
    # Prevent directory traversal and extract a simple filename
    safe_name = Path(script.script_name).name
    # Ensure .py extension
    if not safe_name.endswith(".py"):
        safe_name = safe_name + ".py"

    if safe_name in scripts_table and scripts_table[safe_name].get("status") == "running":
        raise HTTPException(status_code=400, detail=f"Script '{safe_name}' is already running.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_base = os.path.splitext(safe_name)[0]  # Removes '.py' extension

    out_file = f"{args.script_logs}/{script_base}_{timestamp}_out.log"
    err_file = f"{args.script_logs}/{script_base}_{timestamp}_err.log"

    script_path = Path(args.scripts_path).expanduser() / safe_name

    # Check existence
    if not script_path.exists() or not script_path.is_file():
        raise HTTPException(status_code=404, detail=f"Script '{safe_name}' not found.")

    session_name = f"UAV_API_{args.sysid}-{safe_name.replace('.', '_')}-{timestamp}"
    # tmux owns the command lifecycle: when the python process exits, the
    # session auto-terminates, which is what scripts_watcher_loop polls for.
    command = (
        f"{shlex.quote(str(args.python_path))} {shlex.quote(str(script_path))} "
        f"1> {shlex.quote(out_file)} 2> {shlex.quote(err_file)}"
    )
    try:
        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, "bash", "-c", command],
            capture_output=True,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="EXECUTE SCRIPT FAIL: tmux is not installed")
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip() if result.stderr else ""
        raise HTTPException(
            status_code=500,
            detail=f"EXECUTE SCRIPT FAIL: tmux exited with code {result.returncode}: {stderr}",
        )

    scripts_table[safe_name] = {
        "status": "running",
        "session": session_name,
        "started_at": timestamp,
        "stopped_at": None,
        "out_log": out_file,
        "err_log": err_file,
    }

    logger = logging.getLogger("SCRIPT")

    logger.info(f"Running: {safe_name}")
    logger.info(f"To view, use: tmux attach -t {session_name}")

    return {
        "device": "uav",
        "id": str(args.sysid),
        "result": "success",
        "type": 46,
        "script": safe_name,
    }

@router.get("/running-scripts", tags=["mission"], summary="Lists scripts currently running", response_model=RunningScriptsResponse)
def running_scripts(args = Depends(get_args), scripts_table = Depends(get_scripts_table)):
    """Each entry carries the tmux session name and the stdout/stderr log
    paths on the vehicle."""
    scripts = [
        {
            "script": name,
            "session": info["session"],
            "started_at": info["started_at"],
            "out_log": info["out_log"],
            "err_log": info["err_log"],
        }
        for name, info in scripts_table.items()
        if info.get("status") == "running"
    ]
    return {"device": "uav", "id": str(args.sysid), "result": "success", "type": 50, "scripts": scripts}

@router.post("/stop-script/", tags=["mission"], summary="Stops a running mission script", response_model=StopScriptResponse, responses=error_responses({400: "The script is not running.", 404: "The script was never executed (not in the scripts table)."}))
def stop_script(script: Script, args = Depends(get_args), scripts_table = Depends(get_scripts_table)):
    """Sends SIGINT first so the script's cleanup handlers can run (e.g. land
    the drone), waits one second, then kills the tmux session."""
    safe_name = Path(script.script_name).name
    if not safe_name.endswith(".py"):
        safe_name = safe_name + ".py"

    info = scripts_table.get(safe_name)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Script '{safe_name}' not found in scripts table.")
    if info.get("status") != "running":
        raise HTTPException(status_code=400, detail=f"Script '{safe_name}' is not running.")

    session_name = info["session"]
    # Graceful: SIGINT lets the script's finally/atexit handlers run (e.g. land the drone).
    subprocess.run(["tmux", "send-keys", "-t", session_name, "C-c", "C-m"])
    time.sleep(1.0)
    subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)

    info["status"] = "stopped"
    info["stopped_at"] = datetime.now().strftime("%Y%m%d_%H%M%S")

    return {"device": "uav", "id": str(args.sysid), "result": "success", "type": 52, "script": safe_name, "info": "Stopped"}

@router.get("/script-log", tags=["mission"], summary="Reads the tail of a mission script's stdout or stderr log", response_model=ScriptLogResponse, responses=error_responses({404: "The script was never executed, or its log file is missing.", 500: "The log file could not be read."}))
def script_log(
    script_name: str = Query(description="Script filename. Directory components are stripped and '.py' is appended when missing, matching the other /mission endpoints."),
    stream: Literal["out", "err"] = Query("out", description="Which stream to read: 'out' for stdout, 'err' for stderr."),
    tail: int = Query(200, ge=1, le=1000, description="Number of trailing lines to return."),
    args = Depends(get_args),
    scripts_table = Depends(get_scripts_table),
):
    """Reads the log file recorded for the script by /mission/execute-script/.
    Stopped scripts stay in the scripts table for the lifetime of the API
    process, so their logs remain readable after the flight."""
    safe_name = Path(script_name).name
    if not safe_name.endswith(".py"):
        safe_name = safe_name + ".py"

    info = scripts_table.get(safe_name)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Script '{safe_name}' not found in scripts table.")

    log_path = Path(info["out_log"] if stream == "out" else info["err_log"]).expanduser()
    if not log_path.is_file():
        raise HTTPException(status_code=404, detail=f"Log file for '{safe_name}' ({stream}) not found at {log_path}.")

    try:
        # Scripts are read while running, so decoding errors are expected on a
        # partially-written final line; replace rather than fail the request.
        with log_path.open("r", errors="replace") as f:
            lines = deque(f, maxlen=tail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SCRIPT LOG FAIL: {e}")

    return {
        "device": "uav",
        "id": str(args.sysid),
        "result": "success",
        "script": safe_name,
        "stream": stream,
        "lines": [line.rstrip("\n") for line in lines],
    }

@router.delete("/clear-scripts", tags=["mission"], summary="Removes all script files (.py and .sh) from the scripts directory", response_model=ClearScriptsResponse, responses=error_responses({500: "A script file could not be removed."}))
def clear_scripts(args = Depends(get_args)):
    """Deletes the files only; running tmux sessions are not touched."""
    scripts_dir = Path(args.scripts_path).expanduser()
    try:
        removed = []
        for f in scripts_dir.iterdir():
            if f.is_file() and f.suffix in (".py", ".sh"):
                f.unlink()
                removed.append(f.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CLEAR SCRIPTS FAIL: {e}")

    return {"device": "uav", "id": str(args.sysid), "result": "success", "type": 48,
            "info": f"Removed {len(removed)} script(s)", "removed": removed}
