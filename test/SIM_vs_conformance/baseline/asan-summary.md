## Sanitizer reports

17 distinct signatures, 31 reports, 30 log files.

| Tool and kind | First Trick frame | Function | Reports |
| --- | --- | --- | --- |
| ASan: dynamic-stack-buffer-overflow | `trick_source/trick_utils/connection_handlers/TCPConnection.cpp:88` | `Trick::TCPConnection::read(std::__cxx11::basic_string<char, ` | 2 |
| ASan: heap-buffer-overflow | `trick_source/sim_services/VariableServer/VariableReference.cpp:390` | `write_escaped_string` | 3 |
| ASan: heap-buffer-overflow | `trick_source/sim_services/VariableServer/VariableReference.cpp:719` | `Trick::VariableReference::byteswap_var(char*, char*, Trick::` | 3 |
| ASan: heap-buffer-overflow | `trick_source/sim_services/VariableServer/VariableReference.cpp:512` | `Trick::VariableReference::writeValueAscii(std::ostream&) con` | 2 |
| ASan: heap-buffer-overflow | `trick_source/sim_services/VariableServer/VariableReference.cpp:709` | `Trick::VariableReference::byteswap_var(char*, char*, Trick::` | 2 |
| ASan: heap-buffer-overflow | `trick_source/sim_services/VariableServer/VariableReference.cpp:362` | `Trick::VariableReference::stageValue(bool)` | 1 |
| ASan: heap-buffer-overflow | `trick_source/sim_services/VariableServer/VariableReference.cpp:391` | `write_escaped_string` | 1 |
| ASan: heap-use-after-free | `trick_source/sim_services/VariableServer/VariableReference.cpp:365` | `Trick::VariableReference::stageValue(bool)` | 2 |
| ASan: heap-use-after-free | `trick_source/sim_services/VariableServer/VariableReference.cpp:362` | `Trick::VariableReference::stageValue(bool)` | 1 |
| UBSan: division by zero | `VariableServerSession_commands.cpp:274` | `` | 1 |
| UBSan: index N out of bounds for type 'char [*]' | `TCPConnection.cpp:88` | `` | 1 |
| UBSan: left shift of N by N places cannot be represented in type 'int' | `insert_bitfield.c:95` | `` | 1 |
| UBSan: load of value N, which is not a valid value for type 'bool' | `MemoryManager.cpp:39` | `` | 4 |
| UBSan: load of value N, which is not a valid value for type 'bool' | `VariableServer.cpp:90` | `` | 2 |
| UBSan: load of value N, which is not a valid value for type 'bool' | `include/trick/JobData.hh:34` | `` | 2 |
| UBSan: reference binding to null pointer of type 'struct __forced_unwind' | `VariableServerSessionThread_loop.cpp:133` | `` | 2 |
| UBSan: store to address N with insufficient space for an object of type 'char' | `TCPConnection.cpp:88` | `` | 1 |

### First report of each signature

<details><summary>ASan: dynamic-stack-buffer-overflow at trick_source/trick_utils/connection_handlers/TCPConnection.cpp:88</summary>

```
==16467==ERROR: AddressSanitizer: dynamic-stack-buffer-overflow on address 0x7fc3e147f4e0 at pc 0x561322f5ff4f bp 0x7fc3e144e770 sp 0x7fc3e144e760
WRITE of size 1 at 0x7fc3e147f4e0 thread T6
    #0 0x561322f5ff4e in Trick::TCPConnection::read(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >&, int) /home/claude/brendanny/trick-asan/trick_source/trick_utils/connection_handlers/TCPConnection.cpp:88
    #1 0x56132221dbca in Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:159
    #2 0x561322223c33 in Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101
    #3 0x5613221b4013 in Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-asan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395
    #4 0x7fc3ef25ea41 in asan_thread_start ../../../../src/libsanitizer/asan/asan_interceptors.cpp:234
    #5 0x7fc3eda9cb83 in start_thread nptl/pthread_create.c:447
    #6 0x7fc3edb29ecb in clone3 ../sysdeps/unix/sysv/linux/x86_64/clone3.S:78

Address 0x7fc3e147f4e0 is located in stack of thread T6
```

</details>

<details><summary>ASan: heap-buffer-overflow at trick_source/sim_services/VariableServer/VariableReference.cpp:362</summary>

```
```

</details>

<details><summary>ASan: heap-buffer-overflow at trick_source/sim_services/VariableServer/VariableReference.cpp:362</summary>

