# Documentation publishing and recovery

This is the step-4 publishing infrastructure and maintainer runbook, **not an
authorization to cut over**. The migration branch cannot publish. No repository
variables, environment protection rules, Pages settings, or live site have been
changed by this implementation. Browser acceptance, complete legacy evidence,
and a rehearsed rollback remain outstanding.

## Two workflows, separate authority

| Workflow | Trigger and authority | Output |
| --- | --- | --- |
| `docs.yml` / Documentation pilot | Every PR and pushes to `master` and `zensical-migration`; manual runs also available. `contents: read` only. | Diagnostic review artifact plus a successful-build candidate. No deployment. |
| `docs-publish.yml` / Publish approved documentation | Manual dispatch on **nasa/trick master** only, and only when the repository variable `DOCS_PAGES_ENABLED` is exactly `true`. | Promotes one explicitly selected, reviewed candidate through the protected `github-pages` environment. |

Fork PRs, migration-branch runs, failed runs, other workflows, and manually built
candidates are not eligible for production promotion. The publishing workflow
checks the source run through GitHub's API: repository and head repository must
both be `nasa/trick`, the workflow path must be `.github/workflows/docs.yml`, the
event must be `push`, the branch must be `master`, and the completed run must be
successful for the supplied full commit SHA. That SHA must be an ancestor of the
trusted master revision running the publisher.

The read-only preparation job uses helpers and approval data checked out from
the dispatch's master revision. It never executes downloaded candidate files.
Only the separate deployment job has `pages: write` and `id-token: write`; it has
no checkout, build, or dependency installation. Its only action deploys the
verified Pages artifact produced by its successful `prepare` dependency. The
whole publishing workflow shares one concurrency group and does not cancel an
in-flight deployment. It has no automatic push or `workflow_run` trigger.

