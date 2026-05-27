from pathlib import Path
from uav_api.args import read_args_from_env
from uav_api.vehicles.copter import Copter
from uav_api.vehicles.plane import Plane

copter = None
plane = None
args = None

def get_copter_instance(sysid=None, connection=None):
    global copter
    if copter is None:
        copter = Copter(sysid=int(sysid))
        copter.connect(connection_string=connection)
    return copter

def get_plane_instance(sysid=None, connection=None):
    global plane
    if plane is None:
        plane = Plane(sysid=int(sysid))
        plane.connect(connection_string=connection)
    return plane

def get_args():
    global args
    if args is None:
        args = read_args_from_env()
    return args