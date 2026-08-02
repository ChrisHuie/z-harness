---
name: rereview-preimage-underdetermination
description: Third independent implementation confirmed rereview PROTOCOL.md hash preimages are still underdetermined at e98cfdb; the v2 revision changed zero characters of the defective definitions
metadata: 
  node_type: memory
  type: project
  originSessionId: 2bb2b736-d400-4ce6-9fba-4f6c3e4aa6f7
  modified: 2026-07-31T13:28:24.886Z
---

At commit `e98cfdb` (2026-07-26) of rereview-agent, a third independent
implementation of four `PROTOCOL.md` hash preimages produced a third distinct
answer for `admission_core_digest` and `authority_anchor_id`, matching neither
prior implementer. The control `act_id` matched both byte-for-byte, validating
the framing library.

The non-obvious fact: the four preimage formula blocks are **byte-identical**
between `86f1448` and `e98cfdb`, and `## 14. Algebraic properties` is byte-identical
too, despite `PROTOCOL.md` growing 703 lines. The v2 response added *requirements*
(a registry schema, a §3 paragraph declaring "all fields except" invalid, vector
V226 demanding each law name an executable function) without adding the
*content* those requirements describe. No registry instance and no golden
instance exist anywhere in the tree.

Still true at `c4cde8c` (2026-07-27): schema present, instance absent. What did
change is that `governance/cross_check.py` now compares both implementations
with every argument position holding a distinct value, so an argument reorder
is caught *between the two implementations* — but not between either of them
and the protocol prose. The repo now carries this state itself, in
`design/GUARD-LIMITS.md` under "The gap the next round should close"; check
there first rather than trusting this line's date.

**Why:** this is the distinguishing signature to check for on any future revision
of this design — measure whether the defective text changed, not whether the
document grew.

**How to apply:** when re-reviewing a spec revision, diff the specific defective
constructs byte-for-byte against the prior baseline before reading any new
material. Related: [[feedback-adversarial-review-user-adjudicates]],
[[rereview-agent-goal-and-decisions]].
