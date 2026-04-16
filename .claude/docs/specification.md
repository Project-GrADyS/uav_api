# API Specification

Base URL: `http://localhost:<port>`
Interactive docs: `http://localhost:<port>/docs`

All successful responses include `"device": "uav"` and `"id": "<sysid>"`. Failures raise HTTP 500 with a descriptive `"detail"` string.

---

## /command — Vehicle Control

All endpoints use **GET**.

### `GET /command/arm`
Arms the vehicle. Changes flight mode to GUIDED first, then waits until ready to arm.

**Response:**
```json
{"device": "uav", "id": "1", "result": "Armed vehicle"}
```

---

### `GET /command/takeoff?alt=<int>`
Sends a takeoff command. Blocks until the vehicle reaches the target altitude.

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `alt` | int | 15 | Target altitude in meters |

**Response:**
```json
{"device": "uav", "id": "1", "result": "Takeoff successful! Vehicle at 15 meters"}
```

---

### `GET /command/land`
Lands the vehicle and disarms it.

**Response:**
```json
{"device": "uav", "id": "1", "result": "Landed at home successfully"}
```

---

### `GET /command/rtl`
Triggers Return-to-Launch. Blocks until the vehicle returns home and disarms.

**Response:**
```json
{"device": "uav", "id": "1", "result": "Landed at home successfully"}
```

---

### `GET /command/set_air_speed?new_v=<int>`
### `GET /command/set_ground_speed?new_v=<int>`
### `GET /command/set_climb_speed?new_v=<int>`
### `GET /command/set_descent_speed?new_v=<int>`
Set the respective speed in m/s.

| Query param | Type | Description |
|-------------|------|-------------|
| `new_v` | int | New speed value in m/s |

**Response:**
```json
{"device": "uav", "id": "1", "result": "Air speed set to 5m/s"}
```

---

### `GET /command/set_sim_speedup?sim_factor=<float>`
Sets the `SIM_SPEEDUP` MAVLink parameter. Only meaningful in SITL simulated mode.

| Query param | Type | Description |
|-------------|------|-------------|
| `sim_factor` | float | Simulation time multiplier |

**Response:**
```json
{"device": "uav", "id": "1", "result": "Simulation speedup set to 5x"}
```

---

### `GET /command/set_home`
Sets the vehicle's HOME location to its current GPS position.

**Response:**
```json
{"device": "uav", "id": "1", "result": "Home location set successfully!"}
```

---

## /movement — Flight Movement

> All movement POST endpoints accept an optional `look_at_target` boolean (default `false`). When `true`, the vehicle yaws to face the direction of travel.

### `POST /movement/go_to_gps/`
Sends the vehicle to an absolute GPS position. Returns immediately (non-blocking).

**Request body:**
```json
{"lat": 37.7749, "long": -122.4194, "alt": 20.0, "look_at_target": false}
```

**Response:**
```json
{"device": "uav", "id": "1", "result": "Going to coord (37.7749, -122.4194, 20.0)"}
```

---

### `POST /movement/go_to_gps_wait`
Same as `go_to_gps` but blocks until the vehicle arrives (timeout: 60 seconds).

**Response:**
```json
{"device": "uav", "id": "1", "result": "Arrived at coord (37.7749, -122.4194, 20.0)"}
```

---

### `POST /movement/go_to_ned`
Moves to an absolute NED (North-East-Down) position relative to HOME. Non-blocking.

**Request body:**
```json
{"x": 10.0, "y": 5.0, "z": -15.0, "look_at_target": false}
```
> Note: `z` is negative for altitude above ground (Down convention).

**Response:**
```json
{"device": "uav", "id": "1", "result": "Going to NED coord (10.0, 5.0, -15.0)"}
```

---

### `POST /movement/go_to_ned_wait`
Same as `go_to_ned` but blocks until the vehicle arrives.

**Response:**
```json
{"device": "uav", "id": "1", "result": "Arrived at NED coord (10.0, 5.0, -15.0)"}
```

---

### `POST /movement/drive`
Moves the vehicle by a relative NED offset from its current position. Non-blocking.

**Request body:**
```json
{"x": 5.0, "y": 0.0, "z": 0.0, "look_at_target": false}
```

**Response:**
```json
{"device": "uav", "id": "1", "result": "Copter is driving"}
```

