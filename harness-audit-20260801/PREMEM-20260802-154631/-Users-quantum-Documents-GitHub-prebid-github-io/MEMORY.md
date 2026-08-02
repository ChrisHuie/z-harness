<!-- audit-2026-08-01 -->
> **STALE as of 2026-08-01.** Verified no longer accurate during the memory-consolidation audit. Kept for history; do not act on it.
> Evidence: The migration is dormant. The docusaurus branch tip is 554b94fd dated 2026-02-28, while master is at 2026-06-18 and the working tree is checked out on add-prebidjs-logo-to-pages with a pure Jekyll lay

# Prebid.github.io Project Memory

## Project Context
- Jekyll → Docusaurus 3.x migration on `docusaurus` branch
- CLAUDE.md, MIGRATION_PLAN.md, MIGRATION_SUMMARY.md, MIGRATION_TRACKING.md exist at project root
- User prefers surgical doc updates — don't replace existing sections, integrate new info into them

## Key Facts
- Main docs plugin uses `path: "docs/content"` with `routeBasePath: "/"` (NOT `exclude` pattern)
- 5 separate doc plugins with auto-generated sidebars
- Build strict: `onBrokenLinks: "throw"` — any broken link fails the build
- Build currently broken: 472 errors from footer `/docs/intro` and `/blog` template defaults
- CI runs markdownlint on PRs via GitHub Actions
- Phase 4 mostly complete: ~367 Prebid.js files migrated, 5 deferred (need custom components for `site.pages` queries)
- Phase 4 deferred files: modules/index.md, modules/userId.md, modules/consentManagementUsp.md, modules/consentManagementGpp.md, pbs-bidders.md
- Phase 5 complete: 70 Prebid Server files migrated, build passes successfully
- PBS migration required post-processing: {%raw%} tag stripping, link prefix rewriting (/prebid-server/ → /dev-docs/prebid-server/), MDX fixes (self-closing HTML, escaped braces, image CSS markers)
- Migration script doesn't handle: `{:class="..."}` image CSS markers, `{%raw%}` tags, link prefix changes — need manual post-processing

## Migration Edge Cases
- 21 files use `{% capture %}` + alert pattern (36 instances)
- 5 files need full manual conversion (Liquid `site.pages` queries)
- 17 files include reusable markdown fragments from `_includes/dev-docs/`
- 1 HTML file in dev-docs needs special handling
- `static/images/` already has copies of assets — image paths rewrite to `/images/...`

## User Preferences
- Don't delete/replace existing doc content — add to it surgically
- URL preservation: keep `/download` and `/` only, dev-docs can change
- User wants plans documented in project files before executing
