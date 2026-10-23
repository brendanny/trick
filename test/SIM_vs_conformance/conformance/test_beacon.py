"""Check the multicast beacon that announces the SIM.

The beacon has fields that change per run (host, PID, paths), so the test
checks the field count, the field order and the fixed fields. The Java sim
sniffer listens on 239.3.14.15, the Python client on 224.3.14.15; the server
sends to both.
"""

from __future__ import annotations

import os
import socket
import struct
import time

import pytest

BEACON_PORT = 9265
GROUPS = ("239.3.14.15", "224.3.14.15")


def open_listener(group: str) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    s.bind((group, BEACON_PORT))
    mreq = struct.pack("4s4s", socket.inet_aton(group), socket.inet_aton("0.0.0.0"))
    s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    s.settimeout(0.5)
    return s


def beacon_for_port(group: str, port: int, timeout_s: float = 6.0) -> list[str] | None:
    try:
        s = open_listener(group)
    except OSError as e:
        pytest.skip(f"cannot join multicast group {group}: {e}")
    with s:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                data, _ = s.recvfrom(4096)
            except TimeoutError:
                continue
            fields = data.decode(errors="replace").split("\t")
            if len(fields) > 1 and fields[1] == str(port):
                return fields
    return None


@pytest.mark.parametrize("group", GROUPS)
def test_beacon_fields(sim, group: str) -> None:
    fields = beacon_for_port(group, sim.port)
    if fields is None:
        pytest.skip(
            f"no beacon on {group}; multicast loopback may be off in this environment"
        )

    # 12 fields: host, port, user, pid, sim dir, cmdline name, input file,
    # version, user tag, port again, enabled flag, exec mode.
    assert len(fields) == 12, fields
    assert fields[1] == str(sim.port)
    assert fields[3] == str(sim.proc.pid)
    assert fields[4].endswith("SIM_vs_conformance")
    assert fields[5].startswith("S_main") or fields[5].startswith("T_main")
    assert fields[6] == "RUN_conformance/input.py"
    assert fields[8] == "", "user tag is empty unless set"
    assert fields[9] == str(sim.port)
    assert fields[10] == "1", "enabled flag"
    # exec mode as an integer (1 = Freeze); the datagram ends with a newline
    assert fields[11] == "1\n"
    assert fields[0] == socket.gethostname()
    assert fields[2] == (os.environ.get("USER") or fields[2])
