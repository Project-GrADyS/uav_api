# UAV API

HTTP REST API for controlling ArduPilot-compatible UAVs (QuadCopters). Supports real drones via MAVLink and simulated drones via ArduPilot SITL.

## Tech Stack
- **Python 3.10+**, FastAPI, Uvicorn (default TCP) / Hypercorn (optional QUIC/UDP via `--udp`), Pydantic v2
- **MAVLink**: pymavlink, MAVProxy
- **Async**: asyncio, aiohttp (background drain loop + GS location push)
- **Process management**: psutil, multiprocessing

## Project Structure
| Path | Purpose |
|------|---------|
| `uav_api/copter.py` | Core vehicle abstraction — all MAVLink logic (~1850 lines) |
| `uav_api/api_app.py` | FastAPI app + lifespan (startup/shutdown of SITL, drain loop, GS task) |
| `uav_api/routers/` | One file per endpoint group: command, movement, telemetry, mission, peripherical |
| `uav_api/classes/` | Pydantic input models: `Gps_pos`, `Local_pos`, `Local_velocity`, `Servo_output` |
| `uav_api/router_dependencies.py` | Singleton `Copter` instance + args via `Depends()` |
| `uav_api/args.py` | CLI arg parsing; config serialized to `UAV_ARGS` env var for app module access |
| `uav_api/gradys_gs.py` | Async loop that POSTs GPS location to Gradys Ground Station every second |
| `uav_api/log.py` | Logger configuration (file + console, per-component); builds Hypercorn log config dict for `--udp` mode |
| `uav_api/setup.py` | Idempotent home-directory setup (log dirs, scripts dir, ardupilot config) |
| `flight_examples/` | Example client scripts — each in its own subdirectory, sharing `flight_helpers.py` |
| `flight_examples/flight_helpers.py` | Shared helper module (session, send_command, home capture, graceful shutdown) |
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
| `tests/command_test.py` | Command router endpoints (arm, takeoff, land, RTL, speeds, set_home) |
| `tests/movement_test.py` | Movement router endpoints (go_to_ned, drive, go_to_gps, travel_at_ned, stop) |
| `tests/telemetry_test.py` | All telemetry endpoints (general, gps, ned, compass, battery, etc.) |
| `tests/mission_test.py` | Mission script management (upload, list, execute, clear) |
| `tests/peripherical_test.py` | Peripherical endpoints (take_photo validation, servo_output) |

> All tests are **integration tests** that run against a live SITL instance. A session-scoped fixture in `conftest.py` spawns the API with `--simulated true`, arms and takes off before yielding to tests. Requires ArduPilot installed and `xterm` on PATH.

**Adding new tests:** create a new `tests/<router>_test.py`, import helpers from `conftest` (`get`, `post`, `delete`, `wait_for_altitude`), and write tests that call the live API over HTTP. No mocks or `TestClient` — always test against the real SITL server. See `.claude/docs/tests.md` for full details.

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

### UDP/QUIC mode (`--udp`)
| Argument | Default | Description |
|----------|---------|-------------|
| `--udp` | `False` | Use Hypercorn with QUIC/HTTP3 (UDP) instead of Uvicorn (TCP) |
| `--certfile` | None | Path to TLS certificate PEM. Auto-generated self-signed cert if omitted. |
| `--keyfile` | None | Path to TLS private key PEM. Auto-generated if omitted. |

> QUIC requires TLS. When `--udp` is set without `--certfile`/`--keyfile`, self-signed certs are auto-generated in `~/uav_api_certs/`.

## Key Entry Points
- CLI entry: `uav_api/run_api.py` — starts uvicorn (default) or hypercorn (`--udp`)
- App definition: `uav_api/api_app.py:57` (lifespan) and `:126` (app + router registration)
- Copter class: `uav_api/copter.py:110`
- Dependency injection: `uav_api/router_dependencies.py:8`

## When to open which doc

Each `.claude/docs/*.md` is scoped tightly. Open only the ones that match your task.

- `→ .claude/docs/specification.md` — **authoritative HTTP contract** for the whole GrADyS ecosystem (gradys-embedded and gradys-gs consume this spec). Endpoint paths, query/body schemas, response envelopes. Open when adding or changing any endpoint.
- `→ .claude/docs/architectural_patterns.md` — lifespan, singleton `Copter` injection, drain loop, endpoint pair (fire-and-forget vs `_wait`) conventions, `copter.py` method naming (`send_/wait_/run_/get_/set_`), uniform response envelope, tmux script execution. Open when changing app structure or writing a new router.
- `→ .claude/docs/dev-and-run.md` — install steps (incl. ArduPilot/xterm/tmux), simulated and real-drone run commands, INI config file use, log flags, SITL/tmux interactive debugging, common failure modes. Open when setting up a machine or debugging a startup problem.
- `→ .claude/docs/flight-examples-map.md` — index of every script under `flight_examples/`: flight pattern, endpoints exercised, shared helper functions, rules for writing new examples. Open when adding or porting a client script.
- `→ .claude/docs/mavlink-and-coordinate-frames.md` — GPS vs NED vs NED-velocity, why `z` is negative, SITL xterm/UAV_SITL_TAG quirks, `udpin`/`udpout`/`usb` tradeoffs, heartbeat/streamrate/drain loop interactions, common MAVLink pitfalls. Open when touching movement/telemetry logic or debugging a connection/position issue.
- `→ .claude/docs/tests.md` — session-scoped SITL fixture, `conftest` helpers (`get`/`post`/`delete`/`wait_for_altitude`), per-file coverage table, rules for adding new integration tests. Open when writing or modifying a test.

## Consumers of this API (cross-project)

`specification.md` is the ecosystem HTTP contract. The following sibling projects depend on it — update the spec first, then the consumers.

- `→ /home/fleury/gradys/major_projects/gradys-embedded/` — runs simulator protocols on real drones; each drone runs its own uav_api process and gradys-embedded calls `/command/*`, `/movement/*`, `/telemetry/gps` over localhost.
- `→ /home/fleury/gradys/major_projects/gradys-gs/` — Django mission-control web UI; dispatches `/command/*`, `/telemetry/*`, `/mission/*` from browser actions.
- `→ /home/fleury/gradys/major_projects/gradys-sim-nextgen/` — reaches uav_api indirectly via gradys-embedded during real-world deployment.
