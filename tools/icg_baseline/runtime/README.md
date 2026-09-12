# Configured simulation and runtime evidence

`simulation.py` drives `SIM_test_templates`, `SIM_test_io`, and the focused
`SIM_icg_lifecycle` through the production
Perl configuration processor, legacy ICG, SWIG, generated-source compilation,
linking, and the Trick executable. It does not substitute the new extractor or
alter the existing template or I/O models. The lifecycle case compares the
observed MemoryManager operations with separately extracted facts, then relinks
with candidate lifecycle exports and repeats the checks. The template case
relinks five candidate metadata tables and repeats checkpoint/readback.

The same configured workflow also runs the standalone
[scalar MemoryManager gate](../scalars/README.md): separate legacy/candidate
executables register two external records with 13 bool/char/float/long fields,
arrays and aliases. Compact decimal and expanded hexadecimal checkpoints must
restore every mutated value, including long limits and float extremes/subnormals.
Three deliberate mutations must fail at execution. This uses the configured
Trick archives and does not alter the three simulation models below.

## Reproduce

Use a fresh checkout or worktree. Install the dependencies in
[icg-simulation.yml](../../../.github/workflows/icg-simulation.yml), then run:

```sh
./configure --with-llvm=/usr/lib/llvm-17 --with-python=/usr/bin --with-swig=/usr/bin \
  --disable-java --without-x --without-hdf5 --without-gsl --without-civetweb \
  CC=gcc-13 CXX=g++-13 PYTHON_VERSION=3
make -j2 no_dp TRICK_VERBOSE_BUILD=1 ICG_CLANGLIBS=-lclang-cpp
/usr/bin/python3 tools/icg_baseline/simulation.py \
  --case templates --extractor /tmp/icg-extract/trick-icg-extract \
  --output /tmp/icg-simulation-evidence/templates --jobs 2
/usr/bin/python3 tools/icg_baseline/simulation.py \
  --case io --output /tmp/icg-simulation-evidence/io --jobs 2
python3 tools/icg_baseline/simulation.py \
  --case memorymanager --extractor /tmp/icg-extract/trick-icg-extract \
  --output /tmp/icg-simulation-evidence/memorymanager --jobs 2
```

Build the standalone extractor and install `jsonschema` in the runner interpreter
as shown in the workflow before running the template or MemoryManager cases.

This lane is Linux x86-64, LLVM 17.0.6, GCC 13, Python 3.12, and SWIG 4.2.
It builds Trick core and its current bindings. Java tools, data products, X11,
HDF5, GSL, and CivetWeb are outside this scoped run. This is not evidence for the
GCC 8.5/12 or Python 3.11/SWIG 4.1 minimum stacks.

The explicit `ICG_CLANGLIBS` build setting selects Ubuntu's combined Clang shared
library. The legacy configure static-archive list omits LLVM 17's ASTMatchers
dependency and otherwise fails to link. This recipe records the supported
package linkage without modifying production configure or ICG sources.

The runner refuses existing generated simulation outputs and existing evidence
directories. It never cleans a checkout. `--root` selects another prepared
checkout; the runtime probe is taken from the tooling checkout and its digest is
recorded. Preserve verbose configure/core-build logs and package versions as CI
does; the collector cannot reconstruct earlier build commands from a binary.

## What is captured

| Stage | Command / evidence |
|---|---|
| `cold` | Full `trick-CP` build from a fresh simulation directory, including generated-source compile/link |
| `warm` | Repeat `trick-CP`; record content and mtime churn without assuming a no-op |
| `runtime-warm` | Execute the linked simulation with the probe below |
| `forced` | `make -f makefile force_ICG`; includes Make startup and prerequisites |
| `rebuilt` | Full `trick-CP` after forced generation, recompiling/relinking as required |
| `runtime-rebuilt` | Repeat the runtime probe with the resulting executable |

Each build stage uses the existing simulation corpus's required artifact groups,
including `S_source.hh`, `build/S_source.cpp`, legacy metadata, registry, build
rules, and SIE. Optional SWIG/build outputs are captured when present. Missing
required groups or a missing/ambiguous executable fail the run. Each stage keeps
raw logs, measurements, sidecars, and churn; the summary retains configuration,
input/expected-output digests, and the actual executable digest for each run.
The selected probe, auxiliary checkpoint input, and expected values/diagnostics
are copied under `runtime-inputs/`; their digests are recorded in the summary.
`--case` defaults to `templates` for compatibility. CI builds core once, runs
all three cases, and uploads `icg-configured-simulations-llvm17-linux`; evidence is
separated by case. The I/O and lifecycle captures still run if a previous capture
fails, provided the shared core and required extractor builds succeeded.
GNU `timeout` bounds complete build commands (20 minutes by default) and runtime
commands (60 seconds), terminating their process groups on expiry.
`--jobs` sets `MAKEFLAGS`; `trick-CP` does not accept Make's `-j` option or named
targets as its own command-line arguments.

