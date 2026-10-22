# Input file for bench/vs_bench.py. The SIM runs in real time at 100 Hz.
#
#   VS_CONF_PORT        TCP port for the variable server (required)
#   VS_CONF_PARENT_PID  PID of the benchmark; the SIM exits when it is gone

import os
import threading
import time

trick.var_allow_connections()
trick.var_server_set_port(int(os.environ["VS_CONF_PORT"]))

trick.real_time_enable()
trick.itimer_enable()
trick.exec_set_software_frame(0.01)
trick.exec_set_terminate_time(36000.0)
bench.probe.expected_period = 0.01

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
