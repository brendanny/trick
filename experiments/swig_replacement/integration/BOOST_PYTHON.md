# Boost.Python integration experiment

Boost.Python is feasible for the checked-handle integration path tested here.
Boost 1.87.0 passes release and sanitizer runs, including actual Python
finalization. The older 1.83 configuration exposes a native holder-alignment
defect despite passing its release run.

This backend uses the same MSD input, actual IPPython lifecycle, RK4 driver,
MemoryManager checkpoint machinery and nine runtime contract groups as the
pybind11 backend. It adds no SWIG runtime or generated SWIG wrapper. The default
backend remains pybind11; select Boost with `POC_INTEGRATION_BACKEND=boost`.

## Reproduce

Use the Linux/compiler/Python/Flex/Bison/UDUNITS prerequisites in the
[integration README](README.md). Boost.Python must be built as a shared library
for the same Python major/minor version as the executable. Use Boost 1.87.0 for
the corrected configuration tested here. Ubuntu 24.04's 1.83 package has the
holder alignment defect described below.

From `experiments/swig_replacement`, with that native Boost installation available:

```bash
python3 -m venv venv-boost
. venv-boost/bin/activate
python -m pip install -r integration/requirements-boost.txt
cmake -S . -B build/msd-boost -G Ninja \
  -DPOC_INTEGRATION_ONLY=ON -DPOC_INTEGRATION_BACKEND=boost \
  -DCMAKE_BUILD_TYPE=Release -DPython_EXECUTABLE="$(command -v python)" \
  -DCMAKE_PREFIX_PATH=/path/to/boost-prefix
cmake --build build/msd-boost --parallel 4
ctest --test-dir build/msd-boost --output-on-failure
python integration/run.py --build-dir build/msd-boost
```

This requirements file contains only libclang, CMake and Ninja. The Boost-only
build and runner do not require pybind11 or nanobind. If UDUNITS lives in another
prefix, use a semicolon-separated CMake prefix list. Set `Boost_DIR` explicitly
when several versions are installed; use separate build directories for each
backend/version. The runner checks the executable's reported binding version
against CMake's selection and records the Boost runtime filename and SHA256.

