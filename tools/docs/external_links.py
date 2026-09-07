"""Optional bounded HEAD-only audit; no credentials, retries, or redirect following."""

import ipaddress
import json
import subprocess
import time
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup
from common import ROOT


def audit_url(href: str) -> str | None:
    try:
        target = urlsplit(href)
        port = target.port
    except ValueError:
        return None
    if target.scheme not in {"http", "https"} or not target.hostname:
        return None
    if target.hostname == "nasa.github.io" and target.path.startswith("/trick/"):
        return None
    if target.username or target.password or port not in {None, 80, 443}:
        return None
    # This advisory tool accepts public DNS names only, never IP literals or
    # local names. No redirects are followed to a new network destination.
    try:
        ipaddress.ip_address(target.hostname)
    except ValueError:
        if "." not in target.hostname or target.hostname.endswith((
            ".local",
            ".localhost",
            ".internal",
        )):
            return None
    else:
        return None
    return urlunsplit((target.scheme, target.netloc, target.path, target.query, ""))


def audit(
    urls: list[str], exceptions: dict, budget: float = 120, limit: int = 200
) -> dict:
    if not all(
        isinstance(reason, str) and reason.strip() for reason in exceptions.values()
    ):
        raise ValueError("Every external-link exception needs a reviewed reason")
    deadline, results = time.monotonic() + budget, []
    for index, url in enumerate(urls):
        if url in exceptions:
            results.append({
                "url": url,
                "status": "exception",
                "reason": exceptions[url],
            })
            continue
        remaining = deadline - time.monotonic()
        if index >= limit or remaining < 1:
            results.append({
                "url": url,
                "status": "not-checked",
                "reason": "audit budget exhausted",
            })
            continue
        timeout = min(5, remaining)
        try:
            result = subprocess.run(
                [
                    "curl",
                    "--disable",
                    "--silent",
                    "--head",
                    "--proto",
                    "=https,http",
                    "--connect-timeout",
                    "3",
                    "--max-time",
                    str(timeout),
                    "--output",
                    "/dev/null",
                    "--write-out",
                    "%{http_code}",
                    "--url",
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=timeout + 0.5,
                check=False,
            )
            code = int(result.stdout) if result.stdout.isdigit() else 0
            status = (
                ("reachable" if 200 <= code < 300 else "redirect")
                if result.returncode == 0 and 200 <= code < 400
                else "needs-review"
            )
            results.append({"url": url, "status": status, "http_status": code})
        except subprocess.TimeoutExpired:
            results.append({
                "url": url,
                "status": "needs-review",
                "reason": "request timed out",
            })
    return {
        "results": results,
        "limits": {"seconds": budget, "urls": limit},
        "scope": "HEAD responses only; redirects, fragments, authentication, and skipped URLs require review",
    }


def main() -> int:
    urls = set()
    skipped = set()
    for path in sorted((ROOT / "site").rglob("*.html")):
        soup = BeautifulSoup(path.read_text(), "html.parser")
        for tag in soup.select("a[href]"):
            href = tag["href"]
            if url := audit_url(href):
                urls.add(url)
            elif href.startswith(("http:", "https:")) and not href.startswith(
                "https://nasa.github.io/trick/"
            ):
                skipped.add(href)
    report = audit(
        sorted(urls),
        json.loads((ROOT / "tools/docs/external-link-exceptions.json").read_text()),
    )
    report["skipped_urls"] = sorted(skipped)
    output = ROOT / ".docs-build/external-links-report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    failed = any(
        row["status"] in {"needs-review", "not-checked"} for row in report["results"]
    )
    print(
        f"External-link audit: {len(urls)} URLs; manual review {'needed' if failed or skipped else 'not flagged'}. Report: {output}"
    )
    return int(failed or bool(skipped))


if __name__ == "__main__":
    raise SystemExit(main())
