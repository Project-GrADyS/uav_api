# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.1] - 2026-09-27

### Added
- `uav-api setup-sitl`: one command that installs ArduPilot SITL. It clones
  ArduPilot (or reuses an existing checkout), runs the Debian/Ubuntu
  prerequisites script, builds the copter/plane SITL binaries, adds
  `Tools/autotest` to `PATH` in the shell rc, and registers uav_api's SITL
  locations. Every step can be re-run safely; `--skip_prereqs`, `--skip_build`
  and `--no_path` opt out of individual steps.
- `uav-api start`: the API launcher is now a subcommand.
- `--mavlink_streamrate` (default `5`, Hz; also `[api] mavlink_streamrate` in
  config files) exposes the `MAV_DATA_STREAM_ALL` rate requested from the
  autopilot, which was hardcoded at 5. **The default is unchanged, so no
  existing deployment changes behaviour.** Non-positive values are rejected at
  startup. Under SITL the effective rate is this value × `--speedup`.

### Changed
- `uav-api` with options and no command is an alias for `uav-api start`, so
  existing `uav-api --config ...` invocations keep working. The systemd unit
  and `install_service.sh` now spell out `start`.

### Fixed
- Under SITL the stream rate was silently MAVProxy's 4 Hz, not the API's 5 Hz:
  MAVProxy periodically re-sends `REQUEST_DATA_STREAM` at its own
  `--streamrate`, overwriting the API's request. The SITL command now passes
  `--streamrate=<mavlink_streamrate>` through `--mavproxy-args`, so simulated
  vehicles stream at 5 Hz by default (previously an effective 4 Hz).

## [0.3.0] - 2026-08-22

