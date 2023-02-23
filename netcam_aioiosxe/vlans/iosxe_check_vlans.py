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

from typing import Set

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from http import HTTPStatus
from netcad.device import Device
from netcad.checks import CheckResultsCollection, CheckStatus

from netcad.vlans.checks.check_vlans import (
    VlanCheckCollection,
    VlanCheckResult,
    VlanExclusiveListCheck,
    VlanExclusiveListCheckResult,
)

from netcad.vlans import VlanDesignServiceConfig

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from netcam_aioiosxe import IOSXEDeviceUnderTest


# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = []


@IOSXEDeviceUnderTest.register
async def iosxe_check_vlans(
    self, vlan_checks: VlanCheckCollection
) -> CheckResultsCollection:
    """
    This check executor validates tha the device has the VLANs expected by the
    design.  These checks include validating the VLANs exist as they should in
    the design (for example VLAN-10 is "Printers" and not "VideoSystesms").
    This exector also validates the exclusive list of VLANs to ensure the device
    is not configured with any unexpected VLANs.
    """

    dut: IOSXEDeviceUnderTest = self
    device = dut.device
    results = list()

    op_vlan_table = await dut.get_vlans()

    ds_config = VlanDesignServiceConfig.parse_obj(vlan_checks.config)
    if not ds_config.check_vlan1:
        op_vlan_table.pop(1)

    msrd_active_vlan_ids = {
        vlan_id
        for vlan_id, vlan_st in op_vlan_table.items()
        if vlan_st["status"] == "active"
    }

    # keep track of the set of expectd VLAN-IDs (ints) should we need them for
    # the exclusivity check.

    expd_vlan_ids = set()

    for check in vlan_checks.checks:
        result = VlanCheckResult(device=device, check=check)

        # The check ID is the VLAN ID in string form.  Convert to int to be
        # consistent with op-data.

        vlan_id = int(check.check_id())
        expd_vlan_ids.add(vlan_id)

        # If the VLAN data is missing from the device, then we are done.

        if not (vlan_status := op_vlan_table.get(vlan_id)):
            result.measurement = None
            results.append(result.measure())
            continue

        # IOS-XE does not maintain the SVI interface relationship in the STP
        # table, so we need to check the presence of the SVI and add it to the
        # list of vlan-interfaces.

        if_name = f"Vlan{vlan_id}"
        res = await dut.restconf.get(
            "data/Cisco-IOS-XE-interfaces-oper:interfaces" f"/interface={if_name}/name"
        )

        if res.status_code == HTTPStatus.OK:
            op_vlan_table[vlan_id]["interfaces"].add(if_name)

        iosxe_check_one_vlan(
            exclusive=vlan_checks.exclusive,
            vlan_status=vlan_status,
            result=result,
            results=results,
        )

    if vlan_checks.exclusive:
        _check_exclusive(
            device=device,
            expd_vlan_ids=expd_vlan_ids,
            msrd_vlan_ids=msrd_active_vlan_ids,
            results=results,
        )

    return results


# -----------------------------------------------------------------------------
#
#                            PRIVATE CODE BEGINS
#
# -----------------------------------------------------------------------------


def _check_exclusive(
    device: Device,
    expd_vlan_ids: Set,
    msrd_vlan_ids: Set,
    results: CheckResultsCollection,
):
    """
    This function checks to see if there are any VLANs measured on the device
    that are not in the expected exclusive list.  We do not need to check for
    missing VLANs since expected per-vlan checks have already been performed.
    """

    result = VlanExclusiveListCheckResult(
        device=device,
        check=VlanExclusiveListCheck(expected_results=sorted(expd_vlan_ids)),
        measurement=sorted(msrd_vlan_ids),
    )
    results.append(result.measure())


def iosxe_check_one_vlan(
    exclusive: bool,
    result: VlanCheckResult,
    vlan_status: dict,
    results: CheckResultsCollection,
):
    """
    Checks a specific VLAN to ensure that it exists on the device as expected.
    """

    check = result.check
    msrd = result.measurement

    msrd.oper_up = vlan_status["status"] == "active"
    msrd.name = vlan_status["name"]

    # -------------------------------------------------------------------------
    # check the VLAN interface membership list.
    # -------------------------------------------------------------------------

    msrd.interfaces = vlan_status["interfaces"]
    msrd_ifs_set = set(msrd.interfaces)
    expd_ifs_set = set(check.expected_results.interfaces)

    if exclusive:
        if missing_interfaces := expd_ifs_set - msrd_ifs_set:
            result.logs.FAIL("interfaces", dict(missing=missing_interfaces))

        if extra_interfaces := msrd_ifs_set - expd_ifs_set:
            result.logs.FAIL("interfaces", dict(extra=extra_interfaces))

    def on_mismatch(_field, _expd, _msrd):
        if _field == "name":
            # if the VLAN name is not set, then we do not check-validate the
            # configured name.  This was added to support design-unused-vlan1;
            # but could be used for any VLAN.

            if not _expd:
                return CheckStatus.PASS

            result.logs.WARN(_field, dict(expected=_expd, measured=_msrd))
            return CheckStatus.PASS

        if _field == "interfaces":
            if exclusive:
                # use the sets for comparison purposes to avoid mismatch
                # due to list order.
                if msrd_ifs_set == expd_ifs_set:
                    return CheckStatus.PASS
            else:
                # if the set of measured interfaces are in the set of expected, and
                # this check is non-exclusive, then pass it.
                if msrd_ifs_set & expd_ifs_set == expd_ifs_set:
                    return CheckStatus.PASS

    results.append(result.measure(on_mismatch=on_mismatch))
