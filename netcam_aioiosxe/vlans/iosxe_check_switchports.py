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

from urllib import parse
from http import HTTPStatus

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from netcad.checks import CheckResultsCollection

from netcad.vlans.checks.check_switchports import (
    SwitchportCheckCollection,
    SwitchportCheck,
    SwitchportCheckResult,
)

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

    for check in switchport_checks.checks:
        result = SwitchportCheckResult(device=device, check=check)

        expd_status = check.expected_results

        if_name = check.check_id()

        # get the interface switchport configuration

        res = await dut.restconf.get(
            "data/openconfig-interfaces:interfaces"
            f"/interface={parse.quote_plus(if_name)}"
            "/openconfig-if-ethernet:ethernet/openconfig-vlan:switched-vlan/config"
        )

        # if this configuration does not exist, then return a not-exists
        # indication.

        if res.status_code != HTTPStatus.OK:
            result.measurement = None
            results.append(result.measure())
            continue

        iface_switchport = res.json()["openconfig-vlan:config"]

        # verify the expected switchport mode (access / trunk)
        (
            _check_access_switchport
            if expd_status.switchport_mode == "access"
            else _check_trunk_switchport
        )(result=result, msrd_status=iface_switchport, results=results)

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

    expd: SwitchportCheck.ExpectTrunk = result.check.expected_results
    msrd = result.measurement = SwitchportCheckResult.MeasuredTrunk()

    msrd.switchport_mode = msrd_status["interface-mode"].casefold()
    msrd.native_vlan = msrd_status.get("native-vlan")
    expd.trunk_allowed_vlans = [v.vlan_id for v in expd.trunk_allowed_vlans]

    if expd.native_vlan:
        expd.native_vlan = expd.native_vlan.vlan_id

    msrd.trunk_allowed_vlans = msrd_status["trunk-vlans"]
    results.append(result.measure())