```
==16412==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x521000310d00 at pc 0x7f34cccfb303 bp 0x7f34c03171b0 sp 0x7f34c0316958
WRITE of size 5001 at 0x521000310d00 thread T5
    #0 0x7f34cccfb302 in memcpy ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors_memintrinsics.inc:115
    #1 0x561c15dd4782 in memcpy /usr/include/x86_64-linux-gnu/bits/string_fortified.h:29
    #2 0x561c15dd4782 in Trick::VariableReference::stageValue(bool) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableReference.cpp:362
    #3 0x561c15e3a5d5 in Trick::VariableServerSession::copy_sim_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, bool) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:28
    #4 0x561c15e3a01e in Trick::VariableServerSession::copy_sim_data() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:13
    #5 0x561c15e1f7a6 in Trick::VariableServerSession::var_send() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:225
    #6 0x561c15e62673 in var_send() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/var_server_ext.cpp:100
    #7 0x561c163aa9f1 in _wrap_var_send swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156739
    #8 0x7f34cc5d37fe  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #9 0x7f34cc580f67 in PyObject_Vectorcall (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x180f67) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #10 0x7f34cc50ca3c in _PyEval_EvalFrameDefault (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x10ca3c) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #11 0x7f34cc7e863b  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x3e863b) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #12 0x7f34cc6756d7 in PyEval_EvalCode (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2756d7) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #13 0x7f34cc6c733a  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c733a) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #14 0x7f34cc6c8563 in PyRun_StringFlags (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c8563) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #15 0x7f34cc6c85cf in PyRun_SimpleStringFlags (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c85cf) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #16 0x561c1614a9e2 in Trick::IPPython::parse(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-asan/trick_source/sim_services/InputProcessor/IPPython.cpp:236
    #17 0x561c1616e91f in ip_parse /home/claude/brendanny/trick-asan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17
    #18 0x561c15e17d14 in Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162
    #19 0x561c15e1dc33 in Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101
    #20 0x561c15dae013 in Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-asan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395
    #21 0x7f34ccc5ea41 in asan_thread_start ../../../../src/libsanitizer/asan/asan_interceptors.cpp:234
    #22 0x7f34cb49cb83 in start_thread nptl/pthread_create.c:447
```

</details>

<details><summary>ASan: heap-buffer-overflow at trick_source/sim_services/VariableServer/VariableReference.cpp:390</summary>

```
==16412==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x521000310d00 at pc 0x7f34ccc7d96f bp 0x7f34c0316670 sp 0x7f34c0315e18
READ of size 5001 at 0x521000310d00 thread T5
    #0 0x7f34ccc7d96e in strlen ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc:391
    #1 0x561c15dc7aa9 in write_escaped_string /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableReference.cpp:390
    #2 0x561c15dcc7b5 in Trick::VariableReference::writeValueAscii(std::ostream&) const /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableReference.cpp:482
    #3 0x561c15e43204 in Trick::VariableServerSession::write_ascii_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> > const&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:142
    #4 0x561c15e3bb31 in Trick::VariableServerSession::write_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:233
    #5 0x561c15e3abfa in Trick::VariableServerSession::write_data() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:201
    #6 0x561c15e1f816 in Trick::VariableServerSession::var_send() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:226
    #7 0x561c15e62673 in var_send() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/var_server_ext.cpp:100
    #8 0x561c163aa9f1 in _wrap_var_send swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156739
    #9 0x7f34cc5d37fe  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #10 0x7f34cc580f67 in PyObject_Vectorcall (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x180f67) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #11 0x7f34cc50ca3c in _PyEval_EvalFrameDefault (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x10ca3c) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #12 0x7f34cc7e863b  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x3e863b) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #13 0x7f34cc6756d7 in PyEval_EvalCode (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2756d7) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #14 0x7f34cc6c733a  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c733a) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #15 0x7f34cc6c8563 in PyRun_StringFlags (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c8563) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #16 0x7f34cc6c85cf in PyRun_SimpleStringFlags (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c85cf) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #17 0x561c1614a9e2 in Trick::IPPython::parse(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-asan/trick_source/sim_services/InputProcessor/IPPython.cpp:236
    #18 0x561c1616e91f in ip_parse /home/claude/brendanny/trick-asan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17
    #19 0x561c15e17d14 in Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162
    #20 0x561c15e1dc33 in Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101
    #21 0x561c15dae013 in Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-asan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395
    #22 0x7f34ccc5ea41 in asan_thread_start ../../../../src/libsanitizer/asan/asan_interceptors.cpp:234
```

</details>

<details><summary>ASan: heap-buffer-overflow at trick_source/sim_services/VariableServer/VariableReference.cpp:391</summary>

