# Uav_api
This is the repository for Uav_api, an API for UAV autonomous flights. The Uav_api enables UAV movement, telemetry and basic command execution such as RTL and TAKEOFF through HTTP requests, facilitating remote controlled flights, both programmatically and manually. In addition to that, Uav_api supports protocol execution for autonomous flights, oferring the same interface as gradysim-nextgen simulator. At last but not least, Uav_api can be used for simulations based on Ardupilot's SITL.

# Installation
## Prerequisites
Python 3.10 is required
If simulated flights are intended, installing Ardupilot's codebase is necessary. To do that follow the instructions at https://ardupilot.org/dev/docs/where-to-get-the-code.html (Don't forget to build the environment after cloning). In addition to that, following the steps for running the SITL is also required, which are stated at https://ardupilot.org/dev/docs/SITL-setup-landingpage.html

## Installing with pip (recommended)
To install uav-api python package run the following command:

  `pip install uav-api`

This will install the package in your current environment.
After the installation is over, restart you terminal instance and you are ready to go!

## Using git repository
It is also possible to install a local development version of uav_api where you can make changes.
Start by cloning the repository

  `git clone https://github.com/Project-GrADyS/uav_api`

Then, inside of the cloned repository, run the command:

  `pip install -e .`

Now close and re-open your terminal instance and you are ready to go!

# Executing the api in a real drone
## Starting Uav_api
To start the server, run the following command:

  `uav-api --port [port for API] --uav_connection [ardupilot_connection] --connection_type [udpin or updout] --sysid [sysid for ardupilot]`

Alternatively, you can use a configuration file in the following .ini format.
```
[api]
port = 8000
uav_connection = 127.0.0.1:17171
connection_type = udpin
sysid = 1
```
And run the command:

  `uav-api --config /path_to_config`

To see more arguments options and to get better insight on the arguments for `uav-api` run the command bellow:

  `uav-api --help`

And that's it! You can start sending HTTP requests to Uav_api

# Executing a Simulated flight
Executing a simulated flight with UAV API is almost exactly the same as in a real drone, the only difference is that simulated flights take a few more arguments.
## Starting Uav_api and SITL at the same time
To instantiate the API and Ardupilot's SITL, run the following command:

  `uav-api --simulated true --ardupilot_path [path to ardupilot repository] --speedup [speedup factor for SITL] --gs_connection [ip:port telemetry routing for groundstation softwares] --port [port for API] --uav_connection [ardupilot_connection] --connection_type [udpin or updout] --sysid [sysid for ardupilot]`

This command initiates both the SITL, and the Uav_api API. The connection addres of the SITL instance is the one set in `uav_connection` argument and the speedup factor of the simulation is set to the value of the `speedup` argument.

It is also possible to start simulated flights through configuration files.

```
[api]
port=8000
uav_connection=127.0.0.1:17171
connection_type=udpin
sysid=1

[simulated]
ardupilot_path=~/ardupilot
gs_connection=[172.26.176.1:15630]
speedup=1
```

With the command:

`uav-api --config /path_to_config`

# Testing and feedback
## Testing API initialization
To verify the initialization of the API go to the endpoint `localhost:[your_port]/docs`.
<img src="https://github.com/user-attachments/assets/6ef0d0b1-4dd7-4049-b16e-f3b509ab1b94" />

