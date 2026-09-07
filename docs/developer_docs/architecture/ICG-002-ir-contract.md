# ICG-002: Use versioned, strict JSON for extracted facts

- Status: Accepted for the Phase 1 vertical slice
- Date: 2026-09-05
- Schema: [`extracted-facts.schema.json`](../../../trick_source/codegen/TrickCodeGen/ir/extracted-facts.schema.json)

## Context

Parsing is the expensive, LLVM-dependent step. Legacy metadata, later bindings,
SIE, inspection, and build manifests need a stable semantic input without Clang
pointers or backend policy. The representation must be inspectable, deterministic,
and testable before compact encoding is justified.

## Decision

The extractor emits a UTF-8 JSON document with `document_kind` and an integer
`schema_version`. JSON Schema draft 2020-12 defines the wire shape. Readers are
strict: unknown properties and dangling graph references fail validation. The
current facts schema is version 10; the independent diagnostics envelope is v2.

The document contains frontend facts only:

- exact invocation/target/tool provenance and input digest;
- stable file, type, and declaration IDs;
- spelled, real, and portable paths plus spelling/expansion locations;
- a graph of structured types and declarations, including template packs;
- raw annotations, frontend capabilities with reason codes, and diagnostics.

Python normalization will produce a separate resolved codegen model. Selection,
legacy-printability decisions, output directories, Make formatting, and binding
library types do not enter extracted facts.

Within a document, Clang USRs are preferred for named declaration identity when
present. The extractor derives deterministic fallback IDs for unnamed declarations,
missing USRs, and descendants of source-identified contexts from declaration kind,
semantic parent identity, name, and rooted physical source anchors. Overload/type
discriminators must be added before supporting kinds that require them; those
kinds remain rejected today. Types use structural IDs and references. IDs are
opaque to consumers; consumers must not parse them for semantics.

Arrays are sorted by ID unless their order has semantic meaning, such as function
parameters, template arguments, dimensions, or source-order enumerators. JSON
object member order is insignificant. Integral constants are decimal strings
where their full signed/unsigned range may exceed JSON's interoperable integer
range.

The v8 review-hardening contract below specifies the current identity tags,
display-name convention, capability checks, and normalized graph fingerprint.

Paths retain their spelled and real forms for diagnostics and provenance. The
portable form replaces configured roots and is the only form permitted in cache
identity and generated output. Cache keys additionally include exact normalized
arguments, target, extractor/frontend/schema versions, environment inputs, and
transitive dependency contents; the top-level `input_digest` commits to that
complete set once the extractor implements it.

Before the first production cache is written, every incompatible shape or meaning
change increments `schema_version`. Readers reject versions they do not support.
After the initial wire contract freezes, compatible optional additions require an explicitly
revised schema and reader review; silently ignoring unknown properties is not a
compatibility strategy.

## Consequences

- JSON size and parse time are measured before considering a binary encoding.
- The checked-in minimal fixture and validator establish shape plus unique-ID and
  reference-integrity checks; they do not yet prove all kind-specific invariants.
- The [first extractor](../../../trick_source/codegen/TrickCodeGen/README.md) now
  produces this contract through owned JSON values with deterministic serialization.
  Its input digest is explicitly an evidence fingerprint, not the complete,
  relocatable production cache key described above.
- Extractor 0.2.0 adds owned typed nodes and structural identity for builtin,
  record, alias, pointer/reference, and array types, with kind-aware validation.
  Aliases retain declaration/underlying links and a fully desugared canonical link;
  arrays use one node per dimension and normalize qualification onto elements.
  Record redeclarations fold to a definition where available, otherwise to an
  incomplete canonical declaration. Tightening these meanings advances the facts
  schema to version 2, even though its field names remain unchanged. The synthetic
  minimal fixture is migrated, and the reader rejects v1 facts. This increment
  does not freeze the contract or complete fallback identity, namespace contexts,
  the multi-root file model, or the remaining type kinds.

## Review hardening: schema 3

