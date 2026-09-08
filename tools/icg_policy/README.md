# Bounded legacy metadata policy

This development resolver consumes validated facts v12 and an explicit request.
It emits **resolved policy v1**, not C++, and does not replace production ICG.
The next increment is the narrow metadata emitter in
[the rewrite roadmap](../../docs/developer_docs/ICG_REWRITE_PLAN.md#201-next-milestone-generate-and-execute-legacy-metadata).

## Run

Install `python -m pip install -r tools/icg_requirements.txt`. From the checkout,
create a request using the file IDs actually selected during extraction:

```python
import json
from pathlib import Path
from tools.icg_policy.resolve import request_for

facts = json.loads(Path("facts.json").read_text())
Path("request.json").write_text(json.dumps(request_for(facts), indent=2) + "\n")
```

```sh
python tools/icg_policy/resolve.py facts.json --request request.json > resolved.json
python tools/icg_policy/resolve.py facts.json --request request.json --validate resolved.json
```

A request has `policy_version: "scalar-metadata-1"`, `offset_mode: "numeric"`,
`outputs: ["attributes", "enum-attributes"]`, and sorted unique `file_ids`.
It may narrow captured file selection but cannot widen it. A header merely
present in the include graph is insufficient evidence that its unreferenced
records were extracted. Caller-supplied requests remain mandatory for validation.
Errors publish nothing on stdout; the shell may still create an empty redirected
file. No generated-source writer or production cache is implemented.

## Contract and evidence

[resolved.schema.json](resolved.schema.json) defines a closed draft 2020-12
contract. Every fact declaration receives an include/omit decision with its ID,
source, parent ID, and named rule. File decisions reference the exact header
comment index and matching environment path entries. Field decisions reference
the raw comment index, type ID, units/I/O rules and diagnostics, and a separate
operation-specific access decision. Comment/friend indices refer to the input
facts; the model must be consumed with those validated facts, not in isolation.
Names are used for legacy ABI symbols and the legacy ignore-name rule, never for
parent/field relationships. Sanitized output symbol collisions fail explicitly.

`facts.document_digest` hashes the complete input document, including selection
and policy environment; graph equality alone cannot authorize generation.
`input_digest` hashes that fingerprint, the request, effective settings, and
policy version. `digest` hashes every model field except itself. All use SHA-256
of sorted-key, compact, unescaped-Unicode UTF-8 JSON. Schema, policy version, and
facts version are separate contracts. Neither extracted-facts v12 nor its graph
algorithm changes in this increment.

Validation checks the independent JSON schema, validates facts and request, and
replays policy **before** comparing the digest. Replay shares the policy parser;
it is not an independent implementation of the rules. Independent evidence comes
from live legacy output and native compilation. Mutation tests recompute the
digest before checking altered inclusion, I/O, units, source association, access,
settings, and missing decisions.

## Characterized compatibility rules

The live [characterization runner](characterize.py) compares 31 compatible cases and two explicit policy rejections
against the unchanged `Interface_Code_Gen`, independent expected observations,
and the new resolver. It saves commands, raw outputs, source/facts, requests,
resolved models, generated legacy files, binary/XML fingerprints and reports.

| Area | Preserved observation |
|---|---|
| File header | First comment in line order containing case-insensitive `PURPOSE` or exact `@trick_parse` / `\trick_parse` |
| Same-line comments | Last comment starting on a line wins, including comments preceding the field on that line |
| Field association | Use the field declaration's ending line, only with a recognized Trick header and comments enabled; attached preceding comments do not override it |
| Directives | `trick_parse` wins over `ICG` in the chosen comment; modes are tested in legacy order: everything, attributes, dependencies_only |
| No-comment | `ICG: (NoComment)`, `trick_parse{attributes}`, or matching `TRICK_ICG_NOCOMMENT` leaves units `1`, I/O `15` |
| Exclusions | `ICG: (No)`, dependencies_only, ignored type names, inaccessible nested types, unnamed enums; omitted parents omit descendants |
| Environment | Recorded exclusion paths, external-library paths/overrides, semicolon-separated `TRICK_ICG_IGNORE_TYPES`; no ambient resolver environment is read |
| I/O | All 16 primary/checkpoint combinations; `io` overrides `trick_io`, `cio` overrides `trick_chkpnt_io`; unknown values become zero with `LEGACY_UNKNOWN_IO_ZERO` |
| Invalid legacy I/O | Primary `--` becomes full I/O with `LEGACY_DASHDASH_IO`; checkpoint `--` is rejected because legacy exceeds the four-bit contract |
| Units | Bounded vocabulary: `1`, `m`, `cm`, `km`, `s`, `rad`, `degree`; aliases `--`, `r`, `d`, `M`, `one`; alias conversions retain a diagnostic |

A leftover closing comment marker treated as units is the characterized invalid
unit case: legacy repairs it to `1`; the resolver records
`LEGACY_INVALID_UNITS_DEFAULT`. Other unknown units are **rejected**, not claimed
invalid and not repaired to `1`. Composite UDUNITS expressions, arbitrary prose
interpreted as units, malformed or repeated annotations, and unclosed directives
remain outside this grammar. This is an explicit compatibility boundary, not a
complete reimplementation of `FieldDescription::parseComment`. Descriptions and
general annotation precedence remain pending. Units are left uninterpreted when
legacy skips unit validation because primary I/O is zero.

Path settings are split on `:`, trimmed, and resolved relative to the recorded
working directory, including symlinks. Missing paths remain `kind: "missing"`
evidence of legacy's warn-and-ignore behavior. Directories require a slash
boundary; legacy file entries use raw prefix matching. Validation re-observes
these paths: a moved/missing symlink requires re-resolution. This initial policy
model is not an offline, relocatable cache entry. `TRICK_ICG_COMPAT15` with a
nonempty value is rejected. The explicit numeric-offset profile does not infer
legacy automatic compatibility mode from `TRICK_ICG` conditionals or reproduce
unrecorded production command-line settings.

## Access and bounded type coverage

Numeric offsets may describe private/protected fields without a C++ member
access, matching default legacy metadata. The separately recorded
`member-access-in-init-attributes` permission requires public access or an exact
friend target with the generated function's namespace and `void ()` C++ signature,
non-variadic, non-method, ordinary calling convention and non-noexcept definition.
A friend class grants this free function nothing. Overloads and name prefixes
retain `LEGACY_PREFIX_IS_NOT_ACCESS` findings; legacy's friend visitor matches
prefixes and does not prove access. Native compiler tests check the proposed
operation and reject wrong-name, wrong-overload, and exception-specification cases.
These permissions do not grant lifecycle/STL/binding operations access.

The profile covers complete named non-template records without bases, named enums,
and unqualified `int`, `unsigned int`, and `double` fields plus unsigned-int
bitfields. Explicit zero-I/O fields can be omitted before type-policy checks.
Unsupported required fields/types fail the entire resolution. Extraction still
rejects required static/global/function-pointer facts and parse errors before
policy runs; unselected unrelated declarations are absent rather than fabricated
policy exclusions. No opaque STL dependency contract is introduced.

The existing differential gate now requires resolved record/enum selection and
units/I/O to agree with the three fingerprinted legacy headers (six record tables,
six fields, two enum tables), alongside its existing compiled legacy/native layout
checks. Its hardcoded expected exclusions remain independent test expectations;
the resolver derives exclusions from source/environment evidence.

## Verification

```sh
python -m unittest tools.icg_policy.test_resolve.RuleTests -v
python tools/icg_policy/test_resolve.py --extractor build/icg-extract/trick-icg-extract --compiler /usr/bin/g++ -v
python tools/icg_policy/characterize.py \
  --extractor build/icg-extract/trick-icg-extract \
  --legacy build/legacy-baseline/trick-ICG-baseline \
  --udunits-xml /usr/share/xml/udunits/udunits2.xml \
  --output build/policy-evidence
```

The live characterization runs in the reference Linux/LLVM 17 lane. Actual
extractor and native access tests are part of CTest on LLVM 17–23 Linux/macOS and
GCC 8.5/12; pure rule tests also run on Python 3.11/3.12 Linux/macOS. Existing
legacy reference snapshots are immutable. Successful resolution is not evidence
of newly generated metadata, lifecycle, bindings, registry, SIE or build output.
