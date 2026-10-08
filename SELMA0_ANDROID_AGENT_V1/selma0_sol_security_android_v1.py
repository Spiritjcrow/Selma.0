"""Sol Blue defensive exposure review and Sol Red isolated security self-test.

No sockets, subprocesses, filesystem scans, remote targets or automatic attack paths.
All observations are supplied by the caller; results do not prove public reachability.
"""
import ipaddress
from selma0_permission_engine_android_v1 import Selma0PermissionEngineAndroidV1

# Historical indicators from Lumen Black Lotus Labs, published October 2026.
# An IP match is a triage lead, not proof of compromise; indicators can age.
POELLM_C2_IPS_2026_10 = frozenset({
    "92.119.164.50", "103.249.201.108", "178.128.14.204",
    "191.37.28.160", "89.39.253.46", "120.224.114.212",
    "5.78.73.122", "15.204.178.28", "92.119.165.74",
    "45.133.73.28", "185.132.53.158", "136.148.69.233",
})
POELLM_SOURCE = "https://www.lumen.com/blog/en-us/canto-incognito-tracking-the-poellm-malware"


def _classify_host(value):
    """Classify only the supplied literal host; never resolve DNS or connect."""
    host = str(value or "").strip()
    if not host:
        return "not_supplied"
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if any(char in host for char in "/\\@?# \r\n\t") or len(host) > 253:
        return "invalid"
    if host.lower() == "localhost":
        return "loopback"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "hostname_unverified"
    if address.is_unspecified:
        return "wildcard"
    if address.is_loopback:
        return "loopback"
    if address.is_private or address.is_link_local:
        return "nonpublic_address"
    return "public_address"


def blue_exposure_review(bind_host="", model_host="", authentication_enabled=None, observed_ips=None):
    """Analyze declared configuration and caller-supplied network-log IPs offline."""
    if authentication_enabled not in (True, False, None):
        raise ValueError("authentication_enabled must be true, false, or null")
    if observed_ips is None:
        observed_ips = []
    if not isinstance(observed_ips, list) or len(observed_ips) > 64:
        raise ValueError("observed_ips must be a list of at most 64 addresses")

    findings = []
    categories = {}
    for field, host in (("bind_host", bind_host), ("model_host", model_host)):
        category = _classify_host(host)
        categories[field] = category
        if category in ("wildcard", "public_address"):
            findings.append({"severity": "high", "field": field,
                             "finding": "Potential externally reachable AI listener; verify firewall and access controls."})
        elif category == "nonpublic_address":
            findings.append({"severity": "review", "field": field,
                             "finding": "Non-loopback address; check LAN/VPN accessibility and authentication."})
        elif category in ("invalid", "hostname_unverified", "not_supplied"):
            findings.append({"severity": "unknown", "field": field,
                             "finding": "Actual exposure cannot be determined from this host value."})

    if authentication_enabled is False and categories["bind_host"] != "loopback":
        findings.append({"severity": "high", "field": "authentication_enabled",
                         "finding": "Non-loopback service declared without application authentication."})

    matches = []
    invalid_ip_count = 0
    for value in observed_ips:
        try:
            addr = ipaddress.ip_address(str(value).strip())
        except ValueError:
            invalid_ip_count += 1
            continue
        if str(addr) in POELLM_C2_IPS_2026_10 and str(addr) not in matches:
            matches.append(str(addr))
    if matches:
        findings.append({"severity": "investigate", "field": "observed_ips",
                         "finding": "Supplied log IPs match historical PoeLLM indicators; investigate with time and process context."})

    return {
        "mode": "sol_blue", "analysis": "offline_config_and_ioc_review",
        "network_activity": False, "live_exposure_verified": False,
        "categories": categories, "findings": findings,
        "poellm_historical_ioc_matches": sorted(matches),
        "invalid_ip_count": invalid_ip_count,
        "indicator_source": POELLM_SOURCE,
        "note": "No network, device or log access was performed. An IOC match alone does not establish infection.",
    }


def red_isolated_selftest():
    """Run bounded negative security checks against an in-memory policy instance."""
    policy = Selma0PermissionEngineAndroidV1()
    allowed = lambda risk, approved=False, enabled=True: policy.evaluate(
        {"risk": risk, "enabled": enabled}, approved=approved
    ).allowed
    checks = {
        "write_denied_without_approval": not allowed("write"),
        "external_effect_denied_without_approval": not allowed("external_effect"),
        "disabled_tool_denied_even_with_approval": not allowed("read", True, False),
        "unknown_risk_denied_even_with_approval": not allowed("unclassified", True),
        "approved_write_policy_path": allowed("write", True),
        "loopback_classified_local": _classify_host("127.0.0.1") == "loopback",
        "wildcard_classified_risky": _classify_host("0.0.0.0") == "wildcard",
        "public_address_classified_risky": _classify_host("8.8.8.8") == "public_address",
    }
    return {
        "mode": "sol_red", "test_scope": "in_memory_policy_negative_tests",
        "passed": all(checks.values()), "checks": checks,
        "network_activity": False, "attacks_executed": 0,
        "limitations": "Not an exploitation test, public exposure scan, or device compromise assessment.",
    }


def register_sol_security_tools(registry):
    registry.register(
        "sol.blue.exposure_review", blue_exposure_review, risk="read",
        description="Offline review of caller-supplied AI bind addresses, auth setting and PoeLLM IOC IPs; never connects.",
    )
    registry.register(
        "sol.red.isolated_selftest", red_isolated_selftest, risk="sensitive_read",
        description="Approved isolated adversarial policy checks only; no live targets or network traffic.",
    )
