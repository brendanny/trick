# Configured simulation and runtime evidence

`simulation.py` drives the existing `SIM_test_templates` through the production
Perl configuration processor, legacy ICG, SWIG, generated-source compilation,
linking, and the Trick executable. It does not substitute the new extractor or
alter the simulation's existing model or `S_define`.

## Reproduce

Use a fresh checkout or worktree. Install the dependencies in
[icg-simulation.yml](../../../.github/workflows/icg-simulation.yml), then run:

```sh
./configure --with-llvm=/usr/lib/llvm-17 --with-python=/usr/bin --with-swig=/usr/bin \
  --disable-java --without-x --without-hdf5 --without-gsl --without-civetweb \
  CC=gcc-13 CXX=g++-13 PYTHON_VERSION=3
make -j2 no_dp TRICK_VERBOSE_BUILD=1 ICG_CLANGLIBS=-lclang-cpp
/usr/bin/python3 tools/icg_baseline/simulation.py \
  --output /tmp/icg-simulation-evidence --jobs 2
```

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
| `forced` | `trick-CP force_ICG`; includes Make startup and prerequisites |
| `rebuilt` | Full `trick-CP` after forced generation, recompiling/relinking as required |
| `runtime-rebuilt` | Repeat the runtime probe with the resulting executable |

Each build stage uses the existing simulation corpus's required artifact groups,
including `S_source.hh`, `build/S_source.cpp`, legacy metadata, registry, build
rules, and SIE. Optional SWIG/build outputs are captured when present. Missing
required groups or a missing/ambiguous executable fail the run. Each stage keeps
raw logs, measurements, sidecars, and churn; the summary retains configuration,
input/expected-output digests, and the actual executable digest for each run.
GNU `timeout` bounds complete build commands (20 minutes by default) and runtime
commands (60 seconds), terminating their process groups on expiry.

Full generated snapshots are retained as CI artifacts and compared between
stages, with `cold-*.diff` files. They are **observations**, not yet approved
portable goldens. Root-derived SWIG names, generated ordering, and SIE appends
are not normalized away. A successful capture does not imply zero churn or
textual equivalence between all build stages. The existing isolated-header
goldens continue to be checked separately.

## Runtime contract

The real Trick input processor executes `templates.py`. The probe sets integer,
floating, array, enum, and nested-template fields through SWIG and observes them
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

This covers checkpoint reading into existing allocations. It does not cover
executive restart, allocation reconstruction, proxy lifetimes, units conversion,
I/O permissions, every template form, or a new-versus-legacy backend comparison.
The Python plumbing tests use synthetic malformed evidence to check rejection;
the configured CI lane runs the actual simulation.

## Remaining evidence gates

Broaden the configured corpus to I/O/units/permissions and full checkpoint
restart, capture the minimum stacks and macOS, and select representative medium
and large/old models. Review and promote stable generated-output references only
with their actual package/configuration provenance. This one focused simulation
does not close Phase 0 or establish a performance distribution.
