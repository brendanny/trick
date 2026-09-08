#!/usr/bin/env python3
"""Run the generated binding/IPPython/MSD integration gate in a subprocess."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=ROOT.parent / "build/msd")
    parser.add_argument("--output", type=Path)
    opts = parser.parse_args()
    build = opts.build_dir.resolve()
    cache = (build / "CMakeCache.txt").read_text()
    match = re.search(r"^UDUNITS_INCLUDE:PATH=(.*)$", cache, re.M)
    native = Path(match[1]).parent if match else Path("/usr")
    input_file = REPO / "trick_sims/SIM_msd/RUN_bindings/input.py"
    env = os.environ.copy()
    env.update(PYTHONHOME=sys.base_prefix, VIRTUAL_ENV=sys.prefix, TRICK_HOME=str(REPO),
               TRICK_PYTHON_PATH=str(build / "integration"),
               PYTHONPATH=str(build / "integration"))
    env["LD_LIBRARY_PATH"] = os.pathsep.join([str(Path(sys.base_prefix)/"lib"), str(build),
                                             str(build/"integration"), env.get("LD_LIBRARY_PATH", "")])
    xml = native / "share/xml/udunits/udunits2.xml"
    if xml.exists(): env.setdefault("UDUNITS2_XML_PATH", str(xml))
    command = [build/"integration/poc_msd", build/"libpoc_fixture.so", build/"integration/libintegration_models.so",
               input_file, ROOT/"contracts.py", ROOT/"after_restore.py", ROOT/"cleanup.py"]
    try:
        completed = subprocess.run([str(p) for p in command], cwd=REPO/"trick_sims/SIM_msd", env=env,
                                   text=True, errors="replace", capture_output=True, timeout=45)
        log = completed.stdout + completed.stderr
        code = completed.returncode
    except (OSError, subprocess.TimeoutExpired) as error:
        log, code = str(error), -1
    (build / "integration/run.log").write_text(log)
    records = [line.split("=", 1)[1] for line in log.splitlines() if line.startswith("INTEGRATION_RESULT=")]
    groups = [line.split("=", 1)[1] for line in log.splitlines() if line.startswith("INTEGRATION_CHECKS=")]
    result = json.loads(records[-1]) if records else {"status": "fail"}
    if code != 0 or not records or not groups: result["status"] = "fail"
    result.update(exit_code=code, checks=json.loads(groups[-1]) if groups else [],
                  platform=platform.platform(), python=platform.python_version(),
                  pybind11=importlib.metadata.version("pybind11"), libclang=importlib.metadata.version("libclang"),
                  cxx_flags=re.search(r"^CMAKE_CXX_FLAGS:STRING=(.*)$", cache, re.M)[1],
                  build_type=re.search(r"^CMAKE_BUILD_TYPE:STRING=(.*)$", cache, re.M)[1],
                  asan_options=env.get("ASAN_OPTIONS"), ubsan_options=env.get("UBSAN_OPTIONS"),
                  input_file=str(input_file.relative_to(REPO)), input_sha256=hashlib.sha256(input_file.read_bytes()).hexdigest(),
                  declarations=json.loads((build/"integration/generated/declarations.json").read_text()))
    if result["status"] == "fail":
        result["diagnostic"] = log[-12000:]
        print(log, file=sys.stderr)
    output = opts.output or build/"integration/results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(f"MSD integration: {result['status']} ({len(result['checks'])} contract groups)")
    return 0 if result["status"] == "pass" else 1

if __name__ == "__main__":
    sys.exit(main())
