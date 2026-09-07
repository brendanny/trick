"""Package validated static bytes and gate manual promotion; never build or deploy.

The promotion path uses only Python's standard library. Downloaded files are
data, never Python modules or executable workflow helpers.
"""

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import tarfile
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen

from common import ROOT, is_helper

SHA1 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
MAX_BYTES = 512 * 1024 * 1024
LEGACY_GATES = (
    "rendered_heading_ids",
    "client_generated_ids_verified",
    "host_redirects_verified",
    "pages_settings_verified",
)
REVIEWS = (
    "legacy_routes_and_fragments",
    "desktop_mobile_light_dark",
    "keyboard_accessibility",
    "network_independence",
    "pages_settings_and_single_publisher",
)
QUERIES = {
    "S_define",
    "TRICK_HOME",
    "trick-CP",
    "exec_set_terminate_time",
    "checkpoint",
    "variable server",
}


def require(condition, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(
        name
        and not path.is_absolute()
        and path.as_posix() == name
        and "\\" not in name
        and all(ord(char) >= 32 and ord(char) != 127 for char in name)
        and all(not part.startswith(".") for part in path.parts)
        and not is_helper(name)
        and name not in {"_Sidebar.html", "_Footer.html"}
    )


def validate_reports(reports: dict, *, release: bool = False) -> None:
    corpus, experience, search = (
        reports[key] for key in ("corpus", "experience", "search")
    )
    require(
        corpus["gate_errors"] == [] and corpus["migration_findings"] == [],
        "Corpus checks failed",
    )
    require(
        experience["errors"] == [] and experience["nav_pages"] > 0,
        "Reader checks failed",
    )
    checks = search["checks"]
    require(
        len(checks) == 6 and {row["query"] for row in checks} == QUERIES,
        "Missing acceptance queries",
    )
    for row in checks:
        require(
            type(row["rank"]) is int and 1 <= row["rank"] <= row["max_rank"] <= 3,
            "Search relevance check failed",
        )
    require(search["negative_fixtures"] == 4, "Missing search negative fixtures")
    if release:
        require(
            all(corpus["legacy_coverage"].get(key) is True for key in LEGACY_GATES),
            "Legacy evidence is incomplete; this candidate cannot be published",
        )


def validate_approval(approval: dict, source: str, checksum: str) -> None:
    require(
        SHA1.fullmatch(source) and SHA256.fullmatch(checksum),
        "Use full lowercase commit and SHA-256 values",
    )
    require(approval["schema_version"] == 1, "Unsupported approval schema")
    require(
        approval["source_commit"] == source and approval["site_tar_sha256"] == checksum,
        "Approval does not identify this exact candidate",
    )
    for name in REVIEWS:
        review = approval["reviews"][name]
        require(
            review["status"] == "passed"
            and isinstance(review["reviewer"], str)
            and review["reviewer"].strip()
            and isinstance(review["evidence"], str)
            and review["evidence"].startswith("https://"),
            f"Missing reviewed evidence: {name}",
        )
    rollback = approval["rollback"]
    require(
        SHA1.fullmatch(rollback.get("source_commit") or "")
        and SHA256.fullmatch(rollback.get("artifact_sha256") or "")
        and isinstance(rollback.get("artifact_url"), str)
        and rollback["artifact_url"].startswith("https://")
        and isinstance(rollback.get("rehearsal_evidence"), str)
        and rollback["rehearsal_evidence"].startswith("https://"),
        "A preserved rollback artifact and rehearsal evidence are required",
    )


def validate_run(run: dict, run_id: str, source: str) -> None:
    require(run_id.isascii() and run_id.isdigit() and int(run_id) > 0, "Invalid run ID")
    require(
        run["id"] == int(run_id)
        and run["repository"]["full_name"] == "nasa/trick"
        and run["head_repository"]["full_name"] == "nasa/trick",
        "Run repository mismatch",
    )
    require(
        run["path"] == ".github/workflows/docs.yml"
        and run["event"] == "push"
        and run["head_branch"] == "master",
        "Only the trusted master docs push workflow is eligible",
    )
    require(
        run["head_sha"] == source
        and run["status"] == "completed"
        and run["conclusion"] == "success",
        "Run is not successful for the selected commit",
    )


def package(root: Path) -> dict:
    source = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    require(
        not subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=root,
            text=True,
        ).strip(),
        "Package only a clean committed checkout",
    )
    reports = {
        key: json.loads((root / ".docs-build" / filename).read_text())
        for key, filename in (
            ("corpus", "report.json"),
            ("experience", "experience-report.json"),
            ("search", "search-report.json"),
        )
    }
    validate_reports(reports)
    site = root / "site"
    require(site.is_dir() and not site.is_symlink(), "Missing or symlinked site")
    files, seen, total = {}, set(), 0
    for path in sorted(site.rglob("*")):
        require(not path.is_symlink(), f"Symlink in site: {path.name}")
        if path.is_dir():
            continue
        name = path.relative_to(site).as_posix()
        info = path.stat()
        require(
            safe_name(name) and stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
            f"Unsafe site file: {name}",
        )
        require(name.casefold() not in seen, f"Case-colliding output: {name}")
        seen.add(name.casefold())
        total += info.st_size
        require(total <= MAX_BYTES, "Site exceeds the 512 MiB packaging limit")
        files[name] = digest(path)
        require(len(files) <= 10000, "Too many site files")
    require(
        "index.html" in files and "404.html" in files and "search.json" in files,
        "Incomplete site",
    )
    output = root / ".docs-build/candidate"
    require(
        not output.is_symlink() and not output.parent.is_symlink(),
        "Symlinked candidate directory",
    )
    output.mkdir(parents=True, exist_ok=True)
    archive = output / "site.tar"
    require(
        not archive.exists() and not (output / "candidate.json").exists(),
        "Candidate already exists; use a fresh checkout/build",
    )
    with tarfile.open(archive, "w", format=tarfile.PAX_FORMAT) as tar:
        for name in files:
            path = site / name
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode, entry.mtime = path.stat().st_size, 0o644, 0
            with path.open("rb") as stream:
                tar.addfile(entry, stream)
    manifest = {
        "schema_version": 1,
        "source_commit": source,
        "site_tar_sha256": digest(archive),
        "files": files,
        "reports": reports,
        "requirements_sha256": digest(root / "tools/docs/requirements.txt"),
    }
    (output / "candidate.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(
        f"Candidate {source}: {len(files)} files; site.tar SHA-256 {manifest['site_tar_sha256']}"
    )
    return manifest


