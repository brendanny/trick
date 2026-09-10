"""Compile actual legacy metadata and compare it with facts and native layout.

This probe supports the audited scalar/array/unsigned-bitfield/enum fixtures.
It links the real Trick UnitsMap implementation, without stubs.
"""

from __future__ import annotations

import json
import math
import os
import re
import shlex
import subprocess
from pathlib import Path

import baseline as b

ROOT = Path(__file__).resolve().parents[2]
HELPER = Path(__file__).with_name("native_probe.hh")
KINDS = {
    "int": "TRICK_INTEGER",
    "unsigned int": "TRICK_UNSIGNED_INTEGER",
    "double": "TRICK_DOUBLE",
}


def identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", value, re.ASCII):
        raise ValueError(f"unsupported native probe identifier: {value!r}")
    return value


def record_symbol(name: str, report: dict) -> str:
    binding = report.get("record_bindings", {}).get(name)
    return identifier(binding["symbol"] if binding else name).replace("::", "__")


def source(document: dict, report: dict, source_name: str = "legacy.cpp") -> str:
    declarations = {
        node["qualified_name"]: node
        for node in document["declarations"]
        if node["kind"] in ("record", "enum")
    }
    nodes = {n["id"]: n for n in document["declarations"]}
    calls, aliases = [], []
    for name, fields in report["records"].items():
        binding = report.get("record_bindings", {}).get(name)
        cpp_name = (
            identifier(name) if binding is None else f"ProbeTemplate{len(aliases)}"
        )
        if binding:
            if not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_ <>,\[\]]*", binding["cpp_type"], re.ASCII
            ):
                raise ValueError("unsupported native template spelling")
            aliases.append(f"using {cpp_name} = ::{binding['cpp_type']};\n")
        symbol = record_symbol(name, report)
        record = declarations[name]
        unit_containers = []
        while record is not None:
            if record["kind"] == "record":
                unit_containers.insert(0, record["name"])
            record = nodes.get(record.get("semantic_parent_id"))
        unit_prefix = "__".join(unit_containers)
        if binding:
            unit_prefix = binding["units_prefix"]
        native_fields = []
        for field in fields:
            member = identifier(field["name"])
            type_name = f"decltype({cpp_name}::{member})"
            if field["bit_width"] is None:
                native_fields.append(
                    f'probe::member<{type_name}>("{member}", offsetof({cpp_name}, {member}) * CHAR_BIT)'
                )
            else:
                if field["type"] != "unsigned int":
                    raise ValueError("native bitfield probe supports unsigned int only")
                native_fields.append(
                    f'probe::bitfield<{cpp_name}, {type_name}>("{member}", '
                    f"[]({cpp_name}& value, {type_name} bits) {{ value.{member} = bits; }})"
                )
        calls.append(
            f"init_attr{symbol}_c_intf();\n"
            f"probe::record<{cpp_name}>({json.dumps(name)}, {json.dumps(unit_prefix)}, attr{symbol}, "
            f"io_src_sizeof_{symbol}(), {{{', '.join(native_fields)}}});"
        )
    enum_calls = []
    for name, rows in report["enums"].items():
        identifier(name)
        symbol = name.replace("::", "__")
        if any(not -(2**31) <= int(row["value"]) < 2**31 for row in rows):
            raise ValueError(
                "native enum probe requires values representable by ENUM_ATTR.int"
            )
        values = [
            identifier(name + "::" + item["name"])
            for item in declarations[name]["enumerators"]
        ]
        enum_calls.append(
            f'probe::enumeration<{name}>("{name}", enum{symbol}, '
            f"io_src_sizeof_{symbol}(), {{{', '.join(values)}}});"
        )
    separator = '\nstd::cout << ",";\n'
    return (
        f'#include "{source_name}"\n#include "native_probe.hh"\n'
        + "".join(aliases)
        + "void verify_metadata_linkage();\n"
        'int main() {\ntry {\nverify_metadata_linkage();\nstd::cout << "{\\"records\\":[";\n'
        + separator.join(calls)
        + '\nstd::cout << "],\\"enums\\":[";\n'
        + separator.join(enum_calls)
        + '\nstd::cout << "]}\\n";\nreturn 0;\n'
        '} catch (const std::exception& error) { std::cerr << error.what() << "\\n"; return 1; }\n}\n'
    )


