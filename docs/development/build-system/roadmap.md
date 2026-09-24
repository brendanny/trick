# Implementation roadmap

Start with **27 planned PRs in seven short stacks**. This is an initial decomposition: split or combine layers when actual dependencies justify it, retaining focused reviews and independently valid intermediate states. These are planning identifiers, not existing GitHub PR numbers. Each row is one reviewable unit with its own tests and documentation. A layer may depend on lower layers; “self-contained” means that the layer works with its declared dependencies and has no forward dependency on a later repair PR.

**Current delivery:** A1–B6 are implemented as separate commits on the single branch of fork PR #1, as requested. The planning identifiers below remain the unit of review. Stack C is next.

Every implementation PR must include: purpose and non-goals; exact predecessor; owned files/targets; a runnable acceptance command; behavior-difference IDs; and evidence for affected platforms. Introduce relevant tests in the same PR as the behavior. The later CI stack broadens coverage; it is not where tests begin.

Before the complete runtime exists, CMake is explicitly a developer preview with a supported subset, not a source-install alternative. Installing a partial build must not claim to provide the full Trick SDK. Keep Autotools buildable from separate clean checkouts through Trick 28.

### Stack A — foundation and the host generator

Base: nasa/trick PR #2190 at `62d6091db51c25e73874f62f670fdcb3772b6220`; then the merged result on `master` once that PR lands. The implementation has now been rebased onto upstream master `8b25adf1`, which includes merged PR 2190; A1–B6 are consolidated in fork PR #1 above prerequisite PR #5. The original per-layer branch names below are planning labels, not active PR heads.

| PR / branch suffix | Scope and useful result | Acceptance before merge |
| --- | --- | --- |
| **A1 — `cmake/01-contract`** | Add the build contract, checked component/artifact inventory, option disposition map, environment-report format, and difference register. Identify supported internal hooks including `Makefile_jsc_dirs`, hardware-clock libraries, BFD/Avahi, and external ER7 variants; classify each rather than silently losing it. | Validate inventory evidence paths, option coverage, and document links. Record baseline evidence as source inspection; native build/install/simulation results remain unverified until collected in the relevant implementation PR. No Linux or macOS build is required to merge this documentation-only layer. |
| **A2 — `cmake/02-bootstrap`** | Delete obsolete framework CMake scripts/modules/templates and introduce the new 3.26 root, source/binary-tree rules, policy baseline, presets, CTest plumbing, and version parsing from the existing authoritative version file. Leave unrelated example CMake projects intact. | Configure with 3.26.0 on Linux/macOS, reject <3.26 and in-source builds, preserve an unchanged source tree, and keep legacy build checks green. The preview is explicitly configuration-only. |
| **A3 — `cmake/03-utilities`** | Add explicit native utility/math/unit/communication targets in their current archive boundaries, with selected existing focused tests. Scope library-specific requirements correctly. | Build and link a real leaf-library test with Ninja and Unix Makefiles; a consumer inherits required includes but not Trick's private warnings. No recursive framework Make. |
| **A4 — `cmake/04-dependencies`** | Add coherent required-dependency discovery, custom imported targets only where needed, validated option semantics, and tool/version diagnostics. Separate host tools, runtime dependencies, and optional components. | Missing/mismatched dependencies give actionable failures; explicit paths win; a minimal configuration does not require unused GUI/test packages. Probe GCC 8.5 and Python interpreter/embed consistency. |
| **A5 — `cmake/05-icg`** | Build existing ICG as a native executable against LLVM/Clang config packages >=14. Isolate RTTI/definitions/link behavior and resource lookup. | ICG builds and processes a representative header with LLVM 14; a macOS job tests its dynamic-library/resource lookup. Selection never mixes unrelated LLVM/Clang installations. |

### Stack B — generated code and a complete runtime

Base: merged A, or the tip of A while review proceeds.

| PR / branch suffix | Scope and useful result | Acceptance before merge |
| --- | --- | --- |
| **B1 — `cmake/06-icg-outputs`** | Add the explicit, collision-safe ICG output-root/depfile/manifest contract. Replace old CMake-only output branches with runtime options for the new mode; retain legacy behavior for legacy callers. | ER7 duplicate basenames remain distinct; maps/SIE/temp files stay under the requested output root; transitive dependencies are reported; failure publishes no successful stamp. |
| **B2 — `cmake/07-parsers-mm`** | Add native Flex/Bison generation for memory-manager/checkpoint parsers and the memory-manager target. Checkpoint parser objects can remain an internal target until Core uses them. | Parser headers are available before scanner compilation; generated code builds from a read-only source tree; modifying a grammar regenerates only affected outputs. Existing allocation/reference/checkpoint parser tests pass. |
| **B3 — `cmake/08-integrators`** | Build ER7 integration targets with explicit source/header inventories. Define selection of ER7 versus existing Trick algorithms and any reviewed CheckpointHelper variant. | A focused integration test passes with ER7 on and off; headers and feature definitions agree. No duplicate source/object ownership. |
| **B4 — `cmake/09-core-codegen`** | Connect ICG core generation to CMake using explicit outputs, per-feature inventories, depfiles, and success stamps. Generated metadata objects have one owner. | Parallel clean build, transitive header edit, deleted generated file, rebuilt ICG, and feature toggle all behave correctly. A no-op build does not rerun ICG. The manifest matches the declared graph. |
| **B5 — `cmake/10-runtime`** | Add core service targets, main/runtime objects, archive assembly, and required registration/link behavior; consume B2–B4. Avoid runtime API redesign. | A focused service executable and closed-subsystem tests link against the new archives without the not-yet-added Python input processor. Registration survives normal linker elimination. Output archives contain expected symbols and no duplicate objects; full simulation linkage follows in B6/C1. |
| **B6 — `cmake/11-python-input`** | Build input-processor code and SWIG wrappers into the embedded-Python archive; stage generated `.py` modules in the build tree. | An embedded-Python executable initializes wrappers, reads/writes a Trick variable, and exercises a representative pointer/container case. Editing a transitive SWIG input rebuilds the right outputs. |

