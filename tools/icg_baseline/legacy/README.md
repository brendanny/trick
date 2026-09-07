# Isolated legacy ICG reference evidence

These are actual outputs of the unchanged legacy `Interface_Code_Gen`, not
hand-authored expected C++ and not output from `trick-icg-extract`.
See [reproduction commands and limitations](../README.md#reproduce-the-isolated-legacy-header-evidence).
The build is deliberately separate from Trick's production build.

## Reference scope

The initial capture used the implementation and input files at
`8a994204f193e193af9781d87de23f28d8389da3`, Ubuntu 24.04 x86-64, GCC 13.3,
LLVM 17.0.6, UDUNITS 2.2.28, and C++17. Exact source/XML/binary fingerprints and
package versions are in `reference/provenance.json`. Only evidence tooling was
locally changed. Each TU includes an existing regression header from `corpus.json`.

| Case | Captured artifacts per pass | Observed legacy output |
|---|---:|---|
| anonymous-enum | 11 | `attrStarter`, construction/destruction wrappers and registry; the unnamed class enum has no separate `ENUM_ATTR` table |
| deleted-constructor | 11 | `attrEmpty`; allocation uses `calloc` but does not invoke the deleted constructor |
| embedded | 11 | Public nested classes/enums, bitfield metadata, `r` converted to `rad`; ignored types and private nested declarations excluded |
| templates | 12 | Two `io_*.cpp` files; concrete nested templates, array dimensions, enum fields and I/O-excluded pointer fields |

There are 12 snapshots (three per case), including five distinct metadata source
files per pass across the corpus. They also cover registry declarations, Make
dependencies/link lists, processed/policy lists, and `classes.resource`.
Anonymous enum omission and constructor allocation are recorded compatibility
observations, not declarations that those policies are desirable.

## Cold, warm, and forced behavior

All four warm snapshots equal their cold snapshots. This is **content equality**,
not zero file churn: reports separately record byte-identical rewrites.
On a forced run, every artifact except `classes.resource` has equal normalized
content; the SIE file contains two copies of its cold contents. The legacy SIE
printers open the resource in append mode, and this isolated invocation performs
no enclosing Make-target cleanup. Do not generalize this observation to
`make force_ICG` or `trick-CP` without measuring their surrounding steps.

These differences are preserved in separate `cold.json`, `warm.json`, and
`forced.json` references. The content-addressed objects in each case directory
are shared between these snapshots. Do not reformat them or remove trailing
whitespace/newlines: those bytes are evidence and are digest-checked.

## Review and update procedure

Run the collector against these references in a fresh output directory. Review
all reference diffs and raw diagnostics before accepting any update. Never
refresh references automatically in CI. If a deliberate legacy change requires
new references, copy each pass's snapshot into its case directory and copy its
referenced objects byte-for-byte into that directory's `objects/`; update the
provenance and explain the changed behavior. Keep scope labels and package data.

The Linux CI lane rebuilds the real legacy binary and checks all 12 references,
uploading successful and failed captures, raw logs, and the package inventory.
The four Linux/macOS harness lanes verify the reference sidecars without claiming
that the legacy generator was built or validated on all those platforms.

No full simulation, generated-source compile/link, runtime, Python, or performance
gate is closed by this header-only increment. The next evidence step is a
configured focused simulation capture plus generated-code/runtime observations,
before broadening to medium and large/old models.
