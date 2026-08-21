from uav_api.args import read_args_from_env
from uav_api.vehicles.copter import Copter
from uav_api.vehicles.plane import Plane

copter = None
plane = None
args = None
scripts_table = None

def init_copter(sysid, connection):
    """Builds and connects the copter singleton. Called from the lifespan only."""
    global copter
    if copter is None:
        copter = Copter(sysid=int(sysid))
        copter.connect(connection_string=connection)
    return copter

def init_plane(sysid, connection):
    """Builds and connects the plane singleton. Called from the lifespan only."""
    global plane
    if plane is None:
        plane = Plane(sysid=int(sysid))
        plane.connect(connection_string=connection)
    return plane

def get_copter_instance():
    if copter is None:
        raise RuntimeError("Copter not initialized. init_copter must run first (lifespan).")
    return copter

def get_plane_instance():
    if plane is None:
        raise RuntimeError("Plane not initialized. init_plane must run first (lifespan).")
    return plane

def get_args():
    global args
    if args is None:
        args = read_args_from_env()
    return args

def get_scripts_table():
    global scripts_table
    if scripts_table is None:
        scripts_table = {}
    return scripts_table