---
name: reference_verify_spec_skill_not_portable
description: "The verify-spec skill hardcodes another dev's local clones and a stale spec version; for ad-hoc PR spec-grounding, introspect the installed adcp models instead"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 72b5eab3-5772-4ea8-ac45-69eac1644028
---

`.claude/skills/verify-spec/SKILL.md` is NOT runnable as-is on this machine and is not a general PR-review tool:
- **Sources of Truth** are hardcoded to `/Users/konst/projects/adcp`, `/Users/konst/projects/adcp-client-python`, `/Users/konst/projects/adcp-req` (KonstantinMirin's clones) — absent here.
- It cites spec `3.0.0-beta.3`, while the repo pins **3.1.0-beta.3** (adcp==5.7.0) — stale.
- Its formula requires an entity test suite already produced by `/surface`; it STOPS at pre-check otherwise. It also *mutates* test files (adds spec permalinks), which is wrong for reviewing someone else's PR.

**For ad-hoc protocol-behavior spec-grounding, do what verify-spec prescribes but via the installed library** (its priority-2 authoritative source, present here): introspect the adcp Pydantic model. Verified this way that `BrandReference.domain` is lowercase-only by pattern `^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.…)*$` and `GetProductsRequest.brand` is Optional (`anyOf [BrandReference, null]`). Still ground the *contract* in the pinned spec prose (`dist/docs/<version>`), not SDK codes — see [[reference_adcp_spec_grounding]], [[feedback_ground_protocol_work_in_spec_not_assumptions]].
