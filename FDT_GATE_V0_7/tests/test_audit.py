import json
import tempfile
import unittest
from pathlib import Path

from fdt_gate.audit import AuditLedger


class AuditTests(unittest.TestCase):
    def test_tamper_detected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "audit.jsonl"
            a = AuditLedger(p); a.append({"x": 1}); a.append({"x": 2})
            self.assertTrue(a.verify()[0])
            lines = p.read_text("utf-8").splitlines(); rec = json.loads(lines[0]); rec["event"]["x"] = 99
            lines[0] = json.dumps(rec); p.write_text("\n".join(lines) + "\n", "utf-8")
            self.assertFalse(a.verify()[0])


if __name__ == "__main__": unittest.main()
