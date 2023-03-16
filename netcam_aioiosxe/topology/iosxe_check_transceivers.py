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
# System Imports
# -----------------------------------------------------------------------------

from typing import Set
from http import HTTPStatus

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------
from netcad.checks import CheckResultsCollection, CheckStatus

from netcad.topology.checks.check_transceivers import (
    TransceiverCheckCollection,
    TransceiverCheckResult,
    TransceiverExclusiveListCheck,
    TransceiverExclusiveListCheckResult,
)
from netcad.topology import transceiver_model_matches, transceiver_type_matches
from netcad.device import Device, DeviceInterface

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
async def iosxe_check_transceivers(
    dut, check_collection: TransceiverCheckCollection
) -> CheckResultsCollection:
    """
    This method is imported into the ESO DUT class definition to support
    checking the status of the transceivers.

    Notes
    -----
    On EOS platforms, the XCVR inventory is stored as port _numbers-strings_ and
    not as the interface name.  For example, "Interface54/1" is represented in
    the EOS inventor as "54".
    """

    dut: IOSXEDeviceUnderTest
    device = dut.device

    resp = await dut.restconf.get(
        "data/Cisco-IOS-XE-transceiver-oper:transceiver-oper-data/transceiver"
    )

    if resp.status_code == HTTPStatus.NO_CONTENT:
        body = []
    else:
        body = resp.json()["Cisco-IOS-XE-transceiver-oper:transceiver"]

    if_xcvr_table = {if_data["name"]: if_data for if_data in body}

    results = list()

    # first run through each of the per interface test cases ensuring that the
    # expected transceiver type and model are present.  While doing this keep
    # track of the interfaces port-numbers so that we can compare them to the
    # eclusive list.

    rsvd_ports_set = set()
    expd_port_set = set()

    for check in check_collection.checks:
        result = TransceiverCheckResult(device=device, check=check)

        if_name = check.check_id()
        dev_iface: DeviceInterface = device.interfaces[if_name]
        if_xcvr = if_xcvr_table.get(if_name)

        if dev_iface.profile.is_reserved:
            result.status = CheckStatus.INFO
            result.logs.INFO(
                "reserved",
                dict(
                    message="interface is in reserved state",
                    hardware=if_xcvr,  # from the show inventory command
                ),
            )
            results.append(result.measure())
            rsvd_ports_set.add(if_name)
            continue

        expd_port_set.add(if_name)

        eos_test_one_interface(
            if_xcvr=if_xcvr,
            result=result,
            results=results,
        )

    if check_collection.exclusive:
        _check_exclusive_list(
            device=device,
            expd_ports=expd_port_set,
            msrd_ports=if_xcvr_table,
            rsvd_ports=rsvd_ports_set,
            results=results,
        )

    return results


# -----------------------------------------------------------------------------
#
#                            PRIVATE CODE BEGINS
#
# -----------------------------------------------------------------------------


def _check_exclusive_list(
    device: Device,
    expd_ports,
    msrd_ports,
    rsvd_ports: Set,
    results: CheckResultsCollection,
):
    """
    Check to ensure that the list of transceivers found on the device matches the exclusive list.
    This check helps to find "unused" optics; or report them so that a Designer can account for them
    in the design-notepad.
    """

    check = TransceiverExclusiveListCheck(expected_results=expd_ports)

    # for IOS-XE, only those interfaces that have transceivers are returned in
    # the RESTCONF payload.

    used_msrd_ports = set(msrd_ports)

    # remove the reserved ports form the used list so that we do not consider
    # them as part of the exclusive list testing.

    used_msrd_ports -= rsvd_ports

    result = TransceiverExclusiveListCheckResult(
        device=device, check=check, measurement=used_msrd_ports
    )

    results.append(result.measure())


def eos_test_one_interface(
    if_xcvr: dict,
    result: TransceiverCheckResult,
    results: CheckResultsCollection,
):
    """
    This function validates that a specific interface is using the specific
    transceiver as defined in the design.
    """

    # if there is not a transciever when one is expected, then indicate that
    # result and return now.

    if not if_xcvr:
        result.measurement = None
        results.append(result.measure())
        return

    msrd = result.measurement
    msrd.model = if_xcvr["vendor-part"]
    msrd.type = if_xcvr["ethernet-pmd"]

    def on_mismatch(_field, _expd, _msrd):
        match _field:
            case "model":
                is_ok = transceiver_model_matches(
                    expected_model=_expd, given_mdoel=_msrd
                )
            case "type":
                is_ok = transceiver_type_matches(expected_type=_expd, given_type=_msrd)
            case _:
                is_ok = False

        return CheckStatus.PASS if is_ok else CheckStatus.FAIL

    results.append(result.measure(on_mismatch=on_mismatch))
