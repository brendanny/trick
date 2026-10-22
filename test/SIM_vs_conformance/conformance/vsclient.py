"""Raw variable server client for the conformance suite.

This client does not parse replies. It records the exact bytes that the
server sends, so the suite can compare them with golden files.
"""

from __future__ import annotations

import select
import socket
import time
from dataclasses import dataclass

END_MARKER_VAR = "conf.vars.end_marker"
END_MARKER_REPLY = b"5\t@@vs-conformance-end@@\n"

# The server reads its socket once per loop and then sleeps for the update
# rate (0.1 s by default). Commands sent in separate sends with this gap
# between them go to separate reads.
COMMAND_GAP_S = 0.25
QUIET_S = 0.3


class ReplyTimeout(AssertionError):
    pass


@dataclass
class RawSession:
    host: str
    port: int
    timeout_s: float = 10.0

    def __post_init__(self) -> None:
        self.sock = socket.create_connection(
            (self.host, self.port), timeout=self.timeout_s
        )
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def __enter__(self) -> "RawSession":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def send(self, text: str) -> None:
        self.sock.sendall(text.encode("utf-8"))

    def _recv_some(self, deadline: float) -> bytes | None:
        """Return the next bytes, b"" at EOF, or None at the deadline."""
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        ready, _, _ = select.select([self.sock], [], [], remaining)
        if not ready:
            return None
        return self.sock.recv(65536)

    def run_case(self, commands: str) -> bytes:
        """Send one case and return every byte that it caused.

        The case commands go first. After a gap, the session switches to
        ASCII and asks for the end marker. The bytes before the marker reply
        are the case's reply.
        """
        self.send(commands)
        time.sleep(COMMAND_GAP_S)
        self.send(f'trick.var_ascii()\ntrick.var_send_once("{END_MARKER_VAR}")\n')

        data = bytearray()
        deadline = time.monotonic() + self.timeout_s
        while not data.endswith(END_MARKER_REPLY):
            chunk = self._recv_some(deadline)
            if chunk is None:
                raise ReplyTimeout(
                    f"no end marker after {self.timeout_s} s; got {len(data)} bytes"
                )
            if chunk == b"":
                raise ReplyTimeout(
                    f"server closed the connection; got {len(data)} bytes"
                )
            data += chunk

        # Nothing may follow the marker: the session is paused.
        extra = self._recv_some(time.monotonic() + QUIET_S)
        if extra:
            raise AssertionError(
                f"unexpected {len(extra)} bytes after the end marker: {extra[:64]!r}"
            )
        return bytes(data[: -len(END_MARKER_REPLY)])

    def read_until_eof(self, timeout_s: float) -> bytes:
        data = bytearray()
        deadline = time.monotonic() + timeout_s
        while True:
            chunk = self._recv_some(deadline)
            if chunk is None:
                raise ReplyTimeout(f"connection still open after {timeout_s} s")
            if chunk == b"":
                return bytes(data)
            data += chunk


def wait_for_server(host: str, port: int, timeout_s: float, alive) -> None:
    """Wait until the server accepts a connection, or raise."""
    deadline = time.monotonic() + timeout_s
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        if not alive():
            raise RuntimeError("the SIM exited before its variable server started")
        try:
            with socket.create_connection((host, port), timeout=1.0) as s:
                s.sendall(b"trick.var_exit()\n")
            return
        except OSError as e:
            last_error = e
            time.sleep(0.2)
    raise RuntimeError(
        f"variable server on port {port} not ready after {timeout_s} s: {last_error}"
    )
