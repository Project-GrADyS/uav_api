# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.2.1]: https://github.com/Project-GrADyS/uav_api/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Project-GrADyS/uav_api/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/Project-GrADyS/uav_api/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Project-GrADyS/uav_api/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Project-GrADyS/uav_api/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Project-GrADyS/uav_api/compare/v0.0.5...v0.1.0
[0.0.5]: https://github.com/Project-GrADyS/uav_api/compare/v0.0.4...v0.0.5
[0.0.4]: https://github.com/Project-GrADyS/uav_api/releases/tag/v0.0.4
