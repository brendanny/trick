# Variable server baseline (Phase 0)

This file records how the current variable server behaves, before the
rewrite changes any server code. Later phases compare with these results.
The raw files are in `baseline/`.

* Base commit: `nasa/trick` master `09d1000` (2026-10-20)
* Machine: Ubuntu 24.04 container, 2 vCPU Intel Xeon 2.80 GHz, kernel 6.18
* Tools: GCC 13.3, Python 3.11.17, SWIG 4.2.0, LLVM 18.1.3, UDUNITS 2.2.28
* Date: 2026-10-22

## Tests

| Check | Plain | ASan + UBSan | TSan |
| --- | --- | --- | --- |
| VS unit tests (7 binaries, 119 tests) | pass | pass | pass |
| Conformance goldens (82 cases) + 3 other tests | pass | pass, no memory errors | pass |
| Beacon (2 groups) | pass | pass | pass |
| SIM_test_varserv (119 of 120; 1 disabled) | pass, 3 runs in a row | pass | pass |
| Known defects (7, expected to fail) | 4 fail, 3 pass by luck | 7 fail | 4 fail, 3 pass |

The golden-suite SIM must end with no ASan or UBSan report, so every golden
comes from a run with no memory error. Under ASan every known-defect test
fails, as it must: each one crashes the SIM or causes a sanitizer report.

## Known defects (`conformance/test_known_defects.py`)

| Test | Defect | Plain build | ASan |
| --- | --- | --- | --- |
| `test_long_string_ascii` | 5000-char string overflows the 4096-byte stage buffer | right output by luck | heap-buffer-overflow, `VariableReference.cpp:362` |
| `test_char_array_without_nul_ascii` | `strlen` runs past a `char[8]` with no NUL | right output by luck | heap-buffer-overflow, `VariableReference.cpp:390` |
| `test_short_enum_ascii` | enum with `short` base read as 4-byte `int` | prints 65534, not -2 | heap-buffer-overflow, `VariableReference.cpp:512` |
| `test_byteswap_indexed_element` | byteswap swaps the declared array length for one element | SIM aborts (heap corruption) | heap-buffer-overflow, `VariableReference.cpp:709, 719` |
| `test_cycle_zero_then_scheduled` | `var_cycle(0)` then scheduled copy | SIM dies (SIGFPE) | UBSan division by zero, `VariableServerSession_commands.cpp:274` |
| `test_long_command_without_newline` | 250 KB command with no newline | session stalls | stack overflow, `TCPConnection.cpp:88` |
| `test_list_changes_during_scheduled_copy` | `var_add`/`var_clear` while the main thread copies | no visible error | heap-use-after-free, `VariableReference.cpp:362, 365`; TSan races in `var_add`, `var_clear` |

## Sanitizer reports

Full reports: `baseline/asan-summary.md`, `baseline/tsan-summary.md`.
Signature lists for comparison in later phases:
`baseline/asan-signatures.json` (17), `baseline/tsan-signatures.json` (33).
Compare a new run with
`tools/vs-sanitizer-summary.py <logs> --baseline baseline/asan-signatures.json`.

ASan and UBSan, by source:

| Where | Kind | From |
| --- | --- | --- |
| `VariableReference.cpp` (7 lines) | heap-buffer-overflow, heap-use-after-free | known-defect tests |
| `TCPConnection.cpp:88` | stack overflow, out-of-bounds index | known-defect tests (long command, list churn) |
| `VariableServerSession_commands.cpp:274` | division by zero | known-defect test |
| `VariableServer.cpp:90` | uninitialized `bool` (`session_log`) | VS unit tests |
| `VariableServerSessionThread_loop.cpp:133` | reference to null `__forced_unwind` | session thread exit |
| `MemoryManager.cpp:39` | uninitialized `bool` | VS unit tests (outside the VS) |
| `JobData.hh:34` | uninitialized `bool` | SIM_test_varserv (outside the VS) |
| `insert_bitfield.c:95` | signed left shift overflow | `var_set` on a bitfield (outside the VS) |

TSan, 33 signatures after suppressing SWIG helpers that run under the GIL:

| Where | Signatures | Examples |
| --- | --- | --- |
| `sim_services/VariableServer` | 18 | `stageValue` vs `var_clear` and `~VariableReference`; unlocked `get_pause`, `get_cycle_tics`, `get_copy_mode`, `get_next_tics`; listen thread `thread_body` vs `set_broadcast`; heap-use-after-free in `byteswap_var` |
| `sim_services/Executive` | 7 | `freeze()`, `run()` and sim time changed by client commands on VS threads while the main thread uses them; `VariableServer::get_next_freeze_call_time` vs `init_freeze_scheduled` |
| `sim_services/Message`, `Timer`, `ThreadBase`, `MemoryManager` | 8 | message publisher and `ref_attributes` called from VS threads; itimer signal handler; a thread leak at exit |

