#!/usr/bin/env python3
import selma0_runtime_device_crowrf_android_v1 as device_runtime
from selma0_github_adapter_android_v1 import register_github_adapter_tools
from selma0_plugin_adapter_registry_android_v1 import (
    Selma0PluginAdapterRegistryAndroidV1,
    register_plugin_status_tool,
)


PLUGIN_REGISTRY_V1 = Selma0PluginAdapterRegistryAndroidV1()
register_plugin_status_tool(
    device_runtime.command_core.COMMAND_ROUTER_V1.registry,
    PLUGIN_REGISTRY_V1,
)
GITHUB_ADAPTER_V1 = register_github_adapter_tools(
    device_runtime.command_core.COMMAND_ROUTER_V1.registry,
    plugin_registry=PLUGIN_REGISTRY_V1,
)


def main():
    device_runtime.command_core.main()


if __name__ == "__main__":
    main()
