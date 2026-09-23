# B6: embedded Python and complete native runtime linkage

Predecessor: B5. Enable `TRICK_BUILD_PYTHON=ON`, or use the `runtime` preset.
This enables Core and its prerequisite layers, finds a coherent Python 3
interpreter/embed library, and discovers SWIG. It exposes `Trick::PythonInput`
and the complete build-tree `Trick::Runtime` linkage. SDK installation and
`trick-CP` integration remain C1/C2; this is still a developer preview.

The existing InputProcessor and four SWIG interfaces are used unchanged.
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
Python down. The core allocation and existing memory/queue tests remain enabled.
`TRICK_BUILD_RUNTIME_TESTS=ON` and `TRICK_BUILD_UTILITY_TESTS=ON` add existing
GoogleTest suites; they require a GoogleTest config package.

For a disposable checkout/build, `python cmake/tests/verify_build_graph.py
--source . --build <build> --config Release` checks no-op ICG generation, transitive
header changes, deleted metadata, a changed ICG executable, an ER7 toggle in the same cache, isolated grammar
regeneration, and a transitive SWIG input. It temporarily changes source mtimes
and a grammar comment and restores them. Run it separately from other builds.
CI runs the native build with read-only production source directories first,
then these regeneration checks, on Linux and macOS and with ER7 enabled/disabled.

DEC-01/BD-07: the native runtime is Python 3-only; explicitly selecting Python 2
fails. A4's standalone preflight can still inspect Python 2, and the legacy build
route remains during transition. This layer does not raise the documented
Python 3 or SWIG floor based on unrelated modernization work: local evidence is
Python 3.12.14/SWIG 4.2.0, and older supported tuples still require qualification.

See [validation](b-stack-validation.json) and the CI workflow for exact tested
platform/tool versions and remaining qualification limits. Trick 27 deprecates
Autotools; Trick 29 removes it, as established by the migration contract.
