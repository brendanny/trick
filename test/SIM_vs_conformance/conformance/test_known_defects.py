"""Tests that show defects in the old variable server.

Each test starts its own SIM, because the defect can crash it or damage its
memory. They run only with --run-known-defects. They are expected to fail
on the old server (xfail) and to pass after the rewrite. When a test passes,
remove its xfail mark in the same change that fixes the defect.

Run them under ASan to see the memory errors that do not crash the SIM:
see ../README.md.
"""

from __future__ import annotations

import struct
import time

import pytest
from conftest import HOST
from vsclient import RawSession

pytestmark = [pytest.mark.known_defect]

P = "conf.vars."


def assert_alive(sim) -> None:
    time.sleep(0.5)
    assert sim.alive(), (
        f"SIM exited with {sim.proc.returncode}; log:\n{sim.log_text()[-3000:]}"
    )
    # In a sanitizer build, a memory error is a failure even if the SIM lives.
    reports = sim.memory_error_reports()
    assert not reports, "sanitizer reports:\n" + "\n".join(reports)


@pytest.mark.xfail(
    reason="strings of 4096 bytes or more overflow the stage buffer (VariableReference.cpp stageValue)"
)
def test_long_string_ascii(fresh_sim) -> None:
    with RawSession(HOST, fresh_sim.port) as s:
        reply = s.run_case(
            f'trick.var_pause()\ntrick.var_add("{P}str_long")\ntrick.var_send()\n'
        )
    assert_alive(fresh_sim)
    assert reply == b"0\t" + b"x" * 5000 + b"\n"


@pytest.mark.xfail(
    reason="ASCII runs strlen past a char array with no NUL (VariableReference.cpp write_escaped_string)"
)
def test_char_array_without_nul_ascii(fresh_sim) -> None:
    with RawSession(HOST, fresh_sim.port) as s:
        reply = s.run_case(
            f'trick.var_pause()\ntrick.var_add("{P}carr_full")\ntrick.var_send()\n'
        )
    assert_alive(fresh_sim)
    assert reply == b"0\tABCDEFGH\n"
    # The plain build prints the right text by luck; ASan shows the overread.
    assert not fresh_sim.memory_error_reports()


@pytest.mark.xfail(
    reason="ASCII reads every enum as a 4-byte int, past a short enum's buffer (VariableReference.cpp writeValueAscii)"
)
def test_short_enum_ascii(fresh_sim) -> None:
    with RawSession(HOST, fresh_sim.port) as s:
        reply = s.run_case(
            f'trick.var_pause()\ntrick.var_add("{P}scoped")\ntrick.var_send()\n'
        )
    assert_alive(fresh_sim)
    assert reply == b"0\t-2\n"


@pytest.mark.xfail(
    reason="byteswap swaps the declared array length for one element (VariableReference.cpp byteswap_var)"
)
def test_byteswap_indexed_element(fresh_sim) -> None:
    with RawSession(HOST, fresh_sim.port) as s:
        reply = s.run_case(
            "trick.var_pause()\ntrick.var_binary_nonames()\ntrick.var_byteswap(True)\n"
            f'trick.var_add("{P}iarr[2]")\ntrick.var_add("{P}darr[1][1]")\ntrick.var_send()\n'
        )
    assert_alive(fresh_sim)
    # header (3 ints) + iarr[2] (type, size, int) + darr[1][1] (type, size, double), all big-endian
    expected = (
        struct.pack(">iii", 0, 12 + 12 + 16 - 4, 2)
        + struct.pack(">iii", 6, 4, 30)
        + struct.pack(">iid", 11, 8, 1.5)
    )
    assert reply == expected


@pytest.mark.xfail(
    reason="var_cycle(0) then scheduled copy mode divides by zero (VariableServerSession_commands.cpp)"
)
def test_cycle_zero_then_scheduled(fresh_sim) -> None:
    with RawSession(HOST, fresh_sim.port) as s:
        s.send("trick.var_pause()\ntrick.var_cycle(0)\ntrick.var_set_copy_mode(1)\n")
        time.sleep(0.5)
        reply = s.run_case(f'trick.var_send_once("{P}i32")\n')
    assert_alive(fresh_sim)
    assert reply == b"5\t-123456789\n"


@pytest.mark.xfail(
    reason="a command of 200 KB or more with no newline stalls the session (TCPConnection::read)"
)
def test_long_command_without_newline(fresh_sim) -> None:
    with RawSession(HOST, fresh_sim.port, timeout_s=10.0) as s:
        s.send("#" + "a" * 250_000)
        time.sleep(0.5)
        reply = s.run_case(f'\ntrick.var_pause()\ntrick.var_send_once("{P}i32")\n')
    assert_alive(fresh_sim)
    assert reply == b"5\t-123456789\n"


@pytest.mark.xfail(
    reason="var_add and var_clear change the list while the main thread copies it"
)
def test_list_changes_during_scheduled_copy(fresh_sim) -> None:
    names = [
        f"{P}{n}"
        for n in ("i32", "d", "str", "iarr", "darr", "big", "vec[1]", "cptr", "dptr[2]")
    ]
    churn = "".join(f'trick.var_add("{n}")\n' for n in names) + "trick.var_clear()\n"
    with RawSession(HOST, fresh_sim.port) as s:
        s.send(
            "trick.var_set_copy_mode(1)\ntrick.var_cycle(0.1)\ntrick.var_unpause()\n"
        )
        end = time.monotonic() + 10.0
        while time.monotonic() < end:
            s.send(churn * 20)
            time.sleep(0.01)
            try:
                s.sock.setblocking(False)
                while s.sock.recv(1 << 20):
                    pass
            except BlockingIOError:
                pass
            finally:
                s.sock.setblocking(True)
        reply = s.run_case(
            f'trick.var_pause()\ntrick.var_clear()\ntrick.var_send_once("{P}i32")\n'
        )
    assert_alive(fresh_sim)
    assert reply.endswith(b"5\t-123456789\n")
    # The old server gives no sign of the race without TSan, so this test
    # also fails if the SIM log has a sanitizer report.
    assert "ThreadSanitizer" not in fresh_sim.log_text()
    assert not fresh_sim.memory_error_reports()


@pytest.mark.xfail(
    reason="byteswap sends char*, std::string and wchar_t* values as zeros (VariableReference.cpp byteswap_var)"
)
def test_byteswap_strings(fresh_sim) -> None:
    with RawSession(HOST, fresh_sim.port) as s:
        reply = s.run_case(
            "trick.var_pause()\ntrick.var_binary_nonames()\ntrick.var_byteswap(True)\n"
            f'trick.var_add("{P}str")\ntrick.var_add("{P}wptr")\ntrick.var_send()\n'
        )
    assert_alive(fresh_sim)
    text = b"std string value\0"
    wide = struct.pack(">6I", *(ord(c) for c in "wptr!\0"))
    body = (
        struct.pack(">ii", 3, len(text))
        + text
        + struct.pack(">ii", 19, len(wide))
        + wide
    )
    assert reply == struct.pack(">iii", 0, 12 + len(body) - 4, 2) + body


@pytest.mark.xfail(
    reason="a char array reached through std::vector<T*> comes back as its first character"
)
def test_vector_of_pointers_char_array(fresh_sim) -> None:
    with RawSession(HOST, fresh_sim.port) as s:
        reply = s.run_case(
            f'trick.var_pause()\ntrick.var_add("{P}label_ptrs[1].text")\ntrick.var_send()\n'
        )
    assert_alive(fresh_sim)
    assert reply == b"0\tlabel 1\n"
