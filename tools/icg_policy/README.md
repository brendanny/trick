# Bounded legacy metadata policy

This development resolver consumes validated facts v12 and an explicit request.
It emits **resolved policy v12**, not C++, and does not replace production ICG.
The [bounded metadata emitter](../icg_emit/README.md) consumes this policy and
compares generated C++ with legacy/native evidence.

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

A request has `policy_version: "scalar-metadata-12"`, `offset_mode: "numeric"`,
`outputs: ["attributes", "enum-attributes"]`, sorted unique `file_ids`, and
`template_field_ids: []`.
An explicit `outputs=["lifecycle"]` or combined metadata plus lifecycle request
opts into the bounded lifecycle contract; the default request does not.
It may narrow captured file selection but cannot widen it. A header merely
present in the include graph is insufficient evidence that its unreferenced
records were extracted. Caller-supplied requests remain mandatory for validation.
Errors publish nothing on stdout; the shell may still create an empty redirected
file. The separate emitter provides atomic source writes; no production cache is implemented.

## Contract and evidence

[resolved.schema.json](resolved.schema.json) defines a closed draft 2020-12
contract. Every fact declaration receives an include/omit decision with its ID,
source, parent ID, and named rule. File decisions reference the exact header
comment index and matching environment path entries. Field decisions reference
the raw comment index, type ID, units/I/O rules and diagnostics, and a separate
operation-specific access decision. Comment/friend indices refer to the input
facts; the model must be consumed with those validated facts, not in isolation.
Field annotations retain `description` and `mods`. Schema v12 and policy
`scalar-metadata-12` require explicit enum metadata, field storage and UnitsMap key
decisions. Resolve old v1–v11 inputs again rather than changing their version fields.
Record/enum collisions in their shared size-function symbol
namespace are rejected. Names are used for legacy ABI symbols and the legacy ignore-name rule, never for
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
settings, enum labels/values/order/modifiers, array dimensions and storage,
UnitsMap keys, and missing decisions.

Each field has a `units_map_key` and `storage`. Included storage decisions record
the canonical `element_type_id`, legacy `type_name` and `trick_type`, a native
`cpp_type`, and outer-to-inner `dimensions`. Scalars/bitfields have no dimensions;
zero-I/O omissions have null storage. Canonical type IDs expand scalar/array aliases.
Fixed arrays support at most eight positive extents, each representable by signed
`INDEX.int`. Incomplete/zero/oversized extents and excessive rank produce
`ICG_POLICY_ARRAY_EXTENT` or `ICG_POLICY_ARRAY_RANK`.

Policy v12 supports `bool`, `char`, `signed char`, `unsigned char`, `short`,
`unsigned short`, `int`, `unsigned int`, `long`, `unsigned long`, `long long`,
`unsigned long long`, `float`, `double`, and `char16_t` field bases, with aliases and fixed
arrays. These 15 types share the bounded lifecycle and template storage policy.
The emitter checks the little-endian LP64 ABI, 16-bit short, 64-bit long long,
one-byte bool/char and IEEE binary32 float. Plain `char` fields require signed
native `char`; explicit signed/unsigned character types retain their own spellings
and legacy type codes. The [scalar](../icg_baseline/scalars/README.md) and
[integer](../icg_baseline/integers/README.md) corpora provide independent legacy,
native and real MemoryManager evidence. The [character corpus](../icg_baseline/characters/README.md)
adds unsigned 16-bit code-unit storage for `char16_t`, with size/alignment guards,
legacy/native comparisons and complete checkpoint readback. No Unicode validation
or string conversion is implied. `wchar_t` (legacy assignment truncation),
`char32_t` (legacy field omission), extended
integers, `long double`, qualifiers and pointer/reference fields remain
unsupported. Only unsigned-int bitfields are characterized.

The [array corpus](../icg_baseline/arrays/README.md) also establishes the legacy
UnitsMap key convention: enclosing records joined by `__`, followed by `_field`,
with namespaces omitted. Keys are explicit decisions, not the table symbol with
a field suffix. Selected-field key collisions fail with `ICG_POLICY_NAME`; the
resolver does not reproduce ambiguous static initialization order.

Each included enum has `metadata.enum`: `label_rule`, `diagnostics`, `mods`, and
ordered `rows`. A row's `source_index` references the enumerator in the input
facts (including its source), `label` is the legacy lookup spelling, `cpp_name`
is the C++ constant used by native checks, and `value` is an exact decimal string.
The legacy `LEGACY_CONTAINER_SCOPE` rule omits the enum's own name from labels,
even for scoped enums. These retain `LEGACY_SCOPED_LABEL_OMITS_ENUM`; native
references still include the enum's name. Duplicate values remain separate rows,
and empty enums retain an empty row list. Unsigned underlying types set modifier
bit 30. This does not change the existing `ENUM_ATTR` ABI or runtime lookup.

