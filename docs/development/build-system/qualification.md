# Qualification and environment records

## Environment identity

A claim of a verified behavior difference must name an exact environment record. “Linux,” “macOS,” “latest LLVM,” and a mutable container tag are insufficient.

Each record must contain:

- Trick commit and build route; OS release and package/container image digest; architecture and pointer width; WSL version when applicable.
- CMake full version and generator; Ninja/Make version; compiler executable, full version, and C++ runtime; linker identity/version and selected linker flags.
- LLVM/Clang package version, build/revision, source of packages, linkage mode, and resource directory.
- Python interpreter/full version, development library, ABI and architecture; SWIG, Flex, Bison, Perl, Java/Maven, and enabled dependency versions.
- On macOS: macOS build, Xcode/CLT version, AppleClang full build string, SDK, deployment target, Homebrew formula revision, and target architecture.
- Relevant cache settings, prefix/libdir, environment overrides, test command, observed result, and log/artifact reference. Do not dump unrelated environment variables or credentials.

## Proposed matrix

These are **test targets**, not claims that these combinations were built during planning. The PR performing each test must fill package revisions and exact patch versions before marking any result verified. A1 only establishes the format; F1 consolidates release evidence. Deliberately pinned minimum toolchains may require archived packages or a separately provisioned image; current distro packages need not equal the minimum.

| ID | Platform / OS | Required version coverage | Purpose |
| --- | --- | --- | --- |
| **EL8-min** | RHEL/Rocky/Alma 8.10, Linux x86_64 | GCC **8.5.0**, LLVM **14.0.6**, CMake **3.26.0** and packaged **3.26.x**; Python 2.7 and Python 3.6.8/SWIG 3.0.12 deprecated compatibility lanes; pin actual package revisions and build tools. | Joint minimums; embedding/static linkage; oldest launcher Python; `lib64`. |
| **EL8-32** | Oracle Linux 8.10, x86_64 host → i686 target | GCC 8.5.0, host LLVM 14.0.6, CMake 3.26.x; target 32-bit Python and every target development library pinned separately. | Real host/target split and 32-bit simulation coverage. |
| **EL-next** | Supported RHEL-family 9 and 10 releases | Distribution toolchains, with complete version locks; include a recent CMake 4.x lane. | Newer dependency layouts, compiler/policy compatibility. |
| **UBU** | Ubuntu 24.04 and 26.04, Linux x86_64 | Distribution GCC/LLVM/Python, recorded exactly; separate LLVM 14 minimum-library lane if necessary; CMake 3.26 plus distro/newer versions. | Debian multiarch at `/usr`; Ninja/Make; contemporary Python. |
| **MAC-arm** | macOS 26 CI plus the oldest macOS release the project continues to support, arm64 | AppleClang/CLT/SDK recorded exactly; Homebrew LLVM package/revision; CMake 3.26 and supported newer CMake. Include upstream LLVM 14 only on a provisioned compatible host. | Homebrew `/opt/homebrew`; Mach-O linkage, SDK/resource search, Python embedding. |
| **MAC-intel** | Supported macOS release on x86_64 | Exact OS/CLT/AppleClang/SDK and LLVM package tuple; CMake 3.26/newer lanes. DEC-04 must name a maintained host before qualification if no hosted runner exists. | Intel Homebrew paths and x86_64 installation. |
| **WSL** | Windows host + WSL2 Ubuntu 24.04 | Record Windows/WSL build and the complete UBU toolchain tuple. | End-user command and installed simulation smoke on the documented Windows route. |

Minimum supported macOS/Java/Python patch levels beyond the explicitly requested floors are release-policy inputs tracked by DEC-04, not invented by the CMake migration. An unavailable required runner needs maintained equivalent evidence before the platform is called qualified.

## Required release checks

1. **Build graph:** clean parallel build, no-op build, header/grammar/SWIG edit, rebuilt generator, deleted byproduct, optional feature change, and clean/rebuild. No generated file escapes the build tree.
2. **Build variants:** Ninja and Unix Makefiles; Debug and Release; Ninja Multi-Config with configuration-isolated generated outputs. Test switching configurations without mixing metadata, wrappers, or archives. Installation uses one configuration per prefix.
3. **Core simulation correctness:** build/run a small Cannon or equivalent simulation, initialize Python bindings, set/read variables, save/reload a checkpoint, and exercise a variable-server exchange. Keep full existing unit/simulation suites through CTest adapters.
4. **Installed SDK:** fresh prefix; source/build hidden; `DESTDIR`; configured `lib`/`lib64`/Debian multiarch; trickification; CMake consumer; resource resolution; prefix move on the same ABI-compatible machine. Exercise source/build/prefix paths containing spaces; if existing simulation scripts prevent full support, record the exact limitation and diagnose it before installation rather than claiming the wrapper's quoting alone fixes it.
5. **Link/load behavior:** static archive dependencies, registration, JIT/plugin symbol resolution, Python embedding, LLVM resource lookup, and nondefault external-library paths on ELF and Mach-O.
6. **Feature selection:** ER7 on/off; GSL/HDF5/CivetWeb absent/off/on; GUI on/headless; explicit missing requirements fail. Source installer and CI report resolved choices.
7. **Distribution:** source archive without Git, offline preparation with network denied, one-command installation, rerun/failure behavior, and no reliance on stale premade/generated files.
8. **Transition:** separate legacy/CMake builds of the same source revision and selected feature set. Compare capabilities, normalized outputs, installed contracts, and meaningful simulation results—not byte-for-byte archives, compiler command lines, timestamps, or incidental paths.

Use targeted regression checks per layer and full qualification at milestones. Investigate numerical differences before accepting them; a different optimization default is not automatic permission for a simulation-result regression. Set tolerances based on the simulation's existing correctness criteria.


## Recording evidence

Copy [environment-template.json](environment-template.json) for each tested configuration. Replace null fields with observed values; mark unavailable or inapplicable tools explicitly with a reason. The template is not a test result. Store command/log references and the exit status for each configure, build, install, and simulation run. Record failed and skipped runs, not just successful ones. Do not capture unrelated environment variables or credentials.

A1 validation consists of source inventory and document consistency checks. No native Linux/macOS Trick build, installation, or simulation result is claimed by this change. Platform execution belongs to the affected implementation layers and final qualification.

For each tool field, record an object with `executable_or_path`, `full_version`, `package_revision`, `provider`, and `architecture` where applicable. Each run records `phase`, the command as an argument array, `working_directory`, `exit_code`, `result`, and a `log_reference`. A skipped run includes a reason and has no invented exit code. Use separate records for different producer/consumer or host/target environments.
