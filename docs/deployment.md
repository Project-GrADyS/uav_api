# Deploying on hardware

Running uav_api on a drone's companion computer, as a systemd service that starts
on boot. For bringing a vehicle up by hand — or for simulation — see the README's
[Getting Started](../README.md#getting-started) section instead.

## What ships in this repo

| File | Purpose |
|------|---------|
| [`packaging/systemd/uav-api.service`](../packaging/systemd/uav-api.service) | Canonical systemd unit, with placeholders to substitute |
| [`packaging/uav-api.ini.example`](../packaging/uav-api.ini.example) | Canonical real-drone configuration |

Both are the reference copies. Fleet deployments render them per drone from
templates in [gradys-fleet](https://github.com/Project-GrADyS/gradys-fleet)
(`roles/uav_api/templates/`) — when you change one side, change the other.

## Installing on a single companion computer

Prerequisites on the machine: Python 3.10+, the `uav-api` package installed in a
virtualenv, and `tmux` if you intend to use `/mission/execute-script`. A MAVLink
source must reach the address in the config — typically `mavlink-router` or
MAVProxy forwarding the flight controller's stream to `127.0.0.1`.

Copy the configuration and edit it for this vehicle:

```bash
sudo install -D -m 0644 packaging/uav-api.ini.example /etc/gradys/uav-api.ini
sudo nano /etc/gradys/uav-api.ini      # set sysid, gradys_gs, paths
```

Substitute the `__USER__`, `__VENV__`, `__CONFIG__` and `__HOME__` placeholders in
the unit, then install and start it:

```bash
sudo install -m 0644 packaging/systemd/uav-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now uav-api
journalctl -u uav-api -f
```

The API creates its own working directories at startup — `scripts_path`,
`script_logs`, and the parent of `log_path` — whether those paths came from
defaults or from the config file. The deployment only has to ensure the service
user can write to them.

## Configuration notes

The config file is read *after* the command line, so **values in the file
override CLI arguments**. Two consequences that bite on real hardware:

- **A real-drone config must not contain a `[simulated]` section.** Its mere
  presence switches the API into simulated mode whatever it contains; there is no
  `simulated = false` to turn it back off.
- `sysid` must match the flight controller's `SYSID_THISMAV` parameter. Nothing
  validates this — a mismatch looks exactly like receiving no MAVLink at all.

Unlike SITL, where several vehicles share one host and ports are offset per
vehicle, each drone is its own host, so `port` stays at 8000 across the fleet.

## Why the unit looks the way it does

Three directives are load-bearing and should not be "simplified" away:

| Directive | Why |
|-----------|-----|
| `Wants=` / `After=network-online.target` | `network.target` does not wait for an address to be assigned. uav_api resolves its own IP at startup and reports it to the ground station, so starting earlier means reporting a wrong or empty address for the whole flight. |
| `Environment=PATH=<venv>/bin:...` | `--python_path` defaults to the bare string `python3`. This PATH is what makes scripts uploaded through `/mission/upload-script` run under the virtualenv interpreter. |
| `Restart=always` | If uav_api dies mid-flight the flight controller keeps executing its last command, but the vehicle is uncommandable until the API returns. |

`SupplementaryGroups=dialout` is not required on the UDP/mavlink-router path, but
is needed the moment the companion computer is wired to the flight controller
over serial.

## Fleet deployment

For more than one drone, use
[**gradys-fleet**](https://github.com/Project-GrADyS/gradys-fleet). It provisions
companion computers from a golden image and manages every vehicle's identity,
configuration and services from a single inventory, including `gradys-embedded`,
pre-flight verification and post-flight data collection.

## `scripts/install_service.sh` is deprecated

It remains only for backwards compatibility. It hardcodes the user `pi`, assumes
a machine already prepared by hand (it does not create the virtualenv, install the
package, or install OS packages such as `tmux`), and is single-drone by
construction. It also writes `port = 8000 + sysid`, an offset that only makes
sense for SITL. Use `packaging/` or gradys-fleet instead.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| The service reports a wrong or empty IP to the ground station | Unit ordered on `network.target` rather than `network-online.target`, so it started before an address was assigned. |
| The API tries to spawn SITL | The config file has a `[simulated]` section. Delete the section. |
| Telemetry endpoints time out, no MAVLink at all | `sysid` does not match `SYSID_THISMAV`, or nothing is forwarding the flight controller stream to `uav_connection`. |
| `/mission/execute-script` returns 200 but the script produces no output | `script_logs` is not writable by the service user: the shell redirection fails before the interpreter runs, while tmux still starts and the endpoint still reports `running`. |
| A file literally named `None` appears next to the process | `log_path = None` written in the INI. Values are read as strings — omit the key to get the default. |
| Uploaded scripts run under the wrong interpreter | The unit's `Environment=PATH` does not start with the virtualenv's `bin`. |
