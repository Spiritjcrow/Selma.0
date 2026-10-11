"""Bounded PID-bound loopback readiness check for SelmaOS first-run.

No network discovery, privileges, or third-party dependencies. A service already
listening on the port is not proof that *our* newly spawned child is ready.
"""
import http.client
import json
import subprocess
import time


def wait_for_runtime_ready(process, timeout=15.0, port=8765):
    """Return True only while this child serves the expected command-core API."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        remaining = max(0.0, deadline - time.monotonic())
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=min(0.5, remaining))
        try:
            connection.request("GET", "/api/selma0/status/v1")
            response = connection.getresponse()
            body = response.read(8193)
            if response.status == 200 and len(body) <= 8192:
                data = json.loads(body)
                if (isinstance(data, dict)
                    and data.get("name") == "Selma.0"
                    and type(data.get("runtime_pid_v1")) is int
                    and data["runtime_pid_v1"] == process.pid
                    and isinstance(data.get("command_core"), dict)):
                    return process.poll() is None
        except (OSError, ValueError, http.client.HTTPException):
            pass
        finally:
            connection.close()
        time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
    return False


def stop_runtime_child(process):
    """Stop only the child we spawned; never kill an unrelated listener."""
    try:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        pass
