# B6: embedded Python and complete native runtime linkage

Predecessor: B5. Enable `TRICK_BUILD_PYTHON=ON`, or use the `runtime` preset.
This enables Core and its prerequisite layers, finds a coherent Python
interpreter/embed library, and discovers SWIG. It exposes `Trick::PythonInput`
and the complete build-tree `Trick::Runtime` linkage. SDK installation and
`trick-CP` integration remain C1/C2; this is still a developer preview.

The existing InputProcessor and four SWIG interfaces supply the runtime bindings.
Independent Python compatibility fixes are carried by the prerequisite branch.
CMake's UseSWIG generates wrappers with native dependency tracking. Each module
owns its own SWIG output directory; proxy modules are staged under `<build>/python`.
The parser sees Trick's explicit include paths, while compiled wrappers receive
Python/UDUNITS development includes through target links. Passing Python's
implementation headers to `-includeall` is deliberately avoided.

`trick_init_core_python_modules()` from `trick/python_modules.h` registers the
four built-in modules before `Py_Initialize`. It leaves interpreter lifetime and
simulation-specific module registration to the executable. A simulation's
existing `init_swig_modules` hook is not overridden. The build-tree `trick` Python
package exposes core bindings; it does not pretend to contain generated model
bindings or the full installed Python tooling.
Python 2 also supports the existing IPPython hook after interpreter initialization:
the helper directly initializes all four modules and propagates Python errors.
The helper is not idempotent: calling it again after Python 2 initialization
reruns the module initializers; Python 3 rejects an already initialized
interpreter. Call it once per interpreter lifecycle, holding the GIL when the
interpreter is already initialized. The public header documents both contracts.
The IPPython startup script accepts an unset `TRICK_PYTHON_PATH` as empty.
Genuine startup failures call `exec_terminate_with_return`, because the scheduler
ignores `ip.init()`'s return value; a return alone could silently skip the input.

`trick_enable_runtime(target)` links `Trick::Runtime` and enables the executable
symbol exports used by MemoryManager. Core metadata uses CMake's native
`WHOLE_ARCHIVE` link feature so unreferenced named allocators survive static
archive elimination. Other dependencies use their ordinary target links and
declared static cycles. No global linker flags or recursive framework Make are
used. The four wrapper archives are separate native targets linked through the
Python input target/registration entry point, rather than physically merged into
one archive; C1/C2 must preserve this dependency closure in SDK consumers.

Acceptance:

```sh
cmake --preset runtime
cmake --build --preset runtime --parallel 3
ctest --preset runtime
```

The embedded smoke starts the existing IPPython implementation, imports all four
modules, reads/writes a real Clock field, exercises the fixed-array `swig_ref`
wrapper, and reads/writes an allocated integrator state pointer. It then shuts
Python down. Separate tests unset `TRICK_PYTHON_PATH` and require an actual input
file to execute, and unset `TRICK_HOME` to force a startup failure. The latter
ignores `init()`'s return exactly as the scheduler does and requires the termination
exception before the input runs. All runtime CI combinations run both tests.
The core allocation and existing memory/queue tests remain enabled.
`TRICK_BUILD_RUNTIME_TESTS=ON` and `TRICK_BUILD_UTILITY_TESTS=ON` add existing
GoogleTest suites; they require GoogleTest development files.

For a disposable checkout/build, `python cmake/tests/verify_build_graph.py
--source . --build <build> --config Release` checks no-op ICG generation, transitive
header changes, deleted metadata, a changed ICG executable, an ER7 toggle in the same cache, isolated grammar
regeneration, and a transitive SWIG input. It temporarily changes source mtimes
and a grammar comment and restores them. Run it separately from other builds.
CI runs the native build with read-only production source directories first,
then these regeneration checks, on Linux and macOS and with ER7 enabled/disabled.

DEC-01/BD-07: the defaults are `TRICK_PYTHON_MAJOR=3` and
`TRICK_SWIG_MAJOR=4`. The deprecated compatibility selections remain available:

```sh
cmake -S . -B build/compat -DTRICK_BUILD_PYTHON=ON \
  -DTRICK_PYTHON_MAJOR=2 -DTRICK_SWIG_MAJOR=3 \
  -DPython2_EXECUTABLE=/usr/bin/python2 -DSWIG_EXECUTABLE=/usr/bin/swig
```

Each selected legacy tool produces a prominent configure warning naming its
version/path and the modern replacement, even when ordinary CMake deprecation
warnings are disabled. Python 2 and SWIG 3 support will be removed in Trick 27. There is
no silent fallback from the modern defaults. The dependency report records the
actual interpreter, embed library, SWIG executable and versions. Python 2 module
registration uses the Python 2 initialization ABI; Python 3 uses `PyInit_*`.
Python 2 is selectable with either SWIG major. Use a fresh build directory when changing
toolchain installations, or update the cached executable/library hints together.

The Rocky 8 CI compatibility lanes build the entire runtime and run its embedded
smoke with GCC 8.5, CMake 3.26.0 and SWIG 3 for both Python 2 and Python 3. They
also verify the deprecation warnings and run graph checks with `python3.9 -O`.
The other Rocky 8 lanes test SWIG 4/Python 2 and SWIG 4/Python 3.
The latter uses the default major selections and rejects deprecation warnings. The existing
Linux/macOS lanes qualify the modern defaults. Package reports in
each run provide exact revisions; adding a lane is not itself a passing result.

See [validation](b-stack-validation.json) and the CI workflow for exact tested
platform/tool versions and remaining qualification limits. Trick 27 deprecates
Autotools; Trick 29 removes it, as established by the migration contract.
