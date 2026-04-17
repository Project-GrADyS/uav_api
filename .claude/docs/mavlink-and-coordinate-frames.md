# MAVLink & Coordinate Frames

Domain knowledge that does not live in any single file: coordinate frames, SITL launch quirks, real-drone connection tradeoffs, and common MAVLink pitfalls. Read this before writing new movement logic or debugging connection/position issues.

## Coordinate frames

Three frames appear in the API surface:

### 1. GPS (absolute)
Units: degrees of latitude/longitude, meters MSL for altitude.

Used by `/movement/go_to_gps` and all `/telemetry/gps*` endpoints. `/telemetry/gps` scales raw MAVLink ints to floats (lat/lon ÷ 1e7, alt ÷ 1000, velocity ÷ 100) — see `/home/fleury/gradys/major_projects/uav_api/.claude/docs/specification.md` — gives the full response shape.

`relative_alt` in the GPS response is meters **above HOME**, not above ground level; differences matter when flying over terrain that is not level with the takeoff point.

### 2. NED (local, home-relative)
Units: meters. Axes: **N**orth, **E**ast, **D**own.

**`z` is negative for altitude above HOME.** A drone hovering 20 m above takeoff reports `z = -20`. Every `go_to_ned`/`drive` call that expects to stay airborne must pass a negative `z`. Positive `z` is below the HOME plane (toward the ground or below it).

NED is only defined once HOME is known, which happens at arming. Client scripts call `get_home_ned` **after arm, before takeoff** — the recorded tuple is used with `ned_relative_to_absolute()` (see `/home/fleury/gradys/major_projects/uav_api/.claude/docs/flight-examples-map.md` — helper function reference for the `flight_examples/` client pattern).

### 3. NED velocity
Same axes, but meters/s. Used only by `/movement/travel_at_ned`. Note the body model (`Local_velocity`: `vx`, `vy`, `vz`) differs from the position model (`Local_pos`: `x`, `y`, `z`) — copying a position into a velocity call silently fails.

### GPS ↔ NED conversions

`copter.py` computes a longitude scale as `cos(lat * radians(1))` (see `Copter.longitude_scale`). Internally, NED positions are projected back to GPS with this scale when needed. Clients rarely need to convert by hand; when they do, the helper in gradys-embedded is a reference implementation (see `/home/fleury/gradys/major_projects/gradys-embedded/.claude/docs/mobility-and-telemetry.md` — documents the cartesian↔GPS conversion using a shared origin).

## SITL quirks (`--simulated true`)

**xterm wrapping.** SITL is spawned as `xterm -e sim_vehicle.py ...` (see `api_app.py:78`). The xterm window is the only place SITL stderr/stdout land, so if SITL fails to come up, the API will just time out on its connect retries while the xterm shows the real error. Always check the xterm window first.

**UAV_SITL_TAG process tracking.** The subprocess gets `UAV_SITL_TAG=SITL_ID_<sysid>` in its environment. On shutdown, `psutil` walks the process table looking for that tag and calls `kill()` on every match (xterms are stubborn; `terminate()` often does not work). If you ever see zombie SITL processes, it is because they were spawned without the tag — not the normal path.

**Locations.** `--location` picks a named entry from `~/.config/ardupilot/locations.txt`. `setup.py` seeds this file with `AbraDF` (the default). Add new locations to that file; the format is the ArduPilot standard `name=lat,lon,alt,heading`.

**Speedup caps.** `--speedup` values above ~10× start to introduce MAVLink timing artifacts (dropped heartbeats, stale telemetry). For fast iteration, `5` is usually safe; push higher only when you have verified behavior matches at `1`.

**Sysid agreement.** In simulated mode, SITL is launched with `-I <sysid> --sysid <sysid>` and the API connects with the same `--sysid`. Running two SITLs on the same machine requires distinct sysids **and** distinct `--uav_connection` ports — see `flight_examples/uavs/uav_1.ini` and `uav_2.ini` for a working two-drone setup.

## Real-drone connection modes

`--connection_type` drives `mavutil.mavlink_connection` (see `copter.py:201`):

| Mode | Who initiates | When to use |
|------|---------------|-------------|
| `udpin` | Drone sends to us; API listens on `--uav_connection` | Most common. Telemetry radios, companion computers forwarding MAVLink, SITL. |
| `udpout` | API connects out to drone | When the drone has a static IP and we want to be the initiator (e.g., firewall restrictions). |
| `usb` | Serial device | Tether over USB-serial to a flight controller; `--uav_connection` is the device path (e.g., `/dev/ttyUSB0`). |

The connection is created with `retries=1000`, `autoreconnect=True`, and `dialect="ardupilotmega"`. MAVLink 2 is forced via `os.environ['MAVLINK20'] = '1'`.

Source system/component is hardcoded to `(250, 250)` — a GCS-class ID that ArduPilot treats as a ground station. Do not change this; it affects which parameters ArduPilot will accept from you.

## Heartbeat, streamrate, and the drain loop

After `connect()`, `set_streamrate(self.streamrate)` requests `MAV_DATA_STREAM_ALL` at the configured rate and blocks until a `SYSTEM_TIME` message arrives (proves the link is up). Typical failure mode: timeout after 20 s → `TimeoutException`. Raise `--streamrate` cautiously; high rates over poor radio links drop more messages than they gain.

The async drain loop (`api_app.py:87`) continuously reads MAVLink messages so the pymavlink buffer does not fill and stall new requests. It runs for the entire lifespan; if you see telemetry going stale in a long session, check that the task is still alive. See `/home/fleury/gradys/major_projects/uav_api/.claude/docs/architectural_patterns.md` — documents the lifespan, drain loop, and task-cancellation path on shutdown.

## Common pitfalls

| Symptom | Cause |
|---------|-------|
| `go_to_ned z=20` makes the drone land | Forgot the negative sign — NED `z` is Down. Use `z = -20` for 20 m altitude. |
| `travel_at_ned` request 422 | Used position field names (`x`, `y`, `z`) instead of velocity (`vx`, `vy`, `vz`). |
| `/command/arm` hangs | No GPS lock. Check `GET /telemetry/gps_raw` — `satelites` should be ≥ 6 before arming outdoors; in SITL, needs a few seconds after `sim_vehicle` starts. |
| Set parameter succeeds but drone does not obey | Some ArduPilot params only apply on reboot. SITL can be restarted by killing the process and re-running the API. |
| NED drifts away from reported position | HOME was captured before arming; positions report relative to a stale origin. Always arm → capture home → takeoff. |
| After RTL, telemetry still shows old position | RTL is non-blocking unless `/command/rtl` is used; the polled position updates over several seconds as the drone flies. |

## Related docs

- `/home/fleury/gradys/major_projects/uav_api/.claude/docs/specification.md` — the endpoint contract these conventions apply to.
- `/home/fleury/gradys/major_projects/uav_api/.claude/docs/dev-and-run.md` — how to start the API in simulated or real mode.
- `/home/fleury/gradys/major_projects/uav_api/.claude/docs/architectural_patterns.md` — lifespan, naming conventions, fire-and-forget vs `_wait` endpoint pairs.
