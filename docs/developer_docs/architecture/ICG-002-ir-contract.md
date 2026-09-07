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
current facts schema is version 2; the independent diagnostics envelope is v1.

The document contains frontend facts only:

- exact invocation/target/tool provenance and input digest;
- stable file, type, and declaration IDs;
- spelled, real, and portable paths plus spelling/expansion locations;
- a graph of structured types and declarations, including template packs;
- raw annotations, frontend capabilities with reason codes, and diagnostics.

Python normalization will produce a separate resolved codegen model. Selection,
legacy-printability decisions, output directories, Make formatting, and binding
library types do not enter extracted facts.

Within a document, Clang USRs are preferred declaration identity when present.
The extractor derives deterministic fallback IDs from declaration kind, semantic
parent identity, portable spelling location, and overload/type identity. Types use
structural IDs and references. IDs are opaque to consumers; consumers must not
parse them for semantics.

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
