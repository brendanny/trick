# Enum template metadata and checkpoint evidence

Policy v12 / emitter v11 add named, nonempty enums backed by `int` or
`unsigned int` to the explicit `template-attributes` profile. Global enums and
enums in named non-inline namespaces are supported, including scoped enums,
aliases, fixed-array arguments, enum member arrays, and nested template storage.
The 15 builtin scalar bases are unchanged. Ordinary record enum fields,
enum lifecycle requests, other underlying types, enums nested in records or
templates, qualifiers and pointer/reference storage remain outside this increment.

## Legacy naming and dependency rules

The unchanged legacy generator retains the elaborated `enum` keyword in template
type spellings and separates adjacent closing brackets as `> >`. Both affect
first-use symbols and UnitsMap keys. Field type names retain C++ namespace
separators; enum table/size symbols replace those separators with underscores.

| Surface | Example |
|---|---|
| Template type / UnitsMap prefix | `EnumBox<enum enum_fixture::Mode>` |
| First-use record symbol | `EnumConsumers_namespaced_EnumBox_enum_enum_fixture__Mode_` |
| Enum field `type_name` | `enum_fixture::Mode` |
| Enum table | `enumenum_fixture__Mode` |
| Nested template type | `EnumBox<EnumBox<enum EnumState> >` |
| Nested first-use symbol | `EnumConsumers_nested_EnumBox_EnumBox_enum_EnumState___` |

The request identifies containing fields as before. The resolver records each
instance's `dependency_enum_ids` and includes those enum declarations with the
`ENUM_DEPENDENCY` rule. Dependencies come from template arguments and included
member storage; unrelated enums stay omitted. Each enum field records its
`enum_id`, canonical element type, C++ type, legacy spelling and dimensions.
Policy replay verifies the entire closure before rendering.

Enum dependencies follow the existing `ENUM_ATTR` value contract: values must fit
signed `int`, including unsigned enums. The template storage profile additionally
requires the audited 32-bit `int`/`unsigned int` ABI. Missing/ignored definitions,
unsupported scopes and storage widths fail explicitly. Conflicting values for
the same checkpoint label within the emitted dependency closure fail with
`ICG_POLICY_ENUM_LABEL`; identical label/value pairs are compatible. This matters
because legacy scoped-enum labels omit the enum's own name, and MemoryManager
searches labels across registered tables.

Generated enum member rows begin with `TRICK_ENUMERATED`, zero size and null
attributes, matching legacy. Guarded initializers call the actual
`MemoryManager::add_attr_info` to find the enum size export and table. Enum tables
retain source-order labels, duplicate values, signedness flags and sentinels.
Generated assertions check enum layout, signedness and enumerator values.

## Independent evidence

The fixture covers five template tables / 15 fields and three enum tables / eight
enumerators. It includes an alias used after the first consumer, namespace and
scoped enums, fixed-array arguments and nested structured storage. The containing
ordinary record is excluded from candidate generation. Three immutable
cold/warm/forced snapshots preserve the complete legacy output, including that
consumer's table, registry, SIE and build artifacts. Fingerprints identify the
exact capture inputs. Earlier fixtures and references are unchanged.

`template_enum_metadata.py` selects the five captured template blocks and the
three enum blocks. Manually specified names, offsets, types, shapes and enum rows
are independent of the generation policy. Separate legacy and candidate programs
compile at `-Werror`, link actual configured Trick archives, and execute native
layout/metadata comparisons. The probe checks exact enum-table pointers, zero
pre-init metadata, exported size functions, repeated initialization and the
initialization guard. No MemoryManager stubs are used.

Seven controls remove registration or the enum size export, initialize size too
early, select the wrong enum table, remove the init guard, corrupt a label, or
change unsigned enum flags. Each must fail at its designated link, execution or
comparison stage. A compile error or unrelated phase failure does not count.
Portable compiler lanes compile complete legacy and candidate objects and test
dependency selection, policy replay, label collisions and rejection boundaries.

`template_enum_runtime.py` registers native external objects with the real
MemoryManager. It verifies eight label lookups and two complete checkpoint passes
over all 84 enum elements, using compact and expanded arrays. Every element is
changed before restoration. Values include negative and maximum signed integers,
zero, duplicate-valued labels and unnamed numeric values. The first label for a
duplicate value must appear in the checkpoint. Full checkpoint bytes and restored
observations must agree between independent legacy and candidate programs.

Three further controls truncate the enum size, disable checkpoint I/O, or omit
restoration. Each must compile and reach a runtime value mismatch. Sources,
commands, archive hashes, observations, checkpoints and failure logs are retained;
the combined success report is written only after all controls pass. The
configured Linux workflow runs this gate alongside existing scalar, integer,
character, template, I/O and lifecycle comparisons.

## Reproduce

```sh
python tools/icg_baseline/legacy.py \
  --build-dir build/legacy-baseline \
  --manifest tools/icg_baseline/template_enums/corpus.json \
  --udunits-xml /usr/share/xml/udunits/udunits2.xml \
  --output build/template-enum-reference-evidence \
  --reference tools/icg_baseline/template_enums/reference
```

After configuring and building actual Trick core archives:

```sh
python tools/icg_baseline/template_enum_runtime.py \
  --root "$PWD" --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --output build/template-enum-runtime-evidence
```
