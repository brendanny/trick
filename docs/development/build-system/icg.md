# A5: native interface code generator

`TRICK_BUILD_ICG=ON` builds the existing `trick-ICG` executable directly with
CMake. The build target is also available as `Trick::ICG`. This is the existing
Clang frontend, not the separate ICG rewrite. Its 21 local C++ sources and the
existing units-mapping source are listed explicitly.

```sh
cmake --preset icg -DLLVM_DIR=/path/to/llvm/lib/cmake/llvm \
  -DUDUNITS2_ROOT=/path/to/udunits
cmake --build --preset icg --parallel 3
ctest --preset icg
```

`icg` selects Ninja, disables utility archives and enables ICG and CTest. Direct
configuration works with other generators, including multi-config generators.
`TRICK_BUILD_ICG` defaults to OFF, so utility-only builds still need no LLVM.
Enabling ICG discovers LLVM/Clang and UDUNITS regardless of the dependency
preflight profile; it does not require Python, SWIG, Flex/Bison or GUI packages.

The executable is under the binary directory's
`trick_source/codegen/Interface_Code_Gen` subdirectory (plus configuration for a
multi-config generator). A complete installed SDK remains unavailable. No
framework Make, source-tree binary copying, or Autoconf configuration is used.

## Dependency and include-path handling

LLVM/Clang config targets own link dependencies. When available, the shared
`clang-cpp` and `LLVM` targets are used together; otherwise Clang component targets
supply the dependency graph. CMake manages build rpaths, including macOS dynamic
libraries. No global library directories, manual LLVM library filename lists,
`install_name_tool` calls or hard-coded Homebrew prefixes are added.

The target uses C++17, the LLVM package's definitions and RTTI setting, and private
Trick/version definitions. The selected GNU compiler version is provided to ICG's
existing model-language setup. These settings do not propagate to utility targets.

The selected installation's Clang executable supplies `-print-resource-dir`.
Its major version and tools directory must match the LLVM package, and its
`stddef.h` resource header must exist. `TRICK_ICG_CLANG_EXECUTABLE` is an explicit
file hint for that installation, not permission to mix another Clang distribution.

A generated build-tree header records CMake's implicit include directories with
C++ wrappers first, selected Clang builtin headers next, then other system headers.
Host-Clang builtin directories are replaced; SDK symlinks are resolved so ICG
recognizes system headers consistently. The CMake-built ICG
uses this list directly instead of invoking `trick-gte` or guessing an LLVM
resource path. Reconfigure after changing compiler/SDK packages. This preview's
model compiler context is the configured C++ compiler; per-simulation toolchain
configuration is part of C1 and 32-bit host/target separation is E3.

If `TRICK_HOME` is unset, the CMake-built executable defaults it to the configured
source checkout, because existing ICG selection/output code still uses that
variable. An existing value is preserved. This is an explicit build-tree
configuration, not an installed or relocatable SDK contract. The Autotools-built
ICG keeps its existing compiler/header discovery behavior.

UDUNITS' XML database must be available at its package default location or via
its native `UDUNITS2_XML_PATH` environment variable. The smoke test exercises
units handling as well as library loading.

## Tests and boundaries

`icg.smoke` checks the reported Trick version, processes a class with array and
integer fields plus standard-library includes, verifies generated metadata,
checks the input is unchanged, and rejects malformed C++. It unsets `TRICK_HOME`
and empties `TRICK_CXX` to exercise the native configuration path. All inputs and
legacy ICG side products are confined to a disposable fixture under the binary
tree. ICG's output naming, depfiles, registration maps and full generation contract
remain B1; this layer does not claim collision-safe framework code generation.

The CI workflow builds/runs against LLVM 14 on Ubuntu 24.04 and LLVM 20 on macOS 26.
macOS also reports dynamic-library dependencies with `otool`. Exact local results
and package provenance are in [a5-validation.json](a5-validation.json). CI must
pass before the respective platform is considered qualified; configuration alone
is not execution evidence.
