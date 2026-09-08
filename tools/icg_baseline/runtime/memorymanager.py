"""Run through the real input processor and named SWIG ownership transfer."""

import json
import os
from pathlib import Path


def icg_observe():
    output = Path(os.environ["ICG_BASELINE_RESULTS"])
    lifecycle.probe.begin()
    # TMMName is the production shadow-constructor path that registers scalar
    # new storage as TRICK_LOCAL/TRICK_ALLOC_NEW and gives up proxy ownership.
    tracked = trick.IcgLifecycleTracked(TMMName="icg_mm_new_tracked")
    tracked_owned = bool(tracked.thisown)
    lifecycle.probe.owned_tracked(tracked)
    del tracked  # The C++ object has been deleted; never dereference the proxy.
    explicit = trick.IcgLifecycleNoDefault(61, TMMName="icg_mm_new_explicit")
    explicit_owned = bool(explicit.thisown)
    lifecycle.probe.owned_no_default(explicit)
    del explicit
    lifecycle.probe.finish(str(output / "memorymanager.json"))
    (output / "observations.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scenario": "memorymanager-lifecycle",
                "sim_time": float(trick.exec_get_sim_time()),
                "named_proxy_ownership": [tracked_owned, explicit_owned],
            },
            indent=2,
        )
        + "\n"
    )


trick.var_server_set_enabled(False)
trick.exec_set_software_frame(0.1)
trick.add_read(0.1, "icg_observe()")
trick.stop(0.2)