The [independent enum corpus](../icg_baseline/enums/README.md) characterizes
8/16/32/64-bit underlying storage, signed-int boundary values, namespace and record
scopes, and inaccessible nested enums. Opaque declarations are omitted with
`OPAQUE_ENUM_DECLARATION`, matching legacy's definition-only emission. Values
outside signed 32-bit `ENUM_ATTR.int`
fail with `ICG_POLICY_ENUM_VALUE`. Unsigned narrow values whose sign bit is set
fail with `ICG_POLICY_ENUM_SIGN_EXTENSION`: legacy encodes unsigned-char `255`
as `-1`, disagreeing with native C++.
`bool`-backed `true` has the same mismatch because its value uses one bit despite
occupying a byte. Underlying aliases are resolved through canonical type IDs.
Resolution rejects the entire request. Reproducing the numeric mismatch or
changing runtime behavior is outside this profile.

## Characterized compatibility rules

The live [characterization runner](characterize.py) compares 36 compatible cases and two explicit policy rejections
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
complete reimplementation of `FieldDescription::parseComment`. The remaining comment text becomes a description using characterized legacy
cleanup, whitespace normalization, and escaped-byte behavior. General annotation
precedence remains pending. The `--` units alias retains modifier bit 2 (`mods: 4`), independently of its
normalized units string. Units are left uninterpreted when
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
and the 15 unqualified scalar field bases listed above, fixed arrays of those
types, their scalar/array aliases, and unsigned-int bitfields. Qualified elements,
pointer/reference and structured/enum arrays remain outside this policy.
Explicit zero-I/O fields can be omitted before type-policy checks.
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

The integration suite requires both the extractor and C++ compiler. Plain
`python -m unittest discover -s tools/icg_policy` exits nonzero with setup
instructions instead of reporting success with skipped frontend tests. Select
`RuleTests` explicitly for the tool-independent rules, or use CTest/the script
below for the full suite.

