"""Variable server soak test (rewrite Phase 5 exit test).

Starts SIM_vs_conformance with RUN_soak/input.py and runs 8 clients for the
given time:

  1  ascii-async      ASCII, copy and write on the session's cycle (20 Hz)
  2  binary-async     binary with names, 50 Hz, byteswap on
  3  scheduled        copy at the end of the frame, write on the cycle, no names
  4  when-copied      copy at the end of the frame, write as soon as copied
  5  top-of-frame     copy at the top of every second frame, write as copied
  6  polling          var_send, var_exists and var_send_list_size in a loop;
                      reconnects every 200 polls
  7  python           Python lines, var_set, var_send_once and list changes
  8  control          loads the checkpoint taken at 1 s every
                      --reload-s seconds, and polls var_send_once between

Each client checks the shape of what it receives and that data keeps
arriving. The run passes if the SIM is alive at the end and then shuts down
cleanly (trick.stop()), every client got data after every reload, no client
saw a malformed reply, and (in a sanitizer build) the sanitizer wrote no
report.

    python3 soak/vs_soak.py --minutes 10 [--reload-s 10] [--wrapper "..."]

For the Phase 5 exit test, build Trick and the SIM with
tools/vs-sanitizer-env.sh tsan first.
"""

from __future__ import annotations

import argparse
import glob
import os
import socket
import struct
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIM_DIR = HERE.parent
sys.path.insert(0, str(SIM_DIR / "conformance"))

from vsclient import wait_for_server  # noqa: E402

HOST = "127.0.0.1"
P = "conf.vars."
STALL_S = 20.0  # longest gap with no data that is not a failure (a reload under TSan is slow)


@dataclass
class ClientStats:
    name: str
    messages: int = 0
    bytes: int = 0
    reconnects: int = 0
    errors: list[str] = field(default_factory=list)
    last_data: float = field(default_factory=time.monotonic)
    longest_gap: float = 0.0

    def got(self, n: int, messages: int = 1) -> None:
        now = time.monotonic()
        self.longest_gap = max(self.longest_gap, now - self.last_data)
        self.last_data = now
        self.bytes += n
        self.messages += messages

    def error(self, text: str) -> None:
        if len(self.errors) < 20:
            self.errors.append(text)


class Client(threading.Thread):
    """One soak client. Subclasses set up the session and parse the replies."""

    def __init__(self, name: str, port: int, stop: threading.Event) -> None:
        super().__init__(name=name, daemon=True)
        self.port = port
        self.stop_event = stop
        self.stats = ClientStats(name)
        self.sock: socket.socket | None = None
        self.buf = bytearray()

    def connect(self) -> None:
        if self.sock is not None:
            self.sock.close()
        self.sock = socket.create_connection((HOST, self.port), timeout=30)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.settimeout(0.2)
        self.buf.clear()

    def send(self, text: str) -> None:
        assert self.sock is not None
        self.sock.sendall(text.encode())

    def recv(self) -> bool:
        assert self.sock is not None
        try:
            chunk = self.sock.recv(1 << 16)
        except socket.timeout:
            return True
        if not chunk:
            return False
        self.buf += chunk
        return True

    def run(self) -> None:
        try:
            self.connect()
            self.setup()
            while not self.stop_event.is_set():
                if not self.recv():
                    self.stats.error("the server closed the connection")
                    self.connect()
                    self.stats.reconnects += 1
                    self.setup()
                    continue
                self.parse()
                self.step()
        except Exception as e:  # noqa: BLE001 - a soak client reports everything
            self.stats.error(f"{type(e).__name__}: {e}")
        finally:
            if self.sock is not None:
                try:
                    self.sock.sendall(b"trick.var_exit()\n")
                except OSError:
                    pass
                self.sock.close()

    def setup(self) -> None:
        raise NotImplementedError

    def step(self) -> None:
        pass

    # ASCII: whole lines "<type>\t...\n".
    def parse_ascii(self, expect_type: bytes = b"0", fields: int | None = None) -> None:
        while True:
            i = self.buf.find(b"\n")
            if i < 0:
                return
            line = bytes(self.buf[:i])
            del self.buf[: i + 1]
            parts = line.split(b"\t")
            if parts[0] != expect_type:
                # A long value can split a message; a continuation starts with no type.
                if parts[0].isdigit():
                    self.stats.error(f"unexpected message type {line[:40]!r}")
                continue
            if fields is not None and len(parts) - 1 != fields:
                self.stats.error(f"{len(parts) - 1} values, expected {fields}: {line[:80]!r}")
            self.stats.got(len(line) + 1)

    # Binary: 12-byte header, then `count` values.
    def parse_binary(self, names: bool, swap: bool, fields: int) -> None:
        order = ">" if swap else "<"
        while len(self.buf) >= 12:
            mtype, size, count = struct.unpack_from(order + "iii", self.buf, 0)
            total = size + 4
            if mtype != 0 or total < 12 or total > 8192 or count != fields:
                self.stats.error(f"bad binary header type={mtype} size={size} count={count}")
                self.buf.clear()
                return
            if len(self.buf) < total:
                return
            pos = 12
            for _ in range(count):
                if names:
                    (n,) = struct.unpack_from(order + "i", self.buf, pos)
                    pos += 4 + n
                vtype, vsize = struct.unpack_from(order + "ii", self.buf, pos)
                pos += 8 + vsize
            if pos != total:
                self.stats.error(f"binary message is {total} bytes but its values take {pos}")
            del self.buf[:total]
            self.stats.got(total)


