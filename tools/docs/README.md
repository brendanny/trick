# Documentation migration pilot

This is step 1 of the Jekyll-to-Zensical migration: a reproducible build harness,
source baseline, representative-content checks, and **non-deploying** CI.
It does not switch GitHub Pages, rewrite the documentation, introduce release
versioning, or change Doxygen or Trick's runtime dependencies.

The branch is based on `brendanny/trick:master` at
`cc3c4566ad71041efca2f1756bd13047f3829778`, not the newer upstream revision used
when drafting the plan. In particular, this baseline's cannonball equations are
images. No unrelated upstream tutorial changes are included.

## Install and run

Use Python 3.11 and a virtual environment. The documentation environment is
independent of Trick's compiler, Python bindings, Java, and simulation builds.

```sh
python3.11 -m venv .venv-docs
. .venv-docs/bin/activate
python -m pip install --only-binary=:all: --require-hashes -r tools/docs/requirements.txt
python -m unittest discover -s tools/docs/tests -v
python tools/docs/inventory.py --check
python tools/docs/build.py build
python tools/docs/check_site.py
```

Run commands from the repository root. The inventory check requires the recorded
baseline commit to be available locally; CI checks out full history. A shallow
clone may need its history deepened. Binary-only installation deliberately fails
on a platform without compatible dependency wheels rather than unexpectedly
requiring a Rust or C compiler. Linux x86-64/Python 3.11 is the initial CI target;
other platforms should be verified before being described as supported.

Preview locally with:

```sh
python tools/docs/build.py serve
```

The wrapper mirrors source edits, additions, and removals into the generated
projection while Zensical handles live reload. Stop it with Ctrl-C. Do not run
multiple builders/previews in the same checkout simultaneously.

`site/` and `.docs-build/source/` are disposable generated directories; the
wrapper clears them during preparation/building. Do not put authored files
there. It refuses symlinked generated directories and directories containing
tracked files. The original `docs/` tree is never modified by the harness.

## Why there is a generated source projection

