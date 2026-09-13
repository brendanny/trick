# ICG-003: Require migration for legacy wchar_t metadata

- Status: Accepted for the bounded rewrite backend; production adoption requires the migration gate below
- Date: 2026-09-13
- Scope: Legacy-compatible metadata generation and its production replacement criteria

## Context

Legacy ICG successfully emits `wchar_t` scalar and fixed-array fields as
`TRICK_WCHAR`, with native size and offsets. The rewrite currently rejects these
required fields with `ICG_POLICY_TYPE`. This is a deliberate compatibility
divergence, not an uncharacterized coverage gap: a model header accepted by the
production generator can fail under the rewrite.

The [character corpus](../../../tools/icg_baseline/characters/README.md) preserves
the actual legacy metadata and independently executes its runtime behavior. On
the audited Linux target, assigning `20013` through MemoryManager stores `45`;
scalar checkpoint output also writes `A` without quotes. These findings do not
mean that every wide-character operation fails. In particular, existing models
may rely on the current subset of behavior, including truncation.

`char32_t` is a different case: legacy omits the captured fields entirely. The
rewrite rejects rather than producing an apparently successful empty table. That
does not remove functioning legacy metadata for those fields.

## Decision

Keep the explicit `wchar_t` rejection in the rewrite. Do not reproduce lossy
`TRICK_WCHAR` assignment as a compatibility mode, silently omit the fields, or
automatically reinterpret them as another character type. A required `wchar_t`
field fails the complete generation request before candidate source publication.
The existing explicit zero-I/O omission rule still applies.

Treat this as a documented behavior change when considering production adoption.
Affected simulations must make an explicit migration decision before switching
generators; the current development backend is not a drop-in replacement for
their headers. Production ICG and MemoryManager behavior remain unchanged by
this decision.

## Migration and adoption gate

Before enabling the rewrite for a simulation containing `wchar_t` fields:

1. Inventory the fields and their actual uses: numeric values, code units, native
   wide strings, Python/variable input, and checkpoint dependencies.
2. Choose a supported representation based on those semantics. `char16_t` is
   appropriate only for explicitly 16-bit code units; it is not a lossless generic
   replacement for native `wchar_t`. Numeric storage requires explicit conversions
   and range checks. Native wide-string behavior needs a separately designed API.
3. Validate bindings, assignments and old/new checkpoint migration with native
   values covering the simulation's range. A type-name substitution alone does
   not establish compatibility.

Do not promote the rewrite for an affected simulation until these checks pass.
Alternatively, a separately reviewed runtime repair may justify reconsidering
this decision once legacy/new/native value preservation and checkpoint compatibility
are characterized. No automatic migration or wide-character runtime repair is
implemented by the current backend.

## Alternatives and consequences

Reproducing the lossy legacy mapping would retain generated rows and existing
behavior, but would knowingly admit value-changing assignment and still would
not establish complete checkpoint readback. Requiring migration makes the
incompatibility visible before generating a partial replacement.

The immutable wide-character snapshots and legacy-only runtime probes remain
evidence. Successful extraction of `wchar_t` facts does not authorize emission.
The rejection is tracked separately from uncharacterized types such as `long double`
and pointer/reference storage; adding their coverage does not resolve this decision.
