# B4: core metadata graph

Predecessor: B3. Enable `TRICK_BUILD_CORE_METADATA=ON` to build ICG, MemoryManager
and the selected integrators, generate the core metadata, and compile
`Trick::CoreMetadata`. It is not a linked runtime or installed SDK yet.

`cmake/TrickCoreHeaders.cmake` is the reviewed output inventory. The configured
`core-headers.txt` records the selected headers, including ER7's duplicate basenames
when enabled; validation derives both the count and set of headers from that file.
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

BD-05/BD-06: **all invocations of a CMake-built ICG** report system-header errors
as failures and advertise Clang's GNU compatibility version
4.2.1, rather than the compiler used to build ICG. In the locally tested Ubuntu
24.04/GCC 13.3/LLVM 14.0.6/glibc 2.39 tuple, impersonating GCC 13 selected
unsupported `_Float32` declarations and malloc attributes in glibc. This change
uses one build-time frontend policy (`TRICK_ICG_CMAKE_CONFIG`) for configured
include ordering, GNU compatibility macros, and strict diagnostics. Neither
`-o` nor `--output-root` selects frontend semantics. Make-built ICG retains its
historical frontend policy; explicit output still refuses to stamp parse errors.
The old claim that all legacy callers were unchanged was too broad: a caller
using a **CMake-built** ICG receives this native policy with either output layout.
The native ICG also leaves explicitly requested system directories in their
compiler-defined position when already implicit. Ubuntu 24.04/GCC 13/LLVM 14
installs UDUNITS headers in `/usr/include`; moving that directory ahead of the
C++ wrappers breaks `#include_next <stdlib.h>`. Nonstandard dependency prefixes
still take the requested precedence.

`icg.core_output_parity` compares the core metadata C++ and both registration
maps generated using the two output layouts of the same native executable.
`icg.outputs` additionally compares a `__GNUC__`-gated fixture. These prove output
layout independence, not equivalence to a separately Make-built ICG or to the
model compiler. `ICGConfiguration.txt` records the parsing policy explicitly.

**Open frontend compatibility issue:** model headers gated on the real GCC
version can expose a different layout to Clang's 4.2.1 compatibility macros.
The core inventory currently has no version-number-gated model fields, but that
does not qualify user simulations. C1 must report the parser/model compiler
policy and qualify such headers before advertising general simulation support.
An upstream bug report should reproduce GCC 13.3 + LLVM 14.0.6 + glibc 2.39 by
parsing `files_to_ICG.hh` with host-GCC predefines and exposing system errors;
the unsupported `_Float32`/malloc attributes are the original failure. Forcing
4.2.1 is a documented compatibility choice, not a fix for arbitrary GCC-gated
models. The issue is independent of output placement and of the icg2 contract.

BD-01/BD-18: CMake output ownership and native depfiles replace timestamp checks
and recursive Make. Metadata is a dedicated archive pending B5/B6 linkage;
whole-runtime registration is not claimed by this layer.
