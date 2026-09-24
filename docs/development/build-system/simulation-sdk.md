# C1: simulation SDK configuration

Configure with `-DTRICK_BUILD_SDK=ON`, then build. The SDK enables its complete
native runtime dependency closure. Use `<build>/sdk/<config>/bin/trick-CP` in a
simulation directory (`<config>` is empty for an unset single-config build type).
Do not point `TRICK_HOME` at the source checkout. The overlay copies headers,
resources and tools; rebuild it after source changes. Archive links deliberately
point into the build tree. Each multi-config SDK has its own library links.

The generated `config_user.mk`, `cmake-sdk.mk` and `sdk.env` describe the selected
compiler, Python, SWIG, UDUNITS, ER7 and library directory. The existing
`trick-config` and `trick-gte` read these views. Make still builds simulations;
CMake never invokes the framework Makefile. Scripts are copies so their relative
resource lookup finds the SDK, including when `TRICK_HOME` is unset.

Simulation `TRICK_CC`/`TRICK_CXX` substitutions and 32-bit requests fail with a
specific message. Configure another SDK to change the compiler/ABI. Standard
simulation flags and `S_overrides.mk` remain available; changing ABI, language
standard or predefined compiler macros through them is not supported. CMake's
selected C++ flags are recorded; configuration optimization/debug flags apply
to framework archives, not automatically to model compilation. Paths containing
whitespace, `#` or `$` are rejected because legacy simulation Makefiles cannot
represent them reliably.

## Frontend policy and its boundary

ICG still parses system headers in its native Clang dialect (GNU compatibility
4.2.1). The SDK always passes `--model-predefines` with the selected C++ compiler's
C++17 predefined macros. ICG rejects differing compiler predefined macros used
in user headers, including direct and indirect expansions, `defined`/`ifdef`,
and undefined compiler identifiers in `if`/`elif`. It fails conservatively,
even where a differing value would happen to select the same branch. It does
not change the parser dialect to impersonate GCC, nor prove arbitrary ABI
compatibility. Compiler feature probes that differ are rejected too. System
and SDK headers retain the separately tested native policy. This restriction
is part of the pilot SDK, not a resolution of the upstream frontend problem.

The upstream report remains in [icg-frontend-issue.md](icg-frontend-issue.md);
issue creation was denied by GitHub integration permissions. General support
for compiler-dependent model declarations remains gated on upstream resolution.
The guarded pilot SDK supports ordinary, compiler-independent model headers.

`sdk.simulation` copies the example, builds it using `trick-CP`, runs a Python
input file, sets and reads model memory, and verifies a marker. It also compares
both configuration readers. `sdk.compiler_guard` checks ordinary models and
rejects direct, indirect, defined and missing compiler macro fixtures. These
run in the runtime CI lanes (Linux/macOS, ER7 on/off and EL8's four Python/SWIG
combinations). No GUI/native optional tools are promised until stack D.