```
==16412==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x521000310d00 at pc 0x561c15dc784e bp 0x7f34c0316670 sp 0x7f34c0316660
READ of size 1 at 0x521000310d00 thread T5
    #0 0x561c15dc784d in write_escaped_string /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableReference.cpp:391
    #1 0x561c15dcc7b5 in Trick::VariableReference::writeValueAscii(std::ostream&) const /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableReference.cpp:482
    #2 0x561c15e43204 in Trick::VariableServerSession::write_ascii_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> > const&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:142
    #3 0x561c15e3bb31 in Trick::VariableServerSession::write_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:233
    #4 0x561c15e3abfa in Trick::VariableServerSession::write_data() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:201
    #5 0x561c15e1f816 in Trick::VariableServerSession::var_send() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:226
    #6 0x561c15e62673 in var_send() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/var_server_ext.cpp:100
    #7 0x561c163aa9f1 in _wrap_var_send swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156739
    #8 0x7f34cc5d37fe  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #9 0x7f34cc580f67 in PyObject_Vectorcall (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x180f67) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #10 0x7f34cc50ca3c in _PyEval_EvalFrameDefault (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x10ca3c) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #11 0x7f34cc7e863b  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x3e863b) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #12 0x7f34cc6756d7 in PyEval_EvalCode (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2756d7) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #13 0x7f34cc6c733a  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c733a) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #14 0x7f34cc6c8563 in PyRun_StringFlags (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c8563) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #15 0x7f34cc6c85cf in PyRun_SimpleStringFlags (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c85cf) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #16 0x561c1614a9e2 in Trick::IPPython::parse(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-asan/trick_source/sim_services/InputProcessor/IPPython.cpp:236
    #17 0x561c1616e91f in ip_parse /home/claude/brendanny/trick-asan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17
    #18 0x561c15e17d14 in Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162
    #19 0x561c15e1dc33 in Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101
    #20 0x561c15dae013 in Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-asan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395
    #21 0x7f34ccc5ea41 in asan_thread_start ../../../../src/libsanitizer/asan/asan_interceptors.cpp:234
    #22 0x7f34cb49cb83 in start_thread nptl/pthread_create.c:447
```

</details>

<details><summary>ASan: heap-buffer-overflow at trick_source/sim_services/VariableServer/VariableReference.cpp:512</summary>

```
==16430==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x5020000bb110 at pc 0x56423a4d42d3 bp 0x7f9365695770 sp 0x7f9365695760
READ of size 4 at 0x5020000bb110 thread T6
    #0 0x56423a4d42d2 in Trick::VariableReference::writeValueAscii(std::ostream&) const /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableReference.cpp:512
    #1 0x56423a54a204 in Trick::VariableServerSession::write_ascii_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> > const&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:142
    #2 0x56423a542b31 in Trick::VariableServerSession::write_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:233
    #3 0x56423a541bfa in Trick::VariableServerSession::write_data() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:201
    #4 0x56423a526816 in Trick::VariableServerSession::var_send() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:226
    #5 0x56423a569673 in var_send() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/var_server_ext.cpp:100
    #6 0x56423aab19f1 in _wrap_var_send swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156739
    #7 0x7f93723d37fe  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #8 0x7f9372380f67 in PyObject_Vectorcall (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x180f67) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #9 0x7f937230ca3c in _PyEval_EvalFrameDefault (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x10ca3c) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #10 0x7f93725e863b  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x3e863b) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #11 0x7f93724756d7 in PyEval_EvalCode (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2756d7) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #12 0x7f93724c733a  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c733a) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #13 0x7f93724c8563 in PyRun_StringFlags (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c8563) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #14 0x7f93724c85cf in PyRun_SimpleStringFlags (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c85cf) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #15 0x56423a8519e2 in Trick::IPPython::parse(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-asan/trick_source/sim_services/InputProcessor/IPPython.cpp:236
    #16 0x56423a87591f in ip_parse /home/claude/brendanny/trick-asan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17
    #17 0x56423a51ed14 in Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162
    #18 0x56423a524c33 in Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101
    #19 0x56423a4b5013 in Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-asan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395
    #20 0x7f9372a5ea41 in asan_thread_start ../../../../src/libsanitizer/asan/asan_interceptors.cpp:234
    #21 0x7f937129cb83 in start_thread nptl/pthread_create.c:447
    #22 0x7f9371329ecb in clone3 ../sysdeps/unix/sysv/linux/x86_64/clone3.S:78
```

</details>

<details><summary>ASan: heap-buffer-overflow at trick_source/sim_services/VariableServer/VariableReference.cpp:709</summary>

```
==16439==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x5020000bb134 at pc 0x55ec346f65a6 bp 0x7fc14c333750 sp 0x7fc14c333740
READ of size 4 at 0x5020000bb134 thread T6
    #0 0x55ec346f65a5 in Trick::VariableReference::byteswap_var(char*, char*, Trick::VariableReference const&) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableReference.cpp:709
    #1 0x55ec346f67f2 in Trick::VariableReference::byteswap_var(char*, char*) const /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableReference.cpp:673
    #2 0x55ec346f69d2 in Trick::VariableReference::writeValueBinary(std::ostream&, bool) const /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableReference.cpp:759
    #3 0x55ec34765119 in Trick::VariableServerSession::write_binary_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> > const&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:113
    #4 0x55ec347616aa in Trick::VariableServerSession::write_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:230
    #5 0x55ec34760bfa in Trick::VariableServerSession::write_data() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:201
    #6 0x55ec34745816 in Trick::VariableServerSession::var_send() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:226
    #7 0x55ec34788673 in var_send() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/var_server_ext.cpp:100
    #8 0x55ec34cd09f1 in _wrap_var_send swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156739
    #9 0x7fc1599d37fe  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #10 0x7fc159980f67 in PyObject_Vectorcall (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x180f67) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #11 0x7fc15990ca3c in _PyEval_EvalFrameDefault (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x10ca3c) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #12 0x7fc159be863b  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x3e863b) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #13 0x7fc159a756d7 in PyEval_EvalCode (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2756d7) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #14 0x7fc159ac733a  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c733a) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #15 0x7fc159ac8563 in PyRun_StringFlags (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c8563) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #16 0x7fc159ac85cf in PyRun_SimpleStringFlags (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c85cf) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #17 0x55ec34a709e2 in Trick::IPPython::parse(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-asan/trick_source/sim_services/InputProcessor/IPPython.cpp:236
    #18 0x55ec34a9491f in ip_parse /home/claude/brendanny/trick-asan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17
    #19 0x55ec3473dd14 in Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162
    #20 0x55ec34743c33 in Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101
    #21 0x55ec346d4013 in Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-asan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395
    #22 0x7fc15a05ea41 in asan_thread_start ../../../../src/libsanitizer/asan/asan_interceptors.cpp:234
```

