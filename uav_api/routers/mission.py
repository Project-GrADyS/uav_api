from pathlib import Path
import shutil
from fastapi import APIRouter, HTTPException, UploadFile, File, HTTPException

mission_router = APIRouter(
    prefix = "/mission",
    tags = ["mission"],
)


# Define and create the upload directory
# .expanduser() handles the "~" symbol correctly
UPLOAD_DIR = Path("~/uav_scripts").expanduser()

@mission_router.post("/upload-script/", tags=["mission"], summary="Uploads a mission script (.py file) to the UAV scripts directory")
async def upload_script(file: UploadFile = File(...)):
    # 1. Validate file extension
    if not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Only .py files are allowed.")

    # 2. Sanitize the filename
    # Path(file.filename).name extracts only the filename, 
    # preventing directory traversal attacks (e.g., ../../etc/passwd)
    safe_filename = Path(file.filename).name
    target_path = UPLOAD_DIR / safe_filename

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
def list_scripts():
    try:
        scripts = [f.name for f in UPLOAD_DIR.glob("*.py") if f.is_file()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not list scripts: {e}")

    return {"scripts": scripts}