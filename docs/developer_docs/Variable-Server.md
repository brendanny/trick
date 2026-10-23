# Variable Server Design

This page is for developers who change the variable server. For the commands
and the reply formats, see the user documentation:
[Variable Server](../documentation/simulation_capabilities/Variable-Server).

The variable server was rewritten for C++17 (the `vs-rewrite` branch). The rewrite keeps the wire protocol, the `trick.var_*`
API, the S_define job methods and the checkpointed fields. The old design,
with `VariableServerSession`, `VariableReference` and `connection_handlers/`,
is gone.

## Two libraries

| Library | Source | Headers | Depends on |
| --- | --- | --- | --- |
| `libtrick_var_server` (the core) | `trick_source/trick_utils/var_server/` | `include/trick/vs/` | Only the C++17 standard library and POSIX sockets |
| The adapter, in `libtrick` | `trick_source/sim_services/VariableServer/` (`Vs*.cpp`, `VariableServer.cpp`, `var_server_ext.cpp`) | `include/trick/vs/adapter/` | The core, the Memory Manager, the executive, UDUNITS, Python |

The core has no Trick dependency, so its tests run without a SIM:
`make -C trick_source/trick_utils/var_server/test test`, or the CMake test
`trick_var_server_test`. Its README describes each part in more detail.

ICG and SWIG never parse a header in `include/trick/vs/`. The headers they
parse (`VariableServer.hh`, `VariableServerListenThread.hh`,
`variable_server_proto.h`) keep only the public API and the checkpointed
fields.

### Rules

* C++17, limited to what the GCC 8.5 library has: no floating-point
  `std::to_chars`, no `std::pmr`, no `<filesystem>`. Public headers stay C++14.
* No manual memory management. Descriptors are owned by `Fd`, REF2 objects by
  `RefPtr`, threads by `std::thread` members that are joined.
* No iostreams in the variable server. `tools/vs-check-no-iostreams.sh`
  checks this in CI.
* Numbers are formatted in the C locale, whatever locale the SIM sets.
* Wire numbers (`WireType`, `MessageType`, the modes) never change. They are
  the protocol.

## Parts of the core

| Part | Job |
| --- | --- |
| `CommandParser` | Parses a line into a typed `Command` (`var_add`, `var_cycle`, ...). A line that is not a known `trick.var_*` call becomes a `Fallback` that Python runs. |
| `Session` | One client's variable list, copy and write modes, output format and schedule. It does no I/O and starts no thread. |
| `SessionRunner` | One thread per client. It runs commands when they arrive, copies and sends on the `var_cycle` deadline, and sends what the main thread copied. |
| `SessionRegistry` | The list of sessions that the main-thread jobs walk. |
| `TripleBuffer` | Carries a copied frame from the main thread to a runner without a lock on the copy path. |
| `AsciiEncoder`, `BinaryEncoder`, `Packetizer`, `FixedReply` | The reply bytes, with the old split at 8192 bytes. |
| `ListenLoop`, `Listener`, `Connection`, `Poller`, `Beacon` | Non-blocking TCP, UDP and multicast I/O, and the multicast beacon. |
| `Address`, `AddressFilter`, `Endpoint` | IPv4 and IPv6 addresses, the allowlist with CIDR entries, and the bind-address rules. |
| `SystemInterface` | Every system call goes through it, so tests can make one fail. |

## Parts of the adapter

| Part | Job |
| --- | --- |
| `Trick::VariableServer` | The object in `default_trick_sys.sm`. It keeps the job methods and the checkpointed fields, and forwards each job to its `Server`. |
| `VariableServerListenThread` | Configuration only: the requested address, port, user tag and broadcast flag, checkpointed at the old paths. No thread runs in it. Its `ThreadBase` CPU set (`trick_vs.vs.get_listen_thread().cpu_set(n)`) applies to the server's threads. |
| `adapter::Server` | Owns the listener thread, the registry, the runners, the resolver and the units converter. |
| `MemoryResolver` | Resolves a name to a staging plan (REF2 and `ATTRIBUTES`), validates pointers and resolves again after a checkpoint load. |
| `Sampler` | Copies the staged variables of a session into a `Snapshot`. |
| `UdUnitsConverter` | `var_units` conversions through UDUNITS. |
| `VsPythonBridge` | Runs a `Fallback` line through `ip_parse` with the GIL. |
| `var_server_ext.cpp` | The `trick.var_*` functions that SWIG wraps. Each one makes a typed command and gives it to the current session. |

## Threads

| Thread | What it does | What it reads |
| --- | --- | --- |
| Main (the executive) | Runs the jobs: copies for `VS_COPY_SCHEDULED` and `VS_COPY_TOP_OF_FRAME`, the checkpoint jobs, shutdown | Lists and schedules that runners publish |
| Listener | Accepts clients, checks the allowlist, sends the beacon every 2 s | Atomics and the address filter |
| One runner per client | Reads and runs commands, copies for `VS_COPY_ASYNC`, sends replies | Its own `Session` |