Full generated snapshots are retained as CI artifacts and compared between
stages, with `cold-*.diff` files. They are **observations**, not yet approved
portable goldens. Root-derived SWIG names, generated ordering, and SIE appends
are not normalized away. A successful capture does not imply zero churn or
textual equivalence between all build stages. The existing isolated-header
goldens continue to be checked separately.

## Candidate template metadata

The template comparison extracts the unchanged model and generates the
`TTT1<int, double>`, `TTT1<int[2], double[3]>`, `Foo<int>`, `Foo<double[2]>` and
`TTT1<Foo<int>, Foo<double[2]>[3]>` metadata fragments. It checks the original
headers against the immutable capture. Explicit containing-field IDs select the
three outer uses; structured dependency closure includes the two `Foo` leaves.
The independent comparison checks captured symbols and field expectations.

Before the simulation builds, `template_structured.py` links separate full legacy
and candidate probes against the configured Trick archives using `trick-config`.
The real MemoryManager must resolve the exact child table pointers and sizes.
Native checks require zero/null structured rows before initialization and verify
the repeat-call guard. Five controls remove a registration, change a child lookup,
preinitialize a size, bypass the guard, or remove a child export. Each must fail
at its intended run/link stage; compilation failures and timeouts do not count.
`structured-native/` retains sources, commands, observations, mutation failures,
link configuration and archive digests. These probes use no MemoryManager stubs.

An isolated overlay renames old table/init/size/UnitsMap definitions inside their
five generated blocks and preserves the original ABI references in the containing
record. Forward declarations allow those references to resolve to the appended
candidate. Legacy lifecycle helpers and all other metadata/registries remain.
The simulation must recompile/relink without ICG overwriting the overlay, and
`runtime-candidate` must match both the independent expected checkpoint/readback
values and `runtime-rebuilt` observations. Nested leaves have nonzero integer
and array values assigned through MemoryManager checkpoint input, mutated, then
restored. Separate checkpoints observe each state despite opaque nested SWIG
bindings. Missing/duplicate assignments or wrong dimensions fail the probe.

`candidate-templates/` retains original/candidate/overlay sources, request, model,
symbols and hashes, build command and log. Native negative controls prove changed
candidate offsets reach the containing record and a missing candidate table
cannot fall back to its renamed legacy definition. This is a comparison adapter,
not production template/STL integration or a binding replacement.

## MemoryManager lifecycle contract

The `memorymanager` case requires a standalone facts extractor and Python
`jsonschema>=4.18,<5`. CI builds the LLVM 17 extractor and installs the validator
in a separate virtual environment. Simulation Python remains the configured
production interpreter. The original lifecycle header and definitions are
fingerprinted against their captured reference; facts, extractor commands,
diagnostics, source/comparison fingerprints, and runtime evidence are retained.

| Operation | Observation |
|---|---|
| `declare_var` for tracked and implicit-default classes, counts 1/3 | Generated allocation, initial values, `ALLOC_INFO` size/range/dimensions/language, name and interior-address lookup |
| `delete_var` by name and address | Forward destructor events with fact-derived strides; registry removal before callbacks; name/address lookup removed |
| Deleted-default POD, counts 1/3 | Zeroed raw storage, no construction or typed object access, generated no-op destructor and storage release by MemoryManager |
| `declare_extern_var` then unregister | No premature destructor; caller storage remains writable and is destroyed explicitly by the caller |
| SWIG constructors with `TMMName`, with/without constructor arguments | Proxy ownership relinquished; actual `TRICK_LOCAL`/`TRICK_ALLOC_NEW` record; MemoryManager scalar deletion and subsequent proxy disposal |
| No-default and abstract allocation requests | Null result, unchanged allocation map, no events; exactly the two expected pairs of missing-allocator diagnostics |

Nine executions and two rejected requests run through the real configured
simulation at time 0.1. The comparison derives sizes and lifecycle availability
from schema-validated facts; the immutable fixture definitions supply expected
values and event order. JSON comparison distinguishes booleans from integers.
The allocation map must return to its initial size. Extra/missing runtime errors
fail even if the process returns zero. A success report requires both the Python
observations and the C++ MemoryManager document; this case does not write a
checkpoint. Mutation tests recompute fact digests before checking rule coverage.

After completing the legacy stages, the runner now generates an independent
lifecycle-only candidate from the same facts and explicit policy request. A test
overlay renames the original lifecycle exports, retains the legacy metadata and
registry code, and adds the candidate. The simulation must recompile and relink;
regeneration that discards the overlay is an error. `runtime-candidate` repeats
the MemoryManager/SWIG checks and must match both independently specified
expectations and the legacy observations. The candidate therefore supplies the
original lifecycle symbols used by real runtime dispatch; the renamed legacy
exports cannot satisfy a missing candidate function.

`candidate-lifecycle/` retains the original source, candidate, overlay, request,
resolved model, symbol list, hashes, build command and build log. The native
overlay negative control deliberately removes a candidate allocator and requires
lookup failure. This is an isolated evidence adapter, not a production switch.

