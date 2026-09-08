# Focused lifecycle differential evidence

This gate executes actual legacy-generated lifecycle functions for a new,
instrumented six-record corpus. The extractor still exports declaration facts;
`lifecycle.py` contains a deliberately bounded evidence policy, not a production
lifecycle emitter or general access/ownership resolver.

| Record | Default construction | Legacy allocation | Destruct / delete | Executed evidence |
|---|---|---|---|---|
| `IcgLifecycleTracked` | Public, user-declared | `calloc` + placement construction | Element loop / scalar delete | Counts, initialized values, strides, forward destruction, scalar deletion |
| `IcgLifecycleImplicit` | Implicit, with member initializer | `calloc` + placement construction | Element loop / scalar delete | Initializer value, destruction, scalar deletion |
| `IcgLifecycleDeleted` | Explicitly deleted, still POD in C++17 | Raw zeroed storage | Both no-ops | Byte inspection and caller-owned release; no typed object access |
| `IcgLifecycleNoDefault` | Suppressed by an explicit one-argument constructor | Absent | Element loop / scalar delete | Caller placement construction, generated destruction; scalar deletion |
| `IcgLifecyclePrivateDestructor` | Public constructor; private destructor | Present | Both absent | Symbol/operation checks only; allocation is not executed |
| `IcgLifecycleAbstract` | Abstract class | Absent | Element loop / virtual scalar delete | Delete a concrete derived instance through its abstract base |

The probe performs 18 named symbol lookups with `dlsym`, including the four
required absences, and executes 12 scenarios using counts 1 and 3. Declaration
access/deletion/implicit state, abstractness, POD state, destructor virtualness,
and sizes come from validated facts. Compiler-observed placement construction
and destruction are cross-checked separately: a public constructor with a private
destructor permits the placement expression but fails `is_default_constructible`.
Raw POD allocation must not turn a deleted default constructor into a supported
C++ construction capability. Reasons are retained in `lifecycle.json`.

The `pod` fact uses the C++17 language trait, matching `std::is_pod`, rather than
Clang's older TR1/layout classification. Those queries disagree on Darwin for
the deleted-constructor case. A header-only regression compares facts with
`__is_pod` under Linux, x86-64 Darwin, and ARM64 Darwin targets, including deleted,
private, explicit/defaulted, and nontrivial constructors. The native probe keeps
the independent standard-library trait check.

Instrumented definitions record constructor/destructor events out of line.
Expected values and event order belong to these digest-checked definitions;
the facts do not claim to extract bodies or evaluate initializers. Address
evidence uses offsets, with strides compared against fact sizes. The policy
mirrors the two ownership paths in `MemoryManager_delete_var.cpp`: generated
allocation followed by generated destruction and `free`, or scalar `new`
followed by generated `delete`. It never pairs the generated `calloc` allocator
with scalar delete, or passes a `new[]` allocation to that wrapper.

## Run the comparison

```sh
python3 tools/icg_baseline/lifecycle.py \
  --extractor /tmp/trick-icg-build/trick-icg-extract \
  --compiler "$(command -v g++)" --sanitize \
  --output /tmp/icg-lifecycle
```

`--sanitize` enables AddressSanitizer and UndefinedBehaviorSanitizer with fatal
errors and allocation/deallocation mismatch checks. `--leak-check` additionally
enables Linux LeakSanitizer; it requires normal process inspection support and
can fail under ptrace or restricted process environments. Sanitizer settings are
explicit and recorded. The Ubuntu LLVM 17 reference lane enables all three;
every Linux/macOS LLVM 17–23 and GCC 8.5/12 extractor lane runs the ordinary
lifecycle comparison and compiled negative cases. Set CMake
`ICG_TEST_LIFECYCLE_SANITIZERS=ON` to enable the full Linux sanitizer tests.

Regressions compile altered captured C++ to detect wrong initialization,
missing/reordered destruction, unexpected exported wrappers, and, in the leak
lane, a destructor call that omits deallocation. Mutation tests also alter native
observations and regenerate fact digests, so digest rejection cannot masquerade
as semantic rule coverage. The success report is removed before each attempt
and written only after compilation, execution, and comparison succeed.

Artifacts retain facts/diagnostics, expanded captured C++, probe sources,
compiler version/target, exact commands and logs, non-system dependency hashes,
sanitizer environment, symbol/trait observations, policy decisions, and events.
These are evidence fingerprints, not a complete toolchain cache identity.

## Reproduce the captured legacy reference

Build the [unchanged evidence generator](../README.md#reproduce-the-isolated-legacy-header-evidence), then:

```sh
python3 tools/icg_baseline/legacy.py \
  --build-dir /tmp/trick-legacy-build \
  --manifest tools/icg_baseline/lifecycle/corpus.json \
  --udunits-xml /usr/share/xml/udunits/udunits2.xml \
  --output /tmp/icg-lifecycle-reference \
  --reference tools/icg_baseline/lifecycle/reference
```

The three snapshots and content-addressed sidecars were produced by the real
LLVM 17 legacy generator; none are handwritten expected C++. Provenance records
the source revision, uncommitted corpus state, input/build/binary/XML hashes,
compiler, and observed pass results. Cold equals warm; forced output retains the
known duplicate SIE append. The baseline CI job rebuilds the unchanged generator
and compares all three passes against these references. The four existing header
references remain separate and unchanged.

This does not run MemoryManager registration or its dynamic-dispatch methods,
resolve general lifecycle policy, or cover zero/negative counts, allocation
failure, throwing constructors/destructors, over-alignment, inaccessible
destruction, or arbitrary class-specific allocation. Those remain separate gates.