Extractor 0.3.0 advances facts to v3 and diagnostics envelopes to v2. Files carry
an explicit named `root` and relative `portable` path; file identity hashes that
pair after symlink resolution. Source/resource roots are supplied by default,
additional sysroot/build/vendor roots are explicit, and unmapped physical inputs
fail extraction. Exact root locations remain in provenance, so the evidence
fingerprint is still machine-specific and is not a production cache key. OS and
target differences remain meaningful even with portable identity.

Arrays now carry one scalar `extent`, null when incomplete. Layout quantities and
extents are JSON numbers through `2^53-1` and canonical decimal strings above that
threshold; the schema and graph validator enforce this representation. This
policy also applies to future base offsets and bit widths. Enum/template integral
values remain decimal strings throughout their full ranges as already specified.
The extractor's owned extent storage supports 64 bits and rejects larger values.

Type `spelling` is explicitly a representative display value: the smallest
observed spelling under lexical ordering when structural types intern together.
It is neither per-use source spelling nor a lossless source reconstruction.
Per-use spelling requires a future use-site model if a consumer needs it.

The minimal fixture is migrated and older facts are rejected. This revision does
not freeze the wire contract or complete namespace/fallback identity.

## Declaration contexts: schema 4

Extractor 0.4.0 adds named/inline/nested/reopened/anonymous namespaces, namespace
aliases, unnamed records, and anonymous aggregate storage. Namespace nodes merge
canonical redeclarations and retain all block sources and annotations in
translation-unit order. Their sorted child IDs describe selected semantic
ownership, so closing an included namespace does not select its unused siblings.
Alias nodes retain the immediate namespace-or-alias target. Semantic and lexical
parent links remain distinct for out-of-line definitions.

Declarations state `identity_kind` (`usr` or `source`) separately from retained
nullable USR evidence. A source anchor contains rooted file/offset locations for
the declaration and its complete spelling and expansion chains. Intermediate
expansions and argument substitution sites prevent collisions when one macro uses
the same unnamed-record macro or type argument multiple times. Shared origin
subgraphs are memoized and hashed without emitting raw Clang location encodings.
Anonymous namespaces additionally salt their identity with the translation-unit
file ID; source identity propagates to descendants. Canonical AST pointers are
only local memoization/collision-check keys and never enter emitted identity.
Distinct canonical declarations with the same ID or an unrepresentable physical
anchor fail extraction without publishing a document.

This fallback is deterministic for unchanged rooted source trees, including
relocation and symlink aliases. It is not edit-stable: source motion, changes in
macro expansion sites, or a different canonical namespace block can change IDs.
Display names omit anonymous tag locations and retain inline namespace components;
they are descriptive rather than unique keys. Future overload/template identity
remains a separate extension, guarded by the current fail-closed kind checks.

Unnamed records have `anonymous: true`. Their implicit anonymous storage fields
have `anonymous_member: true`, an empty name, a source-based ID, and a record type
link to the nested unnamed declaration. Each physical field appears once; Clang's
implicit promoted lookup aliases do not add storage or duplicate offsets. A
consumer that flattens anonymous member paths must traverse these storage links.

The graph validator checks these relationships and rejects context/alias cycles.
The minimal fixture is migrated and v1/v2/v3 facts are rejected. The diagnostics
envelope stays at v2 because its wire shape did not change. This revision does not
complete enum, bitfield, inheritance, callable, or production selection policy.

## Enums and bitfields: schema 5

Extractor 0.5.0 adds enum type nodes, enum declaration dependencies, and bitfield
layout facts. Enums record `scoped`, `underlying_fixed`, `underlying_signed`,
`underlying_type_id`, size/alignment, and source-order enumerators. Enum declaration
identity and nested/context ownership follow the same rules as records. Enumerator
entries remain inline, with a name, exact value, source and raw annotations.