---

### `POST /movement/drive_wait`
Same as `drive` but blocks until the vehicle reaches the computed target position.

**Response:**
```json
{"device": "uav", "id": "1", "result": "Copter arrived at (15.0, 5.0, -15.0)"}
```

---

### `POST /movement/travel_at_ned`
Sets the vehicle's velocity in NED frame. Non-blocking — the vehicle continues at the specified velocity until stopped.

**Request body:**
```json
{"vx": 2.0, "vy": 0.0, "vz": 0.0, "look_at_target": false}
```
> `vx`=North, `vy`=East, `vz`=Down velocity in m/s. `look_at_target` (optional, default `false`) — when `true`, the vehicle yaws to face the direction of travel.

**Response:**
```json
{"device": "uav", "id": "1", "result": "Travelling at NED velocity (2.0, 0.0, 0.0)"}
```

> Note: This endpoint uses the `Local_velocity` model (fields `vx`, `vy`, `vz`), unlike position endpoints which use `Local_pos` (fields `x`, `y`, `z`).

---

### `GET /movement/set_heading?heading=<float>`
Sets the vehicle's heading (yaw) to the specified angle in degrees. Non-blocking.

| Query param | Type | Description |
|-------------|------|-------------|
| `heading` | float | Target heading in degrees (0–360, 0 = North, 90 = East) |

**Response:**
```json
{"device": "uav", "id": "1", "result": "Heading set to 90.0 degrees"}
```

---

### `GET /movement/set_yaw_rate?yaw_rate=<float>`
Spins the vehicle continuously at the specified angular speed. Positive values rotate clockwise, negative values rotate counter-clockwise. Send 0 to stop spinning. Non-blocking.

| Query param | Type | Description |
|-------------|------|-------------|
| `yaw_rate` | float | Angular speed in degrees/s (positive = CW, negative = CCW) |

**Response:**
```json
{"device": "uav", "id": "1", "result": "Yaw rate set to 30.0 deg/s"}
```

---

### `GET /movement/stop`
Stops the vehicle in place (holds current position).

**Response:**
```json
{"device": "uav", "id": "1", "result": "Copter has stopped"}
```

---

### `GET /movement/resume`
Resumes movement after a stop.

**Response:**
```json
{"device": "uav", "id": "1", "result": "Copter has resumed movement"}
```

---

## /telemetry — Sensor Data

All endpoints use **GET** and return `"result": "Success"` plus an `"info"` object.

### `GET /telemetry/general`
General flight state from the `VFR_HUD` MAVLink message.

```json
{
  "device": "uav", "id": "1", "result": "Success",
  "info": {
    "airspeed": 0.0,
    "groundspeed": 0.02,
    "heading": 270,
    "throttle": 0,
    "alt": 584.27
  }
}
```

---

### `GET /telemetry/gps`
Fused position from `GLOBAL_POSITION_INT` (sensor fusion of GPS + accelerometers).

```json
{
  "info": {
    "position": {"lat": -15.84, "lon": -47.92, "alt": 1063.09, "relative_alt": 0.0},
    "velocity": {"vx": 0.0, "vy": 0.0, "vz": 0.0},
    "heading": 270.0
  }
}
```
> Values are converted: lat/lon to degrees (÷1e7), alt to meters (÷1000), velocity to m/s (÷100).

---

### `GET /telemetry/gps_raw`
Raw data directly from the GPS sensor (`GPS_RAW_INT`).

```json
{
  "info": {
    "position": {"lat": -15.84, "lon": -47.92, "alt": 1063.0},
    "velocity": {"ground_speed": 0.0, "speed_direction": 0.0},
    "satelites": 10
  }
}
```

---

### `GET /telemetry/ned`
Local NED position and velocity from `LOCAL_POSITION_NED`.

```json
{
  "info": {
    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
    "velocity": {"vx": 0.0, "vy": 0.0, "vz": 0.0}
  }
}
```

---

### `GET /telemetry/compass`
Compass calibration status from `MAG_CAL_REPORT`.

```json
{
  "info": {
    "calibration_status": 3,
    "autosaved": true,
    "fitness": {"x": 0.0, "y": 0.0, "z": 0.0}
  }
}
```

---

