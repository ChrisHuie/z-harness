---
name: no-real-names-in-db
description: "The DB stores only GitHub login handles, never real/display names"
metadata: 
  node_type: memory
  type: project
  originSessionId: 648b42ed-f7dd-4392-b314-9c15209dfd0d
---

The `github_activity.db` stores **only GitHub login handles**, never real names. Every
people-field is a login: `pull_requests.submitter`, `merged_by`, and the JSON
`reviewers` / `assignees` / `participants` — even `commits_breakdown[].author` is a
login, not a git author name. There is no display-name column in any table.

To get real names, enrich via the GitHub API: `GET /users/{login}` → `.name`. Coverage
is partial — as of the Q2 2026 report, ~57% (158/278) of active contributors/reviewers
had a public name set; the rest leave it blank or the account was renamed/deleted
(a 404 body can leak into stdout via `gh api`, scrub those).

Gotcha: macOS system `python3` fails TLS cert verification against api.github.com
(`CERTIFICATE_VERIFY_FAILED`) — drive `gh api` via subprocess instead of urllib.
