---
name: agentic-advertising — what this repo is
description: Project-level, language-agnostic documentation/versioning/compliance framework for AdCP Sales+Buyer Agents; markdown+YAML+JSONSchema in v1, React frontend in v2.
type: project
originSessionId: b20ae879-7b4d-4db0-b610-d3da63c2f4da
---
`/Users/quantum/Documents/GitHub/agentic-advertising` is a documentation
workspace, not a runnable system. It classifies AdCP-protocol decisions as
"atoms" with stances, version anchors, and a bidirectional cross-reference
graph. Bootstrapped 2026-05-10 from the planning workspace at
`/Users/quantum/Documents/RepoDocs/`.

**v1/v2 split (load-bearing):**
- v1 = markdown + YAML + 4 JSON Schemas + technical docs. No JS toolchain,
  no React. Lock the data model first.
- v2 = React frontend reading the v1 corpus as typed data (atom browser,
  drift dashboard, cross-reference graph). Audience: internal Prebid+AdCP
  contributors first, then public industry-facing. Out of scope until v1
  corpus stabilizes.
- Every atom validates against `schemas/atom.schema.json`. Every cross-ref
  uses stable atom IDs. Every citation is a typed object. The atoms/
  filesystem maps 1:1 to URL routes.

**Why:** User explicitly said "v1 shouldn't have a frontend. v2 should. We
will approach this once we have locked down the actual data and base for the
frontend with the schema/technical and etc documentation."

**How to apply:**
- Never add a JS toolchain, React app, or build step in v1. If asked to
  visualize, point at v2.
- All proposed automation (drift script, validator hook, CI) is also v2.
  v1 procedures in `tooling/` are intentionally manual checklists per
  genesis/04 line 200 ("don't design the drift mechanism before classifying
  anything").
- The atoms-as-data discipline is non-negotiable: every contributor change
  must pass `tooling/validate.md` (schema + lint + cross-ref) before commit.

**Related repos in user's filesystem (do not modify from this work):**
- `/Users/quantum/Documents/RepoDocs/` — the original planning workspace,
  now copied verbatim into `genesis/` of this repo.
- `/Users/quantum/Documents/ComputedChaos/salesagent/` — the Prebid Python
  sales agent reference implementation. Cited by overlays.

**Standing rules baked into the repo:**
- Local commits only; never `git push` or `gh issue create` without
  explicit instruction. (Per genesis/06 user preferences, codified in
  `genesis/README.md` and root `README.md`.)
- Salesagent's `pyproject.toml` pins `adcp>=3.12.0`, which is unsatisfiable
  on public PyPI (the published version sequence jumps `2.19.0 → 5.0.0`).
  Recorded as a downstream issue; do not "fix" from this work.
