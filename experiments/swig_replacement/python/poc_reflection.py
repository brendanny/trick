"""Generic data access through Trick ATTRIBUTES plus one callable thunk.

Uses the manual CPython runtime for checked handles; no Model Python type is
registered here. This is an architectural hybrid, not another binding library.
"""
from adapters import load
_runtime = load("cpython")
for _name in ("initialize", "array", "managed", "resize", "erase", "checkpoint",
              "restore", "convert", "live_models", "live_allocated", "allocations"):
    globals()[_name] = getattr(_runtime, _name)

class View:
    def __init__(self, name): object.__setattr__(self, "_view", _runtime.View(name))
    def __getattr__(self, field): return self._view.field_get(field)
    def __setattr__(self, field, value): self._view.field_set(field, value)
    def get(self, index): return self._view.get(index)
    def set(self, index, value): self._view.set(index, value)
    def size(self): return self._view.size()
    def field_get(self, name): return self._view.field_get(name)
    def field_set(self, name, value): self._view.field_set(name, value)
    def call_adjust(self, value): return self._view.call_adjust(value)
