# Generated Python bindings through IPPython

This follow-on to the eight-backend comparison closes selected integration gaps:
model binding generation, Python-to-Trick ownership transfer, full MM STL restore,
and execution through the actual `IPPython` implementation.

The default backend is pybind11. A selectable [Boost.Python experiment](BOOST_PYTHON.md)
uses the same declaration model, native ownership runtime, container views, MSD
driver and nine integration contract groups. That report covers the dependency
version constraint exposed by sanitizers and the interpreter-finalization result.

It compiles the **unchanged MSD model sources** from `trick_sims/SIM_msd` and
Trick's actual RK4 and integrator C interface. A new headless
[`RUN_bindings/input.py`](../../../trick_sims/SIM_msd/RUN_bindings/input.py) supplies
ordinary model settings and unit-bearing values. A small driver calls the model
jobs; this is **not the production S_define/Executive scheduler build**. Stock
GUI/realtime input files were not run. The new input is intended to be usable by
the normal simulation too, but that separate execution path has not been tested.

## Build and run

Use Linux with a C++17 compiler, Python development headers, Flex, Bison and
UDUNITS development/data packages. From `experiments/swig_replacement`:

```bash
python3 -m venv venv
. venv/bin/activate
python -m pip install -r integration/requirements.txt
cmake -S . -B build/msd -G Ninja \
  -DPOC_INTEGRATION_ONLY=ON -DCMAKE_BUILD_TYPE=Release \
  -DPython_EXECUTABLE="$(command -v python)"
cmake --build build/msd --parallel 4
ctest --test-dir build/msd --output-on-failure
```

Use a separate build directory from the original comparison. The integration-only
configuration needs libclang and the selected binding library, without the other
adapter toolchains. To include this lane in the comparison's build instead, configure
with `-DPOC_BUILD_INTEGRATION=ON` and install both sets of requirements.

The default `python integration/run.py` uses `build/msd`. `--build-dir` and
`--output` override its locations. The runner sets up the embedded interpreter,
loads the separate consumer module, and records diagnostics plus numerical and
lifetime results. Generated C++, declaration JSON, logs and results stay in the
build directory. CTest also runs 17 generator tests: eight boundary tests per
backend and one check that backend selection preserves declarations and metadata.

For dependencies under a separate prefix, add `-DCMAKE_PREFIX_PATH=/prefix` and
put its Flex/Bison executables on `PATH`. Extracted Bison installations can also
need `BISON_PKGDATADIR=/prefix/share/bison` and `M4=/prefix/bin/m4`. The runner finds
UDUNITS XML relative to the configured include directory, or accepts the usual
`UDUNITS2_XML_PATH`. Relocatable Python distributions with stale library paths
may need `-DPython_LIBRARY=/actual/path/to/libpython3.12.so.1.0`.

## What changed

[`generate.py`](generate.py) parses the real model header with libclang, constructs
a versioned declaration model, and emits two consumers of that model:

* Trick `ATTRIBUTES`, `io_src_*` allocation/destruction hooks, and STL checkpoint,
  restore, cleanup and element-access callbacks.
* pybind11 or Boost.Python constructors, properties, selected method calls, named casts and
  ownership-transfer operations over checked model handles.

The policy selects records, callable names and allocation recipes; field names,
types, fixed extents, unit tokens and callable signatures come from Clang/source
annotations. Offsets use native-compiler `offsetof` with a standard-layout
assertion, so generating metadata does not run model constructors.

The generated records are the existing `MSD`, a minimal `BindingDynamics` shell
containing it, and `BindingProbe`, a lifecycle adversary with the real
`TRICK_MM_INTERFACE`, a fixed array and a `std::vector<double>`. The declaration
JSON includes source and policy fingerprints. This is a bounded experiment,
not an integration with or replacement for the separate TrickCodeGen rewrite.

[`runtime.cpp`](runtime.cpp) gives each root allocation shared ownership state.
Nested model, array, vector and cross-module handles all share that state. Every
access checks the MM allocation ID; manager-owned handles also check the restore
generation. Vector views resolve their container on every call, so vector growth
does not leave a cached element pointer behind.
The native value/view implementation in [`values.hh`](values.hh) and constructor
cleanup in [`runtime.hh`](runtime.hh) are shared by both binding adapters.

`trick.TMMName(object, "name")` explicitly transfers an existing Python-owned
root to MM. Generated constructors also accept `TMMName="name"`. Failed naming
retains Python ownership; duplicate, invalid, repeated and interior-object
adoptions are rejected. Dropping Python wrappers after transfer does not delete
the model. `thisown` is a read-only compatibility property for `IPPython`'s named
variable refresh, not a general reimplementation of SWIG's ownership API.

Allocation recipes are explicit:

| Native allocation | Python-owned cleanup | After MM adoption |
|---|---|---|
| Ordinary `new MSD` / `new BindingDynamics` | Remove external registration, then `delete` | `TRICK_LOCAL` + `TRICK_ALLOC_NEW`, generated delete hook |
| `TRICK_MM_INTERFACE` on `BindingProbe` | Remove external registration, explicit destructor and `free` | `TRICK_LOCAL` + `TRICK_ALLOC_MALLOC`, generated destructor hook and MM's `free` |

The second recipe matches the macro's `calloc` storage. It avoids calling the
macro's delete operator after MM has already removed the allocation record.
Consequently it differs from legacy SWIG's blanket `TRICK_ALLOC_NEW` assignment.
This ownership policy is confined to the experiment; the native correctness fixes
described below do not change the allocation macro. It does not implement arrays of Python-created objects,
arbitrary custom allocators, ownership transfer back to Python, or borrowed raw
pointers escaping the checked-handle API.