This follows [GitHub's artifact-based Pages model](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
Action revisions are pinned. The workflow does not run `configure-pages` or
attempt to enable Pages automatically. Do not introduce a parallel `gh-pages`
publisher or generated site commits on `master`.

## Candidate artifact

After all validators succeed, `release.py package` creates:

- `site.tar`: regular static files only, sorted names and normalized tar metadata.
- `candidate.json`: exact source commit, dependency-lock checksum, tar checksum,
  per-file SHA-256 hashes, and the three validation reports.

These are uploaded together as `documentation-candidate`, retained for 30 days.
The existing `documentation-pilot` diagnostic artifact remains available for
7 days, including when a check fails. A failed job never reaches the successful
candidate upload. Neither artifact is a hosted preview or a durable backup.

Packaging requires a clean committed checkout and the preceding successful build
and validators. Run the complete documented sequence first; `package` alone is
not an independent revalidation of a locally modified `site/` tree. CI creates a
fresh checkout and fresh site output before executing those commands in order.
Candidate output must not already exist; use a fresh checkout for a new local
candidate. No `--force` or validation-skipping switch is provided.

Promotion downloads this exact successful run's candidate, verifies the approved
tar checksum and every manifested file, rejects helpers, path traversal,
symlinks, hard links, other special files, duplicates and file/directory
collisions, then writes into a new output directory. Static input is capped at
512 MiB and 10,000 archive files. `upload-pages-artifact` repackages those verified
files for GitHub Pages; **it does not rebuild or change the site files**. The
deployment job consumes that same-run Pages artifact. The approved `site.tar`
checksum is distinct from GitHub's outer compressed artifact digest.

## Complete the release evidence

Do not fill in approval records with assumptions or mark a gate passed merely
because a script accepts its schema. Evidence URLs and reviewer names are
maintainer attestations, not automated proof that reviews happened. Protect
changes to publishing helpers, workflows, baselines, and approval records with
the project's normal required review rules.

1. Reproduce the recorded legacy Jekyll build and capture its real rendered IDs,
   following the provenance requirements in `README.md`. Keep the immutable
   `legacy-routes.json` unchanged. Import supplemental evidence with:

   ```sh
   python tools/docs/inventory.py --legacy-html /absolute/path/to/matching-jekyll-output --output tools/docs/legacy-rendered.json
   ```

   When this reviewed supplemental file exists, normal CI uses it automatically.
   It must preserve the original source commit, pages, assets, helpers, and
   schema, and capture every baseline HTML page exactly once. Its importer marks
   only static rendered-heading coverage complete. Separately verify and record
   client-generated IDs, live aliases/redirects, and publishing settings before
   setting the corresponding coverage flags to boolean `true`. Preserve the
   build provenance and observations in the review evidence. Correct every
   missing legacy target instead of weakening the checks.

2. Complete desktop/mobile and light/dark review on the seven pilot pages;
   keyboard navigation, focus, zoom, contrast, meaningful image text, copy
   buttons, and wide content; and all six search terms with result navigation and
   highlighting. Test reading, navigation, search, and equation images with
   third-party requests blocked. Record results against the candidate checksum.
   The static reports always identify browser testing as separate; they do not
   perform or certify these reviews.

3. Record the current publishing source/settings, old publisher, pre-cutover
   source revision and dependency environment, and a known-good site artifact.
   Keep that artifact somewhere durable with a checksum, outside the expiring
   Actions artifact store. Rehearse recovery before calling the migration ready.

4. Configure `github-pages` environment protections through authorized maintainer
   access: require review, restrict deployment to `master`, and prohibit bypass
   where the repository's plan/policy permits it. Naming an environment in YAML
   does **not** create these protection rules. Keep `DOCS_PAGES_ENABLED` unset or
   false until the settings, single-publisher state, evidence, and recovery path
   have been verified.

## Coordinated first cutover

1. Reconcile documentation changes made upstream during this migration and agree
   on a short cutover window. The source baseline is the recorded fork revision,
   not a claim that the branch already contains the latest NASA documentation.
2. Preserve and rehearse the fallback above. Have an authorized maintainer retire
   the old automatic publisher and select Actions as the Pages publishing source
   before merging incompatible Markdown onto the publishing branch. Verify that
   the existing known-good site remains available during this transition. Do
   not merge converted source while an old Jekyll publisher can automatically
   publish it. Keep the new publisher disabled during candidate preparation.
3. Merge the reviewed candidate into upstream `master`; wait for its
   Documentation pilot push run to succeed. Download `documentation-candidate`,
   verify `site.tar` against `candidate.json`, and retain the source run ID. Finish
   the artifact-specific reviews and release evidence; incomplete legacy flags
   in that candidate's report are a hard publishing failure.
4. In a **subsequent reviewed master commit**, fill `release-approval.json` with
   the candidate's source SHA and tar checksum, a named reviewer and HTTPS evidence
   link for each `passed` review, and the preserved rollback artifact's source,
   checksum, durable URL, and rehearsal evidence. This subsequent commit avoids
   a circular dependency: the approved checksum is not embedded in the candidate
   whose checksum it describes. Do not select the approval commit's new build by
   mistake; select the already-reviewed candidate.
5. Once the maintainer verifies all prerequisites, set the repository variable
   `DOCS_PAGES_ENABLED=true`. Dispatch **Publish approved documentation** on
   `master`, supplying the selected run ID, its full source SHA, and its
   `site.tar` SHA-256. No arbitrary artifact URL or source branch is accepted.
6. Review the pending `github-pages` deployment: check the exact source run,
   approved hashes, preparation result, and recovery readiness. Approve it only
   after this final check. The publisher has no permission to bypass environment
   protection or alter Pages settings.
7. Verify the live `/trick/` site: home, install, tutorial, deep `.html` URLs,
   verified extensionless aliases and fragments, search, equations, edit links,
   canonical URLs, sitemap, and a genuinely missing nested path's 404. Record the
   deployment ID, source run/commit, candidate checksum, and results. Keep the
   fallback throughout the agreed rollback window.

There is deliberately no successful-production claim until these steps have
actually been performed. Do not remove the legacy helpers as part of preparation;
cleanup is a later focused change after acceptance.

## Recovery procedure

Treat a critical route/content/search regression as a rollback trigger. Record
the failing deployment and disable `DOCS_PAGES_ENABLED` immediately. Cancel any
queued promotion or pending approval; inspect an in-flight deployment explicitly
rather than assuming the variable change stops an already-running action. Keep
one maintainer coordinating recovery so two publishers cannot race.

### Restore an earlier approved Zensical artifact

If its successful master run and `documentation-candidate` are still available,
review an approval-record change identifying that known-good source/checksum and
the current recovery evidence. Re-enable the publisher only for the recovery,
dispatch it with the **old** source run and hash, and approve the protected job.
The ancestry, report, and checksum gates still apply. There is no rebuild and no
need to revert unrelated Trick code. Recheck the live routes and disable further
promotions until the regression is resolved.

### Restore the pre-migration Jekyll site

The Zensical publisher intentionally cannot accept arbitrary legacy artifacts or
unknown workflows. Use the separately preserved and rehearsed old publishing
procedure recorded in the rollback evidence:

1. Keep the Zensical publisher disabled and stop outstanding deployments.
2. On a dedicated recovery branch, restore the **matching** pre-cutover `docs/`
   source, Jekyll configuration/helpers, and recorded generator environment from
   the preserved revision. Review that scoped restoration; do not revert
   unrelated simulation-framework changes or feed converted Markdown to Jekyll.
3. If the old publisher cannot target the preserved revision directly, merge the
   reviewed documentation restoration before re-enabling branch-based publishing.
   Restore the recorded publishing source/settings only through authorized
   maintainer access. If the rehearsed old process restores a preserved artifact
   instead, use that exact artifact and verify its checksum before publication.
4. Re-run the same live-route/content checks and confirm that only the selected
   old publisher is active. Preserve the failed candidate for diagnosis.

If the artifact has expired, the old environment cannot be reproduced, or the
rehearsal has not succeeded, **rollback readiness is not established**. Do not
approve cutover or quietly rebuild a different artifact and call it the reviewed
one. Durable retention and the old-publisher rehearsal are maintainer prerequisites
that this code change cannot fabricate.

## Optional external-link audit

Dispatch `docs.yml` on trusted `master` with `check_external_links=true`, or run
`python tools/docs/external_links.py` after a full local build. Normal push and PR
checks do not contact external destinations. The optional audit uses credential-
free HEAD requests through curl, no redirects/retries, up to 5 seconds per URL,
200 URLs and a 120-second request budget; the CI step also has a 3-minute limit.
Unvisited URLs remain `not-checked`, never silently passed. It excludes IP
literals, local hostnames, credential-bearing URLs and nonstandard ports; it is
an advisory trusted-source audit, not an SSRF/security boundary.

Inspect `external-links-report.json` for failures, redirects, skipped URLs and
inconclusive HEAD responses (some sites reject HEAD or require authentication).
It does not verify fragments or redirect destinations. Reviewed URL-specific
exceptions belong in `external-link-exceptions.json` with a meaningful reason;
there are no initial exceptions. External outages or an exhausted audit budget
can fail that manually requested run, never every prose PR.
