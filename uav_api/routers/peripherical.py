import os

from fastapi import APIRouter
from fastapi.responses import FileResponse

peripherical_router = APIRouter(
    prefix = "/peripherical",
    tags = ["peripherical"],
)

@peripherical_router.get("/take_picture", tags=["peripherical"])
def take_picture():
    os.system("fswebcam -r 1280x720 image.jpg")
    if not os.path.exists("image.jpg"):
        return {"error":"Unable to take picture"}, 404
    return FileResponse(
        path="image.jpg",
        media_type="image/jpeg",
        filename="image.jpg"
    )
