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
current facts schema is version 6; the independent diagnostics envelope is v2.

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
