## Sanitizer reports

33 distinct signatures, 80 reports, 34 log files.

| Tool and kind | First Trick frame | Function | Reports |
| --- | --- | --- | --- |
| TSan: data race | `trick_source/sim_services/MemoryManager/MemoryManager_ref_attributes.cpp:20` | `Trick::MemoryManager::ref_attributes(char const*)` | 9 |
| TSan: data race | `trick_source/sim_services/Timer/ITimer.cpp:48` | `Trick::ITimer::semaphore_post()` | 6 |
| TSan: data race | `trick_source/sim_services/Message/MessagePublisher.cpp:79` | `Trick::MessagePublisher::publish(int, std::__cxx11::basic_st` | 4 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableReference.cpp:295` | `Trick::VariableReference::stageValue(bool)` | 3 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableServerListenThread.cpp:148` | `Trick::VariableServerListenThread::thread_body()` | 3 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:217` | `Trick::VariableServerSession::var_clear()` | 3 |
| TSan: data race | `trick_source/sim_services/Executive/Executive_freeze.cpp:28` | `Trick::Executive::freeze()` | 2 |
| TSan: data race | `trick_source/sim_services/Executive/Executive_freeze_loop.cpp:76` | `Trick::Executive::freeze_loop()` | 2 |
| TSan: data race | `trick_source/sim_services/Executive/Executive_init_freeze_scheduled.cpp:14` | `Trick::Executive::init_freeze_scheduled()` | 2 |
| TSan: data race | `trick_source/sim_services/Executive/Executive_run.cpp:12` | `Trick::Executive::run()` | 2 |
| TSan: data race | `trick_source/sim_services/Message/MessageTCDevice.cpp:214` | `Trick::MessageTCDevice::update(unsigned int, std::__cxx11::b` | 2 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableReference.cpp:189` | `Trick::VariableReference::~VariableReference()` | 2 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableReference.cpp:362` | `Trick::VariableReference::stageValue(bool)` | 2 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableServerSession.cpp:114` | `Trick::VariableServerSession::get_next_tics() const` | 2 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableServerSession.cpp:197` | `Trick::VariableServerSession::get_cycle_tics() const` | 2 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableServerSession.cpp:84` | `Trick::VariableServerSession::get_pause()` | 2 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:28` | `Trick::VariableServerSession::var_add(std::__cxx11::basic_st` | 2 |
| TSan: data race | `trick_source/sim_services/Executive/Executive_freeze.cpp:62` | `Trick::Executive::async_freeze_to_exec_command()` | 1 |
| TSan: data race | `trick_source/sim_services/Executive/Executive_get_sim_time.cpp:15` | `Trick::Executive::get_sim_time()` | 1 |
| TSan: data race | `trick_source/sim_services/Executive/Executive_init_freeze_scheduled.cpp:7` | `Trick::Executive::init_freeze_scheduled()` | 1 |
| TSan: data race | `trick_source/sim_services/MemoryManager/MemoryManager_clear_memory.cpp:41` | `Trick::MemoryManager::clear_rvalue(void*, ATTRIBUTES_tag*, i` | 1 |
| TSan: data race | `trick_source/sim_services/Message/MessagePublisher.cpp:67` | `Trick::MessagePublisher::publish(int, std::__cxx11::basic_st` | 1 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableReference.cpp:185` | `Trick::VariableReference::~VariableReference()` | 1 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableReference.cpp:190` | `Trick::VariableReference::~VariableReference()` | 1 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableReference.cpp:300` | `Trick::VariableReference::stageValue(bool)` | 1 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableServerListenThread.cpp:104` | `Trick::VariableServerListenThread::set_broadcast(bool)` | 1 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableServerListenThread.cpp:215` | `Trick::VariableServerListenThread::thread_body()` | 1 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableServerSession.cpp:193` | `Trick::VariableServerSession::get_copy_mode() const` | 1 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableServerSession.cpp:213` | `Trick::VariableServerSession::get_freeze_frame_offset() cons` | 1 |
| TSan: data race | `trick_source/sim_services/VariableServer/VariableServer_get_next_sync_call_time.cpp:20` | `Trick::VariableServer::get_next_sync_call_time()` | 1 |
| TSan: heap-use-after-free | `trick_source/sim_services/VariableServer/VariableReference.cpp:719` | `Trick::VariableReference::byteswap_var(char*, char*, Trick::` | 3 |
| TSan: signal handler spoils errno | `trick_source/sim_services/Timer/it_handler.cpp:16` | `it_handler(int)` | 5 |
| TSan: thread leak | `trick_source/sim_services/ThreadBase/ThreadBase.cpp:293` | `Trick::ThreadBase::create_thread()` | 9 |

### First report of each signature

<details><summary>TSan: data race at trick_source/sim_services/Executive/Executive_freeze.cpp:28</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Write of size 1 at 0x562892759fec by thread T9:
    #0 Trick::Executive::freeze() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_freeze.cpp:28 (T_main_Linux_13.3_x86_64_test.exe+0x3c288c) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 exec_freeze /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_c_intf.cpp:787 (T_main_Linux_13.3_x86_64_test.exe+0x3bdd9a) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 _wrap_exec_freeze swig_Linux_13.3_x86_64/sim_services_wrap.cpp:66249 (T_main_Linux_13.3_x86_64_test.exe+0x67ec9c) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 <null> <null> (libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #4 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (T_main_Linux_13.3_x86_64_test.exe+0x5be545) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (T_main_Linux_13.3_x86_64_test.exe+0x4b30f2) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (T_main_Linux_13.3_x86_64_test.exe+0x4b4ef7) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous read of size 1 at 0x562892759fec by main thread:
    #0 Trick::Executive::async_freeze_to_exec_command() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_freeze.cpp:60 (T_main_Linux_13.3_x86_64_test.exe+0x3c28c9) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 SysSimObject::call_function(Trick::JobData*) build/S_source.cpp:55 (T_main_Linux_13.3_x86_64_test.exe+0x1dcfda) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (T_main_Linux_13.3_x86_64_test.exe+0x49a24f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:105 (T_main_Linux_13.3_x86_64_test.exe+0x3c701b) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (T_main_Linux_13.3_x86_64_test.exe+0x3c5e29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8e6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  As if synchronized via sleep:
    #0 usleep ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:390 (libtsan.so.2+0x587d1) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:118 (T_main_Linux_13.3_x86_64_test.exe+0x4b4fa5) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

```

</details>

<details><summary>TSan: data race at trick_source/sim_services/Executive/Executive_freeze.cpp:62</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Write of size 1 at 0x562892759fec by main thread:
    #0 Trick::Executive::async_freeze_to_exec_command() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_freeze.cpp:62 (T_main_Linux_13.3_x86_64_test.exe+0x3c28f0) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 SysSimObject::call_function(Trick::JobData*) build/S_source.cpp:55 (T_main_Linux_13.3_x86_64_test.exe+0x1dcfda) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (T_main_Linux_13.3_x86_64_test.exe+0x49a24f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:105 (T_main_Linux_13.3_x86_64_test.exe+0x3c701b) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (T_main_Linux_13.3_x86_64_test.exe+0x3c5e29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8e6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous write of size 1 at 0x562892759fec by thread T37:
    #0 Trick::Executive::freeze() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_freeze.cpp:28 (T_main_Linux_13.3_x86_64_test.exe+0x3c288c) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 exec_freeze /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_c_intf.cpp:787 (T_main_Linux_13.3_x86_64_test.exe+0x3bdd9a) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 _wrap_exec_freeze swig_Linux_13.3_x86_64/sim_services_wrap.cpp:66249 (T_main_Linux_13.3_x86_64_test.exe+0x67ec9c) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 <null> <null> (libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #4 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (T_main_Linux_13.3_x86_64_test.exe+0x5be545) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (T_main_Linux_13.3_x86_64_test.exe+0x4b30f2) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (T_main_Linux_13.3_x86_64_test.exe+0x4b4ef7) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  As if synchronized via sleep:
    #0 nanosleep ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:397 (libtsan.so.2+0x58cc6) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::Clock::clock_spin(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Clock/Clock.cpp:91 (T_main_Linux_13.3_x86_64_test.exe+0x36e6be) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::RealtimeSync::rt_monitor(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/RealtimeSync/RealtimeSync.cpp:414 (T_main_Linux_13.3_x86_64_test.exe+0x48d67d) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 RTSyncSimObject::call_function(Trick::JobData*) build/S_source.cpp:662 (T_main_Linux_13.3_x86_64_test.exe+0x1d8c7f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/Executive/Executive_freeze_loop.cpp:76</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Write of size 4 at 0x562892759fe8 by main thread:
    #0 Trick::Executive::freeze_loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_freeze_loop.cpp:76 (T_main_Linux_13.3_x86_64_test.exe+0x3c31db) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:42 (T_main_Linux_13.3_x86_64_test.exe+0x3c6bb8) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (T_main_Linux_13.3_x86_64_test.exe+0x3c5e29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8e6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous write of size 4 at 0x562892759fe8 by thread T9:
    #0 Trick::Executive::run() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_run.cpp:12 (T_main_Linux_13.3_x86_64_test.exe+0x3c992a) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 exec_run /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_c_intf.cpp:799 (T_main_Linux_13.3_x86_64_test.exe+0x3bde11) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 _wrap_exec_run swig_Linux_13.3_x86_64/sim_services_wrap.cpp:66271 (T_main_Linux_13.3_x86_64_test.exe+0x67f120) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 <null> <null> (libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #4 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (T_main_Linux_13.3_x86_64_test.exe+0x5be545) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (T_main_Linux_13.3_x86_64_test.exe+0x4b30f2) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (T_main_Linux_13.3_x86_64_test.exe+0x4b4ef7) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  As if synchronized via sleep:
    #0 nanosleep ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:397 (libtsan.so.2+0x58cc6) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::Clock::clock_spin(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Clock/Clock.cpp:91 (T_main_Linux_13.3_x86_64_test.exe+0x36e6be) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::RealtimeSync::freeze_pause(double) /home/claude/brendanny/trick-tsan/trick_source/sim_services/RealtimeSync/RealtimeSync.cpp:483 (T_main_Linux_13.3_x86_64_test.exe+0x48cd43) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 RTSyncSimObject::call_function(Trick::JobData*) build/S_source.cpp:656 (T_main_Linux_13.3_x86_64_test.exe+0x1d8c38) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (T_main_Linux_13.3_x86_64_test.exe+0x49a24f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::Executive::freeze_loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_freeze_loop.cpp:67 (T_main_Linux_13.3_x86_64_test.exe+0x3c310d) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/Executive/Executive_get_sim_time.cpp:15</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Read of size 8 at 0x724c00000078 by thread T3:
    #0 Trick::Executive::get_sim_time() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_get_sim_time.cpp:15 (T_main_Linux_13.3_x86_64_test.exe+0x3c3b08) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 exec_get_sim_time /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_c_intf.cpp:238 (T_main_Linux_13.3_x86_64_test.exe+0x3bd004) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::VariableServerSession::log_received_message(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:136 (T_main_Linux_13.3_x86_64_test.exe+0x4b2cea) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:161 (T_main_Linux_13.3_x86_64_test.exe+0x4b30e1) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (T_main_Linux_13.3_x86_64_test.exe+0x4b4ef7) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous write of size 8 at 0x724c00000078 by main thread:
    #0 Trick::Executive::advance_sim_time() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_advance_sim_time.cpp:71 (T_main_Linux_13.3_x86_64_test.exe+0x3bc9ed) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 SysSimObject::call_function(Trick::JobData*) build/S_source.cpp:61 (T_main_Linux_13.3_x86_64_test.exe+0x1dcffc) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (T_main_Linux_13.3_x86_64_test.exe+0x49a24f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:71 (T_main_Linux_13.3_x86_64_test.exe+0x3c6e06) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (T_main_Linux_13.3_x86_64_test.exe+0x3c5e29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8e6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  As if synchronized via sleep:
    #0 usleep ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:390 (libtsan.so.2+0x587d1) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:118 (T_main_Linux_13.3_x86_64_test.exe+0x4b4fa5) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Location is heap block of size 448 at 0x724c00000000 allocated by main thread:
    #0 operator new(unsigned long) ../../../../src/libsanitizer/tsan/tsan_new_delete.cpp:64 (libtsan.so.2+0xa6fae) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/Executive/Executive_init_freeze_scheduled.cpp:14</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Write of size 8 at 0x724800006a50 by main thread:
    #0 Trick::Executive::init_freeze_scheduled() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_init_freeze_scheduled.cpp:14 (T_main_Linux_13.3_x86_64_test.exe+0x3c42dc) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 SysSimObject::call_function(Trick::JobData*) build/S_source.cpp:58 (T_main_Linux_13.3_x86_64_test.exe+0x1dcfeb) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (T_main_Linux_13.3_x86_64_test.exe+0x49a24f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 Trick::Executive::freeze_loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_freeze_loop.cpp:31 (T_main_Linux_13.3_x86_64_test.exe+0x3c2edb) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:42 (T_main_Linux_13.3_x86_64_test.exe+0x3c6bb8) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (T_main_Linux_13.3_x86_64_test.exe+0x3c5e29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8e6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous write of size 8 at 0x724800006a50 by thread T41:
    #0 Trick::VariableServer::get_next_freeze_call_time() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServer_get_next_freeze_call_time.cpp:20 (T_main_Linux_13.3_x86_64_test.exe+0x4c0944) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 var_set_copy_mode(int) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:211 (T_main_Linux_13.3_x86_64_test.exe+0x4c28df) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 _wrap_var_set_copy_mode swig_Linux_13.3_x86_64/sim_services_wrap.cpp:157101 (T_main_Linux_13.3_x86_64_test.exe+0x8966ef) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 <null> <null> (libpython3.11.so.1.0+0x1d3435) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #4 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (T_main_Linux_13.3_x86_64_test.exe+0x5be545) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (T_main_Linux_13.3_x86_64_test.exe+0x4b30f2) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (T_main_Linux_13.3_x86_64_test.exe+0x4b4ef7) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  As if synchronized via sleep:
    #0 nanosleep ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:397 (libtsan.so.2+0x58cc6) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::Clock::clock_spin(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Clock/Clock.cpp:91 (T_main_Linux_13.3_x86_64_test.exe+0x36e6be) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::RealtimeSync::rt_monitor(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/RealtimeSync/RealtimeSync.cpp:414 (T_main_Linux_13.3_x86_64_test.exe+0x48d67d) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/Executive/Executive_init_freeze_scheduled.cpp:7</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Write of size 8 at 0x562892759f40 by main thread:
    #0 Trick::Executive::init_freeze_scheduled() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_init_freeze_scheduled.cpp:7 (T_main_Linux_13.3_x86_64_test.exe+0x3c4274) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 SysSimObject::call_function(Trick::JobData*) build/S_source.cpp:58 (T_main_Linux_13.3_x86_64_test.exe+0x1dcfeb) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (T_main_Linux_13.3_x86_64_test.exe+0x49a24f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 Trick::Executive::freeze_loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_freeze_loop.cpp:31 (T_main_Linux_13.3_x86_64_test.exe+0x3c2edb) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:42 (T_main_Linux_13.3_x86_64_test.exe+0x3c6bb8) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (T_main_Linux_13.3_x86_64_test.exe+0x3c5e29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8e6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous read of size 8 at 0x562892759f40 by thread T41 (mutexes: write M0):
    #0 memcpy ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors_memintrinsics.inc:115 (libtsan.so.2+0x8bd30) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 memcpy ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors_memintrinsics.inc:107 (libtsan.so.2+0x8bd30)
    #2 memcpy /usr/include/x86_64-linux-gnu/bits/string_fortified.h:29 (T_main_Linux_13.3_x86_64_test.exe+0x4a8161) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 Trick::VariableReference::stageValue(bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:362 (T_main_Linux_13.3_x86_64_test.exe+0x4a8161)
    #4 Trick::VariableServerSession::copy_sim_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:28 (T_main_Linux_13.3_x86_64_test.exe+0x4bb646) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::VariableServerSession::copy_sim_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:13 (T_main_Linux_13.3_x86_64_test.exe+0x4bb538) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::VariableServerSession::copy_and_write_async() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:103 (T_main_Linux_13.3_x86_64_test.exe+0x4bb3d6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:112 (T_main_Linux_13.3_x86_64_test.exe+0x4b4f5b) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #8 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  As if synchronized via sleep:
    #0 nanosleep ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:397 (libtsan.so.2+0x58cc6) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::Clock::clock_spin(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Clock/Clock.cpp:91 (T_main_Linux_13.3_x86_64_test.exe+0x36e6be) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/Executive/Executive_run.cpp:12</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Write of size 4 at 0x562892759fe8 by thread T41:
    #0 Trick::Executive::run() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_run.cpp:12 (T_main_Linux_13.3_x86_64_test.exe+0x3c992a) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 exec_run /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_c_intf.cpp:799 (T_main_Linux_13.3_x86_64_test.exe+0x3bde11) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 _wrap_exec_run swig_Linux_13.3_x86_64/sim_services_wrap.cpp:66271 (T_main_Linux_13.3_x86_64_test.exe+0x67f120) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 <null> <null> (libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #4 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (T_main_Linux_13.3_x86_64_test.exe+0x5be545) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (T_main_Linux_13.3_x86_64_test.exe+0x4b30f2) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (T_main_Linux_13.3_x86_64_test.exe+0x4b4ef7) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous write of size 4 at 0x562892759fe8 by main thread:
    #0 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:41 (T_main_Linux_13.3_x86_64_test.exe+0x3c6b8b) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (T_main_Linux_13.3_x86_64_test.exe+0x3c5e29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8e6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  As if synchronized via sleep:
    #0 usleep ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:390 (libtsan.so.2+0x587d1) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:118 (T_main_Linux_13.3_x86_64_test.exe+0x4b4fa5) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Location is global 'trick_sys' of size 1928 at 0x562892759de0 (T_main_Linux_13.3_x86_64_test.exe+0xdb5fe8)

  Thread T41 'VS_VSTest31' (tid=20535, running) created by thread T5 at:
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/MemoryManager/MemoryManager_clear_memory.cpp:41</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Write of size 4 at 0x562892758bcc by main thread (mutexes: write M0):
    #0 Trick::MemoryManager::clear_rvalue(void*, ATTRIBUTES_tag*, int, int) /home/claude/brendanny/trick-tsan/trick_source/sim_services/MemoryManager/MemoryManager_clear_memory.cpp:41 (T_main_Linux_13.3_x86_64_test.exe+0x9c64b9) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 Trick::MemoryManager::clear_class(char*, ATTRIBUTES_tag*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/MemoryManager/MemoryManager_clear_memory.cpp:189 (T_main_Linux_13.3_x86_64_test.exe+0x9c83be) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::MemoryManager::clear_class(char*, ATTRIBUTES_tag*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/MemoryManager/MemoryManager_clear_memory.cpp:185 (T_main_Linux_13.3_x86_64_test.exe+0x9c8377) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 Trick::MemoryManager::clear_class(char*, ATTRIBUTES_tag*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/MemoryManager/MemoryManager_clear_memory.cpp:185 (T_main_Linux_13.3_x86_64_test.exe+0x9c8377) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 Trick::MemoryManager::clear_var_critical_section(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/MemoryManager/MemoryManager_clear_memory.cpp:236 (T_main_Linux_13.3_x86_64_test.exe+0x9c850b) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::MemoryManager::clear_all_vars() /home/claude/brendanny/trick-tsan/trick_source/sim_services/MemoryManager/MemoryManager_clear_memory.cpp:287 (T_main_Linux_13.3_x86_64_test.exe+0x9c8ec4) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 CCP_parse(ChkPtParseContext*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/CheckPointAgent/input_parser.y:242 (T_main_Linux_13.3_x86_64_test.exe+0x3897f8) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::ClassicCheckPointAgent::restore(std::istream*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/CheckPointAgent/ClassicCheckPointAgent.cpp:339 (T_main_Linux_13.3_x86_64_test.exe+0x3727c8) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #8 Trick::MemoryManager::read_checkpoint(std::istream*, bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/MemoryManager/MemoryManager_restore.cpp:25 (T_main_Linux_13.3_x86_64_test.exe+0x9f49c6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #9 Trick::MemoryManager::read_checkpoint(char const*, bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/MemoryManager/MemoryManager_restore.cpp:72 (T_main_Linux_13.3_x86_64_test.exe+0x9f529d) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #10 Trick::MemoryManager::init_from_checkpoint(char const*, bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/MemoryManager/MemoryManager_restore.cpp:116 (T_main_Linux_13.3_x86_64_test.exe+0x9f6034) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #11 Trick::CheckPointRestart::load_checkpoint_job() /home/claude/brendanny/trick-tsan/trick_source/sim_services/CheckPointRestart/CheckPointRestart.cpp:353 (T_main_Linux_13.3_x86_64_test.exe+0x38cf65) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #12 CheckPointRestartSimObject::call_function(Trick::JobData*) build/S_source.cpp:178 (T_main_Linux_13.3_x86_64_test.exe+0x1d957c) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #13 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (T_main_Linux_13.3_x86_64_test.exe+0x49a24f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #14 Trick::Executive::freeze_loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_freeze_loop.cpp:67 (T_main_Linux_13.3_x86_64_test.exe+0x3c310d) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #15 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:42 (T_main_Linux_13.3_x86_64_test.exe+0x3c6bb8) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #16 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (T_main_Linux_13.3_x86_64_test.exe+0x3c5e29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #17 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8e6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #18 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous read of size 4 at 0x562892758bcc by thread T4:
    #0 Trick::ThreadBase::execute_priority() /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:167 (T_main_Linux_13.3_x86_64_test.exe+0x49fc7b) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:392 (T_main_Linux_13.3_x86_64_test.exe+0x49fe9a) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/MemoryManager/MemoryManager_ref_attributes.cpp:20</summary>

```
WARNING: ThreadSanitizer: data race (pid=20216)
  Write of size 4 at 0x55fe50d4d1e4 by thread T13:
    #0 Trick::MemoryManager::ref_attributes(char const*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/MemoryManager/MemoryManager_ref_attributes.cpp:20 (S_main_Linux_13.3_x86_64.exe+0xa00c3b) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #1 ref_attributes /home/claude/brendanny/trick-tsan/trick_source/sim_services/MemoryManager/MemoryManager_C_Intf.cpp:499 (S_main_Linux_13.3_x86_64.exe+0x9cd053) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 Trick::VariableReference::VariableReference(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:96 (S_main_Linux_13.3_x86_64.exe+0x4b2575) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 Trick::VariableServerSession::var_add(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:25 (S_main_Linux_13.3_x86_64.exe+0x4c21df) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 var_add(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:26 (S_main_Linux_13.3_x86_64.exe+0x4ccca7) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 _wrap_var_add__SWIG_0 swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156379 (S_main_Linux_13.3_x86_64.exe+0x7cdea1) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 _wrap_var_add swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156450 (S_main_Linux_13.3_x86_64.exe+0x7cdea1)
    #7 <null> <null> (libpython3.11.so.1.0+0x1d3125) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #8 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (S_main_Linux_13.3_x86_64.exe+0x5d19c9) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #9 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (S_main_Linux_13.3_x86_64.exe+0x4bb97a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #10 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (S_main_Linux_13.3_x86_64.exe+0x4bd77f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #11 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (S_main_Linux_13.3_x86_64.exe+0x4a8747) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)

  Previous write of size 4 at 0x55fe50d4d1e4 by thread T12 (mutexes: write M0):
    #0 Trick::MemoryManager::ref_attributes(char const*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/MemoryManager/MemoryManager_ref_attributes.cpp:20 (S_main_Linux_13.3_x86_64.exe+0xa00c3b) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #1 ref_attributes /home/claude/brendanny/trick-tsan/trick_source/sim_services/MemoryManager/MemoryManager_C_Intf.cpp:499 (S_main_Linux_13.3_x86_64.exe+0x9cd053) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 Trick::VariableReference::stageValue(bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:301 (S_main_Linux_13.3_x86_64.exe+0x4b0822) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 Trick::VariableServerSession::copy_sim_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:28 (S_main_Linux_13.3_x86_64.exe+0x4c3ece) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 Trick::VariableServerSession::copy_sim_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:13 (S_main_Linux_13.3_x86_64.exe+0x4c3dc0) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 Trick::VariableServerSession::copy_and_write_async() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:103 (S_main_Linux_13.3_x86_64.exe+0x4c3c5e) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:112 (S_main_Linux_13.3_x86_64.exe+0x4bd7e3) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (S_main_Linux_13.3_x86_64.exe+0x4a8747) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)

```

</details>

<details><summary>TSan: data race at trick_source/sim_services/Message/MessagePublisher.cpp:67</summary>

```
WARNING: ThreadSanitizer: data race (pid=20216)
  Write of size 8 at 0x7f90c440b320 by thread T89:
    #0 localtime ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc:1305 (libtsan.so.2+0x6031a) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::MessagePublisher::publish(int, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Message/MessagePublisher.cpp:67 (S_main_Linux_13.3_x86_64.exe+0x426e28) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 message_publish /home/claude/brendanny/trick-tsan/trick_source/sim_services/Message/Message_c_intf.cpp:86 (S_main_Linux_13.3_x86_64.exe+0x42a256) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 Trick::VariableServerSession::write_ascii_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> > const&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:150 (S_main_Linux_13.3_x86_64.exe+0x4c4eef) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 Trick::VariableServerSession::write_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:233 (S_main_Linux_13.3_x86_64.exe+0x4c4145) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 Trick::VariableServerSession::write_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:201 (S_main_Linux_13.3_x86_64.exe+0x4c3fb0) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::VariableServerSession::copy_and_write_async() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:112 (S_main_Linux_13.3_x86_64.exe+0x4c3d33) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:112 (S_main_Linux_13.3_x86_64.exe+0x4bd7e3) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (S_main_Linux_13.3_x86_64.exe+0x4a8747) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)

  Previous write of size 8 at 0x7f90c440b320 by thread T91:
    #0 localtime ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc:1305 (libtsan.so.2+0x6031a) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::MessagePublisher::publish(int, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Message/MessagePublisher.cpp:67 (S_main_Linux_13.3_x86_64.exe+0x426e28) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 message_publish /home/claude/brendanny/trick-tsan/trick_source/sim_services/Message/Message_c_intf.cpp:86 (S_main_Linux_13.3_x86_64.exe+0x42a256) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 Trick::VariableServerSession::write_ascii_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> > const&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:150 (S_main_Linux_13.3_x86_64.exe+0x4c4eef) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 Trick::VariableServerSession::write_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:233 (S_main_Linux_13.3_x86_64.exe+0x4c4145) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 Trick::VariableServerSession::write_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:201 (S_main_Linux_13.3_x86_64.exe+0x4c3fb0) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::VariableServerSession::copy_and_write_async() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:112 (S_main_Linux_13.3_x86_64.exe+0x4c3d33) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:112 (S_main_Linux_13.3_x86_64.exe+0x4bd7e3) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (S_main_Linux_13.3_x86_64.exe+0x4a8747) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)

  Location is global '_tmbuf' of size 56 at 0x7f90c440b320 (libc.so.6+0x20b320)

```

</details>

<details><summary>TSan: data race at trick_source/sim_services/Message/MessagePublisher.cpp:79</summary>

```
WARNING: ThreadSanitizer: data race (pid=20216)
  Write of size 8 at 0x72900000a000 by thread T89:
    #0 memcpy ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors_memintrinsics.inc:115 (libtsan.so.2+0x8bd30) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 memcpy ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors_memintrinsics.inc:107 (libtsan.so.2+0x8bd30)
    #2 std::basic_streambuf<char, std::char_traits<char> >::xsputn(char const*, long) <null> (libstdc++.so.6+0x166e5f) (BuildId: 753c6c8608b61d4e67be8f0c890e03e0aa046b8b)
    #3 Trick::MessagePublisher::publish(int, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Message/MessagePublisher.cpp:79 (S_main_Linux_13.3_x86_64.exe+0x427012) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 message_publish /home/claude/brendanny/trick-tsan/trick_source/sim_services/Message/Message_c_intf.cpp:86 (S_main_Linux_13.3_x86_64.exe+0x42a256) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 Trick::VariableServerSession::write_ascii_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> > const&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:150 (S_main_Linux_13.3_x86_64.exe+0x4c4eef) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::VariableServerSession::write_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:233 (S_main_Linux_13.3_x86_64.exe+0x4c4145) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::VariableServerSession::write_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:201 (S_main_Linux_13.3_x86_64.exe+0x4c3fb0) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::VariableServerSession::copy_and_write_async() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:112 (S_main_Linux_13.3_x86_64.exe+0x4c3d33) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #9 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:112 (S_main_Linux_13.3_x86_64.exe+0x4bd7e3) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #10 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (S_main_Linux_13.3_x86_64.exe+0x4a8747) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)

  Previous read of size 8 at 0x72900000a000 by thread T91:
    #0 write ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc:1091 (libtsan.so.2+0x5f3f9) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 std::__basic_file<char>::xsputn(char const*, long) <null> (libstdc++.so.6+0xf91ad) (BuildId: 753c6c8608b61d4e67be8f0c890e03e0aa046b8b)
    #2 Trick::MessagePublisher::publish(int, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Message/MessagePublisher.cpp:79 (S_main_Linux_13.3_x86_64.exe+0x427012) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 message_publish /home/claude/brendanny/trick-tsan/trick_source/sim_services/Message/Message_c_intf.cpp:86 (S_main_Linux_13.3_x86_64.exe+0x42a256) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 Trick::VariableServerSession::write_ascii_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> > const&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:150 (S_main_Linux_13.3_x86_64.exe+0x4c4eef) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 Trick::VariableServerSession::write_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:233 (S_main_Linux_13.3_x86_64.exe+0x4c4145) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::VariableServerSession::write_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:201 (S_main_Linux_13.3_x86_64.exe+0x4c3fb0) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::VariableServerSession::copy_and_write_async() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:112 (S_main_Linux_13.3_x86_64.exe+0x4c3d33) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:112 (S_main_Linux_13.3_x86_64.exe+0x4bd7e3) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #9 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (S_main_Linux_13.3_x86_64.exe+0x4a8747) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/Message/MessageTCDevice.cpp:214</summary>

```
WARNING: ThreadSanitizer: data race (pid=20216)
  Write of size 8 at 0x72a400000000 by thread T89:
    #0 vsnprintf ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc:1652 (libtsan.so.2+0x62971) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 __snprintf_chk ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc:1728 (libtsan.so.2+0x63fa5) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #2 snprintf /usr/include/x86_64-linux-gnu/bits/stdio2.h:54 (S_main_Linux_13.3_x86_64.exe+0x427ee6) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 Trick::MessageTCDevice::update(unsigned int, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Message/MessageTCDevice.cpp:214 (S_main_Linux_13.3_x86_64.exe+0x427ee6)
    #4 Trick::MessagePublisher::publish(int, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Message/MessagePublisher.cpp:79 (S_main_Linux_13.3_x86_64.exe+0x427012) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 message_publish /home/claude/brendanny/trick-tsan/trick_source/sim_services/Message/Message_c_intf.cpp:86 (S_main_Linux_13.3_x86_64.exe+0x42a256) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::VariableServerSession::write_ascii_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> > const&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:150 (S_main_Linux_13.3_x86_64.exe+0x4c4eef) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::VariableServerSession::write_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:233 (S_main_Linux_13.3_x86_64.exe+0x4c4145) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::VariableServerSession::write_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:201 (S_main_Linux_13.3_x86_64.exe+0x4c3fb0) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #9 Trick::VariableServerSession::copy_and_write_async() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:112 (S_main_Linux_13.3_x86_64.exe+0x4c3d33) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #10 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:112 (S_main_Linux_13.3_x86_64.exe+0x4bd7e3) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #11 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (S_main_Linux_13.3_x86_64.exe+0x4a8747) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)

  Previous write of size 8 at 0x72a400000000 by thread T91:
    #0 vsnprintf ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc:1652 (libtsan.so.2+0x62971) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 __snprintf_chk ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc:1728 (libtsan.so.2+0x63fa5) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #2 snprintf /usr/include/x86_64-linux-gnu/bits/stdio2.h:54 (S_main_Linux_13.3_x86_64.exe+0x427ee6) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 Trick::MessageTCDevice::update(unsigned int, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Message/MessageTCDevice.cpp:214 (S_main_Linux_13.3_x86_64.exe+0x427ee6)
    #4 Trick::MessagePublisher::publish(int, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Message/MessagePublisher.cpp:79 (S_main_Linux_13.3_x86_64.exe+0x427012) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 message_publish /home/claude/brendanny/trick-tsan/trick_source/sim_services/Message/Message_c_intf.cpp:86 (S_main_Linux_13.3_x86_64.exe+0x42a256) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::VariableServerSession::write_ascii_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> > const&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:150 (S_main_Linux_13.3_x86_64.exe+0x4c4eef) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::VariableServerSession::write_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:233 (S_main_Linux_13.3_x86_64.exe+0x4c4145) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::VariableServerSession::write_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:201 (S_main_Linux_13.3_x86_64.exe+0x4c3fb0) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/Timer/ITimer.cpp:48</summary>

```
WARNING: ThreadSanitizer: data race (pid=20324)
  Read of size 8 at 0x55a41b460d48 by thread T1:
    #0 Trick::ITimer::semaphore_post() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Timer/ITimer.cpp:48 (S_main_Linux_13.3_x86_64.exe+0x4a9211) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #1 it_handler(int) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Timer/it_handler.cpp:18 (S_main_Linux_13.3_x86_64.exe+0x4aa040) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 CallUserSignalHandler ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:2096 (libtsan.so.2+0x517d5) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #3 <null> <null> (libpython3.11.so.1.0+0x272a50) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)

  Previous write of size 8 at 0x55a41b460d48 by main thread:
    #0 Trick::ITimer::init() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Timer/ITimer.cpp:72 (S_main_Linux_13.3_x86_64.exe+0x4a9a74) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #1 Trick::RealtimeSync::start_sleep_timer() /home/claude/brendanny/trick-tsan/trick_source/sim_services/RealtimeSync/RealtimeSync.cpp:179 (S_main_Linux_13.3_x86_64.exe+0x49505b) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 Trick::RealtimeSync::start_realtime(double, long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/RealtimeSync/RealtimeSync.cpp:235 (S_main_Linux_13.3_x86_64.exe+0x49525b) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 RTSyncSimObject::call_function(Trick::JobData*) build/S_source.cpp:644 (S_main_Linux_13.3_x86_64.exe+0x1d2b82) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (S_main_Linux_13.3_x86_64.exe+0x4a2ad7) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 Trick::Executive::call_initialization() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_call_initialization.cpp:26 (S_main_Linux_13.3_x86_64.exe+0x3c7f80) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::Executive::init() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_init.cpp:45 (S_main_Linux_13.3_x86_64.exe+0x3cb43e) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:42 (S_main_Linux_13.3_x86_64.exe+0x5c1d43) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 main build/S_source.cpp:1350 (S_main_Linux_13.3_x86_64.exe+0x1d3666) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)

  Location is global 'trick_real_time' of size 528 at 0x55a41b460c20 (S_main_Linux_13.3_x86_64.exe+0xdc8d48)

  Thread T1 (tid=20326, running) created by main thread at:
    #0 pthread_create ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:1022 (libtsan.so.2+0x5ac1a) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 PyThread_start_new_thread <null> (libpython3.11.so.1.0+0x2db267) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #2 InputProcessorSimObject::call_function(Trick::JobData*) build/S_source.cpp:381 (S_main_Linux_13.3_x86_64.exe+0x1d2735) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (S_main_Linux_13.3_x86_64.exe+0x4a2ad7) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableReference.cpp:185</summary>

```
WARNING: ThreadSanitizer: data race (pid=20387)
  Write of size 8 at 0x721800003138 by thread T6:
    #0 free ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:724 (libtsan.so.2+0x57c71) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::VariableReference::~VariableReference() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:185 (S_main_Linux_13.3_x86_64.exe+0x4ad2bd) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 Trick::VariableServerSession::var_clear() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:217 (S_main_Linux_13.3_x86_64.exe+0x4bde7d) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 var_clear() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:109 (S_main_Linux_13.3_x86_64.exe+0x4cac70) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 _wrap_var_clear swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156761 (S_main_Linux_13.3_x86_64.exe+0x694e3f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 <null> <null> (libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #6 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (S_main_Linux_13.3_x86_64.exe+0x5d19c9) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (S_main_Linux_13.3_x86_64.exe+0x4bb97a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (S_main_Linux_13.3_x86_64.exe+0x4bd77f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #9 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (S_main_Linux_13.3_x86_64.exe+0x4a8747) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)

  Previous read of size 4 at 0x72180000313c by main thread (mutexes: write M0, write M1):
    #0 Trick::VariableReference::stageValue(bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:314 (S_main_Linux_13.3_x86_64.exe+0x4b0758) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #1 Trick::VariableServerSession::copy_sim_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:28 (S_main_Linux_13.3_x86_64.exe+0x4c3ece) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 Trick::VariableServerSession::copy_sim_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:13 (S_main_Linux_13.3_x86_64.exe+0x4c3dc0) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 Trick::VariableServerSession::copy_and_write_freeze_scheduled(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:41 (S_main_Linux_13.3_x86_64.exe+0x4c371a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 Trick::VariableServer::copy_and_write_freeze_scheduled() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServer_copy_and_write_freeze_scheduled.cpp:15 (S_main_Linux_13.3_x86_64.exe+0x4c8c5f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 VariableServerSimObject::call_function(Trick::JobData*) build/S_source.cpp:549 (S_main_Linux_13.3_x86_64.exe+0x1d2a06) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (S_main_Linux_13.3_x86_64.exe+0x4a2ad7) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::Executive::freeze_loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_freeze_loop.cpp:43 (S_main_Linux_13.3_x86_64.exe+0x3ca4d5) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:42 (S_main_Linux_13.3_x86_64.exe+0x3ce0ca) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #9 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (S_main_Linux_13.3_x86_64.exe+0x3cd33b) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #10 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (S_main_Linux_13.3_x86_64.exe+0x5c1d6a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableReference.cpp:189</summary>

```
WARNING: ThreadSanitizer: data race (pid=20387)
  Write of size 8 at 0x720800033300 by thread T6:
    #0 free ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:724 (libtsan.so.2+0x57c71) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::VariableReference::~VariableReference() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:189 (S_main_Linux_13.3_x86_64.exe+0x4ad2e6) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 Trick::VariableServerSession::var_clear() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:217 (S_main_Linux_13.3_x86_64.exe+0x4bde7d) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 var_clear() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:109 (S_main_Linux_13.3_x86_64.exe+0x4cac70) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 _wrap_var_clear swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156761 (S_main_Linux_13.3_x86_64.exe+0x694e3f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 <null> <null> (libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #6 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (S_main_Linux_13.3_x86_64.exe+0x5d19c9) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (S_main_Linux_13.3_x86_64.exe+0x4bb97a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (S_main_Linux_13.3_x86_64.exe+0x4bd77f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #9 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (S_main_Linux_13.3_x86_64.exe+0x4a8747) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)

  Previous write of size 8 at 0x720800033300 by main thread (mutexes: write M0, write M1):
    #0 memcpy ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors_memintrinsics.inc:115 (libtsan.so.2+0x8bd30) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 memcpy ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors_memintrinsics.inc:107 (libtsan.so.2+0x8bd30)
    #2 memcpy /usr/include/x86_64-linux-gnu/bits/string_fortified.h:29 (S_main_Linux_13.3_x86_64.exe+0x4b09e9) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 Trick::VariableReference::stageValue(bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:362 (S_main_Linux_13.3_x86_64.exe+0x4b09e9)
    #4 Trick::VariableServerSession::copy_sim_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:28 (S_main_Linux_13.3_x86_64.exe+0x4c3ece) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 Trick::VariableServerSession::copy_sim_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:13 (S_main_Linux_13.3_x86_64.exe+0x4c3dc0) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::VariableServerSession::copy_and_write_freeze_scheduled(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:41 (S_main_Linux_13.3_x86_64.exe+0x4c371a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::VariableServer::copy_and_write_freeze_scheduled() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServer_copy_and_write_freeze_scheduled.cpp:15 (S_main_Linux_13.3_x86_64.exe+0x4c8c5f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 VariableServerSimObject::call_function(Trick::JobData*) build/S_source.cpp:549 (S_main_Linux_13.3_x86_64.exe+0x1d2a06) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #9 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (S_main_Linux_13.3_x86_64.exe+0x4a2ad7) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #10 Trick::Executive::freeze_loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_freeze_loop.cpp:43 (S_main_Linux_13.3_x86_64.exe+0x3ca4d5) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableReference.cpp:190</summary>

```
WARNING: ThreadSanitizer: data race (pid=20387)
  Write of size 8 at 0x7228000201e8 by thread T6:
    #0 Trick::VariableReference::~VariableReference() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:190 (S_main_Linux_13.3_x86_64.exe+0x4ad2ee) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #1 Trick::VariableServerSession::var_clear() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:217 (S_main_Linux_13.3_x86_64.exe+0x4bde7d) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 var_clear() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:109 (S_main_Linux_13.3_x86_64.exe+0x4cac70) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 _wrap_var_clear swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156761 (S_main_Linux_13.3_x86_64.exe+0x694e3f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 <null> <null> (libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #5 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (S_main_Linux_13.3_x86_64.exe+0x5d19c9) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (S_main_Linux_13.3_x86_64.exe+0x4bb97a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (S_main_Linux_13.3_x86_64.exe+0x4bd77f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (S_main_Linux_13.3_x86_64.exe+0x4a8747) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)

  Previous read of size 8 at 0x7228000201e8 by main thread (mutexes: write M0, write M1):
    #0 Trick::VariableReference::stageValue(bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:362 (S_main_Linux_13.3_x86_64.exe+0x4b09da) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #1 Trick::VariableServerSession::copy_sim_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:28 (S_main_Linux_13.3_x86_64.exe+0x4c3ece) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 Trick::VariableServerSession::copy_sim_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:13 (S_main_Linux_13.3_x86_64.exe+0x4c3dc0) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 Trick::VariableServerSession::copy_and_write_freeze_scheduled(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:41 (S_main_Linux_13.3_x86_64.exe+0x4c371a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 Trick::VariableServer::copy_and_write_freeze_scheduled() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServer_copy_and_write_freeze_scheduled.cpp:15 (S_main_Linux_13.3_x86_64.exe+0x4c8c5f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 VariableServerSimObject::call_function(Trick::JobData*) build/S_source.cpp:549 (S_main_Linux_13.3_x86_64.exe+0x1d2a06) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (S_main_Linux_13.3_x86_64.exe+0x4a2ad7) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::Executive::freeze_loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_freeze_loop.cpp:43 (S_main_Linux_13.3_x86_64.exe+0x3ca4d5) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:42 (S_main_Linux_13.3_x86_64.exe+0x3ce0ca) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #9 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (S_main_Linux_13.3_x86_64.exe+0x3cd33b) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #10 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (S_main_Linux_13.3_x86_64.exe+0x5c1d6a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #11 main build/S_source.cpp:1350 (S_main_Linux_13.3_x86_64.exe+0x1d3666) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableReference.cpp:295</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Write of size 1 at 0x72280002ffa6 by main thread (mutexes: write M0, write M1):
    #0 Trick::VariableReference::stageValue(bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:295 (T_main_Linux_13.3_x86_64_test.exe+0x4a7e90) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 Trick::VariableServerSession::copy_sim_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:28 (T_main_Linux_13.3_x86_64_test.exe+0x4bb646) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::VariableServerSession::copy_sim_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:13 (T_main_Linux_13.3_x86_64_test.exe+0x4bb538) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 Trick::VariableServerSession::copy_and_write_scheduled(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:62 (T_main_Linux_13.3_x86_64_test.exe+0x4bb06a) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 Trick::VariableServer::copy_and_write_scheduled() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServer_copy_and_write_scheduled.cpp:15 (T_main_Linux_13.3_x86_64_test.exe+0x4c0555) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 VariableServerSimObject::call_function(Trick::JobData*) build/S_source.cpp:543 (T_main_Linux_13.3_x86_64_test.exe+0x1d8a3b) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (T_main_Linux_13.3_x86_64_test.exe+0x49a24f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:71 (T_main_Linux_13.3_x86_64_test.exe+0x3c6e06) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #8 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (T_main_Linux_13.3_x86_64_test.exe+0x3c5e29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #9 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8e6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #10 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous read of size 1 at 0x72280002ffa6 by thread T42:
    #0 Trick::VariableReference::isWriteReady() const /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:630 (T_main_Linux_13.3_x86_64_test.exe+0x4a4ccf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 Trick::VariableReference::writeValueAscii(std::ostream&) const /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:425 (T_main_Linux_13.3_x86_64_test.exe+0x4a4d1d) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::VariableServerSession::write_ascii_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> > const&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:142 (T_main_Linux_13.3_x86_64_test.exe+0x4bc3f2) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 Trick::VariableServerSession::write_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:233 (T_main_Linux_13.3_x86_64_test.exe+0x4bb8bd) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 Trick::VariableServerSession::write_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:201 (T_main_Linux_13.3_x86_64_test.exe+0x4bb728) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::VariableServerSession::copy_and_write_async() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:112 (T_main_Linux_13.3_x86_64_test.exe+0x4bb4ab) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:112 (T_main_Linux_13.3_x86_64_test.exe+0x4b4f5b) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  As if synchronized via sleep:
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableReference.cpp:300</summary>

```
WARNING: ThreadSanitizer: data race (pid=20387)
  Read of size 8 at 0x722800020260 by main thread (mutexes: write M0, write M1):
    #0 Trick::VariableReference::stageValue(bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:300 (S_main_Linux_13.3_x86_64.exe+0x4b0724) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #1 Trick::VariableServerSession::copy_sim_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:28 (S_main_Linux_13.3_x86_64.exe+0x4c3ece) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 Trick::VariableServerSession::copy_sim_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:13 (S_main_Linux_13.3_x86_64.exe+0x4c3dc0) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 Trick::VariableServerSession::copy_and_write_freeze_scheduled(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:41 (S_main_Linux_13.3_x86_64.exe+0x4c371a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 Trick::VariableServer::copy_and_write_freeze_scheduled() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServer_copy_and_write_freeze_scheduled.cpp:15 (S_main_Linux_13.3_x86_64.exe+0x4c8c5f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 VariableServerSimObject::call_function(Trick::JobData*) build/S_source.cpp:549 (S_main_Linux_13.3_x86_64.exe+0x1d2a06) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (S_main_Linux_13.3_x86_64.exe+0x4a2ad7) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::Executive::freeze_loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_freeze_loop.cpp:43 (S_main_Linux_13.3_x86_64.exe+0x3ca4d5) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:42 (S_main_Linux_13.3_x86_64.exe+0x3ce0ca) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #9 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (S_main_Linux_13.3_x86_64.exe+0x3cd33b) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #10 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (S_main_Linux_13.3_x86_64.exe+0x5c1d6a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #11 main build/S_source.cpp:1350 (S_main_Linux_13.3_x86_64.exe+0x1d3666) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)

  Previous write of size 8 at 0x722800020260 by thread T6:
    #0 Trick::VariableReference::~VariableReference() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:186 (S_main_Linux_13.3_x86_64.exe+0x4ad2c5) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #1 Trick::VariableServerSession::var_clear() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:217 (S_main_Linux_13.3_x86_64.exe+0x4bde7d) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 var_clear() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:109 (S_main_Linux_13.3_x86_64.exe+0x4cac70) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 _wrap_var_clear swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156761 (S_main_Linux_13.3_x86_64.exe+0x694e3f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 <null> <null> (libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #5 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (S_main_Linux_13.3_x86_64.exe+0x5d19c9) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (S_main_Linux_13.3_x86_64.exe+0x4bb97a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (S_main_Linux_13.3_x86_64.exe+0x4bd77f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (S_main_Linux_13.3_x86_64.exe+0x4a8747) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableReference.cpp:362</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Read of size 8 at 0x562892759f38 by thread T41 (mutexes: write M0):
    #0 memcpy ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors_memintrinsics.inc:115 (libtsan.so.2+0x8bd30) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 memcpy ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors_memintrinsics.inc:107 (libtsan.so.2+0x8bd30)
    #2 memcpy /usr/include/x86_64-linux-gnu/bits/string_fortified.h:29 (T_main_Linux_13.3_x86_64_test.exe+0x4a8161) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 Trick::VariableReference::stageValue(bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:362 (T_main_Linux_13.3_x86_64_test.exe+0x4a8161)
    #4 Trick::VariableServerSession::copy_sim_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:28 (T_main_Linux_13.3_x86_64_test.exe+0x4bb646) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::VariableServerSession::copy_sim_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:13 (T_main_Linux_13.3_x86_64_test.exe+0x4bb538) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::VariableServerSession::copy_and_write_async() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:103 (T_main_Linux_13.3_x86_64_test.exe+0x4bb3d6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:112 (T_main_Linux_13.3_x86_64_test.exe+0x4b4f5b) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #8 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous write of size 8 at 0x562892759f38 by main thread:
    #0 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:54 (T_main_Linux_13.3_x86_64_test.exe+0x3c6c75) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (T_main_Linux_13.3_x86_64_test.exe+0x3c5e29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8e6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Location is global 'trick_sys' of size 1928 at 0x562892759de0 (T_main_Linux_13.3_x86_64_test.exe+0xdb5f38)

  Mutex M0 (0x722c00016b08) created at:
    #0 pthread_mutex_init ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:1315 (libtsan.so.2+0x594cd) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::VariableServerSession::VariableServerSession() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:46 (T_main_Linux_13.3_x86_64_test.exe+0x4b18c3) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::VariableServerSessionThread::VariableServerSessionThread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread.cpp:17 (T_main_Linux_13.3_x86_64_test.exe+0x4b3cfb) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 Trick::VariableServerListenThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerListenThread.cpp:179 (T_main_Linux_13.3_x86_64_test.exe+0x4af631) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableServerListenThread.cpp:104</summary>

```
WARNING: ThreadSanitizer: data race (pid=20099)
  Write of size 1 at 0x7ffeb8d3eb90 by main thread:
    #0 Trick::VariableServerListenThread::set_broadcast(bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerListenThread.cpp:104 (VariableServerListenThread_test+0xfd03f) (BuildId: 3d20c188cf88cead11ed6ed6e7b25ce6284f2da4)
    #1 VariableServerListenThread_test_run_thread_turn_on_broadcast_Test::TestBody() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/test/VariableServerListenThread_test.cc:278 (VariableServerListenThread_test+0x8aba0) (BuildId: 3d20c188cf88cead11ed6ed6e7b25ce6284f2da4)
    #2 void testing::internal::HandleExceptionsInMethodIfSupported<testing::Test, void>(testing::Test*, void (testing::Test::*)(), char const*) <null> (VariableServerListenThread_test+0x1f15ae) (BuildId: 3d20c188cf88cead11ed6ed6e7b25ce6284f2da4)

  Previous read of size 1 at 0x7ffeb8d3eb90 by thread T3:
    #0 Trick::VariableServerListenThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerListenThread.cpp:212 (VariableServerListenThread_test+0xfe4b7) (BuildId: 3d20c188cf88cead11ed6ed6e7b25ce6284f2da4)
    #1 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (VariableServerListenThread_test+0xf8ca3) (BuildId: 3d20c188cf88cead11ed6ed6e7b25ce6284f2da4)

  As if synchronized via sleep:
    #0 sleep ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:383 (libtsan.so.2+0x58691) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 VariableServerListenThread_test_run_thread_turn_on_broadcast_Test::TestBody() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/test/VariableServerListenThread_test.cc:277 (VariableServerListenThread_test+0x8ab8f) (BuildId: 3d20c188cf88cead11ed6ed6e7b25ce6284f2da4)
    #2 void testing::internal::HandleExceptionsInMethodIfSupported<testing::Test, void>(testing::Test*, void (testing::Test::*)(), char const*) <null> (VariableServerListenThread_test+0x1f15ae) (BuildId: 3d20c188cf88cead11ed6ed6e7b25ce6284f2da4)

  Location is stack of main thread.

  Location is global '<null>' at 0x000000000000 ([stack]+0x1eb90)

  Thread T3 'VarServListen' (tid=20103, running) created by main thread at:
    #0 pthread_create ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:1022 (libtsan.so.2+0x5ac1a) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::ThreadBase::create_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:293 (VariableServerListenThread_test+0xf831f) (BuildId: 3d20c188cf88cead11ed6ed6e7b25ce6284f2da4)
    #2 VariableServerListenThread_test_run_thread_turn_on_broadcast_Test::TestBody() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/test/VariableServerListenThread_test.cc:273 (VariableServerListenThread_test+0x8aa9a) (BuildId: 3d20c188cf88cead11ed6ed6e7b25ce6284f2da4)
    #3 void testing::internal::HandleExceptionsInMethodIfSupported<testing::Test, void>(testing::Test*, void (testing::Test::*)(), char const*) <null> (VariableServerListenThread_test+0x1f15ae) (BuildId: 3d20c188cf88cead11ed6ed6e7b25ce6284f2da4)

```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableServerListenThread.cpp:148</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Write of size 8 at 0x7fa53ce12380 by thread T5:
    #0 getpwuid ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc:1913 (libtsan.so.2+0x64cf6) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::VariableServerListenThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerListenThread.cpp:148 (T_main_Linux_13.3_x86_64_test.exe+0x4af380) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous write of size 8 at 0x7fa53ce12380 by thread T1:
    #0 getpwuid ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc:1913 (libtsan.so.2+0x64cf6) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::VariableServerListenThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerListenThread.cpp:148 (T_main_Linux_13.3_x86_64_test.exe+0x4af380) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Location is global 'resbuf.1' of size 48 at 0x7fa53ce12380 (libc.so.6+0x212380)

  Thread T5 'VarServListen' (tid=20488, running) created by main thread at:
    #0 pthread_create ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:1022 (libtsan.so.2+0x5ac1a) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::ThreadBase::create_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:293 (T_main_Linux_13.3_x86_64_test.exe+0x49f53b) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::VariableServer::init() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServer_init.cpp:18 (T_main_Linux_13.3_x86_64_test.exe+0x4c0b1e) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 VariableServerSimObject::call_function(Trick::JobData*) build/S_source.cpp:519 (T_main_Linux_13.3_x86_64_test.exe+0x1d89a5) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (T_main_Linux_13.3_x86_64_test.exe+0x49a24f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::Executive::call_initialization() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_call_initialization.cpp:26 (T_main_Linux_13.3_x86_64_test.exe+0x3c0a6e) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::Executive::init() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_init.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x3c3f2c) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:42 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8bf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #8 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Thread T1 'VarServListen' (tid=20482, running) created by main thread at:
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableServerListenThread.cpp:215</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Read of size 8 at 0x562892757510 by thread T5:
    #0 vsnprintf ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc:1652 (libtsan.so.2+0x62971) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 __snprintf_chk ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc:1728 (libtsan.so.2+0x63fa5) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #2 snprintf /usr/include/x86_64-linux-gnu/bits/stdio2.h:54 (T_main_Linux_13.3_x86_64_test.exe+0x4af95d) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 Trick::VariableServerListenThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerListenThread.cpp:215 (T_main_Linux_13.3_x86_64_test.exe+0x4af95d)
    #4 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous write of size 8 at 0x562892757510 by thread T40:
    #0 memcpy ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors_memintrinsics.inc:115 (libtsan.so.2+0x8bd30) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 memcpy ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors_memintrinsics.inc:107 (libtsan.so.2+0x8bd30)
    #2 std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >::_M_assign(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&) <null> (libstdc++.so.6+0x16866f) (BuildId: 753c6c8608b61d4e67be8f0c890e03e0aa046b8b)
    #3 var_server_set_user_tag /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:460 (T_main_Linux_13.3_x86_64_test.exe+0x4c3bac) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 _wrap_var_server_set_user_tag swig_Linux_13.3_x86_64/sim_services_wrap.cpp:158440 (T_main_Linux_13.3_x86_64_test.exe+0x63315f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 <null> <null> (libpython3.11.so.1.0+0x1d3435) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #6 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (T_main_Linux_13.3_x86_64_test.exe+0x5be545) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (T_main_Linux_13.3_x86_64_test.exe+0x4b30f2) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #8 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (T_main_Linux_13.3_x86_64_test.exe+0x4b4ef7) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #9 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Location is global 'trick_vs' of size 3744 at 0x562892757320 (T_main_Linux_13.3_x86_64_test.exe+0xdb3510)

  Thread T5 'VarServListen' (tid=20488, running) created by main thread at:
    #0 pthread_create ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:1022 (libtsan.so.2+0x5ac1a) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::ThreadBase::create_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:293 (T_main_Linux_13.3_x86_64_test.exe+0x49f53b) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableServerSession.cpp:114</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Read of size 8 at 0x722c00016b60 by main thread (mutexes: write M0):
    #0 Trick::VariableServerSession::get_next_tics() const /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:114 (T_main_Linux_13.3_x86_64_test.exe+0x4b1014) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 Trick::VariableServer::copy_and_write_scheduled() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServer_copy_and_write_scheduled.cpp:16 (T_main_Linux_13.3_x86_64_test.exe+0x4c04e5) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 VariableServerSimObject::call_function(Trick::JobData*) build/S_source.cpp:543 (T_main_Linux_13.3_x86_64_test.exe+0x1d8a3b) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (T_main_Linux_13.3_x86_64_test.exe+0x49a24f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:71 (T_main_Linux_13.3_x86_64_test.exe+0x3c6e06) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (T_main_Linux_13.3_x86_64_test.exe+0x3c5e29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8e6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous write of size 8 at 0x722c00016b60 by thread T41:
    #0 Trick::VariableServerSession::var_set_copy_mode(int) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:283 (T_main_Linux_13.3_x86_64_test.exe+0x4b58d9) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 var_set_copy_mode(int) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:208 (T_main_Linux_13.3_x86_64_test.exe+0x4c2896) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 _wrap_var_set_copy_mode swig_Linux_13.3_x86_64/sim_services_wrap.cpp:157101 (T_main_Linux_13.3_x86_64_test.exe+0x8966ef) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 <null> <null> (libpython3.11.so.1.0+0x1d3435) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #4 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (T_main_Linux_13.3_x86_64_test.exe+0x5be545) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (T_main_Linux_13.3_x86_64_test.exe+0x4b30f2) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (T_main_Linux_13.3_x86_64_test.exe+0x4b4ef7) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  As if synchronized via sleep:
    #0 nanosleep ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:397 (libtsan.so.2+0x58cc6) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::Clock::clock_spin(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Clock/Clock.cpp:91 (T_main_Linux_13.3_x86_64_test.exe+0x36e6be) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::RealtimeSync::rt_monitor(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/RealtimeSync/RealtimeSync.cpp:414 (T_main_Linux_13.3_x86_64_test.exe+0x48d67d) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableServerSession.cpp:193</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Read of size 4 at 0x722c00016b78 by main thread (mutexes: write M0):
    #0 Trick::VariableServerSession::get_copy_mode() const /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:193 (T_main_Linux_13.3_x86_64_test.exe+0x4b113b) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 Trick::VariableServerSession::copy_and_write_top(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:81 (T_main_Linux_13.3_x86_64_test.exe+0x4bb1dd) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::VariableServer::copy_and_write_top() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServer_copy_and_write_top.cpp:8 (T_main_Linux_13.3_x86_64_test.exe+0x4c0647) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 VariableServerSimObject::call_function(Trick::JobData*) build/S_source.cpp:540 (T_main_Linux_13.3_x86_64_test.exe+0x1d8a29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (T_main_Linux_13.3_x86_64_test.exe+0x49a24f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:49 (T_main_Linux_13.3_x86_64_test.exe+0x3c6c51) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (T_main_Linux_13.3_x86_64_test.exe+0x3c5e29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8e6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #8 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous write of size 4 at 0x722c00016b78 by thread T41:
    #0 Trick::VariableServerSession::var_set_copy_mode(int) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:269 (T_main_Linux_13.3_x86_64_test.exe+0x4b58c6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 var_set_copy_mode(int) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:208 (T_main_Linux_13.3_x86_64_test.exe+0x4c2896) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 _wrap_var_set_copy_mode swig_Linux_13.3_x86_64/sim_services_wrap.cpp:157101 (T_main_Linux_13.3_x86_64_test.exe+0x8966ef) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 <null> <null> (libpython3.11.so.1.0+0x1d3435) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #4 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (T_main_Linux_13.3_x86_64_test.exe+0x5be545) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (T_main_Linux_13.3_x86_64_test.exe+0x4b30f2) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (T_main_Linux_13.3_x86_64_test.exe+0x4b4ef7) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  As if synchronized via sleep:
    #0 nanosleep ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:397 (libtsan.so.2+0x58cc6) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::Clock::clock_spin(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Clock/Clock.cpp:91 (T_main_Linux_13.3_x86_64_test.exe+0x36e6be) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableServerSession.cpp:197</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Read of size 8 at 0x722c00016948 by main thread (mutexes: write M0):
    #0 Trick::VariableServerSession::get_cycle_tics() const /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:197 (T_main_Linux_13.3_x86_64_test.exe+0x4b116d) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 Trick::VariableServerSession::copy_and_write_scheduled(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:69 (T_main_Linux_13.3_x86_64_test.exe+0x4bb13a) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::VariableServer::copy_and_write_scheduled() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServer_copy_and_write_scheduled.cpp:15 (T_main_Linux_13.3_x86_64_test.exe+0x4c0555) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 VariableServerSimObject::call_function(Trick::JobData*) build/S_source.cpp:543 (T_main_Linux_13.3_x86_64_test.exe+0x1d8a3b) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (T_main_Linux_13.3_x86_64_test.exe+0x49a24f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:71 (T_main_Linux_13.3_x86_64_test.exe+0x3c6e06) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (T_main_Linux_13.3_x86_64_test.exe+0x3c5e29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8e6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #8 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous write of size 8 at 0x722c00016948 by thread T38:
    #0 Trick::VariableServerSession::var_cycle(double) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:232 (T_main_Linux_13.3_x86_64_test.exe+0x4b56e9) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 var_cycle(double) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:120 (T_main_Linux_13.3_x86_64_test.exe+0x4c245f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 _wrap_var_cycle swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156794 (T_main_Linux_13.3_x86_64_test.exe+0x8eb78c) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 <null> <null> (libpython3.11.so.1.0+0x1d3435) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #4 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (T_main_Linux_13.3_x86_64_test.exe+0x5be545) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (T_main_Linux_13.3_x86_64_test.exe+0x4b30f2) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (T_main_Linux_13.3_x86_64_test.exe+0x4b4ef7) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  As if synchronized via sleep:
    #0 nanosleep ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:397 (libtsan.so.2+0x58cc6) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::Clock::clock_spin(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Clock/Clock.cpp:91 (T_main_Linux_13.3_x86_64_test.exe+0x36e6be) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableServerSession.cpp:213</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Read of size 4 at 0x722c00016b8c by main thread (mutexes: write M0):
    #0 Trick::VariableServerSession::get_freeze_frame_offset() const /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:213 (T_main_Linux_13.3_x86_64_test.exe+0x4b124c) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 Trick::VariableServerSession::copy_and_write_freeze(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:19 (T_main_Linux_13.3_x86_64_test.exe+0x4bacbd) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::VariableServer::copy_and_write_freeze() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServer_copy_and_write_freeze.cpp:8 (T_main_Linux_13.3_x86_64_test.exe+0x4c0285) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 VariableServerSimObject::call_function(Trick::JobData*) build/S_source.cpp:552 (T_main_Linux_13.3_x86_64_test.exe+0x1d8a6b) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (T_main_Linux_13.3_x86_64_test.exe+0x49a24f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::Executive::freeze_loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_freeze_loop.cpp:67 (T_main_Linux_13.3_x86_64_test.exe+0x3c310d) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:42 (T_main_Linux_13.3_x86_64_test.exe+0x3c6bb8) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (T_main_Linux_13.3_x86_64_test.exe+0x3c5e29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #8 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8e6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #9 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous write of size 4 at 0x722c00016b8c by thread T41:
    #0 Trick::VariableServerSession::var_set_freeze_frame_offset(unsigned int) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:335 (T_main_Linux_13.3_x86_64_test.exe+0x4b5bed) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 var_set_freeze_frame_offset(unsigned int) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:272 (T_main_Linux_13.3_x86_64_test.exe+0x4c2c4e) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 _wrap_var_set_freeze_frame_offset swig_Linux_13.3_x86_64/sim_services_wrap.cpp:157332 (T_main_Linux_13.3_x86_64_test.exe+0x86d57f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 <null> <null> (libpython3.11.so.1.0+0x1d3435) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #4 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (T_main_Linux_13.3_x86_64_test.exe+0x5be545) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (T_main_Linux_13.3_x86_64_test.exe+0x4b30f2) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (T_main_Linux_13.3_x86_64_test.exe+0x4b4ef7) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  As if synchronized via sleep:
    #0 nanosleep ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:397 (libtsan.so.2+0x58cc6) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableServerSession.cpp:84</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Read of size 1 at 0x722c00016c50 by main thread (mutexes: write M0):
    #0 Trick::VariableServerSession::get_pause() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:84 (T_main_Linux_13.3_x86_64_test.exe+0x4b0f4e) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 Trick::VariableServerSession::copy_and_write_scheduled(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:63 (T_main_Linux_13.3_x86_64_test.exe+0x4bb085) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::VariableServer::copy_and_write_scheduled() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServer_copy_and_write_scheduled.cpp:15 (T_main_Linux_13.3_x86_64_test.exe+0x4c0555) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 VariableServerSimObject::call_function(Trick::JobData*) build/S_source.cpp:543 (T_main_Linux_13.3_x86_64_test.exe+0x1d8a3b) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (T_main_Linux_13.3_x86_64_test.exe+0x49a24f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:71 (T_main_Linux_13.3_x86_64_test.exe+0x3c6e06) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (T_main_Linux_13.3_x86_64_test.exe+0x3c5e29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8e6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #8 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous write of size 1 at 0x722c00016c50 by thread T42:
    #0 Trick::VariableServerSession::set_pause(bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:88 (T_main_Linux_13.3_x86_64_test.exe+0x4b0f89) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 var_unpause() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:139 (T_main_Linux_13.3_x86_64_test.exe+0x4c2533) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 _wrap_var_unpause swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156838 (T_main_Linux_13.3_x86_64_test.exe+0x6822c3) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 <null> <null> (libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #4 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (T_main_Linux_13.3_x86_64_test.exe+0x5be545) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (T_main_Linux_13.3_x86_64_test.exe+0x4b30f2) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (T_main_Linux_13.3_x86_64_test.exe+0x4b4ef7) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  As if synchronized via sleep:
    #0 nanosleep ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:397 (libtsan.so.2+0x58cc6) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::Clock::clock_spin(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Clock/Clock.cpp:91 (T_main_Linux_13.3_x86_64_test.exe+0x36e6be) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:217</summary>

```
WARNING: ThreadSanitizer: data race (pid=20387)
  Write of size 8 at 0x722800020280 by thread T6:
    #0 operator delete(void*, unsigned long) ../../../../src/libsanitizer/tsan/tsan_new_delete.cpp:150 (libtsan.so.2+0xa66c8) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::VariableServerSession::var_clear() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:217 (S_main_Linux_13.3_x86_64.exe+0x4bde8a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 var_clear() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:109 (S_main_Linux_13.3_x86_64.exe+0x4cac70) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 _wrap_var_clear swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156761 (S_main_Linux_13.3_x86_64.exe+0x694e3f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 <null> <null> (libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #5 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (S_main_Linux_13.3_x86_64.exe+0x5d19c9) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (S_main_Linux_13.3_x86_64.exe+0x4bb97a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (S_main_Linux_13.3_x86_64.exe+0x4bd77f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (S_main_Linux_13.3_x86_64.exe+0x4a8747) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)

  Previous write of size 1 at 0x722800020286 by main thread (mutexes: write M0, write M1):
    #0 Trick::VariableReference::stageValue(bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:295 (S_main_Linux_13.3_x86_64.exe+0x4b0718) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #1 Trick::VariableServerSession::copy_sim_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:28 (S_main_Linux_13.3_x86_64.exe+0x4c3ece) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 Trick::VariableServerSession::copy_sim_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:13 (S_main_Linux_13.3_x86_64.exe+0x4c3dc0) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 Trick::VariableServerSession::copy_and_write_freeze_scheduled(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:41 (S_main_Linux_13.3_x86_64.exe+0x4c371a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 Trick::VariableServer::copy_and_write_freeze_scheduled() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServer_copy_and_write_freeze_scheduled.cpp:15 (S_main_Linux_13.3_x86_64.exe+0x4c8c5f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 VariableServerSimObject::call_function(Trick::JobData*) build/S_source.cpp:549 (S_main_Linux_13.3_x86_64.exe+0x1d2a06) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (S_main_Linux_13.3_x86_64.exe+0x4a2ad7) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::Executive::freeze_loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_freeze_loop.cpp:43 (S_main_Linux_13.3_x86_64.exe+0x3ca4d5) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:42 (S_main_Linux_13.3_x86_64.exe+0x3ce0ca) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #9 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (S_main_Linux_13.3_x86_64.exe+0x3cd33b) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #10 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (S_main_Linux_13.3_x86_64.exe+0x5c1d6a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #11 main build/S_source.cpp:1350 (S_main_Linux_13.3_x86_64.exe+0x1d3666) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:28</summary>

```
WARNING: ThreadSanitizer: data race (pid=20387)
  Write of size 8 at 0x722c000058f0 by thread T6:
    #0 std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >::push_back(Trick::VariableReference* const&) /usr/include/c++/13/bits/stl_vector.h:1288 (S_main_Linux_13.3_x86_64.exe+0x4c2153) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #1 Trick::VariableServerSession::var_add(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:28 (S_main_Linux_13.3_x86_64.exe+0x4c2153)
    #2 var_add(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:26 (S_main_Linux_13.3_x86_64.exe+0x4ccca7) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 _wrap_var_add__SWIG_0 swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156379 (S_main_Linux_13.3_x86_64.exe+0x7cdea1) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 _wrap_var_add swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156450 (S_main_Linux_13.3_x86_64.exe+0x7cdea1)
    #5 <null> <null> (libpython3.11.so.1.0+0x1d3125) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #6 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (S_main_Linux_13.3_x86_64.exe+0x5d19c9) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (S_main_Linux_13.3_x86_64.exe+0x4bb97a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (S_main_Linux_13.3_x86_64.exe+0x4bd77f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #9 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (S_main_Linux_13.3_x86_64.exe+0x4a8747) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)

  Previous read of size 8 at 0x722c000058f0 by main thread (mutexes: write M0):
    #0 std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >::size() const /usr/include/c++/13/bits/stl_vector.h:993 (S_main_Linux_13.3_x86_64.exe+0x4c3e11) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #1 Trick::VariableServerSession::copy_sim_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, bool) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:18 (S_main_Linux_13.3_x86_64.exe+0x4c3e11)
    #2 Trick::VariableServerSession::copy_sim_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_sim_data.cpp:13 (S_main_Linux_13.3_x86_64.exe+0x4c3dc0) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 Trick::VariableServerSession::copy_and_write_freeze_scheduled(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_copy_and_write_modes.cpp:41 (S_main_Linux_13.3_x86_64.exe+0x4c371a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 Trick::VariableServer::copy_and_write_freeze_scheduled() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServer_copy_and_write_freeze_scheduled.cpp:15 (S_main_Linux_13.3_x86_64.exe+0x4c8c5f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 VariableServerSimObject::call_function(Trick::JobData*) build/S_source.cpp:549 (S_main_Linux_13.3_x86_64.exe+0x1d2a06) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::JobData::call() /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/JobData.cpp:184 (S_main_Linux_13.3_x86_64.exe+0x4a2ad7) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 Trick::Executive::freeze_loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_freeze_loop.cpp:43 (S_main_Linux_13.3_x86_64.exe+0x3ca4d5) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:42 (S_main_Linux_13.3_x86_64.exe+0x3ce0ca) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #9 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (S_main_Linux_13.3_x86_64.exe+0x3cd33b) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #10 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (S_main_Linux_13.3_x86_64.exe+0x5c1d6a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
```

</details>

<details><summary>TSan: data race at trick_source/sim_services/VariableServer/VariableServer_get_next_sync_call_time.cpp:20</summary>

```
WARNING: ThreadSanitizer: data race (pid=20480)
  Write of size 8 at 0x724800006750 by thread T38:
    #0 Trick::VariableServer::get_next_sync_call_time() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServer_get_next_sync_call_time.cpp:20 (T_main_Linux_13.3_x86_64_test.exe+0x4c0a82) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 var_set_copy_mode(int) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:210 (T_main_Linux_13.3_x86_64_test.exe+0x4c28c8) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 _wrap_var_set_copy_mode swig_Linux_13.3_x86_64/sim_services_wrap.cpp:157101 (T_main_Linux_13.3_x86_64_test.exe+0x8966ef) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 <null> <null> (libpython3.11.so.1.0+0x1d3435) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #4 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (T_main_Linux_13.3_x86_64_test.exe+0x5be545) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #5 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (T_main_Linux_13.3_x86_64_test.exe+0x4b30f2) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #6 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (T_main_Linux_13.3_x86_64_test.exe+0x4b4ef7) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #7 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (T_main_Linux_13.3_x86_64_test.exe+0x49febf) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Previous read of size 8 at 0x724800006750 by main thread:
    #0 Trick::ScheduledJobQueue::find_next_job(long long) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ScheduledJobQueue/ScheduledJobQueue.cpp:310 (T_main_Linux_13.3_x86_64_test.exe+0x48f9da) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #1 Trick::Executive::loop_single_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop_single_thread.cpp:69 (T_main_Linux_13.3_x86_64_test.exe+0x3c6d82) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 Trick::Executive::loop() /home/claude/brendanny/trick-tsan/trick_source/sim_services/Executive/Executive_loop.cpp:43 (T_main_Linux_13.3_x86_64_test.exe+0x3c5e29) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 master(int, char**) /home/claude/brendanny/trick-tsan/trick_source/sim_services/mains/master.cpp:45 (T_main_Linux_13.3_x86_64_test.exe+0x5ae8e6) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 main build/S_source.cpp:1313 (T_main_Linux_13.3_x86_64_test.exe+0x1d9642) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)

  Location is heap block of size 344 at 0x724800006600 allocated by main thread:
    #0 operator new(unsigned long) ../../../../src/libsanitizer/tsan/tsan_new_delete.cpp:64 (libtsan.so.2+0xa6fae) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::SimObject::add_job(int, int, char const*, void*, double, char const*, char const*, int, double, double) /home/claude/brendanny/trick-tsan/trick_source/sim_services/SimObject/SimObject.cpp:63 (T_main_Linux_13.3_x86_64_test.exe+0x49d7e1) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #2 VariableServerSimObject::VariableServerSimObject() <null> (T_main_Linux_13.3_x86_64_test.exe+0x1e283f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #3 __static_initialization_and_destruction_0 build/S_source.cpp:1058 (T_main_Linux_13.3_x86_64_test.exe+0x1ddb2f) (BuildId: 459811a00ccdc29717fe982c4730f5140f34e4cb)
    #4 _GLOBAL__sub_I_S_source.cpp build/S_source.cpp:1314 (T_main_Linux_13.3_x86_64_test.exe+0x1ddb2f)
    #5 call_init ../csu/libc-start.c:145 (libc.so.6+0x2a303) (BuildId: a4a7992a8e66555c8141ab2a08a8465ff6e0ea65)
```

</details>

<details><summary>TSan: heap-use-after-free at trick_source/sim_services/VariableServer/VariableReference.cpp:719</summary>

```
WARNING: ThreadSanitizer: heap-use-after-free (pid=20355)
  Read of size 8 at 0x72040001d048 by thread T6:
    #0 Trick::VariableReference::byteswap_var(char*, char*, Trick::VariableReference const&) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:719 (S_main_Linux_13.3_x86_64.exe+0x4ae425) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #1 Trick::VariableReference::byteswap_var(char*, char*) const /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:673 (S_main_Linux_13.3_x86_64.exe+0x4ae496) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 Trick::VariableReference::writeValueBinary(std::ostream&, bool) const /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:759 (S_main_Linux_13.3_x86_64.exe+0x4ae55b) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 Trick::VariableServerSession::write_binary_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> > const&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:113 (S_main_Linux_13.3_x86_64.exe+0x4c74ce) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 Trick::VariableServerSession::write_data(std::vector<Trick::VariableReference*, std::allocator<Trick::VariableReference*> >&, VS_MESSAGE_TYPE) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:230 (S_main_Linux_13.3_x86_64.exe+0x4c40a8) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 Trick::VariableServerSession::write_data() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_write_data.cpp:201 (S_main_Linux_13.3_x86_64.exe+0x4c3fb0) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 Trick::VariableServerSession::var_send() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:226 (S_main_Linux_13.3_x86_64.exe+0x4bdef6) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #7 var_send() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:100 (S_main_Linux_13.3_x86_64.exe+0x4cac07) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #8 _wrap_var_send swig_Linux_13.3_x86_64/sim_services_wrap.cpp:156739 (S_main_Linux_13.3_x86_64.exe+0x6949bb) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #9 <null> <null> (libpython3.11.so.1.0+0x1d37fe) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)
    #10 ip_parse /home/claude/brendanny/trick-tsan/trick_source/sim_services/InputProcessor/input_processor_ext.cpp:17 (S_main_Linux_13.3_x86_64.exe+0x5d19c9) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #11 Trick::VariableServerSession::handle_message() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession.cpp:162 (S_main_Linux_13.3_x86_64.exe+0x4bb97a) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #12 Trick::VariableServerSessionThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSessionThread_loop.cpp:101 (S_main_Linux_13.3_x86_64.exe+0x4bd77f) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #13 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (S_main_Linux_13.3_x86_64.exe+0x4a8747) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)

  Previous write of size 8 at 0x72040001d048 by thread T6:
    #0 realloc ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:698 (libtsan.so.2+0x56f52) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 REF_parse(RefParseContext*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/MemoryManager/ref_parser.y:180 (S_main_Linux_13.3_x86_64.exe+0x9c4e0d) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #2 Trick::MemoryManager::ref_attributes(char const*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/MemoryManager/MemoryManager_ref_attributes.cpp:27 (S_main_Linux_13.3_x86_64.exe+0xa00c6e) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #3 ref_attributes /home/claude/brendanny/trick-tsan/trick_source/sim_services/MemoryManager/MemoryManager_C_Intf.cpp:499 (S_main_Linux_13.3_x86_64.exe+0x9cd053) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #4 Trick::VariableReference::VariableReference(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableReference.cpp:96 (S_main_Linux_13.3_x86_64.exe+0x4b2575) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #5 Trick::VariableServerSession::var_add(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerSession_commands.cpp:25 (S_main_Linux_13.3_x86_64.exe+0x4c21df) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #6 var_add(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >) /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/var_server_ext.cpp:26 (S_main_Linux_13.3_x86_64.exe+0x4ccca7) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
```

</details>

<details><summary>TSan: signal handler spoils errno at trick_source/sim_services/Timer/it_handler.cpp:16</summary>

```
WARNING: ThreadSanitizer: signal handler spoils errno (pid=20324)
  Signal 14 handler invoked at:
    #0 it_handler(int) /home/claude/brendanny/trick-tsan/trick_source/sim_services/Timer/it_handler.cpp:16 (S_main_Linux_13.3_x86_64.exe+0x4aa01e) (BuildId: 6a8a9370181e445b7659306b24f00143cd65b4e4)
    #1 <null> <null> (libpython3.11.so.1.0+0x272a50) (BuildId: a0c5c6a8049367a0b4625151dc5b3fb718a64918)

```

</details>

<details><summary>TSan: thread leak at trick_source/sim_services/ThreadBase/ThreadBase.cpp:293</summary>

```
WARNING: ThreadSanitizer: thread leak (pid=20099)
  Thread T5 'VarServer0' (tid=20106, finished) created by thread T4 at:
    #0 pthread_create ../../../../src/libsanitizer/tsan/tsan_interceptors_posix.cpp:1022 (libtsan.so.2+0x5ac1a) (BuildId: 2a13a7710e361d06f7babbea53065ca2be93f738)
    #1 Trick::ThreadBase::create_thread() /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:293 (VariableServerListenThread_test+0xf831f) (BuildId: 3d20c188cf88cead11ed6ed6e7b25ce6284f2da4)
    #2 Trick::VariableServerListenThread::thread_body() /home/claude/brendanny/trick-tsan/trick_source/sim_services/VariableServer/VariableServerListenThread.cpp:182 (VariableServerListenThread_test+0xfe63b) (BuildId: 3d20c188cf88cead11ed6ed6e7b25ce6284f2da4)
    #3 Trick::ThreadBase::thread_helper(void*) /home/claude/brendanny/trick-tsan/trick_source/sim_services/ThreadBase/ThreadBase.cpp:395 (VariableServerListenThread_test+0xf8ca3) (BuildId: 3d20c188cf88cead11ed6ed6e7b25ce6284f2da4)

```

</details>

```

</details>

