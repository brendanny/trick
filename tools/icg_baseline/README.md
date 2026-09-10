# ICG rewrite: Phase 0 evidence tooling

This implements evidence tooling for the
[ICG rewrite plan](../../docs/developer_docs/ICG_REWRITE_PLAN.md), section 20,
item 1. It collects existing codegen output independently of the new extractor.
It is development tooling, requires Python 3.11+, and uses only the standard
library. It does not participate in the production build.

## Run the harness tests

From the repository root:

```sh
python3 -m unittest discover -s tools/icg_baseline -v
python3 tools/icg_baseline/baseline.py list
```

`test_baseline.py` and the capture plumbing tests use explicitly synthetic text.
The reference integrity tests in `test_legacy.py` additionally inspect captured
legacy output. Neither constitutes semantic parity or runtime validation.

## Reproduce the isolated legacy header evidence

The [legacy reference corpus](legacy/README.md) captures four existing Trick
regression headers with the unchanged `Interface_Code_Gen` implementation. It
does not need a configured simulation or a full Trick installation:

```sh
cmake -S tools/icg_baseline/legacy -B /tmp/trick-legacy-build \
  -DLLVM_DIR=/usr/lib/llvm-17/lib/cmake/llvm -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/trick-legacy-build --parallel 2
python3 tools/icg_baseline/legacy.py \
  --build-dir /tmp/trick-legacy-build \
  --udunits-xml /usr/share/xml/udunits/udunits2.xml \
  --output /tmp/trick-legacy-evidence \
  --reference tools/icg_baseline/legacy/reference
```

This needs LLVM/Clang 17 development libraries, UDUNITS-2 development files and
its XML database, CMake 3.20+, Perl, a C++17 compiler, and Python 3.11+.
The reproducible CI package selections are in `icg-baseline.yml`. Non-system
UDUNITS installations can set CMake's `UDUNITS_INCLUDE_DIR` and `UDUNITS_LIBRARY`.
The evidence build writes `trick-ICG-baseline`, never `bin/trick-ICG`. It uses the
existing source files without patches, and the production build is unchanged.

The runner creates fresh workspaces beneath a **new** output directory, with one
translation unit including each selected header. It then invokes legacy ICG
with `-m --icg-std=c++17`, repeats without `--force`, and repeats with `--force`.
The clean-workspace pass is called `cold`; this does not flush OS caches.
Ambient `TRICK_*` policy and compiler include-path variables are removed; the
runner sets `TRICK_HOME`, the selected `--compiler` (default `c++`), locale, and
the explicit UDUNITS XML path. Compiler paths must be shell-safe because legacy
ICG discovers standard include paths through a shell. Use a checkout path without
spaces; this limitation comes from the legacy `trick-gte` invocation.

`summary.json` records source and binary digests, source revision/status, compiler
version, build-file digests, selected environment, XML sibling digests, and pass
results. The full CMake cache, compile commands, and build configuration are
copied under `build/`. Each pass has the usual snapshot sidecars, raw logs,
timing/resource measurements, and churn report. Workspaces remain available for
inspection. These fingerprints do not cover all transitive system inputs or
prove that an arbitrary supplied binary was built from the current checkout;
CI builds it immediately before capture and uploads the installed package list.

The warm and forced comparisons are observations, **not assumed equality gates**:
the unchanged standalone legacy generator appends to `classes.resource` on a
forced run. Diffs are saved as `cold-warm.diff` and `cold-forced.diff`. With
`--reference`, every pass is separately compared with its checked-in counterpart;
`*-reference.diff` records discrepancies. Exit `0` means complete capture and
(when requested) reference equality, `1` means a reference difference, `2` means
invalid/incomplete evidence, and `3` means a failed ICG command. No failed command
publishes a snapshot from stale output. A capture without `--reference` is not a
regression pass. Existing output directories are never overwritten or cleaned.

This is a Linux x86-64 / LLVM 17 header-level reference, not a macOS, GCC 8.5/12,
full `trick-CP`, SWIG, runtime, or representative-performance baseline. The
simulation workflow below remains the separate full-build evidence path.

