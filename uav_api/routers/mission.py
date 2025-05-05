from fastapi import APIRouter, Depends, HTTPException
from copter import Copter
from copter_connection import get_copter_instance

mission_router = APIRouter(
    prefix = "/mission",
    tags = ["mission"],
)

@mission_router.get("/send_sample", tags=["mission"])
def send_sample(uav: Copter = Depends(get_copter_instance)):
    try:
        # Create WayPoint Mission
        uav.init_wp()
        # We get the home position to serve as reference for the mission and as waypoint 0.
        last_home = uav.home_position_as_mav_location()
        # On uav, we need a takeoff ... for takeoff !
        uav.add_wp_takeoff(last_home.lat, last_home.lng, 10)
        uav.add_waypoint(last_home.lat + 0.005, last_home.lng + 0.005, 20)
        uav.add_waypoint(last_home.lat - 0.005, last_home.lng + 0.005, 30)
        uav.add_waypoint(last_home.lat - 0.005, last_home.lng - 0.005, 20)
        uav.add_waypoint(last_home.lat + 0.005, last_home.lng - 0.005, 15)
        # We add a RTL at the end.
        uav.add_wp_rtl()
        # We send everything to the drone
        uav.send_all_waypoints()

    except Exception as e:
        raise HTTPException(status=500, detail=f"SEND_WP FAIL: {e}")
    return {"result": "Sample Mission sent successfully"}
    
@mission_router.get("/mission_start", tags=["mission"])
def mission_start(uav: Copter = Depends(get_copter_instance)):
    try:
        uav.change_mode("AUTO")
        uav.wp_mission_start()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MISSION_START FAIL: {e}")
    return {"result": "Mission started successfully"}

@mission_router.get("/send_spiral", tags=["mission"])
def send_spiral(uav: Copter = Depends(get_copter_instance)):
    try:
        uav.init_wp()
        # We get the home position to serve as reference for the mission and as waypoint 0.
        last_home = uav.home_position_as_mav_location()
        # On uav, we need a takeoff ... for takeoff !
        uav.add_wp_takeoff(last_home.lat, last_home.lng, 10)
        uav.add_waypoint(-15.84034160, -47.92689090, 15.000000)
        uav.add_waypoint(-15.84027450, -47.92749170, 20.000000)
        uav.add_waypoint(-15.83987200, -47.92759900, 25.000000)
        uav.add_waypoint(-15.83977910, -47.92700890, 30.000000)
        uav.add_waypoint(-15.84028680, -47.92690830, 35.000000)
        uav.add_waypoint(-15.84023450, -47.92746620, 40.000000)
        uav.add_waypoint(-15.83990040, -47.92755200, 45.000000)
        uav.add_waypoint(-15.83982170, -47.92705180, 50.000000)
        uav.add_waypoint(-15.84021650, -47.92697400, 55.000000)
        uav.add_waypoint(-15.84016870, -47.92741920, 60.000000)
        uav.add_waypoint(-15.83992880, -47.92749030, 50.000000)
        uav.add_waypoint(-15.83987720, -47.92710010, 40.000000)
        uav.add_waypoint(-15.84014290, -47.92704370, 50.000000)
        uav.add_waypoint(-15.84013260, -47.92738440, 40.000000)
        uav.add_waypoint(-15.83996750, -47.92742330, 30.000000)
        uav.add_waypoint(-15.83993780, -47.92714830, 20.000000)
        uav.add_waypoint(-15.84010040, -47.92711480, 20.000000)
        # We add a RTL at the end.
        uav.add_wp_rtl()
        # We send everything to the drone
        uav.send_all_waypoints()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SPIRAL_SET FAIL: {e}")
    return {"result", "Spiral Mission sent successfully"}




# DEACTIVATED ENDPOINTS
#@mission_router.get("/sample", tags=["mission"])
def sample(uav: Copter = Depends(get_copter_instance)):
    try:
        uav.init_wp()
        # We get the home position to serve as reference for the mission and as waypoint 0.
        last_home = uav.home_position_as_mav_location()
        # On uav, we need a takeoff ... for takeoff !
        uav.add_wp_takeoff(last_home.lat, last_home.lng, 10)
        uav.add_waypoint(last_home.lat + 0.003, last_home.lng + 0.003, 20)
        uav.add_waypoint(last_home.lat - 0.003, last_home.lng + 0.003, 30)
        uav.add_waypoint(last_home.lat - 0.003, last_home.lng - 0.003, 20)
        uav.add_waypoint(last_home.lat + 0.003, last_home.lng - 0.003, 15)
        # We add a RTL at the end.
        uav.add_wp_rtl()
        # We send everything to the drone
        uav.send_all_waypoints()
    
        # Arm vehicle
        uav.change_mode("GUIDED")
        uav.wait_ready_to_arm()
        uav.arm_vehicle()

        if not uav.armed():
            raise HTTPException(status_code=500, detail=f"ERROR ARMING VEHICLE")
        
        # Run Mission Start command
        uav.wp_mission_start()
    except HTTPException as http_e:
        raise http_e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MISSION_FAIL: {e}")
    return {"result": "Showcase begain, enjoy!"}
