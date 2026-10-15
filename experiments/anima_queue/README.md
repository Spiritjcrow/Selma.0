# Selma Anima queue validation

This is a **dry-run planner**, not an autonomous coding agent. Run `python experiments/anima_queue/queue_dry_run.py` to view ready tasks. Run `python -m unittest discover -s experiments/anima_queue -p 'test_*.py' -v` for tests.

The GitHub Actions workflow runs tests on pushes/PRs, manual dispatch, and on a six-hour schedule **once the workflow exists on the repository default branch**. Scheduled GitHub Actions can be delayed or disabled by GitHub and are not always-on.

No paid cloud server, unattended code changes, agent credentials, or merge permissions are provisioned here. Those require a separate authorized executor and security review. See #68, #69 and draft PR #70.
