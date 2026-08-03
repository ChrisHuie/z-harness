# REGISTRY GAP PASS — the 35 unregistered sources, R310–R340

Continues `PRINCIPLE-REGISTRY.md`'s ID space and format. Nothing in that file, in any skill,
or in `~/.claude/CLAUDE.md` was edited by this pass.

> **Update 2026-08-02 (post-ship audit):** of the 7 IN rows below, the two CLAUDE.md rows
> (R317, R319) were applied by the final assembly; the five skill-destined rows (R321,
> R329, R330, R334, R335) were applied nowhere as of this note.

## Headline

| | count |
|---|---:|
| Sources audited | **35** |
| **Already covered — the only defect is a missing `merged-from` citation** | **13** |
| **Contribute ≥1 principle registered nowhere** | **22** |
| — of those, substantial (rank A, or a rank-B rule with its own mechanism) | **17** |
| — of those, thin residues of an otherwise-covered file | **5** |
| New rows written below | **31** (R310–R340) |
| New rows IN | **7** · CLAUDE.md 2 · craft-context-file 3 · craft-skill 1 · outbound-drafts 1 |
| New rows OUT | **24** · 12 `→refs` (testing-ci 5, pr-review-method 6, agent-dispatch 1) · 12 CLAUDE.md queue |

**Two of the four "zero occurrence" results were instrument artifacts, not gaps.** The check
searched `S#nn` and full file stems; the registry writes neither.

1. **`S#13` is registered.** R309's `merged-from` reads `S#1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 13,
   16, …` — only the first entry carries the `S#` prefix. A matcher on `S#13` returns zero over
   a row that contains it. Verified: `grep "R309" | grep -E "[ ,]13,"` → 1 hit.
2. **11 of the 15 PROJECT stems are registered under truncated keys.** The registry abbreviates
   `P:agentdb_persistent_schema_masks_fresh_db_failures` to `P:agentdb_persistent_schema`,
   `P:corpus-contradictions-are-cross-file-and-untooled` to `P:corpus-contradictions`, and so on.
   Verified by prefix match:

   | full stem (0 hits) | truncated key present in |
   |---|---|
   | corpus-contradictions-are-cross-file-and-untooled | R043 R127 R244 R245 |
   | agentdb_persistent_schema_masks_fresh_db_failures | R106 |
   | feedback_a2a_wire_tests_must_drive_on_message_send | R086 R251 |
   | feedback_check_normalizer_before_input_surface_regression | R014 R086 |
   | feedback_mock_only_tests_dont_prove_wiring | R086 R252 |
   | feedback_run_full_suite_before_every_push | R080 R108 R125 |
   | harness_error_wire_per_transport_mechanics | R083 R087 R118 |
   | no_concurrent_agentdb_during_full_integration_run | R082 R105 |
   | reference_gam_creative_level_targeting_exists | R053 |
   | reference_gam_language_targeting_silent_drop | R053 |
   | reference_harness_freshness_mechanisms | R001 R044 R073 R098 R127 R128 |

3. **Two more are already WRITTEN but never registered** — a different failure. `drafts/final/
   system-design/references/deferred.md` carries `project-transport-and-comms` in full (all five
   clauses, §"Protocol and transport seams", lines 116–126) and
   `feedback_valueerror_boundary_vs_internal` in full (§"Typed boundaries and errors", lines
   130–135). `system-design` has no section in `PRINCIPLE-REGISTRY.md` at all — §16.4 records it
   as "a container the fixed set does not include" — so its body and deferred file were written
   outside the registry's ID space. **Every `system-design` rule is unregistered by construction;
   these two are the only ones this brief happened to name.**

**Citation convention added by this pass:** `C:<stem>` — a file `route.py` routed to
`~/.claude/CLAUDE.md`. The registry had no prefix for that bucket because none of its 309 rows
came from it.

---

# 1. Already covered — citation-only fix, no new row (13)

Add the source to the named row's `merged-from`. No principle is at risk.

