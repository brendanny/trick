# LibTooling extractor: structural model slice

`trick-icg-extract` implements step 3 and the core structural-model portion of
step 4 of the [rewrite sequence](../../../docs/developer_docs/ICG_REWRITE_PLAN.md#20-suggested-first-pr-sequence).
It is a standalone development target, **not** a replacement for `trick-ICG`.
The production build, runtime ABI, and generated metadata are unchanged.

## Build and test

Requires matching LLVM/Clang **17** development packages and resource headers,
CMake 3.20+, a C++17 host compiler, and Python 3.11+ with
`jsonschema>=4.18,<5` for the integration tests. CMake uses the LLVM and Clang
configuration packages and their imported targets, and queries that installation's
`clang -print-resource-dir`. This first adapter deliberately rejects other LLVM
major versions until tested; it does not lower any of the plan's toolchain floors.

```sh
python3 -m pip install 'jsonschema>=4.18,<5'
cmake -S trick_source/codegen/TrickCodeGen -B build/icg-extract \
  -DLLVM_DIR=/usr/lib/llvm-17/lib/cmake/llvm \
  -DPython3_EXECUTABLE="$(command -v python3)" -DCMAKE_BUILD_TYPE=Release
cmake --build build/icg-extract --parallel 2
ctest --test-dir build/icg-extract --output-on-failure
build/icg-extract/trick-icg-extract \
  trick_source/codegen/TrickCodeGen/tests/fixtures/record.hh -- \
  > build/icg-extract/record.json
python3 tools/icg_schema/validate.py \
  --schema trick_source/codegen/TrickCodeGen/ir/extracted-facts.schema.json \
  build/icg-extract/record.json
```

On macOS, install [`llvm@17`](https://formulae.brew.sh/formula/llvm@17) and pass
`-DLLVM_DIR="$(brew --prefix llvm@17)/lib/cmake/llvm"`. The CI matrix builds and
tests Linux/macOS with Python 3.11/3.12. Two Rocky Linux 8 lanes also require GCC
8.5 and GCC 12, build against LLVM 17 with `-Werror`, and run the extractor suite.
The Rocky packages use the combined `clang-cpp` library. These host-build checks
do not complete the separate GCC layout/generated-operation conformance gate.

## Invocation contract

```text
trick-icg-extract [--source-root DIR] [--path-root NAME=DIR] [--diagnostics-format=json] HEADER -- [CLANG FLAGS]
```

Exactly one input and an explicit `--` are required. Relative paths are interpreted
against the process working directory. Arguments remain an argv vector; no shell
command is assembled or run. Clang is invoked in-process through a
[`FixedCompilationDatabase` and `ClangTool`](https://releases.llvm.org/17.0.1/tools/clang/docs/LibTooling.html).
The configured Clang executable provides driver identity and resource discovery,
not a subprocess parse.

The initial audited argument surface is:

- `-I`, `-isystem`, `-iquote`, `-D`, `-U`, `-include`, `-imacros`, `--sysroot`,
  `-isysroot`, `-target`, `--target`, each followed by a nonempty value that does
  not start with `-` (use `./-directory` for a directory beginning with a dash);
- joined `-Ipath`, `-Dname=value`, `-Uname`, `--sysroot=path`, `--target=triple`;
- `-std=c++17`, `-m32`, `-m64`, `-fno-exceptions`, `-fno-rtti`, and Clang `-W...`
  diagnostic controls (not `-Wl,`, `-Wa,`, or `-Wp,` driver forwarding).

The tool explicitly adds C++17, C++ input mode, syntax-only parsing, all-comment
parsing, the discovered resource directory, and diagnostic formatting controls.
Unknown warning names are errors by default. Headers are still parsed as the main
file; the tool disables only `-Wpragma-once-outside-header` to avoid that artificial
warning. Other warnings remain visible, and supplied flags may re-enable it.
The resulting driver argv, target,
working directory, frontend/extractor versions, and selected include/SDK environment
variables appear in provenance. Clang's normal driver-to-cc1 translation still
applies. No code-generation options are silently stripped: other options, response
files, compiler plugins, alternate dialects, and extra source inputs are rejected.
This is **not yet the GCC argument classifier** or a compilation-database reader.

Successful extraction writes one deterministic, schema-version-3 facts document
to stdout. Parse errors, unsupported declarations, and driver failures write no
facts and exit nonzero. Exit 2 means invalid invocation/input; exit 1 means a
frontend or extraction failure. Warnings remain visible and do not fail extraction
unless promoted by a supplied diagnostic flag.

By default diagnostics are human-readable on stderr. `--diagnostics-format=json`
writes a single stderr envelope containing `schema_version: 2`,
`document_kind: "trick.icg.diagnostics"`, `files`, and `diagnostics`, including on
failure. The file and diagnostic nodes use the same definitions as the facts
schema; source locations resolve against that envelope's files. Success also
includes the diagnostics in the facts. `CLANG_<numeric-id>` codes are tied to the
recorded Clang version; extractor codes such as `ICG_UNSUPPORTED_ARGUMENT` and
`ICG_UNSUPPORTED_DECLARATION` are stable. Machine output is not interleaved with
Clang's human warning/error-count summaries. Fix-it edits are not yet extracted.

## Implemented facts and deliberate limits

This slice starts with named records and aliases **in the main file**, and closes
their record/alias dependencies, including declarations in other headers. Nested
named records and aliases retain semantic and lexical parent links. Unreferenced
included declarations are not selected; referenced unsupported declarations fail
the whole extraction. This is dependency closure, not Trick selection policy.

For complete records it records size/alignment and traits, source-order fields,
access/mutability/qualifiers, frontend field offsets, raw comments and
`clang::annotate` payloads, stable USRs, and spelling/expansion source locations.
Forward declarations are folded into a single record node at its definition when
one exists in the translation unit. Otherwise the node is incomplete, with no
field facts, null size/alignment, and `INCOMPLETE_TYPE` layout capability. It does
not query Clang's layout or definition-only base APIs for incomplete records.
Per-redeclaration source/annotation history is not yet modeled; the selected
definition (or canonical forward declaration) supplies that node's source.
End locations for declaration ranges
are exclusive, following the final token; point diagnostics need not span a token.
No Trick annotation policy is applied. Size and offset units are bits, with the
target's character width supplied by Clang. Extents and layout quantities use JSON
numbers through `2^53-1`, then canonical decimal strings, preserving exact values
in readers that store JSON numbers as binary64. Null retains its unknown or
incomplete meaning. The extractor supports array extents through 64 bits.

The frontend adapter copies facts into owned values while the AST is alive.
Serialization occurs after the frontend action ends; no Clang object or borrowed
source buffer crosses that lifetime boundary. Object keys and node arrays are
sorted; fields, includes, diagnostics, and arguments retain semantic order.

`TypeNode` is a typed, frontend-independent value model. `TypeGraph` is a
translation-unit-local interner for builtin types, record references, typedef/using
aliases, pointers, lvalue/rvalue references, and fixed/incomplete arrays. Each array
node describes one dimension using scalar `extent` (null for incomplete arrays);
multidimensional arrays nest via `element_id`.
Thus an array of pointers and a pointer to an array have different edge order,
not just different display strings. Function/member-pointer/vector/dependent
types remain unsupported.

Type IDs hash kind, local CVR qualifiers, and structural child/declaration IDs
(normalized builtin names for leaf types), not rendered composite type strings.
Alias nodes reference their declaration; its `underlying_type_id` preserves the
next sugared type layer, while `canonical_id` links directly to the fully desugared
type. CVR qualifiers are local to a layer: `const int *` and `int *const` differ.
Array qualification is normalized onto its elements, including through aliases;
reference collapsing follows the frontend's semantic reference type. Tag keywords
and redundant parentheses do not create extra graph nodes. Display spelling is
diagnostic information, not a round-trip source representation or identity key.
When equivalent types intern to one node, the lexicographically smallest observed
spelling is retained. Per-use spelling is not modeled by this structural node.

Declaration IDs hash USRs, with forward declarations and definitions sharing one
node. A worklist extracts dependency declarations after type interning, permitting
self/mutually recursive record references without recursive field expansion.
Missing USRs and anonymous declarations are still rejected: the fallback identity
model and namespace contexts remain explicit follow-up work. Node IDs are opaque;
the extractor-version bump to 0.3.0 invalidates earlier evidence fingerprints.
Facts schema version 3 adds named file roots, scalar array extents, and exact
integer encoding to the structural invariants introduced in v2. The synthetic
minimal fixture is migrated; the reader rejects v1/v2 facts. The diagnostics
envelope advances to version 2 because its file nodes now require a root name.

Physical input files, their bytes' SHA-256 digests, and resolved include directives
are recorded through preprocessor callbacks. Forced includes are tracked as inputs
even when their directive comes from Clang's synthetic command-line buffer.
Only referenced included records/aliases enter the declaration graph. Every
physical file must match a named path root. `source` comes from `--source-root`
(default: current directory); `resource-dir` defaults to the matching Clang
installation. Repeat `--path-root NAME=DIR` for `sysroot`, `build`, or vendor roots.
Names match `[a-z][a-z0-9-]*`; directories must exist, resolve uniquely, and may
nest. The longest resolved directory prefix wins. Use the same root names and
relative file layout on each machine. For example:

```sh
trick-icg-extract --source-root "$PWD" \
  --path-root sysroot=/opt/sdk --path-root build="$PWD/build" \
  model.hh -- -isysroot /opt/sdk -I build
```

Root mappings classify paths; they do not add include paths or a compiler sysroot.
The sole exception is `--path-root resource-dir=DIR`, which also selects that
directory's Clang resource headers, allowing a matching SDK to be relocated.
An unmapped input produces `ICG_UNMAPPED_FILE` and no facts. Each path records its
`root` and relative `portable` value; file IDs hash that pair. Resolved symlinks
(including `/var` and `/private/var`) preserve identity. Source and resource header
relocations are exercised with real resource headers in the integration suite.
Original and real paths, root locations, arguments, and target provenance remain
available for diagnostics and evidence. Rooted identity removes machine path noise;
different OS headers and target layouts can still yield legitimate semantic differences.

Homebrew's libc++ wrappers live outside Clang's resource directory. When using
them, also pass `--path-root stdlib="$(brew --prefix llvm@17)/include/c++/v1"`.
Map the macOS SDK separately with `--path-root sysroot="$(xcrun --show-sdk-path)"`
when its headers are used. CTest supplies the matching LLVM installation's libc++
root to the integration runner explicitly; the extractor still rejects other
unmapped inputs.

`input_digest` is an **evidence fingerprint, not a production cache key**. It hashes
the deterministic document before inserting the digest, covering the recorded
arguments, environment, frontend facts, physical inputs, and exact paths. It is
not relocatable and does not capture all filesystem probes, volatile predefined
macros, or every possible environment influence. No cache is created or reused.

Inheritance, templates, namespaces, enums, bitfields, methods, friends, anonymous
records, and unsupported structural type kinds in the selected declaration closure
fail explicitly rather than producing apparently complete facts. Unsupported
members are collected across a record before it is rejected, so one run reports
all offending member locations while still publishing no partial facts. The graph
validator checks required/kind-specific edges, self-canonical targets, canonical
pointee/element consistency, alias targets, member ownership, incomplete layout,
and direct structural cycles. Record-reference cycles are valid; pointer/alias
type cycles with no intervening record declaration are not. It still does not
prove every invariant for not-yet-implemented schema kinds.

The checked-in `tests/fixtures/structured.hh` exercises aliases, recursive/header
records, arrays, and incomplete/reference types. CI captures both this and the
original `record.hh` output for inspection on Linux and macOS.

Next extend namespace/anonymous declaration identity and source coverage before
growing enum, bitfield, inheritance, and callable extraction. Legacy differential
baselines and the remaining Phase 0 gates still need
completion before any production switch.

## Python style

Install `python3 -m pip install -r tools/icg_requirements.txt`, then run:

```sh
ruff check tools/icg_baseline tools/icg_capability tools/icg_schema trick_source/codegen/TrickCodeGen/tests
ruff format --check tools/icg_baseline tools/icg_capability tools/icg_schema trick_source/codegen/TrickCodeGen/tests
```

`ruff.toml` requires Ruff 0.16.6 and preview formatting, matching the existing
repository style workflow. The ICG style workflow enforces these checks on branch
pushes as well as pull requests.
