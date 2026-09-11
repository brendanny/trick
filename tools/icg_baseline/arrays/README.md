# Fixed-array metadata evidence

This isolated corpus compares the unchanged legacy generator, candidate emitter,
and independent native C++ observations for two records and nine fields. Six
fields are arrays, covering ranks one, two, three and eight, unequal dimensions,
scalar typedefs, array typedefs, namespaces and array annotations. Scalar fields
check padding and offsets around arrays.

Expected dimensions, base types, offsets, units, I/O, descriptions and modifiers
are specified manually in `array_metadata.py`. Native probes use `std::rank`,
`std::extent`, `std::remove_all_extents`, `sizeof` and `offsetof`; they do not read
dimensions from policy or generated metadata. The independently captured legacy
source and candidate compile separately against the real Trick ABI and UnitsMap.
A separate translation unit checks C tables and init/size entry points, including
repeated initialization.

## Characterized contract

- `ATTRIBUTES.type_name` and `size` describe the base element. Aliases of scalars
  and arrays expand to the supported base scalar type.
- `num_index` is the rank. Active `index[].size` entries retain outer-to-inner
  declaration order. Starts and unused entries are zero. Rank eight is supported;
  higher ranks, incomplete/zero extents and extents exceeding signed `INDEX.int`
  are rejected before any candidate is published.
- This original corpus covers unqualified `int`, `unsigned int` and `double`.
  Policy v9 also admits `bool`, `char`, `float` and `long` through the separate
  [scalar corpus](../scalars/README.md), including arrays of those bases.
  Pointer/reference, const/volatile, record/enum and other scalar element policies
  remain outside this increment. Explicit zero-I/O fields can still be omitted
  before type validation.
- Units, I/O, descriptions, aliases such as `r`, and the `--` modifier apply to
  arrays as observed in the existing bounded annotation policy.
- UnitsMap keys omit namespaces but retain enclosing record names joined with
  `__`. The previous emitter incorrectly included namespaces. A namespaced array
  with `rad` units exposes that mismatch; unitless fixtures had concealed it
  because missing entries return `1`. Policy now resolves the exact key and
  rejects selected-field key collisions rather than depending on initializer
  ordering. The runtime's existing key convention is unchanged.

Mutation tests alter rank, dimension order (including the same total element
count), extent, index start, unused indices, element size, offset, annotations and
UnitsMap registration. Each must fail compiled comparison and clear any stale
native success report. Rehashed policy mutations cannot authorize altered storage
or keys. Private-array checks require the exact init-function friend; numeric
metadata without a member access still follows the existing policy.

## Reproduce

Build the reference generator as described in [legacy/README.md](../legacy/README.md),
then run:

```sh
python tools/icg_baseline/legacy.py \
  --build-dir build/legacy-baseline \
  --manifest tools/icg_baseline/arrays/corpus.json \
  --udunits-xml /usr/share/xml/udunits/udunits2.xml \
  --output build/array-reference-evidence \
  --reference tools/icg_baseline/arrays/reference
python tools/icg_baseline/array_metadata.py \
  --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --output build/array-evidence
```

Provenance records the actual revision, dirty fixture state and source, manifest,
binary, build and XML fingerprints. Cold and warm snapshots match. Forced
generation preserves legacy's duplicate `classes.resource` append. Content hashes
protect the captured sidecars. Existing enum, lifecycle and original header
references are unchanged.

The baseline CI lane reproduces all three snapshots. The extractor CTest matrix
runs the compiled and mutation gates; an additional reference lane retains CLI
evidence. Local GCC/Clang results do not establish that every remote lane passed.
These tests cover metadata only, not array checkpoint/restart, MemoryManager
ownership, lifecycle helpers, STL or production build/registry/SIE integration.
