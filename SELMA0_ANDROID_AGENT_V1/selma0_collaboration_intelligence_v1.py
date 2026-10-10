"""Selma.0 V1 collaboration assessment and governed learning.

No raw utterances, passwords, tokens, model thoughts, or unrestricted agent actions.
Inputs are caller-labeled turn *metadata*, not evidence of audio speaker identity.
"""

import hashlib
import json
import os
import sqlite3
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

ACTIONS = frozenset({"ack", "ask", "propose", "handoff", "deliver", "verify", "block"})
SOURCES = frozenset({"voice_transcript", "human", "tool", "import"})
EVIDENCE = frozenset({"none", "claim", "test", "external_verified"})
FEEDBACK = frozenset({"useful", "unproductive", "needs_review"})
TURN_FIELDS = frozenset({"speaker_id", "speaker_confidence", "action_kind", "artifact_produced", "evidence", "source_kind"})
DEFAULT_POLICY = {"version": 1, "revision": 1, "ack_streak_limit": 3,
                  "max_turns_no_artifact": 5, "speaker_confidence_floor": 0.70}
POLICY_BOUNDS = {"ack_streak_limit": (2, 6), "max_turns_no_artifact": (3, 10),
                 "speaker_confidence_floor": (0.5, 0.95)}
MAX_TURNS = 64


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def validate_turns(turns):
    if not isinstance(turns, list) or not 1 <= len(turns) <= MAX_TURNS:
        raise ValueError("turns must be a list containing 1..64 metadata entries")
    normalized = []
    for turn in turns:
        if not isinstance(turn, dict) or set(turn) - TURN_FIELDS:
            raise ValueError("turn contains unsupported fields; do not submit raw transcripts")
        speaker = turn.get("speaker_id")
        action = turn.get("action_kind")
        evidence = turn.get("evidence", "none")
        source = turn.get("source_kind", "human")
        confidence = turn.get("speaker_confidence", 0.0 if speaker == "unknown" else 1.0)
        artifact = turn.get("artifact_produced", False)
        if (not isinstance(speaker, str) or not 1 <= len(speaker) <= 40
                or not all(c.isalnum() or c in "_-" for c in speaker)):
            raise ValueError("speaker_id must be a short explicit label")
        if action not in ACTIONS or evidence not in EVIDENCE or source not in SOURCES:
            raise ValueError("action_kind, evidence, or source_kind invalid")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise ValueError("speaker_confidence must be between 0 and 1")
        if not isinstance(artifact, bool):
            raise ValueError("artifact_produced must be a boolean")
        normalized.append({"speaker_id": speaker, "speaker_confidence": float(confidence),
                           "action_kind": action, "artifact_produced": artifact,
                           "evidence": evidence, "source_kind": source})
    return normalized


