# Builtin pointer conformance

Policy v14 / emitter v13 admit one unqualified pointer indirection to each of the
15 supported builtin types in ordinary records, plus aliases and fixed arrays
of those pointers. The corpus preserves six exact legacy captures: cold, warm
and forced for the pointer model and for a separate rejected reference model.
Production ICG and earlier reference snapshots are unchanged.

`PointerModel` has 18 field rows: 15 distinct builtin pointers, an `int*` alias,
a two-by-two pointer matrix and an adjacent integer. Independently audited offsets,
pointee names/sizes, I/O, units and shapes must agree with facts, compiled legacy,
compiled candidate and native member layout. The probe measures eight-byte pointer
storage separately from `ATTRIBUTES.size`, which is the builtin pointee size.
The final active INDEX has extent zero; positive outer array dimensions precede it.
One pointer consumes one of the eight indices, allowing up to seven outer dimensions.

The runtime gate links the real configured MemoryManager and registers the native
record and 15 separately named target arrays. Compact and expanded checkpoints
must be byte-identical across generators. Every target value and every pointer
is changed before readback, including null, shared, interior-array and in-record
addresses. Its two passes audit all 18 rows and all 45 target elements.

| Pointee types | Captured checkpoint behavior |
| --- | --- |
| `bool`, `unsigned char`, `short`, `unsigned short`, `int`, `unsigned int`, `long`, `unsigned long`, `long long`, `unsigned long long`, `float`, `double`, `char16_t` | Named target addresses and null pointers round trip with alias and interior address identity |
| `char`, `signed char` | `TRICK_CHARACTER` checkpoints string contents and restores new string storage; address/alias identity is not preserved |

The string behavior is deliberate legacy parity, including `signed char*`.
This does not characterize arbitrary nonterminated character buffers or ownership.
`char16_t` retains legacy's unsigned-short metadata and target interpretation;
no Unicode validation is implied. Plain `char` retains the signed-char ABI guard.

Seven compiled metadata mutations change pointee size, pointer extent/rank,
offset, pointee kind, array shape and UnitsMap key value. Each must reach execution
or field comparison, so compile errors/timeouts cannot count as success. Five
runtime controls disable scalar/array pointer checkpoint I/O, omit restore,
corrupt a shared/interior alias and corrupt a restored null. All must reach the
specific failed readback assertion.

`ReferenceModel` is characterization only: legacy emits two rows with I/O 3,
modifier 65 (reference plus eight-byte reference storage), no pointer index and
builtin pointee size. Its generated allocation helper tries to default-construct
a record with uninitialized reference members and cannot compile. The extractor
can describe it, but the rewrite rejects reference fields before output; this
capture is not a claim of usable legacy reference lifecycle behavior.

Record pointers, multiple indirection, pointer-to-array/function, qualifiers,
references, template pointer fields and pointer lifecycle remain outside the profile.
Enum pointers are covered by the separate [enum pointer corpus](../enum_pointers/README.md).
Metadata neither allocates nor owns the targets. Managed allocation/resize/deletion,
SWIG ownership, variable-server traffic and executive restart remain separate work.

```sh
python tools/icg_baseline/legacy.py --build-dir build/legacy-baseline \
  --manifest tools/icg_baseline/pointers/corpus.json \
  --udunits-xml /usr/share/xml/udunits/udunits2.xml \
  --output build/pointer-reference-evidence \
  --reference tools/icg_baseline/pointers/reference
python tools/icg_baseline/pointer_metadata.py \
  --extractor build/icg-extract/trick-icg-extract --compiler g++ \
  --output build/pointer-metadata
# Requires a configured Trick tree with real runtime archives.
python tools/icg_baseline/pointer_runtime.py \
  --extractor build/icg-extract/trick-icg-extract --compiler g++ \
  --output build/pointer-runtime
```

Use `--trick-root /path/to/configured/trick` when the runtime archives are in a
separate checkout. Evidence includes commands, compiler/runtime logs, facts,
resolved decisions, candidate source, native observations, checkpoints and the
negative-control outcomes. CTest runs the metadata gate on each compiler lane;
CI separately reproduces references and runs the configured checkpoint gate.
