---
name: pr1389-property-list-context
description: What PR
metadata: 
  node_type: memory
  type: project
  originSessionId: 745b1f81-2de5-41a5-8766-6e6a1442fa2d
---

<!-- audit-2026-08-01 -->
> **STALE as of 2026-08-01.** Verified no longer accurate during the memory-consolidation audit. Kept for history; do not act on it.
> Evidence: (1) Says the PR is on 'affinity-com/salesagent'. It is not: gh pr view 1389 -R affinity-com/salesagent returns 'Could not resolve to a PullRequest with the number of 1389'. affinity-com/salesagent is


**PR #1389** (`feature/property-list-targeting` → `main`, `affinity-com/salesagent`, worktree `salesagent-1389/`) adds end-to-end AdCP `property_list`/`collection_list` targeting: a buyer's `targeting_overlay.property_list` is compiled to native ad-server targeting (Kevel `siteIds`) or rejected with a spec-compliant `UNSUPPORTED_FEATURE` envelope — **never silently dropped**. ~79 files, +7,474/−1,794. Supersedes #1313/#1314/#1315.

Key seams:
- **Honest-declaration boundary**: each adapter declares `supports_property_list_targeting` (base default `False`; only Kevel `True`); `_impl` calls `raise_if_property_list_unsupported`.
- **Kevel compilation**: `KevelSiteResolver` (`src/services/kevel_site_resolver.py`) maps domain/subdomain identifiers → siteIds; site index cached in `ThreadSafeTTLCache` keyed by `(base_url, network_id, HMAC-PRF(api_key))` so tenants can't share an index; prewarmed off the event loop on create.
- **Two HTTP error paths** (don't conflate): adapter **writes** → `wrap_request_errors` (`requests` → always transient `AdCPAdapterError`, correct: ad-server outage is transient); buyer **list-fetch** → 4xx correctable / 5xx transient taxonomy.
- **Wire envelope** (`code`/`recovery`/`field`/`suggestion`) verified across REST/A2A/MCP; "no `Error(code=...)` construction in `_impl`" enforced by guard tests.

Known watch-items from independent read: `ThreadSafeTTLCache` has **no eviction** (slow unbounded growth); `identifier_matching` keeps a **deliberate SDK divergence** (`bbc.co.uk` won't select `www.bbc.co.uk`); update path defers **byte-for-byte submitted-replay** to the b6 idempotency branch ([[salesagent-worktree-layout]] → `salesagent-1312`). The PR body has a "Design decisions (locked)" section that pre-answers many review challenges — read it before flagging.
