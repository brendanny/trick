# Scoped enum metadata evidence

This isolated corpus captures the unchanged legacy generator on LLVM 17, then
compiles its immutable output separately from the candidate and independent native
C++ observations. It extends the existing metadata gate without refreshing its
older reference corpus or modifying the production generator/runtime.

`Enums.hh` covers ten selected tables and 19 enumerators: global, namespace,
inline namespace and nested record scopes; `enum class` and `enum struct`; signed
and unsigned 8/16/32/64-bit storage; signed-int boundary values; duplicate values;
and an empty enum. A private nested enum and an opaque declaration are explicitly
excluded. One record and
field also exercise namespace-correct initialization, the real UnitsMap and
separate-translation-unit C entry points.

The compatible gate requires both sources to match independently specified
labels/values/modifiers and actual C++ enum values and sizes. It checks table
order, counts, aliases, sentinels and linkage. It retains facts, explicit requests,
resolved models, generated sources, commands, diagnostics and observations. A
success report is written only after both lanes complete.

## Observed compatibility boundaries

- Legacy labels omit an enum's own name, including scoped enums. Policy records
  `LEGACY_CONTAINER_SCOPE` and a `LEGACY_SCOPED_LABEL_OMITS_ENUM` diagnostic;
  native checks use the full C++ enumerator name.
- Unsigned underlying types set `mods = 0x40000000`. The supported values must fit
  signed 32-bit `ENUM_ATTR.value` and agree with the legacy conversion.
- `UnsignedNarrow.hh` independently captures the rejected boundary. Legacy
  `EnumVisitor::getSExtValue()` turns unsigned-char `128`/`255` into `-128`/`-1`
  and unsigned-short `32768`/`65535` into `-32768`/`-1`. A compiled probe records
  both legacy and native numbers, including `bool`-backed `true` as legacy `-1`
  versus native `1`. Policy must fail with
  `ICG_POLICY_ENUM_SIGN_EXTENSION`, leaving no candidate. Separate policy tests
  reject out-of-int values; this is not evidence of runtime equivalence for them.
- Legacy reopens an inline namespace without the `inline` keyword. On Clang,
  the legacy lane retains the warning with the sole exception
  `-Wno-error=inline-namespace-reopened-noninline`. Its source is never rewritten.
  Candidate compilation retains full `-Werror`.

The emitter integration suite also mutates labels, unsigned modifiers, values,
alias order/count, empty sentinels, tables and size entry points. Each mutation
must fail compiled comparison and remove any stale success report. Rehashed
policy mutations cannot authorize changed enum decisions.

## Reproduce

Build the standalone legacy tool as described in [legacy/README.md](../legacy/README.md).
Capture its cold, warm and forced output against these references:

```sh
python tools/icg_baseline/legacy.py \
  --build-dir build/legacy-baseline \
  --manifest tools/icg_baseline/enums/corpus.json \
  --udunits-xml /usr/share/xml/udunits/udunits2.xml \
  --output build/enum-reference-evidence \
  --reference tools/icg_baseline/enums/reference
python tools/icg_baseline/enum_metadata.py \
  --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --output build/enum-evidence
```

`reference/provenance.json` records the actual capture revision, dirty fixture
state, manifest/source/build/binary/XML fingerprints, environment and pass results.
Cold and warm snapshots agree. Forced generation preserves the legacy duplicate
append in `classes.resource`; it is neither normalized nor fixed. Sidecar hashes
are verified before use. The baseline CI lane reproduces all six snapshots; the
extractor CTest lanes run candidate/legacy/native and rejection probes. These are
configured gates, not a claim that every remote lane has passed.

This remains metadata evidence. Runtime enum registration/lookup, lifecycle,
STL, registry/SIE/build generation and arbitrary target ABIs are not covered.
