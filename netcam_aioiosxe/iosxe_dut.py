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

import asyncio
from typing import Optional, Any
from functools import singledispatchmethod
from collections import defaultdict

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from netcad.device import Device
from netcad.checks import CheckCollection, CheckResultsCollection
from netcam.dut import AsyncDeviceUnderTest

# -----------------------------------------------------------------------------
# Privae Imports
# -----------------------------------------------------------------------------

from .iosxe_plugin_globals import g_iosxe
from .iosxe_ssh import IOSXESSHDriver
from .iosxe_restconf import IOSXERestConf

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
        self.restconf = IOSXERestConf(device)
        user, password = g_iosxe.auth_read
        self.ssh = IOSXESSHDriver(device, username=user, password=password)
        self._api_cache_lock = asyncio.Lock()
        self._api_cache = dict()

    # -------------------------------------------------------------------------
    #
    #                              DUT Methods
    #
    # -------------------------------------------------------------------------

    async def setup(self):
        """DUT setup process"""
        await super().setup()

        if not await self.ssh.is_available():
            raise RuntimeError(f"{self.device.name}: SSH unavaialble, please check.")

        await self.ssh.cli.open()

        if not await self.restconf.check_connection():
            raise RuntimeError(
                f"{self.device.name}: RESTCONF unavaialble, please check."
            )

    async def teardown(self):
        """DUT tearndown process"""
        await self.ssh.cli.close()
        await self.restconf.aclose()

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

    register = execute_checks.register

    # -------------------------------------------------------------------------
    #
    #                              Cache Methods
    #
    # -------------------------------------------------------------------------

    async def api_cache_get(self, key: str, restconf_path: str, **params) -> Any:
        """
        This function is used by other class methods that want to abstract the
        collection function of a given eAPI routine so that the results of that
        call are cached and avaialble for other check executors.  This method
        should not be called outside other methods of this DUT class, but this
        is not a hard constraint.

        For example, if the result of "show interface switchport" is going to be
        used by multiple check executors, then there would exist a method in
        this class called `get_switchports` that uses this `api_cache_get`
        method.

        Parameters
        ----------
        key: str
            The cache-key string that is used to uniquely identify the contents
            of the cache.  For example 'switchports' may be the cache key to cache
            the results of the 'show interfaces switchport' command.

        restconf_path:
            The RESTCONF URL path to obtain the data.

        Other Parameters
        ----------------
        Any other `params` are URL kwargs to the RESTCONF get method.

        Returns
        -------
        Either the cached data corresponding to the key if exists in the cache,
        or the newly retrieved data from the device; which is then cached for
        future use.
        """
        async with self._api_cache_lock:
            if not (has_data := self._api_cache.get(key)):
                res = await self.restconf.get(restconf_path, params=params)
                self._api_cache[key] = has_data = res.json()

            return has_data

    async def get_interfaces(self) -> dict[str, dict]:
        body = await self.api_cache_get(
            "interfaces", "data/Cisco-IOS-XE-interfaces-oper:interfaces"
        )
        return {
            iface["name"]: iface
            for iface in body["Cisco-IOS-XE-interfaces-oper:interfaces"]["interface"]
        }

    async def get_vlans(self) -> dict[int, dict]:
        # using the STP operational data to get the mapping between VLANs and the
        # interfaces using the VLANs.

        data = await self.api_cache_get(
            "get-stp", "data/Cisco-IOS-XE-spanning-tree-oper:stp-details/stp-detail"
        )
        body = data["Cisco-IOS-XE-spanning-tree-oper:stp-detail"]

        op_vlan_stp_interfaces = defaultdict(list)

        for stp_inst in body:
            vlan_id = int(stp_inst["instance"][4:])
            interfaces = [
                iface["name"] for iface in stp_inst["interfaces"]["interface"]
            ]
            op_vlan_stp_interfaces[vlan_id] = interfaces

        got_vlan_table: dict[int, dict] = dict()

        data = await self.api_cache_get(
            "get-vlans", "data/Cisco-IOS-XE-vlan-oper:vlans/vlan"
        )

        # create a table by VLAN-ID (int) mapping to the per VLAN data object.
        for vlan_data in data["Cisco-IOS-XE-vlan-oper:vlan"]:
            vlan_id = vlan_data["id"]
            vlan_if_names = {
                if_rec["interface"] for if_rec in vlan_data.pop("vlan-interfaces", [])
            }
            vlan_if_names.update(op_vlan_stp_interfaces[vlan_id])
            vlan_data["interfaces"] = vlan_if_names
            got_vlan_table[vlan_id] = vlan_data

        return got_vlan_table
