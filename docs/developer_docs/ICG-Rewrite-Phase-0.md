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

| Gate | Status after this increment |
|---|---|
| Focused corpus manifest and artifact capture | Implemented; harness tested with synthetic output |
| Command timing, CPU/RSS, bytes/files/churn | Implemented; no production performance claim |
| Actual normalized legacy output baselines | Pending configured Trick runs and review |
| Small/medium/large representative corpus | Focused cases selected; medium/large selection pending |
| Full file/symbol/flag/annotation/runtime inventory | Initial source inventory only |
| LLVM 17 libclang capability and GCC 8.5/12 layout probes | Pending |
| Runtime/Python behavior, S_define, binding spikes | Pending |
| Exact platform packages and ADR decisions | Pending |

The next increment should obtain actual baseline evidence and implement the
capability spike, not select an extractor API from assumed coverage.