### Added
- `POST /movement/drive_body` and `POST /movement/drive_body_wait`: relative
  movement in the body FRD frame (`MAV_FRAME_BODY_OFFSET_NED` on the wire —
  ArduPilot rejects the newer `MAV_FRAME_BODY_FRD` name) — front/right/down
  offsets resolved against the vehicle's current position **and heading**,
  alongside the existing global-NED and offset-NED movement. New `Body_pos`
  request model (`front`, `right`, `down`, `look_at_target`); the blocking
  variant computes its arrival target by rotating the offset by the heading
  sampled at send time. (#7)
- **Response models on all 55 routes** (`uav_api/classes/responses.py`): the
  envelope is now machine-readable in the OpenAPI schema. Canonical shape:
  `device`/`id`/`result` on every JSON response. Telemetry `result` is
  normalized to lowercase `"success"` (previously a mix of `"Success"` and
  `"success"`); mission responses gain `result` while keeping their numeric
  `type` codes (42–52), now **deprecated** and scheduled for removal in a
  future release. `/peripherical/take_photo` (a JPEG FileResponse) is
  exempt.
- **Input validation on flight-critical parameters**, returning 422 before
  anything reaches MAVLink: GPS bodies (`lat` ±90, `long` ±180, `alt`
  0–10000 m), speed endpoints (0–50 m/s), copter takeoff (1–500 m), plane
  takeoff (up to 1000 m), `land_at` coordinates, heading (0–360), servo
  `channel` (1–16) and `pwm` (800–2200).
- `--terminal`: the terminal command SITL is wrapped in (default `xterm -e`),
  following ArduPilot's `SITL_RITW_TERMINAL` convention — e.g.
  `--terminal 'gnome-terminal --'`. Ignored with `--headless`.
- The requested `--location` is validated at startup: unknown names abort
  with a clear message when ArduPilot's built-in locations.txt is checkable
  (`--ardupilot_path` set), and warn otherwise.
- `--root_dir` (also settable in config files): a single root for all runtime
  artifacts, defaulting to `~/.uav_api/` with the layout `logs/{uav_logs,
  ardupilot_logs,script_logs}`, `scripts/` and `certs/`. Directories are
  created with mkdir-p semantics, so a pre-provisioned root (e.g. systemd
  `StateDirectory=`) works. `--log_path`, `--scripts_path`, `--script_logs`
  and `--certfile`/`--keyfile` remain as per-path overrides.

### Changed
- **BREAKING (default installs):** runtime artifacts move from
  `~/uav_api_logs/`, `~/uav_scripts/` and `~/uav_api_certs/` (the latter was
  hardcoded and could not be moved at all) to the single `~/.uav_api/` root.
  Deployments that set explicit paths are unaffected.
- The two near-duplicate logging-config builders in `uav_api/log.py` were
  collapsed into one builder parameterized by the server's logger names
  (uvicorn vs hypercorn), so the wiring can no longer drift apart.
- Config-file handling fails loudly instead of guessing: a missing or
  unreadable `--config` path aborts startup (it used to silently run on
  defaults — on a real drone that presented as "API up, no MAVLink"),
  malformed INI files abort with the parser error, and unknown section names
  abort naming the known set (`mode`, `api`, `logs`, `simulated`, `udp`).
  Unknown keys now warn through the `SYSTEM` logger instead of `print`.
- `--connection_type` is constrained to `udpin`/`udpout`/`usb`/`tcp`, and its
  help text documents that `usb` passes `uav_connection` through raw as a
  serial device path.
- **BREAKING (CLI):** `--simulated` is now a bare flag (`action='store_true'`),
  consistent with `--headless` and `--udp`. `--simulated true` is rejected by
  argparse; the old form was broken anyway — `type=bool` made `--simulated
  false` silently enable simulation. Config files are unaffected:
  `simulated = true/false` (and `yes/no`, `on/off`, `1/0`) keep working.
- **BREAKING (plane):** `POST /movement/land_at` was replaced by
  `GET /command/land_at?lat&long&alt&vtol`. Instead of the composite
  DO_REPOSITION → LAND (which needed a pre-arranged approach), it uploads a
  two-item mission (home + `NAV_LAND`, or `NAV_VTOL_LAND` with `vtol=true`)
  and switches to AUTO, returning as soon as the mode switch succeeds.
- Plane mode is no longer labeled beta in the API description.
- MAVLink receive architecture rewritten around a single consumer. A new
  `Vehicle` base class (`uav_api/vehicles/vehicle.py`) owns the connection and
  runs one dedicated receiver thread — the only line of execution that ever
  reads from pymavlink. Every other consumer reads either the latest-by-type
  message cache or a per-waiter subscription queue fed by the receiver, so
  responses wake their waiter the instant they are parsed. All sends are
  serialized behind one lock. `Copter` and `Plane` are now subclasses holding
  only vehicle-specific behavior.
- Endpoint latency improved across the board: telemetry endpoints are O(1)
  cache reads instead of busy-spin socket reads, command endpoints wake on ack
  arrival instead of polling every 50 ms, and long waits (goto, RTL, arm) pace
  at the telemetry stream rate instead of fighting other readers for the
  socket.
- The background `run_drain_mav_loop` asyncio task was removed; draining is
  the receiver thread's job. GCS heartbeats are now sent from the receiver
  loop on schedule instead of piggybacking on message parsing (previously they
  silently stopped whenever no traffic was being parsed).
- Previously unbounded blocking reads (`distance_to_home`, `wait_waypoint`,
  mission helpers, `mavfile.location()`) now have timeouts; the failure mode
  changes from hanging forever to raising a timeout error.

### Fixed
- `GET /peripherical/take_photo` no longer fails with an internal `TypeError`
  whenever `focus_distance` is provided (the manual-focus flags were appended
  with a broken `list.append` call). The parameter is now a `float` (sub-meter
  focus distances work) validated as `> 0`, so `focus_distance=0` returns 422
  instead of hitting a `ZeroDivisionError`.
- `POST /mission/execute-script/` no longer reports success when the script
  never started: a non-zero tmux exit now returns 500 with tmux's stderr in
  the detail, a missing tmux binary returns 503 instead of an unhandled
  traceback, and no "running" entry is recorded in either case. The paths
  interpolated into the `bash -c` command line are shell-quoted, so a
  scripts or log directory containing spaces survives intact. `upload-script`
  is now a sync endpoint, keeping its blocking disk I/O off the event loop.
- Removed the phantom `timeout` query parameter that `GET /command/land`
  advertised but never read, and the unused inline `Movement` model in the
  copter command router.
- The SITL launch command is now built as an argv list end-to-end instead of
  an f-string later split on spaces: no more empty argv entries from the
  double space after `--out`, and paths containing spaces
  (`--ardupilot_path`, the log directory) survive intact. The bare `except:`
  around SITL startup is narrowed to `except Exception` and now logs the
  actual exception.
- Custom SITL home locations are merged into an existing
  `~/.config/ardupilot/locations.txt` (preserving user entries) instead of
  being written only when the file did not exist — on machines with a
  pre-existing file the AbraDF entries were never added and SITL failed on
  the default `--location` with no hint why. The file is now only touched in
  simulated mode.
- On the default (TCP/uvicorn) server, `--log_console UVICORN`, `--debug
  UVICORN` and access logs in `--log_path` were silent no-ops: `uvicorn.run`
  was called without `log_config=None`, so uvicorn's default logging config
  overwrote the `uvicorn.*` loggers configured at startup, and
  `log_level="debug"` was hardcoded. The server now keeps the pre-configured
  loggers and derives its level from `--debug UVICORN`.
- Concurrent request handlers, the drain loop, and the Gradys GS task all read
  the same MAVLink connection at once, silently stealing each other's messages
  (pymavlink's type-filtered reads discard every non-matching message).
  Commands missed their acks, mission uploads lost handshake messages, and
  telemetry reads could spin for their full timeout. The single-consumer
  receiver eliminates the entire class of races; the 0.2.2 `COMMAND_ACK`
  hook workaround is superseded and removed.
- Plane commands still raced for their `COMMAND_ACK` (the 0.2.2 copter fix was
  never ported) and `Plane.run_cmd` byte-drained the connection unparsed,
  destroying other readers' in-flight messages. Both are gone via the shared
  base class.
- The Gradys GS task called a blocking 5-second MAVLink read on the event
  loop every second; it now uses a non-blocking cache read
  (`sensor_has_state_cached`).
- `GET /command/set_home` failed with `MAV_RESULT_FAILED` when called before
  the EKF set its origin (a boot-time race). The command is now retried until
  the autopilot accepts it or a 30 s timeout expires.
- A latched `in_drain_mav` flag (set once, never cleared on the default code
  path) permanently disabled the idle hook; the flag and hook are gone with
  the drain machinery.
- `POST /movement/go_to_gps_wait` (plane) timed out on every call (found by
  the new `tests/plane_test.py`): the arrival check compared the target's
  home-relative altitude against the plane's absolute AMSL altitude, and its
  50 m horizontal accuracy was unreachable — an arriving fixed-wing loiters
  around the target and never comes closer than the loiter radius plus entry
  overshoot. The altitude is now converted to AMSL for the check and the
  default accuracy widened to 120 m (2x the default `WP_LOITER_RAD`).

### Added
- `tests/concurrency_test.py`: while `POST /movement/go_to_gps_wait` is in
  flight, telemetry endpoints must answer with p95 latency under 0.5 s and an
  ack-waiting command must succeed — the exact scenario that hung before the
  refactor.
- Testing & CI overhaul (#26):
  - `dev` optional-dependency extra (`pip install -e .[dev]`) declaring the
    previously undeclared test dependencies (`pytest`, `requests`, `httpx`)
    plus `ruff`, with pytest and ruff config in `pyproject.toml`.
  - GitHub Actions workflow running `ruff check` and the non-SITL test subset
    (Python 3.10 and 3.12) on every push to main and every pull request.
  - `sitl` pytest marker on all SITL-backed integration modules, so
    `pytest -m "not sitl"` runs anywhere without ArduPilot.
  - Unit-test layer (`tests/unit/`, 85 tests): FastAPI `TestClient` against
    `create_app()` with an autospec-mocked vehicle. Pins the HTTP contract of
    every copter and plane endpoint — including the previously untested plane
    surface, `/mission/stop-script/`, `/mission/running-scripts`,
    `go_to_ned_wait`, `drive_wait`, `set_heading` and `set_yaw_rate` — the
    MAVLink unit conversions in the telemetry handlers, and the exact tmux
    argv of the mission-script lifecycle.
  - `tests/plane_test.py`: first plane SITL integration module (port 8007,
    sysid 7) flying a full arc: telemetry grounded → arm → takeoff →
    `go_to_gps_wait` → `stop` (LOITER) → RTL → fire-and-forget `land_at`.
  - Mission lifecycle SITL test asserting execute → running-scripts →
    stop-script transitions plus the scripts-watcher detecting a natural
    script exit.
  - `README` Testing section documenting both layers, prerequisites and the
    port/sysid allocation table.
  - `copter` and `plane` pytest markers: select vehicle-specific tests with
    `-m copter` / `-m plane`, composable with `sitl`
    (e.g. `pytest -m "plane and not sitl"`).

### Changed (internal)
- The routers package was restructured into `uav_api/routers/{copter,plane,common}/`
  subpackages with short module names (`copter/telemetry.py` instead of
  `copter_telemetry.py`); the vehicle-agnostic mission and peripherical routers
  live in `common/`, and `router_dependencies.py` is now
  `uav_api/routers/dependencies.py`. Each module exports a `router` variable.
  No HTTP API change.
- Test modules treat copter and plane as equals: SITL modules are
  vehicle-prefixed per router (`copter_command_test.py`,
  `plane_movement_test.py`, ...), the plane suite is split into three modules
  with their own SITL instances (ports 8007-8009), and the unit layer mirrors
  the router layout. The `flying=True` fixture now supports plane (arms and
  climbs to 50 m in GUIDED).
- Docs no longer label plane support as beta: it is covered by unit tests and
  SITL integration modules, and README/docs module maps reflect the new
  router layout.
- `uav_api/api_app.py` now exposes a `create_app(args)` factory; the module
  imports cleanly without the `UAV_ARGS` environment variable (previously it
  crashed at import). The `uav_api.api_app:app` uvicorn/hypercorn entrypoint
  is unchanged.
- Vehicle construction split from the request dependency
  (`init_copter`/`init_plane` for the lifespan, no-arg
  `get_copter_instance`/`get_plane_instance` for requests). This removes the
  phantom `sysid`/`connection` query parameters that previously leaked into
  every endpoint's OpenAPI schema (they were never functional).
- Repo-wide `ruff` cleanup (unused imports, placeholder-less f-strings,
  `isinstance` type checks); no behavior changes.

## [0.2.2] - 2026-08-13

### Added
- `--headless` flag: SITL runs without spawning terminal windows (no xterm or X
  server required), with MAVProxy kept alive via `--daemon`.
- Canonical systemd unit and config example under `packaging/`, plus a
  deployment guide (`docs/deployment.md`) for running uav_api as a Linux
  service and provisioning fleets with gradys-fleet.
- `ready_to_arm`, `ground_speed`, `air_speed`, `heading` and battery
  information in the gradys_gs task data.
- Reference documentation published under `docs/`: HTTP API specification,
  coordinate frames, and plane support.
- This changelog.

### Changed
- **BREAKING:** `GET /movement/stop` and `GET /movement/resume` (copter) were
  replaced by `GET /command/brake` (BRAKE mode: immediate halt + position
  hold) and `GET /command/guided` (return to GUIDED, re-enabling movement
  commands). The old MAVLink pause left the vehicle silently ignoring every
  subsequent movement command until an explicit resume.
- **BREAKING (gradys_gs):** the `battery_voltage` field was removed from the
  gradys_gs task data in favor of `ready_to_arm`.
- Integration tests now boot a fresh SITL per test file (unique port/sysid)
  instead of sharing one session-scoped instance, eliminating cross-test
  state leaks.
- `POST /movement/travel_at_ned` documentation now states that the velocity
  setpoint is sent once and ArduPilot stops the vehicle after `GUID_TIMEOUT`
  (3 s) unless the caller re-sends it periodically.
- `--ardupilot_path` is now optional: by default `sim_vehicle.py` is resolved
  from the PATH environment variable instead of requiring an explicit
  ArduPilot checkout path.
- Declared Python floor raised to 3.10.
- Config-file precedence and startup directory creation are now documented.

### Fixed
- `POST /movement/drive` sent a zeroed typemask when `look_at_target` was
  false (operator-precedence bug), commanding position, velocity and
  acceleration simultaneously.
- `COMMAND_ACK` messages could be consumed by a concurrent reader of the
  MAVLink connection (background drain loop or another request handler),
  making ack-waiting endpoints hang and fail intermittently. Acks are now
  captured by a message hook and matched by command id and timestamp.
- `GET /telemetry/compass` returned a 500 (`KeyError`) when no compass
  calibration ever ran; it now returns 404 with an explanatory detail.
- Boolean values in config files are coerced correctly.
- Empty list values in config files are parsed correctly.
- uav_api creates its own directories regardless of how the paths are
  configured.
- gradys_gs battery fields reported incorrect values.

### Deprecated
- `scripts/install_service.sh`, superseded by the `packaging/` systemd unit
  and gradys-fleet.

### Removed
- License declaration removed from `pyproject.toml`.
- `.claude/` context files removed from version control.

## [0.2.1] - 2026-06-06

### Added
- Script lifecycle management for the mission router: `GET /mission/running-scripts`,
  `POST /mission/stop-script` (graceful Ctrl+C → kill so scripts can land/clean up),
  per-script status tracking, and a background watcher that marks scripts `stopped`
  when their tmux session ends.
- New `SCRIPT` logging component for script lifecycle messages.

### Changed
- **BREAKING:** the log-component token `API` was renamed to `UVICORN` in
  `--log_console` and `--debug`. Update launch scripts (`--log_console API` →
  `--log_console UVICORN`). Valid components are now `VEHICLE`, `UVICORN`,
  `GRADYS_GS`, `SCRIPT`.
- Logging overhauled: `print` statements replaced with structured per-component
  loggers; loggers configured earlier so startup messages surface.
- Hardened startup/shutdown: SITL liveness is verified after spawn and partially
  started resources are torn down if startup fails; lifespan logic extracted from
  `api_app.py` into `uav_api/lifespan.py`.

### Fixed
- `GET /movement/set_yaw_rate` no longer sends an incorrect position-target
  typemask; continuous yaw now works as documented.
- tmux sessions spawned for scripts are stopped on API shutdown (no orphans).

### Removed
- Stray ArduPilot SITL artifacts committed to the repo (`mav.tlog`,
  `mav.tlog.raw`, `mav.parm`, `eeprom.bin`, terrain data).

## [0.2.0] - 2026-05-27

### Added
- Plane support (beta): `--vehicle plane` selects ArduPlane SITL and registers
  plane-specific command/movement/telemetry routers.

### Changed
- Vehicle refactor: per-vehicle logger names and log folders (`COPTER` / `PLANE`).
- Improved `libcamera-still` camera configuration for `take_photo` (auto-focus
  disabled for more reliable captures).

## [0.1.3] - 2026-04-20

### Added
- HTTP/3 (QUIC over UDP) server mode via Hypercorn (`--udp`), with auto-generated
  self-signed certs and an example client.
- Servo PWM output endpoint.
- Integration test suite covering all routers.
- `upload-version` skill for PyPI publishing.

### Changed
- uvicorn and hypercorn are now started via their programmatic Python APIs
  instead of subprocess CLI calls.
- `flight_examples` standardized (shared helpers, bug fixes); auto-reload removed;
  documentation refactored.

## [0.1.2] - 2026-04-09

### Added
- `set_heading` and `set_yaw_rate` endpoints for yaw control.
- Project docs (`CLAUDE.md`, `.claude/`) added to version control.

### Fixed
- NED position accuracy set to 1 m to prevent `travel_at_ned` timeouts.

## [0.1.1] - 2026-03-25

### Added
- `travel_at_ned` velocity endpoint and `look_at_target` option on movement
  endpoints.

### Changed
- `run_with_args` now uses the parent script's Python interpreter.

## [0.1.0] - 2026-02-24

### Added
- Gradys Ground Station integration: periodic GPS-location push via `--gradys_gs`.
- Mission router: upload, list, execute (in tmux), and clear scripts;
  `--scripts_path` and `--script_logs` arguments.
- Polygon, delivery, and follow flight examples.

### Changed
- Movement endpoints switched from NEU to NED frame and now accept float
  positions; arrival accuracy tuned (30 cm).
- Responses include `device` and `id` so the ground station can identify the
  author.

### Fixed
- Location-fetch error loop and graceful-interrupt handling.

## [0.0.5] - 2025-12-11

### Added
- USB / serial connection support.
- `set_home` command and home-position telemetry.
- Background MAVLink drain loop coroutine.
- INI config-file support (`--config`).

### Changed
- Position endpoints return the last received message instead of blocking for the
  next one.

## [0.0.4] - 2025-11-06

Initial public release (renamed from `uav_control`). Copter GUIDED control over
HTTP, ArduPilot SITL support, `sim_speedup` control, `take_picture`, Swagger
docs, INI config, and initial flight examples.

[0.3.1]: https://github.com/Project-GrADyS/uav_api/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/Project-GrADyS/uav_api/compare/v0.2.2...v0.3.0
[0.2.2]: https://github.com/Project-GrADyS/uav_api/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Project-GrADyS/uav_api/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Project-GrADyS/uav_api/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/Project-GrADyS/uav_api/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Project-GrADyS/uav_api/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Project-GrADyS/uav_api/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Project-GrADyS/uav_api/compare/v0.0.5...v0.1.0
[0.0.5]: https://github.com/Project-GrADyS/uav_api/compare/v0.0.4...v0.0.5
[0.0.4]: https://github.com/Project-GrADyS/uav_api/releases/tag/v0.0.4
