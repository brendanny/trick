# B2: native parsers and memory manager

Predecessor: B1. Enable `TRICK_BUILD_MEMORY_MANAGER=ON`. This discovers Flex,
Bison, Threads and UDUNITS without requiring Python, SWIG, Perl or ICG.
`Trick::MemoryManager` owns the existing memory-manager sources and the closely
coupled CheckPointAgent implementation. `Trick::MemorySupport` owns ADT,
Unicode, UDUNITS helpers and checkpoint formatting helpers used by the manager.
CheckPointRestart's scheduler remains a later Core service.

Flex/Bison outputs have explicit names under the binary tree. Scanner compilation
waits for its parser header via `ADD_FLEX_BISON_DEPENDENCY`. No checked-in or
premade generated parser is used. Editing a grammar invalidates its own parser
outputs. Production sources remain unchanged.

Acceptance: build, then run `ctest --test-dir <build> -L memory_manager
--output-on-failure`. The always-available smoke exercises declaration, indexed
reference lookup, checkpoint assignment, rejected invalid declarations and
allocation deletion. Its message sink supplies the standalone diagnostic
boundary; it does not simulate any memory-manager behavior.

Enable `TRICK_BUILD_RUNTIME_TESTS=ON` with a GoogleTest config package to also run
the existing creation/singleton, bitfield and type-name suites. More existing
user-type/checkpoint tests need B4 metadata and the B5/B6 runtime.

BD-08: CMake uses native Flex/Bison commands and their dependency edges, without
legacy fallback symlinks to premade sources. BD-18: archive partitioning places
CheckPointAgent beside MemoryManager rather than in the separate runtime archive;
CMake target links carry the required support libraries. This closes the
standalone memory subsystem without requiring the future Python input processor.
