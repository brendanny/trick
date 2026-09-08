# Documentation migration pilot

This implements steps 1–3 and the step-4 publishing infrastructure for the
Jekyll-to-Zensical migration: a reproducible
build harness, immutable source baseline, full-corpus content conversion,
task-oriented reader experience, **non-deploying** PR CI, and a separate disabled-
by-default, approval-gated publisher. Browser acceptance and the actual production
cutover are still pending. This does not switch GitHub Pages, introduce release versioning,
or change Doxygen or Trick's runtime dependencies.

The branch is based on `brendanny/trick:master` at
`cc3c4566ad71041efca2f1756bd13047f3829778`, not the newer upstream revision used
when drafting the plan. In particular, this baseline's cannonball equations are
images. No unrelated upstream tutorial changes are included.

## Install and run

Use Python 3.11 and a virtual environment, plus Node.js 24 for the native search
regression check (no npm packages). The documentation environment is
independent of Trick's compiler, Python bindings, Java, and simulation builds.

```sh
python3.11 -m venv .venv-docs
. .venv-docs/bin/activate
python -m pip install --only-binary=:all: --require-hashes -r tools/docs/requirements.txt
python -m unittest discover -s tools/docs/tests -v
python tools/docs/inventory.py --check
python tools/docs/build.py build --strict
python tools/docs/check_site.py
python tools/docs/check_experience.py
node tools/docs/check_search.cjs
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

| Check | Current behavior |
| --- | --- |
| Dependency installation | Exact versions and hashes; Zensical 0.0.59. |
| Full corpus build | Strict build must succeed with no warnings. |
| Baseline pages and assets | Missing output or changed asset bytes fails the check. |
| Explicit source anchors | Missing output anchors fail the check. |
| Jekyll helpers | Publishing a helper fails the check. |
| Seven representative pages | Missing text, headings, code blocks, or images below the recorded minimum fails. |
| Metadata | Every page needs an explicit title and current/historical status; rendered titles are checked. |
| Search index | All current pages must be indexed; all historical pages must be absent. Missing/invalid/empty search fails. |
| Native search relevance | Six Trick queries must return the intended guidance within the first three worker hits; missing targets and rank regressions fail. Browser interaction remains a separate check. |
| Navigation and archive | Every current page has exactly one primary nav home; rendered tabs, active section sidebar, nested breadcrumbs, and Previous/Next order are checked. All historical pages are linked from the archive. |
| Page contents | Every authored page has one top-level title; all Markdown section headings must appear in the native contents panel. Legacy breadcrumb tables, contents headings, and page footers fail the check. |
| Reader metadata | Authored-source edit links, canonical URLs, current-page sitemap, light/dark controls, skip links, and development label are checked. |
| Automatic resources | HTML/CSS subresources and search configuration must resolve locally under `/trick/`; the repository-statistics component is prohibited. Runtime browser network behavior remains unverified. |
| Historical pages | Published at their original paths, with a visible notice and links to current guidance. |
| Code samples | Source samples must match the immutable baseline; rendered samples must match source text and order. |
| Raw-HTML links and duplicate IDs | Every finding fails, including missing fragments; there is no allowance list. |
| Strict validation | Negative fixtures must fail against the real Zensical executable. |
| Publication | PR CI has no deployment job or Pages/OIDC permissions. A separate manual publisher requires upstream master, explicit opt-in, reviewed evidence, an exact successful candidate, and the protected Pages environment. |
| Output collisions | Source paths that would overwrite the same output or collide as files/directories fail before rendering. |

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
- `.docs-build/experience-report.json`: navigation, archive, canonical/edit URLs,
  presentation markup, static resource audit, and explicit browser-check status.
- `.docs-build/search-report.json`: real search-worker hash, measured ranks and
  first-response locations for the six acceptance queries, and negative fixtures.
- `.docs-build/candidate/`: successful validated static candidate and checksum/
  provenance manifest, produced by `python tools/docs/release.py package` from a
  clean committed checkout after the validation sequence above.

See [Publishing and recovery](PUBLISHING.md) for the step-4 trust boundaries,
exact-artifact promotion, required evidence, optional external-link audit, and
the coordinated cutover/rollback procedure. The checked-in approval record is
deliberately incomplete and authorizes no deployment.

## Reader experience (step 3)

The navigation in `zensical.toml` organizes the 101 existing current pages
and the new archive index into Start here, Tutorial, User guide, Reference,
How-to, FAQ, and Developer. Native sticky header tabs select the top-level
section; on wide screens the sidebar shows only that section's pages. On narrow
screens the theme provides its navigation drawer. Each page has one primary
home, and contextual links remain in the content. The tutorial follows the
existing cannonball sequence, with native Previous/Next controls generated from
the same navigation order.

The former tutorial, user-guide, how-to, and developer page lists are concise
overviews at their existing URLs. Their first entries open from the corresponding
tabs; their page lists are maintained only in `zensical.toml`. The existing
filenames are intentionally retained, so these overviews are ordinary first
navigation entries rather than renamed `index.md` files or redirects.

Hand-written breadcrumb tables, tutorial next-page footers, and contents lists
(including the FAQ list and installation jump table) have been removed. The
theme supplies breadcrumbs for nested sections and heading-based “On this page”
navigation. Pages with multiple top-level headings now have a single title and
nested sections so that the entire outline appears. Heading IDs, explicit anchor
aliases, baseline page URLs, asset bytes, and code samples are preserved.

The homepage gives direct routes to installation, the tutorial, and common
references, then links to the manuals, archive, related projects, and license.
`docs/archive.md` groups all 32 historical pages while retaining their original
URLs, notices, and search exclusion. The pinned generator also omits these
search-excluded pages from its sitemap. Their canonical URLs and archive links
remain valid; sitemap omission is not a redirect or an access restriction.

The bundled theme supplies section navigation, breadcrumbs, in-page navigation,
code copying, search highlighting, and system-aware light/dark controls. Local
`docs/stylesheets/trick.css` adds system fonts, the existing Trick logo on a white
tile, constrained wide content, underlined prose links, visible focus outlines,
and reduced-motion rules. There is no custom JavaScript or instant navigation.

Small templates in `tools/docs/overrides/` add the development/master migration
label and a 404 with prefix-safe recovery links. The source partial renders a
plain repository link **without** `data-md-component="source"`: the default
[repository component](https://zensical.org/docs/setup/repository/) requests
GitHub statistics automatically. `repo_url` remains configured for edit actions,
with `edit_uri = "edit/master/docs/"` targeting authored files in upstream NASA
Trick, never `.docs-build/source`. These are eventual upstream-master edit links,
not links to edit the fork's pilot branch. New pilot-only files will not exist at
the upstream edit destination until the migration is integrated there.

Fonts, styles, scripts, icons, search, and equation images are local. The static
audit checks HTML subresources, CSS URLs/imports, and search index/worker paths,
including the 404 under `/trick/`. External user-activated hyperlinks are allowed.
This is not a JavaScript network audit or proof of network-blocked browser use.

### Native search acceptance

The search separator preserves underscores and hyphens in identifiers and
commands, and splits shell `${...}` wrappers. With the default separator,
`TRICK_HOME` split into broad terms and its environment reference was absent
from the first ten worker hits. The configured separator returns it first,
without modifying examples, patching the generated index, or adding a search
service. This is supported by the pinned generator's search configuration.

`check_search.cjs` reads the worker path from built theme configuration and runs
that actual bundled worker in Node's VM with no `fetch`, XMLHttpRequest, or other
network APIs provided. It sends the same query/filter envelope as the 0.0.59 UI;
there is no replacement ranking algorithm. Engine upgrades must rerun these
checks and review changes to the worker protocol, index, and ranking.

| Query | Intended current guidance | Measured worker rank |
| --- | --- | --- |
| `S_define` | Simulation definition file | 1 |
| `TRICK_HOME` | Build environment variables / PATH | 1 |
| `trick-CP` | Making the simulation | 2 |
| `exec_set_terminate_time` | Executive scheduler / Commanding to Shutdown | 1 |
| `checkpoint` | Checkpoints | 1 |
| `variable server` | Variable server reference | 1 |

These are individual section hits in the first worker response, **before** the
UI groups hits by page, not a claim about measured browser positions. Every case
must stay within the first three hits. Four negative fixtures reject empty
results, a rank regression, a wrong section, and an actual index with the target
page removed. The content gate independently checks historical search exclusion.

### Browser acceptance still required

No browser/visual acceptance is claimed by these static checks. Before cutover,
explicitly review all seven pilot pages at desktop and mobile widths in both
palettes: navigation drawers and breadcrumbs; long tables, screenshots, equation
images, and code blocks; keyboard focus, skip links and search controls; contrast
and zoom; copy buttons; and search result navigation/highlights for all six terms.
Run reading, navigation, search, and equation-image checks with third-party
requests blocked, and inspect the browser's network log. Verify helpful 404
behavior for a genuinely missing nested URL on the deployed host. Only that
review can establish visual, interaction, accessibility, and network acceptance.

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

After review, supplemental evidence may be stored as
`tools/docs/legacy-rendered.json`; normal CI then picks it up automatically.
`load_baseline` rejects changes to the immutable source inventory or an incomplete
rendered capture. Source-only `legacy-routes.json` stays unchanged.

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
`pull_request_target`. It also packages and uploads a successful static candidate
for later explicit promotion; it cannot deploy it. The downloaded review artifact
contains only output, diagnostics, and reports—not the environment or other workspace files. It is
not a hosted preview and is not a durable rollback archive.

## Handoff to production cutover

The artifact-based publishing workflow and runbook are now prepared. Next,
complete explicit browser acceptance, the outstanding legacy evidence, recovery
rehearsal, and authorized maintainer coordination before enabling publication.
Follow `PUBLISHING.md`; no release approval is inferred from green CI. The Jekyll configuration and
layout, dependency lock, Doxygen, and Pages settings remain unchanged, but the
authored Markdown now contains the conversion. Do not deploy this branch through
the old publisher or assume it has been verified against Jekyll. Complete the
outstanding legacy evidence and explicit browser checks before cutover; green
corpus validation alone does not authorize deployment.

The eventual switch must preserve the exact tested artifact and a rollback path.
Reverting only a Pages setting is insufficient if converted Markdown no longer
renders correctly with the old Jekyll pipeline.