## Benchmark

`bench/vs_bench.py`, 10 s per row, two runs (`baseline/baseline-old-server*.json`).
Each streaming client asks for 50 doubles at 100 Hz in ASCII. The probe
sends `var_send_once` every 20 ms with the default `var_cycle` (0.1 s).

Run 1:

| Copy mode | Clients | Values/s | RTT p50 ms | RTT p99 ms | Frame p99 ms | Frame max ms | Frames > 1 ms late |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ASYNC | 0 | 0 | 80.4 | 82.2 | 10.504 | 14.599 | 9 |
| ASYNC | 1 | 4760 | 80.4 | 166.0 | 10.429 | 141.240 | 6 |
| ASYNC | 8 | 38840 | 80.4 | 83.1 | 10.362 | 12.269 | 4 |
| SCHEDULED | 0 | 0 | 80.4 | 80.8 | 10.086 | 10.829 | 0 |
| SCHEDULED | 1 | 4850 | 80.4 | 81.5 | 10.077 | 14.433 | 4 |
| SCHEDULED | 8 | 38830 | 80.4 | 85.9 | 10.191 | 12.570 | 1 |
| TOP_OF_FRAME | 0 | 0 | 80.4 | 80.9 | 10.125 | 11.700 | 4 |
| TOP_OF_FRAME | 1 | 4835 | 80.4 | 82.2 | 10.131 | 28.730 | 2 |
| TOP_OF_FRAME | 8 | 38825 | 80.3 | 80.8 | 10.863 | 12.101 | 9 |

Run 2:

| Copy mode | Clients | Values/s | RTT p50 ms | RTT p99 ms | Frame p99 ms | Frame max ms | Frames > 1 ms late |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ASYNC | 0 | 0 | 80.4 | 81.1 | 10.102 | 11.742 | 2 |
| ASYNC | 1 | 4830 | 80.4 | 82.0 | 10.855 | 21.810 | 10 |
| ASYNC | 8 | 39044 | 80.3 | 81.0 | 10.201 | 12.222 | 3 |
| SCHEDULED | 0 | 0 | 80.4 | 81.2 | 10.075 | 10.541 | 0 |
| SCHEDULED | 1 | 4830 | 80.4 | 82.4 | 10.356 | 48.800 | 7 |
| SCHEDULED | 8 | 38939 | 80.3 | 81.5 | 10.555 | 12.689 | 6 |
| TOP_OF_FRAME | 0 | 0 | 80.4 | 82.7 | 10.167 | 11.865 | 4 |
| TOP_OF_FRAME | 1 | 4850 | 80.4 | 80.8 | 10.178 | 11.047 | 1 |
| TOP_OF_FRAME | 8 | 38824 | 80.4 | 81.2 | 10.287 | 16.774 | 3 |

How to read it:

* Command round trip is about 80 ms in every row: the session thread reads
  its socket once per `var_cycle` (0.1 s) and the probe waits 20 ms
  between commands. The rewrite runs commands when they arrive.
* Every client gets about 97 of 100 messages per second in every mode.
* Frame p99 stays within 0.9 ms of the 10 ms period. Single slow frames
  (12–141 ms) happen at random in both runs and in rows with no clients, so
  they are this 2-vCPU container, not the server. Compare p99, not max.

## Defects found in Phase 0 that the plan did not list

| Defect | Evidence |
| --- | --- |
| byteswap sends every `char*`, `std::string` and `wchar_t*` value as zeros | goldens `byteswap_strings`, `byteswap_nonames_strings` |
| ASCII reads every enum as `int`, so a `short`-based enum is over-read | `test_short_enum_ascii`; ASan |
| ASCII runs `strlen` past a `char` array with no NUL | `test_char_array_without_nul_ascii`; ASan |
| A `char` array reached through `std::vector<T*>` comes back as its first character | SIM_test_varserv `DISABLED_VectorPointPtrElementRead` |
| The multicast server reads its own output as commands when the host name resolves to 127.0.0.1 | SIM_test_varserv log before the 127.0.0.1 bind |
| Units `deg` is refused (udunits wants `degree`); the value goes out unconverted with no suffix | golden `ascii_units_on_add` |
| `var_send` with an empty list sends nothing; `var_send_once` with a wrong count sends nothing | goldens `ascii_send_empty_list`, `ascii_send_once_count_mismatch` |
| Stdio replies split one `print` into two messages (text, then newline) | golden `ascii_stdio` |
