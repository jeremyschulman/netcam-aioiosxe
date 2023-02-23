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

from collections import defaultdict

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from netcam_aioiosxe import IOSXEDeviceUnderTest

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = ["iosxe_get_vlans"]

# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


async def iosxe_get_vlans(dut: IOSXEDeviceUnderTest) -> dict[int, dict]:
    # using the STP operational data to get the mapping between VLANs and the
    # interfaces using the VLANs.

    data = await dut.api_cache_get(
        "get-stp", "data/Cisco-IOS-XE-spanning-tree-oper:stp-details/stp-detail"
    )
    body = data["Cisco-IOS-XE-spanning-tree-oper:stp-detail"]

    op_vlan_stp_interfaces = defaultdict(list)

    for stp_inst in body:
        vlan_id = int(stp_inst["instance"][4:])
        interfaces = [iface["name"] for iface in stp_inst["interfaces"]["interface"]]
        op_vlan_stp_interfaces[vlan_id] = interfaces

    got_vlan_table: dict[int, dict] = dict()

    data = await dut.api_cache_get(
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
