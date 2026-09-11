# Bounded legacy metadata and lifecycle emitter

This standalone development backend consumes **facts v12, resolved policy v9,
and the caller's explicit request**. It generates C++ metadata and opt-in
lifecycle helpers against the existing Trick ABI. It is not a production
`trick-ICG` replacement.

**Supported scalar field types are exactly `bool`, `char`, `float`, `int`,
`unsigned int`, `long`, and `double`.** The backend also emits unsigned-int
bitfields and fixed arrays of those scalars. `short`, explicitly signed/unsigned
character types, unsigned/wider integer types, and `long double` remain unsupported;
a required unsupported field fails the request. Separate profiles cover enum
tables (not enum-valued fields), lifecycle exports, and bounded structured template
members. Extraction covers more types than generation, so successful facts
extraction does not establish emitter coverage.

```sh
python tools/icg_policy/resolve.py facts.json --request request.json > resolved.json
python tools/icg_emit/emit.py facts.json --request request.json \
  --resolved resolved.json --output build/candidate.cpp
```

Create the request with `tools.icg_policy.resolve.request_for(facts)` as described
in the [policy documentation](../icg_policy/README.md). Old policy v1–v8 documents
must be resolved again; relabeling their version is not a migration.

## Generated contract

- C-linkage `ATTRIBUTES` and `ENUM_ATTR` tables and complete sentinels.
- Source-order fields and enumerators, numeric offsets, legacy 32-bit unsigned
  bitfield storage, scalar sizes, units, I/O, modifier bits, and descriptions.
- Fixed arrays of the supported scalars: base element size, ordered dimensions,
  zero starts/unused indices, and expanded scalar/array typedefs.
- Namespace-correct C++ initialization functions, global C-interface wrappers,
  and `io_src_sizeof_*` entry points. Initializers are repeatable.
- UnitsMap registration through the real implementation, matching legacy keys.
- Compile-time ABI, record/enum size/alignment, enum signedness and value checks. Public
  scalar offsets/types and those with exact init-function friendship are checked
  inside that function using actual C++ member-access expressions.

Every include/omit and access decision comes from the validated policy model;
the emitter has no fixture-name exclusion list. It replays policy validation and
checks each observed source file's digest before rendering. Numeric private-field
metadata does not itself need member access. An init-function friend grants no
lifecycle, STL, registry, or binding permission.

Ordinary-record metadata supports standard-layout records in the bounded
scalar/array policy and scoped/unscoped enum values representable by `ENUM_ATTR.int` that agree with
legacy's signed integer conversion. Enum labels, C++ names, values, order and
modifier bits come from explicit policy decisions; the emitter does not derive
them again. Field storage, dimensions and UnitsMap keys are likewise resolved
explicitly. Generated checks verify the full native field type and that its
storage fits inside the record. Its target profile is
little-endian LP64 x86-64/AArch64 Linux or macOS, with eight-bit bytes, 32-bit int,
one-byte bool/char, IEEE binary32 float, and 64-bit long/double. Bitfields must fit a complete in-object 32-bit storage unit.
For metadata output, non-standard-layout records, wider enum values, unsigned narrow values that legacy
sign-extends incorrectly, unsafe packed
bitfields, conflicting init-function signatures, and empty selections are explicit
errors. These emitter limits are
narrower than successful fact extraction or policy resolution.

In ordinary-record metadata, arrays require one to eight fixed positive extents,
each fitting signed `INDEX.int`. Const/volatile, pointer/reference and
structured/enum elements remain rejected. The explicit template profile also
supports its bounded structured arrays. UnitsMap keys retain enclosing record
names but omit namespaces, correcting the prior emitter's namespace prefix.
Ambiguous selected-field key collisions are policy errors.

Output includes the original translation-unit header and embeds the emitter
version and policy/input digests. Compile it with the model's matching target and
preprocessing configuration. Compile-time checks provide additional guards; this
is not automatic compile-command replay or proof of arbitrary conditional-header
equivalence. Real source paths are currently required.

No STL helpers, registries, SIE, make/link files, bindings, cache, or
production build integration are emitted. Lifecycle helpers require an explicit
request as described below. A successful metadata-only file does
not satisfy a full per-header ICG generation request.

## Opt-in lifecycle output

Create an explicit request with `resolve.request_for(facts, outputs=["lifecycle"])`
for lifecycle helpers alone, or `outputs=["attributes", "enum-attributes", "lifecycle"]`
to combine them with metadata. The default request remains metadata only.
Use the same resolver/emitter CLI and atomic writer for either profile.

The resolved model separately chooses each `io_src_allocate_*`,
`io_src_destruct_*`, and `io_src_delete_*` C symbol and action. It records the
special-member slot/declaration evidence and public access for the exact operation.
An init-function friend grants no lifecycle access. Generated native traits
independently check POD, abstractness, placement-default availability,
destructibility, destructor virtualness, and allocation alignment.

