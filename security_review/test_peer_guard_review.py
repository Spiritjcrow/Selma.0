"""Pure stdlib tests for review-only peer-address guard."""
import unittest
from security_review.peer_guard_review import is_loopback_peer, verify_socket_peer


class PeerGuardReviewTests(unittest.TestCase):
    def test_ipv4_loopback(self):
        self.assertTrue(is_loopback_peer("127.0.0.1"))

    def test_ipv6_loopback(self):
        self.assertTrue(is_loopback_peer("::1"))

    def test_ipv4_mapped_ipv6(self):
        self.assertTrue(is_loopback_peer("::ffff:127.0.0.1"))

    def test_remote_ip_denied(self):
        self.assertFalse(is_loopback_peer("192.0.2.44"))
        self.assertFalse(is_loopback_peer("::ffff:192.0.2.44"))

    def test_forwarded_hostname_and_invalid_peer_denied(self):
        self.assertFalse(is_loopback_peer("localhost"))
        self.assertFalse(verify_socket_peer(("127.0.0.1",)))
        self.assertFalse(verify_socket_peer(("192.0.2.44", 40000)))


if __name__ == "__main__":
    unittest.main()
