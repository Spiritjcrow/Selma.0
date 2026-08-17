#!/usr/bin/env python3
import json
import shutil
import subprocess
from datetime import datetime, timezone


_MAX_OUTPUT_BYTES_V1 = 1024 * 1024
_DEFAULT_TIMEOUT_SECONDS_V1 = 15


def _utc_now_v1():
    return datetime.now(timezone.utc).isoformat()


def _bounded_text_v1(value, limit=_MAX_OUTPUT_BYTES_V1):
    text = str(value or "")
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text
    return encoded[:limit].decode("utf-8", errors="replace")


class Selma0TermuxDeviceBridgeAndroidV1:
    """Bounded rootless Android device bridge backed by Termux:API.

    No arbitrary shell command strings are accepted. Every operation resolves to a
    fixed executable plus bridge-generated arguments and runs with shell=False.
    """

    JSON_COMMANDS_V1 = {
        "battery_status": "termux-battery-status",
        "wifi_connection": "termux-wifi-connectioninfo",
        "wifi_scan": "termux-wifi-scaninfo",
    }

    EFFECT_COMMANDS_V1 = {
        "notify": "termux-notification",
        "vibrate": "termux-vibrate",
    }

    def __init__(self, runner=None, which=None, timeout_seconds=_DEFAULT_TIMEOUT_SECONDS_V1):
        self._runner = runner or subprocess.run
        self._which = which or shutil.which
        self.timeout_seconds = max(1, min(int(timeout_seconds), 60))

    def _resolve_executable_v1(self, executable):
        path = self._which(executable)
        if not path:
            raise RuntimeError(
                f"required Termux:API command is unavailable: {executable}; "
                "install the Termux:API app and termux-api package"
            )
        return path

    def _run_v1(self, executable, args=None, expect_json=False, stdin_text=None):
        path = self._resolve_executable_v1(executable)
        command = [path] + [str(item) for item in (args or [])]
        try:
            completed = self._runner(
                command,
                input=stdin_text,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Termux:API command timed out: {executable}") from exc
        except OSError as exc:
            raise RuntimeError(f"Termux:API command failed to start: {executable}: {exc}") from exc

        stdout = _bounded_text_v1(getattr(completed, "stdout", ""))
        stderr = _bounded_text_v1(getattr(completed, "stderr", ""))
        returncode = int(getattr(completed, "returncode", 1))
        if returncode != 0:
            detail = stderr.strip() or stdout.strip() or f"exit status {returncode}"
            raise RuntimeError(f"Termux:API command failed: {executable}: {detail}")

        data = stdout
        if expect_json:
            try:
                data = json.loads(stdout)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(f"Termux:API returned invalid JSON: {executable}") from exc

        return {
            "ok": True,
            "source": f"termux-api:{executable}",
            "measurement_kind": "measured" if expect_json else None,
            "device_local": True,
            "collected_at": _utc_now_v1(),
            "command": executable,
            "data": data,
        }

    def read_json(self, operation):
        operation = str(operation or "").strip()
        executable = self.JSON_COMMANDS_V1.get(operation)
        if not executable:
            raise ValueError(f"device read operation is not allowlisted: {operation}")
        return self._run_v1(executable, expect_json=True)

    def location(self, provider="gps"):
        provider = str(provider or "gps").strip().lower()
        if provider not in {"gps", "network", "passive"}:
            raise ValueError("location provider must be gps, network, or passive")
        return self._run_v1(
            "termux-location",
            args=["-p", provider, "-r", "once"],
            expect_json=True,
        )

    def notify(self, title="Selma", content=""):
        title = str(title or "Selma")[:120]
        content = str(content or "")[:4000]
        if not content:
            raise ValueError("notification content is required")
        return self._run_v1(
            self.EFFECT_COMMANDS_V1["notify"],
            args=["--title", title, "--content", content],
            expect_json=False,
        )

    def vibrate(self, duration_ms=250, force=False):
        try:
            duration_ms = int(duration_ms)
        except (TypeError, ValueError) as exc:
            raise ValueError("duration_ms must be an integer") from exc
        duration_ms = max(1, min(duration_ms, 5000))
        args = ["-d", str(duration_ms)]
        if force is True:
            args.append("-f")
        return self._run_v1(
            self.EFFECT_COMMANDS_V1["vibrate"],
            args=args,
            expect_json=False,
        )


def register_device_tools(registry, bridge=None):
    bridge = bridge or Selma0TermuxDeviceBridgeAndroidV1()
    registry.register(
        "device.battery_status",
        lambda: bridge.read_json("battery_status"),
        risk="read",
        description="Read measured Android battery status through Termux:API.",
    )
    registry.register(
        "device.wifi_connection",
        lambda: bridge.read_json("wifi_connection"),
        risk="read",
        description="Read measured current Wi-Fi connection metadata through Termux:API.",
    )
    registry.register(
        "device.location",
        lambda provider="gps": bridge.location(provider=provider),
        risk="sensitive_read",
        description="Read device location through Termux:API; explicit approval required.",
    )
    registry.register(
        "device.notify",
        lambda title="Selma", content="": bridge.notify(title=title, content=content),
        risk="external_effect",
        description="Post an Android notification through Termux:API; explicit approval required.",
    )
    registry.register(
        "device.vibrate",
        lambda duration_ms=250, force=False: bridge.vibrate(duration_ms=duration_ms, force=force),
        risk="external_effect",
        description="Vibrate the Android device through Termux:API; explicit approval required.",
    )
    return bridge
