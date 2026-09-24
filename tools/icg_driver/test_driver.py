"""Probe rejection tests and actual GCC/extractor/emitter conditional-field gates."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools/icg_baseline"))
from tools.icg_driver import extract as driver  # noqa: E402
from tools.icg_schema import validate as ir  # noqa: E402

EXTRACTOR = None
COMPILER = None


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="icg driver ")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def compiler(
        self, version="8.5.0", *, macro_version=None, clang=False, failure=False
    ):
        path = self.work / "selected g++"
        path.write_text(
            f"#!{sys.executable}\n"
            "import sys\n"
            f"version = {version!r}\n"
            f"parts = {(macro_version or version).split('.')!r}\n"
            f"if {failure!r}:\n    sys.stderr.write('compiler unavailable'); sys.exit(1)\n"
            "args = sys.argv[1:]\n"
            "if '-dumpfullversion' in args: print(version)\n"
            "elif '-dumpmachine' in args: print('x86_64-linux-gnu')\n"
            "elif '--version' in args: print('test GCC ' + version)\n"
            "else:\n"
            "    mode = next((a[5:] for a in reversed(args) if a.startswith('-std=')), 'gnu++14')\n"
            "    print('#define __cplusplus ' + ('201703L' if mode.endswith('17') else '201402L'))\n"
            "    if not mode.startswith('gnu'): print('#define __STRICT_ANSI__ 1')\n"
            "    for name, value in zip(('__GNUC__', '__GNUC_MINOR__', '__GNUC_PATCHLEVEL__'), parts): print('#define ' + name + ' ' + value)\n"
            f"    if {clang!r}: print('#define __clang__ 1')\n"
        )
        path.chmod(0o755)
        return path

    def test_old_default_is_rejected_instead_of_silently_upgraded(self):
        with self.assertRaisesRegex(driver.DriverError, "Effective GCC mode"):
            driver.probe(self.compiler(), [])

    def test_explicit_dialects_and_selected_executable_identity(self):
        compiler = self.compiler()
        for dialect in ("c++17", "gnu++17"):
            profile, _ = driver.probe(compiler, ["-std=" + dialect])
            self.assertEqual(profile["executable"], str(compiler))
            self.assertEqual(profile["version"], "8.5.0")
            self.assertEqual(profile["language_standard"], dialect)
            self.assertEqual(profile["dialect_source"], "explicit")
            self.assertEqual(
                profile["executable_digest"],
                hashlib.sha256(compiler.read_bytes()).hexdigest(),
            )
            self.assertEqual(
                profile["normalized_arguments"],
                [
                    "--target=x86_64-linux-gnu",
                    "-std=" + dialect,
                    "-fgnuc-version=8.5.0",
                ],
            )

    def test_unsupported_flags_and_macro_overrides_fail_before_compiler_execution(self):
        for flags in (
            ["-I", "-DSECRET=1"],
            ["-std=gnu++14"],
            ["-std=c++20"],
            ["@response"],
            ["-fplugin=evil.so"],
            ["-Xclang", "evil"],
            ["-fgnuc-version=13.0.0"],
            ["-D__GNUC__=8"],
            ["-U", "__STRICT_ANSI__"],
            ["-Wp,-include,evil"],
            ["--target=aarch64-linux-gnu"],
            ["-o", "output"],
        ):
            with (
                self.subTest(flags=flags),
                self.assertRaises(driver.DriverError) as context,
            ):
                driver.probe(self.work / "nonexistent", flags)
            self.assertNotEqual(context.exception.code, "ICG_COMPILER_EXECUTABLE")

    def test_invalid_compiler_observations_fail_closed(self):
        for options, code in (
            ({"version": "7.5.0"}, "ICG_COMPILER_VERSION"),
            ({"version": "8.5"}, "ICG_COMPILER_VERSION"),
            ({"version": "8.5.0", "macro_version": "4.2.1"}, "ICG_COMPILER_MACROS"),
            ({"clang": True}, "ICG_COMPILER_FAMILY"),
            ({"failure": True}, "ICG_COMPILER_PROBE"),
        ):
            with (
                self.subTest(options=options),
                self.assertRaises(driver.DriverError) as context,
            ):
                driver.probe(self.compiler(**options), ["-std=c++17"])
            self.assertEqual(context.exception.code, code)

    def test_cli_probe_failure_has_json_diagnostics_and_no_facts(self):
        result = subprocess.run(
            [
                sys.executable,
                str(Path(driver.__file__)),
                "--extractor",
                "not-run",
                "--compiler",
                str(self.compiler(failure=True)),
                "model.hh",
                "--",
                "-std=c++17",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            json.loads(result.stderr)["diagnostics"][0]["code"], "ICG_COMPILER_PROBE"
        )


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        if EXTRACTOR is None or COMPILER is None:
            self.skipTest("requires --extractor and a GCC --compiler")
        self.temp = tempfile.TemporaryDirectory(prefix="icg-compiler-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.header = self.work / "model.hh"
        self.header.write_text(
            "struct Model { double x; unsigned char y;\n"
            "#if __GNUC__ >= 8\nunsigned char hidden;\n#endif\n"
            "#ifndef __STRICT_ANSI__\nunsigned char extension;\n#endif\n};\n"
        )
        self.env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("TRICK_")
            and k not in ("CPATH", "CPLUS_INCLUDE_PATH", "C_INCLUDE_PATH")
        }

    def extract(self, flags):
        facts, report, status = driver.extract(
            EXTRACTOR, COMPILER, self.header, flags, source_root=self.work, env=self.env
        )
        self.assertEqual(status, 0, report)
        self.assertEqual(facts["diagnostics"], report["diagnostics"])
        expected = facts["provenance"].pop("input_digest")
        self.assertEqual(
            expected,
            hashlib.sha256(
                json.dumps(
                    facts, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode()
            ).hexdigest(),
        )
        facts["provenance"]["input_digest"] = expected
        return facts

    def native_metadata(self, facts, dialect, fields, label, *, flags=()):
        from tools.icg_baseline import native
        from tools.icg_emit import emit
        from tools.icg_policy import resolve

        request = resolve.request_for(facts)
        source = emit.render(facts, request, resolve.resolve(facts, request))
        output = self.work / label
        output.mkdir()
        candidate = output / "candidate.cpp"
        candidate.write_text(source)
        # The negative control deliberately omits tail-padding fields. All emitted
        # layout/type assertions still compile; only explicit field-list evidence
        # distinguishes it from the correctly adapted metadata.
        check = output / "probe.cpp"
        check.write_text(
            '#include "candidate.cpp"\n#include <cstring>\n#include <cstdio>\nint main() {\n'
            + "\n".join(
                f'if (std::strcmp(attrModel[{i}].name, "{name}")) return 1;'
                for i, name in enumerate(fields)
            )
            + f'\nif (attrModel[{len(fields)}].name[0]) return 2;\nstd::puts("{{}}");\n}}\n'
        )
        native.execute(
            [check, ROOT / "trick_source/sim_services/UnitsMap/UnitsMap.cpp"],
            output,
            COMPILER,
            compile_flags=("-std=" + dialect, *flags),
        )

    def test_conditional_tail_fields_survive_extraction_and_metadata(self):
        default = subprocess.run(
            [str(EXTRACTOR), "--source-root", str(self.work), str(self.header), "--"],
            text=True,
            capture_output=True,
            env=self.env,
            check=True,
        )
        default = json.loads(default.stdout)
        original = next(n for n in default["declarations"] if n["kind"] == "record")
        self.native_metadata(default, "c++17", ["x", "y"], "unadapted")
        for dialect in ("c++17", "gnu++17"):
            facts = self.extract(["-std=" + dialect])
            record = next(n for n in facts["declarations"] if n["kind"] == "record")
            self.assertEqual(
                (record["size_bits"], record["alignment_bits"]),
                (original["size_bits"], original["alignment_bits"]),
            )
            fields = ["x", "y", "hidden"] + (
                ["extension"] if dialect == "gnu++17" else []
            )
            self.assertEqual(
                {n["name"] for n in facts["declarations"] if n["kind"] == "field"},
                set(fields),
            )
            self.native_metadata(facts, dialect, fields, dialect.replace("+", "p"))

    def test_real_default_dialect_is_preserved_or_rejected(self):
        actual = subprocess.check_output(
            [str(COMPILER), "-dM", "-E", "-x", "c++", "-"], input="", text=True
        )
        if "#define __cplusplus 201703L\n" not in actual:
            with self.assertRaises(driver.DriverError) as context:
                self.extract([])
            self.assertEqual(context.exception.code, "ICG_COMPILER_DIALECT")
        else:
            facts = self.extract([])
            self.assertEqual(
                facts["provenance"]["build_compiler"]["dialect_source"],
                "compiler-default",
            )
            self.assertEqual(
                facts["provenance"]["language_standard"],
                "c++17" if "#define __STRICT_ANSI__ " in actual else "gnu++17",
            )

    def test_compiler_probe_matches_minor_and_patch_conditionals(self):
        version = subprocess.check_output(
            [str(COMPILER), "-dumpfullversion", "-dumpversion"], text=True
        ).strip()
        major, minor, patch = version.split(".")
        self.header.write_text(
            f"#if __GNUC__ != {major} || __GNUC_MINOR__ != {minor} || __GNUC_PATCHLEVEL__ != {patch}\n#error compiler mismatch\n#endif\nstruct Model {{ int x; }};\n"
        )
        facts = self.extract(["-std=c++17"])
        self.assertEqual(facts["provenance"]["gcc_compatibility_version"], version)
        self.assertEqual(facts, self.extract(["-std=c++17"]))

    def test_inconsistent_profile_is_rejected(self):
        facts = self.extract(["-std=c++17"])
        schema = json.loads(driver.SCHEMA.read_text())
        for field, value in (
            ("version", "99.0.0"),
            ("language_standard", "gnu++17"),
            ("normalized_arguments", []),
            ("arguments", ["-DLOST_FLAG=1"]),
            ("dialect_source", "compiler-default"),
            ("probe_arguments", [[], [], [], [], []]),
        ):
            changed = copy.deepcopy(facts)
            changed["provenance"]["build_compiler"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                ir.validate(schema, changed)

    def test_failed_parse_never_publishes_compiler_profile_or_partial_facts(self):
        self.header.write_text("#error stop\nstruct Model { int x; };\n")
        facts, report, status = driver.extract(
            EXTRACTOR,
            COMPILER,
            self.header,
            ["-std=c++17"],
            source_root=self.work,
            env=self.env,
        )
        self.assertIsNone(facts)
        self.assertNotEqual(status, 0)
        self.assertTrue(any(d["severity"] == "error" for d in report["diagnostics"]))

    def test_forced_include_cannot_masquerade_as_a_different_compiler_or_dialect(self):
        config = self.work / "config.hh"
        for macro in (
            "__GNUC__",
            "__GNUC_MINOR__",
            "__GNUC_PATCHLEVEL__",
            "__cplusplus",
            "__STRICT_ANSI__",
        ):
            config.write_text(f"#undef {macro}\n#define {macro} 999\n")
            with (
                self.subTest(macro=macro),
                self.assertRaises(driver.DriverError) as context,
            ):
                self.extract(["-std=c++17", "-include", str(config)])
            self.assertEqual(context.exception.code, "ICG_COMPILER_MACROS")

    def test_flags_reach_both_frontends_and_unused_flags_change_evidence_only(self):
        include = self.work / "include space"
        include.mkdir()
        (include / "config.hh").write_text("#define INCLUDED 1\n")
        self.header.write_text(
            "#include <config.hh>\n#if !defined(SELECTED) || !INCLUDED\n#error flag lost\n#endif\nstruct Model { unsigned int x; };\n"
        )
        flags = ["-std=gnu++17", "-I", str(include), "-D", "SELECTED"]
        first = self.extract(flags)
        second = self.extract([*flags, "-DUNUSED=1"])
        self.assertEqual(
            first["provenance"]["graph_digest"], second["provenance"]["graph_digest"]
        )
        self.assertNotEqual(
            first["provenance"]["input_digest"], second["provenance"]["input_digest"]
        )
        self.assertEqual(first["provenance"]["build_compiler"]["arguments"], flags)
        self.native_metadata(first, "gnu++17", ["x"], "flags", flags=tuple(flags))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--extractor", type=Path)
    parser.add_argument("--compiler", type=Path)
    args, remaining = parser.parse_known_args()
    EXTRACTOR, COMPILER = args.extractor, args.compiler
    unittest.main(argv=[sys.argv[0], *remaining])