Once inside the web page, scroll to telemetry router and execute the `telemetry/general` endpoint.
![image](https://github.com/user-attachments/assets/4d1922a7-91c3-4873-81cc-5db9961a2e18)

If everything is fine, the answer should look like this.
![image](https://github.com/user-attachments/assets/47e7c802-6411-4864-9f1c-280327c4303c)

## Visual feedback with Mission Planner
To get visual feedback of drone position and telemetry use Mission Planner, or any other ground station software of your preference, and connect to UDP port specified in `gs_connection` parameter.

![image](https://github.com/user-attachments/assets/b7928581-89c6-46c0-9f02-3bd8edd30570)

# Flying through scripts
One of the perks of using UAV API is being aple to quickly write scripts that control drone movement. Here are some examples
## Running examples
To run the following examples run the following command inside of the `flight_examples` directory:

  `uav-api --config ./uav_1.ini`

Note that this configuration file contains default values for parameters, change the values such that it matches your envinronment. You can also use your own configuration file or start the api through arguments.

Once the api is up and running, run one of the examples bellow in a new terminal instance.

## Simple Takeoff and Landing
This file is located at `uav_api/flight_examples/takeoff_land.py`
```python
import requests
base_url = "http://localhost:8000"

# Arming vehicle
arm_result = requests.get(f"{base_url}/command/arm")
if arm_result.status_code != 200:
    print(f"Arm command fail. status_code={arm_result.status_code}")
    exit()
print("Vehicle armed.")

# Taking off
params = {"alt": 30}
takeoff_result = requests.get(f"{base_url}/command/takeoff", params=params)
if takeoff_result.status_code != 200:
    print(f"Take off command fail. status_code={takeoff_result.status_code}")
    exit()
print("Vehicle took off")

# Landing...
land_result = requests.get(f"{base_url}/command/land")
if land_result.status_code != 200:
    print(f"Land command fail. status_code={land_result.status_code}")
    exit()
print("Vehicle landed.")
```

## NED Square
In this example the uav will move following a square with 100 meters side. This file is located at `flight_examples/ned_square`.
```python
import requests
base_url = "http://localhost:8000"

# Arming vehicle
arm_result = requests.get(f"{base_url}/command/arm")
if arm_result.status_code != 200:
    print(f"Arm command fail. status_code={arm_result.status_code}")
    exit()
print("Vehicle armed.")

# Taking off
params = {"alt": 30}
takeoff_result = requests.get(f"{base_url}/command/takeoff", params=params)
if takeoff_result.status_code != 200:
    print(f"Take off command fail. status_code={takeoff_result.status_code}")
    exit()
print("Vehicle took off")

square_points = [
    (100, 100, -50),
    (100, -100, -50),
    (-100, -100, -50),
    (-100, 100, -50)
]

# Moving
for point in square_points:
    point_data = {
        "x": point[0],
        "y": point[1],
        "z": point[2]
    }
    point_result = requests.post(f"{base_url}/movement/go_to_ned_wait", json=point_data)
    if point_result.status_code != 200:
        print(f"Go_to_ned_wait command fail. status_code={point_result.status_code} point={point}")
        exit()
    print(f"Vehicle at ({point[0]}, {point[1]}, {point[2]})")

# Returning to launch
rtl_result = requests.get(f"{base_url}/command/rtl")
if rtl_result.status_code != 200:
    print(f"RTL command fail. status_code={rtl_result.status_code}")
    exit()
print("Vehicle landed at launch.")
```

## NED Square (Polling)
This example does the same thing as the last one but this time instead of using the `go_to_ned_wait` endpoint we will take a polling aproach using `go_to_ned`. While more verbose, this way of verifying position allows your program to do other things while the uav has not arrived to the specified location. This file is located at `flight_examples/ned_square_polling.py`.
```python
import requests
import time
import math

base_url = "http://localhost:8000"

def euclidean_distance(point1, point2):
    return math.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2 + (point1[2] - point2[2])**2)

def wait_for_point(point, max_error, timeout):
    start = time.time()
    while time.time() < start + timeout:
        ned_result = requests.get(f"{base_url}/telemetry/ned")
        if ned_result.status_code != 200:
            print(f"Ned telemetry fail. status_code={ned_result.status_code}")
            exit()
        ned_pos = ned_result.json()["info"]["position"]
        print(ned_pos)
        ned_point = (ned_pos["x"], ned_pos["y"], ned_pos["z"])
        distance = euclidean_distance(point, ned_point)
        if distance < max_error:
            return True
    return False


# Arming vehicle
arm_result = requests.get(f"{base_url}/command/arm")
if arm_result.status_code != 200:
    print(f"Arm command fail. status_code={arm_result.status_code}")
    exit()
print("Vehicle armed.")

# Taking off
params = {"alt": 30}
takeoff_result = requests.get(f"{base_url}/command/takeoff", params=params)
if takeoff_result.status_code != 200:
    print(f"Take off command fail. status_code={takeoff_result.status_code}")
    exit()
print("Vehicle took off")

square_points = [
    (100, 100, -50),
    (100, -100, -50),
    (-100, -100, -50),
    (-100, 100, -50)
]

# Moving
for point in square_points:
    point_data = {
        "x": point[0],
        "y": point[1],
        "z": point[2]
    }
    point_result = requests.post(f"{base_url}/movement/go_to_ned", json=point_data)
    if point_result.status_code != 200:
        print(f"Go_to_ned command fail. status_code={point_result.status_code} point={point}")
        exit()

    arrived = wait_for_point(point, max_error=3, timeout=60)
    if not arrived:
        print(f"Error while going to point {point}")
        exit()
    print(f"Vehicle at ({point[0]}, {point[1]}, {point[2]})")

# Returning to launch
rtl_result = requests.get(f"{base_url}/command/rtl")
if rtl_result.status_code != 200:
    print(f"RTL command fail. status_code={rtl_result.status_code}")
    exit()
print("Vehicle landed at launch.")
```

## Follower
In this example one UAV will perform a square flight (shown previously) while another UAV follows it by consuming the leader API.
To run this example start 2 different uav-api process with different ports and sysid. Now start the square script using the first UAV port number, then start the follower script (located at `flight_examples/follower.py`) with the port number of the second UAV.
```python
import requests
from time import sleep, time

base_url = "http://localhost:8001"
leader_url = "http://localhost:8000"
# Arming vehicle
arm_result = requests.get(f"{base_url}/command/arm")
if arm_result.status_code != 200:
    print(f"Arm command fail. status_code={arm_result.status_code}")
    exit()
print("Vehicle armed.")

# Taking off
params = {"alt": 20}
takeoff_result = requests.get(f"{base_url}/command/takeoff", params=params)
if takeoff_result.status_code != 200:
    print(f"Take off command fail. status_code={takeoff_result.status_code}")
    exit()
print("Vehicle took off")

# Follow leader for 30 seconds
start_time = time()
current_time = time()
while (current_time - start_time) <= 30:
    leader_telemetry_result = requests.get(f"{leader_url}/telemetry/ned")
    if leader_telemetry_result.status_code != 200:
        print(f"Leader telemetry fail. status_code={leader_telemetry_result.status_code}")
        exit()
    leader_pos = leader_telemetry_result.json()["info"]["position"]

    print("Got leader telemetry.")

    movement_data = {
        "x": leader_pos["x"] + 5,
        "y": leader_pos["y"] + 5,
        "z": -20
    }
    movement_result = requests.post(f"{base_url}/movement/go_to_ned", json=movement_data)
    if movement_result.status_code != 200:
        print(f"Follower go to ({movement_data['x']}, {movement_data['y']}, {movement_data['z']}) failed. status_code={movement_result.status_code}")
        exit()
    
    print(f"Follower going to ({movement_data['x']}, {movement_data['y']}, {movement_data['z']}).")

    sleep(2)
    current_time = time()

# Return to launch
print("Returning to launch...")
rtl_result = requests.get(f"{base_url}/command/rtl")
if rtl_result.status_code != 200:
    print(f"RTL command fail. status_code={rtl_result.status_code}")
    exit()

print("Landed at launch")
```

## Make polygon with Go To

This example raises the drone to a height defined by the user and then, using the endpoint `go_to_ned_wait`, takes the drone to the vertices of regular polygons also to be defined by the user. These polygons have their center located at the point where the drone was raised and are always made vertically. Whenever a polygon is finished, the drone returns to the center before starting the next one.
The algorithm that maps the polygon points is found in the `make_polygon_points` function and works by inscribing a polygon with `s` vertices inside a circle of radius `r` and the NED coordinates of the center defined as `offset`. Since the polygon is inscribed, we know that its vertices are located on the perimeter of the circle, and since we also know that the polygon is regular, the vertices are equidistant, so we can find the angular distance of each vertex from $\frac{2\pi}{n}$. Now, numbering each vertex `v` from $v_{0}=0$ to $v_{n}=s-1$, we can find the angle of each one using the function:  

$$\theta_{i}=v_{i}\frac{2\pi}{n}$$

Finally, knowing the angle of the vertices, the coordinates of the center, and knowing that the polygon must be drawn vertically, we can define the NED coordinates of the vertices as:  

$$x_{i}=\sin(v_{i}\frac{2\pi}{n})+x_{offset}$$
$$y_{i}=y_{offset}$$
$$z_{i}=-\cos(v_{i}\frac{2\pi}{n})+z_{offset}$$

To use the example, the user must define the desired polygons using the `--sides` parameter, inserting the number of vertices of the polygons, the radius of the circle in meters using the `--radius` parameter, and the height at which the center of the polygon should be in meters using the `--height` parameter. So, for example, if the user wants to create a triangle, a square, and a pentagon, inserted in a circle with a radius of 3 meters and a center 4 meters from the ground, the command should be:  

`python go_to_polygon.py --sides 3 4 5 --radius 3 --height 4`  
  
This file is located at `flight_examples/polygon/go_to_polygon.py`.

```python
import requests
import math
from time import sleep
import argparse
base_url = "http://localhost:8000"

SLEEP_TIME = 5

def make_polygon_points(r, s, offset):
    points = []
    for v in range(s):
        point = {
            "x": r*math.sin(v*2*math.pi/s) + offset["x"],
            "y": offset["y"],
            "z": -(r*math.cos(v*2*math.pi/s)) + offset["z"]
        }
        print(f"polygon point {v}: {point}")
        points.append(point)
    return(points)

# Get the user's arguments
parser = argparse.ArgumentParser()
parser.add_argument('--sides', type=int, nargs='+', required=True)
parser.add_argument('--radius', type=int, required=True)
parser.add_argument('--height', type=int, required=True)
args = parser.parse_args()

# Ensures that the user defines a valid regular polygon
if 1 in args.sides or 2 in args.sides:
    print(f"Error: Polygon must have more than two sides!")
    exit()

# Failsafe: Ensure that the radius is smaller than the height of the perimeter's center
if args.radius >= args.height:
    print(f"Error: height vale must be higher then the radius value!")
    exit()

# Arming vehicle
arm_result = requests.get(f"{base_url}/command/arm")
if arm_result.status_code != 200:
    print(f"Arm command fail. status_code={arm_result.status_code}")
    exit()
print("Vehicle armed.")

# Get the NED coordinates, from telemetry, of the initial position with the vehicle still on the ground
initial_result = requests.get(f"{base_url}/telemetry/ned")
if initial_result.status_code != 200:
    print(f"Ned telemetry fail. status_code={initial_result.status_code}")
    exit()
initial_pos = initial_result.json()["info"]["position"]
print(f"Initial point: {initial_pos}")

# Taking off
params = {"alt": args.height}
takeoff_result = requests.get(f"{base_url}/command/takeoff", params=params)
if takeoff_result.status_code != 200:
    print(f"Take off command fail. status_code={takeoff_result.status_code}")
    exit()
print("Vehicle took off")

#sleep ensures the vehicle has time to reach its desired position
sleep(SLEEP_TIME)

# Get the NED coordinates, from telemetry, of the center of the polygons
center_result = requests.get(f"{base_url}/telemetry/ned")
if center_result.status_code != 200:
    print(f"Ned telemetry fail. status_code={center_result.status_code}")
    exit()
center_pos = center_result.json()["info"]["position"]
print(f"center point: {center_pos}")

# Failsafe: Ensures the drone has reached the desired altitude, including a margin of error, if not it will land
if abs(center_pos["z"]-initial_pos["z"]) >= args.height+2 or abs(center_pos["z"]-initial_pos["z"]) <= args.height-2:
        print(f"Error: Vehicle did not reach the desired height.")
        land_result = requests.get(f"{base_url}/command/land")
        if land_result.status_code != 200:
            print(f"Land command fail. status_code={land_result.status_code}")
            exit()
        print("Vehicle landed.")
        exit()

polygon_list = args.sides
for s in polygon_list:
    print(f"\n ---polygon {s}---------------------------------- \n")

    # For each polygon gets the NED coordinates of the vertices
    polygon_points = make_polygon_points(args.radius, s, center_pos)
        
    for point in polygon_points:
        # For each vertex moves the vehicle to its coordinate using go_to_ned_wait
        point_result = requests.post(f"{base_url}/movement/go_to_ned_wait", json=point)
        if point_result.status_code != 200:
            print(f"Go_to_ned_wait command fail. status_code={point_result.status_code} point={point}")
            exit()
        print(f"\nGo to point: {point})")

        #sleep ensures the vehicle has time to reach its desired position
        sleep(SLEEP_TIME)

        # Get the NED coordinates, from telemetry, of the vertex for better user visualization and debugging
        tele_ned_result = requests.get(f"{base_url}/telemetry/ned")
        if tele_ned_result.status_code != 200:
            print(f"Ned telemetry fail. status_code={tele_ned_result.status_code}")
            exit()
        tele_ned_pos = tele_ned_result.json()["info"]["position"]
        print(f"Vehicle at {tele_ned_pos})")

    # After completing the polygon, return the vehicle to the center using go_to_ned_wait
    point_result = requests.post(f"{base_url}/movement/go_to_ned_wait", json=center_pos)
    if point_result.status_code != 200:
        print(f"Go_to_ned_wait command fail. status_code={point_result.status_code} point={center_pos}")
        exit()
    print(f"\nVehicle going back to the center")

    #sleep ensures the vehicle has time to reach its desired position
    sleep(SLEEP_TIME)
    
    print(f"Vehicle at the center")

# Landing
land_result = requests.get(f"{base_url}/command/land")
if land_result.status_code != 200:
    print(f"Land command fail. status_code={land_result.status_code}")
    exit()
print("\nVehicle landed.")

```

## Make polygon with Drive

This example works the same way as the last one with one change, now we will use the `drive_wait` endpoint to take the drone to the vertices of the polygons. For this, the `make_polygon_points` function is replaced by the `make_polygon_trajectory` function. This new function also works by inscribing a polygon of `n` vertices inside a circle of radius `r`, but we don't need the NED coordinates of the circle's center. The same definition for the vertex angles will also be used: $\theta_{i}=v_{i}\frac{2\pi}{n}$.  
Instead of defining the coordinates of the vertices, we will define vectors, still in NED, that take the drone to the vertices. For the first step, the drone must be taken from the center of the polygon to the first vertex, knowing that $v_{0}=0$, the vector must be:

$$x_{0}=\sin(v_{0}\frac{2\pi}{n})=0$$
$$y_{0}=0$$
$$z_{0}=-\cos(v_{0}\frac{2\pi}{n})=-1$$

For the following steps, since the drone is no longer at the center of the polygon, the vector that takes the drone from the center to the desired position must be subtracted by the vector that takes the drone from the center to its current position. This way, the trajectory vector of next points is obtained as follows:

$$x_{i}=\sin(v_{i}\frac{2\pi}{n}) - \sin(v_{i-1}\frac{2\pi}{n})$$
$$y_{i}=0$$
$$z_{i}=-(\cos(v_{i}\frac{2\pi}{n}) - \cos(v_{i-1}\frac{2\pi}{n}))$$

To use this example, the user must define the same parameters `--sides`, `--radius`, and `--height` as demonstrated in the previous example. This file is located at `flight_examples/polygon/drive_polygon.py`.

```python
import requests
import math
from time import sleep
import argparse
base_url = "http://localhost:8000"

SLEEP_TIME = 5

def make_polygon_trajectory(r, l):
    vectors = []
    for n in range(l):
        if n == 0:
            vector = {
                "x": 0,
                "y": 0,
                "z": -1
            }
        else:
            vector = {
                "x": round(r*math.sin(n*2*math.pi/l) - r*math.sin((n-1)*2*math.pi/l)),
                "y": 0,
                "z": -(round(r*math.cos(n*2*math.pi/l) - r*math.cos((n-1)*2*math.pi/l)))
            }
        print(f"polygon vector {n}: {vector}")
        vectors.append(vector)

    return(vectors)

# Get the user's arguments
parser = argparse.ArgumentParser()
parser.add_argument('--sides', type=int, nargs='+', required=True)
parser.add_argument('--radius', type=int, required=True)
parser.add_argument('--height', type=int, required=True)
args = parser.parse_args()

# Ensures that the user defines a valid regular polygon
if 1 in args.sides or 2 in args.sides:
    print(f"Error: Polygon must have more than two sides!")
    exit()

# Failsafe: Ensure that the radius is smaller than the height of the perimeter's center
if args.radius >= args.height:
    print(f"Error: height vale must be higher then the radius value!")
    exit()

# Arming vehicle
arm_result = requests.get(f"{base_url}/command/arm")
if arm_result.status_code != 200:
    print(f"Arm command fail. status_code={arm_result.status_code}")
    exit()
print("Vehicle armed.")

# Get the NED coordinates, from telemetry, of the initial position with the vehicle still on the ground
initial_result = requests.get(f"{base_url}/telemetry/ned")
if initial_result.status_code != 200:
    print(f"Ned telemetry fail. status_code={initial_result.status_code}")
    exit()
initial_pos = initial_result.json()["info"]["position"]
print(f"Initial point: {initial_pos}")

# Taking off
params = {"alt": args.height}
takeoff_result = requests.get(f"{base_url}/command/takeoff", params=params)
if takeoff_result.status_code != 200:
    print(f"Take off command fail. status_code={takeoff_result.status_code}")
    exit()
print("Vehicle took off")

#sleep ensures the vehicle has time to reach its desired position
sleep(SLEEP_TIME)

# Get the NED coordinates, from telemetry, of the center of the polygons
center_result = requests.get(f"{base_url}/telemetry/ned")
if center_result.status_code != 200:
    print(f"Ned telemetry fail. status_code={center_result.status_code}")
    exit()
center_pos = center_result.json()["info"]["position"]
print(f"center point: {center_pos}")

# Failsafe: Ensures the drone has reached the desired altitude, including a margin of error, if not it will land
if abs(center_pos["z"]-initial_pos["z"]) >= args.height+2 or abs(center_pos["z"]-initial_pos["z"]) <= args.height-2:
        print(f"Error: Vehicle did not reach the desired height.")
        land_result = requests.get(f"{base_url}/command/land")
        if land_result.status_code != 200:
            print(f"Land command fail. status_code={land_result.status_code}")
            exit()
        print("Vehicle landed.")
        exit()

polygon_list = args.sides
for l in polygon_list:
    print(f"\n ---polygon {l}---------------------------------- \n")

    # For each polygon gets the NED trajectory vectors to the vertices
    polygon_trajectory = make_polygon_trajectory(args.radius, l)
        
    # Moving
    for vector in polygon_trajectory:
        # For each vertex moves the vehicle along its trajectory using drive_wait
        vector_result = requests.post(f"{base_url}/movement/drive_wait", json=vector)
        if vector_result.status_code != 200:
            print(f"Drive_wait command fail. status_code={vector_result.status_code} vector={vector}")
            exit()
        print(f"\nTrajectory vector: {vector})")

        #sleep ensures the vehicle has time to reach its desired position
        sleep(SLEEP_TIME)

        # Get the NED coordinates, from telemetry, of the vertex for better user visualization and debugging
        tele_ned_result = requests.get(f"{base_url}/telemetry/ned")
        if tele_ned_result.status_code != 200:
            print(f"Ned telemetry fail. status_code={tele_ned_result.status_code}")
            exit()
        tele_ned_pos = tele_ned_result.json()["info"]["position"]
        print(f"Vehicle at {tele_ned_pos})")

    # After completing the polygon, return the vehicle to the center using go_to_ned_wait
    point_result = requests.post(f"{base_url}/movement/go_to_ned_wait", json=center_pos)
    if point_result.status_code != 200:
        print(f"Go_to_ned_wait command fail. status_code={point_result.status_code} point={center_pos}")
        exit()
    print(f"\nVehicle going back to the center")

    #sleep ensures the vehicle has time to reach its desired position
    sleep(SLEEP_TIME)
    
    print(f"Vehicle at the center")

# Landing
land_result = requests.get(f"{base_url}/command/land")
if land_result.status_code != 200:
    print(f"Land command fail. status_code={land_result.status_code}")
    exit()
print("\nVehicle landed.")

```
## Delivery Mission Simulation
This example simulates a complete delivery cycle. The drone takes off from its home position, navigates to a pickup location defined by the user, lands to simulate picking up a package (disarming and waiting), then takes off again to navigate to a delivery location. After landing and simulating the drop-off, the drone returns to the initial home position and lands.

Unlike previous examples that rely on `go_to_ned_wait`, this script uses the asynchronous `go_to_ned` endpoint and implements a custom arrival check loop function called `wait_for_arrival`. This function continuously checks the telemetry to calculate the Euclidean distance between the drone's current position and the target coordinate. The drone is considered to have arrived when the distance `d` is less than a defined tolerance:

$$d = \sqrt{(x_{target}-x_{current})^2 + (y_{target}-y_{current})^2 + (z_{target}-z_{current})^2}$$

Additionally, the script calculates the absolute position adjustments. Since the user inputs coordinates relative to the takeoff point (0,0,0), the script adds the global NED coordinates of the "Home" position to the target:

$$P_{target} = P_{home} + P_{input}$$

To ensure safety during navigation, the script applies a `SAFE_OFFSET` (typically -2 meters) to the flight altitude when moving between points, only descending to the exact Z coordinate during the landing phase.

To use this example, the user must provide the Pickup and Delivery coordinates as command-line arguments in the format `North,East,Down`. Note that altitude (Down) should be negative for positions above ground, though the script attempts to correct positive inputs.

For example, to pick up a package at (1m North, 3m East, 3m Up) and deliver it at (0m North, 2m East, 3m Up):

`python delivery_simulation.py 1,3,-3 0,2,-3`

If no arguments are provided, the script runs with default coordinates.

This file is located at `flight_examples/delivery/delivery_simulation.py`.

```Python
#Objective: Control a drone via Python to simulate a delivery.
#The drone picks up the package, goes to the delivery point, lands,
#disarms, simulates/drops an actuator, arms, takes off, and returns to first takeoff point (home).

#Steps:
# 1. Receive pickup and delivery locations as NED points via command line arguments.
# 2. Get home location from drone telemetry.
# 3. Arm and take off to a safe altitude.
# 4. Navigate to pickup location, land, disarm, simulate package pickup.
# 5. Arm, take off to a safe altitude, navigate to delivery location, land, disarm, simulate package drop.
# 6. Arm, take off to a safe altitude, return to home location, land.

#Observations:
# - A -2 meter offset is applied to the Down NED points for safe altitude during navigation.
# - Takeoff altitude is set to 5 meters above ground level.

import sys #sys module to handle command line arguments
import requests #requests module to make HTTP requests
import time #time module to handle sleep and timeouts
import math #math module for distance calculations

BASE_URL = "http://localhost:8000" # Base URL for the drone API
SLEEP_DURATION = 4 #variable to adjust sleep duration between commands
TAKEOFF_ALTITUDE = 5 # Safe takeoff altitude in meters
SAFE_OFFSET = -2 # Safe offset in Down NED coordinate in meters

# Function to send commands to the drone API
def send_command(endpoint, params=None, method="GET"):
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, params=params)
        elif method == "POST":
            response = requests.post(url, json=params)
        else:
            raise ValueError("Unsupported HTTP method")

        if response.status_code != 200:
            print(f"Command {endpoint} failed. status_code={response.status_code}")
            exit()
        return response.json()
    except requests.RequestException as e:
        print(f"HTTP request failed: {e}")
        exit()

# Function to calculate distance between two NED points
def distance(end, start):
    return math.sqrt((end[0]-start[0])**2 + (end[1]-start[1])**2 + ((end[2] + SAFE_OFFSET)-start[2])**2)

# Function to wait until the drone arrives at a specified location within a tolerance and timeout
def wait_for_arrival(location, tolerance=1.0, timeout=120):
    start = time.time()
    while time.time() < start + timeout:
        ned_result = requests.get(f"{BASE_URL}/telemetry/ned")
        if ned_result.status_code != 200:
            print(f"NED telemetry fail. status_code={ned_result.status_code}")
            exit()
        ned_pos = ned_result.json()["info"]["position"]
        ned_point = (ned_pos["x"]-home_location[0], ned_pos["y"]-home_location[1], ned_pos["z"]-home_location[2])
        dist = distance(location, ned_point)
        print(f"Current position: {ned_point}, distance to target: {dist:.2f} m")
        if dist < tolerance:
            return True
        time.sleep(2)
    return False



#Recieve package and delivery locations via command line format: N,E,D N,E,D
if len(sys.argv) == 1: #if no arguments are provided, default locations are used
    pickup_location = (1, 3, -3) #Default pickup location
    delivery_location = (0, 2, -3) #Default delivery location
    print("No command line arguments provided. Using default locations.")
elif len(sys.argv) != 3: #Invalid number of arguments
    print("Usage: python t3.py <pickup_location> <delivery_location>")
    exit()
else: #Parse command line arguments
    try:
        pickup_location = tuple(map(float, sys.argv[1].split(',')))
        delivery_location = tuple(map(float, sys.argv[2].split(',')))
        if len(pickup_location) != 3 or len(delivery_location) != 3: # Check for correct number of coordinates
            raise ValueError
    except ValueError:
        print("Invalid location format. Use N(orth),E(ast),D(own)")
        exit()
# Ensure altitudes are negative in NED coordinates
if pickup_location[2] >= 0 or delivery_location[2] >= 0:
    pickup_location = (pickup_location[0], pickup_location[1], -abs(pickup_location[2]))
    delivery_location = (delivery_location[0], delivery_location[1], -abs(delivery_location[2]))
    print("Altitude must be negative in NED coordinates. Adjusted to negative values.")

# Start
print("\nNED points received: ", pickup_location, delivery_location)
# Get home location
print("Getting home location based on NED telemetry of EKF origin...")
home = send_command("/telemetry/ned")["info"]["position"]
home_location = (home["x"], home["y"], home["z"])
print("Home location at NED point: ", home_location)
time.sleep(SLEEP_DURATION) # Sleep to ensure commands are spaced out

print("Arming...")
send_command("/command/arm")
time.sleep(SLEEP_DURATION)

print("Takeoff...")
send_command("/command/takeoff", params={"alt": TAKEOFF_ALTITUDE})
time.sleep(SLEEP_DURATION)

# Pickup location
#default pickup_location = (1, 3, -3)
print("Going to pickup location at NED point: ", pickup_location)
send_command("/movement/go_to_ned", params={"x": pickup_location[0]+home_location[0],
                                            "y": pickup_location[1]+home_location[1],
                                            "z": pickup_location[2]+home_location[2]+SAFE_OFFSET},
                                            method="POST")
time.sleep(SLEEP_DURATION)

print(pickup_location)
if wait_for_arrival(pickup_location):
    print("Drone arrived at pickup location")
time.sleep(SLEEP_DURATION)


print("Landing to pick up package...")
send_command("/command/land")
time.sleep(SLEEP_DURATION)

current_ned = send_command("/telemetry/ned")["info"]["position"]
current_ned_point = (current_ned["x"]-home_location[0],
                     current_ned["y"]-home_location[1],
                     current_ned["z"]-home_location[2])
print("Current NED position after landing: ", current_ned_point)
time.sleep(SLEEP_DURATION)

print("Disarming...")
print("Simulating package pickup...")
# simulated pick up
time.sleep(SLEEP_DURATION)

print("Arming...")
send_command("/command/arm")
time.sleep(SLEEP_DURATION)

print("Takeoff...")
send_command("/command/takeoff", params={"alt": TAKEOFF_ALTITUDE})
time.sleep(SLEEP_DURATION)

# Delivery location
#default delivery_location = (0, 2, -3)
print("Going to delivery location at NED point: ", delivery_location)
send_command("/movement/go_to_ned", params={"x": delivery_location[0]+home_location[0],
                                            "y": delivery_location[1]+home_location[1],
                                            "z": delivery_location[2]+home_location[2]+SAFE_OFFSET},
                                            method="POST")
time.sleep(SLEEP_DURATION)

print(delivery_location)
if wait_for_arrival(delivery_location):
    print("Drone arrived at delivery location")
time.sleep(SLEEP_DURATION)

print("Landing to deliver package...")
send_command("/command/land")
time.sleep(SLEEP_DURATION)

current_ned = send_command("/telemetry/ned")["info"]["position"]
current_ned_point = (current_ned["x"]-home_location[0],
                     current_ned["y"]-home_location[1],
                     current_ned["z"]-home_location[2])
print("Current NED position after landing: ", current_ned_point)
time.sleep(SLEEP_DURATION)

print("Disarming...")
print("Simulating package drop...")
# simulated drop
time.sleep(SLEEP_DURATION)

print("Arming...")
send_command("/command/arm")
time.sleep(SLEEP_DURATION)

print("Takeoff...")
send_command("/command/takeoff", params={"alt": TAKEOFF_ALTITUDE})
time.sleep(SLEEP_DURATION)

print("Returning to Home at NED point: ", home_location)
send_command("/movement/go_to_ned", params={"x": home_location[0],
                                            "y": home_location[1],
                                            "z": home_location[2]+SAFE_OFFSET},
                                            method="POST")
time.sleep(SLEEP_DURATION)

if wait_for_arrival(0,0,0):
    print("Drone arrived near Home location")
time.sleep(SLEEP_DURATION)

print("landing at Home location...")
send_command("/command/land")
time.sleep(SLEEP_DURATION)

current_ned = send_command("/telemetry/ned")["info"]["position"]
current_ned_point = (current_ned["x"]-home_location[0],
                     current_ned["y"]-home_location[1],
                     current_ned["z"]-home_location[2])
print("Current NED position after landing: ", current_ned_point)

print("Mission Accomplished")
```

## GPS-Based Follower
This example demonstrates an autonomous follower drone that tracks a leader drone using GPS coordinates. Unlike the previous NED-based follower example, this implementation uses global GPS positioning (latitude, longitude, altitude) and implements a setup/loop architecture similar to microcontroller programming patterns.

The script operates in two phases: a setup phase that initializes the follower drone, and a continuous loop phase that tracks the leader. The follower maintains a configurable offset from the leader's position to avoid collisions.

The core algorithm converts meter-based offsets into GPS coordinate deltas. For latitude, the conversion is straightforward since 1 degree of latitude is approximately 111,111 meters globally:

$$\Delta_{lat} = \frac{offset_{north}}{111111}$$

For longitude, the conversion must account for the convergence of meridians at different latitudes. The distance represented by 1 degree of longitude varies with the cosine of the latitude:

$$\Delta_{lon} = \frac{offset_{east}}{111111 \cdot \cos(lat_{leader})}$$

The target position for the follower is then calculated by adding these deltas to the leader's current position:

$$lat_{target} = lat_{leader} + \Delta_{lat}$$
$$lon_{target} = lon_{leader} + \Delta_{lon}$$

For altitude management, the script calculates relative altitude by subtracting the absolute ground altitude captured during setup, then applies the configured altitude offset:

$$alt_{target} = \max(2.0, (alt_{leader} - alt_{ground}) + offset_{alt})$$

The minimum altitude constraint ensures the follower never flies below 2 meters.

To use this example, configure the leader and follower URLs in the script. The leader URL should point to the leader drone's API endpoint (which may be on a different network address), while the follower URL typically points to localhost:

```python
FOLLOWER_URL = "http://localhost:8000"
LEADER_URL = "http://10.0.2.159:8000"  # Replace with actual leader IP
```

You can also adjust the following offset parameters to control the follower's relative position:

```python
OFFSET_NORTH = -3  # meters behind the leader
OFFSET_EAST = 0    # horizontally aligned
OFFSET_ALT = 2.0   # altitude difference in meters
ALTITUDE_VOO = 2   # takeoff altitude
```

The script includes a keyboard interrupt handler (Ctrl+C) that safely triggers RTL (Return to Launch) before exiting. The loop runs at 2Hz (0.5 second intervals) to balance responsiveness with API load.

This file is located at `flight_examples/follow/follow.py`.

```python
import requests
import time
import math
import sys

# --- CONFIGURAÇÕES ---
FOLLOWER_URL = "http://localhost:8000" # Drone que vai seguir
LEADER_URL   = "http://10.0.2.159:8000" # Drone a ser seguido

# Offset em metros (Para o drone seguidor não bater no líder)
OFFSET_NORTH = -3  # 3 metros atrás (se o líder estiver indo para o Norte)
OFFSET_EAST  = 0   # Alinhado horizontalmente
OFFSET_ALT   = 2.0
ALTITUDE_VOO = 2  # Altura de cruzeiro

ALTITUDE_ABS = 0  # Variável global


def setup():
    """
    Função chamada uma única vez no início.
    Responsável por armar e decolar o drone seguidor.
    """
    print("--- INICIANDO SETUP ---")

    global ALTITUDE_ABS

    # 1. Captura altitute absoluta
    print("Capturando altitude absoluta...")
    pos_result = requests.get(f"{FOLLOWER_URL}/telemetry/gps")

    if pos_result.status_code == 200:
        data = pos_result.json()
        l_pos = data['info']['position']
        ALTITUDE_ABS = float(l_pos['alt'])

    print(f"Altitude absoluta capturada: {ALTITUDE_ABS}m")

    # 2. Armar
    print("Armando o veículo...")
    arm_result = requests.get(f"{FOLLOWER_URL}/command/arm")
    if arm_result.status_code != 200:
        print(f"ERRO: Falha ao armar. Code: {arm_result.status_code}")
        sys.exit(1)

    # 3. Decolar
    print(f"Decolando para {ALTITUDE_VOO}m...")
    params = {"alt": ALTITUDE_VOO}
    takeoff_result = requests.get(f"{FOLLOWER_URL}/command/takeoff", params=params)
    if takeoff_result.status_code != 200:
        print(f"ERRO: Falha na decolagem. Code: {takeoff_result.status_code}")
        sys.exit(1)

    print("--- SETUP CONCLUÍDO ---")

def loop():
    """
    Função rodada repetidamente.
    Lê a posição do Líder, calcula o Offset e move o Seguidor.
    """
    try:
        # 1. PEGAR POSIÇÃO DO LÍDER (Pulling)
        pos_result = requests.get(f"{LEADER_URL}/telemetry/gps")

        if pos_result.status_code == 200:

            data = pos_result.json()

            l_pos = data['info']['position']

            leader_lat = float(l_pos['lat'])
            leader_lon = float(l_pos['lon'])
            leader_alt = float(l_pos['alt'])

            print(f"[Lider] Lat: {leader_lat:.6f}, Lon: {leader_lon:.6f}")

            # 2. CALCULAR NOVA POSIÇÃO COM OFFSET

            delta_lat = OFFSET_NORTH / 111111.0
            delta_lon = OFFSET_EAST / (111111.0 * math.cos(math.radians(leader_lat)))

            target_lat = leader_lat + delta_lat
            target_lon = leader_lon + delta_lon

            raw_target_alt = (leader_alt - ALTITUDE_ABS) + OFFSET_ALT
            target_alt = max(2.0, raw_target_alt)

            # 3. ENVIAR COMANDO DE MOVIMENTO (Go To)

            fly_data = {
                "lat": target_lat,
                "long": target_lon,
                "alt": target_alt,
            }

            follow_result = requests.post(f"{FOLLOWER_URL}/movement/go_to_gps", json=fly_data)
            if follow_result.status_code != 200:
                print(f"ERRO: Falha no movimento. Code: {follow_result.status_code}")
                print(f"Detalhe do erro: {follow_result.text}")
                sys.exit(0)

            print(f">> Movendo Seguidor para: {target_lat:.6f}, {target_lon:.6f}")

        else:
            print(f"ERRO: Não conseguiu ler o líder. Code: {pos_result.status_code}")

        # Delay do Loop (Taxa de atualização)
        # 0.5s = 2Hz
        time.sleep(0.5)

    except Exception as e:
        print(f"Erro no loop: {e}")

# --- BLOCO PRINCIPAL ---
if __name__ == "__main__":
    try:
        setup()
        while True:
            loop()
    except KeyboardInterrupt:
        # Captura Ctrl+C para pousar com segurança
        print("\n--- INTERRUPÇÃO DETECTADA ---")
        print("Iniciando RTL (Return to Land)...")
        requests.get(f"{FOLLOWER_URL}/command/rtl")
        print("Encerrando programa.")
        sys.exit(0)
```