</details>

<details><summary>ASan: heap-buffer-overflow at trick_source/sim_services/VariableServer/VariableReference.cpp:719</summary>

```
==16439==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x5020000bb278 at pc 0x55ec346f66c0 bp 0x7fc14c333750 sp 0x7fc14c333740
READ of size 8 at 0x5020000bb278 thread T6
    #0 0x55ec346f66bf in Trick::VariableReference::byteswap_var(char*, char*, Trick::VariableReference const&) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableReference.cpp:719
    #1 0x55ec346f67f2 in Trick::VariableReference::byteswap_var(char*, char*) const /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableReference.cpp:673
    #2 0x55ec346f69d2 in Trick::VariableReference::writeValueBinary(std::ostream&, bool) const /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableReference.cpp:759
    #3 0x55ec34765119 in Trick::VariableServerSession::write_binary_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> > const&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:113
    #4 0x55ec347616aa in Trick::VariableServerSession::write_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:230
    #5 0x55ec34760bfa in Trick::VariableServerSession::write_data() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:201
    #6 0x55ec34745816 in Trick::VariableServerSession::var_send() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:226
    #7 0x55ec34788673 in var_send() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/var_server_ext.cpp:100
    #8 0x55ec34cd09f1 in _wrap_var_send swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156739
    #9 0x7fc1599d37fe  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #10 0x7fc159980f67 in PyObject_Vectorcall (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x180f67) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #11 0x7fc15990ca3c in _PyEval_EvalFrameDefault (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x10ca3c) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #12 0x7fc159be863b  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x3e863b) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #13 0x7fc159a756d7 in PyEval_EvalCode (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2756d7) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #14 0x7fc159ac733a  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c733a) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #15 0x7fc159ac8563 in PyRun_StringFlags (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c8563) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #16 0x7fc159ac85cf in PyRun_SimpleStringFlags (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c85cf) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #17 0x55ec34a709e2 in Trick::IPPython::parse(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-asan/trick_source/sim_services/InputProcessor/IPPython.cpp:236
    #18 0x55ec34a9491f in ip_parse /home/claude/brendanny/trick-asan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17
    #19 0x55ec3473dd14 in Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162
    #20 0x55ec34743c33 in Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101
    #21 0x55ec346d4013 in Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-asan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395
    #22 0x7fc15a05ea41 in asan_thread_start ../../../../src/libsanitizer/asan/asan_interceptors.cpp:234
```

</details>

<details><summary>ASan: heap-use-after-free at trick_source/sim_services/VariableServer/VariableReference.cpp:362</summary>

```
==16467==ERROR: AddressSanitizer: heap-use-after-free on address 0x5280017e4100 at pc 0x7fc3ef2fb303 bp 0x7ffe1b741190 sp 0x7ffe1b740938
WRITE of size 16000 at 0x5280017e4100 thread T0
    #0 0x7fc3ef2fb302 in memcpy ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors_memintrinsics.inc:115
    #1 0x5613221da782 in memcpy /usr/include/x86_64-linux-gnu/bits/string_fortified.h:29
    #2 0x5613221da782 in Trick::VariableReference::stageValue(bool) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableReference.cpp:362
    #3 0x5613222405d5 in Trick::VariableServerSession::copy_sim_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, bool) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:28
    #4 0x56132224001e in Trick::VariableServerSession::copy_sim_data() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:13
    #5 0x56132223e21e in Trick::VariableServerSession::copy_and_write_freeze_scheduled(long long) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:41
    #6 0x561322255dbc in Trick::VariableServer::copy_and_write_freeze_scheduled() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServer_copy_and_write_freeze_scheduled.cpp:15
    #7 0x5613216712f9 in VariableServerSimObject::call_function(Trick::JobData*) build/S_source.cpp:549
    #8 0x56132218e0c0 in Trick::JobData::call() /home/claude/brendanny/trick-asan/trick_source/sim_services/SimObject/JobData.cpp:184
    #9 0x561321da7128 in Trick::Executive::freeze_loop() /home/claude/brendanny/trick-asan/trick_source/sim_services/Executive/Executive_freeze_loop.cpp:43
    #10 0x561321dbbe70 in Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-asan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:42
    #11 0x561321db729f in Trick::Executive::loop() /home/claude/brendanny/trick-asan/trick_source/sim_services/Executive/Executive_loop.cpp:43
    #12 0x56132253ab89 in master(int, char**) /home/claude/brendanny/trick-asan/trick_source/sim_services/mains/master.cpp:45
    #13 0x561321671436 in main build/S_source.cpp:1350
    #14 0x7fc3eda2a1c9 in __libc_start_call_main ../sysdeps/nptl/libc_start_call_main.h:58
    #15 0x7fc3eda2a28a in __libc_start_main_impl ../csu/libc-start.c:360
    #16 0x56132166cad4 in _start (/home/claude/brendanny/trick-asan/test/SIM_vs_conformance/S_main_Linux_13.3_x86_64.exe+0x3433ad4) (BuildId: adf927ae5ed8277f49efc80c5969f9a937cb0ea5)

0x5280017e4100 is located 0 bytes inside of 16000-byte region [0x5280017e4100,0x5280017e7f80)
freed by thread T6 here:
    #0 0x7fc3ef2fc4d8 in free ../../../../src/libsanitizer/asan/asan_malloc_linux.cpp:52
    #1 0x5613221d07e0 in Trick::VariableReference::~VariableReference() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableReference.cpp:189
    #2 0x561322224f68 in Trick::VariableServerSession::var_clear() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:217
```

