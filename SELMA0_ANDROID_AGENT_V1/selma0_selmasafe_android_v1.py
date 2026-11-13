import hashlib
import hmac
import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone


SELMA0_BASE_V1 = os.path.expanduser(os.getenv("SELMA0_BASE_V1", "~/SELMA0_ANDROID_AGENT_V1"))
SELMA0_SAFE_DIR_V1 = os.path.join(SELMA0_BASE_V1, "selma0_safety_android_v1", "selmasafe_v1")
SELMA0_SAFE_DEVICES_V1 = os.path.join(SELMA0_SAFE_DIR_V1, "devices_v1.json")
SELMA0_SAFE_IDENTITY_V1 = os.path.join(SELMA0_SAFE_DIR_V1, "device_identity_v1.json")
SELMA0_SAFE_OUTBOX_V1 = os.path.join(SELMA0_SAFE_DIR_V1, "outbox_v1")
SELMA0_SAFE_RECORDINGS_V1 = os.path.join(SELMA0_SAFE_DIR_V1, "recordings_v1")
SELMA0_SAFE_INACTIVITY_V1 = os.path.join(SELMA0_SAFE_DIR_V1, "inactivity_state_v1.json")

DEFAULT_INACTIVITY_POLICY_V1 = {
    "warning_after_seconds": 72 * 60 * 60,
    "lock_after_seconds": 7 * 24 * 60 * 60,
    "destructive_auto_delete": False,
}


def _utc_now_v1():
    return datetime.now(timezone.utc).isoformat()