def unpack(
    bundle: Path, output: Path, source: str, checksum: str, approval: dict
) -> None:
    validate_approval(approval, source, checksum)
    archive = bundle / "site.tar"
    metadata = bundle / "candidate.json"
    require(
        not bundle.is_symlink()
        and not archive.is_symlink()
        and not metadata.is_symlink()
        and archive.is_file()
        and metadata.is_file(),
        "Missing or non-regular candidate files",
    )
    require(
        archive.stat().st_size <= MAX_BYTES and digest(archive) == checksum,
        "Candidate archive checksum/size mismatch",
    )
    require(
        metadata.stat().st_size <= 16 * 1024 * 1024, "Candidate metadata is too large"
    )
    manifest = json.loads(metadata.read_text())
    require(
        manifest["schema_version"] == 1
        and manifest["source_commit"] == source
        and manifest["site_tar_sha256"] == checksum,
        "Candidate manifest mismatch",
    )
    validate_reports(manifest["reports"], release=True)
    expected = manifest["files"]
    require(
        {"index.html", "404.html", "search.json"} <= expected.keys(),
        "Incomplete manifest",
    )
    require(
        not output.exists()
        and not output.is_symlink()
        and not output.parent.is_symlink(),
        "Publish output must be a new directory",
    )
    # Validate every member before making any output. Never call extractall.
    with tarfile.open(archive, "r:") as tar:
        members, seen, total = [], set(), 0
        for member in tar:
            require(
                member.isfile() and safe_name(member.name) and member.name in expected,
                f"Unsafe or unmanifested archive member: {member.name}",
            )
            require(
                member.name.casefold() not in seen,
                "Duplicate/case-colliding archive member",
            )
            seen.add(member.name.casefold())
            total += member.size
            require(
                len(seen) <= 10000 and total <= MAX_BYTES,
                "Archive exceeds publication limits",
            )
            with tar.extractfile(member) as stream:
                require(
                    hashlib.file_digest(stream, "sha256").hexdigest()
                    == expected[member.name],
                    f"Changed archive member: {member.name}",
                )
            members.append(member)
        require(
            {member.name for member in members} == expected.keys(),
            "Archive is missing manifested files",
        )
        require(
            not any(
                parent.as_posix().casefold() in seen
                for member in members
                for parent in PurePosixPath(member.name).parents
            ),
            "Archive contains a file/directory collision",
        )
        output.mkdir(parents=True)
        for member in members:
            target = output / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as stream, target.open("xb") as destination:
                while data := stream.read(1024 * 1024):
                    destination.write(data)
    print(f"Verified {len(members)} approved files; no rebuild performed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("package", "preflight", "unpack"))
    args = parser.parse_args()
    if args.command == "package":
        package(ROOT)
        return
    source, checksum = (
        os.environ["DOCS_SOURCE_COMMIT"],
        os.environ["DOCS_SITE_TAR_SHA256"],
    )
    approval = json.loads((ROOT / "tools/docs/release-approval.json").read_text())
    validate_approval(approval, source, checksum)
    if args.command == "unpack":
        unpack(
            ROOT / ".docs-build/download",
            ROOT / ".docs-build/publish",
            source,
            checksum,
            approval,
        )
        return
    require(
        os.environ["GITHUB_REPOSITORY"] == "nasa/trick"
        and os.environ["GITHUB_REF"] == "refs/heads/master"
        and os.environ["GITHUB_EVENT_NAME"] == "workflow_dispatch",
        "Untrusted publishing context",
    )
    run_id = os.environ["DOCS_RUN_ID"]
    require(run_id.isascii() and run_id.isdigit() and int(run_id) > 0, "Invalid run ID")
    request = Request(
        f"https://api.github.com/repos/nasa/trick/actions/runs/{run_id}",
        headers={
            "Authorization": "Bearer " + os.environ["GH_TOKEN"],
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=30) as response:
        validate_run(json.load(response), run_id, source)
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", source, "HEAD"], cwd=ROOT, check=True
    )
    print(
        f"Trusted successful master candidate {source}, run {run_id}; approval matches"
    )


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        tarfile.TarError,
        subprocess.CalledProcessError,
    ) as error:
        raise SystemExit(f"Release refused: {error}") from error
