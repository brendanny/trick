# Roadmap

The first branch demonstrates the compiler-to-runtime path. Subsequent slices
should remain executable and independently reviewable.

## 1. Harden schema composition

Preserve the concrete model type through a typed schema facade so accidental
object/schema mismatches are rejected before invoking erased access functions.
Add an external typed metadata policy for legacy headers and make unsupported
members explicit. Then add integers, booleans, enums, fixed arrays, and nested
value objects with well-defined conversion and bounds behavior.

Acceptance: invalid compositions fail with intentional diagnostics; native
reflection and explicit adapters have equivalent runtime behavior; the C++17
model example continues to compile without conditional definitions or generated
sources. Unit metadata must evolve into real dimensional validation or remain
clearly documented labels.

## 2. Establish commands and observation boundaries

Add versioned schema enumeration and an input-command queue. Specify how commands
target live objects, validate values, report errors, and apply relative to
simulation phases. Define a bounded snapshot publication policy for slow clients.

Acceptance: a concurrent client cannot mutate live model state outside the
executive's input boundary; unregistering an object invalidates pending references
predictably; replaying the same accepted command log reproduces job ordering.

## 3. Define checkpoint semantics before choosing a format

Introduce persistent type/object/field IDs, schema versions, resource policies,
and a state-capture transaction. Include executive time and deadlines. Separate
value restoration from resource reconstruction and validate a restore plan before
changing the live simulation.

Acceptance: save/restore continuation matches an uninterrupted run for supported
models; schema incompatibility is reported without partial mutation; nested aliases
and owned objects have documented identity rules. `const` state and external
resources must have explicit policies. No raw object or coroutine-frame dumps.

## 4. Broaden execution and numerical semantics

Add integration groups and event/discontinuity handling before introducing parallel
jobs. A dependency graph should distinguish declared independent compute from
ordered input/output effects. Prototype an optional `<execution>` backend behind
the serial executive's established timing and failure semantics. Assess `<linalg>`
for actual kernels and `<hive>` against measured allocation workloads.

Acceptance: serial and parallel backends respect the same logical dependencies,
failure boundaries, and snapshot points. Numerical comparisons specify tolerances
and floating-point policies rather than promising universal bitwise identity.

## 5. Add a generic Python/client adapter

Build one optional client or generic bridge over schemas, values, and commands.
Model discovery must not create Python extension code per model. Keep the native
runtime install usable without Python. Specify conversion, ownership, interpreter,
and exception behavior in tests.

Acceptance: adding a model requires only ordinary C++ compilation and registration;
the Python client can discover it and observe/change permitted fields without
SWIG, pybind, an AST tool, comment parsing, or wrapper regeneration.

## 6. Add scenario conveniences deliberately

Evaluate coroutine-based scripts after cancellation, simulation-time waits,
checkpoint behavior, and model lifetimes are defined. Add contracts for programmer
errors without relying on their enabled/disabled policy for external validation.
Keep simulation setup as ordinary C++ rather than a new preprocessed language.
