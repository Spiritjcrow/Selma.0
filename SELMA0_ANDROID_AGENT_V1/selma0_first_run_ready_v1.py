"""SelmaOS first-run bounded readiness and child cleanup (candidate, not yet wired)."""
import http.client
import json
import os
import select
import subprocess
import time


def wait_for_runtime_ready(process, read_fd, timeout=8.0):
    deadline = time.monotonic() + timeout
    message = b""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        remaining = max(0.0, deadline - time.monotonic())
        ready, _, _ = select.select([read_fd], [], [], min(0.2, remaining))
        if not ready:
            continue
        part = os.read(read_fd, 64)
        if not part:
            return False
        message += part
        if len(message) > 64:
            return False
        if b"\n" in message:
            if message.split(b"\n", 1)[0] != b"SELMA0_READY_V1":
                return False
            break
    else:
        return False
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        connection = http.client.HTTPConnection("127.0.0.1", 8765, timeout=0.5)
        try:
            connection.request("GET", "/api/selma0/status/v1")
            response = connection.getresponse()
            body = response.read(8192)
            data = json.loads(body)
            if (response.status == 200 and isinstance(data, dict)
                    and data.get("name") == "Selma.0"
                    and type(data.get("runtime_pid_v1")) is int
                    and data["runtime_pid_v1"] == process.pid
                    and isinstance(data.get("command_core"), dict)):
                return process.poll() is None
        except (OSError, ValueError, http.client.HTTPException):
            pass
        finally:
            connection.close()
        time.sleep(0.1)
    return False


def stop_runtime_child(process):
    try:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            # Reap the killed child before allowing a new startup attempt.
            process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        pass
