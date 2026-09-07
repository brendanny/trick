#!/usr/bin/env python3
"""Build the standalone experiments, keeping per-backend failure evidence."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import time

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-prefix", type=Path, help="Prefix containing include/, lib/, bin/ and share/ (normally /usr)")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build")
    parser.add_argument("--clang-include", type=Path, help="Clang builtin header directory for Shiboken, if not found automatically")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    logs = build / "logs"
    logs.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env["PATH"]
    native = args.native_prefix.resolve() if args.native_prefix else None
    if native:
        env["PATH"] = str(native / "bin") + os.pathsep + env["PATH"]
        if (native / "share/bison").exists(): env["BISON_PKGDATADIR"] = str(native / "share/bison")
        if (native / "bin/m4").exists(): env["M4"] = str(native / "bin/m4")
    # Installed alongside this interpreter, independent of activation/PATH.
    cmake = [sys.executable, "-m", "cmake"]
    result = {"stages": {}, "native_prefix": str(native) if native else None}
    result["toolchain"] = {}
    for name, command in (("cxx", [os.environ.get("CXX", "c++"), "--version"]),
                          ("flex", ["flex", "--version"]), ("bison", ["bison", "--version"]),
                          ("cmake", cmake + ["--version"])):
        try:
            result["toolchain"][name] = subprocess.check_output(command, env=env, text=True, stderr=subprocess.STDOUT).splitlines()[0]
        except (OSError, subprocess.CalledProcessError):
            result["toolchain"][name] = "unavailable"

    def stage(name, command):
        start = time.perf_counter()
        with (logs / (name + ".log")).open("w") as log:
            try:
                completed = subprocess.run([str(x) for x in command], env=env, cwd=ROOT,
                                           stdout=log, stderr=subprocess.STDOUT, timeout=600)
                code = completed.returncode
            except (OSError, subprocess.TimeoutExpired) as error:
                log.write(str(error)); code = -1
        result["stages"][name] = {"status": "pass" if code == 0 else "fail",
                                  "exit_code": code, "seconds": time.perf_counter() - start,
                                  "log": "logs/" + name + ".log"}
        print(f"{name}: {result['stages'][name]['status']}", flush=True)
        return code == 0

    configure = cmake + ["-S", ROOT, "-B", build, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
                        "-DPython_EXECUTABLE=" + sys.executable]
    if native: configure.append("-DCMAKE_PREFIX_PATH=" + str(native))
    # Some relocatable Python distributions retain a nonexistent /install/lib
    # in sysconfig. Use the library actually accompanying the running Python.
    candidates = sorted(p for p in (Path(sys.base_prefix) / "lib").glob(f"libpython{sys.version_info.major}.{sys.version_info.minor}.so*") if p.is_file())
    if candidates: configure.append("-DPython_LIBRARY=" + str(candidates[0]))
    configured = stage("configure", configure)
    base = cmake + ["--build", build, "--parallel", str(args.jobs), "--target"]
    core = configured and stage("fixture", base + ["poc_fixture", "poc_embed"])
    if core:
        for target in ("pybind", "nanobind", "cpython", "abi", "cython"):
            stage(target, base + ["poc_" + target])
        success = stage("nanobind_default_init", base + ["poc_nanobind_default_init"])
        diagnostic = (logs / "nanobind_default_init.log").read_text()
        if not success and "operator new" in diagnostic and "nb_class.h" in diagnostic:
            result["stages"]["nanobind_default_init"]["status"] = "observed_limitation"
        # Shiboken's pip wheel ships the generator and runtime; no Qt GUI needed.
        site = Path(sysconfig.get_paths()["purelib"])
        generator = site / "shiboken6_generator/shiboken6"
        clang_include = args.clang_include
        if not clang_include:
            available = sorted((site / "cppyy_backend/etc/cling/lib/clang").glob("*/include"))
            if available: clang_include = available[-1]
        command = [generator, "--generator-set=shiboken", "--avoid-protected-hack", "--use-global-header",
                   "--compiler-path=" + (shutil.which(os.environ.get("CXX", "c++")) or "c++"),
                   "--clang-option=-DPOC_GENERATOR", "--output-directory=" + str(build),
                   "-I" + str(ROOT / "include")]
        if clang_include: command.append("-isystem" + str(clang_include.resolve()))
        command += [ROOT / "include/poc.hh", ROOT / "shiboken/typesystem.xml"]
        if stage("shiboken_generate", command):
            libraries = sorted((site / "shiboken6").glob("libshiboken6*.so.*"))
            if not libraries:
                result["stages"]["shiboken"] = {"status": "fail", "detail": "runtime library missing"}
            else:
                command = [os.environ.get("CXX", "c++"), "-std=c++17", "-O3", "-shared", "-fPIC",
                           *sorted((build / "poc_shiboken").glob("*_wrapper.cpp")),
                           "-I" + str(ROOT / "include"), "-I" + str(ROOT.parents[1] / "include"),
                           "-I" + str(site / "shiboken6/include"), "-I" + sysconfig.get_paths()["include"],
                           "-L" + str(build), "-lpoc_fixture", libraries[0],
                           "-Wl,-rpath,$ORIGIN", "-Wl,-rpath," + str(site / "shiboken6"),
                           "-o", build / ("poc_shiboken" + sysconfig.get_config_var("EXT_SUFFIX"))]
                if native: command.append("-I" + str(native / "include"))
                stage("shiboken", command)
    (build / "build-results.json").write_text(json.dumps(result, indent=2) + "\n")
    return 1 if any(s["status"] == "fail" for s in result["stages"].values()) else 0

if __name__ == "__main__":
    sys.exit(main())
