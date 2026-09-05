# Extracted-facts schema validation

`validate.py` checks an IR document against the draft 2020-12 JSON Schema and
then checks graph invariants JSON Schema cannot express: unique file/type/
declaration IDs and valid file, type, declaration, include, source, parameter,
base, and template-argument references.

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