[Zensical 0.0.59 does not support `exclude_docs`](https://zensical.org/compatibility/configuration/).
Using that setting silently publishes `_config.yml`, `_layouts/default.html`,
`_Sidebar.html`, and `_Footer.html`. Merely leaving pages out of `nav` is not an
exclusion from publication either.

`build.py` therefore projects `docs/` into the ignored `.docs-build/source/`
directory, omitting the four known Jekyll helpers and dotfiles. It copies content
byte-for-byte: no link rewrites, inferred page titles, historical notices, or
anchor fixes are applied during the build. `zensical.toml` points to this
generated directory. `prepare` can refresh it without starting a build:

```sh
python tools/docs/build.py prepare
```

The projection is not a second authored source tree. Once the Jekyll helpers can
be removed after cutover, or a supported upstream exclusion mechanism is adopted
and tested, it can be simplified away. Calling `zensical build` directly without
preparing the source uses a stale projection and is not the supported workflow.

## What passes now and what remains discovery work

| Check | Step-1 behavior |
| --- | --- |
| Dependency installation | Exact versions and hashes; Zensical 0.0.59. |
| Full corpus build | Must succeed; Zensical link/anchor warnings are recorded, not suppressed. |
| Baseline pages and assets | Missing output or changed asset bytes fails the check. |
| Explicit source anchors | Missing output anchors fail the check. |
| Jekyll helpers | Publishing a helper fails the check. |
| Seven representative pages | Missing text, headings, code blocks, or images below the recorded minimum fails. |
| Search index | Missing/invalid/empty index or missing pilot entries fails; relevance and browser behavior are later checks. |
| Raw-HTML links and duplicate IDs | Findings are reported for the content-conversion step. |
| Strict validation | Negative fixtures must fail against the real Zensical executable. |
| Publication | No deployment job, Pages write permission, OIDC permission, or `gh-pages` push. |

The pilot covers the homepage, install guide, simple cannonball simulation,
analytic cannonball tutorial, `S_define` reference, Variable Server reference,
and screenshot-heavy Data Products GUI guide. `pilot.json` defines the checks.
These are static content-preservation checks, not visual/browser approval.

The initial measured build reports 71 Zensical issues. The separate HTML check
reports 117 findings: 100 duplicate IDs, 10 missing targets, and 7 missing
fragments. These counts are explanatory observations, not a hard-coded allowance
or proof that every issue predates the generator change. Review the actual report
when the sources or dependencies change.

Outputs:

- `site/`: full Zensical pilot output, not a production-ready artifact.
- `.docs-build/zensical-build.log`: complete generator diagnostics.
- `.docs-build/report.json`: structural errors, migration findings, and baseline
  coverage flags. No timestamps or absolute build paths are embedded in this report.

The future strict gates are available explicitly and **are expected to fail at
this stage**:

```sh
python tools/docs/build.py build --strict
python tools/docs/check_site.py --strict
```

The latter also refuses to report cutover readiness while rendered legacy IDs,
live host aliases, or Pages settings remain unverified. A source-file or HTML
existence check cannot prove that an extensionless request works on GitHub Pages.

## Baseline provenance and outstanding legacy evidence

`legacy-routes.json` is deterministic evidence from the exact baseline Git
commit, with 133 Markdown pages, 166 assets/passthrough files, 4 Jekyll helpers,
and 208 explicit source anchors. Each entry retains its Git blob ID. HTML paths
are inferred from source filenames and are explicitly labeled as inferred.
The inventory distinguishes retained pages from pages retained for historical
review; that label is not approval to delete or rewrite anything.

The upstream [Pages run for this exact commit](https://github.com/nasa/trick/actions/runs/31194845713)
succeeded on 2026-08-07, but artifact `9000354686` expired on 2026-08-08.
It cannot supply the original output now. An exact legacy Jekyll build was not
available in the implementation environment. Consequently, this commit does
**not** claim a complete published-route inventory, automatic-heading-ID
baseline, live-URL alias verification, or verified repository Pages settings.

Before the production cutover:

1. Record the real publishing source/settings with authorized maintainer access.
2. Produce a matching Jekyll build from the baseline commit, recording its Ruby,
   GitHub Pages/Jekyll dependency versions, config, and output provenance. Use a
   separate worktree so the migration source and current docs remain untouched.
3. Capture the actual static HTML IDs using the importer below. It requires all
   expected pages to be present rather than silently accepting a partial build.
4. Verify client-generated IDs and real host behavior for `.html`, extensionless,
   root/index, and fragment URLs separately. Keep browser checks explicit.
5. Preserve a known-good published artifact or reproducible fallback for rollback.

```sh
python tools/docs/inventory.py --legacy-html /absolute/path/to/legacy-output --output .docs-build/legacy-rendered.json
python tools/docs/check_site.py --baseline .docs-build/legacy-rendered.json
```

Only pass output generated from the manifest's recorded `source_commit`. The
importer records hashes and static IDs of the supplied HTML; it cannot authenticate
that build's provenance or infer browser-generated IDs. Imported missing anchors
appear as separate migration findings. Keep the source-only tracked manifest
unchanged until a reviewed evidence update is ready.

To reproduce the initial source manifest deliberately:

```sh
python tools/docs/inventory.py --ref cc3c4566ad71041efca2f1756bd13047f3829778 --output .docs-build/source-inventory.json
```

Do not regenerate the legacy baseline from a migration commit just to make a
comparison pass. Preserve the old contract and fix or explicitly map differences.

## Dependencies and CI

`requirements.in` is the direct dependency list; `requirements.txt` locks its
full dependency closure with hashes. The original lock was generated with uv
0.11.33; uv is a maintainer-only lock-generation tool, not required to build docs.

```sh
uv pip compile tools/docs/requirements.in --python-version 3.11 --generate-hashes --no-emit-index-url --output-file tools/docs/requirements.txt
```

Update pins intentionally, inspect the lock diff, reinstall in a fresh environment,
and rerun the unit/integration tests and full pilot before committing an update.
Only use documented, released capabilities. Keep caches disposable; CI builds
with a clean generator cache and fresh output.

`.github/workflows/docs.yml` runs on PRs and pushes to `master` or
`zensical-migration`, with a manual trigger. It always reports its named check,
has read-only repository permissions, pins actions to commit SHAs, and never uses
`pull_request_target`. The downloaded review artifact contains only output,
diagnostics, and the report—not the environment or other workspace files. It is
not a hosted preview and is not a durable rollback archive.

## Handoff to step 2

Keep this branch additive until cutover: Jekyll source/layout and Doxygen remain
unchanged. Next, review and fix the reported link/fragment/duplicate-ID differences,
add stable page metadata, and decide historical-page dispositions. Navigation and
presentation improvements and production publishing remain later steps. Do not
enable deployment merely because the step-1 structural check is green.

The eventual switch must preserve the exact tested artifact and a rollback path.
Reverting only a Pages setting is insufficient if converted Markdown no longer
renders correctly with the old Jekyll pipeline.
