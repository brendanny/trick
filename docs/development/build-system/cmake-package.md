# C3: consuming the CMake SDK package

Configure the framework with `TRICK_BUILD_SDK=ON`. Both `<build>/package` and
`<prefix>/<libdir>/cmake/Trick` provide `TrickConfig.cmake`. Consumers need
CMake 3.26 and a compatible C++17 compiler. Package version compatibility is
restricted to the same Trick major/minor release and pointer size; it is not
an ABI guarantee across compiler or dependency changes.

```cmake
cmake_minimum_required(VERSION 3.26)
project(MyEmbedding LANGUAGES CXX)
find_package(Trick CONFIG REQUIRED COMPONENTS Runtime)
add_executable(embedding main.cpp)
trick_enable_runtime(embedding)
```

Use `-DCMAKE_PREFIX_PATH=<prefix>` (or `-DTrick_DIR=<build>/package`). Dependency
locations may be supplied with normal CMake package hints. The complete example
is in `cmake/examples/consumer`, installed under `share/trick/examples/consumer`.
It allocates a registered runtime type, initializes the four built-in Python
modules, and accesses a core service through Python. `Trick_PYTHON_DIR` identifies
the core proxy import directory; these are embedded modules, not loadable Python
extension modules. This package does not replace `S_define` or `trick-CP`.

| Component | Contract |
| --- | --- |
| `Utilities` | `Trick::Math`, `Units`, `Comm`, `ConnectionHandlers`, `Optimization`, `VarBinaryParser`; Threads dependency, no Python or LLVM discovery. |
| `Runtime` (default) | Native core and embedded Python closure; finds Threads, UDUNITS2 and the producer's Python major/minor embedding development package. No interpreter, SWIG, LLVM/Clang, Bison or Flex discovery. |
| `ICG` | Imported executable `Trick::ICG`; its installed external shared-library/resource dependencies must already exist. Does not require LLVM development package discovery. |

`Trick::Core`, `MemoryManager`, `MemorySupport`, `Integrators`, `CoreMetadata`,
`Main`, `PythonInput` and, when enabled, `Er7Utils` expose constituent targets.
Use `Runtime` when consuming these: the static cycles of this complete SDK carry
the Python dependency. `trick_enable_runtime(target)` links `Trick::Runtime`,
retains metadata using CMake's `WHOLE_ARCHIVE` feature and enables executable
symbol export for named allocators. Main still requires simulation-generated
entry points. Registration/SWIG targets in the export are implementation details.

The installed package locates its targets and proxies relative to its prefix;
it contains no source/build directory references. The build export deliberately
uses producer paths. Dependency discovery supports C++-only consumers.
Unsupported required components cause package discovery to fail.

`sdk.package` builds/runs a runtime consumer and a utilities-only consumer against
the build export. The latter disables Python discovery; both disable generator
dependency discovery. The install qualification repeats these checks against
relocated `lib`/`lib64` packages while source/build trees are hidden and scans installed CMake files, Make fragments and `sdk.env` for producer-path leaks.
Binary execution is tested with producer trees hidden; debug information and the
explicit developer fallback may still contain producer paths in the ICG binary.
CI artifacts record the tool versions for each lane.
