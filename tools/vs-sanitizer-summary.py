#!/usr/bin/env python3
"""Group sanitizer reports by kind and first Trick frame.

    tools/vs-sanitizer-summary.py PATH... [--repo DIR] [--out summary.md]
                                  [--baseline baseline.json] [--write-baseline baseline.json]

Each PATH is a file or a directory (searched recursively). Give it the
log_path= directory of ASAN_OPTIONS and TSAN_OPTIONS, and also the console
logs of the tests and SIMs: GCC's UBSan ignores log_path when it is built
together with ASan, so its reports are only in the console output.

A signature is the report kind plus the first stack frame in a Trick source
file. With --baseline, the exit status is 1 if a signature is not in the
baseline.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ASAN_HEAD = re.compile(r"ERROR: AddressSanitizer: ([\w-]+)")
TSAN_HEAD = re.compile(r"WARNING: ThreadSanitizer: ([\w-]+(?: [\w-]+)*?)(?: \(|$)")
UBSAN_LINE = re.compile(r"(?:^|\s)([^\s:]+):(\d+):\d+: runtime error: (.*)$")
# ASan: "#0 0x55d0 in func /path/file.cpp:12:3"
# TSan: "#0 func /path/file.cpp:12 (binary+0x1234) (BuildId: ...)"
FRAME = re.compile(
    r"^\s*#\d+ (?:0x[0-9a-f]+ in )?(.+?) (/\S+?|[\w./-]+\.\w+):(\d+)(?::\d+)?(?: \(.*)?\s*$"
)
ANSI = re.compile(r"\x1b\[[0-9;]*m|\[[0-9;]*m(?=\S)")
SKIP_PATH = re.compile(
    r"/(usr|lib|lib64)/|sanitizer_common|libsanitizer|/gcc/|libstdc\+\+|/include/c\+\+/"
)


@dataclass
class Group:
    kind: str
    where: str
    function: str
    count: int = 0
    files: set[str] = field(default_factory=set)
    example: str = ""


def first_trick_frame(lines: list[str], repo: str) -> tuple[str, str]:
    for line in lines:
        m = FRAME.match(line)
        if not m:
            continue
        func, path, lineno = m.groups()
        if SKIP_PATH.search(path):
            continue
        rel = path[len(repo) + 1 :] if repo and path.startswith(repo + "/") else path
        return f"{rel}:{lineno}", func
    return "(no Trick frame)", ""


def parse_file(path: Path, repo: str) -> list[tuple[str, str, str, str]]:
    """Return (kind, where, function, first lines) for each report in a file."""
    # Trick colors its messages; drop the escape codes so paths compare.
    text = ANSI.sub("", path.read_text(errors="replace")).splitlines()
    out = []
    i = 0
    while i < len(text):
        line = text[i]
        m = ASAN_HEAD.search(line) or TSAN_HEAD.search(line)
        if m:
            tool = "ASan" if "AddressSanitizer" in line else "TSan"
            j = i + 1
            while j < len(text) and not (
                ASAN_HEAD.search(text[j])
                or TSAN_HEAD.search(text[j])
                or text[j].startswith("SUMMARY:")
            ):
                j += 1
            where, func = first_trick_frame(text[i:j], repo)
            out.append((
                f"{tool}: {m.group(1)}",
                where,
                func,
                "\n".join(text[i : min(j, i + 25)]),
            ))
            i = j + 1
            continue
        u = UBSAN_LINE.search(line)
        if u:
            src, lineno, msg = u.groups()
            rel = src[len(repo) + 1 :] if repo and src.startswith(repo + "/") else src
            kind = "UBSan: " + re.sub(r"0x[0-9a-f]+|-?\d+", "N", msg)[:90]
            out.append((kind, f"{rel}:{lineno}", "", "\n".join(text[i : i + 15])))
        i += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", type=Path, nargs="+")
    ap.add_argument("--repo", default="")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--baseline", type=Path)
    ap.add_argument("--write-baseline", type=Path)
    args = ap.parse_args()
    repo = str(Path(args.repo).resolve()) if args.repo else ""

    groups: dict[tuple[str, str], Group] = {}
    files: list[Path] = []
    for path in args.paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files += sorted(
                p for p in path.rglob("*") if p.is_file() and "venv" not in p.parts
            )
    for f in files:
        for kind, where, func, example in parse_file(f, repo):
            g = groups.setdefault(
                (kind, where), Group(kind, where, func, example=example)
            )
            g.count += 1
            g.files.add(str(f))

    by_kind: dict[str, list[Group]] = defaultdict(list)
    for g in groups.values():
        by_kind[g.kind.split(":")[0]].append(g)

    lines = ["## Sanitizer reports", ""]
    if not groups:
        lines.append(f"No reports in {len(files)} log files.")
    else:
        lines += [
            f"{len(groups)} distinct signatures, {sum(g.count for g in groups.values())} reports, "
            f"{len(files)} log files.",
            "",
            "| Tool and kind | First Trick frame | Function | Reports |",
            "| --- | --- | --- | --- |",
        ]
        for g in sorted(groups.values(), key=lambda g: (g.kind, -g.count, g.where)):
            lines.append(
                f"| {g.kind} | `{g.where}` | `{g.function[:60]}` | {g.count} |"
            )
        lines += ["", "### First report of each signature", ""]
        for g in sorted(groups.values(), key=lambda g: (g.kind, g.where)):
            lines += [
                f"<details><summary>{g.kind} at {g.where}</summary>",
                "",
                "```",
                g.example,
                "```",
                "",
                "</details>",
                "",
            ]
    md = "\n".join(lines) + "\n"
    if args.out:
        args.out.write_text(md)
    print(md)

    sigs = sorted(f"{k} @ {w}" for k, w in groups)
    if args.write_baseline:
        args.write_baseline.write_text(json.dumps(sigs, indent=2) + "\n")
    if args.baseline:
        known = set(json.loads(args.baseline.read_text()))
        new = [s for s in sigs if s not in known]
        gone = [s for s in known if s not in set(sigs)]
        for s in new:
            print(f"NEW: {s}")
        for s in gone:
            print(f"GONE (fixed or not hit this run): {s}")
        return 1 if new else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
