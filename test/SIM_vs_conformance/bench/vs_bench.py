"""Variable server benchmark.

Measures, for each copy mode and client count:
  * frame jitter: wall-clock period of a 100 Hz job in the SIM
  * command round trip: time from var_send_once to its reply, on a probe
    client with the default var_cycle (0.1 s)
  * throughput: values per second that the streaming clients receive

Each streaming client asks for 50 doubles at 100 Hz in ASCII.

    python3 bench/vs_bench.py --out bench/results.json [--seconds 10]

Run it on an idle machine. Numbers from different machines do not compare.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import platform
import signal
import socket
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIM_DIR = HERE.parent
sys.path.insert(0, str(SIM_DIR / "conformance"))

from vsclient import RawSession, wait_for_server  # noqa: E402

HOST = "127.0.0.1"
MODES = {0: "ASYNC", 1: "SCHEDULED", 2: "TOP_OF_FRAME"}
VARS_PER_CLIENT = 50
STREAM_CYCLE_S = 0.01


@dataclass
class Result:
    copy_mode: str
    clients: int
    seconds: float
    values_per_s: float = 0.0
    messages_per_s_per_client: float = 0.0
    rtt_ms_p50: float = 0.0
    rtt_ms_p99: float = 0.0
    rtt_ms_max: float = 0.0
    rtt_samples: int = 0
    frame_ms_mean: float = 0.0
    frame_ms_stdev: float = 0.0
    frame_ms_p99: float = 0.0
    frame_ms_max: float = 0.0
    frames_late_1ms: int = 0
    frames: int = 0
    sim_alive: bool = True
    notes: list[str] = field(default_factory=list)


def free_port() -> int:
    with socket.socket() as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def find_exe(given: str | None) -> Path:
    if given:
        return Path(given).resolve()
    found = sorted(
        glob.glob(str(SIM_DIR / "S_main_*.exe"))
        + glob.glob(str(SIM_DIR / "T_main_*.exe"))
    )
    if not found:
        sys.exit(f"No SIM executable in {SIM_DIR}; build it with trick-CP")
    return Path(found[0])


class Streamer(threading.Thread):
    def __init__(self, port: int, copy_mode: int, index: int) -> None:
        super().__init__(daemon=True)
        self.port = port
        self.copy_mode = copy_mode
        self.index = index
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.messages = 0
        self.values = 0
        self.error: str | None = None

    def snapshot(self) -> tuple[int, int]:
        with self.lock:
            return self.messages, self.values

    def run(self) -> None:
        try:
            sock = socket.create_connection((HOST, self.port), timeout=5)
            cmds = ["trick.var_pause()", f"trick.var_set_copy_mode({self.copy_mode})"]
            if self.copy_mode == 2:
                cmds.append("trick.var_set_frame_multiple(1)")
            cmds.append(f"trick.var_cycle({STREAM_CYCLE_S})")
            cmds += [
                f'trick.var_add("conf.vars.big[{i}]")' for i in range(VARS_PER_CLIENT)
            ]
            cmds.append("trick.var_unpause()")
            sock.sendall(("\n".join(cmds) + "\n").encode())
            sock.settimeout(0.5)
            pending = b""
            while not self.stop.is_set():
                try:
                    chunk = sock.recv(1 << 16)
                except socket.timeout:
                    continue
                if not chunk:
                    self.error = "server closed the connection"
                    return
                pending += chunk
                *lines, pending = pending.split(b"\n")
                with self.lock:
                    for line in lines:
                        if line.startswith(b"0\t"):
                            self.messages += 1
                            self.values += line.count(b"\t")
            sock.sendall(b"trick.var_exit()\n")
            sock.close()
        except OSError as e:
            self.error = str(e)


class RttProbe(threading.Thread):
    def __init__(self, port: int) -> None:
        super().__init__(daemon=True)
        self.port = port
        self.stop = threading.Event()
        self.recording = threading.Event()
        self.samples: list[float] = []
        self.error: str | None = None

    def run(self) -> None:
        try:
            sock = socket.create_connection((HOST, self.port), timeout=5)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.sendall(b"trick.var_pause()\n")
            sock.settimeout(5)
            while not self.stop.is_set():
                t0 = time.perf_counter()
                sock.sendall(b'trick.var_send_once("conf.vars.i32")\n')
                buf = b""
                while not buf.endswith(b"\n"):
                    chunk = sock.recv(4096)
                    if not chunk:
                        self.error = "server closed the connection"
                        return
                    buf += chunk
                dt = time.perf_counter() - t0
                if self.recording.is_set():
                    self.samples.append(dt)
                time.sleep(0.02)
            sock.close()
        except OSError as e:
            self.error = str(e)


def read_probe(port: int) -> dict[str, float]:
    fields = ["count", "mean", "stdev", "p99", "max", "late_1ms"]
    names = ",".join(f"bench.probe.{f}" for f in fields)
    with RawSession(HOST, port) as s:
        reply = s.run_case(
            f'trick.var_pause()\nbench.probe.compute()\ntrick.var_send_once("{names}", {len(fields)})\n'
        )
    parts = reply.decode().strip().split("\t")
    assert parts[0] == "5", reply
    return {f: float(v.split(" ")[0]) for f, v in zip(fields, parts[1:])}


def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    i = max(0, min(len(sorted_vals) - 1, int(round(p * len(sorted_vals) + 0.5)) - 1))
    return sorted_vals[i]


def run_one(
    exe: Path,
    wrapper: list[str],
    copy_mode: int,
    clients: int,
    seconds: float,
    log_dir: Path,
) -> Result:
    res = Result(copy_mode=MODES[copy_mode], clients=clients, seconds=seconds)
    port = free_port()
    env = dict(os.environ, VS_CONF_PORT=str(port), VS_CONF_PARENT_PID=str(os.getpid()))
    log_path = log_dir / f"bench_{MODES[copy_mode]}_{clients}.log"
    with open(log_path, "wb") as log:
        proc = subprocess.Popen(
            wrapper + [str(exe), "RUN_bench/input.py"],
            cwd=SIM_DIR,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    try:
        wait_for_server(HOST, port, 120.0, alive=lambda: proc.poll() is None)
        streamers = [Streamer(port, copy_mode, i) for i in range(clients)]
        probe = RttProbe(port)
        for t in streamers:
            t.start()
        probe.start()
        time.sleep(2.0)  # warm up

        with RawSession(HOST, port) as s:
            s.run_case("trick.var_pause()\nbench.probe.reset()\n")
        start_counts = [t.snapshot() for t in streamers]
        probe.recording.set()
        t0 = time.monotonic()
        time.sleep(seconds)
        elapsed = time.monotonic() - t0
        end_counts = [t.snapshot() for t in streamers]
        probe.recording.clear()
        stats = read_probe(port)

        msgs = sum(e[0] - s0[0] for s0, e in zip(start_counts, end_counts))
        vals = sum(e[1] - s0[1] for s0, e in zip(start_counts, end_counts))
        res.values_per_s = vals / elapsed
        res.messages_per_s_per_client = (msgs / elapsed / clients) if clients else 0.0
        rtts = sorted(probe.samples)
        res.rtt_samples = len(rtts)
        res.rtt_ms_p50 = 1000 * statistics.median(rtts) if rtts else 0.0
        res.rtt_ms_p99 = 1000 * percentile(rtts, 0.99)
        res.rtt_ms_max = 1000 * (rtts[-1] if rtts else 0.0)
        res.frames = int(stats["count"])
        res.frame_ms_mean = 1000 * stats["mean"]
        res.frame_ms_stdev = 1000 * stats["stdev"]
        res.frame_ms_p99 = 1000 * stats["p99"]
        res.frame_ms_max = 1000 * stats["max"]
        res.frames_late_1ms = int(stats["late_1ms"])

        for t in streamers:
            t.stop.set()
        probe.stop.set()
        for t in streamers + [probe]:
            t.join(timeout=5)
            if t.error:
                res.notes.append(f"{type(t).__name__}: {t.error}")
    finally:
        res.sim_alive = proc.poll() is None
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    return res


def machine_info() -> dict[str, str]:
    info = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpus": str(os.cpu_count()),
    }
    try:
        info["cpu_model"] = next(
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        )
    except (OSError, StopIteration):
        pass
    return info


def to_markdown(results: list[Result]) -> str:
    head = (
        "| Copy mode | Clients | Values/s | Msgs/s per client | RTT p50 ms | RTT p99 ms "
        "| Frame mean ms | Frame stdev ms | Frame p99 ms | Frame max ms | Late > 1 ms |"
    )
    rows = [head, "|" + " --- |" * 11]
    for r in results:
        rows.append(
            f"| {r.copy_mode} | {r.clients} | {r.values_per_s:.0f} | {r.messages_per_s_per_client:.1f} "
            f"| {r.rtt_ms_p50:.1f} | {r.rtt_ms_p99:.1f} | {r.frame_ms_mean:.3f} | {r.frame_ms_stdev:.3f} "
            f"| {r.frame_ms_p99:.3f} | {r.frame_ms_max:.3f} | {r.frames_late_1ms} |"
        )
    return "\n".join(rows)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", type=Path, required=True, help="JSON results file")
    ap.add_argument(
        "--seconds", type=float, default=10.0, help="measured time per configuration"
    )
    ap.add_argument(
        "--clients", default="0,1,8", help="comma-separated streaming client counts"
    )
    ap.add_argument("--modes", default="0,1,2", help="comma-separated copy modes")
    ap.add_argument("--sim-exe", default=None)
    ap.add_argument("--sim-wrapper", default="")
    args = ap.parse_args()

    exe = find_exe(args.sim_exe)
    log_dir = SIM_DIR / "conformance_logs"
    log_dir.mkdir(exist_ok=True)
    results = []
    for mode in (int(m) for m in args.modes.split(",")):
        for n in (int(c) for c in args.clients.split(",")):
            r = run_one(exe, args.sim_wrapper.split(), mode, n, args.seconds, log_dir)
            print(
                f"{r.copy_mode:>12} clients={n}: {r.values_per_s:8.0f} values/s, "
                f"rtt p50 {r.rtt_ms_p50:6.1f} ms, frame p99 {r.frame_ms_p99:.3f} ms, "
                f"late>1ms {r.frames_late_1ms}"
                + (f"  NOTES: {r.notes}" if r.notes else ""),
                flush=True,
            )
            results.append(r)

    doc = {
        "machine": machine_info(),
        "sim": exe.name,
        "results": [asdict(r) for r in results],
    }
    args.out.write_text(json.dumps(doc, indent=2) + "\n")
    args.out.with_suffix(".md").write_text(to_markdown(results) + "\n")
    print(to_markdown(results))


if __name__ == "__main__":
    main()
