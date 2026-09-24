# B1: explicit ICG output contract

Predecessor: A5. Opt in with `trick-ICG --output-root <directory> <header>`.
This works with both native CMake and legacy builds of ICG. `-o` and
`--output-root` are mutually exclusive. Existing callers retain their layout.

The caller owns a dedicated directory per invocation and must serialize writers.
ICG writes all metadata, maps, SIE fragments and temporary files there. Metadata
paths are `io/<canonical absolute header path>.cpp`, retaining the header's
extension. This distinguishes duplicate ER7 basenames and `.h`/`.hh` pairs.
Paths therefore change when the checkout moves; this is a build-tree interface,
not an installed or reproducible-path SDK format.

Every invocation regenerates metadata, even when the direct header is unchanged.
The build system decides when to invoke ICG using `dependencies.d`, a GCC-style
depfile targeting `generation.stamp`. It includes all files read by Clang,
including transitive and system headers. Spaces and Make metacharacters are
escaped. Newlines in paths are rejected.

`manifest.json` version 1 lists header/output pairs, all generated data outputs,
and dependencies. `class_map.cpp`, `extern_init_attr.h`, `classes.resource`, and
`dependencies.d` exist even for an empty translation unit. SIE fragments are
reset on each invocation. Old unreferenced metadata files can remain in the
output directory; consumers must use the manifest, never a directory glob.

ICG invalidates the previous manifest and stamp before parsing. Parse errors or
output errors return nonzero; only a completed invocation publishes the new
manifest and then the stamp. Partial data files can remain after failure and must
not be consumed without a successful stamp. No recursive source or output
cleanup is performed. This is not an atomic replacement of the whole directory.

Acceptance: configure with `TRICK_BUILD_ICG=ON`, build, then run
`ctest --test-dir <build> -R '^icg\.' --output-on-failure`. The output-contract test
covers basename/extension collisions, transitive dependencies, spaces, deleted
outputs, repeat SIE generation, parse failure after success, and empty input.
B4 connects this interface to the CMake dependency graph.

Behavior difference BD-06: explicit invocation always regenerates instead of
checking only each direct header's timestamp. Source-relative legacy Make output
is suppressed in this mode. Platform qualification is recorded in the B-stack
validation record as results become available.

## Generator interface v1 (including icg2)

This is the build-system contract, independent of the frontend implementation.
An icg2 replacement must implement these rules and pass `icg.outputs`,
`icg.core_manifest`, and the regeneration checks before replacing `Trick::ICG`.
CMake consumers must not inspect generator internals or discover outputs by glob.

- Inputs: one umbrella header, `-I`/`-isystem` include paths, `-D` definitions,
  `--icg-std`, `--icg-gnu-version`, `--icg-strict-errors`, repeated
  `--icg-system-dir`, `-sim_services`, `--output-root`, and optional `--output-inventory`.
  The output root must be dedicated to one invocation/configuration. The inventory
  is UTF-8, one canonical absolute header path per line, with blank lines ignored.
- For each inventory header, produce `io<canonical-absolute-header-path>.cpp`.
  Preserve the original extension. A header with no metadata still gets a valid
  empty C++ source; generating an undeclared header is an error. Without an
  inventory, list only headers for which metadata was generated.
- Produce `class_map.cpp`, `extern_init_attr.h`, and `classes.resource` with the
  existing Trick runtime registration/attribute ABI. Core maps export
  `populate_sim_services_class_map` and `populate_sim_services_enum_map`.
- `dependencies.d` is a GCC-style depfile whose target is the absolute
  `generation.stamp` path and whose prerequisites include every file read by the
  frontend. Escape Make metacharacters; reject newline-containing paths.
- `manifest.json` is UTF-8 JSON with integer `version: 1`; `headers` is an array
  of `{ "header": "/absolute/Header.hh", "output": "/root/io/absolute/Header.hh.cpp" }`;
  `outputs` lists all metadata C++ files, both maps, the SIE fragment and depfile;
  `dependencies` lists canonical absolute input paths. `outputs` excludes the
  manifest and stamp. Array order is not part of the interface. Consumers ignore
  unknown fields but reject unsupported contract versions.
- Remove previous success records before generation. Return nonzero on parse,
  inventory, or I/O failure and leave no success stamp. Publish the manifest by
  rename after closing all outputs, then write the stamp last. The stamp's
  contents are opaque to consumers. A caller must also remove old success records
  before launching a generator that could fail during process startup.
- Never write outside the output root in explicit-output mode. Leftover files
  absent from the manifest are not outputs and must not be compiled. The caller
  serializes writers and supplies declared CMake dependencies; the generator
  performs no timestamp-based short circuit.

Changing output layout must not change frontend dialect, include ordering, or
metadata semantics. A future generator may change its frontend policy, but must
declare that separately and qualify compiler-conditioned headers. See
[the native ICG policy and compatibility limit](core-codegen.md).
