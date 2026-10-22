# libtrick_var_server

The core of the rewritten variable server. It depends on no other Trick
library: only a C++17 compiler (GCC 8.5 or newer, Clang, Apple Clang) and,
for its tests, GoogleTest. The adapter in `trick_source/sim_services`
connects it to the Memory Manager, the executive, UDUNITS and Python.

Headers are in `include/trick/vs/`; they are internal to Trick and are never
included by a header that ICG or SWIG parses.

## Status

| Phase | Contents | State |
| --- | --- | --- |
| 1 | Data types and interfaces: `WireTypes`, `FieldDesc`, `Snapshot`, `Schedule`, `Command`, `Expected`, `Interfaces` (Resolver, Clock, UnitConverter, CommandFallback); test fakes in `trick/vs/testing/Fakes.hh` | done |
| 2 | Command parser, ASCII and binary encoders, packetizer | next |
| 3 | Sockets, poller, beacon, address filter | |

## Build and test

In a Trick build, `make` builds `lib/libtrick_var_server.a`, and
`make -C trick_source/trick_utils/var_server/test test` runs the tests. The
CMake build adds the target `trick_var_server` and, with `BUILD_TESTING=ON`,
the test `trick_var_server_test`.

On its own, with no other Trick dependency:

```bash
cmake -S trick_source/trick_utils/var_server -B build-vs-core -DCMAKE_CXX_FLAGS=-Werror
cmake --build build-vs-core
ctest --test-dir build-vs-core
```

## Rules

* C++17, limited to what GCC 8.5's library has: no floating-point
  `std::to_chars`, no `std::pmr`, no `<filesystem>`.
* No iostreams. `tools/vs-check-no-iostreams.sh` checks this in CI, including
  headers that would pull iostreams in indirectly. Tests may use them.
* Numbers are formatted in the C locale.
* Wire numbers (`WireType`, `MessageType`, modes) never change; they are the
  protocol.
