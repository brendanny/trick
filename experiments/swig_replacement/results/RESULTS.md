# Recorded feasibility results

Recorded on 2026-09-07 from a fresh standalone build against NASA Trick
`c5ba06ea79a8a9ecc3fa4938fd45a77b1e7b9e43`. GCC 13.3, Python 3.12.13, Linux x86_64;
exact package versions and all case details are in
[linux-gcc13-python312.json](linux-gcc13-python312.json).

All **16 processes** completed successfully: eight implementations, each imported
by Python and loaded by a C++ executable embedding Python. Across those runs,
there were **178 passing checks, 46 explicit limitations, and no unexpected
failures**. Two additional probes reproduced nanobind incompatibilities. These
counts describe this fixture's coverage, not relative library quality.

| Option | Checks per mode: pass / limitation | Evidence and implication |
|---|---:|---|
| pybind11 3.1.0 | 13 / 1 | Native allocation/deletion, both bases, Python inheritance and live vector behavior worked. Best first candidate for generated bindings plus shared Trick lifecycle support. General generation is still absent. |
| nanobind 3.0.1 | 10 / 4 | Shared runtime tests and adapted ownership worked. Default construction conflicts with Trick allocation declarations; raw owning returns bypass the required delete behavior; the second base is not implicitly convertible. Viable for a constrained interface after explicit adaptations, with a substantial compatibility cost. |
| Reflection + callable wrappers | 8 / 6 | Generic scalar properties used real `ATTRIBUTES`; a typed callable thunk worked. Good candidate for shared simulation-data access. Native Python model types, general callable generation and rich data types remain to be implemented. |
| Direct CPython | 11 / 3 | Manual native types and checked views worked in both modes. Base-pointer casts are explicit. Offers runtime control, while making all wrapper policy, error handling and API generation Trick's responsibility. |
| Shiboken6 6.11.2 | 12 / 2 | Generated wrappers handled the custom allocator, both bases and Python inheritance. Explicit factory ownership and exception rules were needed. Worth testing on real model headers; this prototype omits its native vector property. |
| cppyy 3.5.0 / Cling | 13 / 1 | Runtime header parsing exposed overloads, both bases, custom allocation and live vectors. Factory ownership was explicitly set. Strong automatic-exposure result; runtime compilation, distribution and deterministic startup need a separate deployment evaluation. |
| Cython 3.3.0 | 11 / 3 | Typed C++ declarations, owning extension classes and explicit casts worked. A credible compiled runtime option; declaration generation and Python API compatibility still require substantial work. |
| CFFI 2.1.1 | 11 / 3 | The C ABI and Python facade preserved the tested behaviors. C++ overloads and inheritance are implemented explicitly behind the ABI; they are not discovered by CFFI. Suitable for a deliberately smaller runtime API. |

The seventh option was evaluated with both Cython and CFFI. For the six adapters
without generic attribute syntax, that separate reflection feature is marked as
a limitation of this implementation. CPython/Cython/CFFI also omit a native
Python multiple-inheritance hierarchy and a live vector property. These omissions
are not claims that those technologies could never implement those features.

## Concrete findings

**Nanobind's default constructor fails to compile.** `nb::init<double>` uses a
`void*` placement-new argument that does not match `TRICK_MM_INTERFACE`'s
class-specific allocation overloads. The excluded target
`poc_nanobind_default_init` reproduces this. The main implementation uses
`nb::new_` with a factory instead.

**Changing construction alone is insufficient.** Returning a raw custom-allocated
pointer with `rv_policy::take_ownership` destroyed the native object but left one
Trick allocation registration. `negative_cases.py` reproduces this in an isolated
process. Returning a `std::shared_ptr` whose deleter uses the class's delete
expression passed both destructor and registration-balance checks, including
through the factory constructor. This adaptation does not establish arbitrary
MM adoption/disowning semantics.

**Nanobind's second base remains a compatibility gap.** The model's secondary
base has a nonzero C++ offset. Passing it to the second-base function raises
`TypeError`, and Python `isinstance(model, Right)` is false. The same native and
Python hierarchy tests passed with pybind11, Shiboken and cppyy. The manual
CPython/Cython/CFFI adapters instead implement explicit C++ pointer casts.

**An embedding smoke test is not an upstream support guarantee.** Nanobind passed
this single-interpreter, native-worker-thread, finalize-once experiment. Its
[porting guide](https://nanobind.readthedocs.io/en/latest/porting.html) nevertheless
lists embedding, multiple inheritance and custom allocation among unsupported
features. Production adoption must resolve that support mismatch.

**Shiboken required explicit free-function exception rules.** With only the
typesystem-level setting, the generated unit-conversion wrapper did not catch
the C++ exception and the test process aborted. The final XML applies
`exception-handling="auto-on"` to each free function. Both invalid units and
invalid checkpoints then propagated as Python exceptions. The policy is
documented by [Shiboken](https://doc.qt.io/qtforpython-6/shiboken6/typesystem_manipulating_objects.html).
Its factory return also has explicit Python ownership.

**cppyy's ownership policy is visible and testable.** The adapter sets
`__python_owns__ = True` on the raw factory result, following its
[ownership controls](https://cppyy.readthedocs.io/en/latest/misc.html).
Constructor and factory destruction then removed the real Trick registrations.

**The shared runtime is necessary regardless of backend.** Every successful
resize/delete/restore invalidation check used the same checked-handle mechanism.
Those results demonstrate that mechanism's portability across the eight
implementations; they do not demonstrate automatic invalidation by any binding
library. The README describes the missing production lifecycle hooks.

## Measurements, not a performance ranking

The JSON records one load/initialization measurement and a 10,000-call warmed
loop over a checked scalar getter, along with process durations and built binary
sizes. These are smoke measurements from one shared machine. The getter includes
allocation lookup; the adapters use different dispatch shapes. No repetitions,
confidence intervals, representative simulation workload or memory profiling
were performed. Installed compiler/runtime dependencies are excluded from the
local binary sizes. Do not extrapolate a Trick build-time or runtime speedup.

| Implementation | Load + fixture initialization (ms) | Warm checked getter (ns/call) |
|---|---:|---:|
| pybind11 | 17.95 | 133.9 |
| nanobind | 14.77 | 96.6 |
| Reflection | 11.09 | 79.5 |
| CPython | 9.18 | 74.7 |
| Shiboken | 96.23 | 227.2 |
| cppyy | 595.37 | 91.0 |
| Cython | 7.82 | 42.9 |
| CFFI | 40.21 | 1043.5 |

Numbers above use the import-mode run; embedding measurements are also retained
in the JSON. All main runs ended with zero fixture objects and zero MM allocation
records. That is a logical lifetime check, not a sanitizer or general leak audit.

## Decision after this experiment

Advance **generated pybind11 + shared Trick data/lifecycle runtime** into a real
simulation integration prototype. Keep reflection as an architectural component,
and use Shiboken/cppyy as generation alternatives in that next comparison.
Nanobind's measured limitations make it a weaker fit for preserving the full
existing C++/Python surface; its factory adaptation is useful evidence if Trick
chooses to simplify that surface. CPython, Cython and CFFI are credible choices
for a controlled runtime boundary, with more API machinery owned by Trick.

The next gate is an unmodified existing simulation input script exercising real
`IPPython`, generated model bindings, ownership transfer, unit-aware assignment,
STL persistence and checkpoint/restart. No option has passed that gate here.
