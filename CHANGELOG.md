# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.2.2]: https://github.com/Project-GrADyS/uav_api/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Project-GrADyS/uav_api/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Project-GrADyS/uav_api/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/Project-GrADyS/uav_api/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Project-GrADyS/uav_api/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Project-GrADyS/uav_api/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Project-GrADyS/uav_api/compare/v0.0.5...v0.1.0
[0.0.5]: https://github.com/Project-GrADyS/uav_api/compare/v0.0.4...v0.0.5
[0.0.4]: https://github.com/Project-GrADyS/uav_api/releases/tag/v0.0.4
