# Plane Support (beta)

> ⚠️ **Beta.** Plane support is functional for the common operator path (arm → takeoff → goto → land/RTL) but is not yet integration-tested and several copter endpoints have no plane counterpart. Treat as preview.

ArduPlane / QuadPlane support runs side-by-side with the original Copter path. The selection is made once at startup via `--vehicle {copter|plane}` (default `copter`) and decides which routers register and which ArduPilot SITL spawns. Consumer URLs (`/command/*`, `/movement/*`, `/telemetry/*`) keep the same prefixes regardless, so `gradys-embedded` and `gradys-gs` do not need to know which vehicle is on the other side.

For copter (default) endpoint contracts see `specification.md`. The shared lifespan / DI / drain-loop architecture is in `architectural_patterns.md`.

---

## Status — what works / what does not

| Area | State |
|------|-------|
| Arm / disarm (`/command/arm`, `/command/disarm`) | Works |
| Takeoff (`/command/takeoff?alt`) — fixed-wing | Works. Uses TAKEOFF mode under the hood; switches back to GUIDED after altitude is reached. |
| Takeoff — VTOL (`vtol=true`) | Sends `MAV_CMD_NAV_VTOL_TAKEOFF` (QuadPlane). Not field-tested by this codebase. |
| GUIDED goto (`POST /movement/go_to_gps[_wait]`) | Works. Uses `MAV_CMD_DO_REPOSITION`. |
| Land (`/command/land`) | Switches to LAND mode. **Assumes a runway-aligned approach is already arranged** — naïve callers will not get a controlled landing. |
| Land-at (`POST /movement/land_at`) | Composite: DO_REPOSITION → LAND. Same caveat as `/command/land`. |
| RTL (`/command/rtl`) | Plane is near home on return. **Does not wait for disarm** — fixed-wing typically loiters at home unless a landing is in the mission. |
| Stop (`GET /movement/stop`) | Closest analog to "halt": enters LOITER. Fixed-wing can't truly stop. |
| Telemetry (`/telemetry/general,gps,battery_info,sensor_status,error_info,home_info`) | Works. Same response envelope as copter. |
| Mission router (`/mission/*`) | **Not registered in plane mode** — 404. |
| Peripherical router (`/peripherical/*`) | **Not registered in plane mode** — 404. |
| `/command/takeoff` `pitch_deg` query param | Currently a no-op for fixed-wing. ArduPlane drives climb attitude from `TKOFF_LVL_PITCH` / `PTCH_LIM_MAX_DEG` params, not from the NAV_TAKEOFF p1 value. Kept in the signature for API stability. |
| `/movement/go_to_ned`, `/drive`, `/travel_at_ned`, `/set_heading`, `/set_yaw_rate`, `/resume` | **Not implemented** for plane mode. |
| `Plane.set_attitude()` (SET_ATTITUDE_TARGET) | Implemented in the class; no router exposes it yet. |
| Integration tests | None — `tests/` runs Copter only. |

---

## Where the code lives

| Path | Role |
|------|------|
| `uav_api/vehicles/plane.py` | `class Plane` — MAVLink wrapper. Logger named `"PLANE"`. |
| `uav_api/vehicles/copter.py` | `class Copter` — parallel module; no shared base class (deliberate). |
| `uav_api/routers/plane_command.py` | `arm`, `disarm`, `takeoff`, `land`, `rtl`, `set_home`. |
| `uav_api/routers/plane_movement.py` | `go_to_gps`, `go_to_gps_wait`, `land_at`, `stop`. |
| `uav_api/routers/plane_telemetry.py` | `general`, `gps`, `battery_info`, `sensor_status`, `error_info`, `home_info`. |
| `uav_api/routers/router_dependencies.py` | `get_copter_instance` and `get_plane_instance` lazy singletons. |
| `uav_api/classes/attitude.py` | `Attitude_target` Pydantic model (unused by routers today; reserved for future `/movement/set_attitude`). |

---

## How vehicle selection works at runtime

`args.py:parse_mode` defines `--vehicle` with `choices=['copter', 'plane']`, default `copter`. The value is serialised into `UAV_ARGS` env var and read back by `api_app.py` at import time.

Inside `lifespan.py:lifespan`:

1. **SITL spawn** (`start_sitl` in `lifespan.py:85`) — `ardupilot_vehicle = "ArduPlane" if args.vehicle == "plane" else "ArduCopter"`, then `xterm -e sim_vehicle.py -v {ardupilot_vehicle} -I {sysid} …`.
2. **Singleton selection** (`lifespan.py:147-150`):
   ```python
   if args.vehicle == "plane":
       vehicle = get_plane_instance(args.sysid, conn)
   else:
       vehicle = get_copter_instance(args.sysid, conn)
   ```
3. **Drain loop + Gradys GS task** receive `vehicle` and duck-type on `.get_gps_info()` / `.target_system`, which both classes expose.

In `api_app.py` (around line 44):

