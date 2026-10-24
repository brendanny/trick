# trick2
where we get to have nice things

An executable scaffold for a C++26 simulation framework. The first slice connects
**ordinary C++ models, compile-time reflection, runtime introspection, a deterministic
executive, and numerical integration** without an ICG pass, generated wrappers, or
semantic comment parsing.

This is an architectural starting point, not a compatible replacement for NASA
Trick. The API is experimental. The scope and next steps are explicit below.

## Build and run

This branch keeps the experimental framework in a standalone `trick2/` directory.
Run the commands below from that directory, independently of the existing Trick
build at the repository root:

```sh
cd trick2
```

### Native C++26 path

Requirements: GCC 16 with its matching standard library, CMake 4.1+, and Make.
The runtime has no third-party library dependencies. An ordinary CMake build
compiles the models and their registration code; there is no separate source
generator to install or run.

```sh
CXX=g++-16 cmake --preset native
cmake --build --preset native --parallel
ctest --preset native
./build/native/trick2_reflected
./build/native/trick2_mixed
```

Set `CXX` to the actual GCC 16 compiler path on your system. GCC enables reflection
with `-std=c++26 -freflection`; the `trick2::reflection` CMake target supplies these
requirements to consumers. Configuration compiles a real reflection and annotation
probe and fails if it is unsupported. It never silently substitutes another adapter.
Compiler support is described in the [GCC 16 release notes](https://gcc.gnu.org/gcc-16/changes.html)
and [GCC C++ status table](https://gcc.gnu.org/projects/cxx-status.html).

Both examples run a unit-frequency oscillator for ten simulated seconds, integrate
at 1 ms, and emit CSV observations at 100 ms. `--verify` checks every observed
position/velocity pair against the analytic solution and suppresses CSV output.

### Runtime development on an older compiler

```sh
cmake --preset bootstrap
cmake --build --preset bootstrap --parallel
ctest --preset bootstrap
./build/bootstrap/trick2_mixed --verify
```

This explicit development mode uses C++23 and is tested with GCC 13. It builds the
runtime and the explicit-descriptor example. It does **not** build or validate the
C++26 reflection adapter. It does not provide a replacement parser or generator.

The [validation record](docs/validation.md) distinguishes both configurations.

## What simulation code looks like

New model state can carry typed C++26 annotations:

```cpp
struct Model {
    [[=trick2::Field{1, trick2::Unit::metre}]]
    double position{1.0};

    [[=trick2::Field{2, trick2::Unit::metre_per_second}]]
    double velocity{0.0};

    [[=trick2::Field{3, trick2::Unit::radian_per_second,
                    trick2::Access::output}]]
    const double angular_frequency{1.0};

    void advance(double time, double step);
};
```

`Field` is a structural C++ value. Its ID is explicit; its unit and access policy
are enums. Member names come from the compiler. Comments have no framework meaning.
The current default policy is input, output, and reserved checkpoint metadata;
read-only fields declare `Access::output` explicitly.

The descriptor is constructed during ordinary compilation:

```cpp
constexpr auto fields = trick2::describe<Model>();
constexpr trick2::TypeDescriptor schema{"Oscillator", fields};
```

Simulation assembly is ordinary C++, replacing the role of `S_define`:

```cpp
using namespace std::chrono_literals;

Model model;
trick2::Registry registry;
auto registration = registry.expose("oscillator", model, schema);

trick2::Simulation simulation;
const auto dynamics = simulation.every(1ms, trick2::Phase::dynamics,
    [&](const trick2::StepContext& context) {
        const auto time = std::chrono::duration<double>(context.time - context.step).count();
        const auto step = std::chrono::duration<double>(context.step).count();
        model.advance(time, step);
    });
(void)dynamics;
simulation.run_until(10s);
```

There is no registration by static initializer, ownership by a global memory
manager, or hidden scheduler thread. Keep the model alive and at the same address
until its registration is released. The [complete reflected example](examples/reflected)
also reads snapshots in the observation phase, after dynamics at each coincident
timestamp.

## Does the model itself need C++26?

**Only the translation units using C++26 syntax or APIs need that language mode.**
The [mixed-standard example](examples/mixed) makes this distinction executable:

| Translation unit | Language mode | Responsibility |
| --- | --- | --- |
| `examples/mixed/model.cpp` | C++17 in both builds | Existing oscillator equations; no Trick2 headers |
| `examples/mixed/main.cpp` | C++26 native / C++23 bootstrap | Explicit typed field metadata, registration, RK4, simulation assembly |
| `examples/reflected/*.cpp` | C++26 with reflection | Annotated model and automatically discovered fields |
| `src/*.cpp` | C++26 native / C++23 bootstrap | Executive and runtime registry |

The mixed example deliberately uses `make_field<Model, &Model::member>` and explicit
names; it does not claim automatic reflection. The unmodified model header has the
same tokens in every translation unit. An external reflection policy adapter for
such headers is a next step, not implemented here. New inline `[[=...]]` annotations
make the containing header require C++26 for all includers.

These examples use the same compiler installation, ABI configuration, and standard
library across targets. Mixing language modes is not a promise of compatibility
between arbitrary compilers, runtimes, debug modes, packing options, or old binaries.
The public runtime API itself uses C++20 facilities; the C++17 model does not include it.

## Implemented scope

| Piece | Working behavior |
| --- | --- |
| Reflection | `consteval describe<T>()`, typed annotations, member discovery, stable explicit field IDs, typed read/write functions |
| Schema | Flat public `double` and `const double` fields; unit and access metadata; no raw byte-offset access |
| Registry | Explicit borrowed roots, copied metadata, scoped registration, stale-handle detection, checked access, owned telemetry snapshots |
| Executive | Integer nanosecond time; periodic jobs; ordering by time, phase, then registration; resumable absolute horizons; terminal stop/failure |
| Integration | Constrained, `constexpr` classical RK4 over a coupled `std::array<double, N>` state |
| Examples | Native reflected oscillator and separately compiled C++17 model, both exercising registration, integration, scheduling, and observation |
| Build | Native feature probe, explicit bootstrap mode, CTest, installable CMake targets, native/bootstrap CI workflow |

The adapter rejects missing/duplicate annotations, zero/duplicate IDs, unsupported
field types, const input fields, inheritance, private state, and unions. Methods
and static members are not instance fields. Compile-negative tests check that
rejections occur for their intended diagnostics.

The erased `TypeDescriptor` currently has a low-level precondition: its accessors
must match the concrete object passed to `expose`. A mismatch can cause undefined
behavior. A typed schema facade is a priority before treating this as a general
extension API. The registry does not own the model, extend its lifetime, or permit
concurrent access without external serialization.

## Deliberately unfinished

There is no checkpoint serializer, restore, Python adapter, network variable server,
unit conversion, nested-object/array schema, event root finder, job dependency graph,
parallel execution engine, coroutine API, or compatibility layer for existing Trick
inputs. `Access::checkpoint` is reserved metadata; snapshots are telemetry copies.

SWIG and pybind are absent. A future Python client should consume generic descriptors,
snapshots, and queued commands through one optional bridge or protocol. Per-model
wrapper generation would recreate the coupling this design removes.

The [architecture](docs/architecture.md) explains the boundaries and the roles of
`<execution>`, contracts, coroutines, concepts, constant evaluation, `<hive>`, and
`<linalg>`. The [roadmap](docs/roadmap.md) records the implementation sequence.

## Consume as a library

```sh
cmake --install build/native --prefix /path/to/trick2-install
```

```cmake
find_package(trick2 0.1.0 EXACT CONFIG REQUIRED)
target_link_libraries(my_sim PRIVATE trick2::reflection)
# Or trick2::runtime for an explicit descriptor adapter without <meta>.
```

Set `CMAKE_PREFIX_PATH` to the installation prefix. The reflection target propagates
C++26 and the configured reflection options. A bootstrap installation exports only
`trick2::runtime`. Package versioning is intentionally exact while the API and ABI
are experimental.
