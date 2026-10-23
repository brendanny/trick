"""The core library's golden replay test reads the cases from a generated file.

This check needs no SIM: it fails when cases.py changed and
tools/vs-export-golden-cases.py was not run.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[3] / "tools" / "vs-export-golden-cases.py"


def test_golden_cases_inc_is_current() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
