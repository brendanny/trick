# Validation record

Scaffold validation on Linux x86-64, 2026-10-24:

| Configuration | Tools | Result |
| --- | --- | --- |
| Native | GCC 16.1.0 and matching libstdc++, CMake 4.1.3, Release | Reflection probe, full build, and 15 CTest cases passed |
| Bootstrap | GCC 13.3.0, CMake 4.1.3, Release | Runtime build and 4 CTest cases passed |
| Installed-package consumers | GCC 16.1.0, `find_package(trick2)` from a separate project | C++20 runtime consumer and C++26 reflection consumer compiled, linked, and ran |
| Unsupported native compiler | GCC 13.3.0, default native configuration | Rejected at configuration with an explicit compiler/bootstrap diagnostic |
| Registry sanitizer check | GCC 13, AddressSanitizer and UndefinedBehaviorSanitizer | Passed with leak detection disabled; this environment cannot perform LeakSanitizer's process inspection |

Both builds enable `-Wall -Wextra -Wpedantic -Werror`. Test checks remain active
under `NDEBUG`. Native reflection uses `-std=c++26 -freflection`. Compile commands
confirm that the mixed example's model implementation uses `-std=c++17`, while
its assembly translation unit uses C++26 in the native build.

Both native oscillator examples produced 100 observations over ten simulated
seconds. The maximum combined position/velocity error against the analytic solution
was approximately `8.53e-14`, below the acceptance threshold of `1e-9`.

The native suite includes nine intentional compile failures with diagnostic checks.
An unrelated compiler failure does not count as a passing rejection test. The
remaining tests exercise registry lifetime and permissions, deterministic scheduling
and failure semantics, coupled RK4 stages/convergence, reflected field access, and
both complete examples. The bootstrap suite omits all reflection cases explicitly.

The GitHub workflow defines separate GCC 16 native and GCC 13 bootstrap jobs.
This record reports local validation; it does not claim a completed hosted CI run.
No compatibility with other compiler families, platforms, or the existing Trick
runtime has been established by these tests.

For the `brendanny/trick` branch layout, both test suites were rerun from fresh
build directories under `trick2/`. The new C++ sources were formatted with the
repository's `.clang-format`; a clang-format 23.1.3 dry run passed. The experiment
has its own root-level `.github/workflows/trick2.yml` workflow. Existing Trick
sources and build files were not changed, and the legacy Trick test suite was
not rerun for this standalone addition.
