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

import re
from typing import Set

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from netcad.device import Device, DeviceInterface
from netcad.checks import CheckResultsCollection, CheckStatus

from netcad.topology.checks.check_interfaces import (
    InterfaceCheckCollection,
    InterfaceExclusiveListCheck,
    InterfaceExclusiveListCheckResult,
    InterfaceCheck,
    InterfaceCheckResult,
    InterfaceCheckMeasurement,
)

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

_match_svi = re.compile(r"Vlan(\d+)").match


@IOSXEDeviceUnderTest.register
async def iosxe_check_interfaces(
    self, collection: InterfaceCheckCollection
) -> CheckResultsCollection:
    """
    This async generator is responsible for implementing the "interfaces" test
    cases for IOS-XE devices.
    """

    dut: IOSXEDeviceUnderTest = self
    device = dut.device
    results = list()

    if_table = await dut.get_interfaces()

    # -------------------------------------------------------------------------
    # Check for the exclusive set of interfaces expected vs actual.
    # -------------------------------------------------------------------------

    if collection.exclusive:
        iosxe_check_exclusive_interfaces_list(
            device=device,
            expd_interfaces=set(check.check_id() for check in collection.checks),
            msrd_interfaces=set(if_table),
            results=results,
        )

    # -------------------------------------------------------------------------
    # Check each interface for health checks
    # -------------------------------------------------------------------------

    for check in collection.checks:
        if_name = check.check_id()

        iosxe_check_one_interface(
            device=device,
            check=check,
            iface_oper_status=if_table.get(if_name),
            results=results,
        )

    return results


# -----------------------------------------------------------------------------
#
#                       PRIVATE CODE BEGINS
#
# -----------------------------------------------------------------------------


def iosxe_check_exclusive_interfaces_list(
    device: Device,
    expd_interfaces: Set[str],
    msrd_interfaces: Set[str],
    results: CheckResultsCollection,
):
    """
    This check validates the exclusive list of interfaces found on the device
    against the expected list in the design.
    """

    def sort_key(i):
        return DeviceInterface(i, interfaces=device.interfaces)

    check = InterfaceExclusiveListCheck(
        expected_results=sorted(expd_interfaces, key=sort_key)
    )

    result = InterfaceExclusiveListCheckResult(
        device=device, check=check, measurement=sorted(msrd_interfaces, key=sort_key)
    )

    results.append(result.measure(sort_key=sort_key))


# -----------------------------------------------------------------------------
# EOS Measurement dataclass
# -----------------------------------------------------------------------------

BITS_TO_MBS = 10**-6


class IOSXEInterfaceMeasurement(InterfaceCheckMeasurement):
    """
    This dataclass is used to store the values as retrieved from the EOS device
    into a set of attributes that align to the test-case.
    """

    @classmethod
    def from_cli(cls, cli_payload: dict):
        """returns an EOS specific measurement mapping the CLI object fields"""
        return cls(
            used=cli_payload["admin-status"] != "if-state-down",
            oper_up=cli_payload["oper-status"] == "if-oper-state-ready",
            desc=cli_payload["description"],
            speed=int(cli_payload["speed"]) * BITS_TO_MBS,
        )


def iosxe_check_one_interface(
    device: Device,
    check: InterfaceCheck,
    iface_oper_status: dict,
    results: CheckResultsCollection,
):
    """
    Validates a specific physical interface against the expectations in the
    design.
    """

    result = InterfaceCheckResult(device=device, check=check)

    # if the interface does not exist, then no further checking.

    if not iface_oper_status:
        result.measurement = None
        results.append(result.measure())
        return

    # transform the CLI data into a measurment instance for consistent
    # comparison with the expected values.

    measurement = IOSXEInterfaceMeasurement.from_cli(iface_oper_status)

    if_flags = check.check_params.interface_flags or {}
    is_reserved = if_flags.get("is_reserved", False)

    # -------------------------------------------------------------------------
    # If the interface is marked as reserved, then report the current state in
    # an INFO report and done with this test-case.
    # -------------------------------------------------------------------------

    if is_reserved:
        result.status = CheckStatus.INFO
        result.logs.INFO("reserved", measurement.dict())
        results.append(result.measure())
        return results

    # -------------------------------------------------------------------------
    # Check the 'used' status.  Then if the interface is not being used, then no
    # more checks are required.
    # -------------------------------------------------------------------------

    result.measurement.used = measurement.used

    if not check.expected_results.used:
        results.append(result.measure())
        return

    # If here, then we want to check all the opeational fields.

    result.measurement = measurement

    def on_mismatch(_field, _expected, _measured) -> CheckStatus:
        # if the field is description, then it is a warning, and not a failure.
        if _field == "desc":
            return CheckStatus.WARN

        # if the speed is mismatched because the port is down, then this is not
        # a failure.
        if _field == "speed" and measurement.oper_up is False:
            return CheckStatus.SKIP

    results.append(result.measure(on_mismatch=on_mismatch))
    return