### Stack C — a usable installed simulation SDK

Base: merged B.

| PR / branch suffix | Scope and useful result | Acceptance before merge |
| --- | --- | --- |
| **C1 — `cmake/12-simulation-config`** | Generate the SDK configuration/compatibility views and build-tree overlay. Update the configuration readers so a CMake build supplies compiler, dependencies, features, and paths to existing simulation tools. | `trick-config`/`trick-gte` agree with the resolved build; a build-tree `trick-CP` invocation builds/runs a minimal simulation with Python. Source paths are explicit development paths, not accidental fallback. |
| **C2 — `cmake/13-install-sdk`** | Add complete core SDK install rules: archives, binaries, headers, Python/Perl helpers, Make templates, resources, and examples. Correct prefix/resource/rpath behavior and provide the installed smoke test. | Install to a fresh nondefault prefix, hide the source/build trees, then build/run a copied simulation. Test `DESTDIR`, an unwritable prefix, `lib`/`lib64`, trickification, and a prefix move on the same compatible machine. |
| **C3 — `cmake/14-cmake-package`** | Export namespaced CMake package targets with supported components and dependency lookup. Provide a small external consumer example; this is SDK consumption, not a replacement for `S_define`. | `find_package(Trick CONFIG REQUIRED ...)` compiles/links from both build and install exports. A runtime-only consumer does not discover LLVM unnecessarily; installed exports contain no source/build paths. |

**Milestone:** after C, a source-built CMake core SDK can build real existing simulations. It is ready for developer/pilot users, not yet the default full distribution.

### Stack D — distribution components

Base: merged C. For simple GitHub stacking, use the following linear order; the individual optional-component PRs otherwise depend primarily on C.

| PR / branch suffix | Scope and useful result | Acceptance before merge |
| --- | --- | --- |
| **D1 — `cmake/15-data-products`** | Port non-GUI data-product libraries, conversion tools, parsers, and XML/catalog/data installation. | Convert a known recording and compare its parsed values; run installed tools without the checkout. GUI packages are absent in the headless job. |
| **D2 — `cmake/16-x-tools`** | Add X11/Motif-dependent native tools and explicit optional discovery. | Exercise `AUTO`/`ON`/`OFF`, a Linux GUI smoke under a display server, and a macOS XQuartz/Motif build. No GUI dependency leaks into unrelated targets. |
| **D3 — `cmake/17-java`** | Integrate Maven with declared outputs, binary-tree build/test/doc directories, install entries, and launcher resources. Replace old CMake-specific Maven profile plumbing with a clean output-directory property. | Build/test Java and launch installed applications on Linux/macOS; editing Java/resource input updates JARs. No source-tree writes; disabling Java removes its tool requirements. |
| **D4 — `cmake/18-hdf5`** | Add HDF5 recording through imported targets and feature-consistent core/SWIG/SDK metadata. | A simulation writes/reads a small HDF5 recording; disabled and explicitly requested-but-missing cases behave correctly. Test distribution and custom-prefix HDF5. |
| **D5 — `cmake/19-gsl`** | Add GSL support, definitions, and final-link dependencies. | Exercise an existing GSL-backed random/distribution path with a fixed seed; verify enabled/disabled selection and downstream linkage. Do not change algorithms or RNG policy. |
| **D6 — `cmake/20-civetweb`** | Build the current CivetWeb integration against an explicitly selected dependency; install required web resources. Do not rebuild the dashboard application as an unrelated modernization task. | Start the optional server and make a bounded HTTP request; disabled builds omit its dependency and targets. Validate external-library/runtime lookup and exported feature definitions. |

### Stack E — end-user installation and special build modes

Base: merged D.

