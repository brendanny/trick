# B5: core runtime archives

Predecessor: B4. `TRICK_BUILD_CORE=ON` enables the prerequisite native libraries
and exposes `Trick::Core` (`libtrick.a`) and `Trick::Main`. The explicit source
inventory covers the core service directories and remaining ADT-adjacent
utilities, excluding objects already owned by MemoryManager, its support library,
the integrators, or generated metadata. Main's simulation-generated `memory_init`
entry point remains the consumer's responsibility.

Required archive dependencies are target links. The real static dependency
cycle between Core and MemoryManager is declared so CMake repeats the connected
component on the link line. Optional distribution features (HDF5, GSL, CivetWeb,
BFD/Avahi/platform hardware clocks) remain separate roadmap work and are not
silently selected by header presence. No SDK installation is enabled.

`trick_retain_metadata(target <mangled-type>...)` retains specific metadata units
and enables executable symbol exports for MemoryManager's existing `dlsym`
lookup. This is for closed subsystems; B6 supplies complete runtime linkage.
The local platform spelling uses `-u` with Mach-O's leading underscore on macOS
and the ELF symbol name on Linux. Link options stay on the consuming executable.

Acceptance: build, then `ctest --test-dir <build> -L runtime
--output-on-failure`. `runtime.core` allocates a real `Trick::Environment` through
the string-based memory-manager API, reads/writes its environment map, and deletes
it. Its allocator is retained without a direct C++ reference to the generated
function. With runtime tests enabled, the existing ScheduledJobQueue suite also
runs with retained JobData/SimObject metadata. Standalone diagnostics use the
same test sink as B2; no Python input processor is needed for these tests.

BD-18: target graph and narrow metadata retention replace implicit object globs
and handwritten archive order. The only production source repair in this layer
adds the missing standard `<limits>` include to MultiDtIntegLoopScheduler; GCC
13.3 exposed its reliance on a transitive include during the native build.
