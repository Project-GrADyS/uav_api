import shutil
import time

from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, HTTPException, Depends
from uav_api.router_dependencies import get_scripts_path

mission_router = APIRouter(
    prefix = "/mission",
    tags = ["mission"],
)


@mission_router.post("/upload-script/", tags=["mission"], summary="Uploads a mission script (.py file) to the UAV scripts directory")
async def upload_script(file: UploadFile = File(...), scripts_path = Depends(get_scripts_path)):
    # 1. Validate file extension
    if not (file.filename.endswith(".py") or file.filename.endswith(".sh")):
        raise HTTPException(status_code=400, detail="Only .py and .sh files are allowed.")

    # 2. Sanitize the filename
    # Path(file.filename).name extracts only the filename, 
    # preventing directory traversal attacks (e.g., ../../etc/passwd)
    safe_filename = Path(file.filename).name
    target_path = scripts_path / safe_filename

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

    return {"info": f"Mission File '{safe_filename}' saved at {target_path} successfully."}

@mission_router.get("/list-scripts/", tags=["mission"], summary="Lists all uploaded mission scripts")
def list_scripts(scripts_path = Depends(get_scripts_path)):
    try:
        scripts = [f.name for f in scripts_path.glob("*.py") if f.is_file()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not list scripts: {e}")

    return {"scripts": scripts}

@mission_router.get("/execute-script/{script_name}", tags=["mission"], summary="Executes a specified mission script")
def execute_script(script_name: str, scripts_path = Depends(get_scripts_path)):
    # Prevent directory traversal and extract a simple filename
    safe_name = Path(script_name).name

    # Ensure .py extension
    if not safe_name.endswith(".py"):
        safe_name = safe_name + ".py"

    script_path = scripts_path / safe_name

    # Check existence
    if not script_path.exists() or not script_path.is_file():
        raise HTTPException(status_code=404, detail=f"Script '{safe_name}' not found.")

    # Start the script in background, redirect stdout/stderr to log files
    import subprocess
    import sys

    LOG_DIR = Path("~/uav_api_logs/script_logs").expanduser()
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not create log directory: {e}")

    ts = int(time.time())
    stdout_log = LOG_DIR / f"{safe_name}.{ts}.out.log"
    stderr_log = LOG_DIR / f"{safe_name}.{ts}.err.log"

    try:
        out_f = stdout_log.open("w")
        err_f = stderr_log.open("w")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not open log files: {e}")

    try:
        # start_new_session detaches the child from the parent terminal on Unix
        proc = subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=str(scripts_path),
            stdout=out_f,
            stderr=err_f,
            start_new_session=True,
        )
    except Exception as e:
        out_f.close()
        err_f.close()
        raise HTTPException(status_code=500, detail=f"Failed to start script: {e}")

    # Return process info and log paths (absolute)
    return {
        "script": safe_name,
        "pid": proc.pid,
    }
