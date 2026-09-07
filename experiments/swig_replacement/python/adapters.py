"""Normalize spelling only; backend-specific coverage is explicit in cases.py."""
import importlib
import os
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BUILD = Path(os.environ.get("POC_BUILD", ROOT / "build"))


def load(backend):
    if backend in ("pybind", "nanobind", "cython"):
        return importlib.import_module("poc_" + backend)
    if backend == "cffi":
        return importlib.import_module("poc_cffi")
    if backend == "reflection":
        return importlib.import_module("poc_reflection")
    if backend == "cpython":
        module = importlib.import_module("poc_cpython")
        def call(op, handle=None, text="", second="", index=0, value=0.):
            return module.dispatch(op, handle, text, second, index, value)
        return SimpleNamespace(
            Model=module.Model, Allocated=module.Allocated, View=module.View,
            new_allocated=module.Allocated,
            initialize=lambda p: call(0, text=p),
            array=lambda n, c: call(1, text=n, index=c),
            managed=lambda n, v: call(2, text=n, value=v),
            resize=lambda n, c: call(3, text=n, index=c),
            erase=lambda n: call(4, text=n),
            restore=lambda t: call(5, text=t),
            convert=lambda v, a, b: call(6, text=a, second=b, value=v),
            live_models=lambda: call(7), live_allocated=lambda: call(8),
            allocations=lambda: call(9), left=lambda x: call(19, x),
            right=lambda x: call(20, x), right_offset=lambda x: call(21, x),
            checkpoint=lambda: call(30))
    if backend == "cppyy":
        import cppyy
        cppyy.add_include_path(str(ROOT / "include"))
        cppyy.add_include_path(str(ROOT.parents[1] / "include"))
        if os.environ.get("POC_NATIVE_PREFIX"):
            cppyy.add_include_path(str(Path(os.environ["POC_NATIVE_PREFIX"]) / "include"))
        cppyy.load_library(str(BUILD / "libpoc_fixture.so"))
        cppyy.include("poc.hh")
        g = cppyy.gbl
    elif backend == "shiboken":
        g = importlib.import_module("poc_shiboken")
    else:
        raise ValueError(backend)
    result = SimpleNamespace(**{name: getattr(g, "poc_" + name) for name in (
        "initialize", "array", "managed", "resize", "erase", "checkpoint", "restore",
        "convert", "live_models", "live_allocated", "allocations", "left", "right",
        "right_offset", "new_allocated")})
    for name in ("Model", "Allocated", "View", "Left", "Right"):
        setattr(result, name, getattr(g, "POC" + name))
    if backend == "cppyy":
        # Raw pointer returns are borrowed by cppyy by default. State the policy.
        factory = result.new_allocated
        def owned(value):
            obj = factory(value)
            obj.__python_owns__ = True
            return obj
        result.new_allocated = owned
    return result
