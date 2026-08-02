---
name: reference-adcp-spec-grounding
description: "How to ground AdCP/protocol behavior in the ACTUAL version-pinned spec (prose + conformance storyboard), not SDK codes/types/reference-impls, internal contract items, or assumptions. Which version is authoritative + where the spec lives."
metadata: 
  node_type: memory
  type: reference
  originSessionId: f05442f8-8f3d-4746-a9f7-7a5971e6b984
---

To know what an AdCP behavior MUST do, read the spec text for the **authoritative version** — never infer behavior from SDK error codes, Pydantic types, SDK reference impls, or internal contract items.

**Which version is authoritative (check this FIRST, every time):** the version the repo currently PINS is the default ground-truth — UNLESS there is active work to comply with a DIFFERENT target version (a version bump / migration in flight), in which case that TARGET version is the pin to ground against. Confirm which of the two applies before grounding; never ground against a version that is neither the current pin nor the declared migration target. Current pin: `adcp==5.7.0` = spec **3.1.0-beta.3** (bumped in #1399; the pin MOVES — always verify, never quote this literal). Verify: `uv run python -c "import adcp; print(adcp.get_adcp_spec_version())"`.

**Where the authoritative spec lives** (`github.com/adcontextprotocol/adcp`):
- Prose behavioral contracts (idempotency, error-handling, governance): `dist/docs/<version>/building/implementation/*.mdx` — immutable per-version snapshots; compare folders to see when a rule entered.
- Conformance STORYBOARD (the *executable, graded* contract): `dist/compliance/<version>/...*.yaml`. This is what a conformance runner actually checks — when prose and storyboard differ in emphasis, the storyboard is what's GRADED (e.g. it may grade an error CODE but NOT its recovery class, which leaves you free to match the SDK validator there).
- `CHANGELOG.md` records when rules changed + real conformance-runner failures.
- Schemas (normative field text — easy to miss): `dist/schemas/<version>/**/*.json` `description` fields carry version-timing rules, e.g. `core/targeting.json` `property_list` ("SHOULD return a validation error") and `get-adcp-capabilities-response.json` `request_signing` ("Optional in 3.0 — capability-advertised ... Required for spend-committing operations in 4.0").
- Fetch VERBATIM and read it YOURSELF: `gh api repos/adcontextprotocol/adcp/contents/<path>?ref=main --jq .content | base64 -d`. **Do NOT trust WebFetch's summarized answer for normative MUST / version-timing questions** — its fast-model extraction is unreliable: this session three WebFetch passes contradicted each other AND the schema on whether request-signing is mandatory at 3.1 vs 4.0; the verbatim source settled it (optional through 3.x, mandatory at **4.0**). WebFetch is fine for "where does X live"; gh-api-raw is the authority for "what does X require." Blob-by-SHA fallback if `contents` 404s; a `dist/docs/<version>/` folder can be ABSENT at its own tag (pinned prose = latest prior snapshot). Doc layout moved to `building/by-layer/L1..L3/` in 3.0.12+.
- Version anchor (drifts — re-check via repo `package.json`): the #1388 migration LANDED (#1399) — pin now **5.7.0 / spec 3.1.0-beta.3**; re-check repo HEAD spec via `package.json` (was 3.1.0-rc.13).

**Critical distinction (the trap):** the SDK ships error CODES, types, AND — for some behaviors — full EXECUTABLE REFERENCE impls (`adcp.server.idempotency.IdempotencyStore` is the whole success-caching middleware, not just hash primitives). Those are a useful READ-ONLY semantics cross-check, but they are NOT the graded contract and CAN diverge from the spec (#1312: SDK `STANDARD_ERROR_CODES` recovery said `terminal`, prose said `correctable`; the storyboard graded code-only, so terminal was fine). PROSE + STORYBOARD = ground-truth; the SDK is a cross-check, not the authority. A code existing in the SDK tells you nothing about WHEN to emit it.

**The AdCP 3.0.1 idempotency contract (verified verbatim):** key REQUIRED on every mutating request (missing → `INVALID_REQUEST`/`VALIDATION_ERROR`, validated before cache lookup); cache **successes only** (errors NEVER stored, retry re-executes); exact replay → top-level `replayed: true` (byte-for-byte original success); same key + different canonical hash → `IDEMPOTENCY_CONFLICT`; evicted past `replay_ttl_seconds` → `IDEMPOTENCY_EXPIRED` is OPTIONAL (only when the seller can distinguish evicted-vs-never-seen); scope `(agent, account, key)`; per-(agent,account) insert rate-limit → `RATE_LIMITED`. PR #1312 built the inverse (cache+replay rejections) — see [[feedback_ground_protocol_work_in_spec_not_assumptions]].

The stronger lever than this memory is a CLAUDE.md gate requiring protocol-behavior PRs to cite spec section + version before implementation — see [[feedback_escalate_recurring_lessons_to_guards]]. Salesagent IS the AAO Python reference impl ([[reference_adcp_sdk_spec_mapping]]), so conformance is load-bearing, not aspirational.
