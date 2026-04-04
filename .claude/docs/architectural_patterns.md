# Architectural Patterns

## Background Processes and Coroutines

The application lifecycle is managed by a FastAPI `@asynccontextmanager` lifespan in `uav_api/api_app.py:57`. It starts and stops the following processes/tasks:

### Always started

**uvicorn HTTP server**
- Launched by `uav_api/run_api.py`
- The lifespan context manages everything below within uvicorn's lifetime

**MAVLink drain loop** (`api_app.py:87`)
- `asyncio.create_task(copter.run_drain_mav_loop())`
- Continuously drains buffered MAVLink messages to prevent connection stalls
- Runs for the entire API lifetime; cancelled on shutdown (`drain_mav_loop.cancel()`)

### Conditional: simulated mode only (`--simulated true`)

**ArduCopter SITL process** (`api_app.py:78-81`)
- Spawns `xterm -e sim_vehicle.py -v ArduCopter ...` as a subprocess
- Tagged with a unique `UAV_SITL_TAG=SITL_ID_<sysid>` environment variable
- On shutdown, all system processes with that env tag are killed via `psutil` (`api_app.py:43-55`)
- Allows clean teardown even if xterm spawned child processes

### Conditional: Gradys GS integration only (`--gradys_gs` is set)

**GS location push coroutine** (`api_app.py:93`)
- `asyncio.create_task(send_location_to_gradys_gs(copter, session, ...))`
- Defined in `uav_api/gradys_gs.py:35` — POSTs GPS position to `http://<gradys_gs>/update-info/` every second
- Uses a shared `aiohttp.ClientSession`; session is closed on shutdown after task cancellation

---

## Singleton Dependency Injection

**Pattern**: `uav_api/router_dependencies.py:5-13`

A single `Copter` instance and a single `args` namespace are held as module-level globals. All routers receive them via FastAPI's `Depends()`:

```python
Depends(get_copter_instance)  # returns the shared Copter
Depends(get_args)             # returns parsed CLI/config args
```

This ensures one MAVLink connection is shared across all endpoints.

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

The CLI `Namespace` is serialized to JSON and stored in the `UAV_ARGS` env var before uvicorn forks. The uvicorn subprocess reads it back via `read_args_from_env()`. This lets the FastAPI app and all routers access config without re-parsing CLI args.

## Naming Conventions in `copter.py`

Method prefixes signal behavior (`uav_api/copter.py`):

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