def validate(document: dict, report: dict, observed: dict) -> None:
    declarations = {
        node["qualified_name"]: node
        for node in document["declarations"]
        if node["kind"] in ("record", "enum")
    }
    if set(observed) != {"records", "enums"}:
        raise ValueError("unexpected native observation sections")
    for group in ("records", "enums"):
        entries = observed[group]
        if [item["name"] for item in entries] != list(report[group]):
            raise ValueError(f"native {group} names/order differ")
        for item in entries:
            name = item["name"]
            node = declarations[name]
            for key, fact in (
                ("size_bytes", "size_bits"),
                ("legacy_size_bytes", "size_bits"),
                ("alignment_bytes", "alignment_bits"),
            ):
                if item[key] * 8 != int(node[fact]):
                    raise ValueError(f"{name}: native {key} differs from facts")
            if group == "enums":
                expected = [
                    dict(row, native_value=row["value"]) for row in report[group][name]
                ]
                if (
                    item["signed"] != node["underlying_signed"]
                    or item["rows"] != expected
                ):
                    raise ValueError(
                        f"{name}: compiled/native enum value, label, or signedness differs"
                    )
                continue
            fields = report[group][name]
            if len(item["fields"]) != len(fields) or len(item["native_fields"]) != len(
                fields
            ):
                raise ValueError(f"{name}: compiled/native field count differs")
            for field, row, native in zip(
                fields, item["fields"], item["native_fields"], strict=True
            ):
                label = f"{name}::{field['name']}"
                width = field["bit_width"] or 0
                dimensions = field.get("dimensions", [])
                total_size = row["size_bytes"] * math.prod(dimensions)
                if native != dict(
                    name=field["name"],
                    size_bytes=row["size_bytes"],
                    offset_bits=field["offset_bits"],
                    width=width,
                    dimensions=dimensions,
                    total_size_bytes=total_size,
                ):
                    raise ValueError(f"{label}: native field size/offset/width differs")
                if row["size_bytes"] <= 0 or row["offset_bytes"] < 0:
                    raise ValueError(f"{label}: invalid compiled field storage")
                if row["offset_bytes"] + total_size > item["size_bytes"]:
                    raise ValueError(f"{label}: field extends beyond native record")
                kind = "TRICK_UNSIGNED_BITFIELD" if width else KINDS[field["type"]]
                expected = dict(
                    name=field["name"],
                    type=field["type"],
                    kind=kind,
                    units=field["legacy_units"],
                    units_map_units=field["legacy_units"],
                    size_bytes=native["size_bytes"],
                    offset_bytes=row["offset_bytes"],
                    width=width,
                    shift=row["shift"],
                    io=field.get("legacy_io", 15),
                    mods=field.get("legacy_mods", 0),
                    description=field.get("legacy_description", ""),
                    dimensions=dimensions,
                )
                offset = row["offset_bytes"] * 8
                if width:
                    if row["shift"] < 0 or row["shift"] + width > row["size_bytes"] * 8:
                        raise ValueError(f"{label}: invalid compiled bitfield storage")
                    offset += row["size_bytes"] * 8 - row["shift"] - width
                elif row["shift"]:
                    raise ValueError(f"{label}: unexpected compiled scalar index")
                if row != expected or offset != field["offset_bits"]:
                    raise ValueError(f"{label}: compiled ATTRIBUTES differs")


def linkage_source(document: dict, report: dict) -> str:
    """Link public entry points from a separate translation unit, without output."""
    declarations = []
    calls = []
    for group, prefix, row_type in (
        ("records", "attr", "ATTRIBUTES"),
        ("enums", "enum", "ENUM_ATTR"),
    ):
        for name in report[group]:
            symbol = (
                record_symbol(name, report)
                if group == "records"
                else identifier(name).replace("::", "__")
            )
            declarations.append(
                f'extern "C" {{ extern {row_type} {prefix}{symbol}[]; size_t io_src_sizeof_{symbol}(); }}\n'
            )
            calls.append(
                f'    if (!{prefix}{symbol}[0].{"name" if group == "records" else "label"} || !io_src_sizeof_{symbol}()) throw std::runtime_error("metadata linkage/size");\n'
            )
            if group == "records":
                declarations.append(f'extern "C" void init_attr{symbol}_c_intf();\n')
                calls.extend([f"    init_attr{symbol}_c_intf();\n"] * 2)
    return (
        '#include "trick/attributes.h"\n#include <stdexcept>\n'
        + "".join(declarations)
        + "void verify_metadata_linkage() {\n"
        + "".join(calls)
        + "}\n"
    )


