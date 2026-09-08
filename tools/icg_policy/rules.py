"""Characterized legacy rules; unsupported grammar is an error, never a guess."""

from __future__ import annotations

import re
from pathlib import Path


class PolicyError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


PATH_SETTINGS = (
    "TRICK_EXCLUDE",
    "TRICK_ICG_EXCLUDE",
    "TRICK_SYSTEM_ICG_EXCLUDE",
    "TRICK_EXT_LIB_DIRS",
    "TRICK_EXT_LIB_DIRS_OVERRIDES",
    "TRICK_ICG_NOCOMMENT",
)
IO = {
    "o": 1,
    "*o": 1,
    "i": 2,
    "*i": 2,
    "oi": 3,
    "*oi": 3,
    "io": 3,
    "*io": 3,
    "**": 0,
    "--": 4,
}
# This is deliberately a bounded vocabulary, not a substitute for UDUNITS.
UNITS = {u: u for u in ("1", "m", "cm", "km", "s", "rad", "degree")}
UNITS.update({"--": "1", "r": "rad", "d": "degree", "M": "m", "one": "1"})


def settings(facts: dict) -> dict:
    provenance = facts["provenance"]
    env = provenance["policy_environment"]
    if env.get("TRICK_ICG_COMPAT15", "").strip():
        raise PolicyError(
            "ICG_POLICY_SETTINGS", "compat15 is outside numeric-offset policy"
        )
    paths = []
    for key in PATH_SETTINGS:
        for item in env.get(key, "").split(":"):
            if not item.strip():
                continue
            path = Path(item.strip())
            if not path.is_absolute():
                path = Path(provenance["working_directory"]) / path
            try:
                resolved = path.resolve(strict=True)
            except (OSError, RuntimeError):
                # Legacy warns and ignores. Keep the warning and the missing entry.
                paths.append(
                    dict(
                        setting=key, spelled=item.strip(), resolved=None, kind="missing"
                    )
                )
                continue
            if not resolved.is_file() and not resolved.is_dir():
                raise PolicyError(
                    "ICG_POLICY_SETTINGS", f"non-regular policy path: {item}"
                )
            paths.append(
                dict(
                    setting=key,
                    spelled=item.strip(),
                    resolved=str(resolved),
                    kind="directory" if resolved.is_dir() else "file",
                )
            )
    return dict(
        environment=dict(env),
        paths=paths,
        ignore_types=sorted({
            item.strip()
            for item in env.get("TRICK_ICG_IGNORE_TYPES", "").split(";")
            if item.strip()
        }),
    )


def matching(settings: dict, key: str, path: str) -> list[int]:
    # HeaderSearchDirs appends '/' to directories, but file entries use raw
    # prefix matching. Preserve the surprising file.hh -> file.hh.backup case.
    return [
        i
        for i, p in enumerate(settings["paths"])
        if p["setting"] == key
        and p["resolved"] is not None
        and path.startswith(p["resolved"] + ("/" if p["kind"] == "directory" else ""))
    ]


def line_comments(file: dict) -> dict[int, int]:
    # CommentSaver::HandleComment overwrites the map entry for each start line.
    return {c["source"]["spelling"]["line"]: i for i, c in enumerate(file["comments"])}


def file_policy(file: dict, effective: dict) -> dict:
    lines = line_comments(file)
    header = next(
        (
            lines[line]
            for line in sorted(lines)
            if (
                "PURPOSE" in file["comments"][lines[line]]["payload"].upper()
                or re.search(
                    r"[@\\]trick_parse", file["comments"][lines[line]]["payload"]
                )
            )
        ),
        None,
    )
    text = "" if header is None else file["comments"][header]["payload"]
    excluded, no_comment, rule = (
        False,
        header is None,
        "NO_TRICK_HEADER" if header is None else "TRICK_HEADER",
    )
    if "trick_parse" in text:
        tail = text.split("trick_parse", 1)[1]
        if "}" not in tail:
            raise PolicyError(
                "ICG_POLICY_DIRECTIVE",
                "unterminated trick_parse (legacy leaves defaults)",
            )
        argument = tail.split("}", 1)[0]
        mode = next(
            (
                m
                for m in ("everything", "attributes", "dependencies_only")
                if m in argument
            ),
            None,
        )
        if mode is None:
            raise PolicyError(
                "ICG_POLICY_DIRECTIVE", "legacy rejects unknown trick_parse argument"
            )
        excluded, no_comment, rule = (
            mode == "dependencies_only",
            mode == "attributes",
            "TRICK_PARSE_" + mode.upper(),
        )
    elif re.search(r"ICG:", text, re.I):
        tail = re.split(r"ICG:", text, maxsplit=1, flags=re.I)[1]
        if ")" not in tail:
            raise PolicyError("ICG_POLICY_DIRECTIVE", "unterminated ICG directive")
        value = tail.split(")", 1)[0].upper()
        if value.endswith("NOCOMMENT"):
            no_comment, rule = True, "ICG_NOCOMMENT"
        elif value.endswith("NO"):
            excluded, no_comment, rule = True, True, "ICG_NO"
    ignored = set()
    match = re.search(r"ICG[ _]IGNORE[ _]TYPES?:", text, re.I)
    if match:
        tail = text[match.end() :]
        end = re.search(r"\)\s*\)", tail)
        if end is None:
            raise PolicyError("ICG_POLICY_DIRECTIVE", "unterminated ICG_IGNORE_TYPES")
        ignored.update(re.sub(r"[()\n]", " ", tail[: end.start()]).split(" "))
        ignored.discard("")
    for keyword in re.finditer(r"trick_exclude_typename", text):
        match = re.match(r"\s*\{\s*(\S+?)\s*\}", text[keyword.end() :])
        if match is None:
            raise PolicyError(
                "ICG_POLICY_DIRECTIVE", "malformed trick_exclude_typename"
            )
        ignored.add(match[1])
    path = file["path"]["real"]
    exclusions = sum((matching(effective, key, path) for key in PATH_SETTINGS[:3]), [])
    external = matching(effective, "TRICK_EXT_LIB_DIRS", path)
    overrides = matching(effective, "TRICK_EXT_LIB_DIRS_OVERRIDES", path)
    if exclusions:
        excluded, rule = True, "ENV_EXCLUDE"
    elif external and not overrides:
        excluded, rule = True, "ENV_EXTERNAL_LIBRARY"
    nocomment = matching(effective, "TRICK_ICG_NOCOMMENT", path)
    return dict(
        file_id=file["id"],
        excluded=excluded,
        rule=rule,
        header_comment=header,
        no_comment=no_comment or bool(nocomment),
        ignore_types=sorted(ignored),
        path_evidence=sorted(set(exclusions + external + overrides + nocomment)),
        no_comment_rule="ENV_NOCOMMENT" if nocomment else rule,
    )


