#!/usr/bin/env python3
import threading


class Selma0PluginAdapterRegistryAndroidV1:
    """Metadata registry for external-service adapters.

    This registry never stores secret values. Adapters expose a bounded status
    descriptor describing configuration state and registered capabilities.
    Command execution still occurs through the main Selma tool registry/router.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._adapters = {}

    def register(self, name, adapter):
        name = str(name or "").strip().lower()
        if not name or len(name) > 100:
            raise ValueError("adapter name is required and must be <= 100 characters")
        if not hasattr(adapter, "status") or not callable(adapter.status):
            raise ValueError("adapter must expose a callable status() method")
        with self._lock:
            if name in self._adapters:
                raise ValueError(f"adapter already registered: {name}")
            self._adapters[name] = adapter
        return adapter

    def get(self, name):
        name = str(name or "").strip().lower()
        with self._lock:
            adapter = self._adapters.get(name)
        if adapter is None:
            raise KeyError(f"unknown adapter: {name}")
        return adapter

    def describe(self, name):
        adapter = self.get(name)
        status = adapter.status()
        if not isinstance(status, dict):
            raise RuntimeError("adapter status must be an object")
        safe = dict(status)
        safe["name"] = str(name).strip().lower()
        return safe

    def list_status(self):
        with self._lock:
            names = sorted(self._adapters)
        return {
            "ok": True,
            "adapter_count": len(names),
            "adapters": [self.describe(name) for name in names],
        }


def register_plugin_status_tool(tool_registry, plugin_registry):
    tool_registry.register(
        "plugins.status",
        lambda: plugin_registry.list_status(),
        risk="sensitive_read",
        description=(
            "List configured external-service adapters without exposing credentials; "
            "explicit approval required because target/account metadata may be sensitive."
        ),
    )
    return plugin_registry
