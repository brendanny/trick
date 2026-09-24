# Selected-GCC extraction adapter

This development adapter runs `trick-icg-extract` under the selected simulation
compiler's C++17 parse conditions. It does not replace production `trick-ICG` or
read compilation databases. Requires Python 3.11+, `jsonschema`, GCC 8.5+, and the
matching facts-v13 extractor.

```sh
python3 tools/icg_driver/extract.py \
  --extractor build/icg-extract/trick-icg-extract \
  --compiler /usr/bin/g++ --source-root "$PWD" \
  trick_source/codegen/TrickCodeGen/tests/fixtures/record.hh -- -std=gnu++17 \
  > build/icg-extract/record.json
```

Pass the actual build's semantic flags after `--`, in their original order.
Compile the model and generated metadata with that same compiler and those flags.
`--path-root NAME=DIR` and `--select-file HEADER` retain the extractor's meanings.
One facts document goes to stdout and one JSON diagnostic envelope goes to stderr.
Compiler-probe and invocation failures exit 2 without publishing facts. Extractor
failures retain their status and diagnostics. Probe warnings remain visible.

## Parse conditions

The adapter invokes the selected executable directly with argv vectors, without a
shell. Executable paths containing spaces work. It preserves a driver's symlink
name in argv[0] and records the resolved path separately. Five probes collect the
complete GCC version, target, version display, language-mode macros, and effective
macros with the supplied flags. No probe compiles or executes model code.

Only strict `c++17` and GNU `gnu++17` are accepted. If the build supplies no `-std`,
the adapter probes the default and makes that dialect explicit for Clang. An
unsupported default is an error. In particular, GCC 8.5's default GNU C++14 is not
silently upgraded: select a C++17 dialect in the build first. Multiple supported
`-std` options retain GCC's last-option-wins behavior.

The compiler's complete version becomes `-fgnuc-version=major.minor.patch` and
its target becomes `--target=TRIPLE`. Version macros must agree with the driver's
version. Direct overrides of compiler identity/dialect macros are rejected;
forced includes and imacros files must not change those macros either. The version
components use Clang's two-digit encoding, with a nonzero major. There is no
fallback to a configured-at-build-time GCC version or whichever `g++` happens to
be elsewhere on PATH.

The bounded argument interface accepts include paths, definitions/undefinitions,
forced includes, sysroots, `-m32`/`-m64`, `-fno-exceptions`, `-fno-rtti`, the two
C++17 modes, and warning controls. These are passed unchanged and in order. All
other flags are errors, including response files, plugins, driver forwarding,
output/link/code-generation options, user target overrides, and user
`-fgnuc-version`. Nothing is silently dropped. GCC warning options that Clang does
not recognize also fail through the extractor's normal diagnostics.

## Evidence and limits

Facts v13 requires `language_standard`, `gcc_compatibility_version`, and
`build_compiler`. Raw extractor calls set `build_compiler` to null and continue to
default to strict C++17 and Clang's GCC 4.2.1 compatibility version. They make no
claim to represent a selected build compiler. Targets whose Clang driver disables
GNU compatibility instead record a null `gcc_compatibility_version`.

Adapter output records the compiler path, executable SHA-256, full version and
version display, target, original and translated flags, default-versus-explicit
dialect, probe commands/stderr, effective macro-output digest, and relevant
compiler environment. The adapter adds this evidence before recomputing the full
`input_digest`. The independently validated `graph_digest` still describes graph
equivalence only. Validation checks that the dialect, compatibility version, and
argument translation agree with the Clang invocation. This is consistency
validation, not cryptographic attestation of a compiler run.

Matching these conditions does not make Clang equivalent to GCC. `__clang__`,
feature-test builtins, target extensions, and automatic system-header discovery
can still differ. Clang/AppleClang build compilers, general compilation-command
normalization, selected-GCC standard-library discovery, and production build
integration remain outside this increment. The executable digest does not hash
all GCC subprograms, specs, or system files and is not a hermetic toolchain key.

The new CTest `icg_driver_integration` exercises real GCC on GNU host lanes,
including Rocky 8 / GCC 8.5 and 12. Other host compilers run the probe rejection
suite. The native regression checks conditional fields through extraction,
policy, emission, compilation and metadata inspection in both dialects. Its
negative control proves that a missing tail-padding field passes all old layout
assertions. The LLVM 17–23 low-level suites also test all three GCC version macros,
dialect provenance, and malformed version rejection.