To build Boost itself, obtain the official
[Boost 1.87.0 source archive](https://www.boost.org/releases/1.87.0/). The SHA256
for `boost_1_87_0.tar.bz2` is
`af57be25cb4c4f4b413ed692fe378affb4352ea50fbe294a11ef548f4d527d89`.
From its extracted directory:

```bash
./bootstrap.sh --with-libraries=python \
  --with-python="$(command -v python)" --prefix=/path/to/boost-prefix
./b2 --with-python python=3.12 variant=release link=shared \
  threading=multi cxxstd=17 -j4 install
```

Substitute the selected Python version. For a virtual environment or relocatable
Python, check the generated `project-config.jam`: its `using python` entry may
need the actual executable, development include directory and library directory
explicitly. The run in this report supplied those three paths for Python 3.12.13.

The integration sanitizer build uses another directory and these additional
CMake options:

```bash
-DCMAKE_BUILD_TYPE=Debug \
-DCMAKE_C_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer" \
-DCMAKE_CXX_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer"
```

Run it with:

```bash
ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 \
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
  python integration/run.py --build-dir build/msd-boost-asan
```

For the recorded 1.87 sanitizer run, Boost.Python itself was also rebuilt with
sanitizers, using B2's `variant=debug` plus
`cxxflags="-fsanitize=address,undefined -fno-omit-frame-pointer"` and
`linkflags="-fsanitize=address,undefined"`. Install that build to a separate
prefix (set `--prefix`, `--includedir` and `--libdir`), then select its `Boost_DIR`
when configuring the integration sanitizer build. Merely instrumenting the
experiment does not instrument an existing Boost.Python runtime.

The instrumented scope includes the compiled Trick core, generated bindings,
metadata, adapter, consumer module, driver and, for 1.87, the Boost.Python runtime.
Python and UDUNITS binaries remain uninstrumented. LeakSanitizer is disabled
because the standalone fixture retains process-lifetime services; model
destructor balance and MM-record cleanup are checked explicitly. No address,
alignment or other UB checks are suppressed.

The runner returns nonzero on failures; sanitizer findings are not converted to
expected passes. Older Boost releases remain selectable specifically so their
failure can be reproduced, with a configure-time warning below version 1.87.

## Implementation

`generate.py` extracts and validates one declaration model. The existing metadata
emitter produces the same native headers and lifecycle/STL callbacks for either
backend. `emit_boost.py` supplies Boost.Python class, constructor, property,
callable, named-cast and ownership-transfer registrations. Generator tests cover
both emitters and verify that choosing a backend preserves declarations and
metadata byte-for-byte.

`boost_bindings.hh` and `boost_module.cpp` implement Python numeric conversion,
iterable conversion, exception translation and module registration. Conversion
finishes before native bounds/liveness checks, including when `__float__` shrinks
a vector. Static-method registration happens after all overloads are defined.

Native ownership is shared with pybind11: `construct_native`, `State`, `Handle<T>`
and `DoubleView` live outside either binding library. Boost's `make_constructor`
owns a heap-allocated **handle**; the handle's shared State determines whether
Python or MM owns the model. Adoption changes that state and the MM allocation
recipe. We do not bind raw MM pointers with `reference_existing_object`, and we
do not depend on Boost's default deletion policy for Trick-allocated storage.

The separate `_msd_consumer` extension and builtin `trick` module share one
Boost.Python dynamic library and its conversion registry. The contract suite
passes an MSD handle across that module boundary and checks its invalidation
after deletion and restore. This is interoperability between Boost.Python
modules; it does not test exchanging wrapper objects with pybind11 in one process.

## Dependency finding: holder alignment

Ubuntu 24.04's `libboost-python1.83-dev`/runtime version `1.83.0-2.1ubuntu3`
passes the release integration run. UBSan nevertheless stops in
`boost/python/make_constructor.hpp` while constructing a pointer holder: its
address is not aligned to the required eight bytes. See the retained
[1.83 sanitizer failure](results/boost-1.83-asan-ubsan.json).

The constructor calls the holder allocator without its alignment argument.
Upstream [commit b988d702](https://github.com/boostorg/python/commit/b988d702074b3227967f3d440865d0659583f255)
supplies that argument and corrects heap-padding arithmetic. The first final
release tag containing that commit is `boost-1.87.0`; the 1.86 tag still has the
three-argument constructor call. This experiment uses the upstream fix through
the newer dependency, without vendoring a Boost patch or disabling alignment
checks.

## Measured results

Tested on Linux x86-64, GCC 13.3 and Python 3.12.13. The 1.83 runtime came from
Ubuntu 24.04; the 1.87 runtimes were built from the verified upstream archive.

| Backend | Release integration | ASan + UBSan | Interpreter finalization |
|---|---|---|---|
| Boost.Python 1.83.0 | Nine groups pass | Fails on holder alignment | Passes in release; sanitizer run aborts earlier |
| Boost.Python 1.87.0 | Nine groups pass | Nine groups pass, including instrumented Boost runtime | Passes in both builds |
| pybind11 3.1.0, shared runtime regression | Nine groups pass | Not rerun for this increment | Passes in release |

Machine-readable evidence:

* [Boost 1.83 release](results/boost-1.83-release.json) and
  [sanitizer failure](results/boost-1.83-asan-ubsan.json).
* [Boost 1.87 release](results/boost-1.87-release.json) and
  [sanitizer run](results/boost-1.87-asan-ubsan.json).
* [pybind11 regression](results/pybind-shared-runtime.json).

The passing runs have identical final position and velocity. Analytic errors are
approximately `7.53e-10 m` and `3.16e-9 m/s`; checkpoint continuation reproduces
both final values exactly in these runs. All nine probe constructions have
matching destructions and no MM allocations remain after shutdown.

The driver deliberately leaves one Python-owned probe retained only by an
interior array alias until `IPPython.shutdown()`. It verifies the outstanding
allocation before finalization and its destruction afterward. This exercises
native cleanup during `Py_Finalize`, not just finalization after manual cleanup.

All 17 generator tests pass. The generated headers, metadata and declaration
JSON for the actual MSD integration are byte-identical across Boost and pybind11.
The earlier eight-backend fixture matrix was not rerun for this increment.

## Scope

The existing generator and production-integration boundaries in the
[main README](README.md#remaining-boundary-and-next-step) still apply. This
experiment investigates the checked-handle design; a custom Boost holder exposing
native model types directly is a separate, unimplemented alternative.

Interpreter finalization is checked with the actual `IPPython.shutdown()` and
`!Py_IsInitialized()`. There is no skip-finalization workaround. A checkpoint
restart is not an interpreter restart: repeated initialize/finalize cycles,
subinterpreters, free-threaded Python, Python 3.14 and non-Linux platforms are
not validated by this experiment. No binding-throughput or build-performance
advantage over pybind11 is claimed.
