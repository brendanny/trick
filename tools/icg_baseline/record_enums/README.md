# Ordinary enum field conformance

This corpus characterizes ordinary record fields using named, nonempty enums
backed by 32-bit `int` or `unsigned int`. It covers scoped/unscoped enums, scalar
and array aliases, mixed builtin fields, matrices and namespace-qualified names.
The fixture, corpus manifest and three content-addressed legacy snapshots are
fingerprinted. The production legacy generator is unchanged.

| Evidence | Coverage |
| --- | --- |
| Records | `EnumRecord`, `record_enum::Aliases` |
| Field rows | 10: eight enum rows plus `int` and `double` |
| Native storage | 16 enum elements and two neighboring builtin values |
| Enum tables | Three tables, eight enumerator rows, including a duplicate value |
| Legacy captures | Cold, warm and forced; forced appends `classes.resource` as before |
| Metadata controls | Seven mutations rejected at their required link/run/comparison stage |
| Runtime controls | Size truncation, disabled array checkpoint output and omitted restore |
| Checkpoints | Compact and expanded arrays; full readback and exact output bytes |

`record_enum_metadata.py` declares expected offsets, dimensions, names, annotations
and enum rows independently of the generation policy. It compiles both immutable
legacy source and generated candidate at `-Werror`, links actual Trick archives,
and executes both through the real MemoryManager. The native probe measures layout
and verifies exact enum table pointers, initial zero size/null pointers, guarded
repeat initialization, C-linkage entry points and UnitsMap values.

Ordinary enum rows preserve namespace separators in `type_name`, while exported
table/size names replace them with underscores. Array aliases expand to canonical
enum names and ordered dimensions. Rows begin with size zero and a null metadata
pointer; guarded `add_attr_info` calls resolve the enum exports through MemoryManager.
UnitsMap keys continue to omit namespaces from enclosing record names.

The runtime probe registers two native records and independently checks all eight
enumerator lookups. Each checkpoint includes symbolic names, duplicate-valued
enumerators (written with their first label), and numeric fallback for unnamed
values. Every field is overwritten before restoration and compared by native
typed value afterward. Both generators must produce identical checkpoint bytes
and observations. The three behavioral mutations must reach the specific failed
readback assertion; compile failures and timeouts cannot satisfy these controls.
The seven metadata controls separately target omitted registration, premature
size initialization, wrong enum table pointers, missing initialization guards,
missing size exports, changed labels and incorrect unsigned modifier bits.

The policy accepts only enum definitions included by the explicit file selection
and ignore/exclusion rules. Disabled fields are omitted before dependency checks.
Conflicting checkpoint labels fail before generation. Public and exact init-friend
access assertions remain distinct from numeric private-field metadata.
Record-nested enum definitions, inline/anonymous namespace scopes, empty/opaque
enums, qualifiers, pointers/references, enum bitfields, other underlying widths
and enum lifecycle output remain outside this storage extension. Standalone enum
table generation retains its broader previously characterized profile.

Reproduce the immutable references using the standalone legacy build:

```sh
python tools/icg_baseline/legacy.py \
  --build-dir build/legacy-baseline \
  --manifest tools/icg_baseline/record_enums/corpus.json \
  --udunits-xml /usr/share/xml/udunits/udunits2.xml \
  --output build/record-enum-reference-evidence \
  --reference tools/icg_baseline/record_enums/reference
```

Run portable compiler/policy tests with an actual extractor and compiler:

```sh
python tools/icg_emit/test_emit.py \
  --extractor build/icg-extract/trick-icg-extract --compiler /usr/bin/g++ \
  -k record_enum -v
```

After configuring/building Trick as in the configured simulation workflow:

```sh
python tools/icg_baseline/record_enum_runtime.py \
  --extractor build/icg-extract/trick-icg-extract --compiler g++ \
  --root . --output build/record-enum-runtime
```

The runtime command includes the metadata gate and all ten mutation controls.
`comparison.json` is written only after every comparison and required rejection
succeeds. CI reproduces the three references, compiles both sources on the
extractor matrix, and runs the real MemoryManager gate in the configured lane.
