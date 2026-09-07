# Extracted-facts schema validation

`validate.py` checks an IR document against the draft 2020-12 JSON Schema and
then checks graph invariants JSON Schema cannot express: unique file/type/
declaration IDs and valid file, type, declaration, include, source, parameter,
base, enumerator, and template-argument references. For the implemented structural
slice it additionally checks required/kind-specific type edges, canonical targets
and their pointee/element relationships, alias targets, record/field ownership,
incomplete-record layout, and direct type cycles. Each array node represents one
dimension, with CVR qualification on its element. Recursive record references are
valid; a pointer/alias graph cannot refer to itself without a record boundary.

Facts schema version 10 retains validation of the normalized `graph_digest` independently of
the extractor. `graph_digest_version` and `identity_version` are required and
currently 1; older facts versions and unknown fingerprint/identity versions fail.
The projection retains all graph facts except file `path.spelled`/`path.real`,
sorts top-level node arrays by ID, and excludes diagnostics and other provenance.
It is output-equivalence evidence, not a production cache key or ABI assertion.

Known capability prerequisites are checked in both directions: only bitfields
may carry `BITFIELD_NOT_ADDRESSABLE`, attached to `field-address`, and all
bitfields must state that unsupported capability. Record-layout capabilities
must agree with completeness (`supported / SUPPORTED` or
`unknown / INCOMPLETE_TYPE`). Capability names must be unique and these known
capabilities may not be placed on the wrong declaration kind.

Version 10 separates semantic `language_linkage` (`c`, `c++`, or `none`) from
the ABI calling convention. Member callables cannot have C language linkage.
Callable parameter defaults retain effective `has_default` evidence and classify
its `default_origin` as written or inherited. Validation checks that a default is
written at most once, inherited evidence matches its origin, and an effective
default never disappears along the redeclaration chain. A defaulted special member
may also be implicitly deleted; those facts are deliberately not exclusive.

Version 9 adds class-template signatures and concrete specialization validation.
Primary and partial pattern nodes must explicitly classify their dependent bodies
as `unknown / DEPENDENT_TEMPLATE_PATTERN`, with no instantiated fields/layout.
Parameter depths/indices, nested signatures, and default/source evidence are
checked. Concrete record instances link a primary and canonical argument slots;
packs retain an array within one slot, including empty packs. Type, integral,
null-pointer, and class-template arguments have exclusive shapes. Integral decimal
strings are checked against their recorded width/signedness and known integral
or enum type facts. Selected primary/partial patterns and deduced arguments must
agree with specialization state and parameter kinds. Primary instantiation
arguments must match the specialization's arguments. Source identity is required
for instances and propagates to members. Template ownership is bidirectional,
including nested specializations absent from Clang's lexical member iterator.
These checks do not repeat C++ deduction, prove a partial pattern matches its
arguments, or establish validity of a dependent body or a generated operation.

Version 7 added explicit non-template callable validation: ownership,
kind-specific flags and return types, adjusted/original parameter relationships,
redeclaration signatures and evidence, all-or-nothing defaults, and override
targets in base records. Constructors/operators retain overload-aware identities.
Linkage is explicit, and translation-unit-local callables require source identity.
Record `callable_ids` are separate from nested type ownership. Six fixed-order
special-member summaries distinguish implicit, user-declared, suppressed, and
incomplete/unknown states; explicit slots must link matching owned callables,
and only implicit slots may contain implicit deletion/triviality/virtual/noexcept
facts. An implicit destructor override refers to its owning record. These checks
do not establish overload resolution, covariance legality, implicit callable
signatures, constructibility, or permission to generate an operation.

Version 6 source-ordered direct base edges, alias-preserving
base types, effective/written access, complete non-union targets, and acyclic
inheritance remain validated. Nonvirtual edges require fixed offsets; virtual edges must have null
offsets. Each record's sorted, unique `virtual_base_offsets` table must match the
exact transitive virtual-base set and describes only that record as a complete
most-derived object. Record data/nonvirtual sizes and nonvirtual alignment are
required, bounded frontend layout quantities; incomplete records claim none.
Repeated nonvirtual paths are not flattened. The validator does not infer layout
by adding complete-object base sizes, which would mishandle empty bases and reused
tail padding.

Version 5 added enum type/declaration validation, exact decimal-string
enumerator values and annotations, complete-vs-defined opaque enum rules, and
bitfield width/layout/non-addressability invariants. It validates integral
underlying types, fixed builtin signedness (plain char/wchar_t remain target facts),
value ranges, unique enumerator names, source references, and nested enum ownership.
Bitfield widths may exceed their underlying type but not their owning record;
zero-width separators must be unnamed. These are frontend facts, not generated
GCC accessor or runtime conformance results.

Version 4 namespace/namespace-alias nodes, source-vs-USR identity,
and anonymous record/storage facts remain supported. Validation checks bidirectional namespace and
nested-record ownership, namespace block source references, alias targets and
cycles, context cycles, and source-identity propagation. Anonymous storage must
refer to an unnamed record nested in the same parent. Namespace child IDs are
sorted and include only selected dependencies, not all declarations in a header.

Named path roots, scalar `extent` (null for incomplete arrays), and exact layout
integers retain the v3 representation. Numbers through
`2^53-1` are numeric; larger quantities are canonical decimal strings. Path roots
must exist in provenance, portable paths must be relative and canonical, and no
two file nodes may represent the same root/path pair. Version 1 through 9 facts are
rejected; the synthetic minimal fixture has been migrated. These checks are not
complete semantic validation of all future schema kinds, Clang/GCC layout
agreement, or legacy-printability policy. The independent diagnostics envelope
uses version 2, with the same rooted file shape.

The validator is development tooling and currently depends on
`jsonschema>=4.18,<5`. The future `trick_codegen` reader will own production
validation and diagnostics.

```sh
python3 -m pip install 'jsonschema>=4.18,<5'
python3 -m unittest discover -s tools/icg_schema -v
python3 tools/icg_schema/validate.py \
  --schema trick_source/codegen/TrickCodeGen/ir/extracted-facts.schema.json \
  trick_source/codegen/TrickCodeGen/ir/fixtures/minimal-record.json
```
