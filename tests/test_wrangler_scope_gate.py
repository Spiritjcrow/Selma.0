import unittest
from wrangler.scope_gate import ScopePolicy, scope_decision, AuditLog, KillSwitch, PassiveImporter

class WranglerScopeTests(unittest.TestCase):
    def setUp(self):
        self.policy = ScopePolicy(("example.org", "*.example.org"), ("blocked.example.org",))
    def test_scope_and_wildcards(self):
        for url in ("https://example.org/", "https://sub.example.org/path"):
            self.assertTrue(scope_decision(url, self.policy)[0])
        for url in ("https://notexample.org", "https://blocked.example.org", "https://example.org.evil.net", "http://example.org", "https://example.org:8443", "https://user:pass@example.org"):
            self.assertFalse(scope_decision(url, self.policy)[0], url)
    def test_redirect_destination_must_be_rechecked(self):
        self.assertTrue(scope_decision("https://example.org/start", self.policy)[0])
        self.assertFalse(scope_decision("https://evil.net/redirect", self.policy)[0])
    def test_audit_tampering(self):
        log = AuditLog()
        log.append({"event": "scope_check"})
        log.append({"event": "denied"})
        self.assertTrue(log.verify())
        log.records[0]["event"]["event"] = "allowed"
        self.assertFalse(log.verify())
    def test_kill_switch(self):
        stop, log = KillSwitch(), AuditLog()
        importer = PassiveImporter(self.policy, stop, log)
        stop.stop()
        with self.assertRaises(RuntimeError):
            importer.process(["https://example.org"])
        self.assertEqual(len(log.records), 0)
        stop.reset()
        self.assertEqual(len(importer.process(["https://example.org"])), 1)

if __name__ == "__main__":
    unittest.main()
