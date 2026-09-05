# ICG rewrite: Phase 0 evidence tooling

This is the first implementation increment of the
[ICG rewrite plan](../../docs/developer_docs/ICG_REWRITE_PLAN.md), section 20,
item 1. It collects existing codegen output before the extractor/API decision.
It is development tooling, requires Python 3.11+, and uses only the standard
library. It does not participate in the production build.

## Run the harness tests

From the repository root:

```sh
python3 -m unittest discover -s tools/icg_baseline -v
python3 tools/icg_baseline/baseline.py list
```

The tests use explicitly synthetic generated text. They verify the collector;
they are not captured ICG output, semantic parity tests, or LLVM/GCC validation.

## Collect an existing simulation

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
  --case templates --output /tmp/icg-templates-existing
```

`--root PATH` and `--manifest FILE` are global options placed before the subcommand.
An additional corpus manifest can select other in-checkout simulations and
artifact patterns. Case directories must contain `S_define`; artifact globs must
stay inside that directory. Output under alternate `trick-ICG -o` locations and
external/trickified projects needs an explicit manifest extension.

## Evidence format and interpretation

| File | Contents |
|---|---|
| `snapshot.json` | Versioned artifact specification, normalized filenames and complete UTF-8 text, content digests; no timestamps |
| `report.json` | Git revision/status, tracked simulation input digests, manifest digest, host/Python, selected environment values, output bytes/files, raw digests/mtimes, command status and measurements |
| `stdout.log`, `stderr.log` | Unmodified command output, created by `run` only |

`run` measures wall time, user/system CPU, and the OS child-process RSS high-water
mark in bytes. Each measurement uses a fresh worker to avoid inheriting earlier
children's resource accounting. Linux and macOS are supported for measurement.
RSS is **not summed concurrent process memory**; parallel compiler processes can
use more total memory than this number. CPU/RSS accounting depends on descendants
being waited for by their parents. Detached background work is not measured.

Churn distinguishes added, removed, content-changed, and byte-identical rewritten
files using raw hashes and nanosecond mtimes. Files rewritten while preserving
their mtimes cannot be detected this way. The artifact list defines the scope:
these counts are generated source/metadata/build files, not every binary or log
in the simulation tree. Failed commands preserve logs and measurements but never
produce a successful snapshot from stale files. Missing required output groups
are failures. Individual optional artifacts are still compared when present.

Normalization replaces configured absolute simulation and checkout roots with
`${SIM_ROOT}` and `${TRICK_ROOT}`, including the mirrored paths beneath `build`.
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

## Remaining Phase 0 work

- Capture and review actual baseline snapshots on the minimum/reference stacks;
  no generated legacy snapshots are checked in by this increment.
- Add representative medium and real large/old simulations with reproducible
  commands and dependencies. The 12 checked-in cases are focused regressions,
  not a claimed representative performance distribution.
- Add the virtual/diamond layout, friend access, implicit special member,
  packed/bitfield, partial-template and pack capability corpus. Choose libclang
  or LibTooling only after the LLVM 17 C API spike and GCC 8.5/12 probes.
- Complete the contract inventory, runtime/Python behavior snapshots, semantic
  metadata comparison, and the S_define/binding spikes.
- Review the initial ADRs and measured thresholds before advancing Phase 1.

See [the initial contract inventory](../../docs/developer_docs/ICG-Rewrite-Phase-0.md).