ASYNC_VARS = ["time", P + "i32", P + "d", P + "str", P + "vec[1]", P + "dptr", P + "label_ptrs[1].text"]


class AsciiAsync(Client):
    def setup(self) -> None:
        self.send("trick.var_set_client_tag(\"soak-ascii\")\ntrick.var_cycle(0.05)\n"
                  + "".join(f'trick.var_add("{v}")\n' for v in ASYNC_VARS))

    def parse(self) -> None:
        self.parse_ascii(fields=len(ASYNC_VARS))


class BinaryAsync(Client):
    def setup(self) -> None:
        self.send("trick.var_binary()\ntrick.var_byteswap(True)\ntrick.var_cycle(0.02)\n"
                  + "".join(f'trick.var_add("{v}")\n' for v in ASYNC_VARS))

    def parse(self) -> None:
        self.parse_binary(names=True, swap=True, fields=len(ASYNC_VARS))


SCHED_VARS = ["time", P + "i32", P + "darr", P + "iarr[2]", P + "bits.s4", P + "settable"]


class Scheduled(Client):
    def setup(self) -> None:
        self.send("trick.var_binary_nonames()\ntrick.var_cycle(0.1)\n"
                  + "".join(f'trick.var_add("{v}")\n' for v in SCHED_VARS)
                  + "trick.var_set_copy_mode(1)\n")

    def parse(self) -> None:
        self.parse_binary(names=False, swap=False, fields=len(SCHED_VARS))


class WhenCopied(Client):
    def setup(self) -> None:
        self.send("trick.var_cycle(0.05)\n" + "".join(f'trick.var_add("{v}")\n' for v in SCHED_VARS)
                  + "trick.var_sync(2)\n")

    def parse(self) -> None:
        self.parse_ascii(fields=len(SCHED_VARS))


class TopOfFrame(Client):
    def setup(self) -> None:
        self.send("trick.var_set_copy_mode(2)\ntrick.var_set_write_mode(1)\ntrick.var_set_frame_multiple(2)\n"
                  + "".join(f'trick.var_add("{v}")\n' for v in ASYNC_VARS))

    def parse(self) -> None:
        self.parse_ascii(fields=len(ASYNC_VARS))


class Polling(Client):
    polls = 0

    def setup(self) -> None:
        self.send("trick.var_pause()\n" + "".join(f'trick.var_add("{v}")\n' for v in ASYNC_VARS[:4]))
        self.next_poll = 0.0

    def parse(self) -> None:
        while True:
            i = self.buf.find(b"\n")
            if i < 0:
                return
            line = bytes(self.buf[:i])
            del self.buf[: i + 1]
            kind = line.split(b"\t", 1)[0]
            if kind not in (b"0", b"1", b"3"):
                self.stats.error(f"unexpected reply {line[:60]!r}")
            self.stats.got(len(line) + 1)

    def step(self) -> None:
        now = time.monotonic()
        if now < self.next_poll:
            return
        self.next_poll = now + 0.02
        self.polls += 1
        self.send(f'trick.var_send()\ntrick.var_exists("{P}i32")\ntrick.var_send_list_size()\n')
        if self.polls % 200 == 0:
            self.connect()
            self.stats.reconnects += 1
            self.setup()


class Python(Client):
    n = 0

    def setup(self) -> None:
        self.next_step = 0.0
        self.send("trick.var_set_send_stdio(True)\n")

    def parse(self) -> None:
        # Replies: var_send_once ("5\t..."), stdio ("4 1 <n>\n<text>"). Count bytes only.
        if self.buf:
            self.stats.got(len(self.buf))
            if b"Traceback" in self.buf:
                self.stats.error(f"Python error: {bytes(self.buf[:200])!r}")
            self.buf.clear()

    def step(self) -> None:
        now = time.monotonic()
        if now < self.next_step:
            return
        self.next_step = now + 0.05
        self.n += 1
        k = self.n
        lines = [
            f"x = {k} + conf.vars.i32",
            f'trick.var_set("{P}settable", {k % 1000})',
            f'trick.var_add("{P}d")',
            f'trick.var_add("{P}vec[0]")',
            f'trick.var_send_once("{P}vec[0],{P}str,{P}settable", 3)',
            "trick.var_clear()",
        ]
        if k % 20 == 0:
            lines.append("print('soak', x)")
        self.send("\n".join(lines) + "\n")


