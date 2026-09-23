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
B4 will connect this interface to the CMake dependency graph.

Behavior difference BD-06: explicit invocation always regenerates instead of
checking only each direct header's timestamp. Source-relative legacy Make output
is suppressed in this mode. Platform qualification is recorded in the B-stack
validation record as results become available.
