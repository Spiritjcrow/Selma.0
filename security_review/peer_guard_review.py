"""Review-only loopback peer check; not wired to production HTTP."""
import ipaddress


def is_loopback_peer(address):
    if not isinstance(address, str):
        return False
    try:
        ip = ipaddress.ip_address(address)
        if getattr(ip, "ipv4_mapped", None) is not None:
            ip = ip.ipv4_mapped
        return ip.is_loopback
    except ValueError:
        return False


def verify_socket_peer(client_address):
    return (isinstance(client_address, tuple) and len(client_address) >= 2
            and is_loopback_peer(client_address[0]))
