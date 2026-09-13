# ICG rewrite Phase 0: initial contract inventory

Status: implementation started; Phase 0 exit gate is **not complete**.

This inventory was inspected at `brendanny/trick:icg-rewrite`, commit
`c5ba06ea79a8a9ecc3fa4938fd45a77b1e7b9e43`. The
[attached design plan](ICG_REWRITE_PLAN.md) was researched against an earlier
upstream revision; this document records the implementation checkout rather
than asserting that all research has been revalidated.

The first increment adds a [corpus and evidence runner](../../tools/icg_baseline/README.md).
The existing ICG, build path, runtime contract, and toolchain floors remain
authoritative during Phase 0.

## Generated file boundaries

| Producer | Artifact contract | Consumer / observation |
|---|---|---|
| `libexec/trick/configuration_processor` and `pm/s_source.pm` | `S_source.hh`, `build/S_source.cpp`, `build/CP_*`, top-level object resources | ICG/SWIG parse the synthetic header; simulation build compiles the source |
| `PrintAttributes::createIOFileName` | Per-header `io_*.cpp`; simulation paths mirror header directories under `build`; core and explicit output modes differ | Make compiles these into legacy metadata objects |
| `PrintAttributes::openMapFiles` / `closeMapFiles` | `build/class_map.cpp`, `build/extern_init_attr.h`; temporary dot-prefixed map files | Registry initialization; temporary files excluded from stable evidence |
| `PrintAttributes::printIOMakefile` | `Makefile_io_src`, `Makefile_ICG`, `io_link_list`, `trickify_io_link_list`, `ICG_processed`, `ICG_ext_lib` under `build` | Make dependency/link rules and SWIG input discovery |
| `PrintAttributes::printICGNoFiles` | `build/ICG_no_found` | Tracks headers without selected classes/enums |
| `PrintAttributes` SIE printers | `build/classes.resource`; core mode has separate locations | `libexec/trick/sie_concat` aggregates classes, top-level objects, and core resources into `S_sie.resource` |
| `libexec/trick/make_makefile_src` | `Makefile_src`, `Makefile_src_deps`, `Makefile_overrides`, `model_link_list`, `S_library_list`, `trickify_deps` under `build` | Model source/library dependency planning |
| `make_makefile_swig`, `convert_swig`, SWIG | `Makefile_swig*`, `*_py.i`, generated C++ wrappers, Python modules, Python link lists | Existing Python API and build path; the initial collector covers only selected source/build artifacts |

The manifest records mandatory groups separately so a missing registry or link
list cannot be masked by the presence of some metadata source. It does not yet
inventory every alternative output mode, generated Python package, or external
trickified library. Those are explicit additions before the full contract freezes.

## Symbols and semantic contracts

The initial emitter boundary is
`trick_source/codegen/Interface_Code_Gen/PrintFileContents10.cpp`:

| Output | Contract to preserve and subsequently compare semantically |
|---|---|
| `ATTRIBUTES attr<name>[]` | Field selection/order, type and units, access/I/O policy, dimensions, offsets, nested metadata, sentinel, STL callbacks |
| `ENUM_ATTR enum<name>[]` | Enumerator names/values and sentinel; scope/name encoding |
| `init_attr<name>()`, `init_attr<name>_c_intf()` | Namespace and C linkage, field initialization, inherited metadata registration |
| `io_src_sizeof_<name>` | Size entry points for user records/enums |
| `io_src_allocate_<name>`, `io_src_destruct_<name>`, `io_src_delete_<name>` | Availability and behavior based on construction/access/abstractness; exact ownership and allocation semantics |
| STL helper functions | Checkpoint, post-checkpoint, restore, clear, size, element get/set, and callback wiring |
| Class/enum population and units registration | Registry names, ordering dependencies, linkage, unit aliases |

`trick_source/sim_services/MemoryManager/MemoryManager_io_src_intf.cpp` resolves
the lifecycle/size symbol prefixes dynamically. `include/trick/attributes.h`
defines the layout consumed by MemoryManager and downstream services. Flattened
inheritance and layout in `ClassVisitor.cpp` remain a central extractor API gate.
Source snapshots alone do not validate these behaviors.

## Inputs that need to stay auditable

`main.cpp` declares `-I`, `-isystem`, `-D`, `-include`, `-f*`, `-icg-std`,
`-sim_services`, `-force`, `-v`, `-d`, `-m`, `-o`, `-c`/`-compat15`,
`-m32`, `-print-TRICK-ICG`, and the deprecated `-units-truth-is-scary`, plus
a permissive sink for other arguments. Declaring a flag does not establish that
it has a meaningful current effect; that audit is still required.