</details>

<details><summary>ASan: heap-use-after-free at trick_source/sim_services/VariableServer/VariableReference.cpp:365</summary>

```
==16467==ERROR: AddressSanitizer: heap-use-after-free on address 0x50e000403705 at pc 0x5613221db58f bp 0x7ffe1b741190 sp 0x7ffe1b741180
WRITE of size 1 at 0x50e000403705 thread T0
    #0 0x5613221db58e in Trick::VariableReference::stageValue(bool) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableReference.cpp:365
    #1 0x5613222405d5 in Trick::VariableServerSession::copy_sim_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, bool) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:28
    #2 0x56132224001e in Trick::VariableServerSession::copy_sim_data() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:13
    #3 0x56132223e21e in Trick::VariableServerSession::copy_and_write_freeze_scheduled(long long) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:41
    #4 0x561322255dbc in Trick::VariableServer::copy_and_write_freeze_scheduled() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServer_copy_and_write_freeze_scheduled.cpp:15
    #5 0x5613216712f9 in VariableServerSimObject::call_function(Trick::JobData*) build/S_source.cpp:549
    #6 0x56132218e0c0 in Trick::JobData::call() /home/claude/brendanny/trick-asan/trick_source/sim_services/SimObject/JobData.cpp:184
    #7 0x561321da7128 in Trick::Executive::freeze_loop() /home/claude/brendanny/trick-asan/trick_source/sim_services/Executive/Executive_freeze_loop.cpp:43
    #8 0x561321dbbe70 in Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-asan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:42
    #9 0x561321db729f in Trick::Executive::loop() /home/claude/brendanny/trick-asan/trick_source/sim_services/Executive/Executive_loop.cpp:43
    #10 0x56132253ab89 in master(int, char**) /home/claude/brendanny/trick-asan/trick_source/sim_services/mains/master.cpp:45
    #11 0x561321671436 in main build/S_source.cpp:1350
    #12 0x7fc3eda2a1c9 in __libc_start_call_main ../sysdeps/nptl/libc_start_call_main.h:58
    #13 0x7fc3eda2a28a in __libc_start_main_impl ../csu/libc-start.c:360
    #14 0x56132166cad4 in _start (/home/claude/brendanny/trick-asan/test/SIM_vs_conformance/S_main_Linux_13.3_x86_64.exe+0x3433ad4) (BuildId: adf927ae5ed8277f49efc80c5969f9a937cb0ea5)

0x50e000403705 is located 37 bytes inside of 152-byte region [0x50e0004036e0,0x50e000403778)
freed by thread T6 here:
    #0 0x7fc3ef2ff5e8 in operator delete(void*, unsigned long) ../../../../src/libsanitizer/asan/asan_new_delete.cpp:164
    #1 0x561322224f75 in Trick::VariableServerSession::var_clear() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:217
    #2 0x561322268735 in var_clear() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/var_server_ext.cpp:109
    #3 0x5613227b0f66 in _wrap_var_clear swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156761
    #4 0x7fc3eebd37fe  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
```

</details>

<details><summary>UBSan: division by zero at VariableServerSession_commands.cpp:274</summary>

