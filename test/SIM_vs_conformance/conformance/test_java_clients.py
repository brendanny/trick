"""The Java apps' command sequences against the server.

java/VsJavaCheck.java uses the apps' own VariableServerConnection and
SimulationInformation classes (no GUI, no Maven) and sends what the sim
control panel, Trick View, MTV and Monte Monitor send, then reads the beacon
as the sniffer does. It does not replace a check of the GUI apps by hand.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import HOST, SIM_DIR, start_sim

REPO = SIM_DIR.parents[1]
JAVA_SRC = REPO / "trick_source" / "java" / "src" / "main" / "java"
SOURCES = [
    JAVA_SRC / "trick" / "common" / "utils" / "VariableServerConnection.java",
    JAVA_SRC / "trick" / "common" / "utils" / "VariableServerRefusedConnectionException.java",
    JAVA_SRC / "trick" / "sniffer" / "SimulationInformation.java",
    SIM_DIR / "java" / "VsJavaCheck.java",
]


@pytest.mark.skipif(shutil.which("javac") is None or shutil.which("java") is None, reason="needs a JDK")
def test_java_client_sequences(pytestconfig: pytest.Config, tmp_path: Path) -> None:
    build = subprocess.run(
        ["javac", "-nowarn", "-d", str(tmp_path)] + [str(s) for s in SOURCES],
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    sim = start_sim(pytestconfig, "java_clients")
    try:
        run = subprocess.run(
            ["java", "-cp", str(tmp_path), "VsJavaCheck", HOST, str(sim.port)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert sim.alive()
    finally:
        sim.stop()
    assert run.returncode == 0, run.stdout + run.stderr
    assert "ALL PASS" in run.stdout
