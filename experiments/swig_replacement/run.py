#!/usr/bin/env python3
"""Run all eight implementations in import and native-embedding modes."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
BACKENDS = ("pybind", "nanobind", "reflection", "cpython", "shiboken", "cppyy", "cython", "cffi")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build")
    parser.add_argument("--output", type=Path, help="Default: BUILD/results.json")
    parser.add_argument("--backends", nargs="+", choices=BACKENDS, default=BACKENDS)
    parser.add_argument("--modes", nargs="+", choices=("import", "embed"), default=("import", "embed"))
    args = parser.parse_args()
    build = args.build_dir.resolve()
    logs = build / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    build_result = json.loads((build / "build-results.json").read_text()) if (build / "build-results.json").exists() else {}
    env = os.environ.copy()
    env["POC_BUILD"] = str(build)
    env["LD_LIBRARY_PATH"] = os.pathsep.join([str(Path(sys.base_prefix) / "lib"), str(build), env.get("LD_LIBRARY_PATH", "")])
    env["PYTHONPATH"] = os.pathsep.join([str(build), str(ROOT / "python"), env.get("PYTHONPATH", "")])
    env.setdefault("CLING_EXTRA_ARGS", "-std=c++17")
    native = build_result.get("native_prefix")
    if native:
        prefix = Path(native)
        xml = prefix / "share/xml/udunits/udunits2.xml"
        if xml.exists(): env.setdefault("UDUNITS2_XML_PATH", str(xml))
        env["POC_NATIVE_PREFIX"] = native
    packages = {}
    for name in ("pybind11", "nanobind", "Cython", "cffi", "shiboken6", "shiboken6-generator", "cppyy", "CPyCppyy", "cppyy-cling", "cppyy-backend"):
        try: packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: packages[name] = None
    result = {"base_commit": "c5ba06ea79a8a9ecc3fa4938fd45a77b1e7b9e43",
              "platform": platform.platform(), "python": platform.python_version(),
              "packages": packages, "toolchain": build_result.get("toolchain", {}),
              "build": build_result.get("stages", {}), "runs": []}
    for backend in args.backends:
        for mode in args.modes:
            name = backend + "-" + mode
            command = ([sys.executable] if mode == "import" else [str(build / "poc_embed"), sys.executable])
            command += [str(ROOT / "python/cases.py"), backend]
            env["POC_MODE"] = mode
            start = time.perf_counter()
            try:
                completed = subprocess.run(command, env=env, cwd=ROOT, text=True, errors="replace",
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
                output, code = completed.stdout, completed.returncode
            except (OSError, subprocess.TimeoutExpired) as error:
                output, code = str(error), -1
            (logs / (name + ".log")).write_text(output)
            records = [line[len("POC_RESULT="):] for line in output.splitlines() if line.startswith("POC_RESULT=")]
            run = json.loads(records[-1]) if records else {"backend": backend, "mode": mode, "cases": {}}
            failed = any(c["status"] == "fail" for c in run["cases"].values())
            run.update(status="pass" if code == 0 and records and not failed else "fail", exit_code=code,
                       process_seconds=time.perf_counter() - start, log="logs/" + name + ".log")
            if run["status"] == "fail": run["diagnostic"] = output[-6000:]
            result["runs"].append(run)
            counts = {status: sum(c["status"] == status for c in run["cases"].values()) for status in ("pass", "limitation", "fail")}
            print(f"{name}: {run['status']} {counts}", flush=True)
    result["probes"] = []
    result["artifact_bytes"] = {p.name: p.stat().st_size for p in sorted(build.iterdir()) if p.is_file() and (p.suffix == ".so" or p.name == "poc_embed")}
    if "nanobind" in args.backends:
        try:
            completed = subprocess.run([sys.executable, str(ROOT / "python/negative_cases.py")],
                                       env=env, cwd=ROOT, text=True, errors="replace",
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            (logs / "nanobind-raw-ownership.log").write_text(completed.stdout)
            records = [line[10:] for line in completed.stdout.splitlines() if line.startswith("POC_PROBE=")]
            probe = json.loads(records[-1]) if records else {"name": "nanobind_raw_ownership", "status": "fail"}
            if completed.returncode: probe["status"] = "fail"
        except (OSError, subprocess.TimeoutExpired) as error:
            probe = {"name": "nanobind_raw_ownership", "status": "fail", "detail": str(error)}
        result["probes"].append(probe)
        print(f"nanobind raw ownership: {probe['status']}", flush=True)
    output_path = args.output or build / "results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    return 1 if any(r["status"] == "fail" for r in result["runs"] + result["probes"]) else 0

if __name__ == "__main__":
    sys.exit(main())
