# Bounded legacy metadata emitter

This standalone development backend consumes **facts v12, resolved policy v3,
and the caller's explicit request**. It generates C++ metadata against the
existing Trick ABI. It is not a production `trick-ICG` replacement.

```sh
python tools/icg_policy/resolve.py facts.json --request request.json > resolved.json
python tools/icg_emit/emit.py facts.json --request request.json \
  --resolved resolved.json --output build/candidate.cpp
```

Create the request with `tools.icg_policy.resolve.request_for(facts)` as described
in the [policy documentation](../icg_policy/README.md). Old policy v1/v2 documents
must be resolved again; relabeling their version is not a migration.

## Generated contract

- C-linkage `ATTRIBUTES` and `ENUM_ATTR` tables and complete sentinels.
- Source-order fields and enumerators, numeric offsets, legacy 32-bit unsigned
  bitfield storage, scalar sizes, units, I/O, modifier bits, and descriptions.
- Namespace-correct C++ initialization functions, global C-interface wrappers,
  and `io_src_sizeof_*` entry points. Initializers are repeatable.
- UnitsMap registration through the real implementation, matching legacy keys.
- Compile-time ABI, record/enum size/alignment, enum signedness and value checks. Public
  scalar offsets/types and those with exact init-function friendship are checked
  inside that function using actual C++ member-access expressions.

Every include/omit and access decision comes from the validated policy model;
the emitter has no fixture-name exclusion list. It replays policy validation and
checks each observed source file's digest before rendering. Numeric private-field
metadata does not itself need member access. An init-function friend grants no
lifecycle, STL, registry, or binding permission.

Emitter v2 supports standard-layout records in the bounded scalar policy and
scoped/unscoped enum values representable by `ENUM_ATTR.int` that agree with
legacy's signed integer conversion. Enum labels, C++ names, values, order and
modifier bits come from explicit policy decisions; the emitter does not derive
them again. Its target profile is
little-endian LP64 x86-64/AArch64 Linux or macOS, with eight-bit bytes, 32-bit int,
and 64-bit double. Bitfields must fit a complete in-object 32-bit storage unit.
Non-standard-layout records, wider enum values, unsigned narrow values that legacy
sign-extends incorrectly, unsafe packed
bitfields, conflicting init-function signatures, and empty selections are explicit
errors. These emitter limits are
narrower than successful fact extraction or policy resolution.

Output includes the original translation-unit header and embeds the emitter
version and policy/input digests. Compile it with the model's matching target and
preprocessing configuration. Compile-time checks provide additional guards; this
is not automatic compile-command replay or proof of arbitrary conditional-header
equivalence. Real source paths are currently required.

No lifecycle/STL helpers, registries, SIE, make/link files, bindings, cache, or
production build integration are emitted. A successful metadata-only file does
not satisfy a full per-header ICG generation request.

## Failure and incremental behavior

The complete source is validated and rendered before publication. The writer
uses a temporary sibling and atomic replacement, retaining the existing inode and
mtime when bytes are unchanged. Errors produce stderr, a nonzero exit, and no
stdout or new candidate. An earlier successful output is left untouched on
failure; callers must honor the exit status. Input-file and symlink output targets
are refused. This is one-file atomic output, not a build cache or multiprocess
generation scheduler.

## Independent evidence

```sh
python tools/icg_baseline/differential.py \
  --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --output build/emitter-evidence
python tools/icg_baseline/enum_metadata.py \
  --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --output build/enum-evidence
ctest --test-dir build/icg-extract --output-on-failure
```

The differential runner keeps immutable captured legacy sources and compiles
candidate sources in separate executables. It compares both against the existing
independent native layout/enum probes: six record tables/sizes, six fields, two
enum tables, sentinels, UnitsMap values, and entry-point results. A separate
translation unit references C-linkage tables, wrappers, and size functions, so a
same-translation-unit call cannot conceal missing C symbols. Commands, source,
compiler/dependency hashes, raw output, and observations are retained. A success
report is published only after all requested cases compare successfully.

The separate [enum corpus](../icg_baseline/enums/README.md) adds ten tables and
19 enumerators, including scoped enums, aliases, an empty enum, global/inline
namespace/record scopes and signed/unsigned underlying types. Legacy labels omit
the enum's own scope, retained with a policy diagnostic. Separate rejection
evidence compiles legacy unsigned-char/short values against native C++ and requires
policy to reject their sign-extension mismatch without publishing a candidate.
On Clang, only the legacy lane relaxes the `-Werror` promotion for
`-Winline-namespace-reopened-noninline`; the original source and warning are
retained. The candidate lane keeps full warnings-as-errors.

`icg_emit_integration` is part of the existing LLVM 17–23 Linux/macOS and GCC
8.5/12 CTest lanes. It also compiles all I/O combinations, unit aliases and `--`
modifiers, escaped descriptions, and an actual `TRICK_ICG` friend macro in global
and inline-namespace scopes. Removing the exact friendship makes the generated
member-access expression fail compilation; wrong-name and wrong-overload friends
do not authorize it. Mutated offsets, bitfield widths, enum values, units, I/O,
modifiers, enum labels/aliases/order, omitted fields/tables/entry points, incorrect
C++ linkage, and sentinels must
fail. Rehashed policy
mutations, changed source files, unsupported requests, and incremental writes
are tested independently of the emitter's expected output text.

General annotations, inheritance, template/STL emission, and
generated lifecycle/MemoryManager integration remain subsequent milestones.
