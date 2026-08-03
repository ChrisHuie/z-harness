---
name: reference-bdd-harness-pitfalls
description: 9 BDD harness pitfalls (6 from PR #1274 triage, +2 from PR #1374 assertion-strengthening review, +1 from #1399 post-merge issue triage)
metadata: 
  node_type: memory
  type: reference
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

These are SPECIFIC failure modes the harness silently introduces. Use as a pre-check when:
- Adding a new validator (Pydantic `@model_validator` or similar)
- Adding new BDD scenarios that probe contract violations
- Investigating BDD failures that look like "production isn't rejecting X"

## 1. Harness silently fills test data, hiding contract probes

**Site:** `tests/harness/_mixins.py:560-572` (ProductMixin in `tests/harness/product.py`)

The harness applies "sane defaults" — if caller didn't supply `brief`, it fills `effective_brief = "test brief"` when buying_mode="brief". This DEFEATS any test trying to probe "what happens when buying_mode=brief without a brief?".

**Pre-check:** When adding a validator that requires field X, `grep tests/harness/*.py` for `caller_supplied_X` / `effective_X` / default backfill patterns of X. If the harness fills X when not supplied, contract-probe BDD tests through the impl transport will hit the harness's default before reaching the validator. Either:
- The harness needs an additional "caller supplied a DERIVING field" check (e.g., don't fill brief when buying_mode was caller-supplied)
- The contract-probe test must pass `brief=""` or `brief=None` explicitly to defeat the default

## 2. Wrapper drops `suggestion` when translating ValidationError

**Site:** `src/core/validation_helpers.py:104` (`format_validation_error(validation_error: ValidationError, context: str = "request") -> str`) + `src/core/schema_helpers.py:175-177` (wraps the string into `AdCPValidationError(str)` with `suggestion=None`)

`format_validation_error` returns only a string. `AdCPValidationError(format_validation_error(...))` has `suggestion=None`. But BDD feature files routinely assert `error should include "suggestion" field`.

**Pre-check:** Any new cross-field validator wired through `format_validation_error`-style helpers must also populate `suggestion=` explicitly (or via a mapping table from rule → suggestion). BDD `then_error_has_suggestion` step at `tests/bdd/steps/generic/then_error.py:236-244` is the contract.

## 3. Feature-file partition syntax variants need separate handlers

**Site:** `tests/bdd/features/BR-UC-001-discover-available-inventory.feature` has 4 different When-step phrasings:
- `with <invalid_fields>` (T-UC-001-ext-d field-prose)
- `with buying_mode configuration <partition>` (T-UC-001-partition-buying-mode)
- `under <partition> conditions` (T-UC-001-partition-brand-policy)
- `with <partition> field combination` (T-UC-001-partition-catalog-brand)

Each needs its OWN When-step handler OR a uniform `_PARTITION_KWARGS`-style mapping with multi-syntax detection.

**Pre-check:** When a feature file has multiple `Scenario Outline` blocks with `<partition>` placeholders, enumerate ALL distinct When-step text variants up front. Missing handler = silent default-request-then-empty-response failure (not an error — a silent pass-through that fails on the Then assertion later).

## 4. Impl transport ≠ wire boundary

Validators run at request construction (`GetProductsRequest`-extended type). The impl harness uses `GetProductsRequestGenerated(**kwargs)` which IS the extended type — except the harness pre-massages kwargs before constructing it. The pre-massage hides contract violations.

**Architectural insight:** The harness's `call_impl` should be a THIN proxy that exercises the same surface as MCP/A2A/REST. Currently it's "test-friendly" — fills defaults, drops some kwargs (`adcp_version` at `_mixins.py:546`) — which lets contract-probe failures slip past.

**Pre-check:** When CI shows `[mcp]/[a2a]/[rest]` failing but `[impl]` passing (or vice versa), the harness's impl path is doing something the wire transports aren't.

## 5. `then_error_has_suggestion` vs `then_error_has_fix_suggestion`

Two adjacent assertions in `tests/bdd/steps/generic/then_error.py:236-296` with subtly different contracts:
- `has_suggestion`: structural presence of `suggestion` field
- `has_fix_suggestion`: actionable verbs in the suggestion text

**Pre-check:** When adding validation errors, pick which contract the spec demands and document explicitly. Don't satisfy `has_suggestion` with `suggestion=" "` — the second step will fail.

## 6. Pre-existing main failures appear as "this branch broke things"

Sandbox cluster (5 of 41 PR #1274 failures) showed tests can fail on main and STILL appear in a branch's run because nothing previously demanded a clean BDD baseline. Branch gets blamed for pre-existing gaps.

**Pre-check:** Before triaging BDD failures on a branch, separate `git show main:<feature-file>` from current; identify scenarios that were ALREADY broken on main. Don't waste branch budget fixing pre-existing main bugs — file follow-up issues and xfail with citation.

**Verification command:** `git checkout main -- tests/bdd/features/<file>; git checkout @{-1} && pytest tests/bdd/test_X.py -k "..." 2>&1 | grep FAILED` then compare to branch.

## 7. Structural-guard PASS ≠ semantic strength (the AST guard can't see circularity)

`test_architecture_bdd_assertion_strength.py` flags STRUCTURAL weakness (hasattr / getattr-existence / count-only) via AST. A Then step can pass that guard — and have its allowlist entry removed to `set()` — while still being semantically vacuous. Three shapes seen in PR #1374's "strengthening" (all passed the guard):
- **Re-derives production's expression against the same source:** test computes `(raw_request or {}).get("buyer_campaign_ref")` — production's exact line — so both sides move together; under default factory data both are `None` → `None == None`, passes even if the production copy-through were deleted.
- **Asserts a harness-constructed invariant:** `totals == sum(packages)` where the harness builds the adapter total AS `sum(packages)` and production only copies it. The equality is guaranteed by the fixture + faithful copy-through, NOT by any production aggregation (there is none at that layer). Docstring saying "Aggregation" overstates it.
- **Input-echo of a Gherkin literal / hardcoded default:** asserts `probe_count == 1` where the When step set `probe_count = n` directly; or compares an echo against a hardcoded default (`interval=7`) the When step never recorded into ctx, passing only because the scenario happens to use 7.

**Pre-check:** for each "strengthened" Then, trace the asserted value to its SOURCE. If it traces to harness/Given/request/a re-derived production expression rather than an independently-chosen expected literal, it is still weak. The AST guard is necessary, not sufficient; manual data-source tracing is the authority on circularity.

## 8. Check `pytest_plugins` registration before calling a weak assertion "passes on broken production"

A vacuous assertion in an UNREGISTERED step module is DEAD (its scenarios xfail at the harness gate), not "passes on broken production." `tests/bdd/conftest.py` `pytest_plugins` is the live set; `test_architecture_bdd_step_module_reachability.py::_ALLOWED_UNREGISTERED` is the dead-list (e.g. `uc019_query_media_buys`, `uc002_nfr`). Calling a dead-module finding a live bug is a wrong claim — costly in front of a PR author who knows the repo (this misframed my first pass at the uc019 `buyer_campaign_ref` finding).

**Pre-check:** before relaying a weak/vacuous BDD assertion, confirm its module is in `pytest_plugins` (live) vs `_ALLOWED_UNREGISTERED` (dead). Frame a dead one as "weak AND not currently executing," not "passes on broken production." For a live one, distinguish "live-but-weak" (runs + passes; confirm by running the specific scenario) from "dead" — run the scenario and read PASS vs XFAIL, don't infer from an aggregate count. Complements [[feedback_detecting_subagent_overconfidence]] (subagent line refs drift; reachability claims need re-checking).

## 9. Two distinct silent-xfail gates — a step-def-only PR can't flip a scenario whose UC has no harness branch

A BDD scenario can xfail (green in CI, since xfail = pass) at EITHER of two independent gates:
- **Step registration** (pitfall #8): module not in `pytest_plugins` / listed in `_ALLOWED_UNREGISTERED` → scenario xfails.
- **Harness dispatch:** `tests/bdd/conftest.py::_harness_env` (autouse) routes per `_detect_uc`; a UC with NO branch hits `else: pytest.xfail("No harness wired for {uc}")`, so `ctx["env"]` is never set and the scenario xfails before any step runs.

A PR that adds only step definitions clears gate 1 but NOT gate 2 — its scenario still xfails, and CI stays green. So a PR claiming "flips scenario xfail→pass" is UNVERIFIED until you run the specific scenario and read `passed`, not `xfailed` (`tox -e bdd -- -k <scenario>`).

**Authority = per-UC outcome counts in the latest `test-results/<ts>/bdd.json`**, not the runner tail. 2026-06-16 observation (post-#1399 merge): UC-004/005/011 have a `_harness_env` branch and pass; UC-003 (1878 scenarios), UC-019 (973), UC-026 (974) had NO branch → 100% xfail. Their harness wiring was in flight (UC-003 in PR #1417; UC-019 on an unmerged branch). Re-verify currency before relying on these counts.

**Pre-check:** before reviewing or claiming a BDD scenario passes, grep `_harness_env` for the target UC's branch. No branch → the scenario xfails regardless of step defs; the harness wiring must land first. Complements [[feedback_claimed_invariant_needs_failing_oracle]] and [[run_all_tests_congratulations_masks_failures]].

## See also

- [[reference_bdd_harness_patterns]] — 24-pattern catalog
- [[reference_review_patterns]] — review patterns
- [[feedback_no_alarm_mid_operation]] — don't panic on transient state

---
**Currency note (2026-06-11 drift audit):** the reachability guard exists at `tests/unit/test_architecture_bdd_step_module_reachability.py` (verified via git ls-files). Line-number citations in this file (e.g. _mixins.py ranges) drift — re-derive by symbol. PR #1384 (BDD 3.1 re-render) post-dates these pitfalls; re-verify feature-file specifics.
