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
`schema_version`. JSON Schema draft 2020-12 defines the wire shape. Version 1 is
strict: unknown properties and dangling graph references fail validation.

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
After version 1 freezes, compatible optional additions require an explicitly
revised schema and reader review; silently ignoring unknown properties is not a
compatibility strategy.

## Consequences

- JSON size and parse time are measured before considering a binary encoding.
- The checked-in minimal fixture and validator establish shape plus unique-ID and
  reference-integrity checks; they do not yet prove all kind-specific invariants.
- The [first extractor](../../../trick_source/codegen/TrickCodeGen/README.md) now
  produces this contract through owned JSON values with deterministic serialization.
  Its input digest is explicitly an evidence fingerprint, not the complete,
  relocatable production cache key described above. Typed nodes, kind-specific
  invariants, and structural/fallback identity grow with the next slice.
