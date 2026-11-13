import json
import os
import urllib.error
import urllib.request


class Selma0OversizedResponseError(ValueError):
    """Local model responses above the configured safety limit fail closed."""


class Selma0LLMRouterAndroidV1:
    """Offline-first router for OpenAI-compatible chat endpoints.

    Defaults to a local llama.cpp-style server on 127.0.0.1:8080.
    Set SELMA0_ONLINE_BASE_URL_V1 and SELMA0_ONLINE_API_KEY_V1 to enable
    an online fallback. No network call is attempted unless local inference
    fails and an online base URL is configured.
    """

    MAX_RESPONSE_BYTES = 1024 * 1024

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
            raw = response.read(self.MAX_RESPONSE_BYTES + 1)
            if len(raw) > self.MAX_RESPONSE_BYTES:
                raise Selma0OversizedResponseError("LLM response exceeds 1 MiB limit")
            body = json.loads(raw.decode("utf-8"))
        return body["choices"][0]["message"]["content"]

    def reply(self, messages):
        local_error = None
        try:
            text = self._chat(self.local_base, self.local_model, messages)
            return {"text": text, "route": "offline-local", "error": None}
        except Selma0OversizedResponseError:
            # A local resource-limit violation must not forward the user's
            # conversation to a configured cloud fallback.
            return {
                "text": "Selma.0 rejected an oversized local language-model response.",
                "route": "unavailable",
                "error": "local_response_size_limit",
            }
        except Exception as exc:
            local_error = str(exc)

        if self.online_base and self.online_model:
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
            "text": "Selma.0 local inference is not running and no online fallback is configured.",
            "route": "unavailable",
            "error": local_error,
        }
