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
| 2 | `CommandParser` (typed commands or Python fallback), `AsciiEncoder`, `BinaryEncoder`, `Packetizer`, `FixedReply`, `Units`, `CLocale`; golden replay against the Phase 0 captures; libFuzzer targets | done |
| 3 | `SystemInterface` (syscall seam), `Fd`, `Address`, `AddressFilter` (IPv4, IPv6, CIDR), `Endpoint` (bind-address rules), `LineReader`, `WriteQueue`, `Listener`, `Connection` (TCP, UDP, multicast), `Poller`, `Beacon`, `ListenLoop`; tests on loopback sockets and with a hooked `SystemInterface` | done |
| 4 | Adapter in `libtrick` (`sim_services/VariableServer/Vs*.cpp`, headers in `include/trick/vs/adapter/`): `MemoryResolver` (REF2 owned by `RefPtr`), staging plans from `ATTRIBUTES`, pointer validation and re-resolving, `Sampler`, `UdUnitsConverter`; `TimeVar` in the core. `VsAdapter_test` replays every golden case on a real Memory Manager. | done |
| 5 | Sessions, runners, jobs, Python bridge, `var_*` façade | next |

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

## Golden replay

`test/GoldenReplay.hh` holds the executor and the checks, so two tests use
them: `GoldenReplay_test.cpp` here, on a model of the conformance SIM, and
`sim_services/VariableServer/test/VsAdapter_test.cc`, on a real Memory
Manager that holds the conformance SIM's own `ConfVars` (run through ICG).

`test/GoldenReplay_test.cpp` runs every case of
`test/SIM_vs_conformance/conformance/cases.py` through the parser and the
encoders, with the conformance SIM's variables modeled in
`test/ConformanceModel.hh`, and compares the bytes with the Phase 0 captures
in `goldens/`. It reads the cases from `test/golden_cases.inc`; after a change
to `cases.py`, run `tools/vs-export-golden-cases.py` (CI checks that the file
is current). With UDUNITS installed, the units cases run too.

Cases in `EXPECTED_TO_CHANGE` record an old defect that the rewrite fixes.
For those, the structure must match the capture, and each changed value must
be the correctly swapped value from the unswapped capture.

## Fuzzing

The libFuzzer targets need Clang:

```bash
cmake -S trick_source/trick_utils/var_server -B build-vs-fuzz \
  -DCMAKE_CXX_COMPILER=clang++ -DTRICK_VS_FUZZ=ON -DBUILD_TESTING=OFF
cmake --build build-vs-fuzz
mkdir -p corpus-parser corpus-encoders
build-vs-fuzz/fuzz/vs_command_parser_fuzz -max_total_time=3600 \
  -dict=trick_source/trick_utils/var_server/fuzz/command_parser.dict \
  corpus-parser trick_source/trick_utils/var_server/fuzz/corpus/command_parser
build-vs-fuzz/fuzz/vs_encoders_fuzz -max_total_time=600 -max_len=8192 corpus-encoders
```

libFuzzer adds new inputs to the first corpus directory only, so the seeds in
the source tree stay as they are.

`vs_line_reader_fuzz` splits its input into random chunks and checks that
no byte is lost or invented and that the batches do not depend on the
chunking. `vs_command_parser_fuzz` checks that a batch is all typed or one Fallback
that holds the input unchanged, and that every typed command survives
`to_python()` and `parse_line()` unchanged. `vs_encoders_fuzz` encodes
random valid values and checks the sizes of what comes out.

## Network

The network code never blocks and owns every descriptor through `Fd`. Each
system call goes through a `SystemInterface`, so tests can make one fail.

* `Listener` binds by the old rules (`Endpoint.hh`): `""`, `"localhost"` or
  the host name bind every interface; a numeric IPv6 address, such as `"::"`,
  turns IPv6 on. `"127.0.0.1"` binds loopback only, for every socket kind
  (decision 12; the old UDP code bound every interface for it).
* `TcpConnection` reads batches of complete lines (`LineReader`). A line
  longer than 200000 bytes is discarded up to its newline; the old server
  stalled on it. Replies wait in a bounded `WriteQueue`; only a full queue
  drops the client.
* `UdpConnection` checks the allowlist against each datagram's sender.
  `MulticastConnection` sends to its group but never reads from it, so it
  cannot run its own replies as commands.
* `ListenLoop` accepts clients and sends the beacon every 2 s. Its owner
  answers, through `ListenPolicy`, whether connections are open and whether
  an address is allowed.

## Rules

* C++17, limited to what GCC 8.5's library has: no floating-point
  `std::to_chars`, no `std::pmr`, no `<filesystem>`.
* No iostreams. `tools/vs-check-no-iostreams.sh` checks this in CI, including
  headers that would pull iostreams in indirectly. Tests may use them.
* Numbers are formatted in the C locale.
* Wire numbers (`WireType`, `MessageType`, modes) never change; they are the
  protocol.
