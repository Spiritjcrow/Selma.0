import ipaddress
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit


class _NoRedirect:
    """Placeholder for a redirect policy, installed below as a handler."""


class _DenyRedirect(urllib.request.HTTPRedirectHandler):
    """Do not let loopback model servers redirect strict-offline traffic."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Selma0LLMRouterAndroidV1:
    """OpenAI-compatible router. Strict-offline requests cannot contact a remote model.

    Ordinary calls preserve the older local-first/optional cloud fallback behavior.
    Set offline_only=True for the native local agent. Strict mode requires an
    HTTP(S) loopback URL, ignores environment proxy settings, and disallows redirects.
    """

    def __init__(self):
        self.local_base = os.getenv("SELMA0_LOCAL_BASE_URL_V1", "http://127.0.0.1:8080/v1")
        self.local_model = os.getenv("SELMA0_LOCAL_MODEL_V1", "selma0-local")
        self.online_base = os.getenv("SELMA0_ONLINE_BASE_URL_V1", "").rstrip("/")
        self.online_model = os.getenv("SELMA0_ONLINE_MODEL_V1", "")
        self.online_key = os.getenv("SELMA0_ONLINE_API_KEY_V1", "")
        self.timeout = float(os.getenv("SELMA0_LLM_TIMEOUT_V1", "45"))

    def is_loopback_local(self):
        try:
            parsed = urlsplit(self.local_base)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                return False
            if parsed.username is not None or parsed.password is not None:
                return False
            # Parse and reject malformed explicit ports, if any.
            port = parsed.port
            if port is not None and not (1 <= port <= 65535):
                return False
            if parsed.hostname.lower() == "localhost":
                return True
            return ipaddress.ip_address(parsed.hostname).is_loopback
        except (ValueError, TypeError):
            return False

    def _chat(self, base, model, messages, api_key="", local_only=False):
        payload = json.dumps({"model": model, "messages": messages, "temperature": 0.6}).encode()
        req = urllib.request.Request(
            base.rstrip("/") + "/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")

        if local_only:
            # No environment HTTP proxy and no redirect to a non-loopback URL.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _DenyRedirect())
            response = opener.open(req, timeout=self.timeout)
        else:
            response = urllib.request.urlopen(req, timeout=self.timeout)
        with response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]

    def reply(self, messages, offline_only=False):
        # Fail closed before any network request if strict mode is given a remote URL.
        if offline_only and not self.is_loopback_local():
            return {
                "text": "Selma.0 offline-only mode rejected a non-loopback model endpoint.",
                "route": "unavailable",
                "error": "offline_only requires a local loopback model URL",
            }

        local_error = None
        try:
            if offline_only:
                text = self._chat(self.local_base, self.local_model, messages, local_only=True)
            else:
                text = self._chat(self.local_base, self.local_model, messages)
            return {"text": text, "route": "offline-local", "error": None}
        except Exception as exc:
            local_error = str(exc)

        # Never even attempt the online endpoint after an offline-only request.
        if not offline_only and self.online_base and self.online_model:
            try:
                text = self._chat(self.online_base, self.online_model, messages, self.online_key)
                return {"text": text, "route": "online-fallback", "error": None}
            except Exception as exc:
                return {
                    "text": "Selma.0 could not reach either configured language-model endpoint.",
                    "route": "unavailable",
                    "error": f"local={local_error}; online={exc}",
                }

        return {
            "text": "Selma.0 local inference is unavailable."
                    if offline_only else
                    "Selma.0 local inference is not running and no online fallback is configured.",
            "route": "unavailable",
            "error": local_error,
        }
