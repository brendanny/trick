# Character storage evidence

This separate corpus characterizes three C++ character types against the unchanged
legacy generator. **Only `char16_t` enters the emitted profile.** It represents
16-bit code units, with numeric unsigned-short checkpoint behavior. This does not
add Unicode validation, transcoding, string-pointer handling, or wide-character
locale support.

| C++ type | Actual legacy metadata | Generation decision |
|---|---|---|
| `char16_t` | `TRICK_UNSIGNED_SHORT`, spelling `char16_t`, size 2 | Supported for unqualified scalar fields, fixed arrays and aliases |
| `wchar_t` | `TRICK_WCHAR`, spelling `wchar_t`, size 4 on the audited target | Deliberate compatibility divergence: reject with `ICG_POLICY_TYPE` and require migration; legacy runtime assignment truncates |
| `char32_t` | Both fields omitted; the record table contains only its sentinel | Reject with `ICG_POLICY_TYPE`; omitted storage cannot preserve checkpoint values |

Policy v11 / emitter v10 now support 15 scalar bases. Facts remain v12. The
generated ABI guard requires an unsigned 16-bit `char16_t` with the same size and
alignment as `unsigned short`, within the existing little-endian LP64 profile.
Qualifiers, pointer/reference fields and char16_t bitfields remain rejected.

## Independent metadata evidence

Three fixtures have nine immutable cold/warm/forced snapshots. Each retains
legacy metadata, registries, SIE, and build artifacts. Cold and warm agree;
forced generation preserves the observed duplicate `classes.resource` append.
Manifest, fixture, compiler, binary and UDUNITS fingerprints appear in
`reference/provenance.json`. Earlier fixtures and reference bytes are untouched.

`character_metadata.py` compares two UTF-16 records / seven fields, including a
matrix and array aliases, against manually audited spelling, offsets, dimensions
and descriptions. Legacy and candidate sources compile at `-Werror` and execute
separately against real Trick headers and UnitsMap. Both must agree with extracted
facts and native layout. Six compiled mutations cover signedness, narrowing,
element size, type spelling, dimension order and description text.

The rejected fixtures still undergo extraction and independent field/type/layout
checks. Their actual legacy tables compile and execute: two wide-character rows,
zero UTF-32 rows. Policy must reject each with the named diagnostic. The independent
native observer understands `TRICK_WCHAR`; the generation policy does not admit it.
Every compiler lane also checks UTF-16 template tables and lifecycle construction;
the live legacy template gate checks cached first-use naming for `Box<char16_t>`.

## Real MemoryManager evidence

`character_runtime.py` links separate legacy and candidate programs against actual
configured Trick archives. Both register native external records, assign all seven
fields, checkpoint, change every code unit, and restore. Compact and expanded array
passes exercise embedded zeros, non-ASCII values, `32767`/`32768`, `65535`, surrogate
pairs and isolated surrogate code units. No validity assumption discards code units.
Every restored element and the complete checkpoint bytes must agree.

Three controls narrow a code unit to an unsigned byte, disable checkpoint I/O, or
omit restoration. Each must compile, reach execution and report a value mismatch;
compile/link errors, unrelated failures and timeouts do not satisfy the control.
The probe explicitly selects the C locale and all checkpoint formatting options.

Separate **legacy-only** runtime probes explain the rejection boundary on the
configured Linux target. Assigning `20013` to a `wchar_t` through MemoryManager
stores `45`; checkpoint output writes scalar `A` without quotes. A UTF-32 record
retains its native initial values but contributes no field assignments to the
checkpoint. The probe does not attempt to restore that comments-only checkpoint.
These observations do not claim that every possible wide-character operation
fails. `wchar_t` has functioning-if-lossy legacy metadata, so rejecting it is a
deliberate behavior change, distinct from missing type coverage. The accepted
[compatibility decision](../../../docs/developer_docs/architecture/ICG-003-wide-character-compatibility.md)
requires explicit simulation migration before production replacement; the rewrite
will not reproduce truncation or silently substitute another type. `char32_t`
instead lacks legacy field metadata in the captured case.

Successful reports appear only after the positive comparison, required runtime
mutations, and both rejection checks pass. Sources, compile/link/run commands,
archive fingerprints, observations, checkpoints and failure logs are retained.
The configured Linux/LLVM 17/GCC 13 workflow runs the real runtime gate; portable
compiler lanes run the metadata and policy tests.

## Reproduce

Build the isolated legacy generator using [legacy/README.md](../legacy/README.md):

```sh
python tools/icg_baseline/legacy.py \
  --build-dir build/legacy-baseline \
  --manifest tools/icg_baseline/characters/corpus.json \
  --udunits-xml /usr/share/xml/udunits/udunits2.xml \
  --output build/character-reference-evidence \
  --reference tools/icg_baseline/characters/reference
python tools/icg_baseline/character_metadata.py \
  --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --output build/character-metadata-evidence
```

After configuring and building the real Trick core archives:

```sh
python tools/icg_baseline/character_runtime.py \
  --root "$PWD" --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --output build/character-runtime-evidence
```
