#!/usr/bin/env python3
"""Rootless, user-initiated Selma offline acceptance check.

Run with the Android device's Wi-Fi and mobile data disabled to test real
internet-independent inference. No ADB, root, or system permissions are needed.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid

from selma0_llm_router_android_v1 import _DenyRedirect

BASE = "http://127.0.0.1:8765"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _DenyRedirect())


def local_request(method, path, payload=None):
    encoded = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=encoded, method=method)
    if encoded is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with OPENER.open(req, timeout=65) as result:
            if result.status != 200:
                raise RuntimeError("Unexpected HTTP status: " + str(result.status))
            content = result.read(131073)
    except urllib.error.URLError as error:
        raise RuntimeError("Local Termux command core is unavailable: " + str(error)) from error
    if len(content) > 131072:
        raise RuntimeError("Server response exceeded 128 KiB")
    response = json.loads(content.decode("utf-8"))
    if not isinstance(response, dict):
        raise RuntimeError("Server response is not a JSON object")
    return response


def verify(chat=False):
    status = local_request("GET", "/api/selma0/status/v1")
    if status.get("offline_only_supported") is not True:
        raise RuntimeError("FAIL: install/update the offline-only Termux agent before testing")
    if status.get("local_llm_loopback") is not True:
        raise RuntimeError("FAIL: model endpoint is not a verified loopback URL")
    print("PASS: offline-only handshake")
    print("Local model configured:", status.get("local_llm", "<unspecified>"))
    print("Cloud fallback configured:", bool(status.get("online_fallback_configured")))

    if not chat:
        print("STATUS ONLY: model output and internet-disabled behavior are untested")
        return

    response = local_request("POST", "/api/selma0/chat/v1", {
        "message": "Respond with a brief greeting for a local offline acceptance test.",
        "confirmed": True,
        "offline_only": True,
        "request_id": str(uuid.uuid4()),
    })
    if response.get("ok") is not True:
        raise RuntimeError("FAIL: command core rejected the chat request: " + str(response.get("error")))
    result = response.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("FAIL: command core did not return a chat result")
    if result.get("route") != "offline-local":
        raise RuntimeError("FAIL: model route was " + str(result.get("route")))
    if not str(result.get("text") or "").strip():
        raise RuntimeError("FAIL: local model returned no content")
    print("PASS: local model generated a response")
    print("Reply characters:", len(result["text"]))
    print("Report whether Wi-Fi AND mobile data were disabled during this test.")
    print("This test does not certify APK installation, avatar rendering, or server provenance.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat", action="store_true",
                        help="Test live model output; first manually disable Wi-Fi and mobile data")
    args = parser.parse_args()
    try:
        verify(chat=args.chat)
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
