# SelmaOS Network-Agnostic Diagnostics, v1

## Capability and provenance

The current network features are **input-only, offline evaluators**. They do not
log into routers, ping or scan devices, sniff packets, change routes, request
privileged Android APIs or claim to detect malicious users. Information from
a gateway interface is a dated, potentially stale observation, not a direct
measurement by SelmaOS.

The implementation accepts router-exported or manually transcribed observations
from any router. In particular, it is NOT coupled to the gateway, SSID, IP,
carrier, location, or hardware shown in the October 2026 screenshot.

## Call the tools

Use the pre-existing local Selma command router at 127.0.0.1:8765. The
`network.audit_router_snapshot` tool is a `sensitive_read`; the caller must
use explicit approval in the existing command router. A local POST example:

```bash
curl --fail-with-body -sS http://127.0.0.1:8765/api/selma0/tools/execute/v1 \
  -H 'Content-Type: application/json' \
  -d '{
    "tool": "network.audit_router_snapshot",
    "approved": true,
    "arguments": {
      "source": "manually_entered_router_device_list",
      "devices": [
        {
          "name": "my-phone",
          "mac": "02:00:00:00:00:01",
          "ipv4": "192.0.2.10",
          "status": "on",
          "band": "5 GHz"
        }
      ]
    }
  }'
```

The addresses above are **documentation examples**, not captured devices.
Avoid submitting unnecessary names, IPs, MACs, or SSIDs; current command-router
audit logs record tool arguments and results locally.

Network preference calculator, using **caller-observed** quality metrics:

```bash
curl --fail-with-body -sS http://127.0.0.1:8765/api/selma0/tools/execute/v1 \
  -H 'Content-Type: application/json' \
  -d '{
    "tool": "network.plan_transport",
    "arguments": {
      "policy": "save_data",
      "candidates": [
        {"transport":"wifi", "available":true, "metered":false,
         "latency_ms":20, "loss_percent":1, "throughput_mbps":15},
        {"transport":"cellular", "available":true, "metered":true},
        {"transport":"offline", "available":true}
      ]
    }
  }'
```

The values are examples only. Never use example measurements as evidence.
Inputs are not fetched automatically, and recommendations do **not** switch
interfaces or guarantee continuous connectivity.

## Network change and offline policies

- **Identity:** no hardcoded router, MAC, SSID, ISP, fixed address or geographic assumption.
- **Independence:** user records are parsed without any attached network.
- **Routing:** recommendations use explicit availability, latency, loss,
  throughput and metered observations, not fabricated health checks.
- **Connectivity:** actual interface changes, airplane mode, background jobs
  and disallowed Android networking APIs remain OS-governed.
- **Resilience:** the agent's local HTTP API remains bound to loopback by default;
  data should be queued locally by higher-level clients for later authorized sync.
  Full retry queue and seamless transport handoff are NOT implemented by this PR.
- **Privacy:** device snapshots are sensitive, require approval, and may appear
  in the append-only command audit. Do not expose the HTTP API to a LAN without
  an authenticated transport boundary.
- **Offline continuity:** local tool processing requires Python only. Any configured
  remote LLM or cloud feed needs actual connectivity; a local LLM must be separately
  installed and running for disconnected generation.

## Snapshot audit limitations

A gateway may retain devices after disconnect. Locally administered MACs are
common when phones enable MAC randomization and cannot reliably be matched
to a vendor. IPv6 lifetime display values such as 9999-12-31 are not security
permissions. Unknown names by themselves do not establish intrusion.
The proper next step is inventory reconciliation and security settings review,
not automatically denying or disconnecting devices.
