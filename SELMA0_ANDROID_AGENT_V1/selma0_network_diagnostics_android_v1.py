#!/usr/bin/env python3
"""Offline router-snapshot audit and network-agnostic transport advice.

Neither tool contacts a router, scans a LAN, changes connectivity, or
claims to have measured a connection. Inputs are supplied by the caller.
"""
import ipaddress
import re

_MAC = re.compile(r"^(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$")
_ALLOWED_TRANSPORTS = {
    "wifi", "cellular", "ethernet", "usb", "bluetooth", "satellite",
    "other", "offline",
}


def _string(value, limit=128):
    if value is None:
        return None
    text = str(value).strip()
    if len(text) > limit:
        raise ValueError("field exceeds permitted length")
    return text or None


def _ip(value, version):
    text = _string(value)
    if text is None:
        return None
    try:
        parsed = ipaddress.ip_address(text)
    except ValueError as exc:
        raise ValueError("invalid IP address") from exc
    if parsed.version != version:
        raise ValueError("incorrect IP address version")
    return str(parsed)


def audit_router_snapshot_v1(devices, source="manual_router_export"):
    """Analyze user-supplied observations. Never infer unauthorized access."""
    if not isinstance(devices, list) or len(devices) > 256:
        raise ValueError("devices must be an array of no more than 256 entries")
    source = _string(source) or "unattributed_user_input"
    findings = []
    for index, device in enumerate(devices):
        if not isinstance(device, dict):
            raise ValueError("each device must be an object")
        mac = _string(device.get("mac"))
        if mac is not None and not _MAC.fullmatch(mac):
            raise ValueError("invalid MAC address")
        mac = mac.lower() if mac else None
        locally_administered = bool(int(mac[:2], 16) & 0x02) if mac else None
        status = _string(device.get("status"))
        if status is not None:
            status = status.lower()
            if status not in {"on", "off", "unknown"}:
                raise ValueError("status must be on, off, or unknown")
        ipv6 = device.get("ipv6", [])
        if not isinstance(ipv6, list) or len(ipv6) > 32:
            raise ValueError("ipv6 must be an array with at most 32 addresses")
        ipv6 = [_ip(address, 6) for address in ipv6]
        findings.append({
            "entry": index + 1,
            "name": _string(device.get("name")),
            "mac": mac,
            "ipv4": _ip(device.get("ipv4"), 4),
            "ipv6": ipv6,
            "reported_status": status or "unknown",
            "reported_band": _string(device.get("band")),
            "reported_ssid": _string(device.get("ssid")),
            "reported_last_activity": _string(device.get("last_activity")),
            "reported_allocation": _string(device.get("allocation")),
            "mac_locally_administered": locally_administered,
            "observations": (
                ["MAC uses a locally administered address; vendor lookup is unreliable."]
                if locally_administered else []
            ) + (
                ["Router reports this entry offline; retained entries need not be active."]
                if status == "off" else []
            ),
        })
    return {
        "ok": True,
        "kind": "offline_router_snapshot_audit",
        "source": source,
        "live_scan_performed": False,
        "router_access_performed": False,
        "device_count": len(findings),
        "reported_on": sum(f["reported_status"] == "on" for f in findings),
        "reported_off": sum(f["reported_status"] == "off" for f in findings),
        "devices": findings,
        "unauthorized_access_verified": False,
        "limitations": (
            "User-supplied, point-in-time router records cannot independently identify "
            "owners, establish active connectivity now, or prove intrusion. "
            "IPv6 lifetime sentinel dates are router metadata, not access grants."
        ),
        "next_steps": [
            "Match devices to physically owned devices using device Wi-Fi settings.",
            "Review router encryption (prefer WPA3 or WPA2-AES) and WPS state.",
            "Verify remote management is disabled unless intentionally required.",
            "Review activity and recheck after network or device changes.",
        ],
    }


def _metric(candidate, key, max_value):
    value = candidate.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(key + " must be numeric")
    number = float(value)
    if number < 0 or number > max_value or number != number:
        raise ValueError(key + " outside permitted range")
    return number


def plan_transport_v1(candidates, policy="balanced"):
    """Rank reported candidates only. No network probes or OS route changes."""
    if not isinstance(candidates, list) or len(candidates) > 32:
        raise ValueError("candidates must be an array of at most 32 entries")
    if policy not in {"balanced", "save_data", "low_latency", "offline_first"}:
        raise ValueError("unsupported policy")
    results = []
    for item in candidates:
        if not isinstance(item, dict):
            raise ValueError("candidate must be an object")
        kind = _string(item.get("transport"))
        if kind not in _ALLOWED_TRANSPORTS:
            raise ValueError("unsupported transport")
        available = item.get("available")
        if not isinstance(available, bool):
            raise ValueError("available must be a boolean")
        metered = item.get("metered")
        if metered is not None and not isinstance(metered, bool):
            raise ValueError("metered must be a boolean or null")
        latency = _metric(item, "latency_ms", 120000)
        loss = _metric(item, "loss_percent", 100)
        throughput = _metric(item, "throughput_mbps", 100000)
        score = 50.0
        if kind == "offline":
            score = 20.0 if policy != "offline_first" else 100.0
        else:
            if latency is not None:
                score += max(-35.0, 20.0 - latency / 10.0)
            if loss is not None:
                score -= 2.0 * loss
            if throughput is not None:
                score += min(20.0, throughput / 5.0)
            if metered:
                score -= 35.0 if policy == "save_data" else 8.0
            if policy == "low_latency" and latency is not None:
                score -= min(40.0, latency / 5.0)
            if policy == "offline_first":
                score -= 90.0
        results.append({
            "transport": kind,
            "available": available,
            "metered": metered,
            "latency_ms": latency,
            "loss_percent": loss,
            "throughput_mbps": throughput,
            "score": round(score, 2) if available else None,
        })
    ranked = sorted(
        (row for row in results if row["available"]),
        key=lambda row: -row["score"],
    )
    return {
        "ok": True,
        "selected": ranked[0]["transport"] if ranked else None,
        "ranking": ranked,
        "unavailable_count": len(results) - len(ranked),
        "policy": policy,
        "measurement_source": "caller_supplied",
        "probe_performed": False,
        "switch_performed": False,
        "offline_candidate_supported": True,
        "limitations": (
            "Advice only: underlying OS manages actual routing and transport changes. "
            "No unstated SSID, carrier, fixed IP, available bandwidth, or continuous "
            "connectivity is assumed; offline persistence/replay requires app-level support."
        ),
    }


def register_network_diagnostic_tools_v1(registry):
    registry.register(
        "network.audit_router_snapshot",
        audit_router_snapshot_v1,
        risk="sensitive_read",
        description=(
            "Analyze explicitly supplied router observations offline. Requires approval "
            "because MAC addresses, local IPs and SSIDs are sensitive. "
            "Does not scan networks or change router settings."
        ),
    )
    registry.register(
        "network.plan_transport",
        plan_transport_v1,
        risk="read",
        description=(
            "Rank explicitly supplied available transports using latency, loss, "
            "throughput and metered flags. Advisory only, no probing/switching."
        ),
    )
