from uav_api.args import read_args_from_env
from uav_api.vehicles.copter import Copter
from uav_api.vehicles.plane import Plane

copter = None
plane = None
args = None
scripts_table = None

def _stream_rate(stream_rate):
    """int() a stream rate and reject non-positive values.

    Config-file values arrive as strings (args.py layers them with a bare
    setattr), bypassing argparse's positive_int. A rate of 0 stops the streams,
    so connect() would wait out its SYSTEM_TIME timeout and fail opaquely.
    """
    rate = int(stream_rate)
    if rate <= 0:
        raise ValueError(f"mavlink_streamrate must be greater than 0, got {rate}")
    return rate

def init_copter(sysid, connection, stream_rate=5):
    """Builds and connects the copter singleton. Called from the lifespan only."""
    global copter
    if copter is None:
        copter = Copter(sysid=int(sysid), default_stream_rate=_stream_rate(stream_rate))
        copter.connect(connection_string=connection)
    return copter

def init_plane(sysid, connection, stream_rate=5):
    """Builds and connects the plane singleton. Called from the lifespan only."""
    global plane
    if plane is None:
        plane = Plane(sysid=int(sysid), default_stream_rate=_stream_rate(stream_rate))
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