# Avatar state controller v1

This controller is a deterministic policy-free state machine. It consumes already-authorized internal events and emits effect names for platform adapters. It does not open microphones or cameras, render windows, play audio, access networks, or authorize Selma tools.

The allowed states come directly from Gate 1: `IDLE`, `LISTENING`, `THINKING`, `SPEAKING`, `INTERRUPTED`, `SLEEPING`, and `ERROR`. Sequence numbers reject replayed/out-of-order transitions. Model and autonomous events must carry the currently active generation ID; barge-in clears that ID so delayed model output becomes stale.

User interruption emits `cancel_generation` and `drain_audio`, then deterministically recovers to `LISTENING` or `IDLE` according to the locally configured mode. The kill switch clears active generation state, returns to quiet `IDLE`, and emits stop requests for audio, animation, capture, and autonomy. Restart is explicit and remains quiet; it does not resume capture or autonomous behavior.

Effects are requests, not claims. Platform adapters must execute them through Selma's single permission and audit control plane and report unsupported operations honestly. No timing, audio-drain, camera-stop, or physical-device latency claim is made by these unit tests.

Run `python3 -m unittest tests.test_avatar_state -v`.
