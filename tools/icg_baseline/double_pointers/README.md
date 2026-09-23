# Two-level builtin pointer conformance

Policy v17 / emitter v16 admit exactly two unqualified pointer levels ending in
any of the 15 supported builtin types. Aliases and up to six fixed outer array
dimensions fit the eight-index ABI. Single enum/record pointers retain their
existing profiles; enum/record double pointers, three or more pointer levels,
qualifiers at any level, pointers to arrays/functions and reference types remain
rejected. Lifecycle and template profiles do not acquire pointer support.

Three cold/warm/forced snapshots capture unchanged production legacy ICG. The
19-row fixture contains 15 builtin double pointers, an alias, a fixed pointer
matrix, an adjacent scalar and an ordinary pointer used as an in-record slot.
Each double-pointer row uses the terminal builtin's type code/size and two final
zero indices, while its physical storage is an eight-byte pointer. The independent
native checker derives depth and terminal size from C++ types and checks offsets,
array shape, table defaults and UnitsMap values against manually audited rows.

The runtime probe registers 15 arrays of three terminal values and 15 arrays of
three pointer slots with the real MemoryManager. It checks every value, every
intermediate slot and every model pointer after compact and expanded checkpoint
readback. All tracked locations must change before restoration. Cases include
null at either level, two slots sharing a terminal target, two outer pointers
sharing a slot, interior array targets, and a slot inside the model pointing to
its own scalar. Checkpoint bytes and normalized observations must match legacy.

Legacy preserves outer slot identity for `char**` and `signed char**`, but restores
the terminal character pointers as newly allocated strings. Terminal aliases are
not preserved for those two types. The probe explicitly requires this behavior;
all other terminal pointer types require exact native address restoration.
`char16_t` keeps legacy's unsigned-short mapping. These are metadata/checkpoint
semantics, not a new target allocation, ownership or deletion API.

Eight metadata controls change terminal size/type, outer/inner pointer extent,
rank, offset, array shape or units. Ten runtime controls disable outer-pointer
or matrix checkpoint I/O, omit restore, or corrupt outer aliases/nulls, inner
aliases/nulls, terminal scalar values, terminal strings or terminal-string aliases. Controls must reach
native execution and the designated comparison/readback failure; compiler errors,
timeouts and unrelated failures do not satisfy the gate.

```sh
python tools/icg_baseline/legacy.py --build-dir build/legacy-baseline \
  --manifest tools/icg_baseline/double_pointers/corpus.json \
  --udunits-xml /usr/share/xml/udunits/udunits2.xml \
  --output build/double-pointer-reference-evidence \
  --reference tools/icg_baseline/double_pointers/reference
python tools/icg_baseline/double_pointer_runtime.py \
  --extractor build/icg-extract/trick-icg-extract --compiler g++ \
  --output build/double-pointer-runtime
```

The runtime command needs configured Trick archives; `--trick-root` selects
another checkout. CI reproduces snapshots, compiles and executes the metadata
checks across compiler lanes, and runs the configured checkpoint gate separately.
