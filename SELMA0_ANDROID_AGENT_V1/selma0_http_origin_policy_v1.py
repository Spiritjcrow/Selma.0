"""Strict Host and browser-origin checks for the local command core.

This limits CSRF and DNS rebinding, but does NOT authenticate local clients.
See issue #43 for authenticated sessions and trusted per-operation approval.
"""
import ipaddress
from urllib.parse import urlsplit


def _authority(value):
    if not isinstance(value, str) or not value or value != value.strip():
        return None
    if any(ch in value for ch in '\r\n/\\?#@ \t'):
        return None
    try:
        parsed = urlsplit('//' + value)
        host = parsed.hostname
        port = parsed.port
        if not host or parsed.username is not None or parsed.password is not None:
            return None
        return host.lower(), port
    except (TypeError, ValueError):
        return None


def _loopback(host):
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def valid_host(host_header, server_port, allow_nonloopback=False, allowed_hosts=()):
    parsed = _authority(host_header)
    if parsed is None:
        return False
    host, port = parsed
    if port is not None and port != int(server_port):
        return False
    return _loopback(host) or (allow_nonloopback and host in allowed_hosts)


def valid_origin(origin_header, host_header, server_port, allow_nonloopback=False, allowed_hosts=()):
    # Non-browser clients often omit Origin. Separate client authentication is required.
    if origin_header is None or origin_header == '':
        return True
    if not isinstance(origin_header, str) or origin_header != origin_header.strip():
        return False
    authority = _authority(host_header)
    if authority is None or not valid_host(host_header, server_port, allow_nonloopback, allowed_hosts):
        return False
    try:
        parsed = urlsplit(origin_header)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            return False
        if parsed.username is not None or parsed.password is not None:
            return False
        if parsed.path or parsed.query or parsed.fragment:
            return False
        host, host_port = authority
        if parsed.hostname.lower() != host or parsed.port != int(server_port):
            return False
        if _loopback(host) and parsed.scheme != 'http':
            return False
        return True
    except (TypeError, ValueError):
        return False
