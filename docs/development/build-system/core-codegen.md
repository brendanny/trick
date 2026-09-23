# B4: core metadata graph

Predecessor: B3. Enable `TRICK_BUILD_CORE_METADATA=ON` to build ICG, MemoryManager
and the selected integrators, generate the core metadata, and compile
`Trick::CoreMetadata`. It is not a linked runtime or installed SDK yet.

`cmake/TrickCoreHeaders.cmake` is the reviewed output inventory: 145 headers with
Trick algorithms and 213 with ER7. The latter includes ER7's duplicate basenames.
The legacy `files_to_ICG.hh` remains the input umbrella. Each source has one
owning target. CMake declares the metadata sources, maps, SIE fragment, manifest
and success stamp as outputs. The depfile carries all parsed transitive headers;
ICG's executable, the inventory, and configured feature flags are explicit
prerequisites. Output directories separate multi-config configurations.

`--output-inventory <file>` is an optional addition to B1's runtime contract. It
requires `--output-root`, reads canonical header paths (one per line), emits
empty sources for headers with no metadata in that configuration, and rejects
undeclared generated headers. This lets CMake know the whole graph before the
build. Adding a core header with metadata requires updating the inventory;
removing a class leaves an empty output instead of stale compiled metadata.

Acceptance: build then run `ctest --test-dir <build> -L icg --output-on-failure`.
`icg.core_manifest` verifies that the emitted graph matches the declarations.
The ICG contract test also checks inactive outputs and inventory mismatch.
A no-op `cmake --build <build> --target trick_core_codegen` must do no work;
touching a transitive header, deleting an output, rebuilding ICG, or changing
`TRICK_USE_ER7_UTILS` must rerun the generator. All writes stay in the binary tree.

BD-05/BD-06: explicit-output ICG reports system-header errors as failures instead
of silently suppressing them. It advertises Clang's GNU compatibility version
4.2.1, rather than the compiler used to build ICG. In the locally tested Ubuntu
24.04/GCC 13.3/LLVM 14.0.6/glibc 2.39 tuple, impersonating GCC 13 selected
unsupported `_Float32` declarations and malloc attributes in glibc. This change
preserves the existing compiler include paths and leaves legacy callers alone.
The native ICG also leaves explicitly requested system directories in their
compiler-defined position when already implicit. Ubuntu 24.04/GCC 13/LLVM 14
installs UDUNITS headers in `/usr/include`; moving that directory ahead of the
C++ wrappers breaks `#include_next <stdlib.h>`. Nonstandard dependency prefixes
still take the requested precedence.

BD-01/BD-18: CMake output ownership and native depfiles replace timestamp checks
and recursive Make. Metadata is a dedicated archive pending B5/B6 linkage;
whole-runtime registration is not claimed by this layer.
