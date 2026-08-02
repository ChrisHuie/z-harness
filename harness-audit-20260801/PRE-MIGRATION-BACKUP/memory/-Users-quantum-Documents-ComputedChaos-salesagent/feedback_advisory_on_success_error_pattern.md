---
name: feedback-advisory-on-success-error-pattern
description: "Per-item advisory Error(code=...) inside SUCCESS envelopes is legitimate (allowlist-permanent, not Pattern-A migration). Find the current sites by marker grep — `grep -rn 'structural-guard: advisory per' src/` — never by a remembered count (4→6 already drifted once)."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

(Site list re-verified 2026-06-11 by marker grep — the remembered "4 sites" had drifted to **6**, and one old citation (creative_formats.py) no longer carries an Error construction. Lesson folded in: enumerate these by the in-code marker, not from memory.)

Some `Error(code="...")` constructions are NOT Pattern A — they're legitimate per-item advisory errors inside success envelopes, for operations that process multiple items and report success-with-partial-results. Per-item failures belong in the success envelope's `errors[]`, NOT as a typed `raise` that aborts the whole operation. Spec grounding: error-handling spec prose — "Non-fatal errors populate only the payload... MUST NOT populate `adcp_error`".

**Current sites (2026-06-11, by `grep -rn "structural-guard: advisory per" src/`):**
- `src/core/tools/accounts.py` ×2 — per-account results in `SyncAccountsResponse.errors[]`
- `src/core/tools/media_buy_delivery.py` ×2 — per-buy results in `GetMediaBuyDeliveryResponse.errors[]`
- `src/core/tools/media_buy_list.py` ×1 — per-package results in `GetMediaBuysResponse.errors[]`
- `src/core/tools/creatives/_processing.py` ×1 — per-creative results in `SyncCreativeResult.errors[]`

**How to apply:** before migrating any `Error(code=...)` construction, check whether the surrounding code builds a SUCCESS envelope (`errors=[...]` advisory alongside results) or an ERROR envelope / `_impl` return shape. Success-envelope advisory → allowlist-permanent with the `structural-guard: advisory per-...` marker comment; error-envelope → migrate to typed `raise AdCPError`. Always re-derive the site list from the marker grep — counts in prose (including this file's) go stale.
