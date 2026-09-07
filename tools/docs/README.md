# Documentation migration pilot

This implements steps 1 and 2 of the Jekyll-to-Zensical migration: a reproducible
build harness, immutable source baseline, full-corpus content conversion, and
**non-deploying** CI. It does not switch GitHub Pages, introduce release versioning,
or change Doxygen or Trick's runtime dependencies.

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
python tools/docs/build.py build --strict
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

## What passes now and what remains cutover work

| Check | Step-2 behavior |
| --- | --- |
| Dependency installation | Exact versions and hashes; Zensical 0.0.59. |
| Full corpus build | Strict build must succeed with no warnings. |
| Baseline pages and assets | Missing output or changed asset bytes fails the check. |
| Explicit source anchors | Missing output anchors fail the check. |
| Jekyll helpers | Publishing a helper fails the check. |
| Seven representative pages | Missing text, headings, code blocks, or images below the recorded minimum fails. |
| Metadata | Every page needs an explicit title and current/historical status; rendered titles are checked. |
| Search index | All current pages must be indexed; all historical pages must be absent. Missing/invalid/empty search fails. Relevance and browser behavior are later checks. |
| Historical pages | Published at their original paths, with a visible notice and links to current guidance. |
| Code samples | Source samples must match the immutable baseline; rendered samples must match source text and order. |
| Raw-HTML links and duplicate IDs | Every finding fails, including missing fragments; there is no allowance list. |
| Strict validation | Negative fixtures must fail against the real Zensical executable. |
| Publication | No deployment job, Pages write permission, OIDC permission, or `gh-pages` push. |

The pilot covers the homepage, install guide, simple cannonball simulation,
analytic cannonball tutorial, `S_define` reference, Variable Server reference,
and screenshot-heavy Data Products GUI guide. `pilot.json` defines the checks.
These are static content-preservation checks, not visual/browser approval.

Step 1 reported 71 Zensical issues and 117 HTML findings: 100 duplicate IDs,
10 missing targets, and 7 missing fragments. Step 2 reports zero in both checks,
preserves all 133 page paths, 166 asset blobs, 208 explicit anchor targets, and
740 code samples, and excludes 32 historical pages from search. These are measured
observations, not hard-coded allowances or proof of complete Jekyll compatibility.

Outputs:

- `site/`: full Zensical pilot output, not a production-ready artifact.
- `.docs-build/zensical-build.log`: complete generator diagnostics.
- `.docs-build/report.json`: structural errors, migration findings, and baseline
  coverage flags. No timestamps or absolute build paths are embedded in this report.

The build's `--strict` mode is now mandatory in CI. The separate **cutover-evidence
gate remains expected to fail**:

```sh
python tools/docs/check_site.py --strict
```

This additionally refuses to report cutover readiness while rendered legacy IDs,
client-generated IDs, live host aliases, or Pages settings remain unverified. A source-file or HTML
existence check cannot prove that an extensionless request works on GitHub Pages.

## Content-conversion decisions

Markdown page destinations are now explicit relative `.md` paths; raw HTML
`href` attributes use relative `.html` output paths because the generator does
not rewrite raw HTML. Asset and repository/source links are distinct from page
links. Filenames and capitalization have not changed.

The one-time conversion used tree-sitter Markdown block/inline source ranges,
not a global textual substitution. Fenced/indented code was excluded and checked
byte-for-byte during conversion. No conversion code runs as part of a build;
the reviewed Markdown is the authored source.

Redundant raw anchors were removed only where the same target is supplied by a
heading, or where a duplicate `XXX` anchor shadowed the first one in trick-jperf.
Distinct aliases were retained and quoted so strict validation recognizes them.
The first `XXX` target still resolves to Frame Boundaries. Source-linked aliases
were added for five TrickOps headings, `Purpose`, and `volt`; these are not a
substitute for comparing a rendered Jekyll baseline.

Other scoped repairs correct the STL filename's case, the Web Server APIs and
How-To breadcrumb paths, two missing `#` fragment prefixes, an archived image
path, and a malformed anchor attribute. Old wiki markup is converted to working
Markdown links and images. The existing GFM strikethrough in both Python
variable-server guides is enabled via `pymdownx.tilde`, without subscript syntax.
Equation images remain unchanged; this baseline needs no added MathJax bundle.

Each page records its disposition in `documentation_status` front matter:

| Pages | Disposition and rationale |
| --- | --- |
| 101 current pages | Retained and searchable. “Current” is a navigation policy, not a new technical audit of every statement. |
| 9 `developer_docs/Des*.md` pages | Historical; the existing developer index already identifies these designs as potentially outdated. |
| 17 `not_referenced/design/*.md` pages | Historical; retained design drafts, duplicate designs, and incomplete design notes, not removed or silently merged. |
| 6 remaining `not_referenced` pages | Historical; retain the GSL examples, input quick reference, Monte Carlo reference, Python client guide, S_sie parsing notes, and functions overview. Link to current guidance where available, without claiming every old example is invalid. |

Historical notices explain the uncertainty rather than declaring the described
capabilities deprecated. Search exclusion, publication, and primary navigation
are separate: these pages are still published and their existing index links
remain usable, but they are absent from search and the primary `nav` list.
[Page-level search exclusion](https://zensical.org/docs/setup/search/) and
[front matter](https://zensical.org/docs/authoring/frontmatter/) are supported by
the pinned generator and verified in its output.

`content.py` compares code samples with the old Git blobs and with rendered HTML
throughout this migration. A substantive example correction needs its own review
and an explicit adjustment of that migration guard; do not regenerate the legacy
manifest to make a content change pass. Retire the old-source code comparison
after cutover, retaining source-to-output checks.

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

## Handoff to step 3

Next, develop task-oriented navigation, the homepage, search relevance, and
presentation. Keep production publishing separate. The Jekyll configuration and
layout, dependency lock, Doxygen, and Pages settings remain unchanged, but the
authored Markdown now contains the conversion. Do not deploy this branch through
the old publisher or assume it has been verified against Jekyll. Complete the
outstanding legacy evidence and explicit browser checks before cutover; green
corpus validation alone does not authorize deployment.

The eventual switch must preserve the exact tested artifact and a rollback path.
Reverting only a Pages setting is insufficient if converted Markdown no longer
renders correctly with the old Jekyll pipeline.
