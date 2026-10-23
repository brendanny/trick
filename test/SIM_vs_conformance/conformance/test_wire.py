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
from cases import CASES, EXPECTED_TO_CHANGE, NAMES, Case
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
    if case.name in EXPECTED_TO_CHANGE:
        check_changed_case(case.name, actual)
        return
    assert actual == expected, describe_mismatch(expected, actual)


# ----------------------------------------------------------------------
# Cases that record an old defect (EXPECTED_TO_CHANGE). The goldens are the
# old server's bytes (Phase 0); the rewritten server fixes these defects, so
# its bytes differ on purpose. These checks are the same as
# trick_utils/var_server/test/GoldenReplay.hh.
# ----------------------------------------------------------------------

# An unindexed pointer to numbers (dptr) sends the array it points to.
FIXES = {"ascii_pointers": (b"0\t\t0.5\t", b"0\t0.5,1,1.5,2\t0.5\t")}

ELEMENT_SIZE = {4: 2, 5: 2, 6: 4, 7: 4, 10: 4, 18: 4, 19: 4, 25: 4,
                8: 8, 9: 8, 14: 8, 15: 8, 11: 8}


def decode(data: bytes, names: bool, swap: bool) -> list[tuple[int, int, list[tuple[str, int, bytes]]]]:
    """Messages as (type, size, [(name, type, value)]); ints read swapped if `swap`."""
    order = ">" if swap else "<"
    out, pos = [], 0
    while pos + 12 <= len(data):
        mtype, size, count = struct.unpack_from(order + "iii", data, pos)
        pos += 12
        values = []
        for _ in range(count):
            name = ""
            if names:
                (n,) = struct.unpack_from(order + "i", data, pos)
                pos += 4
                name = data[pos : pos + n].decode()
                pos += n
            vtype, vsize = struct.unpack_from(order + "ii", data, pos)
            pos += 8
            values.append((name, vtype, data[pos : pos + vsize]))
            pos += vsize
        out.append((mtype, size, values))
    assert pos == len(data), "trailing bytes"
    return out


def swap_elements(value: bytes, n: int) -> bytes:
    return b"".join(value[i : i + n][::-1] for i in range(0, len(value), n))


def check_changed_case(name: str, actual: bytes) -> None:
    expected = (GOLDEN_DIR / f"{name}.bin").read_bytes()
    if name in FIXES:
        old, new = FIXES[name]
        assert old in expected, f"{name}: the golden no longer has the bytes the fix replaces"
        fixed = expected.replace(old, new, 1)
        assert actual == fixed, describe_mismatch(fixed, actual)
        return
    # A byteswap case: the structure is the golden's; a value may differ only if
    # it is the unswapped capture's value of the same variable, correctly swapped.
    nonames = "_nonames_" in name
    suffix = name[name.rfind("_"):]
    want = decode(expected, not nonames, True)
    have = decode(actual, not nonames, True)
    names = decode((GOLDEN_DIR / f"byteswap{suffix}.bin").read_bytes(), True, True)
    native = {v[0]: v for m in decode((GOLDEN_DIR / f"binary{suffix}.bin").read_bytes(), True, False) for v in m[2]}
    assert len(have) == len(want)
    changed = 0
    for (wt, ws, wv), (ht, hs, hv), (_, _, nv) in zip(want, have, names):
        assert (ht, hs, len(hv)) == (wt, ws, len(wv))
        for (wn, wtype, wval), (hn, htype, hval), (var, _, _) in zip(wv, hv, nv):
            assert (hn, htype, len(hval)) == (wn, wtype, len(wval)), var
            if hval == wval:
                continue
            changed += 1
            ref = native[var][2]
            size = ELEMENT_SIZE.get(htype, len(hval) if htype in (12, 13, 21) else 1)
            assert hval == swap_elements(ref, size), f"{name}: {var} is not the correctly swapped value"
    assert changed > 0, f"{name} is in EXPECTED_TO_CHANGE but nothing changed"


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