| source | covered by | evidence |
|---|---|---|
| `S#13` | **R309** + `CM:L57-59` verbatim ("Tell background agents to SendMessage their report — a finished agent may idle instead of delivering. Never Read its `.output` symlink") | inside R309's comma-list |
| `P:agentdb_persistent_schema_masks_fresh_db_failures` | **R106**, and written at `testing-ci/references/deferred.md` §Environment | truncated key |
| `P:feedback_a2a_wire_tests_must_drive_on_message_send` | **R086** (clause 1) + **R251** (clause 2) | truncated key |
| `P:feedback_check_normalizer_before_input_surface_regression` | **R086** (clause 1) + **R014** (clause 2) | truncated key |
| `P:feedback_run_full_suite_before_every_push` | **R108** (1,2,3,5) + **R080** (6) + **R125** (4) — all six | truncated key |
| `P:harness_error_wire_per_transport_mechanics` | **R087** (1) + **R083** (2) + **R118** (3); clause 4 ("a reviewer's 'just use the uniform API' can rest on a false premise") is **R032** | truncated key |
| `P:no_concurrent_agentdb_during_full_integration_run` | **R105** (1) + **R082** (2) | truncated key |
| `P:project-transport-and-comms` | **written in full** at `system-design/references/deferred.md:116-126`, all 5 clauses | read directly |
| `P:feedback_valueerror_boundary_vs_internal` | **written in full** at `system-design/references/deferred.md:130-135`, incl. the call-graph discriminator and the catch-all translator | read directly |
| `D:feedback_no_blockquote_for_pasteable_text` | **R215**, clause-for-clause including the request discriminator ("draft a comment for" vs "what's the status") | source file read; matches R215 |
| `D:user_profile` | `CM:L19-27` + `CM:L73-77`, item by item — handle, author-name caveat, agent-team model, no-beads + validate commands, Docker novice, push ownership, no fork/clone | source file read |
| `D:feedback_subagents_need_explicit_read` | `CM:L55-57` verbatim (Step-0 read list, absolute paths, "citing filenames does not make a subagent read them") + **R179** for the mechanism | source file read |
| `C:feedback-no-self-declared-convergence` | **R173** (power-validate, diverse-prior searchers, the permissible-claim wording, claimant never authors the criterion) + **R210** (self-attestation) — independently re-derived in `temporal-backbone-design` | source file read |

**Sharpening noted, not registered:** `C:feedback-no-self-declared-convergence` clause (1) says the
acceptance criterion is set or blessed by **the user**; R173 says only "the claimant never authors"
it, which a third party also satisfies. R008 delivers the user-approval scope. Judged covered.

---

# 2. New rows — R310 to R340