def annotation(payload: str | None) -> dict:
    if payload is None:
        return dict(units="1", io=15, rules=["DEFAULT_UNITS_IO"], diagnostics=[])
    text = re.sub(r"^(//|/\*)", "", payload, count=1)
    text = re.sub(r"^([*!]<)?\s*", "", text, count=1)
    text = re.sub(r"^(\\[a-zA-Z0-9]+)?\s*", "", text, count=1)
    rules, diagnostics = [], []
    values = {}
    for key in ("trick_chkpnt_io", "cio", "trick_io", "io"):
        pattern = r"(?<![\w*])@?" + key + r"[({]([^)}]+)[)}]"
        matches = list(re.finditer(pattern, text))
        if len(matches) > 1:
            raise PolicyError(
                "ICG_POLICY_ANNOTATION",
                f"repeated {key} is outside characterized grammar",
            )
        if not matches:
            continue
        match = matches[0]
        value = match[1]
        if value not in IO:
            # std::map::operator[] inserts zero for unknown, whitespace included.
            diagnostics.append("LEGACY_UNKNOWN_IO_ZERO")
        values["checkpoint" if key in ("trick_chkpnt_io", "cio") else "io"] = IO.get(
            value, 0
        )
        rules.append(key.upper())
        text = text[: match.start()] + text[match.end() :]
    units = None
    match = re.search(r"@?trick_units([({])", text)
    if match:
        closing = ")" if match[1] == "(" else "}"
        end = text.find(closing, match.end())
        if end < 0:
            raise PolicyError(
                "ICG_POLICY_ANNOTATION", "unmatched trick_units delimiter"
            )
        units = text[match.end() : end]
        text = text[: match.start()] + text[end + 1 :]
        rules.append("TRICK_UNITS")
    if re.search(r"trick_(?:units|io|chkpnt_io)|(?:io|cio)\s*[({]", text):
        raise PolicyError(
            "ICG_POLICY_ANNOTATION", "malformed or unsupported explicit annotation"
        )
    if "io" not in values:
        match = re.match(r"\s*(\*io|\*oi|\*i|\*o|\*\*)", text)
        if match:
            values["io"] = IO[match[1]]
            text = text[match.end() :]
            rules.append("LEGACY_PREFIX_IO")
    if units is None:
        match = re.match(r"\s*\(([^)]*)\)", text)
        if match and match[1]:
            units = match[1]
        else:
            match = re.match(r"\s*([^\s)]*)", text)
            if match and match[1]:
                units = match[1]
        if units is not None:
            rules.append("LEGACY_PREFIX_UNITS")
    io = values.get("io", 15)
    # Legacy validates units before processing checkpoint permissions; this
    # means a primary ** leaves arbitrary units text uninterpreted.
    if units is None:
        units = "1"
    elif io != 0:
        units = re.sub(r"\s", "", units)
        if units == "*/":
            diagnostics.append("LEGACY_INVALID_UNITS_DEFAULT")
            units = "1"
        if units not in UNITS:
            raise PolicyError(
                "ICG_POLICY_UNITS", f"units outside the bounded vocabulary: {units!r}"
            )
        mapped = UNITS[units]
        if mapped != units and units != "--":
            diagnostics.append("LEGACY_UNIT_ALIAS")
        units = mapped
    if io == 4:
        io = 3
        diagnostics.append("LEGACY_DASHDASH_IO")
    if "checkpoint" in values:
        io = (values["checkpoint"] << 2) + (io & 3)
        if io > 15:
            raise PolicyError(
                "ICG_POLICY_ANNOTATION",
                "legacy checkpoint -- exceeds the four-bit contract",
            )
    elif "io" in values:
        io |= io << 2
    return dict(
        units=units, io=io, rules=rules or ["DEFAULT_UNITS_IO"], diagnostics=diagnostics
    )
