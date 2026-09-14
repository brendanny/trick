# A3: native utility archives

This developer preview builds six existing static archives directly with CMake
3.26+, without running configure or recursive framework Make. It is not a Trick
simulation SDK: installation still fails explicitly. The end-user source installer
arrives in E1; continue using the existing installation instructions meanwhile.

| Build target | Build-tree alias | Archive |
| --- | --- | --- |
| `trick_math` | `Trick::Math` | `libtrick_math.a` |
| `trick_units` | `Trick::Units` | `libtrick_units.a` |
| `trick_comm` | `Trick::Comm` | `libtrick_comm.a` |
| `trick_connection_handlers` | `Trick::ConnectionHandlers` | `libtrick_connection_handlers.a` |
| `trick_optimization` | `Trick::Optimization` | `libtrick_optimization.a` |
| `trick_var_binary_parser` | `Trick::VarBinaryParser` | `libtrick_var_binary_parser.a` |

Archive boundaries and production sources are unchanged. Source lists are explicit;
adding a source requires editing its component's CMakeLists.txt. The separate
data-products units library and optional SAIntegrator are outside this layer.

## Build

No GoogleTest or other optional package is needed to build the archives:

```sh
cmake -S . -B build/cmake/libraries -DBUILD_TESTING=OFF
cmake --build build/cmake/libraries --parallel
```

`TRICK_BUILD_UTILITIES` defaults to `ON`; turn it off for the A2 configuration-only
preview. `TRICK_BUILD_UTILITY_TESTS` defaults to `OFF`. These are incremental
preview controls, not final release feature-default decisions. Utility tests
require both utility builds and `BUILD_TESTING`; inconsistent selections fail.

For the focused tests, install GoogleTest separately, then run:

```sh
cmake --preset utilities-ninja -DCMAKE_PREFIX_PATH=/path/to/gtest/prefix
cmake --build --preset utilities-ninja --parallel
ctest --preset utilities-ninja
```

`GTest_DIR` is also supported. No configure-time downloads occur. The `utilities`
preset honors native generator selection; `utilities-ninja` selects Ninja and
`utilities-multi` selects Ninja Multi-Config. After supplying dependency hints,
`cmake --workflow --preset utilities-ninja` runs configure/build/test together.
This is a developer test workflow, not the planned end-user installer.

## Requirements and dependency boundaries

The targets publish the source include root to build-tree consumers. C++ archives
publish C++17; C sources request C99 and retain compiler extensions needed by the
existing POSIX implementation. PIC and GCC/Clang warning options are target-local;
C sources retain exception unwinding support. Optimization links Math, Math carries
its Unix math-library requirement, and Comm carries `Threads::Threads`. CMake
propagates static link requirements without forcing consumers to copy linker flags.
C++ extensions are disabled for the archives. Normal CMake Debug/Release settings
control optimization and debugging; no project-wide compiler flags are overwritten.
This follows the target-oriented guidance in [Modern CMake](https://cliutils.gitlab.io/modern-cmake/).

Math includes its existing `trick_gsl_rand.c` object. Its message-service references
remain unresolved until an application supplies the runtime service (B5). A3's
focused math and optimization tests do not use those entry points. No dummy message
service is introduced. GSL discovery, its public layout definition, and its link
requirements are added in D5; `_HAVE_GSL` must remain undefined in this preview.
This layer does not claim that whole-archive linking of Math is self-contained.

## Validation and limitations

CTest reuses the existing Euler/quaternion, LDLt, PDIP optimization, device-copy,
connection-handler mock, and binary-parser test sources unchanged. Two small units
consumer cases exercise conversion and dimension errors. Tests link only their
utility target and `GTest::gtest_main`, so they also check inherited includes and
static dependencies. A generated consumer-options check rejects leaked private
`-Wall`/`-Wextra` flags. Test files and results stay in the build tree; each suite
has a timeout. Existing production warnings are not made fatal.

The CI workflow tests CMake 3.26.0 with Unix Makefiles, Ninja, and Ninja Multi-Config
on Ubuntu and macOS, provisioning GoogleTest 1.14.0 outside Trick's configuration.
See [A3 evidence](a3-validation.json) for actual local results and exact versions.
CI configuration is not evidence that macOS has passed. RHEL 8/GCC 8.5, LLVM 14,
and macOS qualification remain pending; A4/A5 add dependency/compiler gates.
