import asyncio
import logging
import subprocess

def get_system_ip():
    interface = "wlan0"
    
    # 1. Try 'ip addr show wlan0'
    try:
        # We use shell=True to easily pipe into grep
        cmd = f"ip -4 addr show {interface} | grep -oP '(?<=inet\s)\d+(\.\d+){{3}}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        # If grep found an IP, it returns 0. If it found nothing, it returns non-zero.
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
            
    except Exception:
        pass # Fall through to the backup method

    # 2. Backup: Try 'hostname -I'
    try:
        # This returns all assigned IPs as a space-separated string
        result = subprocess.run(["hostname", "-I"], capture_output=True, text=True)
        ips = result.stdout.strip().split()
        
        if ips:
            return ips[0]  # Return the first available IP
            
    except Exception:
        pass

    return "127.0.0.1" # Absolute fallback

async def send_location_to_gradys_gs(uav, session, api_port, gradys_gs_address):
    """Asynchronously send location data to Gradys Ground Station."""
    path = "http://" + gradys_gs_address + "/update-info/"
    seq = 0
    ip_address = get_system_ip()

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