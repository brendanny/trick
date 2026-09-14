# Enum pointer conformance

Policy v15 / emitter v14 admit one unqualified pointer indirection to the named,
nonempty 32-bit `int`/`unsigned int` enums already supported as ordinary fields.
Aliases and fixed arrays of enum pointers are included. The fixture and three
content-addressed cold/warm/forced snapshots are fingerprinted against unchanged
production legacy ICG; all earlier reference bytes remain unchanged.

| Evidence | Coverage |
| --- | --- |
| Records | `EnumPointerModel`, `enum_pointer::Targets` |
| Field rows | 12: six enum-pointer rows, four enum-value/array rows, two integers |
| Native storage | 11 pointer locations, ten enum values and two integer values |
| Enum metadata | Three tables and eight labels; signed/unscoped, signed/scoped, unsigned/scoped |
| Pointer shapes | Scalars, typedefs, a three-element array and a two-by-two typedef matrix |
| Metadata controls | Eleven mutations, each required to fail at a designated link/run/comparison stage |
| Runtime controls | Seven mutations, each required to reach the readback assertion |
| Checkpoints | Byte-identical compact and expanded output; native value and address restoration |

`enum_pointer_metadata.py` specifies offsets, types, array extents, labels and
annotations independently of generation policy. Both legacy and candidate compile
with warnings as errors, link the actual Trick runtime and execute against native
member observations. Pointer metadata stores the enum name and resolved enum size;
physical storage contains eight-byte pointers. Fixed extents precede the final
zero pointer index, so at most seven outer dimensions fit `TRICK_MAX_INDEX`.

Every enum row starts with size zero and null metadata. The probe verifies those
initial values, calls the exported C initializer twice, checks exact enum table
addresses, and requires a guard against repeated initialization. Private-field
numeric metadata remains separate from permission to emit C++ member expressions.

The runtime probe registers both native records with the real MemoryManager and
checks all eight enumerator lookups. It saves shared targets, interior array
elements, null pointers and a pointer to the model's own enum field. Every pointer
location and every value is changed before readback. Equality uses native pointer
identity and typed enum values, not textual addresses or copied expected output.
Checkpoints contain symbolic enum names, the first label for duplicate values,
and numeric fallback for unnamed values. Both executables must produce identical
checkpoint bytes and normalized observations across two passes.

Metadata mutations remove registration, set size before initialization, select a
wrong enum table, remove the initializer guard, substitute pointer size for enum
size, change pointer extent/rank/array shape, hide an enum size export, rename an
enumerator and clear unsigned modifiers. Compilation failures do not satisfy
run/comparison controls. Runtime controls truncate enum size, disable pointer or
pointer-array checkpoint I/O, disable target-array I/O, omit restore, corrupt an
alias and replace a restored null. Every control must reach the specific failed
readback assertion; timeouts and unrelated failures cannot count as success.

Ignored/unselected enum definitions, conflicting checkpoint labels, qualifiers,
record-nested or inline/anonymous namespace enums, empty/opaque definitions,
other underlying widths and values outside the existing signed `ENUM_ATTR.int`
contract fail closed. Multiple indirection, pointer-to-array/function and record
pointers remain separate work. The template and lifecycle profiles do not admit
enum pointer fields. This metadata does not allocate, own, resize or destroy targets;
managed allocation, executive restart and SWIG ownership are not covered here.

```sh
python tools/icg_baseline/legacy.py --build-dir build/legacy-baseline \
  --manifest tools/icg_baseline/enum_pointers/corpus.json \
  --udunits-xml /usr/share/xml/udunits/udunits2.xml \
  --output build/enum-pointer-reference-evidence \
  --reference tools/icg_baseline/enum_pointers/reference
# Both comparison commands require a configured Trick runtime.
python tools/icg_baseline/enum_pointer_metadata.py \
  --extractor build/icg-extract/trick-icg-extract --compiler g++ \
  --output build/enum-pointer-metadata
python tools/icg_baseline/enum_pointer_runtime.py \
  --extractor build/icg-extract/trick-icg-extract --compiler g++ \
  --output build/enum-pointer-runtime
```

Use `--root /path/to/configured/trick` if the runtime archives are in another
checkout. Evidence preserves compiler/link/run commands, logs, facts, resolved
policy, candidate source, observations, checkpoints and mutation outcomes. CTest
compiles the complete legacy and candidate sources on every compiler lane and
checks policy replay, dependencies, access and rejection boundaries. CI separately
reproduces the legacy snapshots and executes the configured metadata/runtime gates.
