# LLVM 17 extractor capability spike

This standalone Phase 0 probe evaluates the stable libclang C API against facts
required by Trick's legacy metadata and planned owned IR. It does not link to the
current ICG, generate production metadata, or become a second extractor.

The checked-in `llvm17-results.json` was generated with libclang 17.0.6. It
records three required blockers:

- base declarations and virtuality are available, but named-field lookup on a
  derived type cannot recover ordinary or virtual inherited field offsets;
- explicitly defaulted/deleted constructors are available, but an implicit
  default constructor has no cursor;
- a variadic specialization exposes an opaque pack, without its element facts.

These gaps would require reconstructing C++ semantics from strings or changing
the initial legacy runtime contract. [ICG-001](../../docs/developer_docs/architecture/ICG-001-extractor-api.md)
therefore selects one LLVM 17 LibTooling extractor behind the process/IR boundary.

The probe also verifies fields and field offsets, fixed and dependent bitfields,
type/integral template arguments, partial specializations, comments, annotations,
friend/access discovery, anonymous records, and abstract-record detection.
The layout controls query `Root.root` and `Diamond.own` directly. Both
`clang_Type_getOffsetOf(Diamond, "left")` and `(..., "root")` return `-5`
(`CXTypeLayoutError_InvalidFieldName`). The older base-cursor field query returns
`-1`, as expected for that field-only API; it is no longer the sole layout evidence.

## Reproduce with an LLVM 17 installation

```sh
cmake -S tools/icg_capability -B build/icg-capability \
  -DLLVM_ROOT=/usr/lib/llvm-17 -DCMAKE_BUILD_TYPE=Release
cmake --build build/icg-capability
build/icg-capability/libclang17_probe \
  tools/icg_capability/fixture.hh > build/icg-capability/observations.json
python3 tools/icg_capability/evaluate.py \
  build/icg-capability/observations.json \
  --expected tools/icg_capability/llvm17-results.json \
  --output build/icg-capability/results.json
```

`evaluate.py` fails if observations drift. It ignores only the package-specific
Clang version spelling and the nonnegative control field's target-specific offsets
(the type and cursor queries must agree).
The CI job installs LLVM 17 independently and publishes both JSON files as an
artifact. The result does not replace the pending GCC 8.5/12 layout and generated
operation probes.