This closes the focused dispatch/registration gap, not general lifecycle policy.
It excludes executive checkpoint restart, recursive user destructors, concurrent
registration, OOM/exception recovery, over-aligned types, arbitrary class-specific
allocation, and destruction of private-destructor objects. The full configured
simulation is not sanitizer-instrumented; the separate captured-wrapper gate
retains its ASan/UBSan/LSan checks. No generated production backend is replaced.

## Template runtime contract

The real Trick input processor executes `templates.py`. The probe sets integer,
floating, array, and enum fields through SWIG and observes them
in a scheduler callback at simulation time 0.1 seconds. It writes a synchronous
checkpoint of `tso`, mutates those fields, calls `TMM_read_checkpoint`, and records
the restored values. Reduced checkpoints are disabled for this object subset to
avoid emitting a global allocation-clear command. STL restoration is disabled
for this arithmetic/enum probe; it is a separate coverage gate.

`templates.expected.json` independently specifies the initial, changed, and
restored states, observation time, and restore return code. The collector checks
the complete document, requires a checkpoint containing the model's assignments,
and rejects global-clear checkpoints. A zero process exit without these outputs
is a failure, including Python errors that the simulation might otherwise log.
The binary must also exit successfully after the callback. Results and raw
checkpoint text are retained for inspection before and after regeneration.
Python tracebacks and legacy checkpoint-parser failure diagnostics also fail the
gate: the legacy reader can log a parse failure while returning zero.

The existing bindings expose `TTT_var_template_parameters.aa` as an opaque
`SwigPyObject`, without access to its `t` member. The observations explicitly
record `nested_binding_available: false`; nested-template Python access is an
observed coverage gap, not a successful read/write check. An intentional binding
improvement requires reviewing this baseline expectation.

This covers checkpoint reading into existing allocations. It does not cover
executive restart, allocation reconstruction, proxy lifetimes, units conversion,
I/O permissions, every template form, or a new-versus-legacy backend comparison.
The Python plumbing tests use synthetic malformed evidence to check rejection;
the configured CI lane runs the actual simulation.

## I/O and units runtime contract

`io.py` executes the existing `SIM_test_io` matrix of 16 annotated fields at
simulation time 0.1 seconds. Each row below combines all four variable I/O modes
(`**`, `*o`, `*i`, `*io`) with the indicated checkpoint mode. Values are observed
through the real SWIG bindings before and after each operation.

| Fields | Checkpoint mode | Written checkpoint | Readback after all fields are mutated |
|---|---|---|---|
| `d0`–`d3` | `**` | Omitted | Remain mutated |
| `d4`–`d7` | `*o` | `OUTPUT-ONLY` comments | Remain mutated |
| `d8`–`d11` | `*i` | Omitted | Remain mutated |
| `d12`–`d15` | `*io` | Active assignments | Restore saved values |

The probe checks these distinct legacy behaviors:

- Direct SWIG reads and assignments work for all 16 public fields, including
  those without variable-input permission. This is distinct from `var_set`.
- `var_set` accepts the eight input-enabled fields and leaves rejected fields
  unchanged. `d0`, with all four permission bits disabled, has no generated
  metadata: its status is `2` (missing reference). The other seven rejections
  return `1` (input disabled). These are observed contracts, not new policies.
- Assigning `attach_units("cm", 125.0)` yields `1.25 m`; `var_set` with `2.5 km`
  yields `2500 m`. Both results are exactly representable and compared exactly.
- The generated checkpoint must contain precisely the eight selected numeric
  fields, with the correct values and comment/assignment distinction above.
  Extra, duplicate, missing, or incorrectly active fields fail validation.
- After readback, the independently authored `io.restore_input` attempts all
  16 fields. Only `d8`–`d15` change to the specified values, exercising
  checkpoint-input-only fields as well as forbidden input.

The deliberate negative read produces invalid-reference and failed-assignment
diagnostics for `d0`, seven permission warnings, an eight-invalid-assignments
summary, and restore-failure messages. The legacy reader still returns `0`;
the baseline records that fact.
`io.expected-diagnostics.json` lists the complete expected messages from this
read and `var_set`. The collector compares their multiplicities across stdout
and stderr after removing log prefixes/ANSI colors. Extra or missing classified
messages, any Python traceback, or incorrect observed values fail the gate.
These specific expected failures do not relax the template runtime gate.

The contract covers variable input, checkpoint input/output, direct SWIG access,
and two length conversions. It does not establish variable-server output
permissions, affine/dimensionally invalid conversions, pointer/string behavior,
restart/reallocation, STL restoration, or replacement-backend equivalence.

## Remaining evidence gates

Broaden units/permissions coverage and add full checkpoint restart,
capture the minimum stacks and macOS, and select representative medium
and large/old models. Review and promote stable generated-output references only
with their actual package/configuration provenance. These two focused simulations
does not close Phase 0 or establish a performance distribution.

The [integer extension](../integers/README.md) adds a second standalone configured
MemoryManager gate. `integer_runtime.py` compares two records / 22 fields at
signed and unsigned boundaries in compact and expanded checkpoints, including
full 64-bit unsigned maxima. It reuses the scalar runner and adds six independent
runtime mutations. It does not modify the three simulation models above.
