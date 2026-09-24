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

BD-05/BD-06: CMake generation commands and the SDK explicitly pass
`--icg-gnu-version=4.2.1`, `--icg-strict-errors`, and repeated
`--icg-system-dir=<directory>` options. Both Make-built and CMake-built ICG
accept these runtime controls. Without them, both retain the historical
build-compiler GNU version and runtime include discovery. The build system
only provides executable/source identity for SDK discovery, not parsing policy.
In Ubuntu 24.04/GCC 13.3/LLVM 14.0.6/glibc 2.39, impersonating GCC 13 selects
unsupported `_Float32` declarations and malloc attributes in glibc; the explicit
4.2.1 selection remains a compatibility workaround, not model-compiler parity.

Explicit compiler directories replace runtime discovery and preserve their
order; an `-isystem` duplicate does not move them ahead of C++ wrappers.
Missing directories fail before parsing. Neither output layout selects GNU
macros or include ordering. The `--output-root` contract always reports parse
errors and refuses to write a success stamp; strict mode also applies that
policy to legacy layouts. System diagnostic notes are preserved.

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
The upstream report reproduces GCC 13.3 + LLVM 14.0.6 + glibc 2.39 with a reduced `<cstdlib>` header and host-GCC predefines;
the unsupported `_Float32`/malloc attributes are the original failure. Forcing
4.2.1 is a documented compatibility choice, not a fix for arbitrary GCC-gated
models. The issue is independent of output placement and of the icg2 contract.

The [upstream report draft](icg-frontend-issue.md) contains a separately verified
Clang-driver reproduction and the model-layout counterexample.
Resolve the policy issue before C1 advertises general simulation support.

BD-01/BD-18: CMake output ownership and native depfiles replace timestamp checks
and recursive Make. Metadata is a dedicated archive pending B5/B6 linkage;
whole-runtime registration is not claimed by this layer.
