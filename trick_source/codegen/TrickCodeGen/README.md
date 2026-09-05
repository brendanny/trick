# First LibTooling extractor slice

`trick-icg-extract` implements step 3 of the [rewrite sequence](../../../docs/developer_docs/ICG_REWRITE_PLAN.md#20-suggested-first-implementation-sequence).
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
tests Linux/macOS with Python 3.11/3.12. GCC 8.5/12 host/layout conformance remains
a separate, uncompleted gate.

## Invocation contract

```text
trick-icg-extract [--source-root DIR] [--diagnostics-format=json] HEADER -- [CLANG FLAGS]
```

Exactly one input and an explicit `--` are required. Relative paths are interpreted
against the process working directory. Arguments remain an argv vector; no shell
command is assembled or run. Clang is invoked in-process through a
[`FixedCompilationDatabase` and `ClangTool`](https://releases.llvm.org/17.0.1/tools/clang/docs/LibTooling.html).
The configured Clang executable provides driver identity and resource discovery,
not a subprocess parse.

The initial audited argument surface is:

- `-I`, `-isystem`, `-iquote`, `-D`, `-U`, `-include`, `-imacros`, `--sysroot`,
  `-isysroot`, `-target`, `--target`, each followed by its value;
- joined `-Ipath`, `-Dname=value`, `-Uname`, `--sysroot=path`, `--target=triple`;
- `-std=c++17`, `-m32`, `-m64`, `-fno-exceptions`, `-fno-rtti`, and Clang `-W...`
  diagnostic controls (not `-Wl,`, `-Wa,`, or `-Wp,` driver forwarding).

The tool explicitly adds C++17, C++ input mode, syntax-only parsing, all-comment
parsing, the discovered resource directory, and diagnostic formatting controls.
Unknown warning names are errors by default. The resulting driver argv, target,
working directory, frontend/extractor versions, and selected include/SDK environment
variables appear in provenance. Clang's normal driver-to-cc1 translation still
applies. No code-generation options are silently stripped: other options, response
files, compiler plugins, alternate dialects, and extra source inputs are rejected.
This is **not yet the GCC argument classifier** or a compilation-database reader.

Successful extraction writes one deterministic, schema-version-1 facts document
to stdout. Parse errors, unsupported declarations, and driver failures write no
facts and exit nonzero. Exit 2 means invalid invocation/input; exit 1 means a
frontend or extraction failure. Warnings remain visible and do not fail extraction
unless promoted by a supplied diagnostic flag.

By default diagnostics are human-readable on stderr. `--diagnostics-format=json`
writes a single stderr envelope containing `schema_version: 1`,
`document_kind: "trick.icg.diagnostics"`, `files`, and `diagnostics`, including on
failure. The file and diagnostic nodes use the same definitions as the facts
schema; source locations resolve against that envelope's files. Success also
includes the diagnostics in the facts. `CLANG_<numeric-id>` codes are tied to the
recorded Clang version; extractor codes such as `ICG_UNSUPPORTED_ARGUMENT` and
`ICG_UNSUPPORTED_DECLARATION` are stable. Machine output is not interleaved with
Clang's human warning/error-count summaries. Fix-it edits are not yet extracted.

## Implemented facts and deliberate limits

This slice extracts complete named top-level structs/classes/unions **in the main
file**, with named builtin-typed, non-bitfield data members. It records record
size/alignment and traits, source-order fields, access/mutability/qualifiers,
frontend field offsets, raw comments and `clang::annotate` payloads, stable USRs,
and spelling/expansion source locations. End locations for declaration ranges
are exclusive, following the final token; point diagnostics need not span a token.
No Trick annotation policy is applied. Size and offset units are bits, with the
target's character width supplied by Clang.

The frontend adapter copies facts into owned JSON values while the AST is alive.
Serialization occurs after the frontend action ends; no Clang object or borrowed
source buffer crosses that lifetime boundary. Object keys and node arrays are
sorted; fields, includes, diagnostics, and arguments retain semantic order.
Declaration IDs hash USRs; builtin type IDs use spelling plus qualifiers and record
type IDs use record identity. Missing USRs are rejected in this limited slice,
not assigned an invented identity. The full fallback/structural identity model is
still step 4.

Physical input files, their bytes' SHA-256 digests, and resolved include directives
are recorded through preprocessor callbacks. Forced includes are tracked as inputs
even when their directive comes from Clang's synthetic command-line buffer.
Included declarations are outside this slice's extraction scope. `--source-root`
(default: current directory) makes contained physical paths portable relative to
that root. File IDs use those portable paths after resolving symlinks, so `/var`
and `/private/var` aliases do not change IDs. External paths remain absolute until
the multi-root model is implemented. Original and real paths remain available for
diagnostics; this is not yet path-normalized generator output.

`input_digest` is an **evidence fingerprint, not a production cache key**. It hashes
the deterministic document before inserting the digest, covering the recorded
arguments, environment, frontend facts, physical inputs, and exact paths. It is
not relocatable and does not capture all filesystem probes, volatile predefined
macros, or every possible environment influence. No cache is created or reused.

Inheritance, templates, namespaces, enums, aliases, pointers/references/arrays,
bitfields, methods, friends, nested/anonymous records, and forward declarations in
the main file fail explicitly rather than producing apparently complete facts.
The next slice should extend the structured type/declaration/file model and its
fixtures, then grow extraction coverage. Legacy differential baselines and the
remaining Phase 0 gates still need completion before any production switch.