This profile covers complete named non-template classes/structs without bases,
with the bounded scalar/array fields. Lifecycle-only output can cover non-standard-layout
records, including the abstract fixture; requesting metadata still enforces the
metadata layout boundary. Unions, over-alignment, class-specific allocation,
polymorphic deletion without a virtual destructor, ambiguous special members,
and unsupported fields fail the request. All physical fields are checked even
when I/O would omit their metadata.

Legacy ownership behavior is preserved: POD allocation is zeroed raw storage,
including deleted-default PODs, with no-op destruct/delete wrappers. Other
constructible records use `calloc` and placement construction; destruction runs
forward without freeing, and scalar deletion uses `delete`. Abstract or
inaccessible/deleted construction omits the allocator; inaccessible/deleted
destruction omits both destruction and deletion. Allocation with a private
destructor remains an explicitly recorded legacy export, exercised only for
symbol availability in the reference probe.

The declared domain is positive counts, nonthrowing special members, and matching
ownership. Constructor/destructor bodies are not analyzed for exceptions.
Generated allocation returns null for nonpositive counts or allocation failure;
exception recovery and general OOM behavior are not established by this gate.
Callers must pair generated allocation with destruction plus `free`, and use the
non-POD scalar-delete wrapper only for scalar `new`. POD no-op deletion does not
release caller-owned storage.

```sh
python tools/icg_baseline/lifecycle_codegen.py \
  --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --output build/lifecycle-codegen-evidence
```

The independent captured lifecycle probe compares six records, 18 symbol lookups
(including required absences), and 12 executions for both legacy and candidate
sources. It checks initialized values, event order, strides, raw POD storage and
virtual deletion. Candidate mutations must fail for missing exports, C++ linkage,
reordered/missing destruction, and leaked scalar storage. The LLVM 17 Linux lane
runs the candidate with ASan/UBSan/LSan; all compiler lanes run ordinary comparisons.

The configured MemoryManager gate first completes its legacy runs. It then retains
legacy metadata/registration, renames the legacy lifecycle exports, adds the
candidate helpers, recompiles and relinks the simulation, and repeats all runtime
observations. Renamed helpers cannot satisfy the original symbol lookups; a native
negative control removes a candidate allocator and requires lookup failure.
Original source, candidate, overlay, policy, build log and runtime evidence are retained.
This is a test overlay, not production ICG/build integration.

## Template-member metadata