The provisional, previously unused enumerator `signed_value`/`unsigned_value`
pair is replaced by one `value`: a canonical decimal string representing the
mathematical value after conversion to the enum's underlying type. It is never a
JSON number, supports values wider than 64 bits, and is not a bit reinterpretation.
The validator checks signed/unsigned range against the recorded width, canonical
decimal syntax, unique names (duplicate values are legal), and source references.
Template-argument integral fields are unchanged.

Enum type completeness is separate from an enumerator definition. A fixed opaque
enum has known size/alignment and `complete: true` even with `definition: false`.
It has no enumerator list entries. Scoped enums always have fixed underlying types.
The selected definition, or canonical opaque declaration if none exists, supplies
source/annotation evidence; full enum redeclaration history remains future work.

Bitfields retain declared width and Clang's record-relative bit offset. The record
field list includes unnamed padding and zero-width alignment separators in source
order. They use empty names and source identities, with `anonymous_member: false`.
An overwide C++ bitfield may contain padding beyond its underlying type width;
the extractor does not clamp it. Widths must be concrete and fit Clang's unsigned
32-bit layout interface. Invalid/dependent input publishes no partial document.

Every bitfield states `field-address: unsupported / BITFIELD_NOT_ADDRESSABLE`.
These offsets do not license address-of/offsetof-based emission; named bitfields
will require generated get/set operations and GCC conformance probes. Zero-width
entries describe alignment, not addressable storage. This increment does not
implement accessor generation, inheritance, or callable extraction.

Facts advance to v5; v1/v2/v3/v4 documents are rejected and the minimal fixture is
migrated. The diagnostics envelope remains v2 because its shape is unchanged.

## Inheritance and subobject layout: schema 6

Extractor 0.6.0 adds non-template single, multiple, and virtual inheritance. A
record's `bases` are direct, source-ordered edges: `declaration_id` identifies the
canonical base record, while `type_id` retains a written typedef layer. Each edge
records its base-specifier source range, virtualness, effective `access`, and
`written_access`; `none` for the latter means the class/struct default was used.
Base records enter the selected dependency closure and must be complete, non-union
records. Unsupported members in that closure still reject the whole extraction.

Nonvirtual `offset_bits` is relative to the owning record subobject. Virtual edges
have null offsets because their target position depends on the most-derived type.
Every record instead has a sorted, unique `virtual_base_offsets` table with the
complete-object offsets of all its direct/indirect virtual bases. These positions
apply only when this record is the most-derived object, never when embedded as a
base subobject of another type. Virtual traversal must consult that most-derived
table, not add an intermediate record's complete-object virtual offset.

Shared virtual bases occur once in the table. Distinct nonvirtual subobjects of
the same type remain distinct graph paths, even if a virtual copy also exists.
Fields remain directly owned; inherited fields are not duplicated or assigned
flattened identities. The schema does not encode hidden vptr/vbptr slots or grant
permission for casts through inaccessible or ambiguous base paths.

`data_size_bits`, `non_virtual_size_bits`, and `non_virtual_alignment_bits` retain
Clang's record-layout quantities alongside complete-object size/alignment. Empty
base optimization and reusable tail padding mean complete-object base sizes cannot
be summed to validate member or subobject extents. Incomplete records have null
layout quantities and empty base tables. All quantities retain exact v3 encoding.

Validation checks canonical base types, default/written access, nonvirtual/virtual
offset scope, complete non-union targets, duplicate direct bases, and inheritance
cycles. A postorder graph traversal checks the exact transitive virtual-base set
without enumerating every diamond path. Source/type declaration cycles remain
independent of inheritance cycles.

A native-compiler fixture probe compares actual size, alignment, and public
base-path offsets, including repeated, shared, packed, empty, and tail-reusing
subobjects. CTest runs it with the configured host compiler, including GCC 8.5/12
CI lanes. This is focused evidence, not full GCC ABI/generated-operation parity.
Explicit callables, templates, generated accessors, and legacy metadata flattening
remain future work.

Facts advance to v6; v1/v2/v3/v4/v5 documents are rejected and the minimal fixture
is migrated. The diagnostics envelope remains v2.