The executable compiles the repository's **actual** `InputProcessor.cpp` and
`IPPython.cpp`. Its legacy-named `init_swig_modules` hook registers a pybind11
builtin module instead (or the selected Boost.Python module). Generated `castAsTYPE` functions let the existing named
variable refresh run unchanged. The test executes `init`, worker-thread `parse`,
`restart`, and `shutdown`/Python finalization. Logging, command-line and termination
services have small standalone adapters. Neither a SWIG runtime nor SWIG-generated
wrapper code is compiled into this lane.

## Verification

The runtime gate checks nine contract groups, including:

* Generated nested fields and unit conversions; constructor and static-method
  argument forwarding; type conversion through a separately compiled Python
  extension linked to the model/runtime shared libraries.
* Python-owner retention by interior views, adoption with existing aliases,
  failure cleanup, named constructors, deletion and allocation-name reuse.
* Unit-aware scalar/array/vector assignment; conversion failure without partial
  array writes; live vector aliases across storage growth; bounds revalidation
  after a Python numeric conversion that shrinks the vector.
* The normal `MemoryManager::init_from_checkpoint(..., true)` STL restore path,
  `IPPython.restart` name rebinding, and rejection of old root/interior/container
  handles. The public `get_checkpoint_restore_state()` detects parser failures
  despite the unconditional return code in the MM restore entry point.

The driver runs 200 steps of 0.01 seconds for the undamped MSD. It compares position
and velocity to the closed-form forced-oscillator solution, checkpoints halfway,
restores, and repeats the second half. Regular-run errors were approximately
`7.53e-10 m` and `3.16e-9 m/s`; restored continuation reproduced both final values
exactly in this run. Python finalized, all MM allocations were removed, and all
eight probe constructions had matching destructions.

See [the regular run](results/release.json) and
[the sanitizer run](results/asan-ubsan.json) for measured results and declarations.
The [original pybind11 prototype regression](results/pybind-regression.json)
also passes in import and embedded modes: 26 case passes, two previously reported
limitations, zero failures. The other seven original backends were not rerun.

The sanitizer build instruments the compiled Trick core, generated metadata,
binding runtime, consumer extension and driver with GCC AddressSanitizer and
UndefinedBehaviorSanitizer. Installed Python and UDUNITS libraries are not
instrumented. LeakSanitizer is disabled: the standalone fixture retains
process-lifetime core services; the explicit model lifetime and MM-record checks
do not establish whole-process leak freedom. No address/UB checks are suppressed.
Reproduce using the same dependency configuration as above:

```bash
cmake -S . -B build/msd-asan -G Ninja \
  -DPOC_INTEGRATION_ONLY=ON -DCMAKE_BUILD_TYPE=Debug \
  -DPython_EXECUTABLE="$(command -v python)" \
  -DCMAKE_C_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer" \
  -DCMAKE_CXX_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer"
cmake --build build/msd-asan --parallel 4
ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 \
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
  python integration/run.py --build-dir build/msd-asan
```

## Native defects exposed by this gate

This increment includes two small prerequisite core fixes discovered by the
sanitizer run. The MSD model and IPPython sources remain unchanged.

* `Integrator::state_in` wrote a trailing null pointer past `state_origin` when
  exactly `num_state` arguments were loaded. ASan reported an eight-byte write
  immediately after RK4's two-pointer allocation. The terminator is now written
  only when there is room. The driver deliberately retains the exact two-state
  configuration, exercising this boundary on every completed RK4 step.
* `MemoryManager::declare_var` initialized `allocation_type` only for structured
  objects, leaving primitive arrays (including STL checkpoint staging arrays)
  with an indeterminate enum. UBSan stopped in `delete_var` during checkpoint
  cleanup. All paths in this overload allocate with `calloc`, so the recipe now
  defaults to `TRICK_ALLOC_MALLOC`. This fixes primitive-array cleanup as well
  as the invalid enum load. The actual vector checkpoint/restore gate exercises
  creation and deletion of those staging arrays.

These fixes address the observed paths; they are not a broader audit of core
allocation, integrator argument validation, or the ER7 backend.

## Remaining boundary and next step

The generator supports selected global, standard-layout records with public
double fields, one-dimensional fixed double arrays, nested selected records,
`vector<double>`, double constructor arguments and a small scalar/reference
callable subset. Unsupported pointer graphs, inheritance, deleted constructors,
bitfields and multidimensional arrays fail explicitly. It does not implement
the full Trick annotation/IO-selection language: unit tokens are extracted,
while emitted field IO flags are uniformly 15 in this lane.

Restoration remains reset-first and nontransactional, matching the core path.
Generation changes currently enter through this runtime's restore operation;
arbitrary external MM resize/restore calls and concurrent model access still need
production lifecycle notifications and synchronization. RK4 is checkpointed at
a completed step boundary; the driver reconstructs its time and retains no
intermediate stage. No scheduler, integrator-workspace, variable-server, logging
service, real `trickify` build, Python virtual override or platform matrix has
been validated here.

Next, replace the standalone registration/service/driver adapters with an opt-in
production Python-binding backend in the `S_define`/`trick-CP` build. Feed the
binding emitter a shared TrickCodeGen declaration representation, establish MM
lifecycle notifications, and run this same headless input under the actual
Executive and integration scheduler. Preserve the ownership, STL restart and
cross-module checks as required gates for that transition.
