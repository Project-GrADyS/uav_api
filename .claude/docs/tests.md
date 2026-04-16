# Integration Tests

## Architecture

All tests are **integration tests** that run against a live ArduPilot SITL (Software-In-The-Loop) instance. There are no unit tests or mocked dependencies — every request hits a real running API server backed by a simulated drone.

The test process spawns the full API server in a child process via `uav_api/run_api.py:spawn_with_args()`, which calls `multiprocessing.Process(target=run_with_args)`. Tests communicate with the server over HTTP using the `requests` library, exactly as a real client would.

```
pytest process                    child process
┌──────────────┐   HTTP/REST    ┌──────────────────────┐
│  test runner  │ ─────────────>│  FastAPI (uvicorn)    │
│  (requests)   │ <─────────────│  + Copter + SITL      │
└──────────────┘                └──────────────────────┘
```

## Stack

| Component | Role |
|-----------|------|
| pytest | Test runner and fixture management |
| requests | HTTP client for hitting the live API |
| multiprocessing | Spawns the API server in a background process |
| ArduPilot SITL | Simulated drone (launched in xterm by the API lifespan) |
| `spawn_with_args()` | Entry point in `uav_api/run_api.py:41` — wraps `run_with_args` in a `Process` |

## Test Infrastructure

### Session-scoped fixture (`tests/conftest.py:68`)

A single `api_server` fixture (scope=`session`, autouse=`True`) manages the entire server lifecycle:

1. **Spawn** — calls `spawn_with_args()` with `--simulated true`, `--port 8001`, `--speedup 5`, `--sysid 1`
2. **Wait** — polls `GET /telemetry/general` until the server responds (90s timeout)
3. **Arm + takeoff** — arms the drone and takes off to 15m altitude, waits for stabilization
4. **Yield** — all tests run against this single server instance
5. **Teardown** — terminates the process; falls back to `kill()` if it does not exit within 15s

Because the fixture is session-scoped, SITL starts once and is shared across all test files. Tests that change flight state (land, RTL) are responsible for re-arming and returning the drone to hover before the next test.

### HTTP helpers (`tests/conftest.py:25-34`)

Thin wrappers around `requests` with a 10-second timeout and the base URL (`http://localhost:8001`) baked in:

- `get(path, **kwargs)`
- `post(path, json=None, **kwargs)`
- `delete(path, **kwargs)`

### Wait helpers (`tests/conftest.py:39-63`)

- `wait_for_api(timeout=90)` — polls `/telemetry/general` every 2s until 200 or timeout
- `wait_for_altitude(target_alt, tolerance=2, timeout=30)` — polls `/telemetry/ned` every 1s until NED z stabilizes near the target

## Test Files

| File | Router | Tests | What it covers |
|------|--------|-------|----------------|
| `tests/command_test.py` | `/command` | 7 | Speed setters, sim speedup, set home, land + re-arm, RTL + re-arm |
| `tests/movement_test.py` | `/movement` | 6 | `travel_at_ned`, `go_to_ned`, `drive`, `go_to_gps`, `stop` (each with variants) |
| `tests/telemetry_test.py` | `/telemetry` | 10 | All 10 telemetry endpoints — general, gps, gps_raw, ned, compass, sys_status, sensor_status, battery_info, error_info, home_info |
| `tests/mission_test.py` | `/mission` | 8 | Upload (.py, .sh, invalid extension), list, execute (existing + missing), clear, list after clear |
| `tests/peripherical_test.py` | `/peripherical` | 5 | `take_photo` input validation (disallowed command, invalid resolution, missing param); `servo_output` (success, missing params) |

## Endpoint Coverage

| Router | Endpoints | Tested | Not tested |
|--------|-----------|--------|------------|
| command | 10 | 10 | — |
| movement | 11 | 5 | `go_to_gps_wait`, `go_to_ned_wait`, `drive_wait`, `set_heading`, `set_yaw_rate`, `resume` |
| telemetry | 10 | 10 | — |
| mission | 4 | 4 | — |
| peripherical | 2 | 2 | — |
| **Total** | **37** | **31** | **6** |

The untested movement endpoints are the `_wait` variants (blocking versions of tested async endpoints), heading/yaw-rate setters, and `resume`.

## Test Execution

### Prerequisites

- ArduPilot installed at `~/ardupilot` (or adjust `--ardupilot_path` in `conftest.py`)
- `xterm` available on PATH (SITL launches in an xterm window)
- Python packages: `pytest`, `requests`

### Commands

```bash
# Run all tests
pytest tests/ -v -s --timeout=120

# Run a single router's tests
pytest tests/telemetry_test.py -v -s --timeout=120

# Install test dependencies
pip install pytest requests
```

- `-v` — verbose test names
- `-s` — show stdout (useful for debugging wait timeouts)
- `--timeout=120` — per-test timeout via pytest-timeout (recommended since SITL operations can hang)

### Timing

A full test run takes 2-4 minutes depending on host speed. Most of that time is SITL startup (~60s) and flight operations (land/takeoff cycles in command tests). Telemetry and mission tests are fast since they only read state or manage files.

## Adding New Tests

1. Create `tests/<router>_test.py`
2. Import helpers from `conftest`: `from conftest import get, post, delete, wait_for_altitude`
3. Write test classes/methods that call the live API via the helpers
4. If the test changes flight state (land, mode change), restore the drone to armed hover at 15m before returning
5. No mocks, no TestClient, no dependency overrides — always test against the real SITL server