### `GET /telemetry/sys_status`
Raw `SYS_STATUS` MAVLink message as a dictionary. Useful for low-level diagnostics.

```json
{"device": "uav", "id": "1", "result": "success", "status": {...}}
```

---

### `GET /telemetry/sensor_status`
Parsed sensor health flags extracted from `SYS_STATUS`.

```json
{"device": "uav", "id": "1", "result": "success", "status": {...}}
```

---

### `GET /telemetry/battery_info`
Battery voltage and current from `SYS_STATUS`.

```json
{"device": "uav", "id": "1", "result": "success", "info": {...}}
```

---

### `GET /telemetry/error_info`
Communication and autopilot error flags from `SYS_STATUS`.

```json
{"device": "uav", "id": "1", "result": "success", "info": {...}}
```

---

### `GET /telemetry/home_info`
HOME position (the NED coordinate origin). Set at arming time or via `/command/set_home`.

```json
{
  "device": "uav", "id": "1", "result": "Success",
  "lat": -15.84, "lon": -47.92, "altitude": 1063.0,
  "x": 0.0, "y": 0.0, "z": 0.0
}
```

---

## /mission — Script Management

### `POST /mission/upload-script`
Uploads a Python or shell script to `scripts_path`. Multipart form upload.

| Form field | Type | Description |
|------------|------|-------------|
| `file` | UploadFile | `.py` or `.sh` file only; filename is sanitized |

**Response:**
```json
{"device": "uav", "id": "1", "type": 44, "info": "Mission File 'my_script.py' saved at ~/uav_scripts/my_script.py successfully."}
```

**Errors:** 400 if wrong extension; 500 if file save fails.

---

### `GET /mission/list-scripts`
Lists all `.py` files currently in `scripts_path`.

**Response:**
```json
{"device": "uav", "id": "1", "type": 42, "scripts": ["my_script.py", "square.py"]}
```

---

### `POST /mission/execute-script/`
Executes an uploaded script in a tmux session named `"api-script"`. Non-blocking — returns after launching.

**Request body:**
```json
{"script_name": "my_script"}
```
> `.py` extension is appended if missing.

**Response:**
```json
{"device": "uav", "id": "1", "type": 46, "script": "my_script.py"}
```

**Behavior:**
- If session `"api-script"` already exists, sends `Ctrl+C` to stop the current script, then runs the new one
- stdout → `<script_logs>/<name>_<timestamp>_out.log`
- stderr → `<script_logs>/<name>_<timestamp>_err.log`
- Attach live: `tmux attach -t api-script`

**Errors:** 404 if script not found.

---

### `DELETE /mission/clear`
Deletes all `.py` and `.sh` files from the scripts directory.

**Response:**
```json
{"device": "uav", "id": "1", "type": 48, "info": "Removed 2 script(s)", "removed": ["a.py", "b.sh"]}
```

---

## /peripherical — Hardware Peripherals

### `GET /peripherical/take_photo`
Takes a photo using a whitelisted camera CLI tool. The tool must be installed on the system.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `command` | `str` | *(required)* | Camera tool to use. Allowed: `fswebcam`, `rpicam-still`, `libcamera-still` |
| `resolution` | `str` | `1280x720` | Capture resolution in `WIDTHxHEIGHT` format |
| `capture_time` | `int` | `150` | Capture delay / warm-up in milliseconds |

**Response:** `image/jpeg` file (`Content-Disposition: attachment; filename="photo.jpg"`)

**Errors:**
- `400` — disallowed command or invalid resolution format
- `500` — capture command failed (stderr included in detail)
- `504` — command timed out (fixed 30s limit)

---

### `POST /peripherical/servo_output`
Sends a PWM signal to a servo motor connected to one of the flight controller's actuator ports. Uses the MAVLink `MAV_CMD_DO_SET_SERVO` command.

**Request body:**
```json
{"channel": 9, "pwm": 1500}
```

| Field | Type | Description |
|-------|------|-------------|
| `channel` | int | Servo channel (1-based, matches the flight controller actuator port) |
| `pwm` | int | PWM value in microseconds (typically 1000–2000) |

**Response:**
```json
{"device": "uav", "id": "1", "result": "Servo 9 set to 1500 PWM"}
```

**Errors:**
- `422` — missing or invalid parameters
- `500` — MAVLink command failed
