# Common builtin scalar evidence

This isolated corpus adds `bool`, `float`, `char`, and `long` to the generated
field profile. Two records and 13 fields cover scalar storage, boolean matrices,
float/character/long arrays, scalar and array aliases, padding, units and
descriptions. Expected type names, offsets, dimensions and annotations are
specified independently in `scalar_metadata.py`.

| C++ base type | Legacy kind | Audited element size |
|---|---|---|
| `bool` | `TRICK_BOOLEAN` | 1 byte |
| `char` | `TRICK_CHARACTER` | 1 byte |
| `float` | `TRICK_FLOAT` | 4 bytes, IEEE binary32 |
| `long` | `TRICK_LONG` | 8 bytes on the existing LP64 target profile |

This corpus uses signed native plain `char`. The emitter now rejects plain-char
fields on unsigned-char targets because facts do not yet encode that distinction.
Explicit `signed char` and `unsigned char` are covered separately in the
[integer corpus](../integers/README.md). Other uncharacterized
builtins, qualified or pointer/reference fields, and bitfields with bases other
than `unsigned int` still fail. This corpus was introduced with resolved policy v9 and
emitter v8; facts remain v12. The integer extension advances policy/emitter to v10/v9.

## Independent metadata and failure controls

The three checked-in snapshots are outputs of the unchanged legacy ICG. Cold and
warm snapshots match; forced generation retains the observed duplicate
`classes.resource` append. Source, manifest, binary, compiler and UDUNITS digests
are recorded in `reference/provenance.json`. Existing references are unchanged.

Legacy and candidate sources compile and run separately against real Trick
headers and UnitsMap. Native `sizeof`, `offsetof`, `std::rank` and `std::extent`
observations must agree with the captured tables and extracted facts. The emitter
also asserts the bool/char/float ABI and its existing LP64 contract. Seven emitted
mutations change each new type code, long element size, boolean dimension order
with unchanged total size, or a UnitsMap key. Each must fail compiled metadata
comparison; a compilation failure does not satisfy those controls.

Every compiler lane runs these comparisons, plus checks of the shared scalar
policy in template tables and non-POD lifecycle construction. The baseline CI
lane regenerates and compares all three snapshots. Missing tools do not turn
integration suites into successful skipped runs.

## Real MemoryManager checkpoint gate

`scalar_runtime.py` first runs the metadata comparison, then compiles separate
legacy and candidate executables against the configured Trick archives. Each
registers both native records as external storage through the real MemoryManager.
Every field is assigned, checkpointed, mutated and restored; individual values
are checked independently in `runtime.cpp`. Both observations and checkpoint
bytes must match between generators.

Two modes are exercised with zero-valued assignments enabled:

- Compact decimal checkpoints cover true/false arrays, exact float fractions,
  zero, character controls/strings, and positive/negative long values beyond 32 bits.
- Expanded hexadecimal checkpoints cover float maximum/lowest, normal and
  subnormal minima, negative zero, native character minimum, and `LONG_MIN`/`LONG_MAX`.
  Float equality includes representation checks, so the negative-zero sign and
  subnormal value cannot disappear unnoticed.

Three controls truncate long metadata to integer, disable boolean checkpoint
permissions, or omit restoration. Each must reach execution and fail the value
checks. Compile/link failures and timeouts do not count. Sources, commands,
observations, checkpoints, failures, link configuration and archive fingerprints
are retained. This gate uses no MemoryManager stubs. It runs locally and in the
configured LLVM 17 / GCC 13 Linux workflow; it does not add a SWIG binding or a
production simulation build integration. NaN/infinity and decimal extremes are
not covered by these two finite-value round trips.

## Reproduce

Build the isolated reference generator as in [legacy/README.md](../legacy/README.md):

```sh
python tools/icg_baseline/legacy.py \
  --build-dir build/legacy-baseline \
  --manifest tools/icg_baseline/scalars/corpus.json \
  --udunits-xml /usr/share/xml/udunits/udunits2.xml \
  --output build/scalar-reference-evidence \
  --reference tools/icg_baseline/scalars/reference
python tools/icg_baseline/scalar_metadata.py \
  --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --output build/scalar-metadata-evidence
```

After configuring and building actual Trick core archives:

```sh
python tools/icg_baseline/scalar_runtime.py \
  --root "$PWD" --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --output build/scalar-runtime-evidence
```

The configured comparison records its real compiler and Linux archive link flags
from `trick-config`. Its success is distinct from portable metadata compilation.
