"""Exercise an already built native runtime in a disposable checkout/build tree."""

import argparse
import json
import os
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--build", type=Path, required=True)
parser.add_argument("--cmake", default="cmake")
parser.add_argument("--config", default="Release")
args = parser.parse_args()
source = args.source.resolve()
build = args.build.resolve()


def run(target):
    subprocess.run(
        [
            args.cmake,
            "--build",
            str(build),
            "--config",
            args.config,
            "--target",
            target,
            "--parallel",
            "3",
        ],
        check=True,
    )


roots = [
    build / "trick_source/sim_services/metadata" / args.config,
    build / "trick_source/sim_services/metadata",
]
root = next(path for path in roots if (path / "generation.stamp").exists())
stamp = root / "generation.stamp"
run("trick_core_codegen")
before = stamp.stat().st_mtime_ns
run("trick_core_codegen")
assert stamp.stat().st_mtime_ns == before, "No-op build reran ICG"

# Restore source mtimes so this does not leave unrelated build invalidations.
header = source / "include/trick/Clock.hh"
original = header.stat()
try:
    os.utime(header, None)
    run("trick_core_codegen")
    assert stamp.stat().st_mtime_ns != before, "Transitive header failed to rerun ICG"
finally:
    os.utime(header, ns=(original.st_atime_ns, original.st_mtime_ns))

manifest = json.loads((root / "manifest.json").read_text())
output = Path(manifest["headers"][0]["output"])
assert root in output.parents
output.unlink()
run("trick_core_codegen")
assert output.exists(), "Deleted metadata was not regenerated"

icg_candidates = [
    build / "trick_source/codegen/Interface_Code_Gen" / args.config / "trick-ICG",
    build / "trick_source/codegen/Interface_Code_Gen/trick-ICG",
]
icg = next(path for path in icg_candidates if path.exists())
before = stamp.stat().st_mtime_ns
os.utime(icg, None)
run("trick_core_codegen")
assert stamp.stat().st_mtime_ns != before, "Changed ICG did not rerun generation"

parser_dir = build / "trick_source/sim_services/MemoryManager/parsers"
unchanged = {
    name: (parser_dir / (name + "_parser.tab.cpp")).stat().st_mtime_ns
    for name in ("ref", "input")
}
grammar = source / "trick_source/sim_services/MemoryManager/adef_parser.y"
original = grammar.stat()
contents = grammar.read_bytes()
before = (parser_dir / "adef_parser.tab.cpp").stat().st_mtime_ns
try:
    grammar.chmod(original.st_mode | 0o200)
    grammar.write_bytes(contents + b"\n/* Native parser regeneration test. */\n")
    run("trick_mm")
    assert (parser_dir / "adef_parser.tab.cpp").stat().st_mtime_ns != before
    for name, timestamp in unchanged.items():
        assert (parser_dir / (name + "_parser.tab.cpp")).stat().st_mtime_ns == timestamp
finally:
    grammar.write_bytes(contents)
    grammar.chmod(original.st_mode)
    os.utime(grammar, ns=(original.st_atime_ns, original.st_mtime_ns))

# Changing the feature in an existing cache must replace the declared graph.
cache = (build / "CMakeCache.txt").read_text()
original_er7 = next(
    line.split("=", 1)[1]
    for line in cache.splitlines()
    if line.startswith("TRICK_USE_ER7_UTILS:BOOL=")
)
original_on = original_er7.upper() in ("ON", "TRUE", "YES", "1")


def configure_er7(value):
    subprocess.run(
        [
            args.cmake,
            "-S",
            str(source),
            "-B",
            str(build),
            "-DTRICK_USE_ER7_UTILS=" + value,
        ],
        check=True,
    )


try:
    configure_er7("OFF" if original_on else "ON")
    run("trick_core_codegen")
    changed = json.loads((root / "manifest.json").read_text())
    assert len(changed["headers"]) == (145 if original_on else 213)
finally:
    configure_er7(original_er7)
    run("trick_core_codegen")
assert len(json.loads((root / "manifest.json").read_text())["headers"]) == (
    213 if original_on else 145
)

swig_input = source / "include/trick/swig/trick_swig.i"
wrapper = (
    build / "trick_source/trick_swig/sim_services/wrapper/sim_servicesPYTHON_wrap.cxx"
)
original = swig_input.stat()
before = wrapper.stat().st_mtime_ns
try:
    os.utime(swig_input, None)
    run("trick_swig_sim_services")
    assert wrapper.stat().st_mtime_ns != before, (
        "Transitive SWIG input did not regenerate wrapper"
    )
finally:
    os.utime(swig_input, ns=(original.st_atime_ns, original.st_mtime_ns))
print("Native build graph checks passed")
