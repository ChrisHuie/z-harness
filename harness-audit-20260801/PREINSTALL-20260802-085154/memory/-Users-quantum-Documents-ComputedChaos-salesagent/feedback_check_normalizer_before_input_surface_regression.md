---
name: feedback_check_normalizer_before_input_surface_regression
description: "Before claiming a handler change dropped a request field, trace the request-normalization middleware that runs upstream of every handler — it may already delete or rewrite that field."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b4f8139b-43a8-4409-ab66-71b047289efa
  modified: 2026-07-31T14:50:17.906Z
---

When a diff narrows a transport handler's input surface (e.g. `Model.model_validate(params)` replaced by a builder taking N named fields), the tempting finding is "field X is now silently dropped." That is a claim about the **whole request path**, not about the handler — and in this repo a normalization layer runs before every handler and may already have removed the field.

The miss: claimed an A2A handler regression because the new builder passed 4 of a request schema's 5 fields, and the `_impl` read the 5th to reject it. Proved it with a probe calling `Model.model_validate({"account_id": …})` directly — which bypassed `src/core/request_compat.py::normalize_request_params`, the all-tools translation that rewrites `account_id` → `account={"account_id": …}` and `del`s the original. It runs on A2A, MCP and REST before dispatch, so the old code never saw the field either. The change was behaviour-neutral; five reviewers independently falsified the claim.

**How to apply:**
- Probe the **entry point**, not the model. If the finding is "the buyer sends X and now gets Y", drive the path the buyer's bytes take, including middleware.
- `git grep <normalizer> -- src/` and confirm which transports call it and at what point relative to the handler.
- The generalizable form: a field-level regression claim needs the full upstream chain traced. A model-level probe answers a different question than the one being asked.
- What survived the retraction was the *generic* half — unknown/unmodelled fields are now ignored where the model previously rejected them. That half was real and independently confirmed. Narrow the claim to what the evidence supports rather than dropping it entirely.

Related: [[feedback_trace_flows_not_claims]], [[feedback_verify_before_asserting]], [[feedback_new_abstraction_needs_adoption_completeness]], [[feedback_subagent_mechanism_is_a_claim]]
