def register_selmasafe_tools(registry, safety_guardian):
    """Register SelmaSafe capabilities behind the standard command policy."""

    registry.register(
        "safety.selmasafe.status",
        lambda: safety_guardian.selmasafe_status(),
        risk="sensitive_read",
        description="Return SelmaSafe device/fan-out/recording capability status.",
    )
    registry.register(
        "safety.selmasafe.enroll_device",
        lambda label="", role="family", device_id=None: safety_guardian.enroll_device(
            label=label,
            role=role,
            device_id=device_id,
        ),
        risk="write",
        description="Enroll a user-approved family device using a SelmaSafe-generated or supplied logical device ID; IMEI is not required.",
    )
    registry.register(
        "safety.selmasafe.list_devices",
        lambda: {"devices": safety_guardian.list_devices()},
        risk="sensitive_read",
        description="List user-enrolled SelmaSafe devices.",
    )
    registry.register(
        "safety.selmasafe.check_in",
        lambda: safety_guardian.check_in(),
        risk="write",
        description="Record an explicit SelmaSafe wellbeing/privacy check-in.",
    )
    registry.register(
        "safety.selmasafe.recording_info",
        lambda: safety_guardian.recording_info(),
        risk="sensitive_read",
        description="Read the current Termux microphone recording state when available.",
    )
    registry.register(
        "safety.selmasafe.stop_recording",
        lambda: safety_guardian.stop_audio_recording(),
        risk="external_effect",
        description="Stop the current SelmaSafe microphone recording after explicit approval.",
    )
