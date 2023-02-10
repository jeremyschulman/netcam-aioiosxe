#  Copyright 2021 Jeremy Schulman
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
from functools import singledispatchmethod

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from netcad.device import Device
from netcad.checks import CheckCollection, CheckResultsCollection
from netcad.netcam.dut import AsyncDeviceUnderTest

# -----------------------------------------------------------------------------
# Privae Imports
# -----------------------------------------------------------------------------

from .iosxe_plugin_globals import g_iosxe
from .iosxe_dd import IOSXEDriver

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = ["IOSXEDeviceUnderTest"]


# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


class IOSXEDeviceUnderTest(AsyncDeviceUnderTest):
    def __init__(self, *, device: Device, **_kwargs):
        super().__init__(device=device)
        self.version_info: Optional[dict] = None
        username, password = g_iosxe.auth_read
        self.scrapli = IOSXEDriver(device, username, password)

    # -------------------------------------------------------------------------
    #
    #                              DUT Methods
    #
    # -------------------------------------------------------------------------

    async def setup(self):
        """DUT setup process"""
        await super().setup()

        if not await self.scrapli.is_available():
            raise RuntimeError(f"{self.device.name}: SSH unavaialble, please check.")

        await self.scrapli.cli.open()
        await self.scrapli.cli.get_prompt()

    async def teardown(self):
        """DUT tearndown process"""
        await self.scrapli.cli.close()

    @singledispatchmethod
    async def execute_checks(
        self, checks: CheckCollection
    ) -> Optional[CheckResultsCollection]:
        """
        This method is only called when the DUT does not support a specific
        design-service check.  This function *MUST* exist so that the supported
        checks can be "wired into" this class using the dispatch register mechanism.
        """
        return super().execute_checks()
