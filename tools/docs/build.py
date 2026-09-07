"""Prepare/build the additive Zensical pilot, never deploy or edit docs/.

The ignored projection is necessary until Zensical supports excluding Jekyll
helpers. `serve` mirrors edits/additions/removals into it for normal live reload.
"""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from common import ROOT, is_helper


def source_files(root: Path) -> dict[str, Path]:
    result = {}
    if (root / "docs").is_symlink():
        raise ValueError("docs/ must not be a symlink")
    for path in sorted((root / "docs").rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Documentation symlinks are not supported: {path}")
        if path.is_file():
            name = path.relative_to(root / "docs").as_posix()
            if not is_helper(name) and not any(
                part.startswith(".") for part in Path(name).parts
            ):
                result[name] = path
    if "index.md" not in result:
        raise ValueError("Missing docs/index.md")
    return result


def require_generated_path(root: Path, path: Path) -> None:
    """Only operate on the two fixed disposable directories; reject symlinks."""
    if path not in {root / ".docs-build/source", root / "site"}:
        raise ValueError(f"Not a generated docs directory: {path}")
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError(f"Generated directory must not be a symlink: {path}")
    tracked = subprocess.check_output([
        "git",
        "-C",
        str(root),
        "ls-files",
        "--",
        str(path.relative_to(root)),
    ])
    if tracked.strip():
        raise ValueError(f"Refusing to overwrite tracked files: {path}")


def stage(root: Path, previous: dict | None = None) -> dict:
    directory = root / ".docs-build/source"
    require_generated_path(root, directory)
    paths = source_files(root)
    fingerprints = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths.items()
    }
    if previous is None:
        if directory.exists():
            shutil.rmtree(directory)
        previous = {}
    for name in previous.keys() - fingerprints.keys():
        (directory / name).unlink(missing_ok=True)
    for name, digest in fingerprints.items():
        if previous.get(name) != digest:
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(paths[name], target)
    return fingerprints


def zensical_command(*args: str) -> list[str]:
    executable = Path(sys.executable).parent / (
        "zensical.exe" if os.name == "nt" else "zensical"
    )
    if not executable.is_file():
        raise RuntimeError(
            "Install tools/docs/requirements.txt in the active Python environment first"
        )
    return [str(executable), *args]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["prepare", "build", "serve"], nargs="?", default="build"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on all Zensical warnings (future corpus gate)",
    )
    args = parser.parse_args()
    if args.strict and args.command != "build":
        parser.error("--strict applies to build only")
    fingerprints = stage(ROOT)
    print(
        f"Prepared {len(fingerprints)} source files; authored docs/ was not modified.",
        flush=True,
    )
    if args.command == "prepare":
        return 0
    if args.command == "serve":
        child = subprocess.Popen(zensical_command("serve"), cwd=ROOT)
        try:
            while child.poll() is None:
                time.sleep(0.5)
                fingerprints = stage(ROOT, fingerprints)
        except KeyboardInterrupt:
            pass
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
        return child.returncode or 0
    output = ROOT / "site"
    require_generated_path(ROOT, output)
    if output.exists():
        shutil.rmtree(output)
    log_path = ROOT / ".docs-build/zensical-build.log"
    command = zensical_command(
        "build", "--clean", *(["--strict"] if args.strict else [])
    )
    with log_path.open("w", encoding="utf-8") as log:
        result = subprocess.run(
            command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=300
        )
    log = log_path.read_text(encoding="utf-8")
    plain = re.sub(r"\x1b\[[0-9;]*m", "", log)
    for line in plain.splitlines():
        if "issues found" in line or "Build finished" in line or "Error:" in line:
            print(line)
    print("Full build log:", log_path)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