`HeaderSearchDirs.cpp` consumes `TRICK_HOME`, selected compiler information from
`trick-gte`, and `TRICK_ICG_EXCLUDE`, `TRICK_SYSTEM_ICG_EXCLUDE`, `TRICK_EXCLUDE`,
`TRICK_EXT_LIB_DIRS`, `TRICK_EXT_LIB_DIRS_OVERRIDES`, `TRICK_ICG_NOCOMMENT`, and
`TRICK_ICG_COMPAT15`. `PrintAttributes.cpp` also consumes `TRICK_ICG_IGNORE_TYPES`.
The collector records these along with selected build/compiler environment
variables; values established inside Make are available in verbose logs, not
automatically in the runner's parent environment.

Annotation behavior spans `CommentSaver.cpp` (header selection/comments),
`FieldDescription.cpp` (`trick_io`, `trick_chkpnt_io`, `trick_units`, legacy
comments), and binding-specific parsing in `convert_swig`. The complete grammar,
defaults, malformed-input behavior, and precedence still need differential tests.

## Acceptance status

Generation currently supports 15 scalar bases: `bool`, `char`, `signed char`,
`unsigned char`, `short`, `unsigned short`, `int`, `unsigned int`, `long`,
`unsigned long`, `long long`, `unsigned long long`, `float`, `double`, and `char16_t`, plus
unsigned-int bitfields and fixed arrays/aliases of those scalars. `wchar_t`, `char32_t`,
extended integers and `long double` remain unsupported. Plain-char
fields require signed native char. The [scalar corpus](../../tools/icg_baseline/scalars/README.md)
covers two records / 13 fields, while the [integer corpus](../../tools/icg_baseline/integers/README.md)
adds two records / 22 fields. Both compare legacy/candidate/native metadata and
real MemoryManager checkpoint restoration, with independent failure controls.
The [character corpus](../../tools/icg_baseline/characters/README.md) adds two
UTF-16 records / seven fields with metadata and runtime comparisons. It also
records why `wchar_t` and `char32_t` remain rejected: legacy assignment truncation
and omitted field metadata, respectively. UTF-16 support preserves code units;
it does not perform Unicode validation or conversion.
The [enum template corpus](../../tools/icg_baseline/template_enums/README.md)
adds five template tables / 15 fields with three enum dependencies. Named 32-bit
int/unsigned-int enum arguments, fields, arrays and nested templates pass actual
legacy/native metadata and MemoryManager checkpoint comparisons. The [ordinary enum corpus](../../tools/icg_baseline/record_enums/README.md)
adds two records / ten mixed builtin and enum fields, with aliases, arrays,
namespace-qualified types and compact/expanded checkpoint restoration. Other enum
storage widths, record-nested definitions and enum lifecycle output remain pending.

