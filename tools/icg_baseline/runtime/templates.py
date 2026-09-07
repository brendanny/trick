"""Executed by SIM_test_templates through the real Trick Python input processor."""

import json
import os
from pathlib import Path


def icg_values():
    model = tso.tobj
    return {
        "integer": int(model.TTT_var_scalar_builtins.aa),
        "real": float(model.TTT_var_scalar_builtins.bb),
        "integers": [int(model.TTT_var_array_builtins.aa[i]) for i in range(2)],
        "reals": [float(model.TTT_var_array_builtins.bb[i]) for i in range(3)],
        "enum": int(model.TTT_var_enum.aa),
        "enums": [int(model.TTT_var_enum.bb[i]) for i in range(2)],
        "nested": int(model.TTT_var_template_parameters.aa.t),
    }


def icg_observe():
    # Run after initialization through the actual scheduler, not just input parsing.
    output = Path(os.environ["ICG_BASELINE_RESULTS"])
    before = icg_values()
    trick.checkpoint_cpu(-1)  # Synchronous write, so file presence is meaningful.
    trick.TMM_reduced_checkpoint(
        0
    )  # Do not emit a global clear for this object subset.
    trick.checkpoint_objects("icg_model_checkpoint", "tso")
    checkpoint = output / "icg_model_checkpoint"
    if not checkpoint.is_file() or checkpoint.stat().st_size == 0:
        raise RuntimeError("ICG baseline checkpoint was not written")

    model = tso.tobj
    model.TTT_var_scalar_builtins.aa = -10
    model.TTT_var_scalar_builtins.bb = -20.5
    model.TTT_var_array_builtins.aa = [-1, -2]
    model.TTT_var_array_builtins.bb = [-1.25, 2.5, -3.75]
    model.TTT_var_enum.aa = trick.Bar_2
    model.TTT_var_enum.bb = [trick.Bar_2, trick.Bar_1]
    model.TTT_var_template_parameters.aa.t = -17
    mutated = icg_values()

    # Read into the existing allocations; this tests metadata-driven restore.
    # Executive restart/reallocation and Python proxy lifetime are separate gates.
    trick.TMM_set_stl_restore(0)  # This probe restores arithmetic/enum fields only.
    restore_status = int(trick.TMM_read_checkpoint(str(checkpoint)))
    result = {
        "schema_version": 1,
        "scenario": "templates-checkpoint-read",
        "sim_time": float(trick.exec_get_sim_time()),
        "before": before,
        "mutated": mutated,
        "restored": icg_values(),
        "restore_status": restore_status,
    }
    (output / "observations.json").write_text(json.dumps(result, indent=2) + "\n")


tso.tobj.TTT_var_scalar_builtins.aa = 1000
tso.tobj.TTT_var_scalar_builtins.bb = 2000.25
tso.tobj.TTT_var_array_builtins.aa = [1, 2]
tso.tobj.TTT_var_array_builtins.bb = [1.25, -2.5, 3.75]
tso.tobj.TTT_var_enum.aa = trick.Bar_1
tso.tobj.TTT_var_enum.bb = [trick.Bar_1, trick.Bar_2]
tso.tobj.TTT_var_template_parameters.aa.t = 17
trick.var_server_set_enabled(False)
trick.exec_set_software_frame(0.1)
trick.add_read(0.1, "icg_observe()")
trick.stop(0.2)
