"""A checkpoint written by the old server loads into the rewritten one (rewrite Phase 5).

The variable server's settings are checkpointed at the same paths as before
(rewrite decision 5), so a checkpoint from the old server must load into a
SIM that runs the rewritten server, and the server must then serve with the
checkpoint's settings: the old SIM's port, its allowlist and its switches.
"""

from __future__ import annotations

import shutil
import time

import pytest
from conftest import HOST, SIM_DIR, rewrite_selected, start_sim
from vsclient import RawSession

pytestmark = pytest.mark.skipif(not rewrite_selected(), reason="needs TRICK_VS_REWRITE=1")

P = "conf.vars."


def wait_for(path, timeout_s: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size > 0:
            return
        time.sleep(0.2)
    raise AssertionError(f"{path} was not written")


def test_old_server_checkpoint_loads_into_the_rewrite(pytestconfig: pytest.Config) -> None:
    run_dir = SIM_DIR / "RUN_conformance"
    written = run_dir / "chkpnt_post_init"
    saved = run_dir / "chkpnt_old_server"
    for f in (written, saved):
        if f.exists():
            f.unlink()

    old = start_sim(pytestconfig, "checkpoint_old_server", {"TRICK_VS_REWRITE": "0", "VS_CONF_CHECKPOINT": "1"})
    try:
        wait_for(written)
        time.sleep(0.5)
        shutil.copy(written, saved)
    finally:
        old.stop()
    text = saved.read_text(errors="replace")
    assert "trick_vs.vs.allow_connections = true;" in text
    assert "trick_vs.vs.listen_thread._requested_port" in text

    new = start_sim(pytestconfig, "checkpoint_new_server", {"TRICK_VS_REWRITE": "1"})
    try:
        assert "rewritten variable server is running" in new.log_text()
        with RawSession(HOST, new.port) as s:
            s.send(f'trick.load_checkpoint("{saved.relative_to(SIM_DIR)}")\n')
            deadline = time.monotonic() + 60
            while "Finished loading checkpoint file" not in new.log_text():
                assert time.monotonic() < deadline, "the checkpoint did not load"
                time.sleep(0.2)
        time.sleep(1.0)
        assert new.alive()
        # The checkpoint restored the old SIM's settings, its port among them, as the old
        # server restored them: the rewritten server now listens there.
        with RawSession(HOST, old.port) as s:
            reply = s.run_case(f'trick.var_pause()\ntrick.var_add("{P}i32")\ntrick.var_send()\n')
        assert reply == b"0\t-123456789\n"
    finally:
        new.stop()
        saved.unlink(missing_ok=True)
        written.unlink(missing_ok=True)
