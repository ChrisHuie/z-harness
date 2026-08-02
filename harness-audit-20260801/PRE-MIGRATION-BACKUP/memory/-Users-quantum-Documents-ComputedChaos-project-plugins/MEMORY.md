<!-- audit-2026-08-01 -->
> **STALE as of 2026-08-01.** Verified no longer accurate during the memory-consolidation audit. Kept for history; do not act on it.
> Evidence: (1) 'This machine does NOT have gh CLI authenticated' is FALSE: gh auth status reports 'Logged in to github.com account ChrisHuie (keyring)', active, with scopes gist/read:org/repo/workflow. The whole

# Project Memory

## Key Learnings

### gh CLI Auth & GitHub API
- This machine does NOT have `gh` CLI authenticated
- **DO NOT use** `.diff` URLs — `github.com/...pull/N.diff` redirects to `patch-diff.githubusercontent.com` which is unreliable (ECONNREFUSED)
- **USE** the GitHub API files endpoint: `https://api.github.com/repos/{owner}/{repo}/pulls/{N}/files` — works reliably, returns JSON with filename, status, and patch

### Background Agents & Permissions
- Background Task agents (run_in_background=true) get **auto-denied** on WebFetch and Bash tool permissions
- Always fetch PR data from the main conversation, not from background agents

### Prebid Server Review Skills (4 total)
- **pr-triage**: `prebid-server-go/skills/pr-triage/` — gateway orchestrator, runs FIRST
  - Fetches PR metadata once (file list, CI status, drift checks)
  - Categorizes files by skill ownership, detects PR type
  - Produces routing manifest consumed by all 3 downstream skills
  - Handles: CI status checking, cross-skill concerns, unowned framework files, bulk change detection
- **bidder-info-pr-review**: `prebid-server-go/skills/bidder-info-pr-review/` — YAML config files
- **bidder-params-pr-review**: `prebid-server-go/skills/bidder-params-pr-review/` — JSON schema, imp ext struct, params test
- **adapter-code-pr-review**: `prebid-server-go/skills/adapter-code-pr-review/` — adapter Go code, test runner, test data, registration
- All 3 downstream skills' Step 1 now receives triage data (no redundant API calls)
- File ownership is completely disjoint — no overlaps (except `openrtb_ext/bidders.go` shared between bidder-params + adapter-code)
- Cross-skill references are read-only
- All tested against real PRs; refined iteratively
- **Tested against 40 PRs total**: 20 new adapter PRs + 20 modification PRs
- **Live tested against 9 open PRs** with full 4-skill pipeline (triage → downstream)
- Key security rules: JSON injection via RawMessage, marshal error safety
- Key patterns: BidMeta/BidVideo extraction, Site/App parity, AMP test data, bulk change detection
- Breaking param changes must maintain backward compatibility
- `EndpointTemplateParams` has **19 fields** (not 8!) — always verify macros against full list
- Adapters must use `jsonutil.Marshal`/`Unmarshal`, not `encoding/json`
- Required schema fields must NOT have `omitempty` in json tags
- `jsonutil.StringInt` is the PBS-idiomatic type for `["integer","string"]` schemas
