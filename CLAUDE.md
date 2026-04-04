# UAV API

HTTP REST API for controlling ArduPilot-compatible UAVs (QuadCopters). Supports real drones via MAVLink and simulated drones via ArduPilot SITL.

## Tech Stack
- **Python 3.10+**, FastAPI, Uvicorn, Pydantic v2
- **MAVLink**: pymavlink, MAVProxy
- **Async**: asyncio, aiohttp (background drain loop + GS location push)
- **Process management**: psutil, subprocess

## Project Structure
| Path | Purpose |
|------|---------|
| `uav_api/copter.py` | Core vehicle abstraction — all MAVLink logic (~1850 lines) |
| `uav_api/api_app.py` | FastAPI app + lifespan (startup/shutdown of SITL, drain loop, GS task) |
| `uav_api/routers/` | One file per endpoint group: command, movement, telemetry |
| `uav_api/classes/` | Pydantic input models: `Gps_pos`, `Local_pos`, `Local_velocity` |
| `uav_api/router_dependencies.py` | Singleton `Copter` instance + args via `Depends()` |
| `uav_api/args.py` | CLI arg parsing; config serialized to `UAV_ARGS` env var for subprocess access |
| `uav_api/gradys_gs.py` | Async loop that POSTs GPS location to Gradys Ground Station every second |
| `uav_api/log.py` | Logger configuration (file + console, per-component) |
| `uav_api/setup.py` | Idempotent home-directory setup (log dirs, scripts dir, ardupilot config) |
| `flight_examples/` | Example client scripts (`takeoff_land.py`, `ned_square.py`, `follower.py`) |
| `flight_examples/uavs/` | INI config files for simulated UAVs |

## Essential Commands

**Install (dev mode):**
```bash
pip install -e .
```

**Run the API (simulated — recommended starting point):**
```bash
# Simulated (spawns ArduCopter SITL in xterm)
uav-api --simulated true --ardupilot_path ~/ardupilot --speedup 1 --port 8000 --sysid 1

# Or via INI config file
uav-api --config flight_examples/uavs/uav_1.ini
```

**Run the API (real drone):**
```bash
uav-api --port 8000 --uav_connection 127.0.0.1:17171 --connection_type udpin --sysid 1
```

**Interactive API docs (Swagger UI):** `http://localhost:<port>/docs`

## Testing

**Framework:** pytest + FastAPI `TestClient` (backed by httpx)

**Install test dependencies:**
```bash
pip install pytest httpx
```

**Run the tests:**
```bash
pytest tests/ -v
```

**Test files:**
| File | Covers |
|------|--------|
| `tests/movement_test.py` | Movement router endpoints (integration test — requires SITL) |

> `movement_test.py` is an integration test that runs against a real SITL instance. It uses a session-scoped fixture to start the API with `--simulated true`, so it is slower than unit tests and requires ArduPilot installed.

**How tests are isolated:**
- Each test gets a fresh temporary directory (`pytest`'s `tmp_path` fixture) for scripts and logs — no real `~/uav_scripts` is touched.
- The `get_args` FastAPI dependency is overridden per test via `app.dependency_overrides`, injecting a controlled `argparse.Namespace`.
- `subprocess.run` (tmux calls) is patched with `unittest.mock.patch` so no real tmux session is created.

**Adding new tests:** create a new `tests/<router>_test.py`, build a `TestClient` with `app.dependency_overrides[get_args] = lambda: <your_namespace>`, and use `tmp_path` for any filesystem isolation needed.

## CLI Arguments
All arguments defined in `uav_api/args.py`. Can also be provided via INI config file with `--config <path>`. Config file values are overridden by CLI args.

### General (both modes)
| Argument | Default | Description |
|----------|---------|-------------|
| `--config` | None | Path to INI config file (sections: `[api]`, `[simulated]`, `[logs]`) |
| `--port` | 8000 | HTTP port the API listens on |
| `--sysid` | 10 | MAVLink system ID of the target vehicle; must match the drone's SYSID param |
| `--uav_connection` | `127.0.0.1:17171` | MAVLink address — `host:port` for UDP, or serial device path for USB |
| `--gradys_gs` | None | `host:port` of Gradys GS — when set, API pushes GPS location every second |
| `--scripts_path` | `~/uav_scripts` | Where `/mission/upload-script` saves files and `/mission/execute-script` looks for them |
| `--python_path` | `python3` | Python binary invoked when running uploaded `.py` scripts |
| `--log_console` | `[]` | Space-separated list of components to print logs: `COPTER` `API` `GRADYS_GS` |
| `--log_path` | None | File path to write all component logs combined |
| `--debug` | `[]` | Same component names as `--log_console` but at DEBUG verbosity |
| `--script_logs` | None | Directory where script stdout/stderr are saved as timestamped `.log` files |

### Real drone only
| Argument | Default | Description |
|----------|---------|-------------|
| `--connection_type` | `udpin` | `udpin` = API listens (drone connects to us); `udpout` = API connects to drone; `usb` = serial |

### Simulated mode only (`--simulated true`)
| Argument | Default | Description |
|----------|---------|-------------|
| `--ardupilot_path` | `~/ardupilot` | Path to local ArduPilot repo — SITL is launched from `Tools/autotest/sim_vehicle.py` |
| `--location` | `AbraDF` | Named home position for SITL (registered in `~/.config/ardupilot/locations.txt`) |
| `--speedup` | 1 | SITL simulation time multiplier (e.g., `5` = 5× faster than real time) |
| `--gs_connection` | `[]` | Extra `host:port` addresses SITL streams telemetry to (e.g., Mission Planner) |

> In simulated mode, SITL binds the address set by `--uav_connection`. The API then connects to it (default `udpin`).

## Key Entry Points
- CLI entry: `uav_api/run_api.py` → starts uvicorn
- App definition: `uav_api/api_app.py:57` (lifespan) and `:126` (app + router registration)
- Copter class: `uav_api/copter.py:110`
- Dependency injection: `uav_api/router_dependencies.py:8`

## Additional Documentation
- `.claude/docs/architectural_patterns.md` — design decisions, patterns, conventions
- `.claude/docs/specification.md` — full API endpoint spec (inputs, outputs, behavior)
