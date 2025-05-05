from uav_api.copter import Copter

copter = None

# in the future this function should use different prefix for connection_string based on CopterMode
def get_copter_instance(sysid=None, connection=None):
    global copter
    if copter is None:
        copter = Copter(sysid=int(sysid))
        copter.connect(connection_string=connection)
    return copter