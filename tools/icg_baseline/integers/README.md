# Integer width and signedness evidence

This isolated corpus adds seven integer base types to the bounded emitter. Two
records and 22 fields cover each base as scalar and array storage, aliases,
a short matrix, padding, units and descriptions. Expected names, type spellings,
offsets, dimensions and annotations are specified independently in
`integer_metadata.py`.

| C++ base type | Captured legacy kind | Audited size |
|---|---|---|
| `signed char` | `TRICK_CHARACTER` | 1 byte |
| `unsigned char` | `TRICK_UNSIGNED_CHARACTER` | 1 byte |
| `short` | `TRICK_SHORT` | 2 bytes |
| `unsigned short` | `TRICK_UNSIGNED_SHORT` | 2 bytes |
| `unsigned long` | `TRICK_UNSIGNED_LONG` | 8 bytes |
| `long long` | `TRICK_LONG_LONG` | 8 bytes |
| `unsigned long long` | `TRICK_UNSIGNED_LONG_LONG` | 8 bytes |

Together with the preceding seven types this makes 14 supported scalar bases.
Policy is v10, emitter v9, and facts remain v12. The target profile retains
little-endian LP64 Linux/macOS, with generated short/long-long ABI guards.
Explicit `signed char` has its own legacy spelling even though its type code
matches signed plain `char`. Plain `char` fields now require signed native char:
legacy uses a different code for unsigned plain char, a property facts do not yet
record. A compiler test rejects the mismatch under `-funsigned-char`, and accepts
explicit signed/unsigned character fields under that same flag. Extractor argument
handling is unchanged; this is a generated-source conformance check.

The subsequent [character corpus](../characters/README.md) adds `char16_t` code-unit
storage in policy v11 / emitter v10. `wchar_t`, `char32_t`, extended integers,
`long double`, qualified and pointer/reference fields remain unsupported.
Bitfield support is still unsigned-int only; new bases do not widen it.

## Independent metadata checks

All three snapshots come from the unchanged legacy ICG. Cold and warm are equal;
forced generation retains the observed duplicate `classes.resource` append.
The content-addressed objects preserve the original bytes, including whitespace.
`reference/provenance.json` records exact manifest, source, binary, compiler and
UDUNITS fingerprints. Earlier fixtures and reference snapshots are unchanged.

Legacy and candidate sources compile and execute separately against real Trick
headers and UnitsMap. Their observed tables must match native `sizeof`,
`offsetof`, array rank/extents and extracted facts. Ten candidate mutations change
the seven type codes, unsigned-long-long size, short-matrix dimension order, or
signed-character spelling. Each must compile successfully and fail the independent
metadata comparison. Equal-size signed/unsigned substitutions cannot hide behind
layout equality. All compiler lanes also check template fields and non-POD
lifecycle initialization for every added base type. The live legacy
`template_characterize.py` gate separately verifies all seven first-use template
names and compiled leaf tables, including multiword argument spellings.

## Real MemoryManager checkpoint gate

`integer_runtime.py` first completes the metadata comparison. It then links
separate legacy and candidate executables against the configured Trick archives,
using the same comparison runner as the preceding scalar gate. Both register
native records as external storage in the actual MemoryManager. Every field is
assigned, checkpointed, mutated and restored. The C++ probe explicitly checks
all 22 fields, including every array element. Observations preserve 64-bit integers
as JSON integers; they are never converted through floating point.

Two decimal checkpoint passes exercise compact and expanded arrays. Values cover
signed minima/maxima, negative values, zero, unsigned high-bit values, and the
full `ULONG_MAX` / `ULLONG_MAX` range. Character arrays contain boundary bytes,
including values above 127 and a non-terminated signed-character array; checkpoint
escaping and readback must preserve them. Candidate and legacy checkpoint bytes
and observations must match exactly.

Six controls replace short/unsigned-long/long-long/unsigned-long-long metadata
with narrower types, disable unsigned-character checkpoint permissions, or omit
restoration. Each must reach execution, return the probe's failure code and report
that integer values did not round trip. Compile/link errors, unrelated execution
errors and timeouts do not count. Successful reports appear only after every
positive check and mutation control passes.

The runtime gate uses no MemoryManager stubs. It records sources, commands,
observations, checkpoints, failure logs, link configuration and archive hashes.
It runs in the configured LLVM 17 / GCC 13 Linux workflow. This adds no SWIG
binding or production simulation integration; overflow arithmetic, locale-dependent
wide characters, pointer ownership and executive restart are outside this corpus.

## Reproduce

Build the isolated legacy ICG as described in [legacy/README.md](../legacy/README.md):

```sh
python tools/icg_baseline/legacy.py \
  --build-dir build/legacy-baseline \
  --manifest tools/icg_baseline/integers/corpus.json \
  --udunits-xml /usr/share/xml/udunits/udunits2.xml \
  --output build/integer-reference-evidence \
  --reference tools/icg_baseline/integers/reference
python tools/icg_baseline/integer_metadata.py \
  --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --output build/integer-metadata-evidence
```

After configuring and building actual Trick core archives:

```sh
python tools/icg_baseline/integer_runtime.py \
  --root "$PWD" --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --output build/integer-runtime-evidence
```
