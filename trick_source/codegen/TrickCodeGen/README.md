# LibTooling extractor: structural model and declaration contexts

`trick-icg-extract` implements step 3 and the core structural-model portion of
step 4 of the [rewrite sequence](../../../docs/developer_docs/ICG_REWRITE_PLAN.md#20-suggested-first-pr-sequence).
It is a standalone development target, **not** a replacement for `trick-ICG`.
The production build, runtime ABI, and generated metadata are unchanged.

## Build and test

Requires matching LLVM/Clang **17–23** development packages and resource headers,
CMake 3.20+, a C++17 host compiler, and Python 3.11+ with
`jsonschema>=4.18,<5` for the integration tests. CMake uses the LLVM and Clang
configuration packages and their imported targets, and queries that installation's
`clang -print-resource-dir`. Configuration rejects majors outside that range and
a driver whose major differs from the selected LLVM package; a compile-time check
also requires matching Clang headers. LLVM 17 remains the minimum/reference
frontend, and the C++17, GCC 8.5, and Python 3.11 floors are unchanged.

```sh
python3 -m pip install 'jsonschema>=4.18,<5'
cmake -S trick_source/codegen/TrickCodeGen -B build/icg-extract \
  -DLLVM_DIR=/usr/lib/llvm-17/lib/cmake/llvm \
  -DPython3_EXECUTABLE="$(command -v python3)" -DCMAKE_BUILD_TYPE=Release
cmake --build build/icg-extract --parallel 2
ctest --test-dir build/icg-extract --output-on-failure
build/icg-extract/trick-icg-extract \
  trick_source/codegen/TrickCodeGen/tests/fixtures/record.hh -- \
  > build/icg-extract/record.json
python3 tools/icg_schema/validate.py \
  --schema trick_source/codegen/TrickCodeGen/ir/extracted-facts.schema.json \
  build/icg-extract/record.json
```

On macOS, install [`llvm@17`](https://formulae.brew.sh/formula/llvm@17) and pass
`-DLLVM_DIR="$(brew --prefix llvm@17)/lib/cmake/llvm"`; substitute any supported
major in both places. Linux CI uses the explicit versioned
[`apt.llvm.org`](https://apt.llvm.org/) Noble repositories, including
`llvm-toolchain-noble-23`, rather than the rolling snapshot repository.

The [extractor workflow](../../../.github/workflows/icg-extractor.yml) requires
`-Wall -Wextra -Wpedantic -Werror` builds and the actual-binary integration suite:

| Platform / compiler | LLVM majors | Python / linkage |
|---|---|---|
| Ubuntu 24.04 / GCC | Every major 17–23 | 3.11 / package default |
| macOS 14 / AppleClang | Every major 17–23 | 3.11 / package default |
| Ubuntu 24.04 / GCC | 17, 22, 23 | 3.12 / component libraries |
| macOS 14 / AppleClang | 17, 23 | 3.12 / package default |
| Rocky Linux 8 / GCC 8.5 and 12 | 17 | 3.11 / combined `clang-cpp` |

`-DICG_CLANG_LINKAGE=AUTO` follows the package configuration. `SHARED` explicitly
selects `clang-cpp` plus LLVM; `COMPONENTS` selects the imported `clangTooling` and
`clangIndex` targets and their dependencies. The latter exercises the changed
Clang 22/23 link graph. Some distributions, including Rocky, ship only the
combined library. Each Linux/macOS artifact records exact package versions,
driver/LLVM versions, CMake configuration, test logs, and all eight facts fixtures.
These are tested package combinations, not a GCC 8.5 × LLVM 17–23 runtime/ABI
guarantee. Installation/distribution policy and broader generated-operation
conformance remain separate gates.

Two comparison jobs require all seven versions' eight fixtures, validate each
document and its digest independently, and compare complete `graph_digest` values
against LLVM 17 on the same platform and target. Missing/duplicate fixtures,
mislabeled frontends, different targets, and any changed graph fact fail the job.
Only the existing digest's machine-path/provenance exclusions apply: type
spellings, declaration IDs, source evidence, layouts, annotations, and capabilities
are all compared. Linux and macOS targets are not equated. The comparison report
and full input artifacts are retained; an equal graph is not a parse-cache key.

### Frontend adapters

Version conditions live in `extractor/ClangCompat.hh`, outside the owned facts:

- LLVM 18: scoped linkage and pure-virtual queries; all versions use `FileEntryRef`.
- LLVM 19: include callbacks and structured template-default arguments.
- LLVM 22: removed `ElaboratedType`, declaration-type queries, and type printing.
  Strip only elaboration while preserving local qualifiers and alias nodes;
  retain fully scoped names and the previous anonymous-name display policy.
- LLVM 23: USR header/library relocation, explicit-instantiation directive nodes,
  anonymous-name policy, and occurrence-specific comment lookup. Recover raw
  bytes through the public local parsed-comment API and owning raw-comment list;
  fail closed if the original attachment cannot be recovered. Never substitute a
  comment from a different redeclaration.

Native layout/type-trait probes, rooted paths and symlinks, qualifiers/aliases,
templates/packs, comment provenance/invalid UTF-8, and failure-output checks run
against each actual frontend. This increment does not enable newer model language
modes, experimental evaluators, warning-policy files, or profiling flags.

## Invocation contract

```text
trick-icg-extract [--source-root DIR] [--path-root NAME=DIR] [--diagnostics-format=json] HEADER -- [CLANG FLAGS]
```

Exactly one input and an explicit `--` are required. Relative paths are interpreted
against the process working directory. Arguments remain an argv vector; no shell
command is assembled or run. Clang is invoked in-process through a
[`FixedCompilationDatabase` and `ClangTool`](https://releases.llvm.org/17.0.1/tools/clang/docs/LibTooling.html).
The configured Clang executable provides driver identity and resource discovery,
not a subprocess parse.

The initial audited argument surface is:

- `-I`, `-isystem`, `-iquote`, `-D`, `-U`, `-include`, `-imacros`, `--sysroot`,
  `-isysroot`, `-target`, `--target`, each followed by a nonempty value that does
  not start with `-` (use `./-directory` for a directory beginning with a dash);
- joined `-Ipath`, `-Dname=value`, `-Uname`, `--sysroot=path`, `--target=triple`;
- `-std=c++17`, `-m32`, `-m64`, `-fno-exceptions`, `-fno-rtti`, and Clang `-W...`
  diagnostic controls (not `-Wl,`, `-Wa,`, or `-Wp,` driver forwarding).

The tool explicitly adds C++17, C++ input mode, syntax-only parsing, all-comment
parsing, the discovered resource directory, and diagnostic formatting controls.
Unknown warning names are errors by default. Headers are still parsed as the main
file; the tool disables only `-Wpragma-once-outside-header` to avoid that artificial
warning. Other warnings remain visible, and supplied flags may re-enable it.
The resulting driver argv, target,
working directory, frontend/extractor versions, and selected include/SDK environment
variables appear in provenance. Clang's normal driver-to-cc1 translation still
applies. No code-generation options are silently stripped: other options, response
files, compiler plugins, alternate dialects, and extra source inputs are rejected.
This is **not yet the GCC argument classifier** or a compilation-database reader.

Successful extraction writes one deterministic, schema-version-10 facts document
to stdout. Parse errors, unsupported declarations, and driver failures write no
facts and exit nonzero. Exit 2 means invalid invocation/input; exit 1 means a
frontend or extraction failure. Warnings remain visible and do not fail extraction
unless promoted by a supplied diagnostic flag.

By default diagnostics are human-readable on stderr. `--diagnostics-format=json`
writes a single stderr envelope containing `schema_version: 2`,
`document_kind: "trick.icg.diagnostics"`, `files`, and `diagnostics`, including on
failure. The file and diagnostic nodes use the same definitions as the facts
schema; source locations resolve against that envelope's files. Success also
includes the diagnostics in the facts. `CLANG_<numeric-id>` codes are tied to the
recorded Clang version; extractor codes such as `ICG_UNSUPPORTED_ARGUMENT` and
`ICG_UNSUPPORTED_DECLARATION` are stable. Machine output is not interleaved with
Clang's human warning/error-count summaries. Fix-it edits are not yet extracted.

## Implemented facts and deliberate limits

This slice selects records, class templates, enums, type aliases, callables,
namespaces, and namespace aliases **in the main file**, including declarations
inside namespace blocks. It closes their
type and context dependencies across included headers. Semantic and lexical parent
links distinguish out-of-line record definitions from their owning scope.
Unreferenced included siblings are not selected; a referenced unsupported
declaration fails the whole extraction. This is dependency closure, not Trick
selection policy.

Named, inline, nested, reopened, and anonymous namespaces are supported. A namespace
has one canonical node, sorted `declaration_ids` for its selected semantic children,
and `reopening_sources` for all its blocks in translation-unit order. The first
block supplies `source`; annotations from all blocks are retained in that order.
Namespace aliases preserve their immediate `target_namespace_id`, including alias
chains. Qualified display names retain inline namespaces.

Unnamed records are supported through typedefs, named member declarators, and
anonymous struct/union members. `anonymous` marks unnamed records, enums, and namespaces.
An anonymous aggregate's implicit physical storage field has an empty name and
`anonymous_member: true`; its type refers to the nested unnamed record. Field
offsets are relative to each owning record. Implicit lookup aliases for promoted
members are not duplicated: consumers walk the anonymous storage's nested fields
and add offsets when they need flattened member paths.

For complete records it records size/alignment and traits, source-order fields,
access/mutability/qualifiers, frontend field offsets, raw comments and
`clang::annotate` payloads, stable USRs, and spelling/expansion source locations.
Forward declarations are folded into a single record node at its definition when
one exists in the translation unit. Otherwise the node is incomplete, with no
field facts, null size/alignment, and `INCOMPLETE_TYPE` layout capability. It does
not query Clang's layout or definition-only base APIs for incomplete records.
Record redeclaration source/annotation history is not yet modeled; the selected
definition (or canonical forward declaration) supplies that record's source.
End locations for declaration ranges
are exclusive, following the final token; point diagnostics need not span a token.
No Trick annotation policy is applied. Size and offset units are bits, with the
target's character width supplied by Clang. Extents and layout quantities use JSON
numbers through `2^53-1`, then canonical decimal strings, preserving exact values
in readers that store JSON numbers as binary64. Null retains its unknown or
incomplete meaning. The extractor supports array extents through 64 bits.

Enums preserve scopedness, fixedness and signedness of the underlying type, a
structural underlying-type link, size/alignment, and source-order enumerators with
raw comments/annotations and spelling/expansion locations. Each enumerator has one
canonical decimal-string `value`: its exact mathematical value after conversion
to the underlying type, not two signed/unsigned reinterpretations. Values beyond
64 bits are supported through Clang's arbitrary-precision integers. Different
names may have the same value. Enumerator entries are owned by their enum rather
than duplicated as independent declarations. Named, unnamed, nested, and referenced
enums use the existing identity and dependency-closure rules.

An opaque fixed enum (for example `enum class State : int;`) has `complete: true`
and known layout, but `definition: false` and no enumerators. Scoped enums have a
fixed underlying type even when `int` is implicit. Redeclarations fold to a
definition if one exists; otherwise the canonical opaque declaration supplies
source/annotations. Enum redeclaration history is not yet retained.

Bitfields retain their declared `bit_width` and Clang's record-relative bit offset.
`field_ids` includes unnamed padding and zero-width separators in source order;
these have empty names and source-based IDs, but are **not** anonymous aggregate
members. A width larger than the underlying type is valid C++ padding and is not
clamped. The supported concrete width range matches Clang's unsigned 32-bit layout
API; dependent or unevaluable widths fail extraction. Every bitfield carries
`field-address: unsupported / BITFIELD_NOT_ADDRESSABLE`. Its offset is frontend
layout evidence, not a pointer or permission to emit address-of/`offsetof` code.
No generated bitfield accessor or GCC-layout conformance claim is made here.

The frontend adapter copies facts into owned values while the AST is alive.
Serialization occurs after the frontend action ends; no Clang object or borrowed
source buffer crosses that lifetime boundary. Object keys and node arrays are
sorted; fields, enumerators, includes, diagnostics, and arguments retain semantic order.

`TypeNode` is a typed, frontend-independent value model. `TypeGraph` is a
translation-unit-local interner for builtin types, record/enum references, typedef/using
aliases, pointers, lvalue/rvalue references, and fixed/incomplete arrays. Each array
node describes one dimension using scalar `extent` (null for incomplete arrays);
multidimensional arrays nest via `element_id`.
Thus an array of pointers and a pointer to an array have different edge order,
not just different display strings. Function/member-pointer/vector/dependent
types remain unsupported.

Type IDs hash kind, local CVR qualifiers, and structural child/declaration IDs
(normalized builtin names for leaf types), not rendered composite type strings.
Alias nodes reference their declaration; its `underlying_type_id` preserves the
next sugared type layer, while `canonical_id` links directly to the fully desugared
type. CVR qualifiers are local to a layer: `const int *` and `int *const` differ.
Array qualification is normalized onto its elements, including through aliases;
reference collapsing follows the frontend's semantic reference type. Tag keywords
and redundant parentheses do not create extra graph nodes. Display spelling is
diagnostic information, not a round-trip source representation or identity key.
When equivalent types intern to one node, the lexicographically smallest observed
spelling is retained. Per-use spelling is not modeled by this structural node.

Named declaration IDs normally hash Clang USRs. Unnamed declarations, declarations
without USRs, and descendants of a source-identified context instead hash the
declaration kind, semantic parent ID, name, and rooted physical source anchor.
The anchor includes the complete spelling and expansion chains, distinguishing
repeated uses and macro argument substitution sites inside one outer expansion.
Shared origin subgraphs are memoized and hashed. Anonymous namespaces also include
the translation-unit file ID so header-local entities are not merged across
different translation units.
`identity_kind` records `usr` or `source`; `usr` retains frontend evidence when
available and is null otherwise. Distinct canonical declarations that collide
produce `ICG_IDENTITY_COLLISION`; missing physical fallback locations produce
`ICG_IDENTITY_SOURCE`. Neither failure publishes facts.

Source-based IDs survive root relocation and symlink aliases with unchanged rooted
file names and bytes. Source edits or a different first namespace block may change
them; they are not persistent symbol IDs across revisions. Anonymous display names
omit physical locations, and names are not unique identity keys. Forward
declarations and definitions share one node. A worklist closes dependencies without
recursively expanding mutually referential record fields. Non-template overloads
have distinct identities, including constructors, conversions, and operators whose
semantic names are not Clang identifiers. They use USRs in named contexts and the
same physical source anchors in source-identified contexts. Concrete class-template
specializations add canonical argument identity as described below.
Translation-unit-local functions use source identity plus the translation-unit
file ID, so internal symbols are not merged merely because their USRs share a
header basename. Their IDs still survive relocation of unchanged named roots.

Extractor 0.7.0 advances facts to schema 7 for callables and special-member
declaration state, retaining the inheritance, enum/bitfield, identity, and context meanings.
Extractor 0.8.0 advances facts to schema 8 for review hardening: versioned,
extractor-owned source-identity kind tags, consistent anonymous display names,
capability prerequisites, and a verified normalized graph fingerprint.
Extractor 0.9.0 advances facts to schema 9 for class-template signatures and
concrete specializations. Extractor 0.10.0 advances facts to schema 10 for
language-linkage contexts, fail-closed annotation encoding, and written versus
inherited callable defaults. The synthetic minimal fixture is migrated; the reader
rejects versions 1 through 9.
Named file roots, scalar extents, and exact integer encoding introduced in v3 remain
in force. The diagnostics envelope stays at version 2; its file shape is unchanged.

`provenance.identity_version: 1` replaces the earlier unversioned source recipe,
including Clang-internal kind strings, with owned tags and an explicit version in
the hashed object. Source-based IDs intentionally change at this revision; USR
identity does not. This does not promise stable IDs across LLVM upgrades. Qualified
display names use consistent semantic context components, including associated
typedef names for unnamed tags. Two unnamed siblings can still share a display
name; consumers must follow parent/type IDs rather than match name prefixes.

Concrete records, including instantiated class templates, support single, multiple,
and virtual inheritance. `bases`
contains only direct edges, in source order, with the canonical record declaration,
the written type (including aliases), effective and written access, virtualness,
and base-specifier source range. `written_access: "none"` distinguishes an omitted
access keyword from an explicit one; effective access applies the class/struct
default. Inherited fields are not copied into `field_ids`: following the base graph
preserves the distinct paths to repeated nonvirtual subobjects.

A nonvirtual edge has a fixed `offset_bits` relative to its owning record subobject.
A virtual edge has `offset_bits: null`: its location depends on the most-derived
object. Each complete record instead has a `virtual_base_offsets` table for all
its unique direct/indirect virtual bases, sorted by declaration ID. These offsets
are relative to **this record as a complete object**, not to this record when it
is a base of another class. A consumer traversing virtual edges must use the
most-derived record's table. A shared virtual base appears once; nonvirtual copies
of the same type remain separate graph paths.

Records also expose Clang's `data_size_bits`, `non_virtual_size_bits`, and
`non_virtual_alignment_bits`, alongside complete-object size/alignment. These are
frontend layout facts, not a recipe for summing `sizeof(base)` values: empty-base
optimization and tail-padding reuse can overlap those complete-object extents.
Incomplete records have null layout quantities and empty base tables. This slice
does not expose hidden ABI slots, flatten legacy metadata, or generate casts/accessors.

Non-template functions, methods, constructors, destructors, conversions, and
operators now produce `callable` nodes. Records own their direct explicit methods
through source-ordered `callable_ids`, separate from nested types and fields.
Signatures retain adjusted parameter types and `original_type_id` (notably arrays
before parameter decay), return types, variadicness, CV/ref qualification,
static/virtual/pure/final, explicit, constexpr, deletion/defaulting, and
`user_provided` facts. `linkage` retains Clang's linkage category; `static` covers
both static member functions and free functions with a static declaration, even
when a later redeclaration omits that keyword. Constructors/destructors have null return types. This slice
accepts Clang's `CC_C` ABI calling convention, not other calling conventions or
special parameter/register ABI extensions. The separate `language_linkage` fact
is `c`, `c++`, or `none`: the last applies when Clang gives an internal or otherwise
non-language-linked name. Member functions can be `c++` or `none`, but never `c`.
`extern "C"` blocks are transparent selection/context wrappers rather than graph
declarations, including blocks nested in namespaces.

One canonical callable node retains all observed `redeclarations` in translation-unit
order, including each parameter's name, source, defaults, and raw annotations.
The last redeclaration supplies the node's source, parameters, and lexical context;
the semantic parent remains its owning namespace/record. Function annotations are
also aggregated across occurrences. `definition` means any occurrence is a definition
(including `= delete`/`= default`), not that a linkable implementation was generated.
An out-of-line defaulted constructor can be `defaulted` and `user_provided` together.
`has_default` describes the effective default at that occurrence, while
`default_origin` distinguishes `written`, `inherited`, and null. An inherited
default retains the original `default_spelling` and `default_source`; defaults
cannot be rewritten or disappear later in the redeclaration chain.
`default_spelling` is Clang's pretty-printed expression evidence, **not round-trip
source or generated-code input**. Bodies, local declarations,
and expression dependencies are not serialized or included in declaration selection.

Virtual methods retain direct `overridden_declaration_ids`. When a destructor
overrides an implicit virtual destructor, `overridden_implicit_destructor_record_ids`
identifies that base record instead of inventing a source declaration or callable ID.
Covariant return types remain separate callable facts; no trampoline policy is inferred.

Each record has six fixed-order `special_members` summaries: default/copy/move
construction, copy/move assignment, and destruction. Clang Sema materializes the
implicit declarations before these are queried. States distinguish `implicit`,
`user_declared`, `suppressed`, and `unknown` (incomplete records). User-declared
slots link all matching callable IDs. Only implicit slots contain deletion,
triviality, virtualness, and evaluated noexcept facts; other slots leave those
values null. Unresolved exception specifications remain `unknown`, never assumed
nothrow. These are declaration-state summaries, not full implicit callable
signatures or use-site constructibility/access decisions. A suppressed move can
still permit copying an rvalue; a nondeleted private constructor is not publicly
constructible; a deleted implicit member can still have a triviality flag. No
allocation/destruction/binding capability is inferred from these flags alone.

Class-template primary and partial patterns now have `class_template` nodes.
They retain parameter kind, name, pack boundary, depth/index, source, nested
template-template signatures, and default spelling/source evidence, including
inherited defaults. Non-type parameters retain declared type spelling and whether
that type is dependent. Comments and class annotations are retained together.
A partial pattern links its primary and has descriptive `pattern_spelling`.
These are **signature metadata**, not a dependent type/body graph: every pattern
states `template-pattern: unknown / DEPENDENT_TEMPLATE_PATTERN` and carries no
fields, callable list, or layout. No dependent body is traversed or validated by
this slice, and a pattern definition does not promise that an arbitrary
instantiation is valid or extractable.

Concrete instances remain `record` declarations and structural record types.
Their `specialization_kind` distinguishes uninstantiated references, implicit
instantiation, explicit specialization, and explicit instantiation declarations
and definitions. They link the primary and canonical `template_arguments`,
including defaults. An instantiated record additionally links the selected
primary/partial pattern and its deduced `instantiation_arguments`; an explicit
specialization has neither. A valid `point_of_instantiation` retains physical
source evidence. Pointer-only references can remain incomplete; extraction does
not force all possible instantiations. Selected instances reuse field, bitfield,
base, callable, and special-member extraction and its fail-closed checks.

Arguments are typed objects for canonical types, exact integral values, null
pointers, primary class-template references, and packs. Each pack occupies one
parameter slot with an ordered `elements` array, including empty packs. No type
string is split to recover arguments. Integral values are canonical decimal
strings with Clang's bit width and signedness, including enum and `auto` arguments.
Defaults and alias spellings do not create duplicate instances. Specialization
source identity includes its primary ID and canonical arguments, propagating to
instantiated members whose physical source locations are shared by many instances.
Owned identity tags extend version 1 to class-template kinds; previous supported
kinds retain their recipe. Display names include arguments but remain nonunique.

Function/alias templates, declaration-valued and member/function-pointer
arguments, dependent expressions/expansions as concrete arguments, dependent
pattern bodies/types, and uninstantiated method defaults remain outside this
increment. Encountering one in a selected concrete graph fails without publishing
facts. Pattern spellings/defaults are evidence, not backend code-generation input.
The validator checks argument shape, references, canonicality, pack/parameter
binding, integer range/signedness, specialization state, ownership, and dependent
pattern capabilities; it does not redo C++ template deduction or overload resolution.

Physical input files, their bytes' SHA-256 digests, and resolved include directives
are recorded through preprocessor callbacks. Forced includes are tracked as inputs
even when their directive comes from Clang's synthetic command-line buffer.
Only dependency declarations and their contexts enter from included headers. Every
physical file must match a named path root. `source` comes from `--source-root`
(default: current directory); `resource-dir` defaults to the matching Clang
installation. Repeat `--path-root NAME=DIR` for `sysroot`, `build`, or vendor roots.
Names match `[a-z][a-z0-9-]*`; directories must exist, resolve uniquely, and may
nest. The longest resolved directory prefix wins. Use the same root names and
relative file layout on each machine. For example:

```sh
trick-icg-extract --source-root "$PWD" \
  --path-root sysroot=/opt/sdk --path-root build="$PWD/build" \
  model.hh -- -isysroot /opt/sdk -I build
```

Root mappings classify paths; they do not add include paths or a compiler sysroot.
The sole exception is `--path-root resource-dir=DIR`, which also selects that
directory's Clang resource headers, allowing a matching SDK to be relocated.
An unmapped input produces `ICG_UNMAPPED_FILE` and no facts. Each path records its
`root` and relative `portable` value; file IDs hash that pair. Resolved symlinks
(including `/var` and `/private/var`) preserve identity. Source and resource header
relocations are exercised with real resource headers in the integration suite.
Original and real paths, root locations, arguments, and target provenance remain
available for diagnostics and evidence. Rooted identity removes machine path noise;
different OS headers and target layouts can still yield legitimate semantic differences.

Homebrew's libc++ wrappers live outside Clang's resource directory. When using
them, also pass `--path-root stdlib="$(brew --prefix llvm@17)/include/c++/v1"`.
Map the macOS SDK separately with `--path-root sysroot="$(xcrun --show-sdk-path)"`
when its headers are used. CTest supplies the matching LLVM installation's libc++
root to the integration runner explicitly; the extractor still rejects other
unmapped inputs.

`input_digest` is an **evidence fingerprint, not a production cache key**. It hashes
the deterministic document before inserting the digest, covering the recorded
arguments, environment, frontend facts, physical inputs, and exact paths. It is
not relocatable and does not capture all filesystem probes, volatile predefined
macros, or every possible environment influence. No cache is created or reused.

`graph_digest` is a separate, validator-verified fingerprint of normalized graph
output. Version 1 hashes schema/identity/digest versions and the ID-sorted
`files`/`types`/`declarations`, omitting only file `path.spelled` and `path.real`.
All other graph facts, rooted paths, file contents' digests, and ordered arrays
remain significant. Other provenance and diagnostics are excluded. This permits
comparison after relocation of unchanged rooted inputs/facts, including vendor
and real resource headers. An unused command-line define changes `input_digest`
but not `graph_digest`; changed file bytes, layouts, or annotations change both.
Paths embedded in actual facts (for example `__FILE__` in an annotation) are not
rewritten. Equal graph hashes alone prove neither ABI compatibility nor complete
cache inputs; inspect target/frontend provenance separately, and do not require
Linux/macOS graphs to match. See [ICG-002](../../../docs/developer_docs/architecture/ICG-002-ir-contract.md#review-hardening-schema-8)
for the exact canonical serialization and projection contract.

Raw comment and `clang::annotate` payloads must be valid UTF-8 before they enter
an LLVM JSON value. Invalid bytes produce `ICG_INVALID_ENCODING` at the annotation
source and suppress the facts document; they are never silently replaced by U+FFFD.
File digests continue to cover the exact input bytes.

Function/alias templates, function/member-pointer signatures, deduced-return
structural types, friends, variables, explicit
using declarations/directives, unsupported language linkage, and unsupported structural types
in the selected declaration closure
fail explicitly rather than producing apparently complete facts. Unsupported
members are collected across a record before it is rejected, so one run reports
all offending member locations while still publishing no partial facts. The graph
validator checks required/kind-specific edges, self-canonical targets, canonical
pointee/element consistency, alias targets, member ownership, incomplete layout,
namespace ownership, context/namespace-alias cycles, anonymous storage, source
identity propagation, enum value ranges/completeness, bitfield layout/addressability,
base type/access/layout consistency, inheritance cycles, exact transitive virtual-base
closure, callable ownership/redeclarations/defaults/override ancestry, special-member
state consistency, and direct structural cycles. Record-reference cycles are
valid; pointer/alias
type cycles with no intervening record declaration are not. It still does not
prove every invariant for not-yet-implemented schema kinds.

The checked-in `tests/fixtures/structured.hh` exercises aliases, recursive/header
records, arrays, and incomplete/reference types. `contexts.hh` adds reopened and
inline namespaces, namespace aliases, unnamed records, anonymous union storage,
and nested macro expansions. `enums-bitfields.hh` adds enum values/opaque types and
bitfield storage/separators. `inheritance.hh` adds repeated/mixed/virtual diamonds,
typedef bases, access defaults, packing, empty bases, and tail-padding reuse.
`callables.hh` adds overloads, redeclarations, parameter decay, defaults, virtual
methods, access, deletion/defaulting, and implicit special members. `linkage.hh`
adds global/namespaced C-language blocks and C++ controls; the integration suite
also extracts the real `include/trick/simtime_proto.h`. `templates.hh`
adds primary/partial/explicit specializations, defaults, packs, template-template
arguments, null pointers, explicit instantiations, and incomplete references. CI captures
these and the original `record.hh` output for inspection on Linux and macOS.

CTest also passes the configured native C++ compiler to the integration runner.
One test compiles and runs real fixture objects, comparing `sizeof`, `alignof`, and
public base-path casts against extracted layout, including virtual offsets in
different most-derived objects. This runs in the GCC 8.5/12 host lanes as well as
Linux/macOS lanes. It is focused layout evidence, not completion of the general
GCC generated-operation conformance gate. Private/protected casts are deliberately
not attempted. The intentionally ambiguous `Mixed` fixture keeps
`-Winaccessible-base` nonfatal after a compiler feature check. GCC 8 instead uses
the older `-Wextra` category: only the native probe enables a diagnostic pragma
scoped to that one fixture declaration. Other warnings remain errors; extraction
does not enable this fixture exception.
When invoking `tests/test_extract.py` directly, pass `--layout-compiler /path/to/c++`;
omitting it explicitly skips the three native probe tests. The probes require a native compiler,
not a cross-compiled executable.

A second native probe compiles standard type-trait assertions against the focused
special-member facts and exercises the suppressed-move/copy fallback and private
constructor distinctions above. These probes run in all six extractor CI lanes,
including GCC 8.5/12. They do not establish general generated-operation parity.

A third native probe compiles size/alignment and standard-layout field-offset
assertions against concrete template instances. It runs in those same lanes.

Next extend dependent template modeling and remaining declaration kinds. Legacy
differential baselines and the remaining Phase 0 gates still need
completion before any production switch.

## Python style

Install `python3 -m pip install -r tools/icg_requirements.txt`, then run:

```sh
ruff check tools/icg_baseline tools/icg_capability tools/icg_schema trick_source/codegen/TrickCodeGen/tests
ruff format --check tools/icg_baseline tools/icg_capability tools/icg_schema trick_source/codegen/TrickCodeGen/tests
```

`ruff.toml` requires Ruff 0.16.6 and preview formatting, matching the existing
repository style workflow. The ICG style workflow enforces these checks on branch
pushes as well as pull requests.