A runner publishes its variable list and schedule with `std::atomic_store`
of a `shared_ptr<const T>`. The main thread reads only those copies. A copied
frame carries the list it came from, so a frame from an older list is never
sent.

### The memory lock

Runners read simulation memory under the shared side of a
`std::shared_mutex`. The `preload_checkpoint` job takes the exclusive side
and keeps it until `resumePostCheckpointReload`, so no runner reads memory
while the Memory Manager replaces it. A client that connects during a load
waits until the load ends.

* A Python line runs under the shared lock.
* A typed `var_set` takes the exclusive lock (`Server::write_memory`).
* A thread that holds the GIL lets it go while it waits for the lock.
  Lock order: the memory lock first, then the GIL.

After a load, each runner resolves its names again, and each scheduled
session starts its schedule again from the new sim time.

## How a command runs

```
Client sends "trick.var_add(\"ball.obj.state.output.position[0]\")\n"
SessionRunner reads a batch of complete lines (LineReader)
CommandParser makes cmd::VarAdd { name, units = none }
Session::run(VarAdd) resolves the name through MemoryResolver and adds it
```

A line that is not a typed command goes to Python:

```
Client sends "trick.exec_freeze()\n"
CommandParser makes cmd::Fallback { line }
VsPythonBridge runs ip_parse(line) with the GIL and the shared memory lock
Python calls a var_* function (SWIG) -> var_server_ext.cpp
var_* gives the typed command to Server::current_session(), a thread_local
```

So `trick.var_add(...)` from Python and the typed path do the same work. A
`var_*` call that is not on a runner thread (the input file, an event) does
nothing and returns 0, as before.

`var_server_set_python_commands(False)` turns the Python path off: only
typed commands run. `var_send_ip_errors(True)` makes a session reply
`-1 <length>\n<text>` when its Python line fails.

## Jobs

The job methods in `default_trick_sys.sm` keep their names and job classes:

| Job | Method | Work |
| --- | --- | --- |
| `default_data` | `default_data()` | Default configuration |
| `initialization` | `init()` | Opens the listen socket and starts the listener |
| `preload_checkpoint` | `suspendPreCheckpointReload()` | Takes the memory lock for writing |
| `restart` | `restart()`, `resumePostCheckpointReload()` | Applies the loaded configuration, resolves names again, lets the lock go |
| `top_of_frame` | `copy_and_write_top()` | Copies for `VS_COPY_TOP_OF_FRAME` sessions |
| `automatic_last` | `copy_and_write_scheduled()` | Copies for `VS_COPY_SCHEDULED` sessions |
| `freeze_init`, `freeze_automatic`, `freeze` | `freeze_init()`, `copy_and_write_freeze_scheduled()`, `copy_and_write_freeze()` | The same in freeze mode |
| `shutdown` | `shutdown()` | Stops the listener, asks each runner to stop and joins it. A runner that does not stop in time (it is inside a client command) is left, with a message, so shutdown can continue. |

A copy job only copies into the session's `TripleBuffer` and wakes the
runner. The main thread never sends.

## Tests

| Test | Where | Checks |
| --- | --- | --- |
| Core unit tests | `trick_source/trick_utils/var_server/test` | Parser, encoders, sockets, sessions, runners. `GoldenReplay_test` compares the bytes with the captures of the old server. |
| `VsAdapter_test` | `trick_source/sim_services/VariableServer/test` | The golden cases on a real Memory Manager |
| Conformance suite | `test/SIM_vs_conformance/conformance` | The wire bytes of a running SIM against the goldens, checkpoints, the fixed old-server defects (`--run-known-defects`) and the Python client |
| Soak | `test/SIM_vs_conformance/soak/vs_soak.py` | 8 clients in every mode while a client loads a checkpoint every 10 s |
| `SIM_test_varserv` | `test/SIM_test_varserv` | The SIM test in `test_sims.yml` |
| Fuzzers | `trick_source/trick_utils/var_server/fuzz` | Parser, line reader and encoders (libFuzzer, Clang) |

`tools/vs-ci.sh` runs them in CI, also with ASan, UBSan and TSan.
`tools/vs-tsan.supp` lists the TSan reports outside the variable server's own
state, each with its reason.

## Things to know

* SIM builds do not notice changes to Trick headers (Trick headers are
  `-isystem`, so `-MMD` leaves them out). After you change
  `VariableServer.hh` or another checkpointed class, rebuild the SIM from
  clean (`make spotless`), or ICG offsets go stale.
* The headers in `include/trick/compat/sim_services/VariableServer/` keep the
  old include paths working. `include/trick/VariableServerSessionThread.hh` remains only as a stub, so old S_define
  code that calls `VariableServerSessionThread::set_vs_ptr` still compiles.
