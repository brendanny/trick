"""Exercise SDK inventory and resource copying without building the runtime."""

import argparse
import subprocess
import tempfile
from pathlib import Path


def validate(cmake):
    template = Path(__file__).resolve().parents[1] / "sdk/StageSDK.cmake.in"
    with tempfile.TemporaryDirectory(prefix="trick-stage-helpers-") as temporary:
        root = Path(temporary)
        source, build, sdk = root / "source", root / "build", root / "sdk"

        def write(path, content="fixture\n"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

        for script in (
            "trick-CP",
            "trick-config",
            "trick-gte",
            "trick-ify",
            "trick-killsim",
            "trick-units",
            "trick-version",
        ):
            write(source / "bin" / script)
        (source / "libexec").mkdir()
        (source / "trick_source").mkdir()
        write(source / "external-doc.txt", "external resource\n")
        link = source / "share/trick/trickops/README.md"
        link.parent.mkdir(parents=True)
        link.symlink_to("../../../external-doc.txt")
        # Exercise the configure-time install check on the same fixture tree.
        checker = template.parents[1] / "TrickSDKSourceLinks.cmake"
        check_script = root / "check-links.cmake"
        check_script.write_text(
            "cmake_minimum_required(VERSION 3.26)\n"
            f'include("{checker}")\n'
            f'trick_check_sdk_source_links("{source}")\n'
        )

        def check_links(success):
            result = subprocess.run(
                [cmake, "-P", str(check_script)],
                capture_output=True,
                text=True,
                check=False,
            )
            if (result.returncode == 0) != success:
                raise RuntimeError(
                    "Unexpected source-link check result: " + result.stderr
                )
            if not success and "Unhandled SDK source symlink" not in result.stderr:
                raise RuntimeError("Source-link check failed for another reason")

        check_links(False)  # The known path with an unexpected target is unsafe.
        link.unlink()
        doc = source / "docs/documentation/miscellaneous_trick_tools/TrickOps.md"
        write(doc, "external resource\n")
        link.symlink_to(
            "../../../docs/documentation/miscellaneous_trick_tools/TrickOps.md"
        )
        check_links(True)
        for name, target in (
            ("share/trick/new-link", "missing"),
            ("libexec/trick/new-link", str(doc)),
            ("include/link-dir", str(doc.parent)),
        ):
            unexpected = source / name
            unexpected.parent.mkdir(parents=True, exist_ok=True)
            unexpected.symlink_to(target)
            check_links(False)
            unexpected.unlink()
        check_links(True)
        special = source / "include/obsolete/nested/@NAME@.hh"
        write(special)
        retained = source / "include/retained/nested/header.hh"
        write(retained)
        for name in ("config_user.mk", "cmake-sdk.mk", "sdk.env"):
            write(build / "sdk-config" / name)
        write(build / "sdk-model-predefines.txt")
        write(build / "trick_source/sim_services/metadata/classes.resource")
        for module in ("sim_services", "swig_double", "swig_int", "swig_ref"):
            write(build / "python" / (module + ".py"))
        write(build / "icg", "#!/bin/sh\nexit 0\n")
        (build / "icg").chmod(0o755)
        text = template.read_text()
        for old, new in {
            "@PROJECT_SOURCE_DIR@": str(source),
            "@PROJECT_BINARY_DIR@": str(build),
            "@TRICK_SDK_ROOT@": str(sdk) + "/",
            "@TRICK_USE_ER7_UTILS@": "ON",
            "@sdk_stage_libraries@": "",
            "$<CONFIG>": "",
            "$<TARGET_FILE:trick-ICG>": str(build / "icg"),
        }.items():
            text = text.replace(old, new)
        stage = root / "stage.cmake"
        stage.write_text(text)

        def run():
            subprocess.run([cmake, "-P", str(stage)], check=True)

        run()
        manifest = build / "sdk-config/staged-files.txt"
        if "include/obsolete/nested/@NAME@.hh" not in manifest.read_text().splitlines():
            raise RuntimeError("Inventory interpreted a filename as a template")
        copied = sdk / "share/trick/trickops/README.md"
        if copied.is_symlink() or copied.read_text() != "external resource\n":
            raise RuntimeError("Source-relative resource link was not materialized")
        if not (sdk / "bin/trick-ICG").stat().st_mode & 0o111:
            raise RuntimeError("Staging lost executable permissions")
        write(sdk / "include/retained/.user-output")
        special.unlink()
        retained.unlink()
        run()
        if (sdk / "include/obsolete").exists() or (
            sdk / "include/retained/nested"
        ).exists():
            raise RuntimeError("Obsolete empty directories were retained")
        if not (sdk / "include/retained/.user-output").is_file():
            raise RuntimeError("Directory pruning removed a user output")
    print(
        "SDK helper checks passed: literal paths, resource links and empty directories"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cmake", default="cmake")
    validate(parser.parse_args().cmake)
