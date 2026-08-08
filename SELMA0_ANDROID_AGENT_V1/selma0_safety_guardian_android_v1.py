import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone

SELMA0_BASE_V1 = os.path.expanduser(os.getenv("SELMA0_BASE_V1", "~/SELMA0_ANDROID_AGENT_V1"))
SELMA0_SAFETY_DIR_V1 = os.path.join(SELMA0_BASE_V1, "selma0_safety_android_v1")
SELMA0_SAFETY_CONFIG_V1 = os.path.join(SELMA0_SAFETY_DIR_V1, "safety_profile_v1.json")
SELMA0_SAFETY_AUDIT_V1 = os.path.join(SELMA0_SAFETY_DIR_V1, "safety_events_v1.jsonl")
os.makedirs(SELMA0_SAFETY_DIR_V1, exist_ok=True)

DEFAULT_PROFILE_V1 = {
    "trusted_contacts": [],
    "sos_message": "Selma.0 safety alert. I intentionally activated SOS and may need help.",
    "include_location_in_sos": True,
    "send_sms_on_sos": False,
}


def _utc_now_v1():
    return datetime.now(timezone.utc).isoformat()


def _json_compact_v1(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class Selma0SafetyGuardianAndroidV1:
    """Local, auditable safety helper for the Selma.0 Android/Termux runtime.

    This module records user-reported observations and performs explicitly requested
    local safety actions. It does not infer criminal identity, claim surveillance is
    occurring, or automatically contact emergency services.
    """

    def __init__(self, profile_path=SELMA0_SAFETY_CONFIG_V1, audit_path=SELMA0_SAFETY_AUDIT_V1):
        self.profile_path = profile_path
        self.audit_path = audit_path
        self.profile = self._load_profile_v1()

    def _load_profile_v1(self):
        if not os.path.exists(self.profile_path):
            self._save_profile_v1(DEFAULT_PROFILE_V1)
            return dict(DEFAULT_PROFILE_V1)
        try:
            with open(self.profile_path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, ValueError):
            raw = {}
        profile = dict(DEFAULT_PROFILE_V1)
        if isinstance(raw, dict):
            profile.update(raw)
        if not isinstance(profile.get("trusted_contacts"), list):
            profile["trusted_contacts"] = []
        return profile

    def _save_profile_v1(self, profile):
        os.makedirs(os.path.dirname(self.profile_path), exist_ok=True)
        tmp = self.profile_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(profile, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp, self.profile_path)

    def update_profile(self, updates):
        allowed = {"trusted_contacts", "sos_message", "include_location_in_sos", "send_sms_on_sos"}
        for key, value in dict(updates or {}).items():
            if key in allowed:
                self.profile[key] = value
        if not isinstance(self.profile.get("trusted_contacts"), list):
            raise ValueError("trusted_contacts must be a list")
        self._save_profile_v1(self.profile)
        return self.public_profile()

    def public_profile(self):
        contacts = []
        for item in self.profile.get("trusted_contacts", []):
            if isinstance(item, dict):
                contacts.append({
                    "name": str(item.get("name", "")).strip(),
                    "number": str(item.get("number", "")).strip(),
                })
        return {
            "trusted_contacts": contacts,
            "sos_message": str(self.profile.get("sos_message", DEFAULT_PROFILE_V1["sos_message"])),
            "include_location_in_sos": bool(self.profile.get("include_location_in_sos", True)),
            "send_sms_on_sos": bool(self.profile.get("send_sms_on_sos", False)),
        }

    def capabilities(self):
        names = [
            "termux-location",
            "termux-notification",
            "termux-sms-send",
            "termux-battery-status",
            "termux-wifi-connectioninfo",
        ]
        return {name: bool(shutil.which(name)) for name in names}

    def _run_v1(self, argv, timeout=12):
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
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        parsed = stdout
        if stdout:
            try:
                parsed = json.loads(stdout)
            except ValueError:
                pass
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": parsed,
            "stderr": stderr,
        }

    def location_snapshot(self):
        first = self._run_v1(["termux-location", "-p", "gps", "-r", "once"], timeout=15)
        if first.get("ok"):
            return first
        fallback = self._run_v1(["termux-location", "-p", "network", "-r", "once"], timeout=10)
        if fallback.get("ok"):
            return fallback
        return {"ok": False, "gps": first, "network": fallback}

    def device_snapshot(self):
        return {
            "captured_at": _utc_now_v1(),
            "battery": self._run_v1(["termux-battery-status"], timeout=6),
            "wifi": self._run_v1(["termux-wifi-connectioninfo"], timeout=6),
        }

    def _last_hash_v1(self):
        if not os.path.exists(self.audit_path):
            return "0" * 64
        try:
            with open(self.audit_path, "rb") as handle:
                lines = handle.readlines()
            if not lines:
                return "0" * 64
            row = json.loads(lines[-1].decode("utf-8"))
            return str(row.get("event_hash", "0" * 64))
        except (OSError, ValueError, UnicodeDecodeError):
            return "0" * 64

    def _append_event_v1(self, event_type, summary, details=None):
        event = {
            "event_id": str(uuid.uuid4()),
            "recorded_at": _utc_now_v1(),
            "unix_time": time.time(),
            "event_type": str(event_type),
            "summary": str(summary).strip(),
            "details": details if isinstance(details, dict) else {},
            "previous_hash": self._last_hash_v1(),
        }
        material = _json_compact_v1(event).encode("utf-8")
        event["event_hash"] = hashlib.sha256(material).hexdigest()
        with open(self.audit_path, "a", encoding="utf-8") as handle:
            handle.write(_json_compact_v1(event) + "\n")
        return event

    def recent_events(self, limit=50):
        limit = max(1, min(int(limit), 200))
        if not os.path.exists(self.audit_path):
            return []
        events = []
        try:
            with open(self.audit_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            return []
        return events[-limit:]

    def record_incident(self, summary, details=None, source="user_report", confidence=None, include_device_snapshot=False):
        summary = str(summary).strip()
        if not summary:
            raise ValueError("summary is required")
        payload = dict(details or {}) if isinstance(details, dict) else {}
        payload["source"] = str(source or "user_report")
        if confidence is not None:
            payload["confidence"] = confidence
        if include_device_snapshot:
            payload["device_snapshot"] = self.device_snapshot()
        return self._append_event_v1("incident", summary, payload)

    def local_alert(self, title, content):
        return self._run_v1([
            "termux-notification",
            "--id", "selma0-safety-v1",
            "--priority", "high",
            "--title", str(title),
            "--content", str(content),
        ], timeout=8)

    def _format_location_v1(self, result):
        if not result.get("ok"):
            return None
        data = result.get("stdout")
        if not isinstance(data, dict):
            return None
        lat = data.get("latitude")
        lon = data.get("longitude")
        acc = data.get("accuracy")
        if lat is None or lon is None:
            return None
        suffix = f" accuracy={acc}m" if acc is not None else ""
        return f"location={lat},{lon}{suffix}"

    def activate_sos(self, reason="", confirmed=False):
        if confirmed is not True:
            raise ValueError("SOS requires confirmed=true")
        reason = str(reason).strip()
        location_result = self.location_snapshot() if self.profile.get("include_location_in_sos", True) else {"ok": False, "skipped": True}
        location_text = self._format_location_v1(location_result)
        message = str(self.profile.get("sos_message", DEFAULT_PROFILE_V1["sos_message"]))
        if reason:
            message += f" Reason: {reason}"
        if location_text:
            message += f" {location_text}"

        alert_result = self.local_alert("Selma.0 SOS ACTIVE", message)
        sms_results = []
        if bool(self.profile.get("send_sms_on_sos", False)):
            for contact in self.profile.get("trusted_contacts", []):
                if not isinstance(contact, dict):
                    continue
                number = str(contact.get("number", "")).strip()
                if not number:
                    continue
                result = self._run_v1(["termux-sms-send", "-n", number, message], timeout=10)
                sms_results.append({"name": str(contact.get("name", "")), "number": number, "result": result})

        event = self._append_event_v1(
            "sos",
            "User-confirmed Selma.0 SOS activation",
            {
                "reason": reason,
                "location": location_result,
                "local_alert": alert_result,
                "sms_results": sms_results,
                "sms_enabled": bool(self.profile.get("send_sms_on_sos", False)),
            },
        )
        return {
            "event": event,
            "message": message,
            "local_alert": alert_result,
            "sms_results": sms_results,
            "note": "This SOS does not call or text 911 automatically. Use emergency services directly when immediate danger exists.",
        }

    def status(self):
        return {
            "module": "selma0_safety_guardian_android_v1",
            "profile": self.public_profile(),
            "capabilities": self.capabilities(),
            "audit_path": self.audit_path,
            "events_recorded": len(self.recent_events(200)),
        }
