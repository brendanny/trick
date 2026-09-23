# Behavior differences and option migration

## A2 implementation status

A2 implements the configuration-only portion of BD-01 (external build trees),
BD-03/04 (native configuration/compiler selection), and BD-14 (CTest bootstrap
checks). It also replaces the obsolete CMake entry point. Runtime code generation,
dependency discovery, installation, and simulation behavior remain unimplemented.
The preview rejects installation explicitly. See [bootstrap.md](bootstrap.md)
and [A2 evidence](a2-validation.json) for tested platform/tool versions; the
proposed end-state entries below do not become verified wholesale.

## A3 implementation status

The utility portion of BD-01, BD-03/04 and BD-14 is now implemented. See
[utility build instructions](utilities.md) and [exact local evidence](a3-validation.json).
The following observations are verified on **Linux x86_64, Ubuntu 24.04.3,
GCC/G++ 13.3.0, GNU ld 2.42, CMake 3.26.0, GNU Make 4.3 and Ninja
1.11.1.git.kitware.jobserver-1**, with GoogleTest 1.14.0. macOS and EL8 remain
unverified. Legacy comparisons here are source-observed, not a paired legacy build.

| IDs | Legacy source behavior | A3 behavior and action |
| --- | --- | --- |
| BD-01 | Archives in `lib_${TRICK_HOST_CPU}`, objects beside component sources. | Archives/objects stay under the selected binary directory's component paths (configuration subdirectory for multi-config). Do not rely on the legacy build-tree paths; consume targets. Installed layout is deferred to C2. |
| BD-03/04 | Common Make flags and manually assembled `-I`/`-l` arguments. | CMake configuration flags and target requirements; private warnings do not propagate. Use native toolchain/cache inputs. |
| BD-14 | Per-directory Make tests, manually selected GoogleTest paths, XML under the checkout. | Explicit opt-in utility tests use `find_package(GTest)`, CTest and build-tree output. Supply `GTest_DIR` or `CMAKE_PREFIX_PATH`; requesting tests without a package fails. |

GSL-off Math retains the legacy runtime message dependency; this is a staged
limitation, not a new self-contained RNG API. No algorithms or public runtime
headers are changed. Other proposed rows below remain unverified.

## A4 implementation status

A4 implements compiler/dependency selection and preflight diagnostics (BD-04),
coherent Python embedding discovery (part of BD-07), and selective dependency
lookup (part of BD-09). Reproduce with the profiles in [dependencies.md](dependencies.md).

| Difference | Legacy source behavior | A4 behavior / action | Verified scope |
| --- | --- | --- | --- |
| BD-04 | GCC version is recorded; tools and library flags are found by shell probes. | GNU C/C++ <8.5 fail, C++17 compilation is checked, native artifact hints select dependencies. | Ubuntu 24.04.3 x86_64, GCC/G++ 13.3.0, CMake 3.26.0; synthetic 8.4/8.5 policy tests only. |
| BD-07 | Interpreter and python-config are separately searched; default can select Python 2. | Default Python 3, explicit `TRICK_PYTHON_MAJOR=2` retained. Request interpreter/embed together and compile/link/run a consistency check. No new Python 3 minor floor. | Linux environment above, Python 3.12.14; Python 2 and other versions pending. |
| BD-09 | Configure discovers dependencies for the framework and optional components broadly. | Default utility profile requires no unused runtime/ICG/GUI packages. Request runtime/ICG preflight explicitly; final feature defaults remain open. | Minimal-selection fixtures passed; full distribution preflight and macOS pending. |
| BD-05 (partial) | LLVM/Clang filenames and flags are assembled manually. | LLVM config >=14 plus sibling Clang config; explicit mismatched paths fail. Non-sibling layouts currently unsupported. | Synthetic config selection fixtures only; actual ICG link/ABI validation is A5. |

The local runtime has a broken unversioned libpython symlink. A valid temporary
symlink to the existing Python 3.12.14 library was supplied via `Python3_LIBRARY`
for the successful local probe; no environment-specific workaround was added to
Trick. Exact local results and remaining gates are in [a4-validation.json](a4-validation.json).

## A5 implementation status