| id | principle | dest | rank | IN/OUT | merged-from | notes |
|---|---|---|---|---|---|---|
| R310 | **The verification contract ESCALATES on the first surprise** — skipping the gate once is fine; skipping it *after* a skip already burned you this session is the failure. Track skips across the session, not per commit; the urge to skip because "we're so close" IS the signal | testing-ci | A | OUT→refs | S#113, D:feedback_thoroughness_over_momentum(5) | **Cross-bucket merge**: the SKILL row and the DELETE file are one mechanism, derived independently. Absent from CLAUDE.md, from all four bodies and all four deferred files (grep: `avalanche\|verification bar\|after the first surprise` → 0 hits over 14 draft files). **Dissent:** Gate 2 A2 fires — no request will name the topic, and the rule's whole job is to fire when the cue is absent. If CLAUDE.md ever gets a line back, this is a candidate |
| R311 | **Verification authority lives OUTSIDE the model** — "I tested locally and it passes" is one observation, not a verification; the gate, the CI verdict and the user reading the diff are the verifications. Describe state; do not grade it | CLAUDE.md | A | OUT | D:feedback_session_workflow_rules(W3) | The brief's named worst case, **confirmed absent**. `CM:L92-93` names `gh pr checks` as "CI's actual verdict" and `CM:L150` requires the same instrument — neither states that the authority is external. This is the load-bearing half: without it, every other verification rule can be satisfied by the model grading itself |
| R312 | **Re-read the prior decisions before each substantial action** — do not generate the next action from the most-recent context alone; cross-check it against what was agreed earlier | CLAUDE.md | A | OUT | D:feedback_session_workflow_rules(W6) | Genuinely absent. `CM:L99-100` re-verifies the *premise* (assumption stack ≥2); this re-verifies the *commitment*. Different failure: the premise stays true while the plan silently drifts. Binds hardest in long agent sessions, which is this corpus's whole shape |
| R313 | **Label observation vs inference in your OWN prose, and tag an unavoidable prediction explicitly** — "I ran X, output Y", then optionally "I infer Z"; never "Z is true" without the observation that backs it | CLAUDE.md | B | OUT | D:feedback_session_workflow_rules(M4, M5) | R187 is the delegate-scoped twin and is IN `agent-dispatch`; `CM:L66-69` applies it to subagent output. The self-scope version exists nowhere — the same asymmetry as R218 vs `CM:L170`. 1 line if merged into `CM:L96-98` |
| R314 | **Name a divergence BEFORE acting on it, not after** — "I want to do X, we agreed on Y; switching to Y, or is X the new plan?" | CLAUDE.md | B | OUT | D:feedback_session_workflow_rules(M7, W2 residue) | `CM:L37-38` has this for *method* substitution inside a dispatch ("the cardinal sin is the hidden downgrade"). The general form — any deviation from an agreed plan, any turn — is absent, and `CM:L122`'s "restate the contract" stops short of the call-out |
| R315 | **Test scope is chosen by change CLASS, not by what you expect to break** — schema/type/wire ⇒ the full gate; cross-file ⇒ the gate plus integration; single-file ⇒ scoped run. Never let a narrow run imply "fully tested" | testing-ci | B | OUT→refs | D:feedback_session_workflow_rules(M2), D:feedback_verify_before_asserting | `CM:L100` carries exactly one rung of the ladder (merge/rebase/wire-shape ⇒ full gate). The class→scope mapping is the part that makes it decidable |
| R316 | **One change at a time per multi-turn segment — finish it or hand it off cleanly before starting the next**; each concurrent piece carries context that drifts | CLAUDE.md | C | OUT | D:feedback_session_workflow_rules(W4) | Weakest of the W-set. `CM:L107` is scope-per-PR, `CM:L122` is steps-within-a-task; neither is changes-per-session. Registered so the deletion does not silently drop it; would not spend a line on it |
| R317 | **Do not append the `Co-Authored-By: Claude` trailer to commit messages, even though the harness default instructs it** — these are the user's own contributions to public repos under their name. Already pushed: offer amend + `--force-with-lease`, never assume | **CLAUDE.md** | A | **IN** | C:feedback_no_claude_coauthor_trailer | **Highest-stakes single row in this pass.** Gate 2 A1 (must hold before the first `git commit`) **plus the Gate 2 strengthener** — verified live: this session's own system prompt reads "End git commit messages with: Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>". A rule that counteracts an always-on harness instruction must sit in the same context window as it; a skill body loaded on a git cue arrives after the default has already been obeyed. Absent from CLAUDE.md and from all 14 draft files (grep `Co-Authored` → 0). Wrong artifact: an irreversible public commit under the user's name. **Eviction: R003** (transient file state during an in-flight VCS/hook operation) — its consumer is a git-cued dispatch, so its A2 argument is the weakest of the eight IN rows, and `git-workflow` R141–R143 already carry the mechanism at body level. Remedy half (amend + `--force-with-lease`, and `CM:L73-77` forbids the push) → `git-workflow` refs |
| R318 | **No durations, time estimates or timeframes on any deliverable** — sequence by dependency and risk, never by speed; never label a deliverable quick / thin / demo to save time. Applies to responses *and* to authored repo and strategy documents. Hard external dates that are real dependencies are facts, not estimates | CLAUDE.md | A | OUT | C:feedback-dont-reference-time | **First in the OUT queue, ahead of R009.** Absent (grep `two weeks\|timeframe\|duration` → 0 across the drafts; nothing in `CM:L111-126`). Rank A because it ships into authored strategy documents, not just chat. Also a **Gate-1 TOOL candidate**: T1 passes (a vocabulary gate over bytes), T2 passes (the pattern list is not authored by the checked party); T3/T4 need the corpus. Related but distinct from R013 — "defer to a follow-up" is a time-shaped *smaller option* |
| R319 | **Register matches the domain: dense for strategy, market and protocol; plain for infrastructure** — explain the problem in plain English with a concrete example before any acronym, and **never ask the user to adjudicate a technical trade-off in vocabulary they do not hold**. Make the under-the-hood call and flag it in one sentence; escalate only when the choice has strategic stakes | **CLAUDE.md** | B | **IN** | C:user-plain-language-for-infra | **Cheapest IN row in the pass — net +1 line, not +2.** `CM:L20` ("Docker novice. Explain what a step does and why") is one *instance* of this rule; rewriting L20 as this general form absorbs it. The absent half is the decision rule ("do not make them adjudicate in a vocabulary they lack; make the call and flag it"), which interacts with the permission boundary at `CM:L82-86`. Grep `acronym\|plain English` → 0 across drafts |
| R320 | **After a milestone or a completed stage, report the outcome and stop** — do not reflexively pitch the next task, and never re-pitch a crossing the user has not authorized. Match the pace; landing at a finished milestone with no forward proposal is the correct shape | CLAUDE.md | B | OUT | C:feedback-dont-be-eager-to-advance, C:feedback-pace-and-presentation(a) | **Cross-silo merge — two independently recorded user corrections in different projects**, which is the strongest T3-analog evidence in the CLAUDE.md six. `CM:L119-120` bans "soft sign-offs" (partial coverage of the shape) but not the act of pitching forward. Distinct from R008: R008 is the hard gate on *crossing*, this is the ban on *nudging toward* it |
| R321 | **When asked to "see" or "show" something, presentation IS the deliverable** — comprehensive and structured, a rendered artifact when the content has structure, never a terminal dump | outbound-drafts | B | **IN** | C:feedback-pace-and-presentation(b) | 1,900 B of headroom in this body. `CM:L118-120` has "more structure, not less content" but neither the show/see trigger nor the rendered-artifact channel. Sits beside R217 (the artifact is the deliverable, surfaced in the response) |
| R322 | **Internal tooling metrics are not findings** — "25 call sites", "0 grep hits", round counts and fan-out numbers describe your instrument, not their project. State the consequence in the user's terms | CLAUDE.md | B | OUT | C:feedback-pace-and-presentation(c2) | **Scope extension, not a duplicate.** `CM:L113-116` and R211 both ban detector names and provenance **for GitHub-bound artifacts**. This clause applies to every response to the user. The other half of the same source — reassurance/softening closers — IS covered at `CM:L119-120` |
| R323 | **Adversarial structure by default on substantive work — independent draft, then an attack pass that refutes with MEASUREMENT — and contestable findings go to the user for acceptance, never auto-applied** | agent-dispatch | A | OUT→refs | S#36 | **Records a live conflict**: the first clause contradicts `CM:L31` ("Default is a SINGLE pass, ZERO spawned agents"). `SKILL-121-split.md` flagged it at extraction and the conflict was never adjudicated. The *second* clause — the user adjudicates contestable findings rather than the agent applying them — is not in conflict, is absent everywhere, and is a permission boundary in the shape of R008. **Recommend splitting**: the adjudication half is the part worth carrying; the adversarial-default half stays refused under CM:L31 and should be recorded as refused, not silently dropped |
| R324 | **Mechanism-correct, contract-satisfied and downstream-safe are three separate axes** — trace the CHANGED VALUE into its downstream consumers, not just its construction: a "safe" default can be wrong three calls later | pr-review-method | A | OUT→refs | S#64 | The headline phrase "the issue's behavioral done-contract" *did* land in the body at R038 (`pr-review-method/SKILL.md:77`), but S#64 is in no row's `merged-from` and the downstream-trace axis was dropped between `drafts/pr/SKILL.md:81-82` and the final body. The below-the-boundary axis is R086. **Only the downstream-value trace is genuinely homeless** |
| R325 | **On a re-review, diff the specific DEFECTIVE CONSTRUCTS byte-for-byte against the prior baseline before reading any new material** — measure whether the defective text changed, not whether the document grew (703 lines added, defect blocks byte-identical) | pr-review-method | A | OUT→refs | P:rereview-preimage-underdetermination(1) | R018 says proof of "addressed" is a diff at the item's `path:line`; this adds the ordering (before new material) and the prose-artifact failure mode (growth read as repair). Grep `byte-for-byte` → 0 across all drafts |
| R326 | **A revision can add REQUIREMENTS describing content without adding the CONTENT** — a schema with no instance, a law with no executable function. Check for the instance, not the requirement | pr-review-method | A | OUT→refs | P:rereview-preimage-underdetermination(2) | Near-neighbour of R053 (a declaration with no consumer) but a distinct object: R053 is a field nothing reads, this is a requirement nothing instantiates. Also the dual of R027 (a consolidation that does not delete the duplicates) |
| R327 | **Include a CONTROL that should MATCH** — when three implementations disagreed on two fields the byte-identical control is what proved the instrument was sound and the subject was at fault. Without it, every disagreement is ambiguous between the two | testing-ci | A | OUT→refs | P:rereview-preimage-underdetermination(3) | The **dual of R173's power validation**: R173 seeds a known *flaw* and requires the instrument to find it; this seeds a known *match* and requires the instrument not to invent a difference. Both are needed and neither implies the other. Strongest single row in this pass |
| R328 | **A mock returns a plain object with no lifecycle, so a lifecycle bug passes green while production takes the invalid path** — lifecycle needs a test against the real resource. Review scan: any attribute access on a scope-returned object after the dedent | testing-ci | A | OUT→refs | P:feedback_uow_detached_after_exit | The scope-exit half of this file **is** written (`system-design/references/deferred.md:136-139`); the *test-vacuity* half is not. It is a **fourth vacuity shape** alongside R081's three (re-deriving production's expression · a harness-constructed invariant · echoing an input literal) and the only one where the mock's *type* rather than its *value* is what lies |
| R329 | **A harness or detector artifact must never hardcode a version — derive it at runtime** — otherwise the harness commits the sin it exists to catch, validating against a stale proxy instead of the derived source of truth | craft-skill | A | **IN** | P:reference_harness_freshness_mechanisms(1) | 3,100 B of headroom. The only clause of this 7-clause file with no home: (2)→R098, (3)→R001/R073, (5)→R128, (6)→R044, (7)→R127, and (4) ("a derived authority lags its source and silently FORCES a less-precise substitute") is **R272** — add the source there too |
| R330 | **Exclude deliberately-frozen snapshot inputs from a staleness check**, or the check reports drift it was built to ignore | craft-context-file | B | **IN** | P:corpus-contradictions-are-cross-file-and-untooled(5) | The other four clauses are R244, R245, R043, R127. 2,500 B of headroom; sits with R245 (a corpus check must fail loud when its anchors go missing) as its false-positive counterpart |
| R331 | **The wiring gap is mechanically countable**: new real-entry-point calls in the diff vs new error-path tests — zero on an error-path change is the gap, with an explicit carve-out for pure helper and schema tests | testing-ci | B | OUT→refs | P:feedback_mock_only_tests_dont_prove_wiring(2) | Clauses 1 and 3 are R086 and R252. **This is the corpus's second asserted Gate-1 TOOL candidate** after R024 — T1 passes (counts from the diff), T2 passes (the count is not chosen by the author). T3/T4/T5 unevaluated. The registry records only one TOOL candidate; that count is low by at least this one |
| R332 | **A capability can be driven by the OTHER party's configuration rather than by your request** (check their config path before declaring it missing), **and a validate path that says "supported" beside a build path that unconditionally raises means wiring the field alone will not work** | pr-review-method | B | OUT→refs | P:reference_gam_creative_level_targeting_exists(2), P:reference_gam_language_targeting_silent_drop(2) | **Cross-source merge** of the two files' second clauses; their first clauses are both R053. One mechanism: the declaration surface and the execution surface disagree, and the direction of the disagreement decides the remedy |
| R333 | **When editing at a boundary, read the WHOLE file, not the diff hunk** — wire, error and transport code has invariants the hunk cannot show | pr-review-method | A | OUT→refs | D:feedback_verify_before_asserting | The one genuinely uncovered clause of that file (see §3). R041's "an excerpt is not the file" is its review-time twin; this is the edit-time form and the two belong adjacent |
| R334 | **A triage or consolidation pass records its deliberate NON-merges, or the next pass silently undoes them** — the negative decisions are the perishable half of a triage artifact | craft-context-file | B | **IN** | D:project_backlog_triage_2026_07 | The one travelling principle in a file otherwise made of dated instance. Sits with R250 (amend a standing decision row when a change makes its wording false) and R037 (de-dup is not synthesis). **Gate 5 verdict: the file itself is NOT memory** — it is volatile state whose expiry event cannot be named ("re-verify issue states before acting" is not an event), and per Gate 5 that makes it durable-or-a-note, not memory |
| R335 | **Narrower is stickier: ban one short word rather than write a workflow rule** — the friction of typing the longer replacement is the mechanism, because it forces the missing fact to surface | craft-context-file | B | **IN** | D:feedback_no_ready_claims | Rule-design guidance for the very file being authored. `CM:L90-94` carries the *content* of this file completely (banned list, raw state, both commands); the **design rationale for why a one-word ban outperformed a workflow rule** is the residue, and it generalises to every gate in the corpus. Adjacent to `CM:L176-178`'s leverage ladder |
| R336 | **Two plan-mode harness facts**: the plan file is the only writable surface, so a viewable sample must be embedded inside it; and the question tool is for clarifications and trade-off choices — asking it "is this plan ready / should I proceed" is the plan-exit tool's job | CLAUDE.md | B | OUT | D:feedback_iterative_planning(b,c) | Harness mechanics with no cue ⇒ Gate 2 A2. R004 already put the sibling `AskUserQuestion` fact (a timed-out question is not an answer) in CLAUDE.md, so this is the same channel. **Note the destination-set gap**: these are MACHINE-class and the fixed set has no MACHINE row; `agent-dispatch/references/claude-md-lines.md` records the same problem for R276/R275/R283 |
| R337 | **"One final pass" means a thorough verification round, not ship-now** — a non-trivial plan is expected to take 2–3 rejection rounds; a first plan submission is a draft | CLAUDE.md | B | OUT | D:feedback_iterative_planning(a) | `CM:L82-86` has the approval gate and nothing about the expected round count or the word "final". Distinct from R320: R320 is about not pitching forward; this is about not reading a user's word as an authorization. The file's fourth clause (spawn critic / verifier / completeness-checker lenses) is **R191** — add the source there |
| R338 | **A change touching >5 files, or any mechanical replacement across the codebase, gets ≥2 verification rounds — the second cross-checking against the repo's own standards, not generic ones** | pr-review-method | B | OUT→refs | D:feedback_thorough_review | Sits with R062 (pre-apply your own catalog before requesting review) and R061 (grade against the repo's stated bar). **New finding not in the extraction doc**: this file's original mechanism was "do the rounds with subagents", which **directly contradicts `CM:L31`**. The size trigger and the second-round content survive that strip; the dispatch shape does not. The extraction doc's "SAFE, but the label is wrong" caught the mislabel and missed the conflict |
| R339 | **Add "momentum / sunk cost" as a seventh named optimism bias** — progress-feeling is rewarded in the moment, so each step on an unverified premise both adds sunk cost and makes the wrong path feel more right | CLAUDE.md | B | OUT | D:feedback_thoroughness_over_momentum (headline) | **Merge into R011 rather than write a separate line.** R011's six (helpful⇒positive prediction · vendor-framing leak · completion-feel · speed-pressure rationalization · politeness wrap-up · story-generation) do not include it, and it is the one that produces a *wrong path* rather than a *wrong sentence*. `CM:L93` instructs "name the bias" without the taxonomy; R011 is the taxonomy and is currently OUT |
| R340 | **"Done" has three parts and needs all three: every real instance addressed, the end state verified, the enforcement in place** — motion this turn is not any of them | CLAUDE.md | B | OUT | D:feedback_thoroughness_over_momentum(4) | Nearest coverage is R023 (a completeness claim needs the enumeration) plus `CM:L176-178` (build the gate) — the two halves exist in different channels and neither states that both must hold before "done" is said. `CM:L90-91` bans the word; this defines the condition under which it would have been true |

