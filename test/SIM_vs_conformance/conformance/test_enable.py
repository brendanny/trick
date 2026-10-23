"""The enabled flag is the master switch (upstream #2133).

When the variable server is disabled at run time, it closes the sessions that
are connected and refuses new clients. The beacon continues.
"""

from __future__ import annotations

import socket
import time

from conftest import HOST
from vsclient import RawSession

P = "conf.vars."


def _closed_by_server(sock: socket.socket, timeout_s: float) -> bool:
    """True if the server closes `sock` within the time; data before the close is ignored."""
    sock.settimeout(0.2)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if sock.recv(65536) == b"":
                return True
        except socket.timeout:
            continue
        except OSError:
            return True
    return False


def test_disable_closes_every_session(fresh_sim) -> None:
    with RawSession(HOST, fresh_sim.port) as watcher, RawSession(HOST, fresh_sim.port) as control:
        # Both sessions work before.
        assert watcher.run_case(f'trick.var_add("{P}i32")\ntrick.var_send()\ntrick.var_clear()\n') == (
            b"0\t-123456789\n"
        )
        control.send("trick.var_server_set_enabled(0)\n")
        assert _closed_by_server(control.sock, 10.0), "the session that disabled the server stays open"
        assert _closed_by_server(watcher.sock, 10.0), "a connected session stays open"

    # A new client is closed at once and no command runs.
    with socket.create_connection((HOST, fresh_sim.port), timeout=5.0) as late:
        late.sendall(b'trick.var_add("conf.vars.i32")\ntrick.var_send()\n')
        assert _closed_by_server(late, 10.0)
    assert fresh_sim.alive()
    assert "disabled; closing" in fresh_sim.log_text()