class Control(Client):
    reloads = 0

    def __init__(self, name: str, port: int, stop: threading.Event, reload_s: float) -> None:
        super().__init__(name, port, stop)
        self.reload_s = reload_s

    def setup(self) -> None:
        self.next_reload = time.monotonic() + self.reload_s
        self.next_poll = 0.0

    def parse(self) -> None:
        self.parse_ascii(expect_type=b"5", fields=2)

    def step(self) -> None:
        now = time.monotonic()
        if now >= self.next_reload:
            self.next_reload = now + self.reload_s
            self.send('trick.load_checkpoint("RUN_soak/chkpnt_1.000000")\n')
            self.reloads += 1
        if now >= self.next_poll:
            self.next_poll = now + 0.1
            self.send(f'trick.var_send_once("{P}i32,time", 2)\n')


def free_port() -> int:
    with socket.socket() as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--reload-s", type=float, default=10.0)
    ap.add_argument("--wrapper", default=os.environ.get("VS_CONF_SIM_WRAPPER", ""))
    ap.add_argument("--exe")
    args = ap.parse_args()

    exe = Path(args.exe) if args.exe else Path(sorted(glob.glob(str(SIM_DIR / "S_main_*.exe")))[0])
    port = free_port()
    env = dict(os.environ, VS_CONF_PORT=str(port), VS_CONF_PARENT_PID=str(os.getpid()))
    log_dir = SIM_DIR / "conformance_logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / "soak.log"
    chk = SIM_DIR / "RUN_soak" / "chkpnt_1.000000"
    if chk.exists():
        chk.unlink()
    with open(log_path, "wb") as log:
        sim = subprocess.Popen(args.wrapper.split() + [str(exe), "RUN_soak/input.py"], cwd=SIM_DIR, env=env,
                               stdout=log, stderr=subprocess.STDOUT)
    try:
        wait_for_server(HOST, port, timeout_s=300.0, alive=lambda: sim.poll() is None)
        deadline = time.monotonic() + 300
        while not chk.exists() and time.monotonic() < deadline:
            time.sleep(0.5)
        if not chk.exists():
            print("the 1 s checkpoint was not written", file=sys.stderr)
            return 2

        stop = threading.Event()
        clients: list[Client] = [
            AsciiAsync("ascii-async", port, stop),
            BinaryAsync("binary-async", port, stop),
            Scheduled("scheduled", port, stop),
            WhenCopied("when-copied", port, stop),
            TopOfFrame("top-of-frame", port, stop),
            Polling("polling", port, stop),
            Python("python", port, stop),
            Control("control", port, stop, args.reload_s),
        ]
        for c in clients:
            c.start()
        end = time.monotonic() + args.minutes * 60
        while time.monotonic() < end and sim.poll() is None:
            time.sleep(1.0)
            for c in clients:
                gap = time.monotonic() - c.stats.last_data
                if gap > STALL_S:
                    c.stats.error(f"no data for {gap:.1f} s")
                    c.stats.last_data = time.monotonic()
        stop.set()
        for c in clients:
            c.join(timeout=10)
        alive = sim.poll() is None
        # End the SIM through its shutdown jobs, so the variable server stops and joins its threads.
        clean_exit = False
        if alive:
            try:
                with socket.create_connection((HOST, port), timeout=30) as s:
                    s.sendall(b"trick.stop()\n")
                sim.wait(timeout=300)
                clean_exit = sim.returncode == 0
            except (OSError, subprocess.TimeoutExpired) as e:
                print(f"the SIM did not shut down: {e}")
    finally:
        if sim.poll() is None:
            sim.terminate()
            try:
                sim.wait(timeout=60)
            except subprocess.TimeoutExpired:
                sim.kill()

    log_text = log_path.read_text(errors="replace")
    loads = log_text.count("Finished loading checkpoint file")
    failed = not alive or not clean_exit
    print(f"SIM alive at the end: {alive}; clean shutdown: {clean_exit}; checkpoint reloads finished: {loads}")
    print(f"{'client':14} {'messages':>9} {'bytes':>11} {'reconnects':>10} {'longest gap s':>13}  errors")
    for c in clients:
        s = c.stats
        print(f"{s.name:14} {s.messages:9d} {s.bytes:11d} {s.reconnects:10d} {s.longest_gap:13.2f}  {len(s.errors)}")
        for e in s.errors:
            print(f"    {e}")
        if s.errors or s.messages == 0:
            failed = True
    control = next(c for c in clients if isinstance(c, Control))
    if loads < max(1, control.reloads - 1):
        print(f"only {loads} of {control.reloads} reloads finished")
        failed = True
    log_dir_env = os.environ.get("VS_SANITIZER_LOG_DIR")
    if log_dir_env:
        # Sanitizer logs are named <log_path>.<pid>: only this SIM's count.
        reports = [p for p in glob.glob(os.path.join(log_dir_env, f"*.{sim.pid}")) if os.path.getsize(p) > 0]
        print(f"sanitizer reports: {len(reports)}")
        for r in reports[:10]:
            print(f"    {r}")
        failed = failed or bool(reports)
    print("PASS" if not failed else "FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
