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

Facts schema version 3 adds named path roots, scalar `extent` (null for incomplete
arrays), and exact layout integers to these structural rules. Numbers through
`2^53-1` are numeric; larger quantities are canonical decimal strings. Path roots
must exist in provenance, portable paths must be relative and canonical, and no
two file nodes may represent the same root/path pair. Version 1/2 facts are
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
