from pathlib import Path
from uav_api.args import read_args_from_env
from uav_api.copter import Copter

copter = None
scripts_path = None

def get_copter_instance(sysid=None, connection=None):
    global copter
    if copter is None:
        copter = Copter(sysid=int(sysid))
        copter.connect(connection_string=connection)
    return copter

def get_scripts_path():
    global scripts_path
    if scripts_path is None:
        args = read_args_from_env()
        scripts_path = Path(args.scripts_path).expanduser()
    return scripts_path