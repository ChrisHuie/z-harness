---
name: Always improve tests, never delete them
description: When a test category is dead or broken, resurrect it with better quality — never delete tests to close a gap
type: feedback
originSessionId: e8f76811-d8de-4454-a72d-4e19c77af704
---
When asked whether to delete dead/skipped tests vs. resurrect them, always default to resurrect-with-quality-improvements. User explicitly stated "We want to always have better and more robust testing. ALWAYS!"

**Why:** User views test robustness as a one-way ratchet — reducing the surface is a regression even when the tests are currently dead code. Fortune-50 posture means compounding quality, not trimming to minimum viable.

**How to apply:**
- For issue #1233 D11: resurrect the 22 `@pytest.mark.requires_server` tests with a proper CI job running against the e2e Docker stack + quality improvements, instead of deleting.
- Generally: when a plan offers "delete vs. resurrect" for tests, default to resurrect.
- When proposing fixes for broken tests, offer assertion strengthening, new edge cases, and structural guards in the same PR — don't just restore the prior state.
- If tests are genuinely obsolete (feature removed), confirm explicitly before deletion.