```
VariableServerSession_commands.cpp:274:44: runtime error: division by zero
    #0 0x560544ba40a7 in Trick::VariableServerSession::var_set_copy_mode(int) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:274
    #1 0x560544be6f30 in var_set_copy_mode(int) /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/var_server_ext.cpp:208
    #2 0x56054541a666 in _wrap_var_set_copy_mode swig_Linux_13.3_x86_64/sim_services_wrap.cpp:157101
    #3 0x7f9236bd3435  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x1d3435) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #4 0x7f9236b80f67 in PyObject_Vectorcall (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x180f67) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #5 0x7f9236b0ca3c in _PyEval_EvalFrameDefault (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x10ca3c) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #6 0x7f9236de863b  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x3e863b) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #7 0x7f9236c756d7 in PyEval_EvalCode (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2756d7) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #8 0x7f9236cc733a  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c733a) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #9 0x7f9236cc8563 in PyRun_StringFlags (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c8563) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #10 0x7f9236cc85cf in PyRun_SimpleStringFlags (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c85cf) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #11 0x560544ece9e2 in Trick::IPPython::parse(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-asan/trick_source/sim_services/InputProcessor/IPPython.cpp:236
    #12 0x560544ef291f in ip_parse /home/claude/brendanny/trick-asan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17
    #13 0x560544b9bd14 in Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162
```

</details>

<details><summary>UBSan: index N out of bounds for type 'char [*]' at TCPConnection.cpp:88</summary>

```
TCPConnection.cpp:88:24: runtime error: index 200000 out of bounds for type 'char [*]'
    #0 0x561322f5fd9a in Trick::TCPConnection::read(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >&, int) /home/claude/brendanny/trick-asan/trick_source/trick_utils/connection_handlers/TCPConnection.cpp:88
    #1 0x56132221dbca in Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:159
    #2 0x561322223c33 in Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101
    #3 0x5613221b4013 in Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-asan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395
    #4 0x7fc3ef25ea41 in asan_thread_start ../../../../src/libsanitizer/asan/asan_interceptors.cpp:234
    #5 0x7fc3eda9cb83 in start_thread nptl/pthread_create.c:447
    #6 0x7fc3edb29ecb in clone3 ../sysdeps/unix/sysv/linux/x86_64/clone3.S:78

TCPConnection.cpp:88:26: runtime error: store to address 0x7fc3e147f4e0 with insufficient space for an object of type 'char'
0x7fc3e147f4e0: note: pointer points here
 74 72 69 63  00 f5 47 e1 c3 7f 00 00  33 de 2d ef c3 7f 00 00  80 a8 08 00 70 50 00 00  40 0d 03 00
              ^ 
    #0 0x561322f5fdca in Trick::TCPConnection::read(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >&, int) /home/claude/brendanny/trick-asan/trick_source/trick_utils/connection_handlers/TCPConnection.cpp:88
    #1 0x56132221dbca in Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:159
```

</details>

<details><summary>UBSan: left shift of N by N places cannot be represented in type 'int' at insert_bitfield.c:95</summary>

```
insert_bitfield.c:95:28: runtime error: left shift of 2112 by 20 places cannot be represented in type 'int'
    #0 0x55a5265b3698 in insert_bitfield_any /home/claude/brendanny/trick-asan/trick_source/sim_services/MemoryManager/insert_bitfield.c:95
    #1 0x55a52669c8a6 in Trick::MemoryManager::assign_recursive(void*, ATTRIBUTES_tag*, int, int, v_tree*, cv_converter*) /home/claude/brendanny/trick-asan/trick_source/sim_services/MemoryManager/MemoryManager_ref_assignment.cpp:223
    #2 0x55a5266a3d94 in Trick::MemoryManager::ref_assignment(REF2*, v_tree*) /home/claude/brendanny/trick-asan/trick_source/sim_services/MemoryManager/MemoryManager_ref_assignment.cpp:508
    #3 0x55a52545850a in CCP_parse(ChkPtParseContext*) /home/claude/brendanny/trick-asan/trick_source/sim_services/CheckPointAgent/input_parser.y:268
    #4 0x55a525408655 in Trick::ClassicCheckPointAgent::restore(std::istream*) /home/claude/brendanny/trick-asan/trick_source/sim_services/CheckPointAgent/ClassicCheckPointAgent.cpp:339
    #5 0x55a5266c401b in Trick::MemoryManager::read_checkpoint(std::istream*, bool) /home/claude/brendanny/trick-asan/trick_source/sim_services/MemoryManager/MemoryManager_restore.cpp:25
    #6 0x55a5266c7290 in Trick::MemoryManager::read_checkpoint(char const*, bool) /home/claude/brendanny/trick-asan/trick_source/sim_services/MemoryManager/MemoryManager_restore.cpp:72
    #7 0x55a5266c94d9 in Trick::MemoryManager::init_from_checkpoint(char const*, bool) /home/claude/brendanny/trick-asan/trick_source/sim_services/MemoryManager/MemoryManager_restore.cpp:116
    #8 0x55a52546367f in Trick::CheckPointRestart::load_checkpoint_job() /home/claude/brendanny/trick-asan/trick_source/sim_services/CheckPointRestart/CheckPointRestart.cpp:353
    #9 0x55a524e27818 in CheckPointRestartSimObject::call_function(Trick::JobData*) build/S_source.cpp:178
    #10 0x55a52595e756 in Trick::JobData::call() /home/claude/brendanny/trick-asan/trick_source/sim_services/SimObject/JobData.cpp:184
    #11 0x55a525582eb4 in Trick::Executive::freeze_loop() /home/claude/brendanny/trick-asan/trick_source/sim_services/Executive/Executive_freeze_loop.cpp:67
    #12 0x55a52559751a in Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-asan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:42
    #13 0x55a525592949 in Trick::Executive::loop() /home/claude/brendanny/trick-asan/trick_source/sim_services/Executive/Executive_loop.cpp:43
```

