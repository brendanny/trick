"""A checkpoint written by the old server loads into the rewritten one.

The variable server's settings are checkpointed at the same paths as before
(rewrite decision 5). data/old_server.checkpoint is a post-initialization
checkpoint of this SIM, written by the old server before Phase 6 removed it.
The test points its listen settings at a free port, loads it into a SIM that
runs the rewritten server, and checks that the server then serves with the
checkpoint's settings.
"""

from __future__ import annotations

import re
import time

import pytest
from conftest import HOST, SIM_DIR, free_port, start_sim
from vsclient import RawSession, wait_for_server

P = "conf.vars."
OLD_CHECKPOINT = SIM_DIR / "data" / "old_server.checkpoint"


def test_old_server_checkpoint_loads(pytestconfig: pytest.Config) -> None:
    text = OLD_CHECKPOINT.read_text(errors="replace")
    assert "trick_vs.vs.allow_connections = true;" in text
    assert "trick_vs.vs.listen_thread._requested_port" in text
    # The recorded port and host name belong to the machine that wrote the checkpoint.
    port = free_port()
    text = re.sub(r"(trick_vs\.vs\.listen_thread\._requested_port = )\d+;", rf"\g<1>{port};", text)
    text = re.sub(r'(trick_vs\.vs\.listen_thread\._requested_source_address = )"[^"]*";', r'\1"";', text)
    loaded = SIM_DIR / "RUN_conformance" / "chkpnt_old_server_test"
    loaded.write_text(text)

    sim = start_sim(pytestconfig, "checkpoint_old_server")
    try:
        with RawSession(HOST, sim.port) as s:
            s.send(f'trick.load_checkpoint("{loaded.relative_to(SIM_DIR)}")\n')
            deadline = time.monotonic() + 60
            while "Finished loading checkpoint file" not in sim.log_text():
                assert time.monotonic() < deadline, "the checkpoint did not load"
                time.sleep(0.2)
        assert sim.alive()
        # The restored settings move the listen port to the checkpoint's port.
        wait_for_server(HOST, port, timeout_s=30.0, alive=sim.alive)
        with RawSession(HOST, port) as s:
            reply = s.run_case(f'trick.var_pause()\ntrick.var_add("{P}i32")\ntrick.var_send()\n')
        assert reply == b"0\t-123456789\n"
    finally:
        sim.stop()
        loaded.unlink(missing_ok=True)