## Collect an existing simulation

For the automated full-build and runtime path, see
[configured template and I/O simulation evidence](runtime/README.md). It captures cold,
warm, forced, and rebuilt output and checks Python field access plus checkpoint
readback using the actual linked simulations. The I/O case also checks permission
rejections, checkpoint output selection, and units conversion. Other cases can use the general
commands below.

First configure and build this checkout of Trick using its normal installation
instructions. Record the exact installed LLVM, GCC, Python, Java, and SWIG package
versions with the evidence. The rewrite target is LLVM 17, GCC 8.5 and GCC 12,
Python 3.11, Java 17, and transitional SWIG 4.1. This increment does not change
the existing configure requirements or claim that those combinations pass.

In a fresh checkout with no generated simulation artifacts, run:

```sh
python3 tools/icg_baseline/baseline.py run \
  --case io --output /tmp/icg-io-cold --stage build --label cold -- \
  ../../bin/trick-CP TRICK_VERBOSE_BUILD=1

python3 tools/icg_baseline/baseline.py run \
  --case io --output /tmp/icg-io-warm --stage build --label warm -- \
  ../../bin/trick-CP TRICK_VERBOSE_BUILD=1

python3 tools/icg_baseline/baseline.py compare \
  /tmp/icg-io-cold/snapshot.json /tmp/icg-io-warm/snapshot.json
```

Each command executes in the selected simulation directory. The command above is
relative to that directory; a command supplied as an absolute path also works.
Pass arguments after `--` as separate shell-quoted arguments. The runner forwards
the array directly to `subprocess`, without evaluating it as shell code. The
legacy commands can themselves invoke Make, Perl, and shells as usual.

Output directories must be new and outside the measured simulation. No automatic
cleanup occurs: `--label cold` describes the setup, it does not clean files or
flush OS caches. A second identical run is a warm/no-op observation, not an
assumed zero-churn result. Repeat measurements into separate directories before
computing percentiles. A whole `trick-CP` build is labeled `build`; it must not be
reported as isolated extractor time.

To measure the existing ICG Make target after a successful simulation build:

```sh
python3 tools/icg_baseline/baseline.py run \
  --case io --output /tmp/icg-io-force --stage icg --label forced -- \
  make force_ICG TRICK_VERBOSE_BUILD=1
```

This measures the Make target including its startup and any prerequisites that
Make updates. For a truly isolated stage, supply the exact command from the
verbose build log (including all flags), and use the stage label accordingly.
The manifest requires the common simulation codegen outputs, so isolated-stage
measurements need an already prepared simulation. Label generated-source compile
and link commands separately; do not infer their times by subtracting unrelated
build runs.

To snapshot existing outputs without executing any command:

```sh
python3 tools/icg_baseline/baseline.py capture \
  --case templates --extractor /tmp/icg-extract/trick-icg-extract \
  --output /tmp/icg-templates-existing
```

`--root PATH` and `--manifest FILE` are global options placed before the subcommand.
An additional corpus manifest can select other in-checkout simulations and
artifact patterns. Case directories must contain `S_define`; artifact globs must
stay inside that directory. Output under alternate `trick-ICG -o` locations and
external/trickified projects needs an explicit manifest extension.

## Evidence format and interpretation

| File | Contents |
|---|---|
| `snapshot.json` | Versioned artifact specification, normalized filenames, groups, and content digests; no timestamps or inline artifact text |
| `objects/<sha256>.txt` | Complete normalized UTF-8 artifact text, addressed by its digest; identical content shares one sidecar |
| `report.json` | Git revision/status, tracked simulation input digests, manifest digest, host/Python, selected environment values, output bytes/files, raw digests/mtimes, command status and measurements |
| `stdout.log`, `stderr.log` | Unmodified command output, created by `run` only |

