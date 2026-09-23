# A4: dependency preflight

A4 checks dependency selections for the later native runtime and ICG targets.
A5 now optionally builds [native ICG](icg.md); installation remains unavailable.
There are no dependency downloads, automatic package installations, or PATH edits
in CMake. The profile is a preflight selection, not a build-feature promise.

| `TRICK_DEPENDENCY_PROFILE` | Checks |
| --- | --- |
| `UTILITIES` (default) | Compiler requirements; Threads when utilities are enabled; GoogleTest only for explicitly enabled utility tests. |
| `RUNTIME` | Bison, Flex, SWIG >=3 with Python support, Perl >=5.14 with Text::Balanced and Digest::MD5, matching Python interpreter/embedding development files, UDUNITS-2. |
| `ICG` | LLVM >=14 and the Clang development config package from the same installation. |
| `ALL` | Both RUNTIME and ICG checks. |

Values are case-sensitive and invalid values fail. GUI, Java, HDF5, GSL and
CivetWeb discovery stays with the owning D-layer implementation; this PR does not
introduce options that imply those features already work. Final release feature
defaults (DEC-03) remain open. Native preflight is supported; cross-compiling a
runtime/ICG profile is rejected until E3 separates host and target requirements.

```sh
cmake -S . -B build/cmake/dependencies -G Ninja \
  -DTRICK_DEPENDENCY_PROFILE=ALL \
  -DLLVM_DIR=/path/to/llvm/lib/cmake/llvm \
  -DPython3_EXECUTABLE=/path/to/python3
cmake --build build/cmake/dependencies --parallel
ctest --test-dir build/cmake/dependencies --output-on-failure
```

`TrickDependencies.txt` records the selected tools, versions, headers and libraries
in the build tree. CMake's configuration log contains the compile/link/run probes.
A dependency report is not proof of a complete Trick build or a qualification of
the selected SDK. Unselected profiles do not have their dependencies discovered.

## Selection and validation

C and C++ GNU compilers are checked independently against GCC 8.5. The selected
C++ compiler and standard library must compile C++17. AppleClang version numbers
are not compared to the LLVM library floor. Compiler selection uses normal CMake
variables/toolchains; change compilers in a fresh build directory.

Python discovery requests `Interpreter` and `Development.Embed` together. A native
probe checks interpreter/header major-minor agreement, links the selected library,
checks its runtime version, initializes the interpreter, and finalizes it. A
broken runtime library search path is a configuration failure, with the probe log
available for diagnosis. No separate `python-config` lookup occurs. Patch releases
within the same Python major/minor are allowed.

`TRICK_PYTHON_MAJOR` selects `3` (default) or `2` explicitly. Corresponding hints
are `Python3_EXECUTABLE`, `Python3_ROOT_DIR`, `Python3_INCLUDE_DIR` and
`Python3_LIBRARY`, or the `Python2_*` equivalents. CMake 3.26's supported Python
versions apply; no Python 3.11 floor or Python-2 retirement is imposed here.
Python 2 is a deprecated compatibility selection with a prominent warning;
Python 2 and SWIG 3 support will be removed in Trick 27.
`TRICK_SWIG_MAJOR` selects `4` by default, or deprecated `3` explicitly.
Python 2 is selectable with either SWIG major. See [runtime policy and CI](python-input.md). The imported `Trick::Python` alias
wraps the selected built-in embedding target.

Use `BISON_EXECUTABLE`, `FLEX_EXECUTABLE`, `SWIG_EXECUTABLE` and `PERL_EXECUTABLE`
for host tools. Built-in Find modules provide their diagnostics. Missing required
Perl modules produce an explicit error naming the interpreter and modules.

CMake 3.26 has no UDUNITS-2 finder, so a small custom module provides
`UDUNITS2::UDUNITS2` and checks an actual header/library link. Set `UDUNITS2_ROOT`
or the exact `UDUNITS2_INCLUDE_DIR` and `UDUNITS2_LIBRARY` artifacts. An explicit
root is searched exclusively (including lib64 and Linux multiarch paths); exact
artifact overrides take precedence. Use a fresh cache when changing roots so
previously cached artifact selections do not remain. Static-only installations
requiring extra dependency libraries are not yet supported by this finder; they
fail the link probe rather than producing an unusable target.

LLVM uses its config package. The Clang config must be its sibling in the same
installation (after resolving LLVM directory symlinks); an unrelated explicit
`Clang_DIR` fails. A malformed explicit `LLVM_DIR` cannot silently select another
installation. `CMAKE_PREFIX_PATH` can select LLVM when no explicit directory is
provided. Non-sibling custom package layouts are currently rejected; package
layout exceptions need validation in A5. A4 checks package metadata, required
target presence and the Clang header major version; A5 validates ABI and ICG linkage.

## Evidence

CTest adds selection and failure-path fixtures for GCC 8.4/8.5 policy boundaries,
minimal discovery, invalid profiles, LLVM minimum/selection/mismatch/missing
packages, UDUNITS root selection and link failures using small compiled library fixtures,
and Python major selection. Compiler-version and LLVM
fixtures use synthetic metadata: they do not qualify a real GCC 8.5 or LLVM 14
installation. Runtime profiles also register real Python embed and mismatched
library tests. Existing bootstrap and utility suites remain enabled as before.

The Ubuntu full-profile CI provisions distribution dependencies and records exact
package versions. Existing Linux/macOS bootstrap and utility jobs also run the
portable dependency fixtures. Local evidence and unexecuted qualification gates
are recorded in [a4-validation.json](a4-validation.json).

If only SWIG 3 is installed, the default configure fails with guidance to install
SWIG 4 or explicitly select `-DTRICK_SWIG_MAJOR=3` until Trick 27.
