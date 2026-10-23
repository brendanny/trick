"""Compare the server's reply bytes with the golden captures.

The golden files are the old server's bytes on x86_64 Linux. Binary replies
use native byte order and native type sizes, so the suite runs only on
64-bit little-endian hosts.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest
from cases import CASES, NAMES, Case
from conftest import HOST
from vsclient import RawSession

GOLDEN_DIR = Path(__file__).resolve().parent / "goldens"

pytestmark = pytest.mark.skipif(
    sys.byteorder != "little" or struct.calcsize("P") != 8,
    reason="golden files are for 64-bit little-endian hosts",
)


def capture(port: int, case: Case) -> bytes:
    with RawSession(HOST, port) as session:
        return session.run_case(case.script())


def first_difference(a: bytes, b: bytes) -> int:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return min(len(a), len(b))


def describe_mismatch(expected: bytes, actual: bytes) -> str:
    at = first_difference(expected, actual)
    lo = max(0, at - 32)
    return (
        f"first difference at byte {at} (expected {len(expected)} bytes, got {len(actual)})\n"
        f"expected[{lo}:{at + 32}] = {expected[lo : at + 32]!r}\n"
        f"actual  [{lo}:{at + 32}] = {actual[lo : at + 32]!r}"
    )


@pytest.mark.parametrize("case", CASES, ids=NAMES)
def test_reply_matches_golden(sim, pytestconfig: pytest.Config, case: Case) -> None:
    golden = GOLDEN_DIR / f"{case.name}.bin"
    actual = capture(sim.port, case)

    if pytestconfig.getoption("--update-goldens"):
        # A golden is only useful if the reply is the same every time.
        again = capture(sim.port, case)
        assert again == actual, (
            f"reply is not repeatable:\n{describe_mismatch(actual, again)}"
        )
        GOLDEN_DIR.mkdir(exist_ok=True)
        golden.write_bytes(actual)
        return

    assert golden.exists(), f"no golden file {golden.name}; run with --update-goldens"
    expected = golden.read_bytes()
    assert actual == expected, describe_mismatch(expected, actual)


# Goldens that are not command cases: test_beacon.py records beacon.bin.
OTHER_GOLDENS = {"beacon"}


def test_no_orphan_goldens() -> None:
    names = set(NAMES) | OTHER_GOLDENS
    orphans = sorted(p.name for p in GOLDEN_DIR.glob("*.bin") if p.stem not in names)
    assert not orphans, f"golden files with no case: {orphans}"


def test_var_exit_closes_connection(sim) -> None:
    with RawSession(HOST, sim.port) as session:
        session.send(
            'trick.var_pause()\ntrick.var_send_once("conf.vars.i32")\ntrick.var_exit()\n'
        )
        data = session.read_until_eof(timeout_s=5.0)
    assert data == b"5\t-123456789\n"


def test_session_survives_client_disconnect(sim) -> None:
    for _ in range(5):
        with RawSession(HOST, sim.port) as session:
            session.send(
                'trick.var_add("conf.vars.big")\ntrick.var_cycle(0.01)\ntrick.var_unpause()\n'
            )
    with RawSession(HOST, sim.port) as session:
        assert (
            session.run_case(
                'trick.var_pause()\ntrick.var_send_once("conf.vars.i32")\n'
            )
            == b"5\t-123456789\n"
        )
