from fastapi import APIRouter, Depends, HTTPException
from uav_api.copter import Copter
from uav_api.router_dependencies import get_copter_instance, get_args
from argparse import Namespace

telemetry_router = APIRouter(
    prefix="/telemetry",
    tags=["telemetry"],
)

@telemetry_router.get("/general", tags=["telemetry"],
    operation_id="get_general_telemetry",
    summary="Get flight overview",
    description="Returns a high-level flight overview: airspeed (m/s), groundspeed (m/s), heading (degrees 0-360), throttle (percentage 0-100), and barometric altitude (meters). Use this for a quick status check of the vehicle's flight state.")
def general_info(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
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
            "alt": info.alt
        }
    }

@telemetry_router.get("/gps", tags=["telemetry"],
    operation_id="get_gps",
    summary="Get fused GPS position",
    description="Returns the vehicle's current position from sensor fusion (GPS + accelerometers + barometer). More accurate than raw GPS. Includes: lat/lon (degrees), altitude (meters ASL), relative altitude (meters above HOME), velocity components vx/vy/vz (m/s), and heading (degrees). Use this as the primary position source for navigation decisions.")
def gps_info(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        info = uav.get_gps_info()
        res_obj = {
            "device": "uav",
            "id": str(args.sysid),
            "result": "Success",
            "info": {
                "position": {
                    "lat": info.lat / 1.0e7, # to degrees
                    "lon": info.lon / 1.0e7, # to degrees
                    "alt": info.alt / 1000, # to meters
                    "relative_alt": info.relative_alt / 1000, # to meters
                },
                "velocity": {
                    "vx": info.vx / 100, # to meters per second
                    "vy": info.vy / 100, # to meters per second
                    "vz": info.vz / 100, # to meters per second
                },
                "heading": info.hdg / 100 # to degrees
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GET_GPS_POSITION FAIL: {e}")
    return res_obj

@telemetry_router.get("/gps_raw", tags=["telemetry"],
    operation_id="get_gps_raw",
    summary="Get raw GPS sensor data",
    description="Returns raw GPS receiver data without sensor fusion. Includes: lat/lon (degrees), altitude (meters), ground speed (m/s), course over ground (degrees), and number of visible satellites. Use 'get_gps' instead for navigation — this is for diagnostics and GPS signal quality assessment.")
def gps_raw(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        info = uav.get_raw_gps()
        res_obj = {
            "device": "uav",
            "id": str(args.sysid),
            "result": "success",
            "info": {
                "position": {
                    "lat": info.lat / 1.0e7, # to degrees
                    "lon": info.lon / 1.0e7, # to degrees
                    "alt": info.alt / 1000, # to meters
                },
                "velocity": {
                    "ground_speed": info.vel / 100, # to meters per second
                    "speed_direction": info.cog / 100 # to degrees
                },
                "satelites": info.satellites_visible
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GET_GPS_RAW FAIL: {e}")
    return res_obj

@telemetry_router.get("/ned", tags=["telemetry"],
    operation_id="get_ned",
    summary="Get local NED position and velocity",
    description="Returns the vehicle's position and velocity in the NED (North-East-Down) local coordinate frame, relative to HOME. Position: x/y/z in meters. Velocity: vx/vy/vz in m/s. Use this when working with go_to_ned, drive, or travel_at_ned commands — the coordinate frame matches.")
def ned_info(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        info = uav.get_ned_info()
        res_obj = {
            "device": "uav",
            "id": str(args.sysid),
            "result": "Success",
            "info": {
            "position": {
                "x": info.x,
                "y": info.y,
                "z": info.z,
            },
            "velocity": {
                "vx": info.vx,
                "vy": info.vy,
                "vz": info.vz
            }
        }
    }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GET_NED_INFO FAIL: {e}")
    return res_obj

@telemetry_router.get("/compass", tags=["telemetry"],
    operation_id="get_compass",
    summary="Get compass calibration status",
    description="Returns compass calibration information: calibration status, whether it was auto-saved, and fitness values (x/y/z). Use for pre-flight diagnostics — poor compass calibration can cause navigation issues.")
def compass_info(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        info = uav.get_compass_info()
        res_obj = {
            "device": "uav",
            "id": str(args.sysid),
            "result": "Success",
            "info": {
                "calibration_status": info.calibration_status,
                "autosaved": bool(info.autosaved),
                "fitness": {
                    "x": info.fitness[0],
                    "y": info.fitness[1],
                    "z": info.fitness[2]
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GET_COMPASS_INFO FAIL: {e}")

    return res_obj

@telemetry_router.get("/sys_status", tags=["telemetry"],
    operation_id="get_sys_status",
    summary="Get raw system status",
    description="Returns the complete raw SYS_STATUS MAVLink message as a dictionary. Contains detailed system health data. For most use cases, prefer the more specific tools: get_battery, get_sensor_status, or get_errors.")
def sys_status(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        status_message = uav.get_raw_status_message()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GET_RAW_SYS_STATUS FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "success", "status": status_message.to_dict()}

@telemetry_router.get("/sensor_status", tags=["telemetry"],
    operation_id="get_sensor_status",
    summary="Get sensor health flags",
    description="Returns parsed sensor health flags from SYS_STATUS. Shows which sensors are present, enabled, and healthy. Use for pre-flight checks or diagnosing sensor failures.")
def sensor_status(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        sensor_status = uav.get_sensor_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GET_SENSOR_STATUS FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "success", "status": sensor_status}

@telemetry_router.get("/battery_info", tags=["telemetry"],
    operation_id="get_battery",
    summary="Get battery status",
    description="Returns battery voltage (mV) and current draw (mA). Monitor this to ensure safe flight duration — land or RTL when battery is low. Critical for autonomous mission planning.")
def battery_info(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        info = uav.get_battery_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GET_BATTERY_INFO FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "success", "info": info}

@telemetry_router.get("/error_info", tags=["telemetry"],
    operation_id="get_errors",
    summary="Get communication and autopilot errors",
    description="Returns error counters for communication (dropped packets, errors) and autopilot subsystems. Non-zero values may indicate connection quality issues. Use for health monitoring during extended operations.")
def error_info(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        info = uav.get_error_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GET_ERROR_INFO FAIL: {e}")
    return {"device": "uav", "id": str(args.sysid), "result": "success", "info": info}

@telemetry_router.get("/home_info", tags=["telemetry"],
    operation_id="get_home",
    summary="Get HOME position",
    description="Returns the HOME position in both GPS (lat/lon/altitude in degrees/meters) and NED (x/y/z in meters) coordinates. HOME is the origin (0,0,0) of the NED frame and the RTL destination. Use this to understand the reference frame for NED-based navigation.")
def home_info(uav: Copter = Depends(get_copter_instance), args: Namespace = Depends(get_args)):
    try:
        info = uav.get_home_position()
        res_obj = {
            "device": "uav",
            "id": str(args.sysid),
            "result": "Success",
            "lat": info["latitude"] / 1.0e7, # to degrees
            "lon": info["longitude"] / 1.0e7, # to degrees
            "altitude": info["altitude"] / 1000, # to meters
            "x": info["x"],
            "y": info["y"],
            "z": info["z"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GET_HOME_INFO FAIL: {e}")
    return res_obj