```python
if args.vehicle == "plane":
    app.include_router(plane_command_router)
    app.include_router(plane_movement_router)
    app.include_router(plane_telemetry_router)
else:
    app.include_router(command_router)
    app.include_router(telemetry_router)
    app.include_router(movement_router)
    app.include_router(mission_router)
    app.include_router(peripherical_router)
```

Routers are mutually exclusive — only the matching set is mounted. This is why `/mission/*` returns 404 in plane mode.

---

## Plane endpoint reference

All endpoints share the standard envelope `{"device": "uav", "id": "<sysid>", "result": "...", "info"?: {...}}` and return HTTP 500 with a `detail` string on failure.

### `/command`

| Method | Path | Query / body | Notes |
|--------|------|--------------|-------|
| GET | `/command/arm` | — | Switches to GUIDED, waits ready-to-arm, arms. |
| GET | `/command/disarm` | — | |
| GET | `/command/takeoff` | `alt: float`, `pitch_deg: float = 15`, `vtol: bool = False` | Fixed-wing: sets `TKOFF_ALT`, enters TAKEOFF mode, waits for altitude, returns to GUIDED. VTOL: sends `MAV_CMD_NAV_VTOL_TAKEOFF`. `pitch_deg` is currently informational for fixed-wing. Default timeout 120 s. |
| GET | `/command/land` | — | LAND mode. Requires a runway approach pre-arranged. |
| GET | `/command/rtl` | — | Switches to RTL; returns when plane is near home (does **not** wait for disarm). |
| GET | `/command/set_home` | — | Sets HOME to current position. |

### `/movement`

| Method | Path | Body | Notes |
|--------|------|------|-------|
| POST | `/movement/go_to_gps` | `Gps_pos` (`lat`, `long`, `alt`) | Fire-and-forget `MAV_CMD_DO_REPOSITION`. `look_at_target` field from the model is currently ignored. |
| POST | `/movement/go_to_gps_wait` | `Gps_pos` | Same + blocks via `wait_location` (default 180 s). |
| POST | `/movement/land_at` | `Gps_pos` | Composite: DO_REPOSITION to the target, then `change_mode("LAND")`. |
| GET | `/movement/stop` | — | Enters LOITER at current position. |

### `/telemetry`

All GET, no body. `info` field shape matches `specification.md` for the corresponding copter endpoints — same scaling (`÷1e7` for lat/lon, `÷1000` for alt, `÷100` for velocity and heading).

| Path | Source MAVLink message |
|------|------------------------|
| `/telemetry/general` | `VFR_HUD` — `airspeed`, `groundspeed`, `heading`, `throttle`, `alt`. |
| `/telemetry/gps` | `GLOBAL_POSITION_INT` — position (`lat`/`lon`/`alt`/`relative_alt`), velocity (`vx`/`vy`/`vz`), `heading`. |
| `/telemetry/battery_info` | `SYS_STATUS` — battery voltage, current, remaining. |
| `/telemetry/sensor_status` | `SYS_STATUS` — parsed sensor health flags. |
| `/telemetry/error_info` | `SYS_STATUS` — comm/autopilot error counters. |
| `/telemetry/home_info` | `HOME_POSITION` — `lat`, `lon`, `altitude`, NED `x`/`y`/`z`. |

---

## Behavioural differences vs Copter

| Topic | Copter | Plane |
|-------|--------|-------|
| Takeoff primitive | `MAV_CMD_NAV_TAKEOFF` in GUIDED | TAKEOFF mode + `TKOFF_ALT` (ArduPlane rejects NAV_TAKEOFF in GUIDED) |
| Land | LAND mode lands at current position | LAND mode follows pre-arranged runway approach; not "land here" |
| RTL completion | Waits for disarm at home | Returns when near home — plane loiters at home unless mission has a landing |
| Stop | `MAV_CMD_DO_PAUSE_CONTINUE` (holds in place) | LOITER mode (orbits — fixed-wing can't halt) |
| Goto primitive | `SET_POSITION_TARGET_GLOBAL_INT` | `MAV_CMD_DO_REPOSITION` (COMMAND_INT) |
| Logger name | `"COPTER"` | `"PLANE"` |
| SITL binary | `sim_vehicle.py -v ArduCopter` | `sim_vehicle.py -v ArduPlane` |

---

## Logging

The CLI tokens `VEHICLE` (in `--log_console` / `--debug`) route to the active vehicle's logger, which is dispatched in `log.py:113-117`. The formatter is `[%(name)s-<sysid>] LEVEL - msg`, so the prefix you see in the console is `[COPTER-<sysid>]` or `[PLANE-<sysid>]` depending on `--vehicle`. The flag is vehicle-agnostic; the printed prefix is not.

---

## Cross-references

- `specification.md` — full copter endpoint contract.
- `architectural_patterns.md` — lifespan, singleton DI, drain loop, response envelope.
- `mavlink-and-coordinate-frames.md` — MAVLink-level gotchas (mostly copter examples but applies to plane).
