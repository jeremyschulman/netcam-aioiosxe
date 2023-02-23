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
#

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from netcad.topology.checks.check_cabling_nei import (
    InterfaceCablingCheckCollection,
    InterfaceCablingCheck,
    InterfaceCablingCheckResult,
)
from netcad.topology.checks.utils_cabling_nei import (
    nei_interface_match,
    nei_hostname_match,
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


@IOSXEDeviceUnderTest.execute_checks.register
async def iosxe_check_cabling(
    self, testcases: InterfaceCablingCheckCollection
) -> CheckResultsCollection:
    """
    Support the "cabling" tests for Cisco IOS-XE devices.  These tests are
    implementeding by examing the LLDP neighborship status.

    Parameters
    ----------
    self: ** DO NOT TYPE HINT **
        EOS DUT instance

    testcases:
        The device specific cabling testcases as build via netcad.
    """
    dut: IOSXEDeviceUnderTest = self
    device = dut.device
    results = list()

    resp = await dut.restconf.get(
        "data/Cisco-IOS-XE-lldp-oper:lldp-entries/lldp-intf-details"
    )
    data = resp.json()["Cisco-IOS-XE-lldp-oper:lldp-intf-details"]

    # create a map of local interface name to the LLDP neighbor record.
    dev_lldpnei_ifname = {nei["if-name"]: nei for nei in data}

    for check in testcases.checks:
        if_name = check.check_id()

        if not (
            port_nei := dev_lldpnei_ifname.get(if_name).get("lldp-neighbor-details")
        ):
            result = InterfaceCablingCheckResult(
                device=device, check=check, measurement=None
            )
            results.append(result.measure())
            continue

        _check_one_interface(
            device=dut.device, check=check, ifnei_status=port_nei[0], results=results
        )

    return results


def _check_one_interface(
    device: Device,
    check: InterfaceCablingCheck,
    ifnei_status: dict,
    results: CheckResultsCollection,
):
    """
    Validates the LLDP information for a specific interface.
    """
    result = InterfaceCablingCheckResult(device=device, check=check)
    msrd = result.measurement

    msrd.device = ifnei_status["system-name"]
    msrd.port_id = ifnei_status["port-id"]

    def on_mismatch(_field, _expd, _msrd):
        is_ok = False
        match _field:
            case "device":
                is_ok = nei_hostname_match(_expd, _msrd)
            case "port_id":
                is_ok = nei_interface_match(_expd, _msrd)

        return CheckStatus.PASS if is_ok else CheckStatus.FAIL

    results.append(result.measure(on_mismatch=on_mismatch))