---

# 3. The DELETE ten — clause-by-clause against `~/.claude/CLAUDE.md`

Every one of the ten source files was **read directly** at
`~/.claude/projects/<silo>/memory/<stem>.md`, not summarised from the extraction document, and
checked against `~/.claude/CLAUDE.md` read in full in this session. Where my reading differs from
`PROJECT-66-and-DELETE-48.md`, the difference is stated.

### 1. `feedback_session_workflow_rules` — **5 of 15 genuinely absent, not 9**

| rule | file says | CLAUDE.md | verdict |
|---|---|---|---|
| W1 | smaller atomic actions with a verification gate between each | **L122** "Work in single verified steps" | **COVERED** — *the extraction doc lists W1 as absent; that is wrong* |
| W2 | restate the contract before executing | **L122** verbatim | COVERED |
| W3 | verification authority lives OUTSIDE the model; "I tested locally" is one observation | — | **ABSENT** → R311 |
| W4 | one change per multi-turn segment; finish or hand off | — (L107 is scope-per-PR; L122 is steps-within-a-task) | **ABSENT** → R316 (rank C) |
| W5 | never pre-commit to multi-step plans; "I'll do A, then we decide B" | **L122-123** verbatim | COVERED |
| W6 | re-read prior decisions before each substantial action | — (L99-100 re-verifies the *premise*, not the *commitment*) | **ABSENT** → R312 |
| W7 | surface uncertainty *before* predicting | **L93-94** "'I don't know' is a full answer. Name the optimism bias out loud when felt" | **LARGELY COVERED** — *the extraction doc lists W7 as absent; residue is thin (rank C), the "ask before predicting" phrasing only* |
| M1 | `gh pr checks`, `git log @{u}..HEAD`, cite exact scope | **L91-93** verbatim, both commands | COVERED |
| M2 | test-scope defaults by change class | **L100** carries one rung (merge/rebase/wire-shape ⇒ full gate) | **PARTIAL** → R315 |
| M3 | banned phrases | **L90-91** verbatim | COVERED |
| M4 | observation-first sentence structure, inference labelled | L66-69 and L96-98 do this for *subagent output* and *claims*; not for own prose | **ABSENT at self-scope** → R313 |
| M5 | tag unavoidable predictions `[PREDICTION based on X]` | — (L82's `[DECISION]` is a different tag) | **ABSENT** → R313 |
| M6 | honest closing pattern incl. what was NOT tested | **L126** "Close with what was **not** tested" | COVERED |
| M7 | surface drift in real time | L37-38 covers method substitution in a dispatch only | **PARTIAL** → R314 |
| M8 | no preamble; first-sentence test | **L123-124** verbatim | COVERED |

**Confirmed:** *verification authority lives outside the model* (W3) is genuinely absent — the
single most consequential clause in the DELETE set, because without it every other verification
rule can be satisfied by the model grading itself. **Corrected:** the brief inherits the extraction
doc's "W1/W3/W4/W6/W7 + M2/M4/M5/M7" list; W1 is covered at L122 and W7 is largely covered at
L93-94, so the true loss is 5 absent + 3 partial, not 9.

### 2. `feedback_verify_before_asserting` — **1 of 4 named residues is genuinely absent**

| clause | CLAUDE.md / registry | verdict |
|---|---|---|
| no factual claim without a citation verified in the moment, at the claim's scope | **L96-97** verbatim | COVERED |
| memory files, comments, docstrings, PR text are claims; re-read the governing file, do not cite from recall | **L97** | COVERED |
| "redundant / covered / can't be done" needs the same proof as "it's a bug" | **L101** verbatim | COVERED |
| verification floor for a merge / rebase / wire-shape change is the full gate | **L100** verbatim | COVERED |
| the Recommended verification option defaults to the BROADER scope | **L124-125** "Lead options with the better end state, not the smaller one" | **COVERED** — *the extraction doc lists this as absent; that is wrong* |
| the trap: verification biased toward the bugs you already had hypotheses for | **L96** "at the claim's scope — not just the cases I expected" | **COVERED** — *also listed as absent; also wrong* |
| the four-step PR-audit protocol | R018 · R030 · R031 · R032 · R045 | COVERED across five rows |
| **when editing at a boundary, read the WHOLE file, not the diff hunk** | — | **ABSENT** → R333 |

The extraction doc's **UNSAFE-HIGH** verdict on this file is over-stated: three of its four named
residues are in fact in `CLAUDE.md` or the registry.

### 3. `feedback_thoroughness_over_momentum` — 2 absent of 5 checkpoints + the bias name

| checkpoint | coverage | verdict |
|---|---|---|
| 1 premise re-verification; assumption stack ≥2 is the tell | **L99-100** verbatim | COVERED |
| 2 the sweep precedes the fix — enumerate the class, then fix all instances | **R021** (count the copies before writing the fix; fix every instance in one commit) | COVERED at mechanism level; R021 is PR-scoped and this is any work — note the scope difference |
| 3 wrong-at-speed is negative progress | **L90** "A wrong claim is 100% fail regardless of speed or framing" | COVERED |
| 4 completeness defines done: instances + end state + enforcement | R023 has the enumeration half, L176-178 the enforcement half; neither states all three | **PARTIAL** → R340 |
| 5 after the first surprise the verification bar RISES | — | **ABSENT** → R310 (merges with S#113) |
| the named bias itself (momentum / sunk cost) | R011's six do not include it | **ABSENT** → R339 |

### 4. `feedback_iterative_planning` — 3 of 4 absent

Extraction doc verdict (MISLABELLED, superseder largely absent) **confirmed**. `CM:L82-86` covers
the approval gate only. Absent: the 2–3-round expectation and the meaning of "final pass" (R337);
the plan file as the only writable surface (R336); the question-tool-vs-plan-exit-tool boundary
(R336). Its fourth clause — spawn critic / verifier / completeness-checker lenses — **is** R191.

### 5. `feedback_thorough_review` — mislabel confirmed, plus an unrecorded conflict

Its banner names `feedback_thoroughness_over_momentum` as its superseder, and that file is itself
DELETE-routed — the chain-deletion the extraction doc describes. **New finding:** the file's
mechanism is "do the rounds *with subagents*", which contradicts `CM:L31` ("Default is a SINGLE
pass, ZERO spawned agents"). Strip that and what survives is the size trigger (>5 files or a
mechanical replacement ⇒ ≥2 rounds, the second against the repo's own standards) → R338.

### 6. `feedback_no_ready_claims` — SAFE confirmed, one non-obvious residue

`CM:L90-94` carries the banned list, the raw-state replacement, and both commands. The residue is
not content but **rule design**: this file deliberately banned one short word instead of writing a
workflow, because the friction of typing the longer replacement is what forces the missing fact
("CI has not seen this") to surface. That generalises → R335.

### 7. `feedback_subagents_need_explicit_read` — SAFE confirmed

`CM:L55-57` carries the whole thesis including the mechanism ("citing filenames does not make a
subagent read them") and the absolute-path requirement; R179 carries the underlying fact that a
subagent inherits nothing. Residue: the idea of a **standing minimum read-list** for any
code-modifying subagent. The file's actual list is repo-specific instance. Rank C; not registered.

### 8. `feedback_no_blockquote_for_pasteable_text` — SAFE confirmed

R215 carries it clause for clause, including the request discriminator. Add the source.

### 9. `user_profile` — SAFE confirmed, item by item

Handle + author-name caveat → L25-26 · agent-team execution model → L19 · no beads, standalone
skills, `make quality` / `./run_all_tests.sh` → L21-22 · Docker novice → L20 · push ownership →
L73-77 · never fork or clone → L27. The only non-transferred item is the attribution of the repo's
beads files to another contributor, which is instance. **Nothing lost.**

### 10. `project_backlog_triage_2026_07` — SAFE confirmed, one principle rescued

The file is a dated snapshot: 151 issue numbers, cluster ids, an artifact URL. **Gate 5 verdict:
it is not memory** — its own text says "re-verify issue states before acting", which is not a
nameable expiry event, and Gate 5 requires one. One principle travels: record the deliberate
non-merges so a later pass does not undo them → R334.

---

# 4. Per-destination summary of the new rows

| destination | IN | OUT | note |
|---|---:|---:|---|
| `~/.claude/CLAUDE.md` | **2** (R317, R319) | 12 | R317 evicts R003; R319 rewrites L20, net +1 line. R318 heads the OUT queue, ahead of the existing R009 |
| `pr-review-method` | 0 | **6** all `→refs` | at cap; `references/deferred.md` exists and is the correct destination |
| `testing-ci` | 0 | **5** all `→refs` | at cap; `references/deferred.md` exists |
| `agent-dispatch` | 0 | **1** `→refs` | at cap; `references/deferred.md` exists |
| `system-design` | 0 | 0 | its two candidates are **already written** into `references/deferred.md` and merely unregistered |
| `craft-context-file` | **3** (R330, R334, R335) | 0 | 2,500 B headroom |
| `craft-skill` | **1** (R329) | 0 | 3,100 B headroom |
| `outbound-drafts` | **1** (R321) | 0 | 1,900 B headroom |
| MEMORY | 0 | 0 | one candidate examined (`project_backlog_triage_2026_07`) and **rejected on Gate 5** — no nameable expiry event |
| DROP-vacuous | 0 | 0 | none of the 35 reduced to nothing under substitution |

**No eviction is claimed at any capped skill.** All 12 capped-destination rows are `→refs`, which
costs zero body bytes. The two CLAUDE.md IN rows are argued individually above and are the only
displacements proposed in this pass.

---

# 5. Findings that are not routing decisions

**1. The gap-detection instrument under-reported by 13 of 35 and over-reported nothing.** Two
distinct citation-format mismatches (`S#nn` written bare inside a list; PROJECT stems truncated to
a prefix) account for 12 of the 13, and a third — content written into a body that has no registry
section at all — accounts for the other two. A stem-equality matcher is a weaker instrument than
the registry's own citation practice; it fails toward "gap", which is the direction that
*generates* work rather than ending it, so no false-clean was produced. It cost this pass one
verification cycle to establish.

**2. `system-design` is unregistered in its entirety, not just for these two files.**
`PRINCIPLE-REGISTRY.md` has no `system-design` section — §16.4 explicitly records it as a
destination the fixed set did not include, and parks ~90 sub-principles at REPO instead (R288–R301).
But `drafts/final/system-design/SKILL.md` (5,383 B) and `references/deferred.md` (13,496 B) exist
and are written. **Every rule in those two files is outside the registry's ID space.** Two of them
happened to be named in this brief; the rest are invisible to any registry-based check. That is a
larger unregistered surface than the 35 sources this pass was scoped to.

**3. The registry's TOOL count is low by at least one.** §NOT-DONE records R024 as "the corpus's
one asserted TOOL candidate". R331 (count real-entry-point calls vs new error-path tests in the
diff) passes T1 and T2 on the same standard R024 was asserted on. R318 (a duration/time-estimate
vocabulary gate) also passes T1 and T2. Neither was evaluated on T3–T5.

**4. One extraction-document conflict resolved, one created.** `feedback_thorough_review`'s
mechanism contradicts `CM:L31` — the extraction doc caught the mislabelled superseder and missed
the conflict (R338). S#36's adversarial-by-default clause contradicts `CM:L31` in the same way;
`SKILL-121-split.md` flagged that one at extraction and it was never adjudicated. Both need the
same decision, and R323 records that the *adjudication* half of S#36 survives the refusal while the
*fan-out* half does not.

**5. Two extraction-document loss claims are over-stated.** `feedback_session_workflow_rules` W1
and W7, and `feedback_verify_before_asserting`'s broader-scope and self-biased-scope residues, are
in fact in `~/.claude/CLAUDE.md` (L122, L93-94, L124-125, L96). The rescue verdicts stand — both
files still lose real content — but the loss is smaller than recorded, and the difference matters
because it is 4 lines of a 179-line file that would have been added twice.

**6. `MACHINE` is still the missing destination.** R336 (plan-mode writable surface; the question
tool is not the plan-exit tool) is machine/harness-class with no cue, exactly like R275/R276/R283.
The fixed destination set has no MACHINE row, so it lands in the CLAUDE.md queue by elimination.
`agent-dispatch/references/claude-md-lines.md` reaches the same conclusion for the other three and
prices it at ~11 lines. This pass adds a fourth to that bill.

---

# NOT VERIFIED — explicit list

1. **I did not read the 121 SKILL source files, the 66 PROJECT source files, or the 48 DELETE
   files as a set.** I read the four named SKILL rows and the named PROJECT entries **from the
   extraction documents only**. The only original source files I opened are the **ten DELETE files
   and the six CLAUDE.md-routed files** — those sixteen were read in full, directly, as the brief
   required.
2. **The 11 truncated-key matches are prefix matches, not content matches.** I verified that
   `P:agentdb_persistent_schema` appears in R106 and that R106's text describes the same mechanism
   as the extraction doc's entry for `agentdb_persistent_schema_masks_fresh_db_failures`. I did not
   open the 11 original PROJECT memory files to confirm that the extraction doc's summary of each is
   itself faithful. If an extraction summary is wrong, my "already covered" verdict inherits it.
3. **I did not read `SKILL-SET.md`** (34,427 B). Where this pass cites §3x or §7.x numbers it is
   relaying `PRINCIPLE-REGISTRY.md`'s account of them.
4. **No byte measurement was made for any proposed row.** The IN/OUT calls rest on the registry's
   headroom figures (`craft-context-file` 2,500 B, `craft-skill` 3,100 B, `outbound-drafts` 1,900 B),
   which §NOT-DONE states are `count × 190 B` estimates, not measured text. If the real per-rule
   cost is 250 B, `craft-context-file` holds 10 more rules and my three IN rows still fit; the
   capped destinations move regardless because all 12 of those rows are `→refs`.
5. **The R317 eviction of R003 is an argument, not a measurement.** I did not count how often a
   mid-VCS-operation state claim occurs in the transcript corpus, which is the number that would
   settle it. `drafts/git/CLAUDE-md-additions.md` measures the analogous trigger (`pre-commit` in 41
   of 2,565 units, 1.6%) and calls its own block 3 "the first of the three to cut" — that is
   supporting evidence for the eviction, not proof.
6. **No trigger or firing behaviour was tested** for any destination, and no proposed line was
   exercised against a fresh session. Inherited from the registry's own NOT-DONE section.
7. **Gate 1 T3/T4/T5 were not run** on R318 or R331. Both are asserted on T1/T2 only, the same
   standard on which R024 was asserted.
8. **I did not adjudicate the two `CM:L31` conflicts** (S#36, `D:feedback_thorough_review`). Both
   are recorded as conflicts with the surviving clause identified; neither is resolved.
9. **`~/.claude/` was not modified except for this file.** No skill, no memory file, no config, no
   `CLAUDE.md`, and not `PRINCIPLE-REGISTRY.md` itself. `claude -p` was not run.
