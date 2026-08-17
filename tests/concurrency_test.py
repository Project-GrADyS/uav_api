"""Concurrency: the API must stay responsive while a long-blocking endpoint runs.

Reproduces the message-theft bug the single-consumer MAVLink refactor fixed:
before it, a request blocked in /movement/go_to_gps_wait drained the shared
connection, so simultaneous telemetry reads spun until their timeout and
ack-waiting commands frequently missed their COMMAND_ACK. With one receiver
thread feeding per-waiter queues, telemetry stays an O(1) cache read and acks
cannot be stolen.

Port 8006 / sysid 6 (see conftest for the allocation table).
"""

import threading
import time

from conftest import make_api_fixture

api = make_api_fixture(8006, 6, flying=True)

# ~600 m north of the SITL home position (1 deg lat ~= 111 km). At ~10 m/s and
# SITL --speedup 5 that is roughly 12 s of wall time — long enough for the
# telemetry/command probes below to run while the movement is in flight.
DELTA_LAT = 600 / 111_000


def test_telemetry_and_commands_during_go_to_gps_wait(api):
    r = api.get("/telemetry/gps")
    assert r.status_code == 200, r.text
    pos = r.json()["info"]["position"]
    target = {
        "lat": pos["lat"] + DELTA_LAT,
        "long": pos["lon"],
        "alt": 15,
    }

    result = {}

    def fly():
        # Client timeout larger than the endpoint's internal 60 s wait_location
        # timeout, per the conftest warning.
        result["response"] = api.post("/movement/go_to_gps_wait", json=target, timeout=120)

    mover = threading.Thread(target=fly)
    mover.start()
    time.sleep(0.2)  # let the movement request reach its wait loop

    telemetry_latencies = []
    command_response = None
    deadline = time.time() + 30
    try:
        while mover.is_alive() and time.time() < deadline:
            for path in ("/telemetry/gps", "/telemetry/general"):
                tstart = time.time()
                r = api.get(path, timeout=10)
                telemetry_latencies.append(time.time() - tstart)
                assert r.status_code == 200, f"{path} failed mid-flight: {r.text}"
            # One ack-waiting command mid-flight (CONDITION_YAW doesn't cancel
            # the position target): pre-refactor this frequently timed out
            # because another handler consumed the COMMAND_ACK.
            if command_response is None and len(telemetry_latencies) >= 4:
                command_response = api.get("/movement/set_heading",
                                           params={"heading": 90}, timeout=30)
            time.sleep(0.2)
    finally:
        mover.join(timeout=120)

    assert result["response"].status_code == 200, result["response"].text
    assert command_response is not None, "movement finished before the mid-flight command was sent"
    assert command_response.status_code == 200, command_response.text

    assert len(telemetry_latencies) >= 10, "not enough telemetry samples while flying"
    telemetry_latencies.sort()
    p95 = telemetry_latencies[int(len(telemetry_latencies) * 0.95) - 1]
    assert p95 < 0.5, f"telemetry p95 latency {p95:.2f}s while movement in flight"