| Gate | Status after this increment |
|---|---|
| Focused corpus manifest and artifact capture | Implemented; synthetic plumbing tests plus actual legacy header reference integrity tests |
| Command timing, CPU/RSS, bytes/files/churn | Implemented; no production performance claim |
| Actual normalized legacy output baselines | Four existing headers / 12 checked-in snapshots, a focused lifecycle header / three snapshots, plus configured `SIM_test_templates` and `SIM_test_io` cold/warm/forced/rebuilt captures; [header references](../../tools/icg_baseline/legacy/README.md), [lifecycle reference](../../tools/icg_baseline/lifecycle/README.md), and [full-build scope](../../tools/icg_baseline/runtime/README.md). Full-build golden promotion, broader simulations, and minimum stacks remain pending |
| Legacy metadata versus extracted facts | Three fingerprinted headers: six record tables/sizes, six fields, two enum tables, and explicit record/enum exclusions. Actual captured C++ compiles against real Trick headers/UnitsMap; initialization/size entry points, compiled metadata, and independent native layouts/enum constants agree with facts. Compiler/dependency evidence and negative mutations are retained. Bounded candidate output now compiles separately and agrees with captured legacy/native observations; C-linkage entry points, source/symbol checks and atomic output are tested; general annotations, broader lifecycle/template coverage, STL and production integration remain pending |
| Policy input evidence | Explicit file requests and source-located roots, exact preprocessor comment spans, observed legacy policy environment, and structured concrete friend evidence implemented in facts v12. Real embedded/template headers and a multi-header synthetic input are exercised. Bounded resolved policy v4 characterizes eligibility, comment association, exclusions, units/I/O, descriptions/modifiers and operation-specific friend access with 38 live legacy cases. General policy remains pending |
| Rewrite-generated legacy metadata | Compiled legacy/candidate/native comparisons cover the 15 scalar types above, fixed arrays and aliases, unsigned bitfields, and enum tables. The [enum corpus](../../tools/icg_baseline/enums/README.md) includes ten compatible tables / 19 enumerators and explicit numeric rejections; the [array corpus](../../tools/icg_baseline/arrays/README.md) includes two records / nine fields. Policy v13 / emitter v12 also generate bounded template dependencies with first-use symbols and guarded real MemoryManager initialization; five tables replace legacy definitions in the configured checkpoint comparison. Opt-in lifecycle exports have independent native and configured runtime gates. Wide/UTF-32 characters, broader records/annotations, STL and production integration remain pending; see the [milestone](ICG_REWRITE_PLAN.md#201-next-milestone-generate-and-execute-legacy-metadata) |
| Small/medium/large representative corpus | Focused cases selected; medium/large selection pending |
| Full file/symbol/flag/annotation/runtime inventory | Initial source inventory only |
| LLVM 17 libclang capability | Complete; three required blockers recorded and LibTooling selected in ICG-001 |
| First C++17 LibTooling extraction target | Implemented as a standalone, main-file record slice; [scope and tests](../../trick_source/codegen/TrickCodeGen/README.md) |
| Core structured type/declaration graph | Implemented for pointers/references/arrays/aliases and recursive/nested/referenced records, namespace contexts/aliases, and unnamed declaration identity/storage; broader type kinds pending |
| Enum and bitfield facts | Scoped/unnamed/opaque enums, exact values and annotations, bitfield offsets/widths/padding and explicit non-addressability implemented; GCC conformance/accessors pending |
| Inheritance and base-layout facts | Source-ordered direct bases, access/source evidence, alias-preserving types, complete-object virtual-base tables, and data/nonvirtual layout implemented; inherited fields remain graph-owned rather than flattened |
| Callables and special-member declaration state | Non-template signatures, overload identity, defaults/redeclarations, virtual overrides, and explicit/implicit/deleted/defaulted/suppressed state implemented; full implicit signatures and generated-operation policy pending |
| Language linkage and annotation encoding | Transparent global/namespaced `extern "C"` traversal, explicit callable language linkage, actual Trick header regression, and fail-closed UTF-8 annotation validation implemented |
| Class-template signatures and concrete specializations | Primary/partial parameter metadata, canonical arguments/packs/defaults, selected pattern and deduced arguments, instance/member identity, layout and native probes implemented; dependent bodies and function/alias templates pending |
| Review hardening | Named file roots, exact integers/scalar extents, complete member diagnostics and safe reference collection, argument/normalization regressions, content-addressed sidecars, pinned Ruff CI, versioned owned identity tags, consistent display names, capability prerequisites, and verified normalized graph fingerprints implemented |
| GCC 8.5/12 extractor host builds | Dedicated LLVM 17 / Rocky Linux 8 CI jobs; does not establish generated-code conformance |
| LLVM 17–23 extractor adapters | Localized API adapters; every major in Linux/macOS CI, component linkage at 17/22/23, exact same-platform comparison of nine validated fixture graphs and selection requests, and package/version artifacts. LLVM 17 remains the floor; this does not establish every host/compiler/package combination |
| GCC 8.5/12 layout and generated-operation probes | Focused native size/alignment/public base-path, special-member type-trait, concrete-template layout, compiled legacy metadata/init/size, and lifecycle execution probes wired into host CI; broader generated-operation gates pending |
| Focused lifecycle differential | Six instrumented records, three actual legacy snapshots, 18 symbol-presence/absence checks, exact-operation traits, and 12 execution scenarios compared with validated facts. Generated allocation/destruction/free and scalar-new/delete ownership paths are distinct. Linux reference CI adds ASan/UBSan/LSan and a missing-deallocation regression. General lifecycle emission and exception/OOM/over-alignment handling remain pending |
| MemoryManager lifecycle integration | Configured `SIM_icg_lifecycle` compares nine real registration/dispatch/external-storage/SWIG-ownership executions and two rejected allocations with validated facts, before/after forced regeneration. Allocation metadata, name/interior lookup, removal before destructor callbacks, exact event order/stride, proxy ownership, and classified diagnostics are gated. Executive restart, recursive/concurrent ownership, general policy, and broader stacks remain pending |
| Runtime/Python behavior | Configured template and I/O simulations check scalar/array/enum bindings, the 16-field variable-input/checkpoint permission matrix, length conversions, and checkpoint readback before/after regeneration. Opaque nested-template access and direct-SWIG versus metadata permission differences are recorded. Executive restart, lifetime, nested access, variable-server output, and broader units/I/O coverage remain pending |
| S_define and replacement-binding spikes | Pending; configured baseline uses the existing Perl/SWIG path |
| Exact platform packages and ADR decisions | Package matrix pending; ICG-001 and ICG-002 accepted, eight initial ADRs pending |

The capability decision and first standalone extractor slice are implemented.
The core structural model and namespace/anonymous declaration increment are also
implemented, together with enum, bitfield, and inheritance/base-layout facts.
Callable facts and implicit special-member summaries are now implemented as well.
Class-template signature metadata and concrete specialization graphs are implemented;
language-linkage blocks and written/inherited callable defaults are now explicit.
Dependent bodies and function/alias templates remain. The next priority is a
[facts-to-legacy-metadata vertical slice](ICG_REWRITE_PLAN.md#201-next-milestone-generate-and-execute-legacy-metadata),
with broader real-header selection/comment/friend evidence and compiled execution
of newly generated output. Broader configured simulation/runtime baselines and
the remaining Phase 0 gates are still required. This does not authorize switching
the production ICG.
