---
name: reference_gam_creative_level_targeting_exists
description: "GAM already implements creative-level targeting (LICA targetingName + line-item creativeTargetings) via publisher-side placement_targeting product config (adcp#208)"
metadata: 
  node_type: memory
  type: reference
  originSessionId: c38325cd-848d-4ad8-ae47-80af5f386bbc
---

GAM creative-level targeting IS implemented (adcp#208), driven by **publisher product config**, not buyer request. Don't assume it's missing.

- `PlacementTargeting` schema: `src/adapters/gam_implementation_config_schema.py:30` — part of `GAMImplementationConfig`, stored in products table `implementation_config`. Keyed `placement_id → targeting_name → raw GAM targeting dict`.
- Map built from all products' impl_configs: `src/adapters/google_ad_manager.py:682-700` (`_placement_targeting_map`).
- Line item `creativeTargetings` emitted: `src/adapters/gam/managers/orders.py:1007-1020`.
- LICA `targetingName` set (keyed on creative's `placement_ids`): `src/adapters/gam/managers/creatives.py:1069-1073`.
- Tests: `tests/unit/test_gam_placement_targeting.py` (~525 lines).

This matches the AdCP spec direction: `creative-assignment.json` finest per-creative discriminator is `placement_ids` (placement-level routing), NOT a per-creative TargetingOverlay. Buyer-driven per-creative *axis* targeting (language/geo per creative) is NOT in spec 3.1.0-beta.3 and would be an upstream proposal.

Contrast the INERT buyer field: `CreativeAssignment.targeting_overlay` (`src/core/schemas/creative.py:267`) exists in schema but NO adapter reads assignment-level overlay — adapters only consume `package.targeting_overlay`. Looks like "creative targeting implemented" but isn't wired. See [[reference_review_patterns]].