class Selma0CollaborationIntelligenceV1:
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir or os.getenv("SELMA0_COLLAB_DATA_DIR_V1", "~/.selma0/collaboration_v1")).expanduser()
        self._lock = threading.RLock()
        self._initialized = False

    def _prepare(self):
        if self._initialized:
            return
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.data_dir, 0o700)
        self.policy_path = self.data_dir / "policy.v1.json"
        self.db_path = self.data_dir / "observations.v1.sqlite3"
        if not self.policy_path.exists():
            self._write_policy(DEFAULT_POLICY)
        if not self.db_path.exists():
            fd = os.open(self.db_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        os.chmod(self.db_path, 0o600)
        with sqlite3.connect(self.db_path) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS observations (
                fingerprint TEXT PRIMARY KEY, recorded_at TEXT NOT NULL,
                policy_revision INTEGER NOT NULL, feedback TEXT NOT NULL,
                loop_detected INTEGER NOT NULL, turn_count INTEGER NOT NULL,
                speaker_ambiguity INTEGER NOT NULL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS policy_history (
                revision INTEGER PRIMARY KEY, changed_at TEXT NOT NULL,
                config_json TEXT NOT NULL)""")
        self._initialized = True

    def _write_policy(self, policy):
        fd, name = tempfile.mkstemp(prefix=".policy-", dir=self.data_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(policy, file, indent=2, sort_keys=True)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.chmod(name, 0o600)
            os.replace(name, self.data_dir / "policy.v1.json")
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _policy(self):
        self._prepare()
        with self.policy_path.open(encoding="utf-8") as f:
            policy = json.load(f)
        if not isinstance(policy, dict) or set(policy) != set(DEFAULT_POLICY) or policy.get("version") != 1:
            raise ValueError("unknown policy schema; refusing to operate")
        self._validate_updates({k: policy[k] for k in POLICY_BOUNDS})
        return policy

    @staticmethod
    def _validate_updates(updates):
        if not isinstance(updates, dict) or not updates or set(updates) - set(POLICY_BOUNDS):
            raise ValueError("only bounded collaboration thresholds may be changed")
        for k, v in updates.items():
            low, high = POLICY_BOUNDS[k]
            if (isinstance(v, bool) or not isinstance(v, (int, float)) or
                    (k != "speaker_confidence_floor" and not isinstance(v, int)) or not low <= v <= high):
                raise ValueError(f"{k} outside permitted bounds")

    @staticmethod
    def _evaluate(turns, policy):
        streak = []
        for turn in reversed(turns):
            if turn["action_kind"] in {"ack", "ask", "handoff"} and not turn["artifact_produced"]:
                streak.append(turn)
            else:
                break
        repetitive = len(streak) >= policy["ack_streak_limit"] and len({t["speaker_id"] for t in streak}) >= 2
        no_artifact = len(turns) >= policy["max_turns_no_artifact"] and not any(
            t["artifact_produced"] for t in turns[-policy["max_turns_no_artifact"]:])
        low_speaker = any(t["speaker_id"] == "unknown" or
                          t["speaker_confidence"] < policy["speaker_confidence_floor"] for t in turns)
        unverified = any(t["action_kind"] == "deliver" and t["evidence"] in {"none", "claim"} for t in turns)
        flags = []
        if repetitive:
            flags.append("reciprocity_loop")
        if no_artifact:
            flags.append("no_verified_progress")
        if low_speaker:
            flags.append("speaker_identity_uncertain")
        if unverified:
            flags.append("delivery_unverified")
        if repetitive:
            next_action = "assign_one_executor_and_request_specific_artifact"
        elif low_speaker:
            next_action = "confirm_speaker_labels_before_handoff"
        elif unverified:
            next_action = "request_reproducible_test_evidence"
        elif no_artifact:
            next_action = "request_concrete_deliverable"
        else:
            next_action = "continue_with_named_owner_and_expected_output"
        return {"schema_version": 1, "policy_revision": policy["revision"],
                "turn_count": len(turns), "flags": flags,
                "loop_detected": repetitive, "speaker_ambiguity": low_speaker,
                "next_action": next_action,
                "epistemic_status": "deterministic_metadata_heuristics_not_speaker_authentication"}

    def assess(self, turns):
        normalized = validate_turns(turns)
        with self._lock:
            return self._evaluate(normalized, self._policy())

    def record_observation(self, turns, feedback):
        if feedback not in FEEDBACK:
            raise ValueError("feedback must be useful, unproductive, or needs_review")
        normalized = validate_turns(turns)
        with self._lock:
            policy = self._policy()
            result = self._evaluate(normalized, policy)
            fingerprint = hashlib.sha256(json.dumps(normalized, sort_keys=True,
                                       separators=(",", ":")).encode()).hexdigest()
            with sqlite3.connect(self.db_path) as con:
                cursor = con.execute("""INSERT OR IGNORE INTO observations
                    (fingerprint,recorded_at,policy_revision,feedback,loop_detected,turn_count,speaker_ambiguity)
                    VALUES (?,?,?,?,?,?,?)""", (fingerprint, utc_now(), policy["revision"], feedback,
                      int(result["loop_detected"]), len(normalized), int(result["speaker_ambiguity"])))
            return {"recorded": cursor.rowcount == 1, "fingerprint_sha256": fingerprint,
                    "assessment": result, "stored_fields": "derived_metadata_only"}

    def suggest_policy(self):
        with self._lock:
            p = self._policy()
            with sqlite3.connect(self.db_path) as con:
                rows = con.execute("SELECT feedback,loop_detected FROM observations WHERE policy_revision=?",
                                   (p["revision"],)).fetchall()
            misses = sum(f == "unproductive" and not loop for f, loop in rows)
            false_alarms = sum(f == "useful" and loop for f, loop in rows)
            update = {}
            if misses >= 3 and misses > false_alarms and p["ack_streak_limit"] > 2:
                update["ack_streak_limit"] = p["ack_streak_limit"] - 1
            elif false_alarms >= 3 and false_alarms > misses and p["ack_streak_limit"] < 6:
                update["ack_streak_limit"] = p["ack_streak_limit"] + 1
            return {"policy_revision": p["revision"], "observations": len(rows),
                    "misses": misses, "false_alarms": false_alarms,
                    "suggested_updates": update, "applied": False,
                    "requires": "human_review_and_approved_config_write"}

    def apply_policy(self, updates, expected_revision):
        self._validate_updates(updates)
        with self._lock:
            policy = self._policy()
            if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision != policy["revision"]:
                raise ValueError("policy revision mismatch")
            next_policy = dict(policy)
            next_policy.update(updates)
            next_policy["revision"] += 1
            with sqlite3.connect(self.db_path) as con:
                con.execute("INSERT INTO policy_history VALUES (?,?,?)",
                            (next_policy["revision"], utc_now(), json.dumps(next_policy, sort_keys=True)))
            self._write_policy(next_policy)
            return {"applied": True, "revision": next_policy["revision"],
                    "policy": next_policy}


def register_collaboration_tools(registry):
    """Register with Selma command policy. Never create an alternate direct HTTP route."""
    engine = Selma0CollaborationIntelligenceV1()
    registry.register("collab.assess", engine.assess, risk="read",
                      description="Assess strictly labeled, non-sensitive collaboration metadata (no transcript)")
    registry.register("collab.suggest_policy", engine.suggest_policy, risk="read",
                      description="Suggest bounded thresholds from feedback; does not alter policy")
    registry.register("collab.record_observation", engine.record_observation, risk="write",
                      description="Write a deduplicated, metadata-only feedback observation with explicit approval")
    registry.register("collab.apply_policy", engine.apply_policy, risk="write",
                      description="Apply allowlisted bounded threshold changes with explicit approval and revision check")
