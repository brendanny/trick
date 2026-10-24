# Architecture

## Design constraints

Trick2 should turn C++ model declarations into simulation metadata during the
normal compiler invocation. It must not add an ICG pass, parse semantic comments,
generate SWIG/pybind wrappers, or require a Trick-specific source language.
Simulation ownership and assembly remain ordinary C++. The standard library is
the only runtime dependency in this scaffold.

The initial executable slice is deliberately small enough to establish semantics:
reflect scalar state, register an owned model explicitly, integrate an oscillator,
schedule observations deterministically, and inspect the results. It does not
attempt to copy every service from the existing Trick implementation.

## Boundaries

| Boundary | Data crossing it | Responsibility |
| --- | --- | --- |
| Model declaration to registration code | Complete C++ type and typed annotation values | Compile-time schema discovery and policy validation |
| Registration code to runtime | Ordinary descriptors and typed access functions | Names, field IDs, units, permissions, access to actual objects |
| Simulation application to executive | Periods, phases, callbacks | Explicit assembly, object ownership, configuration |
| Executive to model | Logical step context | Deterministic scheduling; model-specific numerical work |
| Registry to observer | Owned value snapshots | Observation at a caller-selected boundary |
| Future external clients to executive | Validated commands | Applying changes at agreed simulation boundaries |

The reflection library is a frontend to the runtime metadata representation. The
executive has no reflection dependency in its implementation. The registry does
not schedule work. The integrator is a numerical function that knows nothing about
the registry. The application explicitly connects these pieces.

## Reflection and metadata

`describe<T>()` is `consteval`. It uses C++26 member reflection, typed annotations,
expansion statements, and splicing to create an array of `FieldDescriptor` values.
`std::define_static_array` gives the reflected member range the necessary static
storage. No generated C++ files or compiler AST tooling are involved.

Each reflected accessor is a real typed C++ member access after conversion from
the registered address. There is no `offsetof` arithmetic, assumed layout, or
reinterpretation of numeric representations. The runtime descriptors contain
ordinary strings, IDs, enums, and function pointers; `std::meta::info` does not
cross into runtime protocols or persistent state.

The first policy deliberately supports complete, unqualified, flat class types
whose public instance fields are `double` or `const double`. Every field must
have exactly one `Field` annotation. Bases and non-public state are rejected,
rather than silently omitted from a supposedly complete schema. Methods and
static members are outside the instance-state schema. Const fields cannot be
inputs. Units are labels in this revision; they do not enforce dimensions or
convert quantities.

IDs are supplied explicitly, scoped to the model schema, and independent of member
order. They are a foundation for future persistence and protocols, not a complete
schema-evolution design. No hash of a compiler's spelling is advertised as a
stable wire identity. A durable format still needs type IDs, schema versions,
compatibility rules, and migrations.

`TypeDescriptor` currently erases the concrete C++ type. Its field functions must
match the object passed to `Registry::expose`; this precondition is not checked by
the present API. A typed schema facade should preserve the association until the
runtime boundary. This is a real hardening item: passing the wrong schema can cause
undefined behavior. Ordinary reflection use constructs a schema for the same
`Model` it registers, and the tests exercise that path.

### Existing model code

The explicit `make_field<T, &T::member>` adapter also produces runtime descriptors.
It is useful for migration and makes the runtime testable without a reflection
compiler. The mixed example keeps equations in a C++17 translation unit and puts
Trick2 assembly in a separate translation unit. Its metadata is explicit, not
automatically reflected.

A future external typed policy can pair reflected members with units, access
rules, and IDs in a C++26 integration translation unit. That translation unit must
see the complete model definition; reflection cannot discover members from an
opaque binary. The shared model definition must remain ODR-consistent. Conditional
annotations that change the definition between language modes are not the migration
strategy. An ABI-compatible C interface would be a separate option for truly opaque
or incompatible binaries.

## Ownership and object identity

The application owns each model through normal C++ lifetime mechanisms. The registry
borrows its address. `Registration` is a move-only token whose destruction removes
that exposure. The application must keep the model alive at the same address and
keep its accessor code loaded until the token is released. Destroying a token
does not destroy the model. Destroying a registry before its tokens is safe.

`ObjectHandle` carries registry identity, slot index, and generation. Reusing a
slot does not revive earlier handles. A saturated generation retires the slot
instead of wrapping. These handles identify live runtime registrations only; they
are not persistent object IDs or transferable protocol handles.

The registry copies names and descriptor records on exposure. Snapshots own their
names and scalar values. Snapshot ordering follows current slot order and field
declaration order; the slot order is not a promise of permanent insertion order
after unregister/reuse. External consumers should use explicit identities rather
than infer identity from array positions.

All registry operations, token destruction, model access, and simulation execution
are thread-confined or externally serialized. `write` applies immediately on the
calling thread and checks input permission. `read` and `snapshot` require output
permission. A remote client must not call these functions concurrently with model
updates; a future command queue will enforce a controlled application point.

## Executive semantics