## Explicit callables and special-member declaration state: schema 7

Extractor 0.7.0 emits non-template functions, methods, constructors, destructors,
conversions, and operators. Records own direct explicit callables through
source-ordered `callable_ids`, not `nested_declaration_ids`. Canonical declarations
merge redeclarations but never overloads. Constructors/operators/conversions have
semantic names without Clang identifiers; their USRs remain usable in named
contexts. Source-identified contexts retain physical-anchor fallback identity.
Translation-unit-local functions also require physical-anchor identity including
the translation-unit file ID. Linkage categories are retained explicitly; static
free-function declarations are not mistaken for external functions when a later
redeclaration omits `static`.

Each callable retains adjusted and original parameter types, return type (null for
constructors/destructors), variadicness, CV/ref/noexcept, static/virtual/pure/final,
explicit/constexpr, deleted/defaulted, and user-provided flags. The calling
convention is explicitly `c` (Clang `CC_C`, not C language linkage); other calling
conventions and special parameter/register ABI modes are rejected in this slice.
Function and member-pointer types and undeduced/deduced auto type layers remain
unsupported. Bodies are parsed by Clang but not serialized or traversed for IR
declaration selection. Signature types and overrides do enter the dependency closure.

`redeclarations` retains every observed occurrence in translation-unit order, with
its source, lexical context, parameters/defaults, annotations, and definition flag.
The latest declaration supplies the node's primary source and parameters; semantic
ownership remains canonical, including out-of-line definitions. Function annotations
are also aggregated. Defaults preserve a physical source range and a pretty-printed
expression string, not an evaluated value, expression graph, or round-trip source.
Consumers must not emit that string as generated code without further policy.

Direct virtual overrides link explicit declarations. An override of an implicit
destructor instead lists the base record in `overridden_implicit_destructor_record_ids`;
no synthetic source declaration or callable identity is invented. The validator
checks virtualness, ownership, base ancestry, parameter signatures, and CV/ref
consistency. Return covariance legality and overload resolution remain Clang's
responsibility, not reconstructed policy in the graph validator.

Sema forces declaration of implicit members in complete selected records and
evaluates implicit exception specifications. `special_members` contains six entries
in fixed order: default/copy/move constructors, copy/move assignment, destructor.
Each is `implicit`, `user_declared`, `suppressed`, or `unknown` for incomplete types.
User-declared entries link all matching explicit callable nodes. Only implicit
entries carry deletion, triviality, virtualness, and noexcept facts; other states
use null values. Unresolved noexcept remains `unknown`. These summaries do not
attempt full implicit signatures, access/overload resolution at a generated call
site, allocation/deletion policy, or binding lifetime decisions.

In particular, suppressed move declarations do not imply lack of move
constructibility (copying can bind an rvalue), nondeleted does not imply accessible,
and triviality flags do not override deletion. Native type-trait fixtures exercise
these distinctions in the GCC 8.5/12 and Linux/macOS host lanes. This is focused
conformance evidence, not the full generated-operation gate.

Facts advance to v7 and the minimal fixture is migrated; versions 1 through 6 are
rejected. The diagnostics envelope remains v2. Templates, friends, static data,
annotation policy, legacy emission, and production integration remain future work.

## Review hardening: schema 8

Extractor 0.8.0 introduces explicit `provenance.identity_version: 1`. Earlier
source-identity recipes were unversioned and included Clang's `getDeclKindName()`;
that internal display string is no longer an identity input. The owned kind tags
are `namespace`, `namespace-alias`, `record`, `enum`, `typedef`, `type-alias`,
`field`, `function`, `method`, `constructor`, `destructor`, and `conversion`.
Unsupported kinds diagnose rather than falling back to a frontend string.
The source-identity object now includes `version: 1` alongside kind, parent, name,
and the physical-anchor digest (and translation-unit salt when required). This
intentionally changes source-based IDs and structural IDs that depend on them.
USR-based IDs retain their existing recipe. Opaque IDs still make no persistence
promise across source edits or LLVM upgrades: USRs, canonical declarations, and
source/macro behavior remain frontend dependencies. A future cache must account
for schema, identity, extractor, and frontend versions, plus complete parse inputs.

