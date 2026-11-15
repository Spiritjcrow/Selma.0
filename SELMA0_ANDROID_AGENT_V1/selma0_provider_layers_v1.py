"""SelmaOS v1 opt-in text provider adapters. Standard library; no background execution.

This is NOT a substitute for Selma's approval/permission control plane.
It is not connected to the production HTTP router until separately reviewed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    protocol: str
    endpoint: str
    key_env: str
    model_env: str
    default_model: str = ""


PROVIDERS = {
    "claude": Provider("anthropic", "https://api.anthropic.com/v1/messages", "ANTHROPIC_API_KEY", "SELMA_CLAUDE_MODEL", "claude-fable-5-2"),
    "grok": Provider("responses", "https://api.x.ai/v1/responses", "XAI_API_KEY", "SELMA_GROK_MODEL", "grok-4.7"),
    "gemini": Provider("gemini", "https://generativelanguage.googleapis.com/v1beta/models/", "GEMINI_API_KEY", "SELMA_GEMINI_MODEL"),
    "kimi": Provider("chat", "https://api.moonshot.ai/v1/chat/completions", "KIMI_API_KEY", "SELMA_KIMI_MODEL"),
    "deepseek": Provider("chat", "https://api.deepseek.com/chat/completions", "DEEPSEEK_API_KEY", "SELMA_DEEPSEEK_MODEL", "deepseek-flash"),
}
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _messages(messages):
    if not isinstance(messages, list) or not 1 <= len(messages) <= 20:
        raise ValueError("messages must contain 1..20 items")
    checked = []
    for message in messages:
        if not isinstance(message, dict) or set(message) != {"role", "content"}:
            raise ValueError("only role and content are allowed")
        role, content = message["role"], message["content"]
        if role not in ("system", "user", "assistant") or not isinstance(content, str) or not 0 < len(content) <= 16000:
            raise ValueError("unsupported role or content length")
        checked.append({"role": role, "content": content})
    if not any(m["role"] == "user" for m in checked):
        raise ValueError("at least one user message required")
    return checked


def _build(provider, model, messages, max_tokens):
    headers = {"Content-Type": "application/json"}
    endpoint = provider.endpoint
    if provider.protocol == "anthropic":
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        conversation = [m for m in messages if m["role"] != "system"]
        body = {"model": model, "max_tokens": max_tokens, "messages": conversation}
        if system:
            body["system"] = system
        headers["anthropic-version"] = "2026-10-21"
    elif provider.protocol == "responses":
        body = {"model": model, "input": messages, "max_output_tokens": max_tokens}
    elif provider.protocol == "gemini":
        endpoint += urllib.parse.quote(model, safe="") + ":generateContent"
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        body = {"contents": [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]} for m in messages if m["role"] != "system"], "generationConfig": {"maxOutputTokens": max_tokens}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
    else:
        body = {"model": model, "messages": messages, "max_tokens": max_tokens}
    return endpoint, headers, body


def _extract(protocol, data):
    if protocol == "anthropic":
        parts = [c.get("text", "") for c in data["content"] if c.get("type") == "text"]
    elif protocol == "gemini":
        parts = [c.get("text", "") for c in data["candidates"][0]["content"]["parts"] if "text" in c]
    elif protocol == "responses":
        parts = [c.get("text", "") for item in data["output"] if item.get("type") == "message" for c in item.get("content", []) if c.get("type") == "output_text"]
    else:
        parts = [data["choices"][0]["message"]["content"]]
    text = "".join(parts)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty provider text response")
    return text


def request(provider_name, messages, *, allow_network=False, model=None, max_tokens=512, transport=None, environ=None):
    """Execute a single explicitly approved provider call, never automatic fallback.

    Returns a status dictionary. Never returns API keys or raw HTTP error bodies.
    Production callers must independently enforce Selma's permission policy.
    """
    if provider_name not in PROVIDERS:
        return {"status": "blocked", "reason": "unknown provider"}
    if not allow_network:
        return {"status": "blocked", "provider": provider_name, "reason": "network approval required"}
    try:
        checked = _messages(messages)
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or not 1 <= max_tokens <= 4096:
            raise ValueError("max_tokens must be 1..4096")
        provider = PROVIDERS[provider_name]
        env = os.environ if environ is None else environ
        key = env.get(provider.key_env, "")
        selected = model or env.get(provider.model_env, "") or provider.default_model
        if not selected or not isinstance(selected, str) or not MODEL_RE.fullmatch(selected):
            return {"status": "unavailable", "provider": provider_name, "reason": "valid model ID not configured"}
        if not key:
            return {"status": "unavailable", "provider": provider_name, "reason": "API key not configured"}
        endpoint, headers, body = _build(provider, selected, checked, max_tokens)
        if provider.protocol == "gemini":
            headers["x-goog-api-key"] = key
        else:
            headers["Authorization"] = "Bearer " + key
        data = json.dumps(body).encode("utf-8")
        opener = transport if transport is not None else urllib.request.urlopen
        req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
        with opener(req, timeout=45) as response:
            payload = response.read(2_000_001)
        if len(payload) > 2_000_000:
            raise ValueError("response too large")
        answer = _extract(provider.protocol, json.loads(payload))
        return {"status": "ok", "provider": provider_name, "model": selected, "text": answer}
    except urllib.error.HTTPError as exc:
        return {"status": "error", "provider": provider_name, "reason": "HTTP status " + str(exc.code)}
    except (ValueError, KeyError, TypeError, IndexError, UnicodeError, urllib.error.URLError, OSError, TimeoutError):
        return {"status": "error", "provider": provider_name, "reason": "invalid input, response, or transport failure"}


def main():
    parser = argparse.ArgumentParser(description="Opt-in Selma multimodel text adapter")
    parser.add_argument("--list", action="store_true", help="list provider IDs without network")
    parser.add_argument("--provider", choices=sorted(PROVIDERS))
    parser.add_argument("--model", help="provider model ID override")
    parser.add_argument("--message", help="single text message to send")
    parser.add_argument("--execute", action="store_true", help="explicitly permit one external request, which may incur charges")
    args = parser.parse_args()
    if args.list or not args.provider:
        print(json.dumps({"providers": sorted(PROVIDERS), "network": "disabled by default"}))
        return 0
    if not args.message:
        parser.error("--message required with --provider")
    result = request(args.provider, [{"role": "user", "content": args.message}], allow_network=args.execute, model=args.model)
    print(json.dumps(result))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