A5 adds native ICG compilation and implements the build-tree portion of BD-05.
On Linux x86_64 / Ubuntu 24.04.3, CMake 3.26.0, Ninja
1.11.1.git.kitware.jobserver-1, GCC/G++ 13.3.0, LLVM/Clang 14.0.6 and UDUNITS
2.2.28, the executable builds, loads its libraries through CMake's build rpath,
and processes a representative header with units annotations and C++ headers.
Exact package revisions and environment details are in [a5-validation.json](a5-validation.json).

| Legacy source behavior | A5 CMake behavior | Scope / action |
| --- | --- | --- |
| ICG is compiled by Make, with llvm-config flags and platform-specific linker/rpath commands. | Config-package targets supply link dependencies and native CMake build rpaths. | Native ICG build; installed rpaths remain C2. macOS execution is a CI gate. |
| Runtime compiler headers come from trick-gte and a shell compiler invocation; Linux Clang resources use a guessed versioned path. | Configured compiler implicit include directories plus the selected Clang's reported resource directory. | CMake-built ICG only; reconfigure after compiler/SDK changes. Per-simulation compiler selection is C1. |
| TRICK_HOME is supplied by the legacy invocation environment. | If unset, build-tree ICG uses its configured source checkout; existing values are preserved. | Build-tree preview only, not an installed SDK promise. |

The extracted local development packages require a library search environment for
their Clang driver during configuration and an explicit UDUNITS XML path. Those
are local provisioning details, not hard-coded in the project. The built ICG
itself passes its smoke test without a library-search environment override.
Generation/output changes remain B1; no claim is made yet for a complete SDK.

Maintain this register with machine-readable environment/test records alongside it. Every difference gets: ID; user-visible effect; legacy source behavior; new behavior; rationale; affected platform/OS/tool versions; implementation PR; reproduction; compatibility action; and status.