```sh
python -m unittest tools.icg_policy.test_resolve.RuleTests -v
ctest --test-dir build/icg-extract -R icg_policy_integration --output-on-failure
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
legacy reference snapshots are immutable. Successful resolution alone is not evidence of generated metadata; the separate
emitter gate establishes the bounded contract. Bindings, registry, SIE and build output remain outside this profile.

## Bounded lifecycle policy

Policy v5 adds a nullable `metadata.lifecycle` to record decisions. It is null for
metadata-only requests. Lifecycle requests record separate allocator, destructor,
and scalar-deletion actions/symbols/reasons; default-constructor and destructor
evidence names special-member slots and declaration IDs. Public operation access
is independent of init-function friendship. Deleted-default POD raw storage does
not claim C++ construction is available. Suppressed/abstract construction and
inaccessible destruction produce explicit absent exports, with legacy POD no-ops
preserved separately from scalar deletion.

Lifecycle-only requests omit enum and field metadata with `OUTPUT_NOT_REQUESTED`,
while validating every physical field's storage for lifecycle eligibility.
Selection, file exclusions, ignored names, inaccessible nested types and parent
omissions still apply. The domain is positive-count, nonthrowing operations with
matching ownership; unions, over-alignment, class allocation operators, ambiguous
special members, inheritance/templates and unsupported fields are rejected.
Model mutation tests rehash altered actions, access, evidence links and symbols
before requiring policy replay to reject them.

See the [emitter lifecycle contract](../icg_emit/README.md#opt-in-lifecycle-output)
for the native differential and configured MemoryManager comparison. Facts v12
and all captured legacy references remain unchanged.

## Explicit template-member requests

Policy v12 supports the separate `outputs: ["template-attributes"]` profile. Supply
sorted, unique, nonempty `template_field_ids` identifying the exact containing
fields to generate. Other output profiles require an empty list. Existing
metadata requests still reject template records; this opt-in generates fragments,
not complete containing-record metadata.

```python
request = request_for(
    facts,
    outputs=["template-attributes"],
    template_field_ids=sorted(selected_field_ids),
)
```

`template_instances` has one entry per selected specialization, deduplicating
repeated requests. `field_id` identifies the first active use, `requested_field_ids`
retains the sorted explicit requests (empty for automatic dependencies), and
`dependency_path` records the field-ID path from an ordinary root to that first use.
`dependency_record_ids` identifies the included structured child tables. Each
entry also records the concrete record, primary template, argument type IDs,
C++ spelling, cached legacy symbol,
initializer and field decisions. Schema v12 requires exact replay of this evidence.

Traversal starts with selected global ordinary records whose template fields
are all in one physical file. Roots and fields follow physical source order,
independent of serialized graph IDs. It expands canonical aliases, arrays and
pointer/reference targets, skips zero-I/O uses before visiting their types, and
caches each specialization **before** visiting its members. This preserves first
use across repeated fields and terminates recursive dependencies. Template
arguments alone do not claim a name; a member that visits that type does.
Every captured user file, including the translation unit and definition headers,
must be selected: an unselected header could hide an earlier ordinary consumer
from the declaration closure. Traversed definitions must be included by file policy.

Requests may select public unqualified objects or fixed arrays, including aliases
and nested fields reachable through template members. Emitted tables cover
the 15 scalar base types listed above, the bounded 32-bit enum types described
below, nested specializations of those templates, and fixed arrays of supported
types; zero-I/O members are omitted
before storage checks. Structured fields carry the concrete child record/type IDs,
its cached legacy symbol, C++ storage spelling and dimensions. Emitted element
sizes must fit the positive `ATTRIBUTES.size` integer range. Selecting a parent
automatically includes its transitive structured dependencies, deduplicated by ID.
Traversed templates must be complete, standard-layout global primary
instantiations without bases or nested declarations
(other than aliases), using nonpack type parameters without defaults.

Cross-file ordinary-root order, namespaces, private/static template uses,
non-type/default/pack arguments, explicit/partial specializations, enum and
ordinary-record template arguments, pointer/reference rows, bitfields and STL
remain unsupported.
Only requested tables and their by-value structured dependencies are emitted.
This is a bounded extraction-scope naming contract,
not a full-program template registry.

[Live characterization](template_characterize.py) independently checks eight cases:
repeated requests, source ordering across ordinary roots, a zero-I/O first use,
canonical alias/array use, pointer/reference first use, nested first use and recursive dependencies. It compiles
legacy and candidate leaf tables separately against native C++ expectations.
The [template comparison](../icg_baseline/template_metadata.py) checks four tables,
six scalar/array fields and six pointer exclusions from the immutable existing
`TemplateTest.hh` capture, including `Foo<int>` and `Foo<double[2]>` nested leaves.
The [structured comparison](../icg_baseline/template_structured.py) adds the outer
`TTT1<Foo<int>, Foo<double[2]>[3]>` table and requests its nested leaves through
dependency closure. Both complete sources compile on every compiler lane. The
configured Linux gate links independent legacy/candidate executables against the
real MemoryManager, checks initialization and pointer identity, and replaces all
five tables in the simulation checkpoint/readback gate. See the
[emitter contract](../icg_emit/README.md#template-member-metadata).

The live `template_characterize.py` gate also compares all seven added integer
argument types with legacy first-use naming and compiled leaf metadata. Its
multiword type spellings and expected symbols are independent of generation
policy, alongside the original eight traversal-order cases.

The same live template gate checks `Box<char16_t>` against legacy first-use
naming and unsigned-short metadata, bringing the gate to 16 cases.


## Enum template dependencies

Policy v12 adds named nonempty enums backed by 32-bit `int`/`unsigned int` to
`template-attributes`, including aliases, fixed arrays, scoped enums and named
non-inline namespace scopes. Other enum storage, record-nested enums, qualifiers,
pointers and ordinary record enum fields remain unsupported. The existing enum
value limits still apply. See the [independent corpus](../icg_baseline/template_enums/README.md).

Each instance records `dependency_enum_ids`; only enums required by selected
arguments and included fields receive `ENUM_DEPENDENCY` declaration decisions.
Enum storage records the enum ID, canonical element ID, C++ type, legacy spelling
and dimensions. The emitter generates the dependency tables/size exports and
uses guarded real MemoryManager lookup for zero-initialized enum member rows.
Unrelated enums remain omitted, and ignored dependencies fail the request.

Canonical template spellings retain `enum` and legacy `> >` spacing for adjacent
closing brackets. Enum member names retain namespace separators; their exported
table names use underscores. Conflicting values for an identical legacy checkpoint
label within the emitted closure fail with `ICG_POLICY_ENUM_LABEL`. This prevents
ambiguous readback between scoped enums whose labels omit their enum names.