def _compact_json_v1(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _atomic_json_write_v1(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


class Selma0SelmaSafeAndroidV1:
    """Portable SelmaSafe core for Android/Termux.

    The core intentionally avoids IMEI/device-account scraping. Devices are enrolled
    with SelmaSafe-generated IDs. Cross-device events are HMAC signed and staged in
    an outbox for an approved transport adapter. A missing shared secret fails
    closed for remote fan-out without blocking local SOS actions.

    Inactivity protection never destructively deletes data on a missed check-in.
    It can mark the profile locked/pending verification; any future purge executor
    must be a separately approved, audited capability.
    """

    def __init__(
        self,
        runner=None,
        base_dir=SELMA0_SAFE_DIR_V1,
        devices_path=None,
        identity_path=None,
        outbox_dir=None,
        recordings_dir=None,
        inactivity_path=None,
    ):
        self.runner = runner
        self.base_dir = os.path.expanduser(base_dir)
        self.devices_path = devices_path or os.path.join(self.base_dir, "devices_v1.json")
        self.identity_path = identity_path or os.path.join(self.base_dir, "device_identity_v1.json")
        self.outbox_dir = outbox_dir or os.path.join(self.base_dir, "outbox_v1")
        self.recordings_dir = recordings_dir or os.path.join(self.base_dir, "recordings_v1")
        self.inactivity_path = inactivity_path or os.path.join(self.base_dir, "inactivity_state_v1.json")
        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.outbox_dir, exist_ok=True)
        os.makedirs(self.recordings_dir, exist_ok=True)
        self.local_identity = self._load_or_create_identity_v1()

    def _load_json_v1(self, path, fallback):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                value = json.load(handle)
            return value
        except (OSError, ValueError):
            return fallback

    def _load_or_create_identity_v1(self):
        identity = self._load_json_v1(self.identity_path, {})
        if not isinstance(identity, dict) or not str(identity.get("device_id", "")).strip():
            identity = {
                "device_id": str(uuid.uuid4()),
                "created_at": _utc_now_v1(),
                "label": os.getenv("SELMA0_DEVICE_LABEL_V1", "Selma Android device"),
            }
            _atomic_json_write_v1(self.identity_path, identity)
        return identity

    def _shared_secret_v1(self):
        value = os.getenv("SELMA0_SAFE_SHARED_SECRET_V1", "")
        return value.encode("utf-8") if value else b""

    def capabilities(self):
        return {
            "microphone_record": bool(shutil.which("termux-microphone-record")),
            "signed_fanout": bool(self._shared_secret_v1()),
            "transport": "outbox_adapter_required",
            "imei_required": False,
        }

    def enroll_device(self, label, role="family", device_id=None):
        label = str(label or "").strip()
        role = str(role or "family").strip() or "family"
        if not label:
            raise ValueError("device label is required")
        device_id = str(device_id or uuid.uuid4()).strip()
        state = self._load_json_v1(self.devices_path, {"devices": []})
        devices = state.get("devices", []) if isinstance(state, dict) else []
        if not isinstance(devices, list):
            devices = []
        entry = {
            "device_id": device_id,
            "label": label,
            "role": role,
            "enabled": True,
            "enrolled_at": _utc_now_v1(),
        }
        replaced = False
        for index, item in enumerate(devices):
            if isinstance(item, dict) and str(item.get("device_id")) == device_id:
                entry["enrolled_at"] = item.get("enrolled_at", entry["enrolled_at"])
                devices[index] = entry
                replaced = True
                break
        if not replaced:
            devices.append(entry)
        _atomic_json_write_v1(self.devices_path, {"devices": devices})
        return dict(entry)

    def list_devices(self):
        state = self._load_json_v1(self.devices_path, {"devices": []})
        devices = state.get("devices", []) if isinstance(state, dict) else []
        if not isinstance(devices, list):
            return []
        return [dict(item) for item in devices if isinstance(item, dict)]

    def _sign_v1(self, payload):
        secret = self._shared_secret_v1()
        if not secret:
            return None
        return hmac.new(secret, _compact_json_v1(payload).encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_envelope(self, envelope, now=None):
        if not isinstance(envelope, dict):
            return {"ok": False, "error": "envelope must be an object"}
        payload = envelope.get("payload")
        signature = str(envelope.get("signature") or "")
        if not isinstance(payload, dict):
            return {"ok": False, "error": "missing payload"}
        secret = self._shared_secret_v1()
        if not secret:
            return {"ok": False, "error": "shared secret not configured"}
        expected = self._sign_v1(payload)
        if not signature or not hmac.compare_digest(signature, expected):
            return {"ok": False, "error": "signature mismatch"}
        current = float(time.time() if now is None else now)
        expires_at = float(payload.get("expires_unix", 0) or 0)
        if expires_at <= current:
            return {"ok": False, "error": "event expired"}
        return {"ok": True, "payload": payload}

    def build_sos_envelope(self, reason="", emergency_level="critical", request_recording=True, ttl_seconds=180):
        now = time.time()
        payload = {
            "schema": "selmasafe.sos.v1",
            "event_id": str(uuid.uuid4()),
            "sender_device_id": self.local_identity["device_id"],
            "issued_at": _utc_now_v1(),
            "issued_unix": now,
            "expires_unix": now + max(30, min(int(ttl_seconds), 900)),
            "emergency_level": str(emergency_level or "critical"),
            "reason": str(reason or "").strip(),
            "actions": {
                "show_high_priority_notification": True,
                "request_audio_recording": bool(request_recording),
            },
        }
        return {
            "algorithm": "HMAC-SHA256" if self._shared_secret_v1() else None,
            "payload": payload,
            "signature": self._sign_v1(payload),
        }

    def queue_sos_fanout(self, reason="", emergency_level="critical", request_recording=True):
        devices = [d for d in self.list_devices() if d.get("enabled") is not False]
        if not devices:
            return {"ok": False, "queued": False, "error": "no enrolled peer devices"}
        if not self._shared_secret_v1():
            return {
                "ok": False,
                "queued": False,
                "error": "SELMA0_SAFE_SHARED_SECRET_V1 is not configured; unsigned remote fan-out is blocked",
            }
        envelope = self.build_sos_envelope(
            reason=reason,
            emergency_level=emergency_level,
            request_recording=request_recording,
        )
        envelope["targets"] = [
            {
                "device_id": str(d.get("device_id", "")),
                "label": str(d.get("label", "")),
                "role": str(d.get("role", "")),
            }
            for d in devices
        ]
        event_id = envelope["payload"]["event_id"]
        path = os.path.join(self.outbox_dir, f"{event_id}.json")
        _atomic_json_write_v1(path, envelope)
        return {
            "ok": True,
            "queued": True,
            "event_id": event_id,
            "targets": envelope["targets"],
            "outbox_path": path,
            "transport": "pending_adapter_delivery",
        }

    def _run_v1(self, argv, timeout=12):
        if self.runner is not None:
            return self.runner(argv, timeout=timeout)
        if not argv or not shutil.which(argv[0]):
            return {"ok": False, "error": f"missing capability: {argv[0] if argv else 'unknown'}"}
        try:
            proc = subprocess.run(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "command timed out"}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }

    def start_audio_recording(self, limit_seconds=300, encoder="aac", sample_rate=48000, channels=1):
        limit_seconds = max(10, min(int(limit_seconds), 3600))
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = os.path.join(self.recordings_dir, f"selmasafe_{stamp}_{uuid.uuid4().hex[:8]}.m4a")
        result = self._run_v1([
            "termux-microphone-record",
            "-f", path,
            "-l", str(limit_seconds),
            "-e", str(encoder),
            "-r", str(int(sample_rate)),
            "-c", str(int(channels)),
        ], timeout=10)
        return {
            "ok": bool(result.get("ok")),
            "path": path,
            "limit_seconds": limit_seconds,
            "command_result": result,
        }

    def recording_info(self):
        return self._run_v1(["termux-microphone-record", "-i"], timeout=8)

    def stop_audio_recording(self):
        return self._run_v1(["termux-microphone-record", "-q"], timeout=8)

    def fingerprint_file(self, path):
        path = os.path.abspath(os.path.expanduser(str(path)))
        if not os.path.isfile(path):
            return {"ok": False, "error": "file not found", "path": path}
        digest = hashlib.sha256()
        size = 0
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        return {
            "ok": True,
            "path": path,
            "bytes": size,
            "sha256": digest.hexdigest(),
        }

    def check_in(self):
        state = {
            "last_check_in_at": _utc_now_v1(),
            "last_check_in_unix": time.time(),
            "state": "active",
            "policy": dict(DEFAULT_INACTIVITY_POLICY_V1),
        }
        _atomic_json_write_v1(self.inactivity_path, state)
        return state

    def evaluate_inactivity(self, now=None):
        state = self._load_json_v1(self.inactivity_path, {})
        if not isinstance(state, dict) or not state.get("last_check_in_unix"):
            return {
                "state": "uninitialized",
                "action": "check_in_required",
                "destructive_action": False,
            }
        policy = dict(DEFAULT_INACTIVITY_POLICY_V1)
        policy.update(state.get("policy") if isinstance(state.get("policy"), dict) else {})
        current = float(time.time() if now is None else now)
        elapsed = max(0.0, current - float(state["last_check_in_unix"]))
        if elapsed >= float(policy["lock_after_seconds"]):
            status = "locked_pending_verification"
        elif elapsed >= float(policy["warning_after_seconds"]):
            status = "warning"
        else:
            status = "active"
        return {
            "state": status,
            "seconds_since_check_in": elapsed,
            "destructive_action": False,
            "destructive_auto_delete": False,
            "note": "Missed check-ins never trigger irreversible deletion. Any future purge requires a separate verified and audited approval path.",
        }

    def status(self):
        return {
            "module": "selma0_selmasafe_android_v1",
            "local_device": dict(self.local_identity),
            "peer_devices": len(self.list_devices()),
            "capabilities": self.capabilities(),
            "inactivity": self.evaluate_inactivity(),
            "outbox_dir": self.outbox_dir,
            "recordings_dir": self.recordings_dir,
        }
