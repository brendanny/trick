# Ordinary record pointer conformance

Policy v16 / emitter v15 cover single unqualified pointers to complete ordinary
named standard-layout structs/classes. This corpus captures unchanged production
legacy ICG in cold/warm/forced passes and preserves content-addressed output and
source fingerprints. No earlier reference bytes are modified.

The three records have twelve fields, including eight record-pointer rows. The
fixture covers global and namespace names, pointer aliases, fixed arrays, a
self-reference and mutual record dependencies. Pointer rows begin with size zero
and null metadata, then resolve the exact target ATTRIBUTES address and pointee
size through guarded MemoryManager initialization. The record still physically
stores an eight-byte pointer, including when its pointee is 16 or 24 bytes.

`record_pointer_metadata.py` checks manually audited offsets/types/shapes against
facts and executes both legacy and candidate metadata compiled with warnings as
errors. Nine mutations target registration, initial size, target identity,
repeated initialization, pointee size, pointer extent/rank, array shape and size
export linkage. Each must fail at its specified link/run/comparison stage.

`record_pointer_runtime.py` registers a model, three nodes and two peers with the
real MemoryManager. Two compact/expanded checkpoints preserve null, shared and
interior targets, a self-cycle, a two-node cycle and mutual Node/Peer links. All
values and pointer locations are changed before readback; native pointer equality
and typed values must be restored. Normalized observations and checkpoint bytes
must match legacy. Eight controls disable pointer/array/target checkpoint I/O,
omit restoration, or corrupt aliases, nulls, self-cycles and mutual cycles.

The policy rejects omitted/unselected dependencies, unsupported target fields,
incomplete records, unions, non-standard-layout pointees, inheritance/templates,
nested/anonymous/inline namespace types, qualifiers, deeper indirection and
pointers to arrays/functions. By-value ordinary record fields, managed allocation,
ownership/deletion, executive restart and SWIG remain separate work.

```sh
python tools/icg_baseline/legacy.py --build-dir build/legacy-baseline \
  --manifest tools/icg_baseline/record_pointers/corpus.json \
  --udunits-xml /usr/share/xml/udunits/udunits2.xml \
  --output build/record-pointer-reference-evidence \
  --reference tools/icg_baseline/record_pointers/reference
python tools/icg_baseline/record_pointer_runtime.py \
  --extractor build/icg-extract/trick-icg-extract --compiler g++ \
  --output build/record-pointer-runtime
```

The runtime command requires configured Trick archives; use `--root` for another
checkout. Evidence retains source, commands, logs, facts, resolved policy, native
observations, checkpoint bytes and mutation outcomes. CI reproduces references,
compiles metadata in CTest and runs the configured runtime comparison separately.
