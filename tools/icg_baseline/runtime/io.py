"""Observe the existing SIM_test_io permission matrix through the real runtime."""

import json
import os
from pathlib import Path


def icg_values():
    return [float(getattr(test_io, f"d{i}")) for i in range(16)]


def icg_observe():
    output = Path(os.environ["ICG_BASELINE_RESULTS"])
    result = {
        "schema_version": 1,
        "scenario": "io-permissions-and-units",
        "sim_time": float(trick.exec_get_sim_time()),
        "initial": icg_values(),
    }
    # Direct SWIG assignment and var_set are distinct legacy API contracts.
    for i in range(16):
        setattr(test_io, f"d{i}", 200.0 + i)
    result["swig_written"] = icg_values()
    result["var_set_status"] = [
        int(trick.var_set(f"test_io.d{i}", 300.0 + i)) for i in range(16)
    ]
    result["var_set_values"] = icg_values()

    test_io.d3 = trick.attach_units("cm", 125.0)
    result["swig_centimeters_in_meters"] = float(test_io.d3)
    result["var_set_kilometers_status"] = int(trick.var_set("test_io.d3", 2.5, "km"))
    result["var_set_kilometers_in_meters"] = float(test_io.d3)
    result["before_checkpoint"] = icg_values()

    trick.checkpoint_cpu(-1)
    trick.TMM_reduced_checkpoint(0)
    trick.checkpoint_objects("icg_model_checkpoint", "test_io")
    checkpoint = output / "icg_model_checkpoint"
    if not checkpoint.is_file() or checkpoint.stat().st_size == 0:
        raise RuntimeError("ICG baseline checkpoint was not written")
    for i in range(16):
        setattr(test_io, f"d{i}", -100.0 - i)
    result["mutated"] = icg_values()
    trick.TMM_set_stl_restore(0)
    # The writer comments out output-only fields. They must remain mutated
    # when this otherwise valid checkpoint is read into existing allocations.
    result["checkpoint_read_status"] = int(trick.TMM_read_checkpoint(str(checkpoint)))
    result["checkpoint_read_values"] = icg_values()

    # Exercise input-only fields too: they cannot appear in the written checkpoint.
    restore_input = Path(os.environ["ICG_BASELINE_RESTORE_INPUT"])
    result["explicit_read_status"] = int(trick.TMM_read_checkpoint(str(restore_input)))
    result["explicit_read_values"] = icg_values()
    (output / "observations.json").write_text(json.dumps(result, indent=2) + "\n")


trick.var_server_set_enabled(False)
trick.exec_set_software_frame(0.1)
trick.add_read(0.1, "icg_observe()")
trick.stop(0.2)
