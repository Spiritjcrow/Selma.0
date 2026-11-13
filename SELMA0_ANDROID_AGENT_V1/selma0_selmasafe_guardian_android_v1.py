import os

from selma0_safety_guardian_android_v1 import Selma0SafetyGuardianAndroidV1
from selma0_selmasafe_android_v1 import Selma0SelmaSafeAndroidV1


DEFAULT_SELMA_SAFE_PROFILE_V1 = {
    "record_audio_on_sos": True,
    "record_limit_seconds": 300,
    "selmasafe_fanout_enabled": True,
    "selmasafe_emergency_level": "critical",
}


class Selma0SelmaSafeGuardianAndroidV1(Selma0SafetyGuardianAndroidV1):
    """Safety Guardian extension that adds SelmaSafe SOS behaviors.

    Local SOS remains available even when cross-device transport is not configured.
    Remote fan-out fails closed unless peer devices are enrolled and the shared
    HMAC secret is present. Recording begins only after an explicitly confirmed SOS.
    """

    def __init__(
        self,
        profile_path=None,
        audit_path=None,
        selmasafe_base_dir=None,
        selmasafe_runner=None,
    ):
        kwargs = {}
        if profile_path is not None:
            kwargs["profile_path"] = profile_path
        if audit_path is not None:
            kwargs["audit_path"] = audit_path
        super().__init__(**kwargs)
        safe_dir = selmasafe_base_dir or os.path.join(
            os.path.dirname(self.profile_path),
            "selmasafe_v1",
        )
        self.selmasafe = Selma0SelmaSafeAndroidV1(
            runner=selmasafe_runner or self._run_v1,
            base_dir=safe_dir,
        )
        changed = False
        for key, value in DEFAULT_SELMA_SAFE_PROFILE_V1.items():
            if key not in self.profile:
                self.profile[key] = value
                changed = True
        if changed:
            self._save_profile_v1(self.profile)

    def update_profile(self, updates):
        updates = dict(updates or {})
        parent_keys = {
            "trusted_contacts",
            "sos_message",
            "include_location_in_sos",
            "send_sms_on_sos",
        }
        safe_keys = set(DEFAULT_SELMA_SAFE_PROFILE_V1)

        parent_updates = {key: value for key, value in updates.items() if key in parent_keys}
        if parent_updates:
            super().update_profile(parent_updates)

        if "record_audio_on_sos" in updates:
            self.profile["record_audio_on_sos"] = bool(updates["record_audio_on_sos"])
        if "selmasafe_fanout_enabled" in updates:
            self.profile["selmasafe_fanout_enabled"] = bool(updates["selmasafe_fanout_enabled"])
        if "record_limit_seconds" in updates:
            self.profile["record_limit_seconds"] = max(
                10,
                min(int(updates["record_limit_seconds"]), 3600),
            )
        if "selmasafe_emergency_level" in updates:
            level = str(updates["selmasafe_emergency_level"] or "").strip().lower()
            if level not in {"advisory", "urgent", "critical"}:
                raise ValueError("selmasafe_emergency_level must be advisory, urgent, or critical")
            self.profile["selmasafe_emergency_level"] = level

        ignored = set(updates) - parent_keys - safe_keys
        if ignored:
            # Preserve parent behavior: unknown profile keys are ignored rather than persisted.
            pass

        self._save_profile_v1(self.profile)
        return self.public_profile()

    def public_profile(self):
        profile = super().public_profile()
        profile.update({
            "record_audio_on_sos": bool(self.profile.get("record_audio_on_sos", True)),
            "record_limit_seconds": max(
                10,
                min(int(self.profile.get("record_limit_seconds", 300)), 3600),
            ),
            "selmasafe_fanout_enabled": bool(
                self.profile.get("selmasafe_fanout_enabled", True)
            ),
            "selmasafe_emergency_level": str(
                self.profile.get("selmasafe_emergency_level", "critical")
            ),
        })
        return profile

    def capabilities(self):
        caps = super().capabilities()
        caps["termux-microphone-record"] = bool(
            self.selmasafe.capabilities().get("microphone_record")
        )
        caps["selmasafe"] = self.selmasafe.capabilities()
        return caps

    def enroll_device(self, label, role="family", device_id=None):
        return self.selmasafe.enroll_device(
            label=label,
            role=role,
            device_id=device_id,
        )

    def list_devices(self):
        return self.selmasafe.list_devices()

    def selmasafe_status(self):
        return self.selmasafe.status()

    def check_in(self):
        return self.selmasafe.check_in()

    def recording_info(self):
        return self.selmasafe.recording_info()

    def stop_audio_recording(self):
        return self.selmasafe.stop_audio_recording()

    def activate_sos(self, reason="", confirmed=False):
        if confirmed is not True:
            raise ValueError("SOS requires confirmed=true")

        reason = str(reason or "").strip()
        recording_result = {
            "ok": False,
            "skipped": True,
            "reason": "record_audio_on_sos disabled",
        }
        if bool(self.profile.get("record_audio_on_sos", True)):
            recording_result = self.selmasafe.start_audio_recording(
                limit_seconds=self.profile.get("record_limit_seconds", 300)
            )

        fanout_result = {
            "ok": False,
            "queued": False,
            "skipped": True,
            "reason": "selmasafe_fanout_enabled disabled",
        }
        if bool(self.profile.get("selmasafe_fanout_enabled", True)):
            fanout_result = self.selmasafe.queue_sos_fanout(
                reason=reason,
                emergency_level=self.profile.get("selmasafe_emergency_level", "critical"),
                request_recording=bool(self.profile.get("record_audio_on_sos", True)),
            )

        local_result = super().activate_sos(reason=reason, confirmed=True)
        check_in_result = self.selmasafe.check_in()
        extension_event = self._append_event_v1(
            "selmasafe_sos_extension",
            "SelmaSafe SOS extension executed",
            {
                "recording": recording_result,
                "fanout": fanout_result,
                "check_in": check_in_result,
            },
        )
        local_result["selmasafe"] = {
            "recording": recording_result,
            "fanout": fanout_result,
            "event": extension_event,
        }
        return local_result

    def status(self):
        status = super().status()
        status["selmasafe"] = self.selmasafe.status()
        return status
