#!/usr/bin/env python3
"""SelmaOS experimental queue dry-run. No external execution or network access."""
import argparse
import json
from pathlib import Path

TASKS = [
    {"id": "A1", "depends_on": [], "description": "Audit coordinator and permissions"},
    {"id": "S1", "depends_on": ["A1"], "description": "Speaker diarization prototype"},
    {"id": "A2", "depends_on": ["A1"], "description": "Bounded affect-state simulation"},
    {"id": "N1", "depends_on": ["S1", "A2"], "description": "Naturalism adapter"},
    {"id": "T1", "depends_on": ["N1"], "description": "Independent White tests"},
    {"id": "U1", "depends_on": ["T1"], "description": "UltraViolet security review"},
]
VALID = {"queued", "blocked", "ready", "done"}

def evaluate(states):
    if set(states) - {t["id"] for t in TASKS}:
        raise ValueError("Unknown task ID")
    if set(states.values()) - VALID:
        raise ValueError("Invalid task state")
    out = []
    for task in TASKS:
        current = states.get(task["id"], "queued")
        if current == "done" and any(states.get(d) != "done" for d in task["depends_on"]):
            raise ValueError("Completed task has incomplete dependency: " + task["id"])
        status = "ready" if current in ("queued", "ready") and all(states.get(d) == "done" for d in task["depends_on"]) else current
        out.append({**task, "status": status})
    return out

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--state", type=Path, help="Optional JSON task-id to state map")
    args = p.parse_args()
    states = json.loads(args.state.read_text()) if args.state else {}
    if not isinstance(states, dict):
        raise ValueError("State must be a JSON object")
    print(json.dumps({"mode": "dry-run", "execution_enabled": False, "tasks": evaluate(states)}, indent=2))

if __name__ == "__main__":
    main()