Qualified declaration display names are composed from semantic context components,
using the same component when a declaration names itself or parents another node.
Inline namespaces are retained. Unnamed tags use their associated typedef name
when present, otherwise `(anonymous struct)`, `(anonymous class)`,
`(anonymous union)`, or `(anonymous enum)`; unnamed namespaces use
`(anonymous namespace)`. Storage fields and padding bitfields use
`(anonymous member)` and `(unnamed bitfield)`. The raw `name` remains empty for
unnamed declarations. Callable components retain constructor/destructor/operator
and conversion spellings. Display names are neither unique nor identity inputs:
two unnamed siblings may still have the same display name, and a typedef may share
its name with its underlying unnamed record. Ownership always follows IDs.

Known capabilities must agree with their prerequisites, and capability names are
unique per declaration. Bitfields require exactly
`field-address: unsupported / BITFIELD_NOT_ADDRESSABLE`; that reason cannot be
attached to a non-bitfield or another capability. A `frontend-record-layout`
capability belongs only to records and is required: complete records state
`supported / SUPPORTED`, incomplete records `unknown / INCOMPLETE_TYPE`.
Other field-address decisions and future capability names are not inferred here.
Request failures do not insert empty IDs into reference collections; null virtual
base targets diagnose, and collecting other independent errors continues.

`provenance.graph_digest_version: 1` and `provenance.graph_digest` introduce a
second SHA-256 fingerprint. Its input is the following exact projection:

- `schema_version`, `identity_version`, and `graph_digest_version`;
- `files`, sorted by ID, with only each `path.spelled` and `path.real` removed;
- `types` and `declarations`, each sorted by ID, with every fact retained.

Root names, portable paths, file-content digests, includes, source anchors, display
strings, annotations, and all ordered semantic arrays are retained. No provenance
object or diagnostics enter this projection. Canonical JSON uses recursively
sorted object keys, compact separators, UTF-8 without ASCII escaping or Unicode
normalization, decimal integers, and lowercase `\u00xx` for control characters
other than the short escapes `\b`, `\f`, `\n`, `\r`, and `\t`. Quote and backslash
are escaped; slash is not. There is no trailing newline in the hashed bytes.
The Python validator independently reconstructs the projection and rejects a
stale digest, unknown version, or missing version. The exact-evidence
`input_digest` remains separate and includes the graph fingerprint before hashing
the document with only `input_digest` itself absent.

This is normalized **output equivalence**, not a semantic-only hash or production
cache key. Identical rooted inputs/facts can compare equal after source, vendor,
and resource-directory relocation; path strings embedded in actual annotations,
include spellings, or default arguments are not blindly rewritten. Source-byte
changes (including comments) change the fingerprint. Target/frontend/invocation
provenance must still be considered separately: Linux and macOS graphs can differ
legitimately, and equality does not prove ABI compatibility or that all parse
inputs have been captured. There is no unconditional cross-lane equality gate.

The LLVM 17–23 adapter matrix adds a **controlled** equality gate for the eight
checked-in extractor fixtures: compare every major against LLVM 17 separately
on Linux and macOS, with matching target triples and C++17. Each input is fully
validated before its graph digest is compared; no display or semantic fields are
removed. The gate fails for missing versions or artifacts and records exact
frontend versions. This establishes regression evidence for that fixture set,
not a cross-target ABI promise or a frontend-independent cache identity.

Facts advance to v8; versions 1 through 7 are rejected. The synthetic fixture is
migrated and includes a real graph fingerprint, while its input/file evidence
digests remain explicitly synthetic. The diagnostics envelope remains v2.


## Class-template signatures and concrete specializations: schema 9

