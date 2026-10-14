"""Pure-Python tests; no network or user stores."""
import unittest
from selma0_http_boundary_v1 import exact_authority, exact_origin


class BoundaryTests(unittest.TestCase):
    def test_ipv4(self):
        self.assertTrue(exact_authority('127.0.0.1:8765', '127.0.0.1', 8765))
        self.assertTrue(exact_origin('http://127.0.0.1:8765', '127.0.0.1', 8765))

    def test_ipv6(self):
        self.assertTrue(exact_authority('[::1]:8765', '::1', 8765))
        self.assertTrue(exact_origin('http://[::1]:8765', '::1', 8765))

    def test_localhost(self):
        self.assertTrue(exact_authority('localhost:8765', 'localhost', 8765))
        self.assertTrue(exact_origin('http://localhost:8765', 'localhost', 8765))

    def test_wrong_port(self):
        self.assertFalse(exact_authority('127.0.0.1:8766', '127.0.0.1', 8765))
        self.assertFalse(exact_origin('http://127.0.0.1:8766', '127.0.0.1', 8765))

    def test_wrong_host(self):
        self.assertFalse(exact_authority('localhost:8765', '127.0.0.1', 8765))
        self.assertFalse(exact_origin('http://localhost:8765', '127.0.0.1', 8765))

    def test_malformed(self):
        for host in ('', None, 'evil.test:8765', '127.0.0.1:8765@evil.test',
                     '127.0.0.1:8765/path', '127.0.0.1:8765?x', '127.0.0.1:8765#',
                     '127.0.0.1:8765\r\nHeader: injected', '127.0.0.1:99999'):
            with self.subTest(host=host):
                self.assertFalse(exact_authority(host, '127.0.0.1', 8765))

    def test_invalid_origin(self):
        for origin in (None, '', 'null', 'https://127.0.0.1:8765',
                       'http://127.0.0.1:8765/', 'http://127.0.0.1:8765?',
                       'http://127.0.0.1:8765#', 'http://127.0.0.1:8765.evil.test',
                       'http://user@127.0.0.1:8765', 'http://127.0.0.1:8765/path',
                       'http://127.0.0.1:8765\r\nInjected: x'):
            with self.subTest(origin=origin):
                self.assertFalse(exact_origin(origin, '127.0.0.1', 8765))


if __name__ == '__main__':
    unittest.main()
