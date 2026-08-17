#!/usr/bin/env python3
import selma0_runtime_command_core_android_v1 as command_core
from selma0_crowrf_derived_metrics_android_v1 import register_crowrf_derived_tools
from selma0_crowrf_measurement_store_android_v1 import (
    Selma0CrowRFMeasurementStoreAndroidV1,
    register_crowrf_measurement_store_tools,
)
from selma0_crowrf_wifi_scan_android_v1 import register_crowrf_tools
from selma0_device_bridge_android_v1 import (
    Selma0TermuxDeviceBridgeAndroidV1,
    register_device_tools,
)


DEVICE_BRIDGE_V1 = Selma0TermuxDeviceBridgeAndroidV1()
CROWRF_STORE_V1 = Selma0CrowRFMeasurementStoreAndroidV1()
register_device_tools(command_core.COMMAND_ROUTER_V1.registry, bridge=DEVICE_BRIDGE_V1)
register_crowrf_tools(command_core.COMMAND_ROUTER_V1.registry, bridge=DEVICE_BRIDGE_V1)
register_crowrf_measurement_store_tools(
    command_core.COMMAND_ROUTER_V1.registry,
    store=CROWRF_STORE_V1,
    bridge=DEVICE_BRIDGE_V1,
)
register_crowrf_derived_tools(
    command_core.COMMAND_ROUTER_V1.registry,
    store=CROWRF_STORE_V1,
)


def main():
    command_core.main()


if __name__ == "__main__":
    main()
