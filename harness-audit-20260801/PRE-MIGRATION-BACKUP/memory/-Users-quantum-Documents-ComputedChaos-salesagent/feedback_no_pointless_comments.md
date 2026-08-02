---
name: No pointless comments
description: Don't add explanatory comments to code that is already clear — user considers them noise
type: feedback
originSessionId: d251b34a-4b19-48a0-aef6-7b61d23dab95
---
Don't add comments that explain how standard Python patterns work (e.g., mock patching, inline imports). The user considers these pointless noise. Only add comments when the logic is genuinely non-obvious.

**Why:** User rejected comment additions during a PR fix session, calling them "pointless comments."

**How to apply:** When reviewing or fixing code, resist the urge to add explanatory comments about mock targets, import patterns, or standard library usage. The code should speak for itself. If something truly needs explanation, keep it to the docstring, not inline comments.
