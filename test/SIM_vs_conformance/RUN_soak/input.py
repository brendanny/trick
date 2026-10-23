# Input file for soak/vs_soak.py (rewrite Phase 5 exit test). The SIM runs in
# real time; the soak clients use every copy and write mode while a control
# client reloads the post-initialization checkpoint every few seconds.
#
#   VS_CONF_PORT        TCP port for the variable server (required)
#   VS_CONF_PARENT_PID  PID of the soak script; the SIM exits when it is gone

import os
import threading
import time

trick.var_allow_connections()
trick.var_server_set_port(int(os.environ["VS_CONF_PORT"]))

trick.real_time_enable()
trick.itimer_enable()
trick.exec_set_software_frame(0.05)
trick.exec_set_terminate_time(36000.0)

# The checkpoint the control client reloads: RUN_soak/chkpnt_1.000000, taken
# after initialization. (A post-initialization checkpoint is taken while
# initialization is still running, so a SIM that loads it never runs its
# shutdown jobs.)
trick.checkpoint(1.0)

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
