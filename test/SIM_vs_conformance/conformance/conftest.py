"""Fixtures for the variable server conformance suite.

The suite starts SIM_vs_conformance itself. Build the SIM first:

    cd test/SIM_vs_conformance && trick-CP

Then run, from the repository root:

    python3 -m pytest test/SIM_vs_conformance/conformance
"""

from __future__ import annotations

import glob
import os
import signal
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SIM_DIR = HERE.parent
sys.path.insert(0, str(HERE))

from vsclient import wait_for_server

HOST = "127.0.0.1"


def rewrite_selected() -> bool:
    """True when the SIM runs the rewritten variable server (rewrite Phase 5)."""
    return os.environ.get("TRICK_VS_REWRITE") == "1"


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("vs-conformance")
    group.addoption(
        "--update-goldens",
        action="store_true",
        help="Write the captured bytes to goldens/ instead of comparing.",
    )
    group.addoption(
        "--run-known-defects",
        action="store_true",
        help="Run tests that show known defects. Each starts its own SIM.",
    )
    group.addoption(
        "--sim-exe",
        default=None,
        help="SIM executable. Default: the T_main_*.exe or S_main_*.exe in the SIM directory.",
    )
    group.addoption(
        "--sim-wrapper",
        default=os.environ.get("VS_CONF_SIM_WRAPPER", ""),
        help="Command that runs the SIM, for example 'valgrind -q'.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "known_defect: shows a defect that the rewrite fixes"
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-known-defects"):
        return
    skip = pytest.mark.skip(reason="needs --run-known-defects")
    for item in items:
        if "known_defect" in item.keywords:
            item.add_marker(skip)


def find_sim_exe(config: pytest.Config) -> Path:
    given = config.getoption("--sim-exe")
    if given:
        return Path(given).resolve()
    found = sorted(
        glob.glob(str(SIM_DIR / "T_main_*.exe"))
        + glob.glob(str(SIM_DIR / "S_main_*.exe"))
    )
    if not found:
        pytest.exit(
            f"No SIM executable in {SIM_DIR}. Build it with: cd {SIM_DIR} && trick-CP",
            returncode=2,
        )
    return Path(found[0])


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


@dataclass
class RunningSim:
    proc: subprocess.Popen
    port: int
    log_path: Path

    def alive(self) -> bool:
        return self.proc.poll() is None

    def log_text(self) -> str:
        try:
            return self.log_path.read_text(errors="replace")
        except OSError:
            return ""

    def memory_error_reports(self) -> list[str]:
        """First line of each ASan or UBSan report from this SIM.

        ASan writes to $VS_SANITIZER_LOG_DIR/asan.<pid> when log_path is set
        (tools/vs-sanitizer-env.sh); UBSan always writes to the console.
        """
        texts = [self.log_text()]
        log_dir = os.environ.get("VS_SANITIZER_LOG_DIR")
        if log_dir:
            for p in Path(log_dir).glob(f"*.{self.proc.pid}"):
                texts.append(p.read_text(errors="replace"))
        return [
            line.strip()
            for text in texts
            for line in text.splitlines()
            if "ERROR: AddressSanitizer" in line or "runtime error:" in line
        ]

    def stop(self, timeout_s: float = 15.0) -> int | None:
        if self.alive():
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        return self.proc.returncode


def start_sim(config: pytest.Config, log_name: str, extra_env: dict[str, str] | None = None) -> RunningSim:
    exe = find_sim_exe(config)
    port = free_port()
    env = dict(os.environ)
    env.update(extra_env or {})
    env["VS_CONF_PORT"] = str(port)
    env["VS_CONF_PARENT_PID"] = str(os.getpid())
    log_dir = SIM_DIR / "conformance_logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"{log_name}.log"
    wrapper = config.getoption("--sim-wrapper").split()
    cmd = wrapper + [str(exe), "RUN_conformance/input.py"]
    with open(log_path, "wb") as log:
        proc = subprocess.Popen(
            cmd, cwd=SIM_DIR, env=env, stdout=log, stderr=subprocess.STDOUT
        )
    sim = RunningSim(proc=proc, port=port, log_path=log_path)
    try:
        wait_for_server(HOST, port, timeout_s=120.0, alive=sim.alive)
    except Exception:
        sim.stop()
        raise RuntimeError(f"SIM did not start; log follows:\n{sim.log_text()[-4000:]}")
    return sim


@pytest.fixture(scope="session")
def sim(pytestconfig: pytest.Config):
    running = start_sim(pytestconfig, "session")
    yield running
    alive_at_end = running.alive()
    running.stop()
    if not alive_at_end:
        pytest.fail(
            f"the SIM exited during the suite; log:\n{running.log_text()[-4000:]}"
        )
    # A golden is only trustworthy if the old server made it without a
    # memory error. Known memory defects belong in test_known_defects.py.
    reports = running.memory_error_reports()
    if reports:
        pytest.fail("sanitizer reports from the golden suite:\n" + "\n".join(reports))


@pytest.fixture
def fresh_sim(pytestconfig: pytest.Config, request: pytest.FixtureRequest):
    """A SIM for one test only, for tests that can crash or damage it."""
    running = start_sim(pytestconfig, request.node.name)
    yield running
    running.stop()
