"""Review-stage exact loopback HTTP boundary for Selma issue #43.

Not caller authentication. Integrate only alongside authenticated sessions and
per-operation approval evidence; do not deploy this alone as a security fix.
"""
import ipaddress
from urllib.parse import urlsplit


def _same_host(value, bound_host):
    try:
        return ipaddress.ip_address(value) == ipaddress.ip_address(bound_host)
    except ValueError:
        return value.lower() == bound_host.lower() == 'localhost'


def exact_authority(value, bound_host, bound_port):
    if not isinstance(value, str) or not value or value.strip() != value:
        return False
    if any(c in value for c in '\r\n/@\\?#'):
        return False
    try:
        parsed = urlsplit('//'+value)
        return (parsed.username is None and parsed.password is None and
                not parsed.path and not parsed.query and not parsed.fragment and
                parsed.port == bound_port and parsed.hostname is not None and
                _same_host(parsed.hostname, bound_host))
    except (ValueError, TypeError):
        return False


def exact_origin(value, bound_host, bound_port):
    if not isinstance(value, str) or not value or value.strip() != value:
        return False
    if any(c in value for c in '\r\n\\?#'):
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == 'http' and parsed.username is None and
                parsed.password is None and not parsed.path and not parsed.query and
                not parsed.fragment and parsed.port == bound_port and
                parsed.hostname is not None and _same_host(parsed.hostname, bound_host))
    except (ValueError, TypeError):
        return False
