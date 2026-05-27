from argparse import Namespace
from fastapi import APIRouter, Depends, HTTPException
from uav_api.vehicles.plane import Plane
from uav_api.routers.router_dependencies import get_plane_instance, get_args

plane_telemetry_router = APIRouter(
    prefix="/telemetry",
    tags=["telemetry"],
)


@plane_telemetry_router.get("/general", tags=["telemetry"], summary="Returns plane general information from VFR_HUD: airspeed, groundspeed, heading, throttle, altitude")
def general_info(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    try:
        info = uav.get_general_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GET_GENERAL_INFO FAIL: {e}")
    return {
        "device": "uav",
        "id": str(args.sysid),
        "result": "Success",
        "info": {
            "airspeed": info.airspeed,
            "groundspeed": info.groundspeed,
            "heading": info.heading,
            "throttle": info.throttle,
            "alt": info.alt,
        },
    }


@plane_telemetry_router.get("/gps", tags=["telemetry"], summary="Returns the plane current GPS information (sensor-fused position from GLOBAL_POSITION_INT)")
def gps_info(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    try:
        info = uav.get_gps_info()
        res_obj = {
            "device": "uav",
            "id": str(args.sysid),
            "result": "Success",
            "info": {
                "position": {
                    "lat": info.lat / 1.0e7,
                    "lon": info.lon / 1.0e7,
                    "alt": info.alt / 1000,
                    "relative_alt": info.relative_alt / 1000,
                },
                "velocity": {
                    "vx": info.vx / 100,
                    "vy": info.vy / 100,
                    "vz": info.vz / 100,
                },
                "heading": info.hdg / 100,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GET_GPS_POSITION FAIL: {e}")
    return res_obj


@plane_telemetry_router.get("/battery_info", tags=["telemetry"], summary="Returns battery information extracted from SYS_STATUS message")
def battery_info(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    try:
        info = uav.get_battery_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GET_BATTERY_INFO FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "success", "info": info}


@plane_telemetry_router.get("/sensor_status", tags=["telemetry"], summary="Returns sensors status extracted from SYS_STATUS message")
def sensor_status(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    try:
        sensors = uav.get_sensor_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GET_SENSOR_STATUS FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "success", "status": sensors}


@plane_telemetry_router.get("/error_info", tags=["telemetry"], summary="Returns error information extracted from SYS_STATUS message")
def error_info(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    try:
        info = uav.get_error_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GET_ERROR_INFO FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "success", "info": info}


@plane_telemetry_router.get("/home_info", tags=["telemetry"], summary="Returns information about HOME position (the (0,0,0) point in static NED frame)")
def home_info(uav: Plane = Depends(get_plane_instance), args: Namespace = Depends(get_args)):
    try:
        info = uav.get_home_position()
        res_obj = {
            "device": "uav",
            "id": str(args.sysid),
            "result": "Success",
            "lat": info["latitude"] / 1.0e7,
            "lon": info["longitude"] / 1.0e7,
            "altitude": info["altitude"] / 1000,
            "x": info["x"],
            "y": info["y"],
            "z": info["z"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GET_HOME_INFO FAIL: {e}")
    return res_obj
