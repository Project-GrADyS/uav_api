# Architectural Patterns

## Background Processes and Coroutines

The application lifecycle is managed by a FastAPI `@asynccontextmanager` lifespan in `uav_api/api_app.py:60`. It starts and stops the following processes/tasks:

### Always started

**uvicorn HTTP server**
- Launched by `uav_api/run_api.py`
- The lifespan context manages everything below within uvicorn's lifetime

**MAVLink drain loop** (`api_app.py:95`)
- `asyncio.create_task(vehicle.run_drain_mav_loop())` where `vehicle` is the active singleton (Copter or Plane, picked by `--vehicle`)
- Continuously drains buffered MAVLink messages to prevent connection stalls
- Runs for the entire API lifetime; cancelled on shutdown (`drain_mav_loop.cancel()`)

### Conditional: simulated mode only (`--simulated true`)

**ArduPilot SITL process** (`api_app.py:81-85`)
- Spawns `xterm -e sim_vehicle.py -v {ArduCopter|ArduPlane} ...` as a subprocess; the vehicle binary is chosen by `args.vehicle` (line 81: `ardupilot_vehicle = "ArduPlane" if args.vehicle == "plane" else "ArduCopter"`)
- Tagged with a unique `UAV_SITL_TAG=SITL_ID_<sysid>` environment variable
- On shutdown, all system processes with that env tag are killed via `psutil` (`api_app.py:46-58`)
- Allows clean teardown even if xterm spawned child processes

### Conditional: Gradys GS integration only (`--gradys_gs` is set)

**GS location push coroutine** (`api_app.py:101`)
- `asyncio.create_task(send_location_to_gradys_gs(vehicle, session, ...))`
- Defined in `uav_api/gradys_gs.py:35` — POSTs GPS position to `http://<gradys_gs>/update-info/` every second. Duck-types on `.get_gps_info()` and `.target_system`, which both `Copter` and `Plane` expose.
- Uses a shared `aiohttp.ClientSession`; session is closed on shutdown after task cancellation

---

## Singleton Dependency Injection

**Pattern**: `uav_api/routers/router_dependencies.py`

Module-level globals hold one `Copter`, one `Plane`, and one `args` namespace. Routers pick the right vehicle via FastAPI's `Depends()`:

```python
Depends(get_copter_instance)  # shared Copter — used by copter_* routers
Depends(get_plane_instance)   # shared Plane  — used by plane_*  routers
Depends(get_args)             # parsed CLI/config args
```

Only one vehicle singleton is instantiated per process (in the lifespan, conditional on `args.vehicle`), so there is one MAVLink connection regardless of which routers are mounted. The unused `get_*_instance` is never called and stays `None`.

## Vehicle Selection (`--vehicle`)

**Pattern**: `uav_api/api_app.py:142-150`

`--vehicle {copter|plane}` (default `copter`, defined in `args.py:parse_mode`) controls which router set is registered:

```python
if args.vehicle == "plane":
    app.include_router(plane_command_router)
    app.include_router(plane_movement_router)
    app.include_router(plane_telemetry_router)
else:
    app.include_router(command_router)      # alias for copter_command_router
    app.include_router(telemetry_router)
    app.include_router(movement_router)
    app.include_router(mission_router)
    app.include_router(peripherical_router)
```

The router sets share URL prefixes (`/command`, `/movement`, `/telemetry`) so HTTP consumers don't see a vehicle-type difference at the path level. Plane mode has no `mission` or `peripherical` routers and a smaller movement surface — see `plane-support.md`.

## Endpoint Pairs (Fire-and-Forget vs Blocking)

**Pattern**: `uav_api/routers/movement.py`

Movement commands come in pairs. The blocking (`_wait`) variant issues the command then polls for arrival:

| Fire-and-forget | Blocking |
|-----------------|---------|
| `POST /go_to_gps/` | `POST /go_to_gps_wait` (calls `wait_location`, timeout=60s) |
| `POST /go_to_ned` | `POST /go_to_ned_wait` (calls `wait_ned_position`) |
| `POST /drive` | `POST /drive_wait` (computes target from current pos + offset) |
| `POST /travel_at_ned` | *(none — velocity command, not position-based)* |

> All movement POST endpoints accept an optional `look_at_target: bool` field (default `false`). When `true`, the copter yaws to face the direction of travel. This is implemented in the Pydantic input models (`Gps_pos`, `Local_pos`, `Local_velocity`) in `uav_api/classes/movement.py`.

## Configuration Propagation via Environment Variable

**Pattern**: `uav_api/args.py:17-18`

The CLI `Namespace` is serialized to JSON and stored in the `UAV_ARGS` env var before the ASGI server starts. Since both uvicorn and hypercorn are invoked programmatically with the app as an import path string, the app module reads the env var back via `read_args_from_env()` at import time. This lets the FastAPI app and all routers access config without re-parsing CLI args.

## Naming Conventions in Vehicle Classes

Method prefixes signal behavior. The convention is shared by `uav_api/vehicles/copter.py` and `uav_api/vehicles/plane.py`:

| Prefix | Behavior |
|--------|---------|
| `wait_*` | Blocking — polls until condition met or timeout raised |
| `send_*` | Fire MAVLink message, return immediately |
| `run_*` | Send command and wait for completion |
| `get_*` | Read and return current state/data |
| `set_*` | Configure a parameter or state |

## Uniform Response Envelope

All routers return a consistent JSON structure:

```json
{"device": "uav", "id": "<sysid>", "result": "..."}
```

Telemetry endpoints add an `"info": {...}` field. All errors raise `HTTPException(status_code=500)` with a descriptive `detail` string.

## Script Execution via tmux

**Pattern**: `uav_api/routers/mission.py:72-94`

`POST /mission/execute-script/` runs uploaded scripts in a persistent tmux session named `"api-script"`:
- If the session already exists, sends `Ctrl+C` to stop any running script before re-executing
- stdout/stderr are redirected to timestamped log files in `script_logs/`
- Allows attaching to the session with `tmux attach -t api-script` for live debugging
