# A2: configuration-only CMake preview

The obsolete framework CMake implementation has been replaced. This layer
configures a C/C++ project and runs bootstrap tests; it does not compile Trick,
produce a simulation SDK, or replace the current installation instructions.
`cmake --install` deliberately fails until the SDK installation layer exists.

## Try the preview

Requirements: CMake **3.26.0 or newer**, a working C and C++ compiler, and a
generator backend such as GNU Make or Ninja. No LLVM, Python, Java, SWIG, or
other Trick dependencies are discovered yet; that starts in A4/A5.

From the repository root:

```sh
cmake --workflow --preset bootstrap
```

Or run each stage directly:

```sh
cmake --preset bootstrap
cmake --build --preset bootstrap
ctest --preset bootstrap
```

`bootstrap` honors normal CMake generator discovery, including `CMAKE_GENERATOR`.
`bootstrap-ninja` selects Ninja; `bootstrap-multi` selects Ninja Multi-Config.
All use separate directories under `build/cmake`. A multi-config build uses
`--config`/the preset's configuration; it does not depend on `CMAKE_BUILD_TYPE`.
The presets use schema 6, supported by the minimum CMake.

Direct configuration remains supported:

```sh
cmake -S . -B /tmp/trick-preview -G Ninja -DBUILD_TESTING=OFF
cmake --build /tmp/trick-preview
```

Compiler and toolchain choices use CMake's normal command-line/environment
interfaces. Use a new build directory when changing the compiler or generator.
Put machine-specific presets in ignored `CMakeUserPresets.json`.

## Version and source-tree behavior

`share/trick/trick_ver.txt` remains the only version authority. CMake reads it
without executing it or requiring Git/Perl. `PROJECT_VERSION` contains the
numeric version; `TRICK_VERSION` retains prerelease/build suffixes. Generated
`TrickVersionInfo.cmake` records both in the build tree. Editing the source
version file triggers automatic reconfiguration on the next build.

An in-source configure is rejected before compiler setup/generation, including
path aliases resolving to the same directory. CMake may still leave its cache
or `CMakeFiles` after a failed invocation. Remove only those files created by
that attempt; **do not delete the checked-in Makefile**. Successful external
configuration/builds do not write generated files into the source tree.

The two independent example CMake projects listed in the A1 inventory remain
intact. Autoconf inputs, framework/simulation Makefiles, Maven configuration,
and ICG's legacy output behavior are unchanged. Old CMake-specific ICG output
branches are handled by B1; Maven output plumbing is handled by D3.

## Tests and qualification

CTest exercises external source/build paths containing spaces, source-content
preservation, rejection of in-source configuration, release/prerelease versions,
malformed or duplicate version declarations, version-change regeneration, and
rejection of an empty installation. Failure tests use disposable miniature
source fixtures, not the working checkout. Tests are written in CMake script
and do not impose a Python test dependency.

To test rejection with an actual older executable:

```sh
cmake --preset bootstrap -DTRICK_TEST_OLD_CMAKE=/path/to/cmake-3.25.2
ctest --preset bootstrap --output-on-failure
```

The workflow `cmake-bootstrap.yml` provisions CMake 3.26.0 and 3.25.2 on Linux
and macOS with Unix Makefiles, Ninja, and Ninja Multi-Config. A passing local
Linux test is not a macOS qualification result. This preview also does not
establish the GCC/LLVM minimum compatibility gates or a successful legacy
Trick build; those require their later component/dependency checks.

See [the build contract](README.md), [roadmap](roadmap.md), and
[qualification records](qualification.md) for the remaining migration scope.