</details>

<details><summary>UBSan: load of value N, which is not a valid value for type 'bool' at MemoryManager.cpp:39</summary>

```
MemoryManager.cpp:39:70: runtime error: load of value 190, which is not a valid value for type 'bool'
    #0 0x5587a18b0e82 in Trick::MemoryManager::MemoryManager() /home/claude/brendanny/trick-asan/trick_source/sim_services/MemoryManager/MemoryManager.cpp:39
    #1 0x5587a188290f in VariableReference_test::VariableReference_test() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/test/VariableReference_test.hh:48
    #2 0x5587a18844ca in VariableReference_test_getName_Test::VariableReference_test_getName_Test() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/test/VariableReference_test.cc:3
    #3 0x5587a18844ca in testing::internal::TestFactoryImpl<VariableReference_test_getName_Test>::CreateTest() /usr/include/gtest/internal/gtest-internal.h:457
    #4 0x5587a1d4e1e6 in testing::Test* testing::internal::HandleExceptionsInMethodIfSupported<testing::internal::TestFactoryBase, testing::Test*>(testing::internal::TestFactoryBase*, testing::Test* (testing::internal::TestFactoryBase::*)(), char const*) (/home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/test/VariableReference_test+0xee31e6) (BuildId: c84ecceee01e0c7defe65b8b6055da22afc49f69)
    #5 0x5587a1d35a3d in testing::TestInfo::Run() (/home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/test/VariableReference_test+0xecaa3d) (BuildId: c84ecceee01e0c7defe65b8b6055da22afc49f69)
    #6 0x5587a1d35cde in testing::TestSuite::Run() (/home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/test/VariableReference_test+0xecacde) (BuildId: c84ecceee01e0c7defe65b8b6055da22afc49f69)
    #7 0x5587a1d43b4b in testing::internal::UnitTestImpl::RunAllTests() (/home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/test/VariableReference_test+0xed8b4b) (BuildId: c84ecceee01e0c7defe65b8b6055da22afc49f69)
    #8 0x5587a1d4e666 in bool testing::internal::HandleExceptionsInMethodIfSupported<testing::internal::UnitTestImpl, bool>(testing::internal::UnitTestImpl*, bool (testing::internal::UnitTestImpl::*)(), char const*) (/home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/test/VariableReference_test+0xee3666) (BuildId: c84ecceee01e0c7defe65b8b6055da22afc49f69)
    #9 0x5587a1d35ed7 in testing::UnitTest::Run() (/home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/test/VariableReference_test+0xecaed7) (BuildId: c84ecceee01e0c7defe65b8b6055da22afc49f69)
    #10 0x5587a185f433 in main (/home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/test/VariableReference_test+0x9f4433) (BuildId: c84ecceee01e0c7defe65b8b6055da22afc49f69)
    #11 0x7fd04b82a1c9 in __libc_start_call_main ../sysdeps/nptl/libc_start_call_main.h:58
    #12 0x7fd04b82a28a in __libc_start_main_impl ../csu/libc-start.c:360
    #13 0x5587a185f464 in _start (/home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/test/VariableReference_test+0x9f4464) (BuildId: c84ecceee01e0c7defe65b8b6055da22afc49f69)
```

</details>

<details><summary>UBSan: load of value N, which is not a valid value for type 'bool' at VariableServer.cpp:90</summary>

```
VariableServer.cpp:90:12: runtime error: load of value 190, which is not a valid value for type 'bool'
    #0 0x5602a40a79b7 in Trick::VariableServer::get_session_log() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServer.cpp:90
    #1 0x5602a40d70e6 in Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:64
    #2 0x5602a40a11b3 in Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-asan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395
    #3 0x7f941505ea41 in asan_thread_start ../../../../src/libsanitizer/asan/asan_interceptors.cpp:234
    #4 0x7f941389cb83 in start_thread nptl/pthread_create.c:447
    #5 0x7f9413929ecb in clone3 ../sysdeps/unix/sysv/linux/x86_64/clone3.S:78

[       OK ] VariableServerListenThread_test.accept_connection (3002 ms)
[ RUN      ] VariableServerListenThread_test.reject_connection_when_disabled

GMOCK WARNING:
Uninteresting mock function call - returning default value.
    Function call: publish(1, "Trick VariableServer: Enabling the Variable Server. See Trick documentation for associated security concerns.\n")
          Returns: 0
```

</details>

<details><summary>UBSan: load of value N, which is not a valid value for type 'bool' at include/trick/JobData.hh:34</summary>

