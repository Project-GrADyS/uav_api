import shutil
import time
import subprocess
import os

from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, HTTPException, Depends
from uav_api.routers.router_dependencies import get_args, get_scripts_table
from uav_api.classes.script import Script

copter_mission_router = APIRouter(
    prefix = "/mission",
    tags = ["mission"],
)

@copter_mission_router.post("/upload-script", tags=["mission"], summary="Uploads a mission script (.py file) to the UAV scripts directory")
async def upload_script(file: UploadFile = File(...), args = Depends(get_args)):
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
        await file.close()

    return {"device": "uav", "id": str(args.sysid), "type": 44, "info": f"Mission File '{safe_filename}' saved at {target_path} successfully."}

@copter_mission_router.get("/list-scripts", tags=["mission"], summary="Lists all uploaded mission scripts")
def list_scripts(args = Depends(get_args)):
    try:
        scripts = [f.name for f in (Path(args.scripts_path).expanduser()).glob("*.py") if f.is_file()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not list scripts: {e}")

    return {"device": "uav", "id": str(args.sysid), "type": 42, "scripts": scripts}

@copter_mission_router.post("/execute-script/", tags=["mission"], summary="Executes a specified mission script")
def execute_script(script: Script, args = Depends(get_args), scripts_table = Depends(get_scripts_table)):
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
    command = f"{args.python_path} {script_path} 1> {out_file} 2> {err_file}"
    subprocess.run(["tmux", "new-session", "-d", "-s", session_name, "bash", "-c", command])

    scripts_table[safe_name] = {
        "status": "running",
        "session": session_name,
        "started_at": timestamp,
        "stopped_at": None,
        "out_log": out_file,
        "err_log": err_file,
    }
    print(f"Running: {safe_name}")
    print(f"To view, use: tmux attach -t {session_name}")

    return {
        "device": "uav",
        "id": str(args.sysid),
        "type": 46,
        "script": safe_name,
    }

@copter_mission_router.get("/running-scripts", tags=["mission"], summary="Lists scripts currently running")
def running_scripts(args = Depends(get_args), scripts_table = Depends(get_scripts_table)):
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
    return {"device": "uav", "id": str(args.sysid), "type": 50, "scripts": scripts}

@copter_mission_router.post("/stop-script/", tags=["mission"], summary="Stops a running mission script")
def stop_script(script: Script, args = Depends(get_args), scripts_table = Depends(get_scripts_table)):
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

    return {"device": "uav", "id": str(args.sysid), "type": 52, "script": safe_name, "info": "Stopped"}

@copter_mission_router.delete("/clear-scripts", tags=["mission"], summary="Removes all script files (.py and .sh) from the scripts directory")
def clear_scripts(args = Depends(get_args)):
    scripts_dir = Path(args.scripts_path).expanduser()
    try:
        removed = []
        for f in scripts_dir.iterdir():
            if f.is_file() and f.suffix in (".py", ".sh"):
                f.unlink()
                removed.append(f.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CLEAR SCRIPTS FAIL: {e}")

    return {"device": "uav", "id": str(args.sysid), "type": 48,
            "info": f"Removed {len(removed)} script(s)", "removed": removed}