Status vocabulary: **proposed**, **implemented/unverified**, **verified**, **known regression**, **retired**. The entries below are **proposed**, including the source-installer prefix and optional feature defaults; A1 does not approve those choices. See the [decision register](README.md#decisions-to-finalize). Their environment IDs refer to [qualification matrix](qualification.md); a result cannot become verified while its exact version fields are unresolved.

| ID | Autoconf/Make behavior observed in source | Proposed CMake behavior and user action | Platform / tooling scope | Owning PR |
| --- | --- | --- | --- | --- |
| **BD-01** | In-source objects, generated wrappers, metadata, and configuration. | Out-of-source only; remove a build directory to discard that configuration. Source-tree artifacts are never a prerequisite. | All profiles, CMake >=3.26; Ninja/Make versions recorded. | A2, B1–B6 |
| **BD-02** | `./configure`, `make`, and separate installation. | End users run `./install-trick`; developers use CMake directly. Prerequisites remain explicit. | Linux/macOS/WSL profiles; CMake >=3.26; launcher Python version recorded. | E1 |
| **BD-03** | Per-Makefile flags and environment conventions; ICG explicitly adds `-g`. | CMake configurations own optimization/debug settings; installer chooses Release. Use a new build dir for compiler/ABI changes. Simulation override variables remain a separate interface. | GCC 8.5+ / supported Clang tuples, CMake >=3.26. | A2, A5, C1, E1 |
| **BD-04** | Compiler/tool paths discovered through shell commands and custom switches. | CMake compiler/toolchain selection and `<Package>_DIR`/prefix hints. Legacy `TRICK_*FLAGS` do not silently configure the framework CMake build. | All profiles; compiler, linker, CMake versions required in records. | A4, C1 |
| **BD-05** | LLVM library filename probing, manual order, macOS extra libraries/rpath edits. | Coherent LLVM/Clang imported targets; explicit minimum/mismatch errors; reproduce any necessary package workaround. | EL8-min LLVM 14.0.6; UBU/EL-next package tuples; MAC-arm/MAC-intel with exact LLVM/CLT/linker revisions. | A5 |
| **BD-06** | `-o` uses flat ICG basenames; several other outputs use source-relative paths. | Collision-safe external output layout and complete dependency/output reporting. Legacy simulation mode remains available. | All profiles, LLVM >=14; generator commit and feature selection recorded. | B1, B4 |
| **BD-07** | Configure searches Python/Python-config separately, including Python 2 possibilities. | CMake defaults to matching Python **3** artifacts and SWIG **4**. Explicit Python 2 and SWIG 3 selections remain allowed with prominent deprecation warnings. | EL8-min Python 3.6.8 lane and newer exact Python tuples; SWIG version recorded. | A4, B6 |
| **BD-08** | Generator failure may fall back to premade parser sources. | Explicit regeneration or release-generated-source mode; no fallback after a genuine generator failure. | All profiles; exact Flex/Bison versions and release-source hashes recorded. | B2, E2 |
| **BD-09** | Optional packages use mixed directory/header autodetection. | Consistent `AUTO`/`ON`/`OFF`, with required-on failures and a visible feature report. `AUTO` can find packages legacy probing missed. | D1–D6 affected OS profiles; record each optional dependency version. | A4, D1–D6 |
| **BD-10** | Linux selects `lib64` using `/etc/redhat-release`, otherwise generally `lib`. | `GNUInstallDirs`; respect `CMAKE_INSTALL_LIBDIR`. Installed SDK readers use recorded layout. Debian `/usr` may use a multiarch directory. | EL8/EL-next, UBU and WSL, macOS; CMake 3.26 vs tested newer versions, prefix and architecture recorded. | C1, C2 |
| **BD-11** | Broad directory copying; `/usr/local` default and a special privilege check. | Explicit `install()` entries and `DESTDIR`. Direct CMake retains its native default prefix; `./install-trick` chooses a dedicated user prefix. | All native/WSL profiles; install method, prefix, CMake version recorded. | C2, E1 |
| **BD-12** | Rpaths assembled as flags, plus macOS `install_name_tool`. | Per-target build/install runtime paths and relative own-resource lookup; external dependency locations remain explicit. | Linux ELF/glibc and macOS Mach-O; exact linker, Python, LLVM, CMake tuples. | A5, C2 |
| **BD-13** | Java output/resources live under checkout paths; special offline copy behavior. | Maven owns Java compilation, but outputs go to the binary tree and installed data locations; offline inputs are validated. | Linux/macOS; Java/Maven/plugin versions and JAR metadata recorded. | D3, E2 |
| **BD-14** | `make test` runs bespoke unit/simulation drivers. | CTest coordinates focused/full tests; `ctest` does not implicitly build in the baseline workflow. Installer uses a small acceptance check. | All profiles; CMake/CTest 3.26+, test-driver versions recorded. | A2 onward, F1 |
| **BD-15** | `--enable-32bit` and `-m32` are mixed into a largely host-configured build. | Separate host ICG and target-runtime toolchain; explicit target dependency selection. | Oracle/RHEL-family 8.10 x86_64→i686; GCC 8.5.0, host LLVM14.0.6, exact 32-bit Python/dependency tuple. | E3 |
| **BD-16** | Configure-time results and platform Makefiles are queried again by installed simulation tools. | CMake-generated SDK values; incompatible compiler/ABI substitutions diagnosed; normal simulation flags/overrides preserved. | All profiles; producer and simulation-consumer tuples both recorded. | C1, C2 |
| **BD-17** | Different clean/spotless/uninstall conventions and directory-wide cleanup. | CMake clean/reconfigure semantics; reinstall/staging uses explicit manifests. No automatic broad uninstall of shared prefix directories. Document package-manager or manifest-based removal. | All profiles; generator/CMake version and prefix ownership recorded. | C2, E1, E2 |
| **BD-18** | Global includes/flags and fixed archive/link order. | Target-scoped usage requirements, required static-link dependencies and narrow registration/export settings. Flag spelling/order may differ; capability cannot disappear. | Linux GNU/LLVM linkers and macOS ld; exact versions and link mode required. | A3, B5, C3 |
| **BD-19** | A checked-out/configured Trick is routinely treated as `TRICK_HOME`. | Supported build-tree overlay or installed prefix; source root alone is not a runnable CMake SDK. | All profiles; configuration/ABI and generator recorded. | C1, C2 |
| **BD-20** | Current offline flag covers a specific legacy bundle convention. | Explicit source/generated-source/Maven-or-JAR inputs; CMake configure is network-free; offline builds verified with network denied. | All profiles; artifact hashes and Maven/CMake versions recorded. | E2 |

A working legacy capability that disappears without an accepted disposition is a **known regression**, even if CMake could technically be configured that way. Conversely, a better install layout or generator choice does not require emulating Autotools when the SDK and user guidance handle it correctly.

### Configure-option migration map

| Existing interface | Replacement / disposition |
| --- | --- |
| `--prefix=...` | `CMAKE_INSTALL_PREFIX` or installer `--prefix`. |
| `CC`, `CXX`, `CFLAGS`, `CXXFLAGS`, `LDFLAGS` | CMake's native initial environment/cache behavior; toolchain/preset for reproducibility. No project-level forced overrides. |
| `--with-llvm=...` | `LLVM_DIR`, `Clang_DIR`, `CMAKE_PREFIX_PATH`; installer `--llvm` resolves the matching config-package directories. |
| `--with-python`, `PYTHON_VERSION` | `Python3_EXECUTABLE`/`Python3_ROOT_DIR`; installer `--python`. |
| `--with-swig` | `SWIG_EXECUTABLE`. |
| `--with-udunits` | `UDUNITS2_ROOT` or supported config-package/prefix hint. |
| `--with-hdf5`, `--with-gsl`, `--with-civetweb` | Corresponding `TRICK_WITH_*` selection plus package root/config hints. |
| `--with-gtest` | `BUILD_TESTING` plus `GTest_DIR`/`CMAKE_PREFIX_PATH`; test dependency discovery only when requested. |
| `--enable/disable-java` | `TRICK_BUILD_JAVA`; honor selected Java/Maven executables. |
| `--enable/disable-er7utils` | `TRICK_USE_ER7_UTILS`. |
| `--enable-offline` | `TRICK_OFFLINE` plus explicitly prepared artifact locations. |
| `--enable-32bit` | Documented multilib toolchain and host-ICG selection; installer orchestration in E3. |
| `--with-prepend-path[=DIR]` / `--without-prepend-path` | Native package hints or a user preset; do not mutate global PATH to influence unrelated probes. |
| `make no_dp`, `make dp`, `make java` | Configure component selection; build the named native target when developing that component. |
| `make premade`, `make spotless`, `make uninstall` | Explicit release preparation; fresh build directory/`cmake --fresh` as appropriate; documented manifest/package removal. No false claim of a built-in CMake uninstall command. |

## B1 implementation status

BD-06 now has an opt-in [ICG output contract](icg-outputs.md): canonical-path
metadata names, complete dependency reporting, confined maps/SIE/temporary
files, and success publication after diagnostics and output checks. Legacy
callers retain their existing layout; obsolete `EXTERNAL_BUILD` branches are
replaced by the runtime option.

## B-stack implementation status

| IDs | Native behavior | Evidence / qualification |
| --- | --- | --- |
| BD-01, BD-06 | Binary-tree ICG outputs, declared metadata inventory, depfile, manifest and stamp; parser and SWIG output ownership. | Ubuntu 24.04 x86_64, CMake 3.26.0, Ninja 1.11.1, GCC 13.3, LLVM 14.0.6, Flex 2.6.4, Bison 3.8.2; exact evidence in `b-stack-validation.json`. |
| BD-05 | Explicit-output ICG uses Clang's GNU compatibility version and surfaces system-header errors. | GCC 13.3/LLVM 14.0.6/glibc 2.39 required this to parse core headers; legacy invocation mode is unchanged. |
| BD-07 | Native runtime defaults to Python 3/SWIG 4; explicitly selected Python 2/SWIG 3 are deprecated, with warnings. | Local Python 3.12.14/SWIG 4.2.0; Rocky 8 CI records Python 2.7/Python 3.6 with SWIG 3.0.12 and GCC 8.5; consult completed run artifacts. |
| BD-08 | Parser generation fails on generator errors instead of falling back to premade source. | Native Flex/Bison rules with scanner/header ordering; grammar edit validation. |
| BD-18 | CheckPointAgent belongs to the memory-manager archive; integrators, metadata, main and SWIG wrappers have separate owners and target links. Narrow retention or whole-metadata retention protects runtime lookup. | Linux ELF GNU ld 2.42 locally. macOS Mach-O and generator combinations are covered by the runtime CI matrix; use run results rather than assuming qualification. |

The B stack does not supply an installed SDK, external ER7/CheckpointHelper
variants, or distribution features scheduled in later layers. See each layer's
usage document for its exact boundary. GCC 8.5/RHEL 8, older Python/SWIG tuples,
and native platform qualification beyond the CI matrix remain explicit work.
