import tempfile
from pathlib import Path
import unittest
import osiris_sync as s

FIXTURES = {
    'eonet': b'{"events":[{"id":"a","title":"Storm"}]}',
    'epic': b'[{"identifier":"1","image":"earth","date":"2026-11-25","caption":"Earth"}]',
}

class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'test.db'
        self.db = s.open_db(self.path)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def seed(self):
        s.sync(self.db, FIXTURES.__getitem__)
        return s.status(self.db)['eonet']['snapshot'][0]

    def test_sync(self):
        self.seed()
        self.assertTrue(all(not x['stale'] for x in s.status(self.db).values()))

    def test_digest(self):
        h = self.seed()
        self.assertEqual(h, self.seed())

    def test_failure_isolation(self):
        h = self.seed()
        s.sync(self.db, lambda k: b'{}' if k=='eonet' else FIXTURES[k])
        state = s.status(self.db)
        self.assertTrue(state['eonet']['stale'])
        self.assertFalse(state['epic']['stale'])
        self.assertEqual(h, state['eonet']['snapshot'][0])

    def test_stop(self):
        before = s.status(self.db)
        s.sync(self.db, lambda k: self.fail('unexpected fetch'), stop=lambda:True)
        self.assertEqual(before, s.status(self.db))

    def test_size(self):
        with self.assertRaises(ValueError):
            s.normalize('eonet', b'x'*(s.MAX_BYTES+1))

    def test_schema(self):
        with self.assertRaises(ValueError):
            s.normalize('eonet', b'{"events":[{"id":1}]}')

    def test_restart(self):
        h = self.seed()
        self.db.close()
        self.db = s.open_db(self.path)
        self.assertEqual(h, s.status(self.db)['eonet']['snapshot'][0])

if __name__ == '__main__':
    unittest.main()
