import asyncio

async def send_location_to_gradys_gs(uav, session, api_port, gradys_gs_address):
    """Asynchronously send location data to Gradys Ground Station."""
    path = "http://" + gradys_gs_address + "/update-info/"
    seq = 0

    while True:
        try:
            # Fetch location from Gradys Ground Station
            print("Fetching location for Gradys GS...")
            location = uav.get_gps_info()
            print(f"Location fetched: alt={location.alt}, lat={location.lat}, lng={location.lon}")
            data = {
                "id": uav.target_system,
                "lat": str(location.lat), 
                "lng": str(location.lon), 
                "alt": str(location.relative_alt),
                "device": "uav",
                "type": 102, # Internal UAV location update message type,
                "seq": seq,
                "ip": "127.0.0.1:"+str(api_port)+"/"
            }

            print("Sending request to Gradys GS...")
            try:
                response = await session.post(path, data=data)
                if response.status != 200:
                    print(f"Failed to send location data: {response.status}")
                else:
                    print(f"Location {seq} sent to Gradys GS.")
                    seq += 1
            except Exception as e:
                print(f"Error sending location data: {e}")
        except Exception as e:
            print(f"Error sending location to Gradys GS: {e}")
            return
        await asyncio.sleep(1)  # Fetch location every second