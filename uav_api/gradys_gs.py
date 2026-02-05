import asyncio
import logging
import socket

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # We don't even have to be reachable for this to work
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

async def send_location_to_gradys_gs(uav, session, api_port, gradys_gs_address):
    """Asynchronously send location data to Gradys Ground Station."""
    path = "http://" + gradys_gs_address + "/update-info/"
    seq = 0
    ip_address = get_local_ip()

    _logger = logging.getLogger("GRADYS_GS")

    while True:
        await asyncio.sleep(1)  # Fetch location every second

        try:
            # Fetch location from Gradys Ground Station
            try:
                _logger.info("Fetching location for Gradys GS...")
                location = uav.get_gps_info()
            except Exception as e:
                _logger.warning("Failed to fetch location")
                continue
            _logger.info(f"Location fetched: alt={location.alt}, lat={location.lat}, lng={location.lon}")
            data = {
                "id": uav.target_system,
                "lat": str(location.lat / 1.0e7), 
                "lng": str(location.lon / 1.0e7), 
                "alt": str(location.relative_alt / 1000),
                "device": "uav",
                "type": 102, # Internal UAV location update message type,
                "seq": seq,
                "ip": f"{ip_address}:{api_port}/"
            }

            _logger.info("Sending request to Gradys GS...")
            try:
                response = await session.post(path, data=data)
                if response.status != 200:
                    _logger.warning(f"Failed to send location data: {response.status}")
                else:
                    _logger.info(f"Location {seq} sent to Gradys GS.")
                    seq += 1
            except Exception as e:
                _logger.warning(f"Error sending location data: {e}")
        except Exception as e:
            _logger.warning(f"Error sending location to Gradys GS: {e}")