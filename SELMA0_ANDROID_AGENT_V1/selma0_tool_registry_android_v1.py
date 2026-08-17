class Selma0ToolRegistryAndroidV1:
    """Registry for explicit, bounded Selma capabilities.

    Tools are callable only when registered with a risk class and handler.
    Model output never names an arbitrary executable path.
    """

    def __init__(self):
        self._tools = {}

    def register(self, name, handler, risk, description="", enabled=True):
        name = str(name).strip()
        if not name:
            raise ValueError("tool name is required")
        if not callable(handler):
            raise ValueError("tool handler must be callable")
        if name in self._tools:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = {
            "name": name,
            "handler": handler,
            "risk": str(risk).strip(),
            "description": str(description).strip(),
            "enabled": bool(enabled),
        }
        return self.describe(name)

    def unregister(self, name):
        return self._tools.pop(str(name), None) is not None

    def get(self, name):
        return self._tools.get(str(name))

    def describe(self, name):
        tool = self.get(name)
        if not tool:
            return None
        return {
            "name": tool["name"],
            "risk": tool["risk"],
            "description": tool["description"],
            "enabled": tool["enabled"],
        }

    def list_public(self):
        return [self.describe(name) for name in sorted(self._tools)]

    def execute_handler(self, name, arguments):
        tool = self.get(name)
        if not tool:
            raise KeyError(f"unknown tool: {name}")
        if tool.get("enabled") is False:
            raise PermissionError(f"tool disabled: {name}")
        args = arguments if isinstance(arguments, dict) else {}
        return tool["handler"](**args)
