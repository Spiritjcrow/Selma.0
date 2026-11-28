import json
import os
import urllib.error
import urllib.request

from selma0_continuity_android_v1 import provider_fingerprint


class Selma0LLMRouterAndroidV1:
    """Offline-first router for OpenAI-compatible chat endpoints.

    Defaults to a local llama.cpp-style server on 127.0.0.1:8080.
    Set SELMA0_ONLINE_BASE_URL_V1 and SELMA0_ONLINE_API_KEY_V1 to enable
    an online fallback. No network call is attempted unless local inference
    fails and an online base URL is configured.
    """

    def __init__(self):
        self.local_base = os.getenv("SELMA0_LOCAL_BASE_URL_V1", "http://127.0.0.1:8080/v1")
        self.local_model = os.getenv("SELMA0_LOCAL_MODEL_V1", "selma0-local")
        self.online_base = os.getenv("SELMA0_ONLINE_BASE_URL_V1", "").rstrip("/")
        self.online_model = os.getenv("SELMA0_ONLINE_MODEL_V1", "")
        self.online_key = os.getenv("SELMA0_ONLINE_API_KEY_V1", "")
        self.timeout = float(os.getenv("SELMA0_LLM_TIMEOUT_V1", "45"))

    def _chat(self, base, model, messages, api_key=""):
        payload = json.dumps({"model": model, "messages": messages, "temperature": 0.6}).encode()
        req = urllib.request.Request(
            base.rstrip("/") + "/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]

    def provider_fingerprint(self, route):
        if route == "offline-local":
            return provider_fingerprint(route, self.local_base, self.local_model)
        if route == "online-fallback":
            if not (self.online_base and self.online_model):
                raise RuntimeError("configured online model is unavailable")
            return provider_fingerprint(route, self.online_base, self.online_model)
        raise ValueError("unknown model route")

    def reply(self, messages, locked_route=None):
        """Honor a previously pinned provider rather than silently switching."""
        if locked_route not in (None, "offline-local", "online-fallback"):
            raise ValueError("unknown locked model route")
        local_error = None
        if locked_route in (None, "offline-local"):
            try:
                text = self._chat(self.local_base, self.local_model, messages)
                return {"text": text, "route": "offline-local", "error": None}
            except Exception as exc:
                local_error = str(exc)
                if locked_route == "offline-local":
                    return {
                        "text": "Selma.0's pinned local model is unavailable. Provider was not changed.",
                        "route": "unavailable",
                        "error": local_error,
                    }

        if locked_route in (None, "online-fallback") and self.online_base and self.online_model:
            try:
                text = self._chat(self.online_base, self.online_model, messages, self.online_key)
                return {"text": text, "route": "online-fallback", "error": None}
            except Exception as exc:
                return {
                    "text": "Selma.0 could not reach the configured model endpoint; no provider change occurred.",
                    "route": "unavailable",
                    "error": f"local={local_error}; online={exc}",
                }

        return {
            "text": "Selma.0's selected model is unavailable; provider was not changed.",
            "route": "unavailable",
            "error": local_error or "online endpoint not configured",
        }
