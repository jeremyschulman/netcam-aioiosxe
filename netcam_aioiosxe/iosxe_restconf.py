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

import asyncio
from socket import getservbyname

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

import httpx
from netcad.device import Device

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from netcam_aioiosxe.iosxe_plugin_globals import g_iosxe

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = ["IOSXERestConf"]


# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


class IOSXERestConf(httpx.AsyncClient):
    """
    IOS-XE RESTCONF asyncio client that uses JSON by default
    """

    def __init__(self, device: Device):
        self.device = device
        base_url = httpx.URL(f"https://{device.name}/restconf")
        self.port = getservbyname(base_url.scheme)

        super().__init__(
            base_url=base_url,
            auth=g_iosxe.basic_auth_read,
            verify=False,
            timeout=g_iosxe.config.timeout,
        )

        self.headers["accept"] = "application/yang-data+json"
        self.headers["content-type"] = "application/yang-data+json"

    async def check_connection(self) -> bool:
        """
        This function checks the target device to ensure that the eAPI port is
        open and accepting connections.  It is recommended that a Caller checks
        the connection before involing cli commands, but this step is not
        required.

        Returns
        -------
        True when the device eAPI is accessible, False otherwise.
        """
        try:
            await asyncio.open_connection(self.base_url.host, port=self.port)
        except OSError:
            return False
        return True