`run` measures wall time, user/system CPU, and the OS child-process RSS high-water
mark in bytes. Each measurement uses a fresh worker to avoid inheriting earlier
children's resource accounting. Linux and macOS are supported for measurement.
RSS is **not summed concurrent process memory**; parallel compiler processes can
use more total memory than this number. CPU/RSS accounting depends on descendants
being waited for by their parents. Detached background work is not measured.

Snapshot schema 2 publishes the manifest only after its sidecars are written.
Copy the entire evidence directory to relocate a capture. `compare` verifies every
object's digest and containment, even when both snapshots have equal hashes;
missing or corrupt sidecars fail. It loads text one artifact at a time for
verification, then loads changed pairs for textual diffs. Capture still collects
artifact text in memory, so this is not yet a streaming collector. Older inline
snapshots must be recaptured before comparison with the new schema/normalization.

Churn distinguishes added, removed, content-changed, and byte-identical rewritten
files using raw hashes and nanosecond mtimes. Files rewritten while preserving
their mtimes cannot be detected this way. The artifact list defines the scope:
these counts are generated source/metadata/build files, not every binary or log
in the simulation tree. Failed commands preserve logs and measurements but never
produce a successful snapshot from stale files. Missing required output groups
are failures. Individual optional artifacts are still compared when present.

Normalization replaces configured absolute simulation and checkout roots with
`${SIM_ROOT}` and `${TRICK_ROOT}`, including the mirrored paths beneath `build`.
Both the configured spelling and the resolved path are recognized, including
symlink aliases such as macOS's `/var` and `/private/var`. Filesystem containment
checks continue to use resolved paths. Normalization version 2 also recognizes
bare roots followed by punctuation such as `;`, `)`, or `,`, while preserving
path-name suffixes such as `-other` and `.old`. Recapture older snapshots before
comparing them with this normalization version.
It preserves other paths, whitespace, comments, ordering, numeric offsets, units,
symbol names, timestamps embedded in text, and XML content. It does not parse C++
or interpret metadata. Root-derived SWIG hashes and other non-path differences
are deliberately exposed; relocation equivalence of *all* legacy output is not
promised. The report retains raw paths and hashes to audit normalization.

`compare` is a conservative textual regression check, not the future semantic ABI
comparator. Different generated source can be semantically equivalent. Matching
source does not prove GCC layout, runtime, or Python API equivalence. Snapshots
must have the same case, artifact specification, and supported versions; content
digests are checked before comparison.

The provenance fingerprint covers tracked simulation files and records working
tree status. It does **not** cover all transitive includes, installed libraries,
untracked input contents, compiler binaries, or compiler predefined macros. It
must not be used as a cache key. The recorded argv is the measured outer command;
verbose build logs provide the commands executed by Make. Record package versions,
configuration, target/ABI flags, compiler commands, and external models alongside
reviewed baselines. Only an explicit environment allowlist is serialized.

Exit codes: `0` success/equal, `1` comparison differences, `2` invocation or
incomplete/invalid evidence, `3` measured command failure. The original command
exit status (including negative signal status) is retained in the report.

## Compare captured metadata with extractor facts and native execution

On the x86_64 Linux reference target, with the standalone rewrite extractor built:

```sh
python3 tools/icg_baseline/differential.py \
  --extractor /tmp/trick-icg-build/trick-icg-extract \
  --compiler "$(command -v g++)" \
  --output /tmp/trick-native-comparison
```

This checks source and legacy-sidecar fingerprints for `anonymous-enum`,
`deleted-constructor`, and `embedded`, validates fresh facts, and compares the
captured record and enum tables. All three headers are included in a synthetic
`S_source.hh`; each comparison explicitly requests its model header and retains
the selection evidence. The other included headers must not become metadata
roots accidentally. The runner compares both legacy-generated and candidate C++.
It compiles and links the entire captured
C++ with the real Trick headers, `UnitsMap.cpp`, and the Starter constructor.
There is no substituted metadata ABI or mocked runtime implementation.

