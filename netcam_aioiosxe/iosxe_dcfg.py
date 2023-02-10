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

from typing import Optional

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from netcad.device import Device
from netcad.netcam.dev_config import AsyncDeviceConfigurable

# -----------------------------------------------------------------------------
# Privae Imports
# -----------------------------------------------------------------------------

from .iosxe_dd import IOSXEDriver
from .iosxe_plugin_globals import g_iosxe

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

_Caps = AsyncDeviceConfigurable.Capabilities


class IOSXEDeviceConfigurable(AsyncDeviceConfigurable):
    DEFAULT_CAPABILITIES = _Caps.diff | _Caps.rollback | _Caps.replace

    def __init__(self, *, device: Device, **_kwargs):
        """
        Initialize the instance with eAPI
        Parameters
        ----------
        device:
            The netcad device instance from the design.
        """
        super().__init__(device=device)
        self._dev_fs = "flash:"
        username, password = g_iosxe.auth_admin
        self.cli = IOSXEDriver(device=device, username=username, password=password)
        self.capabilities = self.DEFAULT_CAPABILITIES

    def _set_config_id(self, name: str):
        pass

    async def is_reachable(self) -> bool:
        """
        Returns True when the device is reachable over eAPI, False otherwise.
        """
        return await self.cli.is_available()

    async def config_get(self) -> str:
        pass

    async def config_cancel(self):
        pass

    async def config_check(self, replace: Optional[bool | None] = None):
        pass

    async def config_diff(self) -> str:
        pass

    async def config_replace(self, rollback_timeout: int):
        pass

    async def config_merge(self, rollback_timeout: int):
        pass

    async def file_delete(self):
        """
        This function is used to remove the configuration file that was
        previously copied to the remote device.  This function is expected to
        be called during a "cleanup" process.
        """
        pass
