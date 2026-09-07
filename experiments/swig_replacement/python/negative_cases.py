"""Isolate a known unsafe ownership policy so it cannot poison the main suite."""
import gc
import json
from adapters import BUILD, load

api = load("nanobind")
api.initialize(str(BUILD / "libpoc_fixture.so"))
before = api.allocations()
obj = api.raw_new_allocated(1.)
assert obj.registered()
del obj
gc.collect()
evidence = {"remaining_objects": api.live_allocated(),
            "remaining_registrations": api.allocations() - before}
observed = evidence == {"remaining_objects": 0, "remaining_registrations": 1}
print("POC_PROBE=" + json.dumps({"name": "nanobind_raw_ownership",
      "status": "observed_limitation" if observed else "fail", "evidence": evidence}), flush=True)
if not observed:
    raise RuntimeError("ownership behavior differs from pinned expected limitation")
