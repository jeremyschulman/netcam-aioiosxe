#  Copyright 2023 Jeremy Schulman
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

import importlib.metadata as importlib_metadata

from netcad.device import Device

from .iosxe_dut import IOSXEDeviceUnderTest
from .config.iosxe_dcfg import IOSXEDeviceConfigurable
from .iosxe_plugin_init import iosxe_plugin_config

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------


plugin_version = importlib_metadata.version(__name__)
plugin_description = "Cisco IOS-XE systems (asyncio)"


def plugin_get_dut(device: Device) -> IOSXEDeviceUnderTest:
    if device.os_name != "ios-xe":
        raise RuntimeError(
            f"{device.name} called IOS-XE with improper os-name: {device.os_name}"
        )

    return IOSXEDeviceUnderTest(device=device)


def plugin_get_dcfg(device: Device) -> IOSXEDeviceConfigurable:
    if device.os_name != "ios-xe":
        raise RuntimeError(
            f"{device.name} called IOS-XE with improper os-name: {device.os_name}"
        )

    return IOSXEDeviceConfigurable(device=device)


def plugin_init(plugin_def: dict):
    if not (config := plugin_def.get("config")):
        raise RuntimeError("Missing IOS-XE driver config, please check.")

    iosxe_plugin_config(config)