```
/home/claude/brendanny/trick-asan/include/trick/JobData.hh:34:11: runtime error: load of value 190, which is not a valid value for type 'bool'
    #0 0x55a52557bf7c in Trick::JobData::operator=(Trick::JobData const&) /home/claude/brendanny/trick-asan/include/trick/JobData.hh:34
    #1 0x55a525579023 in Trick::Executive::checkpoint() /home/claude/brendanny/trick-asan/trick_source/sim_services/Executive/Executive_checkpoint.cpp:29
    #2 0x55a524e32275 in SysSimObject::call_function(Trick::JobData*) build/S_source.cpp:40
    #3 0x55a52546ddc1 in Trick::CheckPointRestart::do_checkpoint(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >, bool) /home/claude/brendanny/trick-asan/trick_source/sim_services/CheckPointRestart/CheckPointRestart.cpp:187
    #4 0x55a5254701df in Trick::CheckPointRestart::checkpoint(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >, bool, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-asan/trick_source/sim_services/CheckPointRestart/CheckPointRestart.cpp:168
    #5 0x55a5260d5769 in _wrap_CheckPointRestart_checkpoint__SWIG_0 swig_Linux_13.3_x86_64/sim_services_wrap.cpp:123442
    #6 0x55a5263680db in _wrap_CheckPointRestart_checkpoint swig_Linux_13.3_x86_64/sim_services_wrap.cpp:123518
    #7 0x7f20fefd3125  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x1d3125) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #8 0x7f20fef829ab in _PyObject_Call (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x1829ab) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #9 0x7f20fef0d361 in _PyEval_EvalFrameDefault (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x10d361) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #10 0x7f20ff1e863b  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x3e863b) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #11 0x7f20ff0756d7 in PyEval_EvalCode (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2756d7) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #12 0x7f20ff0c733a  (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c733a) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #13 0x7f20ff0c8563 in PyRun_StringFlags (/lib/x86_64-linux-gnu/libpython3.11.so.1.0+0x2c8563) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
```

</details>

<details><summary>UBSan: reference binding to null pointer of type 'struct __forced_unwind' at VariableServerSessionThread_loop.cpp:133</summary>

```
VariableServerSessionThread_loop.cpp:133:34: runtime error: reference binding to null pointer of type 'struct __forced_unwind'
    #0 0x555de58ac1d3 in Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:133
    #1 0x555de5869401 in Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-asan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395
    #2 0x7ff81e45ea41 in asan_thread_start ../../../../src/libsanitizer/asan/asan_interceptors.cpp:234
    #3 0x7ff81cc9cb83 in start_thread nptl/pthread_create.c:447
    #4 0x7ff81cd29ecb in clone3 ../sysdeps/unix/sysv/linux/x86_64/clone3.S:78

[       OK ] VariableServerSessionThread_test.thread_cancelled (3 ms)
[ RUN      ] VariableServerSessionThread_test.turn_session_log_on

GMOCK WARNING:
Uninteresting mock function call - returning default value.
    Function call: publish(1, "Trick VariableServer: Enabling the Variable Server. See Trick documentation for associated security concerns.\n")
          Returns: 0
NOTE: You can safely ignore the above warning unless this call should not happen.  Do not suppress it by blindly adding an EXPECT_CALL() if you don't mean to enforce the call.  See https://github.com/google/googletest/blob/main/docs/gmock_cook_book.md#knowing-when-to-expect-useoncall for details.
```

</details>

<details><summary>UBSan: store to address N with insufficient space for an object of type 'char' at TCPConnection.cpp:88</summary>

```
TCPConnection.cpp:88:26: runtime error: store to address 0x7fc3e147f4e0 with insufficient space for an object of type 'char'
0x7fc3e147f4e0: note: pointer points here
 74 72 69 63  00 f5 47 e1 c3 7f 00 00  33 de 2d ef c3 7f 00 00  80 a8 08 00 70 50 00 00  40 0d 03 00
              ^ 
    #0 0x561322f5fdca in Trick::TCPConnection::read(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >&, int) /home/claude/brendanny/trick-asan/trick_source/trick_utils/connection_handlers/TCPConnection.cpp:88
    #1 0x56132221dbca in Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:159
    #2 0x561322223c33 in Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-asan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101
    #3 0x5613221b4013 in Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-asan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395
    #4 0x7fc3ef25ea41 in asan_thread_start ../../../../src/libsanitizer/asan/asan_interceptors.cpp:234
    #5 0x7fc3eda9cb83 in start_thread nptl/pthread_create.c:447
    #6 0x7fc3edb29ecb in clone3 ../sysdeps/unix/sysv/linux/x86_64/clone3.S:78

|L   2|2026/10/22,16:11:09.257602|vm| |T 0|0.000000| tag=<> Variable Server buffer[8192] too small for symbol conf.vars.big, TRUNCATED IT.
|L   2|2026/10/22,16:11:13.130267|vm| |T 0|0.000000| tag=<> Variable Server buffer[8192] too small for symbol conf.vars.big, TRUNCATED IT.
Process terminated by signal SIGTERM
```

</details>

