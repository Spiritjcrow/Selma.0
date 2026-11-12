import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fixer.core import Registry,priority
from fixer.github_read import GitHubReadOnly,GitHubError
from fixer.reporting import generate

RECORD={"repository":"Spiritjcrow/Selma.0","kind":"issue","number":43,"title":"Secure command auth","url":"https://github.com/Spiritjcrow/Selma.0/issues/43","updated_at":"2026-11-01T00:00:00Z","head_sha":None}

class TestFixer(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)
        self.reg=Registry(self.path/"db.sqlite3")
    def tearDown(self):
        self.reg.close();self.tmp.cleanup()
    def test_priority(self):self.assertEqual(priority("Spiritjcrow/Selma.0","issue",43),"P0")
    def test_import_idempotence(self):
        self.assertEqual(self.reg.import_item(RECORD)[1],"added")
        self.assertEqual(self.reg.import_item(RECORD)[1],"unchanged")
        self.assertEqual(len(self.reg.list_items()),1)
    def test_approval_does_not_execute(self):
        key,_=self.reg.import_item(RECORD)
        self.assertEqual(self.reg.decide(key,"A"),"APPROVE_READ_ONLY_REVIEW")
        self.assertEqual(self.reg.list_items()[0]["decision"],"APPROVE_READ_ONLY_REVIEW")
    def test_source_change_revokes_decision(self):
        key,_=self.reg.import_item(RECORD);self.reg.decide(key,"A")
        update=dict(RECORD,updated_at="2026-11-02T00:00:00Z")
        self.assertEqual(self.reg.import_item(update)[1],"updated")
        self.assertIsNone(self.reg.list_items()[0]["decision"])
    def test_bad_choice_fails(self):
        key,_=self.reg.import_item(RECORD)
        with self.assertRaises(ValueError):self.reg.decide(key,"X")
    def test_url_spoofing_fails(self):
        bad=dict(RECORD,url="https://example.com/hello")
        with self.assertRaises(ValueError):self.reg.import_item(bad)
    def test_invalid_kind_fails(self):
        bad=dict(RECORD,kind="shell")
        with self.assertRaises(ValueError):self.reg.import_item(bad)
    def test_missing_item_fails(self):
        with self.assertRaises(ValueError):self.reg.decide("nope","A")
    def test_audit_chain_detects_tamper(self):
        self.reg.import_item(RECORD);self.assertTrue(self.reg.verify_chain())
        self.reg.db.execute("UPDATE events SET details='changed' WHERE seq=1");self.reg.db.commit()
        self.assertFalse(self.reg.verify_chain())
    def test_html_escape_and_real_link(self):
        record=dict(RECORD,title="<script>alert(1)</script>")
        self.reg.import_item(record);generate(self.reg,self.path/"out")
        html=(self.path/"out"/"index.html").read_text()
        self.assertIn("&lt;script&gt;",html);self.assertNotIn("<script>alert(1)</script>",html)
        self.assertIn(RECORD["url"],html)
    def test_empty_report_is_explicit(self):
        generate(self.reg,self.path/"out")
        data=json.loads((self.path/"out"/"inventory.json").read_text())
        self.assertEqual(data["count"],0)
    def test_inventory_excludes_pr_from_issues(self):
        g=GitHubReadOnly(token="stub")
        iss=[{"number":1,"title":"issue","html_url":"https://github.com/a/b/issues/1","updated_at":None},
             {"number":2,"title":"pr","html_url":"https://github.com/a/b/pull/2","pull_request":{},"updated_at":None}]
        prs=[{"number":2,"title":"pr","html_url":"https://github.com/a/b/pull/2","head":{"sha":"abc"},"updated_at":None}]
        with patch.object(g,"pages",side_effect=[iss,prs]):
            got=g.inventory_repo("a/b")
        self.assertEqual([x["kind"] for x in got],["issue","pr"])
    def test_paginated_failure_is_not_empty(self):
        g=GitHubReadOnly(token="stub",max_pages=1)
        with patch.object(g,"_get",return_value=[{}]*100):
            with self.assertRaises(GitHubError):list(g.pages("a/b","issues"))
    def test_invalid_repo_identifier(self):
        with self.assertRaises(ValueError):GitHubReadOnly().pages("a/../b","issues")
    def test_duplicate_latest_non_destructive(self):
        key,_=self.reg.import_item(RECORD);self.reg.decide(key,"B")
        self.reg.import_item(RECORD)
        self.assertEqual(self.reg.list_items()[0]["decision"],"HOLD")
    def test_event_chain_after_multiple_valid_events(self):
        key,_=self.reg.import_item(RECORD);self.reg.decide(key,"C");self.reg.decide(key,"D")
        self.assertTrue(self.reg.verify_chain())

if __name__=="__main__":unittest.main()