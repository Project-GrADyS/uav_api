# Dev & Run

How to install, run, and debug uav_api locally — in both simulated and real-drone modes.

## Install

```bash
pip install -e .
```

Python 3.10+ is required (see `pyproject.toml`). Dev dependencies (`pytest`, `httpx`, `niquests` for HTTP/3 examples) are listed in `requirements.txt`.

System dependencies (simulated mode only):
- **ArduPilot** cloned at `~/ardupilot` (or any path passed via `--ardupilot_path`). SITL is launched from `Tools/autotest/sim_vehicle.py`.
- **xterm** on `PATH`. The SITL process is spawned inside an `xterm` window so its console output stays visible; the lifespan teardown relies on `UAV_SITL_TAG` to kill the whole subtree on shutdown.
- **tmux** on `PATH`, if you use `/mission/execute-script`.

First-run setup (idempotent, executed from `uav_api/setup.py`) writes:
- `~/.config/ardupilot/locations.txt` with a default `AbraDF` location — used by `--location`.
- `~/uav_scripts/` — default `scripts_path` for the mission router.
- `~/uav_api_certs/` — self-signed certs when `--udp` is set without `--certfile`/`--keyfile`.

## Run — simulated (recommended starting point)

Spawns ArduCopter SITL in an `xterm`, waits for it to come up, then the API connects to it over UDP.

```bash
uav-api --simulated true --ardupilot_path ~/ardupilot --speedup 1 --port 8000 --sysid 1
```

Or via INI file (sections `[api]`, `[simulated]`, `[logs]`):

```bash
uav-api --config flight_examples/uavs/uav_1.ini
```

`--speedup N` multiplies SITL time (use `5` or `10` for fast iteration). `--sysid` must match the target drone's MAVLink system ID; in simulated mode SITL is launched with the same `sysid` so they agree.

## Run — real drone

```bash
# Drone is configured to send MAVLink to us (most common over radio):
uav-api --port 8000 --uav_connection 127.0.0.1:17171 --connection_type udpin --sysid <drone_sysid>

# Or API initiates the connection:
uav-api --uav_connection 192.168.1.50:14550 --connection_type udpout --sysid <drone_sysid>

# USB / telemetry-radio serial:
uav-api --uav_connection /dev/ttyUSB0 --connection_type usb --sysid <drone_sysid>
```

See `/home/fleury/gradys/major_projects/uav_api/.claude/docs/mavlink-and-coordinate-frames.md` — covers the tradeoffs between `udpin` / `udpout` / `usb` and the MAVLink-level gotchas when connecting to real hardware.

## Health checks

Once running:
- Interactive Swagger UI: `http://localhost:<port>/docs` — useful for ad-hoc testing.
- `GET /telemetry/general` — returns `{"info": {...}}` once SITL/drone is connected; used by tests as the readiness probe.
- `GET /telemetry/gps` — confirms GPS fusion is producing a position (lat/lon non-zero) before arming.

## Logs

By default, logs are per-component and written to file + console depending on flags:

| Flag | Effect |
|------|--------|
| `--log_console COPTER API GRADYS_GS` | Print these components' logs to stdout |
| `--debug COPTER API` | Same component names, but at DEBUG level |
| `--log_path /tmp/uav_api.log` | Write all component logs combined to this file |
| `--script_logs ~/uav_logs/` | Redirect `/mission/execute-script` stdout/stderr to timestamped files here |

The component name to log level plumbing lives in `uav_api/log.py`. In `--udp` (Hypercorn) mode, that module also builds Hypercorn's log-config dict.

## Interactive debugging

**SITL xterm** — you can type MAVProxy commands directly into the spawned xterm (e.g., `mode GUIDED`, `status`, `param show SIM_SPEEDUP`). This is often faster than issuing HTTP calls when investigating MAVLink behavior.

**tmux session for scripts** — scripts launched via `/mission/execute-script` run in a tmux session named `api-script`. Attach live:

```bash
tmux attach -t api-script
```

Re-executing the endpoint sends `Ctrl+C` to the session before launching the new script, so the session persists across executions. Detailed behavior lives in `/home/fleury/gradys/major_projects/uav_api/.claude/docs/architectural_patterns.md` — describes the singleton/lifespan patterns, the drain loop, and the fire-and-forget vs blocking movement split.

**MAVProxy parameter inspection** — inside SITL's xterm, `param show <NAME>` and `param set <NAME> <VAL>` let you poke parameters the API does not expose.

## Common failure modes

| Symptom | Likely cause |
|---------|--------------|
| `/telemetry/general` times out on startup (simulated) | `~/ardupilot` path wrong, or `xterm` not on PATH. Check the xterm window — SITL errors print there. |
| Arm endpoint hangs forever | GPS fix not yet acquired (especially on cold start). `GET /telemetry/gps_raw` shows `satelites` count. |
| NED `z` values look inverted | NED is North-East-**Down**. Negative `z` = altitude above HOME. See mavlink-and-coordinate-frames.md — explains the NED sign convention and GPS↔NED translation. |
| `--udp` fails with TLS error | Missing or stale certs in `~/uav_api_certs/`. Delete and rerun; certs are auto-regenerated. |
| Shutdown leaves SITL/xterm running | Should not happen — `UAV_SITL_TAG` kills the tree. If it does, `pkill -f sim_vehicle` is the manual cleanup. |

## Related docs

- `/home/fleury/gradys/major_projects/uav_api/.claude/docs/specification.md` — authoritative HTTP endpoint contract (request/response shapes).
- `/home/fleury/gradys/major_projects/uav_api/.claude/docs/architectural_patterns.md` — lifespan, singleton injection, endpoint pair conventions, naming.
- `/home/fleury/gradys/major_projects/uav_api/.claude/docs/flight-examples-map.md` — index of runnable client scripts under `flight_examples/`.
- `/home/fleury/gradys/major_projects/uav_api/.claude/docs/tests.md` — how the integration suite drives a live SITL instance.
