"""Executed by SIM_test_templates through the real Trick Python input processor."""

import json
import os
import re
from pathlib import Path


def icg_set_nested(integer, reals):
    # These specializations are opaque in SWIG. Resolve actual member names
    # through MemoryManager, using the same metadata as checkpoint restoration.
    output = Path(os.environ["ICG_BASELINE_RESULTS"])
    patch = output / "icg_nested_input"
    prefix = "tso.tobj.TTT_var_template_parameters"
    assignments = [f"{prefix}.aa.t = {integer};"]
    assignments += [
        f"{prefix}.bb[{i}].t = {{{row[0]}, {row[1]}}};" for i, row in enumerate(reals)
    ]
    patch.write_text("\n".join(assignments) + "\n")
    if trick.TMM_read_checkpoint(str(patch)) != 0:
        raise RuntimeError("nested template assignment failed")


def icg_checkpoint(name):
    trick.checkpoint_objects(name, "tso")
    path = Path(os.environ["ICG_BASELINE_RESULTS"]) / name
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("ICG baseline checkpoint was not written")
    return path


def icg_nested_values(checkpoint):
    text = checkpoint.read_text()
    prefix = "tso.tobj.TTT_var_template_parameters"

    def values(member, count):
        matches = re.findall(
            r"(?m)^\s*" + re.escape(prefix + member) + r"\s*=\s*([^;]+);", text
        )
        if len(matches) != 1:
            raise RuntimeError(
                "missing or duplicate nested checkpoint assignment: " + member
            )
        raw = matches[0].strip().strip("{}").split(",")
        if len(raw) != count:
            raise RuntimeError("unexpected nested checkpoint dimensions")
        return [float(value) for value in raw]

    integer = values(".aa.t", 1)[0]
    if not integer.is_integer():
        raise RuntimeError("nested checkpoint integer changed type")
    return {
        "integer": int(integer),
        "reals": [values(f".bb[{i}].t", 2) for i in range(3)],
    }


def icg_values(checkpoint):
    model = tso.tobj
    return {
        "integer": int(model.TTT_var_scalar_builtins.aa),
        "real": float(model.TTT_var_scalar_builtins.bb),
        "integers": [int(model.TTT_var_array_builtins.aa[i]) for i in range(2)],
        "reals": [float(model.TTT_var_array_builtins.bb[i]) for i in range(3)],
        "enum": int(model.TTT_var_enum.aa),
        "enums": [int(model.TTT_var_enum.bb[i]) for i in range(2)],
        "nested": icg_nested_values(checkpoint),
    }


def icg_observe():
    # Run after initialization through the actual scheduler, not just input parsing.
    output = Path(os.environ["ICG_BASELINE_RESULTS"])
    trick.checkpoint_cpu(-1)  # Synchronous write, so file presence is meaningful.
    trick.TMM_reduced_checkpoint(
        0
    )  # Do not emit a global clear for this object subset.
    trick.TMM_set_stl_restore(0)
    icg_set_nested(17, [[1.5, -2.25], [3.5, 4.75], [-5.5, 6.25]])
    checkpoint = icg_checkpoint("icg_model_checkpoint")
    before = icg_values(checkpoint)

    model = tso.tobj
    model.TTT_var_scalar_builtins.aa = -10
    model.TTT_var_scalar_builtins.bb = -20.5
    model.TTT_var_array_builtins.aa = [-1, -2]
    model.TTT_var_array_builtins.bb = [-1.25, 2.5, -3.75]
    model.TTT_var_enum.aa = trick.Bar_2
    model.TTT_var_enum.bb = [trick.Bar_2, trick.Bar_1]
    icg_set_nested(-17, [[-1.5, 2.25], [-3.5, -4.75], [5.5, -6.25]])
    mutated = icg_values(icg_checkpoint("icg_mutated_checkpoint"))

    # Read into the existing allocations; this tests metadata-driven restore.
    # Executive restart/reallocation and Python proxy lifetime are separate gates.
    restore_status = int(trick.TMM_read_checkpoint(str(checkpoint)))
    result = {
        "schema_version": 1,
        "scenario": "templates-checkpoint-read",
        "sim_time": float(trick.exec_get_sim_time()),
        "before": before,
        "mutated": mutated,
        "restored": icg_values(icg_checkpoint("icg_restored_checkpoint")),
        "restore_status": restore_status,
        # Current production SWIG exposes this nested specialization as an
        # opaque pointer. Record the limitation instead of claiming access.
        "nested_binding_available": hasattr(model.TTT_var_template_parameters.aa, "t"),
    }
    (output / "observations.json").write_text(json.dumps(result, indent=2) + "\n")


tso.tobj.TTT_var_scalar_builtins.aa = 1000
tso.tobj.TTT_var_scalar_builtins.bb = 2000.25
tso.tobj.TTT_var_array_builtins.aa = [1, 2]
tso.tobj.TTT_var_array_builtins.bb = [1.25, -2.5, 3.75]
tso.tobj.TTT_var_enum.aa = trick.Bar_1
tso.tobj.TTT_var_enum.bb = [trick.Bar_1, trick.Bar_2]
trick.var_server_set_enabled(False)
trick.exec_set_software_frame(0.1)
trick.add_read(0.1, "icg_observe()")
trick.stop(0.2)
