"""Verify incremental SDK staging after build-tree tests, without concurrent builds."""

import argparse
import os
import subprocess
import time
from pathlib import Path

from verify_sdk_stage_helpers import validate as validate_helpers


def validate(args):
    validate_helpers(args.cmake)
    build = args.build.resolve()
    sdk = build / "sdk" / args.config
    manifest = build / "sdk-config" / args.config / "staged-files.txt"
    command = [
        args.cmake,
        "--build",
        str(build),
        "--config",
        args.config,
        "--target",
        "trick_sdk",
        "--parallel",
        "3",
    ]

    def run():
        subprocess.run(command, check=True)

    def snapshot():
        return {
            name: (sdk / name).lstat().st_mtime_ns
            for name in manifest.read_text().splitlines()
        }

    run()
    before = snapshot()
    if not before:
        raise RuntimeError("SDK inventory is empty")
    # Also expose churn on filesystems with one-second timestamp resolution.
    time.sleep(1.1)
    run()
    after = snapshot()
    changed = sorted(
        name
        for name in before.keys() | after.keys()
        if before.get(name) != after.get(name)
    )
    if changed:
        raise RuntimeError(f"No-op SDK build changed file mtimes: {changed}")

    # Simulate an inventory entry whose producer has disappeared. Files outside
    # the ownership manifest must survive the same synchronization.
    stale = sdk / f"include/stale-stage-test-{os.getpid()}/nested/stale.hh"
    user_output = sdk / f"user-stage-test-{os.getpid()}"
    original = manifest.read_text()
    try:
        stale.parent.mkdir(parents=True)
        stale.write_text("obsolete SDK header\n")
        user_output.write_text("user output\n")
        with manifest.open("a") as output:
            output.write(str(stale.relative_to(sdk)) + "\n")
        run()
        if stale.parent.parent.exists() or not user_output.is_file():
            raise RuntimeError("SDK inventory did not preserve ownership boundaries")
    finally:
        stale.unlink(missing_ok=True)
        user_output.unlink(missing_ok=True)
        if manifest.read_text() != original:
            manifest.write_text(original)
    print(f"SDK staging preserved {len(before)} mtimes and removed obsolete files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument("--config", default="Release")
    validate(parser.parse_args())