Extractor 0.9.0 adds `class_template` declarations for primary templates and
partial-specialization patterns. `template_kind` distinguishes `primary` and
`partial_specialization`; `record_tag` and `definition` describe the pattern.
Each source-ordered `template_parameters` entry contains:

- `kind` (`type`, `non_type`, or `template`), name, pack flag, depth/index, and source;
- nested `parameters` for template-template parameters, empty otherwise;
- `type_spelling` and `type_dependent` for non-type parameters, null otherwise;
- paired `default_spelling` and `default_source`, null when absent, including
  inherited defaults when Clang exposes them on the selected declaration.

The selected definition (or most recent forward declaration) supplies signature
metadata. Full template redeclaration history is not retained. Raw comments on the
template declaration and annotations on its templated record are retained once.
Partial patterns link `primary_template_id` and descriptive `pattern_spelling`;
primary patterns have null values for both. Pattern parameter/default spellings
are diagnostic evidence, not structured dependent types or backend source.

Every pattern carries exactly `template-pattern: unknown /
DEPENDENT_TEMPLATE_PATTERN`. Dependent bodies are deliberately not traversed and
patterns have no record type, fields, callables, traits, or layout. A definition
flag does not mean its body was modeled or that any requested instantiation is
valid. A future dependent graph must introduce a reviewed schema extension.

Concrete class-template specializations remain ordinary structural record types
and `record` declarations with additional fields:

| Field | Meaning |
|---|---|
| `specialization_kind` | `undeclared`, `implicit_instantiation`, `explicit_specialization`, `explicit_instantiation_declaration`, or `explicit_instantiation_definition` |
| `primary_template_id` | Primary class-template declaration |
| `template_arguments` | Canonical semantic arguments to the primary, including defaults and pack slots |
| `instantiation_pattern_id` | Selected primary or partial pattern for an instantiation; null for explicit specializations or uninstantiated references |
| `instantiation_arguments` | Deduced arguments bound to the selected pattern's parameters; null with no selected pattern |
| `point_of_instantiation` | Physical source evidence when Clang provides a valid point, otherwise null |

Instantiation arguments for a primary equal its specialization arguments. A
partial can have a different parameter list and deduced arguments; both lists
are retained, rather than assuming primary arguments describe the partial's
binding. The validator checks relationships and parameter slot/kind agreement;
it does not reimplement deduction or prove that a partial pattern matches.
Pointer-only references can remain `undeclared` and incomplete. No eager Sema
instantiation of every class or method is requested. Explicit directives in the
main file are selected even when the primary comes from a dependency header.
Referenced headers contribute only the selected dependency closure.

Argument nodes use these exclusive shapes:

| Kind | Additional fields |
|---|---|
| `type` | canonical `type_id` |
| `integral` | canonical `type_id`, decimal-string `value`, `bit_width` (1–128), `signed` |
| `null_pointer` | canonical pointer or `std::nullptr_t` `type_id` |
| `template` | `declaration_id` of a primary class template |
| `pack` | ordered `elements` of the preceding concrete argument kinds |

A pack is one signature slot, including when empty; concrete nested packs are not
part of this contract. Arguments come from Clang's semantic API, never splitting
display strings. Integral values include enum, bool, and deduced `auto` arguments
and preserve the exact post-conversion value. Validation checks recorded range,
known builtin signedness, enum width/signedness, and bool's one-bit range. It does
not infer all target builtin widths or compare spelled non-type parameter types
to deduced argument types. Alias sugar canonicalizes in arguments; ordinary
field/alias facts retain their existing structural alias representation.

Owned source-identity version 1 is extended with `class-template`,
`class-template-partial`, and `class-template-specialization` kind tags. Concrete
specializations always use source identity, adding a `specialization` object
containing `primary_template_id` and canonical `arguments` to the existing hash
input. This distinguishes instantiated members sharing pattern source locations;
source identity propagates to them. Existing supported declaration kinds retain
their identity recipe. Frontend USRs are still retained as evidence, and IDs are
not promised stable across revisions or LLVM versions. Display names include
semantic template arguments, without becoming identity keys.

