# Drone Delivery Simulation

## Objective
Control a drone via Python to simulate a delivery mission:
- Arm and take off to a safe altitude.
- Navigate to pickup location, land, disarm, simulate package pickup.
- Arm, take off, navigate to delivery location, land, disarm, simulate package drop.
- Arm, take off, return to home location, land.

## Features
- Uses NED (North, East, Down) coordinates.
- Applies a -2 meter offset in Down axis for safe navigation.
- Default takeoff altitude: 5 meters.
- Accepts pickup and delivery coordinates via command line arguments.

## Requirements
- Python 3.x
- `requests` library
- Drone API running locally at `http://localhost:8000`

Install dependencies:
```bash
pip install requests
Usage
Run the script with default locations:

bash
python t3.py
Or provide custom pickup and delivery NED coordinates:

bash
python t3.py 1,3,-3 0,2,-3
Example Flow
Arm and take off.

Fly to pickup location.

Land, disarm, simulate package pickup.

Arm, take off, fly to delivery location.

Land, disarm, simulate package drop.

Arm, take off, return to home, land.