def capture(
    document: dict,
    legacy: str,
    report: dict,
    case: dict,
    output: Path,
    compiler: Path,
    *,
    source_name: str = "legacy.cpp",
    compile_flags: tuple[str, ...] = (),
) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result_path = output / "native.json"
    result_path.unlink(missing_ok=True)
    if any(ch in str(ROOT) for ch in ('"', "\\", "\n", "\r")):
        raise ValueError("repository path cannot be represented in a C++ include")
    materialized = legacy.replace("${TRICK_ROOT}", str(ROOT))
    if "${" in materialized:
        raise ValueError("unresolved normalization token in legacy source")
    if source_name not in ("legacy.cpp", "candidate.cpp"):
        raise ValueError("unsupported metadata source filename")
    (output / source_name).write_text(materialized)
    (output / "native_probe.hh").write_bytes(HELPER.read_bytes())
    (output / "probe.cpp").write_text(source(document, report, source_name))
    (output / "entry-points.cpp").write_text(linkage_source(document, report))
    sources = [
        output / "probe.cpp",
        output / "entry-points.cpp",
        ROOT / "trick_source/sim_services/UnitsMap/UnitsMap.cpp",
    ]
    if case["id"] == "anonymous-enum":
        sources.append(ROOT / "test/SIM_anon_enum/models/starter.cpp")
    evidence = execute(sources, output, compiler, compile_flags=compile_flags)
    validate(document, report, evidence["observations"])
    result_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return evidence


def execute(
    sources: list[Path],
    output: Path,
    compiler: Path,
    *,
    compile_flags: tuple[str, ...] = (),
    link_flags: tuple[str, ...] = (),
    runtime_environment: dict[str, str] | None = None,
) -> dict:
    """Compile/link/run an evidence probe, retaining argv, logs and dependencies.

    The caller validates observations before publishing its success report.
    """
    commands = []

    def run(
        arguments: list[str], label: str, timeout: int = 180
    ) -> subprocess.CompletedProcess:
        timed_out = False
        try:
            result = subprocess.run(
                arguments,
                cwd=output,
                capture_output=True,
                timeout=timeout,
                check=False,
                env={**os.environ, **runtime_environment}
                if label == "run" and runtime_environment
                else None,
            )
        except subprocess.TimeoutExpired as error:
            timed_out = True
            result = subprocess.CompletedProcess(
                arguments, None, error.stdout or b"", error.stderr or b""
            )
        (output / f"{label}.stdout").write_bytes(result.stdout)
        (output / f"{label}.stderr").write_bytes(result.stderr)
        commands.append(
            dict(
                argv=arguments,
                returncode=result.returncode,
                timed_out=timed_out,
                environment=runtime_environment or {} if label == "run" else {},
                stdout=f"{label}.stdout",
                stderr=f"{label}.stderr",
            )
        )
        (output / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        if timed_out:
            raise ValueError(f"native {label} timed out after {timeout}s")
        if result.returncode:
            raise ValueError(
                f"native {label} failed ({result.returncode}): {result.stderr.decode(errors='replace')}"
            )
        return result

    version = (
        run([str(compiler), "--version"], "compiler-version").stdout.decode().strip()
    )
    target = (
        run([str(compiler), "-dumpmachine"], "compiler-target").stdout.decode().strip()
    )
    objects = []
    dependencies = {Path(__file__), HELPER}
    for index, path in enumerate(sources):
        obj = output / f"{index}.o"
        dep = output / f"{index}.d"
        run(
            [
                str(compiler),
                "-std=c++17",
                "-Wall",
                "-Wextra",
                "-Werror",
                *compile_flags,
                "-I" + str(ROOT / "include"),
                "-MMD",
                "-MF",
                str(dep),
                "-c",
                str(path),
                "-o",
                str(obj),
            ],
            f"compile-{index}",
        )
        dependencies.update(
            output / name
            for name in shlex.split(
                dep.read_text().replace("\\\n", " ").split(":", 1)[1]
            )
        )
        objects.append(str(obj))
    executable = output / "probe"
    run([str(compiler), *objects, *link_flags, "-o", str(executable)], "link")
    result = run([str(executable)], "run", timeout=30)
    observed = json.loads(result.stdout)
    evidence = dict(
        compiler=str(compiler),
        compiler_version=version,
        compiler_target=target,
        executable_sha256=b.digest(executable.read_bytes()),
        observations=observed,
        input_sha256={
            str(path): b.digest(path.read_bytes()) for path in sorted(dependencies)
        },
        commands=commands,
    )
    return evidence
