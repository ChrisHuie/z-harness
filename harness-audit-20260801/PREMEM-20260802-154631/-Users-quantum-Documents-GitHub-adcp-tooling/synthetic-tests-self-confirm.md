---
name: synthetic-tests-self-confirm
description: "Test fixtures that mirror the parser's own assumptions are a self-referential oracle — pair them with a real-corpus fixture + a completeness oracle."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0ec17d38-47f0-44c3-8dba-412e46a45e03
---

A green suite over hand-written fixtures proves the parser parses ITS OWN fixtures, not that it reads the real input correctly. In the P2 overlay, the storyboard parser handled `check: error_code` only with `allowed_values:`; the canonical single-code `value:` form was silently dropped — and every test fixture used `allowed_values:`, so the suite stayed green while the headline recovery layer under-extracted against the real spec corpus (missed GOVERNANCE_DENIED, evaluator_auth, etc.). External review caught it, not the tests.

**Why:** this is the same self-referential-oracle trap the project disciplines against in its [[adcp-kernel-empirical-anchors]] recovery oracle — reproduced in the TEST layer, where it's easy to miss.

**How to apply:** for any extractor/parser, (1) commit ≥1 real fixture from the actual corpus (not synthetic), (2) add a completeness oracle asserting a structural invariant over real data ("every step asserting a code yields ≥1 recovery obligation"), and (3) when a tolerant parser silently skips malformed/unknown input, make the skip observable (count/warn/nonzero-exit) — a real-corpus fixture is the only thing that catches future schema drift.