Concrete instances reuse record/base/bitfield/callable/special-member extraction.
Nested selected instances omitted from Clang's lexical member iterator are
appended by ID after source-ordered `nested_declaration_ids`. Existing explicit
members are not duplicated. Function/alias templates, declaration-valued and
function/member-pointer arguments, dependent expression/expansion arguments,
uninstantiated method defaults, and dependent pattern bodies/types remain outside
this slice. Encountering unsupported facts in a selected concrete graph fails
without publishing a partial document.

The `templates.hh` fixture and native size/alignment/standard-layout offset probe
run with the existing six extractor CI lanes, including GCC 8.5/12. Regression
coverage includes partial deduction, empty and recursive packs, defaults,
explicit specialization/instantiation, nested and anonymous instance identity,
relocation, and validator mutations. This is focused frontend/layout evidence,
not legacy emission or general generated-operation conformance.

Facts advance to v9 and versions 1 through 8 are rejected. The synthetic fixture
is migrated. Identity and graph-digest recipe versions remain 1; the graph digest
already includes the facts schema version and all new graph facts. Diagnostics
remain v2. Production ICG integration and remaining Phase 0 gates are unchanged.

## Linkage, encoding, and callable defaults: schema 10

Extractor 0.10.0 treats `LinkageSpecDecl` as a transparent selection and context
wrapper. Global and namespace-scoped declarations inside `extern "C"` blocks are
selected exactly as siblings outside the block; no linkage-block declaration node
or artificial ownership edge is emitted. This matches the legacy visitor and
allows direct extraction of Trick's `#ifdef __cplusplus` C-interface headers.

Every callable has `language_linkage: "c" | "c++" | "none"`, copied from
Clang's semantic language linkage. `none` is retained for internal and other names
for which Clang reports no language linkage. Member callables can therefore be
`c++` or `none`, but never `c`. This field is independent of `linkage` (symbol visibility across
translation units) and `calling_convention` (the ABI function calling convention).
The current extractor still accepts only Clang `CC_C`; that value does not imply
that a C++ function has C language linkage. The legacy backend's generated
`init_attr*_c_intf` wrappers remain unconditionally C-linked output and are not
evidence about the input declaration's language linkage.

Callable parameters retain the effective `has_default`, `default_spelling`, and
`default_source` at each declaration occurrence. New `default_origin` is `written`
when that occurrence contains the default, `inherited` when Clang propagates an
earlier occurrence's default, and null when there is no effective default. The
validator requires paired evidence, at most one written default per parameter,
identical inherited evidence, and no disappearance later in the redeclaration
chain. The canonical callable continues to use its last redeclaration's effective
parameter view. These remain frontend facts rather than round-trip source.

`deleted` and `defaulted` are intentionally independent: a defaulted special
member can be implicitly defined as deleted. Schema validation preserves this
legal and policy-relevant state. Likewise, an empty override list is not rejected:
a newly introduced virtual method legitimately overrides nothing, and proving a
missing edge would require C++ override resolution outside this graph validator.
Real extraction tests instead assert known override relationships.

Raw comment and `clang::annotate` payloads are checked with LLVM's strict UTF-8
validator before construction of a JSON value. Invalid bytes produce
`ICG_INVALID_ENCODING`, retain physical source evidence, and suppress facts
publication. No U+FFFD replacement enters the graph. File SHA-256 facts continue
to cover the original bytes. This slice does not claim that every filesystem path
or frontend-generated display string has an independently selected source encoding.

The new `linkage.hh` fixture covers global and namespaced C blocks alongside C++
controls. Integration also extracts the checked-in `include/trick/simtime_proto.h`
and closes its `GMTTIME` dependency. A Latin-1 comment payload probe verifies
failure with empty stdout; attribute payloads pass through the same guard after
Clang's string-literal validation. Facts advance to v10 and versions 1 through 9
are rejected. Identity, graph-digest, and diagnostics versions remain unchanged.
