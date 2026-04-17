# Flight Examples Map

Client scripts under `flight_examples/` that drive a running uav_api over HTTP. Each example is a self-contained `python <file>` invocation; all share a helper module (`flight_helpers.py`). Use this map to find the closest-matching example before writing a new one.

Run a uav_api server first (see `/home/fleury/gradys/major_projects/uav_api/.claude/docs/dev-and-run.md` — covers install, run commands, and debugging).

## Shared helper: `flight_examples/flight_helpers.py`

| Function | Purpose |
|---|---|
| `add_common_args(parser)` | Adds `--url`, `--altitude`, `--h3`, `--certfile` to an `argparse.ArgumentParser` |
| `get_base_url(args)` | Returns `http://` or `https://` URL depending on `--h3` |
| `create_session(args)` | Returns a `requests.Session` or `niquests.Session` (HTTP/3) |
| `send_command(session, base_url, endpoint, params=None, method="GET")` | Fires one HTTP call; `sys.exit(1)` on non-200 |
| `euclidean_distance(p1, p2)` | 3D distance between `(x, y, z)` tuples |
| `wait_for_arrival(session, base_url, target, tolerance=1.0, timeout=120)` | Polls `/telemetry/ned` until within tolerance of absolute NED target |
| `get_home_ned(session, base_url)` | Returns current NED as a `(x, y, z)` tuple — **call after arm, before takeoff** |
| `get_home_gps(session, base_url)` | Same, but GPS `(lat, lon, alt)` |
| `ned_relative_to_absolute(relative, home)` | Adds home offsets to a relative NED tuple |
| `setup_graceful_shutdown(session, base_url)` | Installs a `SIGINT` handler that sends `/command/rtl` before exit |

All examples follow the same shape: parse args → build session → install `SIGINT` handler → arm → capture home → takeoff → run pattern → land/RTL.

## Examples

| Directory | Entry | Flight pattern | Endpoints exercised |
|---|---|---|---|
| `takeoff_land/` | `takeoff_land.py` | Arm → takeoff → land. Simplest example; good smoke test. | `/command/arm`, `/command/takeoff`, `/command/land` |
| `ned_square/` | `ned_square.py` | Flies a square by firing `go_to_ned` at each corner with fixed sleeps between moves. | `/command/arm`, `/command/takeoff`, `/movement/go_to_ned`, `/command/land` |
| `ned_square_polling/` | `ned_square_polling.py` | Same square, but uses `wait_for_arrival` to poll `/telemetry/ned` instead of sleeping — prefer this pattern when timing matters. | adds `/telemetry/ned` polling to the ned_square set |
| `go_to_polygon/` | `go_to_polygon.py` | N-sided polygon via absolute-position moves (`go_to_ned`). `--sides` accepts a list; `--radius`, `--height` configure shape. | `/movement/go_to_ned` |
| `drive_polygon/` | `drive_polygon.py` | Same polygon, but built from relative-offset moves (`/movement/drive` instead of `go_to_ned`). Useful reference for the `drive` vs `go_to_ned` tradeoff. | `/movement/drive` |
| `gps_follower/` | `gps_follower.py` | Second drone follows a leader. Polls the leader's `/telemetry/gps`, applies `--offset-north/east/alt`, and issues `/movement/go_to_gps` on itself. Requires **two** uav_api instances. | `/telemetry/gps` on leader; `/movement/go_to_gps` on follower |
| `delivery/` | `delivery_simulation.py` | Multi-leg mission: take off → pickup location → land → take off → delivery → land → RTL. Uses home-relative NED and `wait_for_arrival`. Most complete example. | `/command/arm`, `/command/takeoff`, `/command/land`, `/movement/go_to_ned`, `/telemetry/ned` |

## Simulated UAV config files

`flight_examples/uavs/uav_1.ini` and `uav_2.ini` are ready-to-use INI configs for running two uav_api instances side-by-side (different ports, different sysid). Passed via `uav-api --config <path>`. Required when running `gps_follower` (one leader + one follower).

## Adding a new example

1. Create `flight_examples/<name>/<name>.py`.
2. Add the `sys.path.insert(0, ...)` trick at the top to import `flight_helpers` from the parent dir (every existing example does this).
3. Call `add_common_args(parser)` first so `--url`, `--altitude`, `--h3` work consistently.
4. Use `setup_graceful_shutdown` so `Ctrl+C` triggers RTL instead of leaving the drone hovering.
5. Capture home with `get_home_ned` / `get_home_gps` **after `/command/arm` and before `/command/takeoff`** — the NED origin is set at arming, so calling before arming returns stale data and calling after takeoff loses the ground reference.
6. Prefer `wait_for_arrival` over `time.sleep` when the next step depends on position.

Consult the authoritative request/response shapes in `/home/fleury/gradys/major_projects/uav_api/.claude/docs/specification.md` — full endpoint contract including NED conventions and the fire-and-forget vs `_wait` variants.
