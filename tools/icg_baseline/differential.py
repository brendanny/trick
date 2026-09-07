#!/usr/bin/env python3
"""Compare focused legacy ATTRIBUTES tables with validated extractor facts.

This deliberately recognizes only the scalar/bitfield rows in three captured
headers. It is an evidence bridge, not a general C++ parser or legacy backend.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import baseline as b

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/icg_schema"))
import validate as ir  # noqa: E402

REFERENCE = Path(__file__).resolve().parent / "legacy/reference"
EXCLUSIONS = {
    "anonymous-enum": {},
    "deleted-constructor": {},
    "embedded": {
        "IgnoreType1": "ICG_IGNORE_TYPES",
        "IgnoreType2": "ICG_IGNORE_TYPES",
        "TopClass::PrivateEmbed": "private nested record",
    },
}
TABLE = re.compile(r"^ATTRIBUTES attr(\w+)\[\] = \{\n(.*?)\} \};", re.M | re.S)
ROW = re.compile(
    r'\{"([^"\n]*)", "([^"\n]*)", "([^"\n]*)", "", "",\s*"[^"\n]*",\s*'
    r"15,(TRICK_\w+), (sizeof\([\w ]+\)|\d+), 0, 0, Language_CPP, 0,\s*"
    r"(\d+), NULL, 0, \{\{(\d+), (\d+)\},"
)
KINDS = {
    "int": "TRICK_INTEGER",
    "unsigned int": "TRICK_UNSIGNED_INTEGER",
    "double": "TRICK_DOUBLE",
}


def tables(text: str) -> dict:
    result = {}
    for match in TABLE.finditer(text):
        symbol, body = match.groups()
        rows = ROW.findall(body)
        if not rows or len(rows) != body.count('{"') or rows[-1][:2] != ("", ""):
            raise ValueError(f"{symbol}: unsupported legacy ATTRIBUTES row shape")
        if symbol in result:
            raise ValueError(f"duplicate legacy table: {symbol}")
        entries = []
        for name, spelling, units, kind, size, offset, width, shift in rows[:-1]:
            if not name:
                raise ValueError(f"{symbol}: premature sentinel")
            entries.append(
                dict(
                    name=name,
                    spelling=spelling,
                    units=units,
                    kind=kind,
                    size=size,
                    offset=int(offset),
                    width=int(width),
                    shift=int(shift),
                )
            )
        result[symbol] = entries
    if len(result) != text.count("ATTRIBUTES attr") or not result:
        raise ValueError("missing or unrecognized legacy ATTRIBUTES table")
    return result


def compare(document: dict, legacy: str, case_id: str) -> dict:
    declarations = {node["id"]: node for node in document["declarations"]}
    types = {node["id"]: node for node in document["types"]}
    records = {
        node["qualified_name"].replace("::", "__"): node
        for node in declarations.values()
        if node["kind"] == "record"
    }
    if len(records) != sum(node["kind"] == "record" for node in declarations.values()):
        raise ValueError("ambiguous legacy record name")
    actual = tables(legacy)
    absent = {
        node["qualified_name"] for key, node in records.items() if key not in actual
    }
    if absent != set(EXCLUSIONS[case_id]) or set(actual) - records.keys():
        raise ValueError(f"{case_id}: changed record tables or policy exclusions")
    report = {"records": {}, "policy_exclusions": EXCLUSIONS[case_id]}
    for symbol, rows in actual.items():
        record = records[symbol]
        fields = [declarations[identifier] for identifier in record["field_ids"]]
        if [row["name"] for row in rows] != [field["name"] for field in fields]:
            raise ValueError(f"{symbol}: field names/order differ")
        compared = []
        for row, field in zip(rows, fields, strict=True):
            type_node = types[field["type_id"]]
            if (
                type_node["kind"] != "builtin"
                or type_node["spelling"] != row["spelling"]
            ):
                raise ValueError(f"{symbol}::{row['name']}: field type differs")
            expected_kind = (
                "TRICK_UNSIGNED_BITFIELD"
                if field["bitfield"]
                else KINDS[row["spelling"]]
            )
            offset = row["offset"] * 8
            if field["bitfield"]:
                # Legacy bit starts count from the most significant bit of the
                # storage unit; facts use offsets from the start of the record.
                offset += int(row["size"]) * 8 - row["shift"] - row["width"]
                if int(field["bit_width"]) != row["width"]:
                    raise ValueError(f"{symbol}::{row['name']}: bitfield width differs")
            elif (
                row["width"]
                or row["shift"]
                or row["size"] != f"sizeof({row['spelling']})"
            ):
                raise ValueError(f"{symbol}::{row['name']}: unexpected scalar storage")
            if expected_kind != row["kind"] or offset != int(field["offset_bits"]):
                raise ValueError(f"{symbol}::{row['name']}: field kind/offset differs")
            compared.append({
                "name": row["name"],
                "type": row["spelling"],
                "offset_bits": offset,
                "bit_width": row["width"] if field["bitfield"] else None,
                "legacy_units": row["units"],
                "source_annotations": [
                    item["payload"] for item in field["annotations"]
                ],
            })
        report["records"][record["qualified_name"]] = compared
    report["not_compared"] = [
        "unit/annotation policy",
        "enum tables",
        "lifecycle wrappers",
        "generated execution",
    ]
    return report


def capture(extractor: Path, output: Path) -> dict:
    schema = json.loads(
        (
            ROOT / "trick_source/codegen/TrickCodeGen/ir/extracted-facts.schema.json"
        ).read_text()
    )
    provenance = json.loads((REFERENCE / "provenance.json").read_text())
    corpus = json.loads((REFERENCE.parent / "corpus.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    reports = {}
    for case in corpus["cases"]:
        if case["id"] not in EXCLUSIONS:
            continue
        header = ROOT / case["header"]
        source_digest = b.digest(header.read_bytes())
        if source_digest != provenance["source_sha256"][case["header"]]:
            raise ValueError(f"{case['id']}: source differs from legacy reference")
        result = subprocess.run(
            [
                str(extractor),
                "--source-root",
                str(ROOT),
                "--diagnostics-format=json",
                str(header),
                "--",
            ],
            capture_output=True,
            check=False,
        )
        (output / f"{case['id']}.facts.json").write_bytes(result.stdout)
        (output / f"{case['id']}.diagnostics.json").write_bytes(result.stderr)
        result.check_returncode()
        document = json.loads(result.stdout)
        ir.validate(schema, document)
        inputs = [
            node
            for node in document["files"]
            if node["path"]["root"] == "source"
            and node["path"]["portable"] == case["header"]
        ]
        if len(inputs) != 1 or inputs[0]["digest"] != source_digest:
            raise ValueError(
                "extracted source differs from the legacy input fingerprint"
            )
        if document["provenance"]["target_triple"] != "x86_64-pc-linux-gnu":
            raise ValueError("this legacy reference requires the x86_64 Linux target")
        snapshot = REFERENCE / case["id"] / "cold.json"
        artifacts = json.loads(snapshot.read_text())["artifacts"]
        metadata = [
            item for item in artifacts.values() if item["group"] == "legacy-metadata"
        ]
        if len(metadata) != 1:
            raise ValueError("expected one digest-verified legacy metadata artifact")
        report = compare(document, b.artifact_text(snapshot, metadata[0]), case["id"])
        report.update(
            source_sha256=source_digest,
            legacy_sha256=metadata[0]["sha256"],
            graph_digest=document["provenance"]["graph_digest"],
            frontend_version=document["provenance"]["frontend_version"],
        )
        reports[case["id"]] = report
    if set(reports) != set(EXCLUSIONS):
        raise ValueError("incomplete differential corpus")
    (output / "comparison.json").write_text(
        json.dumps(reports, indent=2, sort_keys=True) + "\n"
    )
    return reports


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extractor", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    capture(args.extractor.resolve(strict=True), args.output)
