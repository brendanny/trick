"""Exercise the real Linux Make-built ICG independently of the CMake frontend.

Stage only its source prerequisites and a minimal configure-equivalent Make
configuration. All objects, executable and test outputs stay in --work.
"""

import argparse
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--llvm-root", type=Path, required=True)
    parser.add_argument("--udunits-include", type=Path, required=True)
    parser.add_argument("--udunits-library", type=Path, required=True)
    parser.add_argument("--cxx", default="g++")
    parser.add_argument("--cmake", default="cmake")
    args = parser.parse_args()
    source = args.source.resolve()
    work = args.work.resolve()
    llvm = args.llvm_root.resolve()
    cxx = shutil.which(args.cxx)
    if not cxx:
        raise RuntimeError("C++ compiler not found: " + args.cxx)
    clang_libraries = sorted((llvm / "lib").glob("libclang-cpp.so*"))
    if not clang_libraries:
        raise RuntimeError("LLVM prefix must contain the Linux libclang-cpp library")
    gcc_version = subprocess.check_output([cxx, "-dumpfullversion"], text=True).strip()
    # Refuse existing work directories rather than risk overwriting source links.
    work.mkdir(parents=True, exist_ok=False)
    for directory in ("bin", "libexec", "include"):
        (work / directory).symlink_to(source / directory, target_is_directory=True)
    makefiles = work / "share/trick/makefiles"
    makefiles.mkdir(parents=True)
    shutil.copyfile(
        source / "share/trick/makefiles/Makefile.common", makefiles / "Makefile.common"
    )
    shutil.copyfile(
        source / "share/trick/trick_ver.txt", work / "share/trick/trick_ver.txt"
    )
    for directory in (
        "trick_source/codegen/Interface_Code_Gen",
        "trick_source/sim_services/UdUnits",
    ):
        target = work / directory
        target.mkdir(parents=True)
        for path in (source / directory).iterdir():
            if path.suffix in (".cpp", ".hh", ".h") or path.name == "makefile":
                shutil.copyfile(path, target / path.name)
    udunits = args.udunits_library.resolve()
    (makefiles / "config_Linux.mk").write_text(
        "CONFIG_MK = 1\n"
        f"LLVM_HOME = {llvm}\n"
        f"TRICK_CXX = {cxx}\n"
        f"TRICK_GCC_VERSION = {gcc_version}\n"
        f"UDUNITS_INCLUDES = -I{args.udunits_include.resolve()}\n"
        f"UDUNITS_LDFLAGS = {udunits} -Wl,-rpath,{udunits.parent}\n"
        f"ICG_CLANGLIBS = {clang_libraries[0]}\n"
    )
    icg = work / "trick-ICG"
    subprocess.run(
        [
            "make",
            "-C",
            str(work / "trick_source/codegen/Interface_Code_Gen"),
            "-j3",
            "TRICK_HOST_TYPE=Linux",
            "TRICK_HOST_CPU=Linux_x86_64",
            f"CXX={cxx}",
            f"ICG={icg}",
            f"OBJ_DIR={work / 'objects'}",
        ],
        check=True,
    )
    subprocess.run(
        [
            args.cmake,
            f"-DICG={icg}",
            f"-DTRICK_SOURCE={source}",
            f"-DTEST_ROOT={work / 'system-errors'}",
            "-P",
            str(source / "cmake/tests/ICGSystemErrors.cmake"),
        ],
        check=True,
    )
    print(
        "Make-built ICG reports system-header errors on stderr and invalidates success records"
    )


if __name__ == "__main__":
    main()
