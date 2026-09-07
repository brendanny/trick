"""Executed in a fresh process per backend, both imported and embedded.

Limits are deliberately separate from successes; unexpected errors always fail.
The shared-runtime tests are not claims about automatic backend invalidation.
"""
import gc
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapters import BUILD, load

class Limitation(Exception): pass

def raises(operation):
    try:
        operation()
    except Exception:
        return
    raise AssertionError("operation unexpectedly accepted invalid/stale input")

def run(backend):
    start = time.perf_counter()
    api = load(backend)
    api.initialize(str(BUILD / "libpoc_fixture.so"))
    startup = time.perf_counter() - start
    results = {}

    def record(name, fn):
        before = time.perf_counter()
        try:
            detail = fn()
            status = "pass"
        except Limitation as error:
            status, detail = "limitation", str(error)
        except Exception:
            status, detail = "fail", traceback.format_exc()
        results[name] = {"status": status, "detail": detail,
                         "seconds": time.perf_counter() - before}

    def require_native():
        if backend == "reflection":
            raise Limitation("Generic records intentionally expose data and selected thunks; no native Python Model class.")

    def native_model():
        require_native()
        before = api.live_models()
        obj = api.Model(2.)
        assert obj.mass == 2.
        obj.mass = 3.
        assert obj.adjust(2) == 7.  # int overload doubles its input
        assert obj.adjust(.5) == 7.5
        obj.position_set(1, 4.)
        assert obj.position_get(1) == 4.
        obj.sample_push(9.)
        assert obj.sample_get(0) == 9.
        raises(lambda: obj.position_get(3))
        del obj
        gc.collect()
        assert api.live_models() == before
        return "Construct/mutate; both overloads; fixed array and vector methods; exception; one destructor."

    def native_mi():
        require_native()
        obj = api.Model(2.)
        assert api.right_offset(obj) > 0
        assert api.left(obj) == 11
        if backend == "nanobind":
            try:
                value = api.right(obj)
            except TypeError:
                raise Limitation("Observed: second-base implicit conversion rejected; Right has a nonzero C++ offset.")
            assert value == 29
        else:
            assert api.right(obj) == 29
        return "Both base-pointer calls return correct values across a nonzero secondary-base offset."

    def python_mi():
        require_native()
        if backend in ("cpython", "cython", "cffi"):
            raise Limitation("This adapter implements explicit base-pointer casts, not a Python multiple-inheritance hierarchy.")
        obj = api.Model(2.)
        if backend == "nanobind" and not isinstance(obj, api.Right):
            raise Limitation("Observed: Model is not an instance of the registered secondary base Right.")
        assert isinstance(obj, api.Left) and isinstance(obj, api.Right)
        return "Python isinstance recognizes both C++ bases."

    def allocation(factory=False):
        require_native()
        before, records = api.live_allocated(), api.allocations()
        obj = api.new_allocated(3.) if factory else api.Allocated(3.)
        assert api.live_allocated() == before + 1
        registered = obj.registered()
        during = api.allocations()
        del obj
        gc.collect()
        assert api.live_allocated() == before, "native destructor not called exactly once"
        assert api.allocations() == records, "allocation registration leaked"
        assert registered and during == records + 1
        if backend == "nanobind" and not factory:
            raise Limitation("Default nb::init does not compile with TRICK_MM_INTERFACE (separate compile probe); nb::new_ factory constructor passed registration/destruction checks here.")
        return "Real TRICK_MM_INTERFACE registered storage; Python ownership removed registration and destroyed exactly once."

    def aliases():
        api.array("alias_data", 3)
        a, b = api.View("alias_data"), api.View("alias_data")
        a.set(1, 9.)
        assert b.get(1) == 9.
        del a
        gc.collect()
        assert b.get(1) == 9.  # dropping a borrowed wrapper must not delete storage
        raises(lambda: b.get(-1))
        raises(lambda: b.set(3, 2.))
        api.erase("alias_data")
        raises(lambda: b.get(1))
        return "Live aliases share actual MM storage; wrapper GC retains storage; bounds/deletion checked."

    def resize():
        api.array("resized_data", 2)
        old = api.View("resized_data")
        old.set(0, 7.)
        api.resize("resized_data", 5)
        raises(lambda: old.get(0))
        raises(old.size)
        fresh = api.View("resized_data")
        assert fresh.size() == 5 and fresh.get(0) == 7.
        fresh.set(4, 2.)
        assert fresh.get(4) == 2.
        api.erase("resized_data")
        return "Real MM resize preserves data; shared epoch rejects old handles; fresh handle sees new size."

    def replacement():
        api.array("replaced_data", 1)
        old = api.View("replaced_data")
        api.erase("replaced_data")
        api.array("replaced_data", 1)
        raises(lambda: old.get(0))
        api.erase("replaced_data")
        return "Allocation identity rejects stale aliases even when the name is reused."

    def checkpoint():
        before = api.live_models()
        api.managed("checkpoint_model", 12.)
        model = api.View("checkpoint_model")
        assert model.field_get("mass") == 12.
        assert model.call_adjust(1.5) == 13.5
        api.array("checkpoint_data", 2)
        array = api.View("checkpoint_data")
        array.set(1, 42.)
        text = api.checkpoint()
        assert "checkpoint_model" in text and "checkpoint_data" in text
        model.field_set("mass", 99.)
        array.set(1, -2.)
        api.restore(text)
        raises(lambda: model.field_get("mass"))
        raises(lambda: array.get(1))
        assert api.View("checkpoint_model").field_get("mass") == 13.5
        assert api.View("checkpoint_data").get(1) == 42.
        assert api.live_models() == before + 1
        api.erase("checkpoint_model")
        api.erase("checkpoint_data")
        assert api.live_models() == before
        return "Actual ClassicCheckPointAgent serialized/restored C++ record and array; old handles rejected."

    def units():
        assert math.isclose(api.convert(1., "ft", "m"), .3048)
        assert math.isclose(api.convert(0., "degC", "K"), 273.15)
        raises(lambda: api.convert(1., "m", "kg"))
        return "UDUNITS scale, affine offset and incompatible-dimension exception."

    def invalid_checkpoint():
        raises(lambda: api.restore("not_a_type broken;"))
        return "Invalid checkpoint declaration propagates a Python exception through the adapter."

    def vector():
        require_native()
        if backend not in ("pybind", "nanobind", "cppyy"):
            raise Limitation("This adapter exposes vector methods only; a native live container property is not implemented.")
        obj = api.Model(1.)
        view = obj.samples
        obj.sample_push(3.)
        assert view[0] == 3.
        view[0] = 8.
        assert obj.sample_get(0) == 8.
        del obj
        gc.collect()
        assert view[0] == 8., "container view did not retain its Python-owned parent"
        del view
        gc.collect()
        return "Opaque/live vector property mutates C++ storage and retains Python-owned parent."

    def reflection():
        if backend != "reflection":
            raise Limitation("Generic attribute syntax is a separate architectural experiment; not added to this adapter.")
        api.managed("reflected_model", 3.)
        obj = api.View("reflected_model")
        assert obj.mass == 3.
        obj.mass = 5.
        assert obj.call_adjust(.5) == 5.5
        raises(lambda: obj.unknown_field)
        api.erase("reflected_model")
        raises(lambda: obj.mass)
        return "Property reads/writes resolve real ATTRIBUTES; callable uses representative typed thunk."

    for name, fn in (
        ("native_model", native_model), ("secondary_base_cast", native_mi),
        ("python_multiple_inheritance", python_mi),
        ("default_custom_allocator", allocation),
        ("owned_factory", lambda: allocation(True)),
        ("borrowed_aliases", aliases), ("resize_invalidation", resize),
        ("name_reuse_invalidation", replacement), ("checkpoint_restore", checkpoint),
        ("invalid_checkpoint", invalid_checkpoint), ("units", units),
        ("live_vector", vector), ("reflection_syntax", reflection)):
        record(name, fn)
    # The benchmark is a smoke measurement, not a decision-quality performance study.
    api.array("benchmark_data", 1)
    obj = api.View("benchmark_data")
    count = 10000
    start = time.perf_counter()
    for _ in range(count): obj.get(0)
    call_ns = (time.perf_counter() - start) * 1e9 / count
    api.erase("benchmark_data")
    gc.collect()
    results["final_lifetime_balance"] = {
        "status": "pass" if api.live_models() == api.live_allocated() == api.allocations() == 0 else "fail",
        "detail": {"models": api.live_models(), "allocated": api.live_allocated(), "records": api.allocations()}}
    result = {"backend": backend, "mode": os.environ.get("POC_MODE", "import"),
              "startup_seconds": startup, "checked_get_ns": call_ns, "cases": results}
    print("POC_RESULT=" + json.dumps(result), flush=True)
    return not any(case["status"] == "fail" for case in results.values())

if __name__ == "__main__":
    if not run(sys.argv[1]):
        raise RuntimeError("feasibility checks failed; see POC_RESULT")
