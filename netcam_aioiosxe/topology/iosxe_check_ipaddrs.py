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

from typing import Sequence
import ipaddress

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from netcad.topology.checks.check_ipaddrs import (
    IPInterfacesCheckCollection,
    IPInterfaceCheck,
    IPInterfaceCheckResult,
    IPInterfaceExclusiveListCheck,
    IPInterfaceExclusiveListCheckResult,
)

from netcad.device import Device
from netcad.checks import CheckResultsCollection, CheckStatus

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from netcam_aioiosxe import IOSXEDeviceUnderTest


# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = []


# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


@IOSXEDeviceUnderTest.register
async def iosxe_check_ipaddrs(
    dut, collection: IPInterfacesCheckCollection
) -> CheckResultsCollection:
    """
    This check executor validates the IP addresses used on the device against
    those that are defined in the design.
    """

    dut: IOSXEDeviceUnderTest

    device = dut.device
    if_table = await dut.get_interfaces()

    results = list()
    if_names = list()

    for check in collection.checks:
        if_name = check.check_id()
        if_names.append(if_name)

        # if the IP address does not exist, then report that measurement and
        # move on to the next interface.

        if not (if_ip_data := if_table.get(if_name)):
            results.append(
                IPInterfaceCheckResult(
                    device=device, check=check, measurement=None
                ).measure()
            )
            continue

        await iosxe_test_one_interface(
            dut, device=device, check=check, msrd_data=if_ip_data, results=results
        )

    # only include device interface that have an assigned IP address; this
    # conditional is checked by examining the interface IP address mask length
    # against zero. IOS-XE sets the 'ipv4' field to '0.0.0.0' if no IP address
    # is assigned.

    if collection.exclusive:
        eos_test_exclusive_list(
            device=device,
            expd_if_names=if_names,
            msrd_if_names=[
                if_ip_data["name"]
                for if_ip_data in if_table.values()
                if if_ip_data["ipv4"] != "0.0.0.0"
            ],
            results=results,
        )

    return results


# -----------------------------------------------------------------------------


async def iosxe_test_one_interface(
    dut: "IOSXEDeviceUnderTest",
    device: Device,
    check: IPInterfaceCheck,
    msrd_data: dict,
    results: CheckResultsCollection,
):
    """
    This function validates a specific interface use of an IP address against
    the design expectations.
    """

    if_name = check.check_id()
    result = IPInterfaceCheckResult(device=device, check=check)
    msrd = result.measurement

    # IOS-XE designates an unassigned IP address as 0.0.0.0.  Therefore, if
    # this is the value found, then report a missing IP address.

    if (ipv4_addr := msrd_data["ipv4"]) == "0.0.0.0":
        result.measurement = None
        results.append(result.measure())
        return results

    # convert the API provided value "<ipaddr> <subnetmask>" into expected
    # format of <ipaddr/prefixlen>

    msrd.if_ipaddr = str(
        ipaddress.IPv4Interface((ipv4_addr, msrd_data["ipv4-subnet-mask"]))
    )

    # -------------------------------------------------------------------------
    # Ensure the IP interface value matches.
    # -------------------------------------------------------------------------

    expd_if_ipaddr = check.expected_results.if_ipaddr

    # if the IP address is marked as "is_reserved" it means that an external
    # entity configured the IP address, and this check will only record the
    # value as an INFO check result.

    if expd_if_ipaddr == "is_reserved":
        result.status = CheckStatus.INFO
        results.append(result.measure())

    # -------------------------------------------------------------------------
    # Ensure the IP interface is "up".
    # TODO: should check if the interface is enabled before presuming this
    #       up condition check.
    # -------------------------------------------------------------------------

    # check to see if the interface is disabled before we check to see if the IP
    # address is in the up condition.

    dut_interfaces = dut.device_info["interfaces"]
    dut_iface = dut_interfaces[if_name]
    iface_enabled = dut_iface["enabled"] is True

    msrd.oper_up = msrd_data["oper-status"] == "if-oper-state-ready"

    if iface_enabled and not msrd.oper_up:
        # if the interface is an SVI, then we need to check to see if _all_ of
        # the associated physical interfaces are either disabled or in a
        # reseverd condition.

        if if_name.startswith("Vlan"):
            await _check_vlan_assoc_interface(
                dut, if_name=if_name, result=result, results=results
            )
            return results

    results.append(result.measure())
    return results


def eos_test_exclusive_list(
    device: Device,
    expd_if_names: Sequence[str],
    msrd_if_names: Sequence[str],
    results: CheckResultsCollection,
):
    """
    This check determines if there are any extra IP Interfaces defined on the
    device that are not expected per the design.
    """

    # the previous per-interface checks for any missing; therefore we only need
    # to check for any extra interfaces found on the device.

    result = IPInterfaceExclusiveListCheckResult(
        device=device,
        check=IPInterfaceExclusiveListCheck(expected_results=expd_if_names),
        measurement=msrd_if_names,
    )

    results.append(result.measure())


async def _check_vlan_assoc_interface(
    dut: IOSXEDeviceUnderTest,
    if_name: str,
    result: IPInterfaceCheckResult,
    results: CheckResultsCollection,
):
    """
    This function is used to check whether a VLAN SVI ip address is not "up"
    due to the fact that the underlying interfaces are either disabled or in a
    "reserved" design; meaning we do not care if they are up or down. If the
    SVI is down because of this condition, the test case will "pass", and an
    information record is yielded to inform the User.

    Parameters
    ----------
    dut:
        The device under test

    result:
        The result instance bound to the check

    if_name:
        The specific VLAN SVI name, "Vlan12" for example:

    Yields
    ------
    netcad test case results; one or more depending on the condition of SVI
    interfaces.
    """

    vlan_id = if_name.split("Vlan")[-1]

    # -------------------------------------------------------------------------
    # Need to extract the list of interfaces from the VLAN.  Unfortunately this
    # is not available in the RESTCONF (reasons unknown, TAC case opened).
    #
    # Need to get the interfaces from the "show vlan" command, but that output
    # uses "short" interface names.  So then we need to convert to full
    # interface names by running through the "show interfaces" command.
    # ... *sigh*.
    # -------------------------------------------------------------------------

    res = await dut.restconf.get(
        "data/Cisco-IOS-XE-spanning-tree-oper:stp-details"
        f"/stp-detail=VLAN{vlan_id:04}/interfaces/interface"
    )

    body = res.json()["Cisco-IOS-XE-spanning-tree-oper:interface"]
    vlan_cfgd_ifnames = [vlan_if["name"] for vlan_if in body]

    disrd_ifnames = set()
    dut_ifs = dut.device_info["interfaces"]

    for check_ifname in vlan_cfgd_ifnames:
        dut_iface = dut_ifs[check_ifname]
        if (dut_iface["enabled"] is False) or (
            "is_reserved" in dut_iface["profile_flags"]
        ):
            disrd_ifnames.add(check_ifname)

    if disrd_ifnames == vlan_cfgd_ifnames:
        # then the SVI check should be a PASS because of the conditions
        # mentioned.

        result.logs.INFO(
            "oper_up",
            dict(
                message="interfaces are either disabled or in reserved state",
                interfaces=list(vlan_cfgd_ifnames),
            ),
        )

        def on_mismatch(_field, _expd, _msrd):
            return CheckStatus.PASS if _field == "oper_up" else CheckStatus.FAIL

        results.append(result.measure(on_mismatch=on_mismatch))

    return results
