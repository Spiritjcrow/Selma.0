#!/usr/bin/env python3
import json, sys, tempfile, unittest
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = AGENT_ROOT / "skills" / "project_recovery_inspector_v1"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from project_recovery_inspector_v1 import inspect_project, inspect_workspace, register_project_recovery_tools, write_report

class FakeRegistry:
    def __init__(self): self.tools={}
    def register(self,name,handler,risk,description="",enabled=True):
        self.tools[name]={"handler":handler,"risk":risk,"description":description,"enabled":enabled}

class RecoveryInspectorTests(unittest.TestCase):
    def _manifest(self,root,project_id="demo"):
        p=Path(root)/"manifest.json"
        p.write_text(json.dumps({"project_id":project_id,"name":"Demo","keywords":["demo","gate"]}),encoding="utf-8")
        return p

    def test_ci_startup_failure_is_classified_as_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=self._manifest(root)
            (root/"status.md").write_text("Demo Gate is blocked. GitHub completed as startup_failure / BuildFailed and No jobs were run.",encoding="utf-8")
            report=inspect_project(str(manifest),source_roots=[str(root)])
            self.assertIn("ci_admission",{b["category"] for b in report["blockers"]})
            first=next(b for b in report["blockers"] if b["category"]=="ci_admission")
            self.assertIn("Restore the CI control plane",first["native_fix"])

    def test_unchecked_acceptance_is_evidence_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=self._manifest(root)
            (root/"gate.md").write_text("- [ ] physical-device acceptance evidence\n",encoding="utf-8")
            report=inspect_project(str(manifest),source_roots=[str(root)])
            self.assertTrue(any(b["category"]=="unverified_acceptance" for b in report["blockers"]))
            self.assertFalse(report["truth_policy"]["mock_success_allowed"])

    def test_chat_export_is_keyword_filtered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=self._manifest(root);export=root/"conversations.json"
            export.write_text(json.dumps([{"title":"Demo work","mapping":{
                "1":{"message":{"author":{"role":"user"},"content":{"parts":["Demo is waiting for the gate."]}}},
                "2":{"message":{"author":{"role":"user"},"content":{"parts":["Unrelated cooking note."]}}}
            }}]),encoding="utf-8")
            report=inspect_project(str(manifest),chat_exports=[str(export)])
            self.assertEqual(report["chat_records_scanned"],2)
            findings=[b for b in report["blockers"] if b["origin"]=="chat_export"]
            self.assertTrue(findings)
            self.assertTrue(all("cooking" not in b["evidence"].lower() for b in findings))

    def test_write_report_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=self._manifest(root)
            (root/"state.txt").write_text("Demo is on hold waiting for a dependency.",encoding="utf-8")
            result=write_report(str(manifest),str(root/"reports"),source_roots=[str(root)])
            self.assertTrue(Path(result["json_report"]).exists())
            self.assertTrue(Path(result["markdown_report"]).exists())

    def test_workspace_inspects_multiple_manifests(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)/"manifests";d.mkdir()
            for name in ("one","two"):
                (d/f"{name}.json").write_text(json.dumps({"project_id":name,"name":name.title(),"keywords":[name]}),encoding="utf-8")
            self.assertEqual(inspect_workspace(str(d))["project_count"],2)

    def test_registered_risks_are_read_read_write(self):
        registry=FakeRegistry();register_project_recovery_tools(registry)
        self.assertEqual(registry.tools["recovery.inspect_project"]["risk"],"read")
        self.assertEqual(registry.tools["recovery.inspect_workspace"]["risk"],"read")
        self.assertEqual(registry.tools["recovery.write_report"]["risk"],"write")

if __name__=="__main__":
    unittest.main()
