import shutil
import time
import subprocess
import os

from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, HTTPException, Depends
from uav_api.router_dependencies import get_args
from uav_api.classes.script import Script

mission_router = APIRouter(
    prefix = "/mission",
    tags = ["mission"],
)

@mission_router.post("/upload-script", tags=["mission"], summary="Uploads a mission script (.py file) to the UAV scripts directory")
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

@mission_router.get("/list-scripts", tags=["mission"], summary="Lists all uploaded mission scripts")
def list_scripts(args = Depends(get_args)):
    try:
        scripts = [f.name for f in (Path(args.scripts_path).expanduser()).glob("*.py") if f.is_file()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not list scripts: {e}")

    return {"device": "uav", "id": str(args.sysid), "type": 42, "scripts": scripts}

@mission_router.post("/execute-script/", tags=["mission"], summary="Executes a specified mission script")
def execute_script(script: Script, args = Depends(get_args)):
    # Prevent directory traversal and extract a simple filename
    safe_name = Path(script.script_name).name
    # Ensure .py extension
    if not safe_name.endswith(".py"):
        safe_name = safe_name + ".py"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_base = os.path.splitext(safe_name)[0]  # Removes '.py' extension

    out_file = f"{args.script_logs}/{script_base}_{timestamp}_out.log"
    err_file = f"{args.script_logs}/{script_base}_{timestamp}_err.log"

    script_path = Path(args.scripts_path).expanduser() / safe_name

    # Check existence
    if not script_path.exists() or not script_path.is_file():
        raise HTTPException(status_code=404, detail=f"Script '{safe_name}' not found.")

    session_name = "api-script"
    
    # Check if the tmux session already exists
    # '0' exit code means it exists
    has_session = subprocess.run(["tmux", "has-session", "-t", session_name], 
                                 capture_output=True)

    if has_session.returncode != 0:
        # 1. Create a new detached session
        subprocess.run(["tmux", "new-session", "-d", "-s", session_name])
        print(f"Session '{session_name}' started.")
    else:
        # 2. Session exists: Send Interrupt (Ctrl+C) to stop any running process
        print(f"Session '{session_name}' already exists. Restarting script...")
        subprocess.run(["tmux", "send-keys", "-t", session_name, "C-c", "C-m"])
        time.sleep(0.5) # Give it a moment to stop

    # 3. Prepare the command sequence
    # We chain commands with '&&' to ensure they run in order
    command = f"{args.python_path} {script_path} 1> {out_file} 2> {err_file}"
    
    # 4. Send the command to the session
    subprocess.run(["tmux", "send-keys", "-t", session_name, command, "C-m"])
    
    print(f"Running: {safe_name}")
    print(f"To view, use: tmux attach -t {session_name}")

    # Return process info and log paths (absolute)
    return {
        "device": "uav",
        "id": str(args.sysid),
        "type": 46,
        "script": safe_name,
    }
