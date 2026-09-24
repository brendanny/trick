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
compatibility. Configure probes operator availability using the selected compiler and flags;
`-dM` alone does not list every builtin operator. The profile records this
availability explicitly. `defined`, `ifdef` and `ifndef` checks are accepted
only when ICG and the model compiler agree. Calls to `__has_builtin`,
`__has_attribute`, `__has_cpp_attribute` and `__has_feature` are rejected even when both compilers have
the operator: presence does not establish equal answers for its arguments.
`__has_include` and `__has_include_next` retain their
exception when present in both frontends. Their query results can differ and
are not an ABI equivalence guarantee.
Third-party headers can use `-isystem` or `TRICK_ICG_EXCLUDE` to opt out of
metadata and guard checks; compiler-dependent layout exposed by those headers
is then the consumer's responsibility. System
and SDK headers retain the separately tested native policy. This restriction
is part of the pilot SDK, not a resolution of the upstream frontend problem.

The upstream report remains in [icg-frontend-issue.md](icg-frontend-issue.md);
general support for compiler-dependent model declarations remains gated on upstream resolution.
The guarded pilot SDK supports ordinary, compiler-independent model headers.

`sdk.simulation` copies the example, builds it using `trick-CP`, runs a Python
input file, sets and reads model memory, and verifies a marker. It also compares
both configuration readers. `sdk.compiler_guard` checks ordinary models and
rejects direct, indirect, defined and missing compiler macro fixtures. These
run in the runtime CI lanes (Linux/macOS, ER7 on/off and EL8's four Python/SWIG
combinations). No GUI/native optional tools are promised until stack D.

## C2: install and relocate

```sh
cmake --install build --config Release --prefix "$HOME/trick-sdk"
export PATH="$HOME/trick-sdk/bin:$PATH"
# In a copied simulation directory:
trick-CP
```

The core SDK installs native archives, ICG, simulation scripts, headers, Perl and
Python helpers, Make templates, core class resources and the SDK example. It
uses `GNUInstallDirs` for the library directory (`lib`, `lib64`, or a relative
multiarch path); the established `bin`, `include`, `libexec` and `share` resource
layout is fixed for the existing tools. `DESTDIR` stages files without baking
the staging path into configuration. `--prefix` may select a new installation
prefix. No SDK install is offered from a utility-only configuration.

Install into a fresh prefix: CMake's manifest records installed files but does
not remove obsolete files from an older configuration. There is no broad
uninstall command. Use a dedicated prefix or package manager. The source and
build directories are not runtime dependencies. Installed ICG locates its own
SDK when `TRICK_HOME` is unset; a raw developer ICG still has an explicit source
fallback. The SDK can move on the same compatible machine. External compiler,
LLVM runtime/resource headers, UDUNITS, Python, SWIG, Perl and Make installations
remain dependencies; moving Trick does not relocate those packages or promise
cross-machine ABI compatibility. ICG uses native CMake install rpaths for its
external shared libraries.

The standalone `cmake/tests/verify_sdk_install.py` runs after build-tree tests.
It installs both library layouts to nondefault prefixes and through DESTDIR,
moves the staged prefixes, hides the source and build trees with restoration on ordinary exceptions and
SIGTERM (not SIGKILL), then builds/runs copied simulations and trickifies a header. It
checks an invalid install destination and, when running unprivileged, a genuinely
unwritable prefix. Root/container runs explicitly cannot qualify filesystem
permission denial. Run this script in a disposable checkout/build pair, not
while another process builds or uses them.

To run only the installed smoke test:

```sh
cmake -DSDK="$HOME/trick-sdk" \
  -DFIXTURE="$HOME/trick-sdk/share/trick/examples/SIM_sdk" \
  -DTEST_ROOT=/tmp/trick-sdk-smoke \
  -P "$HOME/trick-sdk/share/trick/tests/SDK.cmake"
```

SDK staging copies changed content directly into the persistent SDK and removes
obsolete files using its ownership manifest. Unchanged files and archive links
retain their mtimes, so rebuilding Trick does not invalidate simulation Python
proxies. `verify_sdk_staging.py` builds the SDK twice and checks the complete
inventory's mtimes, then verifies stale-file removal. ER7 headers have one SDK
location, `trick_source/er7_utils`; exported targets supply `trick_source`.

Developer ICG discovery compares the executable's real path with the configured
target path, including custom runtime output directories and multi-config builds.
Other copies require an adjacent SDK marker. The ordinary native CI lanes use
default compiler flags; a separate Linux lane tests a conflicting C++ standard
flag and a developer executable under `build/bin`.

Source resource symlinks are materialized as regular SDK files, since their
relative targets can lie outside the copied trees. Archive links remain explicit
build-tree links. Stale-file cleanup prunes empty ancestor directories but keeps
nonempty directories and user outputs. The inventory is written as literal text,
so filenames containing `@NAME@` are not interpreted as template variables.
