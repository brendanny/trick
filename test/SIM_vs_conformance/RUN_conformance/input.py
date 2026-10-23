# Input file for the variable server conformance suite.
#
# The suite (conformance/) starts this SIM. It sets these environment
# variables:
#   VS_CONF_PORT        TCP port for the variable server (required)
#   VS_CONF_PARENT_PID  PID of the test process; the SIM exits when it is gone
#
# The SIM stays in freeze, so sim time stays at 0 and every value is fixed.

import os
import threading
import time

trick.var_allow_connections()
trick.var_server_set_port(int(os.environ["VS_CONF_PORT"]))

trick.real_time_enable()
trick.itimer_enable()
trick.exec_set_software_frame(0.1)
trick.exec_set_freeze_frame(0.1)
# SIGINT (the suite's stop) then exits through the shutdown jobs instead of toggling freeze.
trick.exec_set_enable_freeze(False)
trick.exec_set_freeze_command(True)
trick.exec_set_terminate_time(36000.0)

# Write RUN_conformance/chkpnt_post_init (how data/old_server.checkpoint was made).
if os.environ.get("VS_CONF_CHECKPOINT") == "1":
    trick.checkpoint_post_init(True)

# Do not leave an orphan SIM if the test process dies.
_parent = int(os.environ.get("VS_CONF_PARENT_PID", "0"))


def _watch_parent():
    while True:
        time.sleep(1.0)
        try:
            os.kill(_parent, 0)
        except OSError:
            os._exit(3)


if _parent > 0:
    threading.Thread(target=_watch_parent, daemon=True).start()