Emitter v8 accepts `outputs=["template-attributes"]` with explicit containing
field IDs. It emits each selected specialization and its structured dependency
closure: scalar/array/structured tables, sentinels,
initializer/C wrapper, size function and UnitsMap entries. It uses resolved
first-use symbols and type spellings; a generated C++ alias makes native `offsetof`
checks safe for template types containing commas. Selection and limits are in the
[template policy](../icg_policy/README.md#explicit-template-member-requests).

```sh
python tools/icg_baseline/template_metadata.py \
  --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --output build/template-metadata-evidence
```

The comparison uses the unchanged `TemplateTest.hh` and its existing immutable
legacy capture. It selects four complete generated blocks by independently
specified symbol names, preserving their original bodies. Legacy and candidate
compile in separate executables against the same real Trick headers and UnitsMap.
Independent native types and manual expectations compare four tables, six fields,
array shapes, offsets, sizes, annotations, sentinels, C linkage and six zero-I/O
pointer exclusions. Expected symbols and layouts are specified independently of production policy.
No legacy snapshot or fixture is regenerated for this increment.

The configured simulation overlay renames the old definitions of those metadata
entries while preserving containing-record references to the original ABI names.
Only candidate tables can satisfy those references. The nested `Foo<int>` and
`Foo<double[2]>` leaves use cached first-use names reached through the outer `TTT1`.
Rebuild/relink and identical checkpoint/readback observations are required,
including nonzero nested scalar/array values assigned, mutated and restored
through the real MemoryManager. A native negative control removes
a candidate table and requires link failure; a changed-offset control proves the
containing record sees the candidate. Policy mutations with recomputed hashes and
emitted dimension/offset/UnitsMap/symbol mutations must fail separate checks.

Before changing generated simulation sources, the overlay requires exactly one
candidate table definition for every selected symbol and rejects missing,
unexpected or duplicate tables. Forward declarations do not count as definitions.
An invalid candidate raises `template candidate table definitions mismatch` at
installation; no overlay source or success evidence is written. A separate link
control still proves that renamed legacy definitions cannot satisfy a missing
candidate table.

Structured template fields start with `size=0` and `attr=NULL`, as in legacy ICG.
Their type-name strings use the child's cached first-use symbol. The guarded
initializer calls the real `MemoryManager::add_attr_info` for each structured row,
which finds the exported size, table and C initializer and recursively initializes
the child. The guard is set before lookup and preserves legacy repeated-call
behavior. Generated static assertions check native structured size, offset and
array shape independently of that dynamic initialization.

The configured [structured comparison](../icg_baseline/template_structured.py)
adds the outer `TTT1<Foo<int>, Foo<double[2]>[3]>` table. It compiles complete legacy
and candidate sources in separate executables linked to actual Trick archives.
Native checks cover five tables, eight fields, nine I/O exclusions, zero/null
preinitialization state, resolved child sizes/pointers and initialization guards.
Missing registration, wrong child lookup, premature size initialization, an absent
guard and a missing child export must fail at the expected runtime/link stage.
The simulation overlay replaces all five tables and repeats nonzero nested
checkpoint restoration through MemoryManager. Every compiler lane additionally
compiles both complete structured sources; the linked MemoryManager comparison is
currently the configured Linux lane.

These fragments do not emit ordinary containing-record tables, template lifecycle
helpers, STL callbacks or global template registries. Other metadata, lifecycle,
registration and bindings in the configured simulation remain legacy-generated.

## Failure and incremental behavior

The complete source is validated and rendered before publication. The writer
uses a temporary sibling and atomic replacement, retaining the existing inode and
mtime when bytes are unchanged. Errors produce stderr, a nonzero exit, and no
stdout or new candidate. An earlier successful output is left untouched on
failure; callers must honor the exit status. Input-file and symlink output targets
are refused. This is one-file atomic output, not a build cache or multiprocess
generation scheduler.

## Independent evidence

```sh
python tools/icg_baseline/differential.py \
  --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --output build/emitter-evidence
python tools/icg_baseline/enum_metadata.py \
  --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --output build/enum-evidence
python tools/icg_baseline/array_metadata.py \
  --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --output build/array-evidence
ctest --test-dir build/icg-extract --output-on-failure
```

The differential runner keeps immutable captured legacy sources and compiles
candidate sources in separate executables. It compares both against the existing
independent native layout/enum probes: six record tables/sizes, six fields, two
enum tables, sentinels, UnitsMap values, and entry-point results. A separate
translation unit references C-linkage tables, wrappers, and size functions, so a
same-translation-unit call cannot conceal missing C symbols. Commands, source,
compiler/dependency hashes, raw output, and observations are retained. A success
report is published only after all requested cases compare successfully.

The separate [enum corpus](../icg_baseline/enums/README.md) adds ten tables and
19 enumerators, including scoped enums, aliases, an empty enum, global/inline
namespace/record scopes and signed/unsigned underlying types. Legacy labels omit
the enum's own scope, retained with a policy diagnostic. Separate rejection
evidence compiles legacy unsigned-char/short values against native C++ and requires
policy to reject their sign-extension mismatch without publishing a candidate.
On Clang, only the legacy lane relaxes the `-Werror` promotion for
`-Winline-namespace-reopened-noninline`; the original source and warning are
retained. The candidate lane keeps full warnings-as-errors.

The [array corpus](../icg_baseline/arrays/README.md) adds two records and nine
fields, including six arrays. Independent `std::extent`/`sizeof`/`offsetof`
observations check dimensions, element size and total storage. Mutation tests
catch swapped dimensions with equal total size, changed ranks/extents/index
starts, unused index data, wrong element sizes/offsets, annotations and UnitsMap
keys. Private-array access uses the same exact-friend compile controls.

`icg_emit_integration` is part of the existing LLVM 17–23 Linux/macOS and GCC
8.5/12 CTest lanes. It also compiles all I/O combinations, unit aliases and `--`
modifiers, escaped descriptions, and an actual `TRICK_ICG` friend macro in global
and inline-namespace scopes. Removing the exact friendship makes the generated
member-access expression fail compilation; wrong-name and wrong-overload friends
do not authorize it. Mutated offsets, bitfield widths, enum values, units, I/O,
modifiers, enum labels/aliases/order, omitted fields/tables/entry points, incorrect
C++ linkage, and sentinels must
fail. Rehashed policy
mutations, changed source files, unsupported requests, and incremental writes
are tested independently of the emitter's expected output text.

Run the configured integration suites with their actual extractor and C++ compiler:

```sh
ctest --test-dir build/icg-extract -R 'icg_(emit|policy)_integration' --output-on-failure
python tools/icg_emit/test_emit.py \
  --extractor build/icg-extract/trick-icg-extract --compiler /usr/bin/g++ -v
```

Plain `python -m unittest discover -s tools/icg_emit` intentionally exits nonzero
with these instructions: it cannot run the integration suite without native tools.
The optional lifecycle sanitizer check remains a separate configured Linux lane.

The [common scalar corpus](../icg_baseline/scalars/README.md) adds two records and
13 fields with `bool`, `char`, `float`, `long`, arrays and aliases. Seven mutations
must fail compiled comparisons. The configured Linux gate links separate legacy
and candidate programs against real Trick archives and compares two complete
MemoryManager checkpoint round trips, including 64-bit integer limits, boolean
arrays, character strings and hexadecimal float extremes/subnormals/negative zero.
It requires three runtime mutations to fail at execution. The shared scalar policy
also has template-table and lifecycle-construction checks on every compiler lane.

Next characterize the remaining integer/character widths and signedness variants,
then template enum arguments/member rows and pointer/reference storage. General
annotations, inheritance, broader template/STL emission, and lifecycle
exception/ownership handling remain subsequent milestones.
