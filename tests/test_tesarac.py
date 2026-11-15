import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "tesarac.py"
spec = importlib.util.spec_from_file_location("tesarac", SOURCE)
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)

class TesaracTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.ledger = self.dir / "ledger.jsonl"

    def test_chain_init_append_verify(self):
        a = t.init(self.ledger)
        b = t.note(self.ledger, "checkpoint", "https://github.com/a/b/issues/4")
        got = t.verify_bytes(self.ledger.read_bytes(), expected_sha=b["head_sha256"], expected_count=2)
        self.assertEqual(got["records"], 2)
        self.assertNotEqual(a["head_sha256"], b["head_sha256"])

    def test_not_initialized_fails(self):
        with self.assertRaises(t.EvidenceError): t.note(self.ledger, "test")

    def test_no_double_init(self):
        t.init(self.ledger)
        with self.assertRaises(t.EvidenceError): t.init(self.ledger)

    def test_tamper_detected(self):
        t.init(self.ledger)
        t.note(self.ledger, "original")
        raw = self.ledger.read_bytes().replace(b"original", b"modified")
        with self.assertRaises(t.EvidenceError): t.verify_bytes(raw)

    def test_trailing_partial_detected(self):
        t.init(self.ledger)
        with self.assertRaises(t.EvidenceError): t.verify_bytes(self.ledger.read_bytes()[:-1])

    def test_truncation_requires_external_anchor(self):
        t.init(self.ledger)
        end = t.note(self.ledger, "last")
        trunc = self.ledger.read_bytes().splitlines(keepends=True)[0]
        self.assertEqual(t.verify_bytes(trunc)["records"], 1)
        with self.assertRaises(t.EvidenceError): t.verify_bytes(trunc, end["head_sha256"], 2)

    def test_duplicate_keys_rejected(self):
        with self.assertRaises(t.EvidenceError): t.strict_json('{"x":1,"x":2}')
        with self.assertRaises(t.EvidenceError): t.strict_json('{"x":NaN}')

    def test_chunk_partition_exact_ranges(self):
        src = self.dir / "fixture.pcap"
        src.write_bytes(b"a" * 1024 + b"b" * 19)
        result = t.partition(src, 1024)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(len(result["parts"]), 2)
        self.assertEqual(result["parts"][1]["start"], 1024)
        self.assertEqual(result["parts"][1]["end_exclusive"], 1043)

    def test_partition_rejects_symlink(self):
        src = self.dir / "src"
        src.write_bytes(b"hello")
        dest = self.dir / "link"
        dest.symlink_to(src)
        self.assertEqual(t.partition(dest)["verdict"], "BLOCKED")

    def test_probe_missing_tool_blocks(self):
        with patch.object(t.shutil, "which", return_value=None):
            self.assertEqual(t.probe("interfaces")["verdict"], "BLOCKED")

    def test_probe_never_records_raw_output(self):
        class Done:
            stdout = b"192.168.1.6 secret MAC AA:00:00"
            stderr = b""
            returncode = 0
        with patch.object(t.shutil, "which", return_value="/usr/bin/ifconfig"), patch.object(t.subprocess, "run", return_value=Done()):
            result = t.probe("interfaces")
        self.assertEqual(result["verdict"], "PASS")
        self.assertNotIn("192.168", json.dumps(result))
        self.assertEqual(result["output_sha256"], t.sha(Done.stdout))

    def test_reject_forward_dependency(self):
        with self.assertRaises(t.EvidenceError):
            t.check_plan({"version": 1, "units": [{"id": "b", "kind": "note", "depends_on": ["a"]}]})

    def test_mosaic_note_only_not_a_pass(self):
        t.init(self.ledger)
        plan = self.dir / "plan.json"
        plan.write_text(json.dumps({"version": 1, "units": [{"id": "s", "kind": "note", "segments": ["a", "b"]}]}))
        result = t.run_mosaic(self.ledger, plan)
        self.assertEqual(result["verdict"], "NOT_RUN")
        self.assertEqual(t.verify_bytes(self.ledger.read_bytes())["records"], 3)

    def test_mosaic_missing_dependency_blocks(self):
        t.init(self.ledger)
        plan = self.dir / "plan.json"
        plan.write_text(json.dumps({"version": 1, "units": [
            {"id":"first","kind":"note","segments":["hello"]},
            {"id":"second","kind":"interfaces","depends_on":["first"]}]}))
        result = t.run_mosaic(self.ledger, plan)
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertEqual(result["units"][1]["verdict"], "BLOCKED")

    def test_mosaic_required_probe_pass(self):
        t.init(self.ledger)
        plan = self.dir / "plan.json"
        plan.write_text(json.dumps({"version":1,"units":[{"id":"intro","kind":"note","segments":["hello"],"required":False},{"id":"net","kind":"interfaces"}]}))
        with patch.object(t, "probe", return_value={"verdict":"PASS", "output_sha256": "0" * 64}):
            self.assertEqual(t.run_mosaic(self.ledger, plan)["verdict"], "PASS")

    def test_mosaic_duplicate_json_rejected(self):
        t.init(self.ledger)
        plan = self.dir / "plan.json"
        plan.write_text('{"version":1,"version":1,"units":[]}')
        with self.assertRaises(t.EvidenceError): t.run_mosaic(self.ledger, plan)

if __name__ == "__main__": unittest.main()
