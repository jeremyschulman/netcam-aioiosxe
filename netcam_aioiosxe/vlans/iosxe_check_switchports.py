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

from typing import cast
from urllib import parse

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from netcad.checks import CheckResultsCollection

from netcad.vlans.checks.check_switchports import (
    SwitchportCheckCollection,
    SwitchportCheck,
    SwitchportCheckResult,
)

from netcad.vlans import VlanDesignServiceConfig
from netcam_aioiosxe import IOSXEDeviceUnderTest
from .iosxe_get_vlans import iosxe_get_switchports

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
async def iosxe_check_switchports(
    dut, switchport_checks: SwitchportCheckCollection
) -> CheckResultsCollection:
    """
    This check executor validates the device operational status of the interface
    switchports.

    Parameters
    ----------
    dut:
        The DUT instance for the specific device being checked.

    switchport_checks: SwitchportCheckCollection
        The collection of checks created by the netcad tool for the
        vlans.switchports case.

    Returns
    -------
    A collection of check-results that will be logged and reported to the User
    during check execution and showing results.
    """

    dut: IOSXEDeviceUnderTest
    device = dut.device
    results = list()

    # each check represents one interface to validate.  Loop through each of the
    # checks to ensure that the expected switchport use is as expected.

    # has_lags = await iosxe_get_lags(dut)

    has_if_switchports = await iosxe_get_switchports(dut)

    ds_config = VlanDesignServiceConfig.parse_obj(switchport_checks.config)
    remove_vlan1 = {1} if not ds_config.check_vlan1 else set()

    for check in switchport_checks.checks:
        result = SwitchportCheckResult(device=device, check=check)
        expd_status: SwitchportCheck.ExpectSwitchport = cast(
            SwitchportCheck.ExpectSwitchport, check.expected_results
        )

        if_name = check.check_id()

        iface_obj = dut.device.interfaces[if_name]
        if_port_name = "/".join(map(str, iface_obj.port_numbers))
        if_port_type_name = if_name.split(if_port_name)[0]
        res = await dut.restconf.get(
            "data/Cisco-IOS-XE-native:native/interface/"
            f"{if_port_type_name}={parse.quote_plus(if_port_name)}/"
            "switchport-config/switchport"
        )

        msrd_status = dict()
        body = res.json()
        if_swp_data = body["Cisco-IOS-XE-native:switchport"]
        if if_swp_trunk := if_swp_data.get("Cisco-IOS-XE-switch:trunk"):
            msrd_status["interface-mode"] = "trunk"
            msrd_status["trunk-vlans"] = set(has_if_switchports[if_name]) - remove_vlan1
            try:
                msrd_status["native-vlan"] = if_swp_trunk["native"]["vlan"]["vlan-id"]
            except KeyError:
                msrd_status["native-vlan"] = None
        else:
            if_swp_access = if_swp_data["Cisco-IOS-XE-switch:access"]
            msrd_status["interface-mode"] = "access"
            msrd_status["access-vlan"] = if_swp_access["vlan"]["vlan"]

        if expd_status.switchport_mode == "access":
            _check_access_switchport(
                result=result, msrd_status=msrd_status, results=results
            )
        else:
            _check_trunk_switchport(
                result=result, msrd_status=msrd_status, results=results
            )

    # return the collection of results for all switchport interfaces
    return results


def _check_access_switchport(
    result: SwitchportCheckResult, msrd_status: dict, results: CheckResultsCollection
):
    """
    This function validates that the access port is reporting as expected.
    This primary check here is ensuring the access VLAN-ID matches.
    """

    msrd = result.measurement = SwitchportCheckResult.MeasuredAccess()
    msrd.switchport_mode = msrd_status["interface-mode"].casefold()

    # the check stores the VlanProfile, and we need to mutate this value to the
    # VLAN ID for comparitor reason.
    result.check.expected_results.vlan = result.check.expected_results.vlan.vlan_id

    # EOS stores the vlan id as int, so type comparison AOK
    msrd.vlan = msrd_status["access-vlan"]
    results.append(result.measure())


def _check_trunk_switchport(
    result: SwitchportCheckResult, msrd_status: dict, results: CheckResultsCollection
):
    """
    This function validates a trunk switchport against the expected values.
    These checks include matching on the native-vlan and trunk-allowed-vlans.
    """

    expd: SwitchportCheck.ExpectTrunk = cast(
        SwitchportCheck.ExpectTrunk, result.check.expected_results
    )

    msrd = result.measurement = SwitchportCheckResult.MeasuredTrunk()

    msrd.switchport_mode = msrd_status["interface-mode"].casefold()
    msrd.native_vlan = msrd_status.get("native-vlan")
    expd.trunk_allowed_vlans = set(v.vlan_id for v in expd.trunk_allowed_vlans)

    if expd.native_vlan:
        expd.native_vlan = expd.native_vlan.vlan_id

    msrd.trunk_allowed_vlans = msrd_status["trunk-vlans"]
    results.append(result.measure())