| PR / branch suffix | Scope and useful result | Acceptance before merge |
| --- | --- | --- |
| **E1 — `cmake/21-source-installer`** | Implement `./install-trick` with the [build contract](README.md#source-installer-contract), prerequisite recipes, phase logs, stable option handling, and installed acceptance test. | One command succeeds on fresh supported Linux/macOS setups with prerequisites; WSL follows the Linux path. Test missing CMake, failed configure/build/test/install, incompatible cache reuse, and a successful rerun. |
| **E2 — `cmake/22-offline-release`** | Replace release/premade preparation with explicit parser-source selection, offline Java support, required assets, source archives, and staging rules. Use CPack only for formats it usefully owns. | Build/install a release archive without `.git`; repeat with network denied using the prepared offline inputs. Missing inputs fail clearly. Editing a grammar cannot silently use stale premade output. |
| **E3 — `cmake/23-32bit-tools`** | Add the Linux multilib toolchain and explicit host-ICG selection, including source-installer orchestration of host and target builds. Carry forward supported 32-bit simulation behavior. | On Oracle/RHEL-family 8, a 64-bit host ICG generates for and builds/runs a 32-bit simulation with matching target libraries/Python. Wrong-architecture packages fail early. Native Apple Silicon/x86_64 paths remain separate and unaffected. |

For E2, offline Java can either build using a complete prefetched Maven repository or consume release-provided JARs with version/hash metadata. The chosen mode must be explicit. CMake dependency-disconnection variables alone cannot enforce Maven's network behavior. Avoid automatic downloading inside the default CMake configuration.

### Stack F — release qualification

Base: merged E.

| PR / branch suffix | Scope and useful result | Acceptance before merge |
| --- | --- | --- |
| **F1 — `cmake/24-release-qualification`** | Extend the incremental CTest/CI coverage already introduced into the full platform and installed-simulation matrix; update Homebrew/release scripts and CI entry points. Add configuration reports and publish the behavior register with verified evidence. | All required environments meet the release gates in [qualification contract](qualification.md); representative project owners complete the migration checks; release source/offline artifacts install successfully. Remaining intentional deviations have user-facing notes. |

F1 changes orchestration, recipes, and acceptance coverage. Any missing component implementation discovered here gets its own focused prerequisite PR instead of being hidden in a “CI fixes” batch. Performance optimization is follow-up work: record representative configure, clean build, no-op build, header edit, and simulation-build times, then investigate concrete regressions.

### Stack G — release policy, timed to each major

These are separate release-time PRs, not branches kept open across years.

| PR / branch suffix | Scope and useful result | Acceptance before merge |
| --- | --- | --- |
| **G1 — `cmake/25-deprecate-autotools` — Trick 27** | Make CMake and `./install-trick` the normal instructions; add an Autotools deprecation notice naming Trick 29; update release notes and migration mapping. | F1 has passed. Both routes remain available; the legacy route still passes its maintained Linux/macOS smoke checks. Deprecation does not itself fail builds. |
| **G2 — `cmake/26-transition-completion` — Trick 28** | Confirm release production and distribution packaging use CMake; publish final migration guidance and explicitly resolve remaining internal/user hooks. | Required capabilities have CMake coverage or an approved documented retirement; no undocumented installation-layout dependence remains in representative simulations. |
| **G3 — `cmake/27-remove-autotools` — Trick 29** | Delete `configure`, Autoconf inputs/macros, framework Make recipes, obsolete generated configuration templates, and legacy-only release/CI paths. Preserve Make files still needed by simulations and independent examples. | Build, install, package, and run existing simulations on machines without Autoconf/Automake. GNU Make may still be present for simulation builds. Repository audit finds no live framework dependency on removed files. |

## Mapping to GitHub stacks

GitHub's native stacked PR feature is currently in public preview. It requires the stack's branches to live in the **same repository**, with each layer targeting the preceding branch; cross-fork stacks are not supported. For native stacks into `nasa/trick`, use branches in `nasa/trick`. This A1 branch is in `brendanny/trick` at the user's direction; it is an ordinary fork branch, not a native cross-fork stack. Subsequent native stacks can live entirely in the fork, or maintainers can import the commits into same-repository upstream branches. PR #2190's inspected head already resides there. If repository permissions require fork branches, use ordinary dependent PRs or arrange same-repository branches with a maintainer; do not assume a cross-fork chain gains native stack semantics. [GitHub stack rules](https://docs.github.com/en/pull-requests/get-started/about-stacked-prs)

Suggested working convention:

- Open only the current small stack and, when useful, its immediate successor. Land bottom-up rather than holding all 27 PRs open.
- If #2190 is still open, attach foundation work above it or use its branch as the temporary stack trunk; retarget/restack onto its merged result before landing independently.
- Give each PR a focused diff, include its planning ID, and link the migration tracking issue and difference IDs.
- Verify required checks on each layer's actual head/merge candidate after lower-layer changes. Do not rely on a passing tip to establish that every intermediate layer is valid.
- Keep build directories and caches separated by OS, compiler/ABI, dependency versions, generator, and feature configuration. Separate Autotools and CMake checkout/build state.

GitHub documents the `gh stack` extension with GitHub CLI >=2.90.0 and Git >=2.20. These are **maintainer workflow tools**, not Trick build dependencies. The normal sequence is `gh stack init`, `gh stack add <branch>`, `gh stack push`, and `gh stack submit`; use `master` as the normal trunk. [Stack quickstart](https://docs.github.com/en/pull-requests/get-started/stacked-prs-quickstart)
