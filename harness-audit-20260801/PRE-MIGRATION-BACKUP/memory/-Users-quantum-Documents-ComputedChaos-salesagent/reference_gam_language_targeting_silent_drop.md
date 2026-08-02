---
name: reference_gam_language_targeting_silent_drop
description: "AdCP `language` targeting is a valid inherited TargetingOverlay field but the GAM adapter silently ignores it (No-Quiet-Failures violation)"
metadata: 
  node_type: memory
  type: reference
  originSessionId: c38325cd-848d-4ad8-ae47-80af5f386bbc
---

`language` is a real AdCP 3.1.0-beta.3 `TargetingOverlay` field (ISO 639-1 inclusion list, `targeting.json:385-391`) and is INHERITED into our internal `Targeting` (verified: `Targeting.model_fields` contains `language`). But the GAM adapter neither applies nor rejects it:

- `build_targeting()` (`src/adapters/gam/managers/targeting.py:650+`) has NO `language` branch. device/os/browser/content/keyword each `raise ValueError` (fail loudly, ~770-799); language just falls through → silently dropped.
- `validate_targeting()` (`targeting.py:608-648`) only checks device/media/city/postal — not language.
- `validate_unknown_targeting_fields()` (`src/services/targeting_capabilities.py:181`) only flags `model_extra` (typos/unknown names); `language` is a known field so it passes.

Net: a buyer sending package `targeting_overlay.language` passes all validation and gets NO targeting applied, NO error — violates CLAUDE.md "No Quiet Failures". This is package-level, distinct from creative-level ([[reference_gam_creative_level_targeting_exists]]).

Also note GAM device inconsistency (relevant to issue #1076): `validate_targeting` treats DEVICE_TYPE_MAP members as supported, but `build_targeting` unconditionally raises on any `device_type_any_of` (`targeting.py:771-775`) — so wiring the field alone won't work; the GAM technology-targeting build path is unimplemented.
