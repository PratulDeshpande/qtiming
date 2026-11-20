"""Pass-manager stage plug-in `qtiming` for the `scheduling` stage: check, then strip annotations.

The contract comes from the QTIMING_CONTRACT environment variable (a path or a shipped
instance name). Select it with `generate_preset_pass_manager(..., scheduling_method="qtiming")`.
"""

from __future__ import annotations

import os

from qiskit.transpiler import PassManager
from qiskit.transpiler.preset_passmanagers.plugin import PassManagerStagePlugin

from .strip import StripTimingAnnotations
from .timing_check import TimingCheck


class QtimingSchedulingPlugin(PassManagerStagePlugin):  # type: ignore[misc]
    def pass_manager(self, pass_manager_config, optimization_level=None):  # type: ignore[no-untyped-def]
        contract = os.environ.get("QTIMING_CONTRACT")
        if not contract:
            raise ValueError("set QTIMING_CONTRACT to a contract path or shipped instance name")
        return PassManager([TimingCheck(contract, fail_on="refuted"), StripTimingAnnotations()])