The native executable calls generated initialization/size entry points and reads
the actual tables. Record sizes/alignments, scalar sizes/offsets, unsigned bitfield
positions/widths, and enum sizes/values/signedness are checked against independently
measured native types and the facts. The bitfield probe is restricted to the
audited standard-layout, trivially-copyable fixture on little-endian hosts.
Sentinels and every currently unused metadata slot must retain their audited
defaults. Changed size thunks or metadata outside the text reader's subset are
regression-tested using compiled corruptions. Every extractor CI lane also runs
these probes, including the GCC 8.5/12 host lanes and LLVM 17–23 on macOS/Linux.

`comparison.json` is published only after all cases pass; stale success reports
are removed before a new attempt. Each case retains materialized C++, the native
probe, compiler version/target, exact compile/link/run argv and logs, non-system
dependency hashes from compiler depfiles, executable digest, and observations.
Installed system headers, runtime libraries, and compiler binary contents are not
fingerprinted; this evidence is not a cache key. CI records package provenance
separately. Use a native C++17 compiler for `--compiler` (default `g++`).

The gate covers six emitted records, six fields, and two enum tables. It checks
explicit record/enum policy exclusions and UnitsMap lookup agreement, without
claiming a general annotation policy or registration-presence test (UnitsMap
returns `1` for an unknown name). These three header probes compile lifecycle
wrappers; the separate [lifecycle gate](lifecycle/README.md) executes a dedicated
six-record corpus with observable construction/destruction and ownership checks.
Template/STL closure, broad registry behavior, and generated simulation behavior
remain outstanding.

The lifecycle gate adds three actual legacy snapshots, 18 symbol-presence/absence
checks, and 12 execution scenarios. Every extractor platform/compiler lane runs
the focused contract; the Linux reference lane also runs ASan/UBSan/LSan and a
missing-deallocation regression. See its [scope and reproduction commands](lifecycle/README.md).

## Remaining Phase 0 work

- Extend the configured template and I/O simulation capture/runtime lane to additional
  simulations and minimum stacks; promote reviewed full-build references.
- Add representative medium and real large/old simulations with reproducible
  commands and dependencies. The 12 checked-in cases are focused regressions,
  not a claimed representative performance distribution.
- Extend the existing capability/layout/template probes into legacy-versus-new
  semantic metadata, generated-operation, and runtime comparisons. ICG-001 has
  selected LibTooling; that decision does not substitute for baseline evidence.
- Complete the contract inventory, runtime/Python behavior snapshots, semantic
  metadata comparison, and the S_define/binding spikes.
- Review the initial ADRs and measured thresholds before advancing Phase 1.

See [the initial contract inventory](../../docs/developer_docs/ICG-Rewrite-Phase-0.md).

## Bounded policy comparison

The differential runner now also resolves [policy v4](../icg_policy/README.md)
from validated facts, comparing record/enum selection and units/I/O against the
three immutable legacy headers. Request and resolved documents accompany each
report. Existing explicit expected exclusions remain independent checks; they
are not inputs to the resolver. The reference lane additionally runs 38 live
legacy policy characterization cases, preserving successful and failed evidence.
Candidate metadata emission is checked through separate compiled probes.

The differential runner also generates a bounded candidate from validated
resolved policy v4 and compiles it in a separate executable. Candidate and legacy
observations must agree with the independent native probe. A separate translation
unit checks C-linkage tables and init/size entry points. The generated-source
contract and negative tests are documented in [icg_emit](../icg_emit/README.md).

The separate [enum corpus](enums/README.md) extends this gate to scoped enum
labels, alias order, signed/unsigned storage and empty tables. Its independent
legacy/native rejection probe records unsigned-narrow sign-extension mismatches;
policy rejects these values without producing a candidate. The new corpus has
its own immutable references and CI reproduction gate.

The [fixed-array corpus](arrays/README.md) adds two records / nine fields, including
six arrays and scalar/array aliases. Native type traits check dimensions and base
element/whole-field sizes independently. Non-default namespace-scoped units expose
and correct the emitter's UnitsMap key mismatch. The array references have their
own reproduction gate; the earlier reference bytes remain unchanged.