Time is a signed integer count of nanoseconds starting at zero. The initial
executive is serial. It orders jobs by due time, then phase, then registration
ID. Phase order is `input`, `dynamics`, `control`, `observation`. This is a small
explicit policy, not a claim that all simulations need these phases.

`every(period, phase, callback)` schedules the first firing at the current time
plus one period. `StepContext.time` is that firing timestamp and `step` is the
registered period. An integrator advancing the preceding interval therefore starts
at `time - step`. A nonautonomous RHS must receive that start time.

`run_until(horizon)` uses an absolute inclusive horizon. It executes all eligible
deadlines and then advances the clock to the horizon. Repeated calls preserve
existing deadlines. Registration between runs is permitted and uses the new
current time as its origin. Registration during execution and nested `run_until`
calls are rejected. Initial conditions are set in ordinary C++ before running;
there is no hidden time-zero firing.

Stop takes effect after the current callback, so remaining callbacks at the same
timestamp can remain unexecuted. Stop is terminal. If a callback throws, the
exception propagates and the executive enters a terminal failed state at the
active timestamp. Previously completed side effects are not rolled back. A rerun
cannot accidentally replay part of that timestamp. Recovery would require a
separate explicit rollback/checkpoint design.

Periods must be positive and their first deadlines representable. If the next
deadline after a completed callback would exceed the clock range, the job becomes
exhausted. Clock arithmetic never wraps. The current scheduler scans jobs;
large-scale scheduling data structures can be introduced after measuring actual
workloads while retaining these ordering semantics.

Deterministic callback ordering does not imply bit-identical floating-point output
across processors, compiler flags, numerical libraries, or concurrent backends.
Fast-math and aggressive reassociation are not enabled by the project.

## Numerical integration

`rk4_step` is a constrained, `constexpr` classical RK4 function. Its derivative
receives the entire state for each stage and returns the entire derivative. The
function returns a new state, leaving the caller to commit it. This prevents a
naive per-member update from mixing old and new stage values within a coupled
system.

It supports fixed-size arrays of doubles. It checks finite start time, step, and
endpoint; it does not validate model-produced derivatives or supply adaptive error
control. Positive, negative, and zero steps are allowed by the numerical function,
while periodic scheduling requires positive durations. Events, discontinuities,
constraints, and multirate integration require additional explicit semantics.

## C++ facilities: what belongs where

| Facility | Current use | Intended next role or constraint |
| --- | --- | --- |
| Reflection and typed annotations | Member discovery and checked field metadata | Extend schema coverage and external policies without a parser or generator |
| `consteval` | Descriptor generation | Validate complete schema policies and persistent identity declarations at compile time |
| `constexpr` | Descriptors, access flags, RK4, compile-time tests | Tables, unit algebra, validated static configuration |
| Concepts | Supported member types and derivative signature | Clear requirements for model, integrator, and backend extension points |
| `constinit` | Not needed by this slice | Only for necessary process-wide state that must avoid dynamic initialization; never an excuse for a global self-registering model graph |
| Contracts | Not required to build this slice | Express programmer preconditions once compiler and build policy are chosen; input, protocol, and checkpoint validation must still run when contract checking is disabled |
| `<execution>` | Not used by the serial executive | An optional compute backend for declared independent jobs, completion/cancellation, and explicit barriers; it must not own simulation logical time |
| Coroutines | Not used | Scenario sequencing and asynchronous orchestration after lifecycle/cancellation semantics are defined; coroutine frames are not checkpoint data |
| `<hive>` | Not required; runtime handles use indexed slots | Evaluate for frequently inserted/erased object records; address stability does not replace identity, generations, or ownership rules |
| `<linalg>` and `mdspan` | Not needed for a two-state RK4 example | Optional numerical-kernel adapters; define layout, aliasing, backend, and reproducibility policies before selecting acceleration |

This table is a design allocation, not a claim that every library facility is
available in every C++26 implementation. The build probes the reflection facilities
it actually uses. Future optional features need their own small executable probes
and tests instead of a single blanket “C++26 supported” check. Compiler and library
coverage can differ; see the [GCC implementation status](https://gcc.gnu.org/projects/cxx-status.html)
and its linked standard-library status.

## Python, persistence, and service boundaries

No Python runtime is required by the core. A future Python client can use a stable
schema/value/command protocol or one generic optional CPython bridge. Neither path
needs generated wrappers for each model. Choosing a direct CPython bridge would
introduce an optional CPython dependency and require explicit object lifetime,
conversion, exception, and interpreter-state policies. Reflection alone does not
provide those semantics.

Telemetry snapshots are copied scalar values. `Access::checkpoint` currently marks
policy intent only and does not imply serialization or restorability. A real
checkpoint must capture simulation time, job scheduling state, model state, and
object-graph identity together; validate them before mutation; and reconstruct
resources through explicit policies. Raw pointers, file/socket handles, mutexes,
and coroutine frames cannot serve as portable persistent state. Whether a const
member is reconstructed, verified, or excluded belongs to that future design.

The first external interface should expose a versioned schema and immutable
snapshots, with input commands queued and applied in a defined input phase.
Checkpointing, remote control, and Python should consume that boundary rather than
reintroduce per-model generated code or semantic comments.
