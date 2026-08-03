# MASTER PRINCIPLE REGISTRY

> **CORRECTIONS 2026-08-02 (post-ship audit).** (1) R229's Ran/Not-run footer shipped in
> `outbound-drafts`, not `pr-review-method` — the note's "keep one copy there" resolved the
> other way. (2) R273/R274 shipped IN `prebid-adcp` (headroom existed) despite OUT here.
> (3) §16.7's sanctioned R029/R073 duplicate was later cut on its own test
> (`drafts/AUDIT-FIXES.md` F22). (4) §16.4's homeless block (R288–R301) landed when
> `system-design` was built after this registry froze. Counts and byte figures are
> point-in-time.

Every distinct principle from all four extraction passes, exactly once, with exactly one
destination. Deduplicated on **mechanism**, not wording.

## Headline

Counts below are derived mechanically from the table itself (`merged-from` entries, `IN`/`OUT`
column), not estimated.

| | count |
|---|---:|
| Raw principle statements across the four passes (= total `merged-from` entries) | **500** |
| **Collapsed by merge — the same mechanism stated in ≥2 places** | **191** |
| **Distinct principles registered, one row each** | **309** |
| IN — written into a destination body | **175** |
| OUT — registered and ranked, displaced by budget | **80** |
| OUT→refs — displaced, recommended for a `references/` file rather than lost | **50** |
| DROP rows (3 vacuous + the 26-file R2 duplicate block) | **4** |

## Conventions

**`merged-from` source IDs**
- `S#nn` — row *nn* of `SKILL-121-split.md` (1–121).
- `P:name` — a file in `PROJECT-66-and-DELETE-48.md` JOB 1.
- `D:name` — a file in `PROJECT-66-and-DELETE-48.md` JOB 2 (the DELETE-48 rescues).
- `GD` / `PD` — a bullet already written in `drafts/git/SKILL.md` / `drafts/pr/pr-review-method/SKILL.md`.
- `RR` — `ROUTING-RULE.md`. `CM:Lnn` — `~/.claude/CLAUDE.md` at that line.

**`rank`** — bindingness, not importance.
- **A** — violating it produces a **wrong artifact that ships**: a false green, a wrong claim
  in a PR comment, an unauthorized edit, a lost finding.
- **B** — violating it wastes work or produces a weaker artifact that does not assert
  something false.
- **C** — style, legibility, efficiency.

**`IN`/`OUT`** — IN = written into that destination's body. OUT = registered and ranked, not
written. `→refs` in notes = recommended for a `references/*.md` file in the same skill
directory (loads on demand, does not spend the 5,000 B body budget) rather than discarded.

**Budget** — 5,000 B per skill body; measured floor ~190 B per rule including its mechanism
⇒ **26 rules per body**. `~/.claude/CLAUDE.md` ≤3 lines per rule, currently 10,368 B / 179 lines.

**Measured correction to `SKILL-SET.md` §7.4** — the 5,519 B / 5,403 B figures are whole-file
including frontmatter. **Body only: `pr-review-method` = 5,000 B / 27 rules (185 B/rule,
exactly at cap); `git-workflow` = 5,106 B / 17 rules (300 B/rule, 106 B over).** Both have
zero headroom, but for different reasons: pr is at the rule ceiling, git is at the byte
ceiling with 9 spare rule-slots' worth of verbosity.

---

# 1. `~/.claude/CLAUDE.md` — 8 IN / 7 OUT

Already 10,368 B. `SKILL-SET.md` §3i budgets ~9 added lines. Cut line drawn at 11 lines.

| id | principle | dest | rank | IN/OUT | merged-from | notes |
|---|---|---|---|---|---|---|
| R001 | An empty result set is a hypothesis about your **matcher**, not a fact about the tree — a negative tests the query before it tests the code; POSIX-ERE silently ignores `\b` and returns empty rather than erroring | CLAUDE.md | A | **IN** | S#33, S#43, S#108, S#109, P:reference_harness_freshness(3) | **The 4-file duplicate named in the brief.** Two descendants stay separate in `testing-ci` (R044 matcher completeness, R043 selector proof) — different mechanisms |
| R002 | Cut the branch as the **first action** of implementation, before any edit — branching retroactively hides in-flight work from the branch listing | CLAUDE.md | A | **IN** | S#26, D:feedback_multi_phase_workflow | SKILL-SET §3h. `--no-track` mechanism stays in the `git-workflow` body (R120) |
| R003 | File state during an in-flight VCS/hook operation is **transient** — a hook that stashes unstaged work makes files read as their committed content; defer the observation, never describe state mid-operation | CLAUDE.md | A | **IN** | S#29 | SKILL-SET §3h |
| R004 | A harness-injected "proceed on best judgment" after a question times out **is not an answer** — restate and stop; a pending approval waits or expires-DENY, never default-approves; where a vendor default cannot be disabled a hook is the only reliable layer | CLAUDE.md | A | **IN** | S#4, P:project-hermes-fleet-plan(5) | **Cross-bucket merge**: the harness timeout and the approval-queue design are one mechanism. File stays as `question_timeout_guard.sh`'s documentation |
| R005 | No explanatory comments on standard patterns, and no issue/PR/ticket numbers in code comments — a comment restating metadata is a second copy of the same fact to keep true | CLAUDE.md | A | **IN** | S#20, S#21 | SKILL-SET §3d. A3 fires: the review-lens consumers have `tools:` allowlists without `Skill` |
| R006 | Source-priority ladder for any external system, and never let a lower tier overrule a higher one: the **locally installed artifact** (introspect it) → the normative repository (MUST vs SHOULD) → the implementation source → never its README → never a search summary or press | CLAUDE.md | A | **IN** | S#79, D:feedback_trace_flows_not_claims | **Cross-source merge** of two independently-derived ladders. Delete S#79's fan-out sentence: it contradicts CM:L31 |
| R007 | When the user is a **firsthand source**, their account outranks sanitized public documentation — and mechanism research ("how does it work") never re-litigates a premise ("is it real") the user set from the inside | CLAUDE.md | A | **IN** | S#85 | SKILL-SET §3b split |
| R008 | Approval is scoped to the **step approved** — completing step N is not authorization for N+1, and an exhaustive design pass is not a go to build | CLAUDE.md | A | **IN** | D:feedback-explicit-go-before-building, D:feedback_plan_approval_gate | Strictly broader than CM:L82's research→code rule. Highest-value DELETE-48 rescue |
| — | **CUT LINE — 8 rules ≈ 11 lines ≈ ~900 B added (8.7% growth)** | | | | | |
| R009 | Record the **query that regenerates a number**, never the number — a count recorded in prose drifted 4→6 while one cited site no longer qualified | CLAUDE.md | A | OUT | P:feedback_advisory_on_success_error_pattern(1) | First to promote if a slot opens. Memory §, 1 line |
| R010 | Attribute governance and maintainership to the **organization**, never the individual who operates the repos; do not invent operational scope for an organization because a design could use it | CLAUDE.md | A | OUT | S#92 | Will read as conflicting with CM:L25 (`@chrishuie` for CODEOWNERS) unless both scopes are stated. Held out for that reason |
| R011 | Six named sources of optimism bias, so "name the bias" has an instrument: helpful⇒positive prediction · vendor-framing leak · completion-feel · speed-pressure rationalization · politeness wrap-up · **story-generation when asked "what happened?"** | CLAUDE.md | A | OUT | D:feedback_truth_over_optimism | 2 lines. CM:L93 has the instruction without the taxonomy |
| R012 | After a crash, enumerate `~/.claude/projects/<CWD-project>/` before answering what survived — answer a loss question in the scope the asker **named** before widening | CLAUDE.md | B | OUT | S#1 | SKILL-SET §3i names it "first to drop". Signature → R280 (MACHINE) |
| R013 | The recognizable smaller-option tells: "document as known-deviation" · "defer to a follow-up" · "note it in the description" · a focused sub-suite over the full gate · the literal ask over the architectural completion. Self-check: correct, or quicker? | CLAUDE.md | B | OUT | D:feedback_lean_toward_quality_not_smaller_option | CM:L124 has the preference; this is the trigger list. →refs |
| R014 | When a claim is falsified, **narrow it to the half the evidence supports** rather than withdrawing it entirely | CLAUDE.md | B | OUT | P:feedback_check_normalizer(2) | 1 line, genuinely absent, but not artifact-binding |
| R015 | An autofixer's own safe/unsafe classification is semantics-preserving **only under the usages it can see** — re-exported names defeat it; enumerate and categorize call sites first, run the affected tests before committing, recover with `git checkout --` never a hard reset | CLAUDE.md | A | OUT | D:feedback_no_unsafe_autofix | CM:L105-109 has the ban and the incident; this is the procedure. →`git-workflow` refs |

---

# 2. `pr-review-method` — 26 IN / 31 OUT — **most over-subscribed destination**

57 candidates for 26 slots. 27 rules already drafted at 5,000 B (185 B/rule, exactly at cap),
so **every new rule evicts a drafted one**. Six evictions below are marked `EVICT`.

| id | principle | dest | rank | IN/OUT | merged-from | notes |
|---|---|---|---|---|---|---|
| R016 | Re-pull review state on the **current head** every time, across all four surfaces (`reviews` · `comments` · `issues/comments` · GraphQL `reviewThreads`) — one endpoint misses items, and re-checking CI plus prior findings is not a review-state re-check | pr-review-method | A | **IN** | PD, S#74, S#60 | drafted |
| R017 | Never filter by author on the **first** pass — inventory every commenter, then narrow; the strategically important comment is usually from the non-cited participant | pr-review-method | A | **IN** | PD, S#52 | drafted |
| R018 | Proof of "addressed" is a **code diff at the item's `path:line`** — not a resolved marker, a commit message, or recall; a composite comment is two items | pr-review-method | A | **IN** | PD, S#74 | drafted |
| R019 | Re-earn every verdict on the **final head** — the fix commit is the least-reviewed, highest-risk code in the PR; a verdict inherited across a new commit is void; a diff you yourself requested is still an unreviewed diff once it lands | pr-review-method | A | **IN** | PD, S#68, P:feedback_readiness_verdict_gate | drafted + rescue clause folded in |
| R020 | Run the gate **yourself** on the asserted head (`HEAD == headRefOid`, clean tree, read the summary not the exit code) — a green CI rollup is the author's evidence, not the reviewer's | pr-review-method | A | **IN** | PD, S#66 | drafted |
| R021 | Grep repo-wide and **count the copies before writing the fix** — N>1 is a missing abstraction, not a site defect; fix every instance in one commit and paste the zero-hit evidence | pr-review-method | A | **IN** | PD, S#41, S#56 | drafted |
| R022 | Every new top-level def/class/constant gets a repo-wide grep — the twin lives in a file the diff cannot see, and "is this new?" is a repo-wide question answered narrowly inside the diff | pr-review-method | A | **IN** | PD, S#43 | drafted |
| R023 | Sweep the pattern across every **open** item from a written list — deciding not to fix item Y is not deciding not to check it, and a completeness claim needs the enumeration, not recency | pr-review-method | A | **IN** | PD, S#39, S#38 | drafted |
| R024 | Grep the codebase's **own confessions** — *keep in sync*, *only verifies setup*, unverified defensive rationales; a keep-in-sync comment IS a deferred duplication, so extract it rather than document it | pr-review-method | A | **IN** | PD, S#40 | drafted. Also the corpus's one live Gate-1 TOOL candidate (T1/T2 pass; T3–T5 unevaluated) |
| R025 | **Semantic SSOT escapes textual-DRY guards** — one constant as two literals, one invariant computed two ways, one concept named three ways; sweep siblings by hand | pr-review-method | A | **IN** | PD, S#68 | drafted |
| R026 | Grade a new helper **N adopted / M eligible**, name every holdout, check *which* absorbed behavior it kept (a seam built from N divergent sites can ship the weakest everywhere), and enumerate the contract's parts — a seam can own one of five and be named for the whole | pr-review-method | A | **IN** | PD, S#51 | drafted |
| R027 | A consolidation/SSOT change **deletes the duplicates in the same commit**, or the consolidation is fictional and the canonical thing's own docstring is not yet true | pr-review-method | A | **IN** | PD, S#69 | drafted |
| R028 | Deleting one of N duplicate writes is a **behavior claim** — enumerate every reader on the success path AND every error path and ask what each does when the state is absent; a green suite measures the suite | pr-review-method | A | **IN** | PD, S#44 | drafted |
| R029 | A detector's **scan set is half its verdict** — CLEAN over the wrong surface reads as an all-clear; state the set, and include prose surfaces when the obligation lives there | pr-review-method | A | **IN** | PD, S#42 | drafted. Canonical copy is R042 in `testing-ci`; this stays as the review-time restatement — **the one deliberate two-channel duplicate**, justified because the PR consumer cannot see `testing-ci` |
| R030 | A finding from your **own prior round** is a lead, not a fact — re-derive it on the current tree; binds hardest once the author adopted your wording, because nobody else will check it | pr-review-method | A | **IN** | PD, S#58 | drafted |
| R031 | "Pre-existing" needs **provenance, not a stable count** — the set churns (remove N, add N); prove a byte-identical site-set base-vs-head plus `git log -G` over the range. Pre-existing ≠ harmless: answer as a scope decision | pr-review-method | A | **IN** | PD, S#71 | drafted |
| R032 | Verify a reviewer's proposed **fix**, and every sibling you extrapolate from it, against the code and any spec/test authority that may *mandate* the flagged behavior — deference is not verification, including for items inherited from a colleague; skip a verified non-defect with one line of evidence | pr-review-method | A | **IN** | PD, S#72, S#73 | drafted |
| R033 | Anchor every finding to `path:line` and post as **inline threads** — prose in one summary comment has no lifecycle, no resolution state, and falls out of remediation both unaddressed and undeclined. Never reuse a finding ID across rounds | pr-review-method | A | **IN** | PD, S#47 | drafted |
| R034 | Compute the commentable set from the **diff hunks** before building the payload — an anchor the platform refuses is a **scope signal**, never a formatting problem; never fall back to the nearest commentable line; verify the children landed | pr-review-method | A | **IN** | PD, S#77 | drafted |
| R035 | Ban "optional / non-blocking / nice-to-have" — it collapses **severity** (how wrong) into **disposition** (what happens next) and answers neither; every finding resolves to a named action, and "non-gating" is a laundering phrase for a dropped finding | pr-review-method | A | **IN** | PD, S#54, P:reference_per_diff_review_detectors(4) | drafted. Strip the `bd create` anchor — CM:L21 bans it (R1 failure) |
| R036 | A missing-test observation used as evidence is its **own finding** with its own disposition — "folds into X" only if one edit closes both | pr-review-method | A | **IN** | PD, S#45 | drafted |
| R037 | **De-dup is not synthesis** — de-dup by (path,line) collapses the same finding raised twice and leaves same-concept findings at different paths as separate low-severity items, which is the drop channel. Unify at max member severity, preserve every site, then diff the working-note citations against the final artifact | pr-review-method | A | **IN** | PD, S#63, P:reference_per_diff_review_detectors(3) | drafted + the citation-diff check folded in |
| R038 | Grade the **composition** of landed remedies — two individually correct fixes to one path can cancel, and a remedy can fix one side of its own mechanism (construct vs read, declare vs enforce). Mutate the half nobody asked about | pr-review-method | A | **IN** | PD, S#49 | drafted |
| R039 | Diff **two-dot against current main** as well as three-dot — commits already landed via a sibling are legitimate additions in the merge-base diff and invisible to every specialist | pr-review-method | A | **IN** | PD, S#61 | drafted |
| R040 | Pin every subagent to a fetched head SHA, re-check the live head **after** the fan-out, and re-base every finding before consolidating — an active PR moves mid-review, and a draft's findings go stale between derivation and delivery | pr-review-method | A | **IN** | PD, S#62, P:rereview-agent(21) | drafted + delivery-time re-verification folded in |
| R041 | **Steelman first**: read the surrounding paragraphs, decision records, "notable design decisions / locked" sections, sibling files and commit messages before raising — assume the implementer knows things you do not; an excerpt is not the file, so "X is missing" must be checked repo-wide; frame an ambiguous finding as a **question**, not a defect | pr-review-method | A | **IN** | D:feedback_review_rigor, D:pr1389-property-list-context, P:rereview-agent(11) | **NEW — highest-value DELETE rescue in this bucket.** `EVICT` PD "on someone else's PR, propose never author" (superseded by R047) |
| — | **CUT LINE — 26 rules ≈ 5,000 B. 31 candidates below are OUT.** | | | | | |
| R042 | Walk four levels before proposing or claiming: the change and its full execution path · everything it touches across boundaries · what **masks or proves** those interactions · what keeps it true after this session. A proposal grounded only at level 1 is a surface patch | pr-review-method | A | OUT→refs | S#67 | Strip the "gold-standard PRs" provenance (CM:L115 bans the phrase) |
| R043 | An enumeration of **explicit occurrences systematically undercounts** — a 4-way scan found 106 explicit sites, ~55–60% of the real surface. Sweep twice: once on the identifier, then again on the **semantic claim**, and enumerate every emission surface for a value | pr-review-method | A | OUT→refs | P:adcp-kernel-standalone(5), P:corpus-contradictions(3), P:reference_per_diff_review_detectors(5) | **3-source cross-silo merge.** Strongest OUT row in the registry |
| R044 | Personal tooling that **reviews** others' work must never mutate the shared repo or gate their CI — the reviewer tier is the ceiling; check the path is ignored before creating any file, and a tool that MUTATES the files it inspects is disqualified for reviewing someone else's change | pr-review-method | A | OUT→refs | S#111, S#68(clause), P:reference_harness_freshness(6), D:reference_verify_spec_skill_not_portable | SKILL-SET §3e placed the file here; `SKILL-121` argued Gate 2 A1 ⇒ `CLAUDE.md`. **Dissent recorded** — A1 is real (must hold before the first Write) |
| R045 | The scope test is not "is it in the title" but: does the expansion let the change land at a **more correct end state**, and does its principal remain intact? Plumbing that completes the principal is in scope; a forced title change is drift; **small ≠ in-scope** | pr-review-method | A | OUT→refs | S#57 | |
| R046 | A dependency PR that only **widens** a constraint is a no-op against a frozen lock — green CI proves the old version still works, which was never in question; the detonation is latent at the next refresh. Verify by installing the target and running the import lines; a source-tree 404 at a tag is inference, the installed package is the observation | pr-review-method | A | OUT→refs | S#93 | SKILL-SET §3a routes it here |
| R047 | On someone else's change you are a **reviewer**: propose, never author, patch, or push. "Clean and easy" almost always means **narrow**, not correct — the narrow change is fine for its scope; calling the area clean is the over-optimism | pr-review-method | A | OUT | S#66, PD | `EVICT`ed by R041; the never-push half is CM:L73 |
| R048 | A **dependency bump** is scoped "fix what broke" and blind to changes that break nothing (a new optional field, a field going optional, a removal, a renamed enum, a swapped nested type) — the authoritative check is a full model-surface delta between the two versions, every unhandled change traced as a hypothesis to falsify | pr-review-method | A | OUT→refs | S#84 | SKILL-SET §3e moves it out of `prebid-adcp` |
| R049 | Diff-anchored review dispatch **cannot see a test that should cover the change but lives in a file the diff never touched** — map the changed field to every scenario that grades it across the whole corpus, then check each is executing | pr-review-method | A | OUT→refs | P:feedback_changed_wire_field_dormant_grader_check | |
| R050 | Reusing a hardened contract's **vocabulary** is not inheriting its **mechanisms** — a design reads correct precisely because it uses the right words. Per borrowed claim: which predicate/invariant/guard makes this true, and is it the same one the parent shipped? | pr-review-method | A | OUT→refs | S#37, P:project-real-money-first(7) | **No clean home.** `pr-review-method`'s description is PR-scoped; the object here is a design/spec doc. See §14 |
| R051 | "The environment can't host this" is a **load-bearing claim** needing a throwaway prototype or a line-level cost read off the actual call sites — a true premise does not license the deferral, and an infra excuse is the easiest way to quietly take the smaller option because it sounds like engineering judgement | pr-review-method | A | OUT→refs | S#50 | |
| R052 | Reviewing a tool/CLI change: state its **cardinal invariant**, adversarially enumerate the inputs and environment that defeat it, and **run it end-to-end on real input** — its unit tests mock exactly the environment-bound layer where these bugs live. Catalog-driven review is strong at "does this violate a known pattern" and weak at "what invariant should this guarantee that nobody wrote down" | pr-review-method | A | OUT→refs | S#65 | |
| R053 | A **declaration with no consumer is inert** — it validates, it looks implemented, and nothing reads it. When checking "is X implemented", find the consumer, not the declaration; a field known to the schema but unhandled by the backend is silently dropped because the validator only rejects *unknown* fields | pr-review-method | A | OUT→refs | P:reference_gam_creative_level_targeting, P:reference_gam_language_targeting, P:project_teal(2), P:flask_migration(4) | **4-source merge.** Distinct from R079 (an allowlist entry pointing at dead code) |
| R054 | Relocating code **out of a guard's scan set** silently disables it — widen the guard, never move the code; a scan-set escape is a silent hatch | pr-review-method | A | OUT→refs | P:reference_review_patterns(P39) | Deliberately kept separate from R042 (scan set as claim): offense vs defense |
| R055 | A security-workflow change can move **which events it runs on** and relocate the merge-block outside the repo — diff triggers against BASE and ask what still blocks a fresh, never-commented request | pr-review-method | A | OUT→refs | S#48(c) | |
| R056 | When porting between two homes, the **target's review norms outrank literal source fidelity** — fidelity is the means, conformance the end; record the divergence and file it upstream; a latent anti-pattern in the source is a bug to fix in the port, not a behavior to reproduce | pr-review-method | A | OUT→refs | S#91, P:project_teal_pr_remediation(1) | **Cross-source merge.** SKILL-SET §3b left the *file* in its silo; the principle passes Gate 4 and travels |
| R057 | A **vendor capability gap misfiles as an internal configuration task** — when a doc or issue says "add the exclusion in settings" and the setting does not exist, the blocker is upstream and the doc is wrong; a roadmap-dependent fact carries an expiry | pr-review-method | B | OUT | S#76 | SKILL-121 routed the dated instance to MEMORY; no MEMORY destination exists in the fixed set, so instance → R305 (REPO) |
| R058 | Branching on a **type** to answer a control-flow question makes the type a proxy — enumerate which conditions land in it and whether they all deserve the same answer to *this* question; reusing a set built for a different consumer's question is a semantic-boundary violation even where it came from | pr-review-method | B | OUT | S#46 | |
| R059 | The same syntactic form is correct in one envelope and a defect in another — the discriminator is the **enclosing envelope**, not the call | pr-review-method | B | OUT | P:feedback_advisory_on_success_error_pattern(2) | |
| R060 | Where the error envelope is assembled at **one** dispatch boundary, a handler must raise the typed error, never return a hand-built one — success is derived from the *shape* of what is returned, so a hand-built error lacking the marker field ships a **fake success artifact** | pr-review-method | B | OUT | P:feedback_a2a_skill_handlers_must_raise | |
| R061 | Grade against the **repo's stated bar**, not generic standards — a repo may treat duplication as a correctness invariant with a ratcheting baseline and a mandatory pre-push full-suite gate | pr-review-method | B | OUT | D:salesagent-worktree-layout | |
| R062 | **Pre-apply your own catalog to your own change** before requesting review — many findings are defects the rework itself introduced; substrate authorship does not exempt the work from the substrate criteria; after fixing a nit once, grep to confirm it did not regress | pr-review-method | B | OUT | P:reference_review_patterns(meta) | |
| R063 | For ongoing tracking across cycles, edit **one comment in place** — do not add a new one each round — and include the head SHA so a reader can tell when it is stale | pr-review-method | B | OUT | D:feedback_no_pr_specifics_in_memory | |
| R064 | Re-derive the **rationale**, not just the decision — a right decision resting on a wrong reason gets reversed the moment someone checks the reason | pr-review-method | B | OUT | P:flask_migration_critical_knowledge(1) | |
| R065 | Reviewing an image/CVE fix is **empirical**: build both sides with the gate's exact flags, scan both, confirm the cited findings are present-then-gone, and confirm the gate's exit flips | pr-review-method | B | OUT | S#75 | |
| R066 | Facts can **all be right while the relationships between them hide the blocker** | pr-review-method | B | OUT | P:adcp-kernel-standalone-decoupled(3) | |
| R067 | A change can be factually flawless and still wrong at the level of **what it prioritizes** | pr-review-method | B | OUT | P:project-hermes-fleet-plan(19) | |
| R068 | Error-path code must never raise — a translator that crashes **shadows the original exception and fails open with no output** | pr-review-method | B | OUT | P:reference_review_patterns(P41) | |
| R069 | Enforcing a constraint by **rebuilding a typed object** drops every field not passed | pr-review-method | B | OUT | P:reference_review_patterns(P27) | |
| R070 | A **partial copy of a canonical map** is its own defect class; hand-sweep new **test** code for duplication, because sub-threshold duplication is invisible to the ratchet | pr-review-method | B | OUT | P:feedback_readiness_verdict_gate | |
| R071 | Residual code-review patterns: named outcome types replace ambiguous tuples (P18) · no compat path without a deletion criterion (P22) · every scoped query filters on the scope key (P16) · one operation family, one verb prefix so grep finds the primitive (P37) · cross-surface symmetry (P5/P26/P36/P42) | pr-review-method | C | OUT | P:reference_review_patterns | Grouped: 5 patterns, each below the bar individually. →refs |
| R072 | On a framework/ecosystem swap, enumerate the **defaults that differ**, not just the APIs — a changed default is a silent behavioral change at every site that relied on it | pr-review-method | C | OUT | P:flask_migration_critical_knowledge(2) | |

---

# 3. `testing-ci` — 26 IN / 42 OUT — **second most over-subscribed**

68 candidates for 26 slots. No draft body exists; all 26 are written fresh.

| id | principle | dest | rank | IN/OUT | merged-from | notes |
|---|---|---|---|---|---|---|
| R073 | A detector's **scan set is part of its claim** — a verdict complete over the files it read says nothing about where the obligation lives. Print roots, file count, base ref and resolved commit with every verdict; **zero inputs is an error, never a clean verdict**; verify in both directions before repeating it | testing-ci | A | **IN** | S#42, S#48(a), S#75, S#108, S#117, P:reference_bdd_inline_steps_escape_guards, P:reference_harness_freshness(3), RR SHIP-GATE#4 | **The 5-file duplicate named in the brief.** Deliberate second copy at R029 for the PR consumer |
| R074 | A guard catches only the syntactic forms its **matcher models** — enumerate every distinct spelling before coding it or name what is out of scope *in its own output*; a guard that trivially matches nothing is worse than no guard. Positive **and** negative self-tests | testing-ci | A | **IN** | S#108, S#116, RR SHIP-GATE#2 | Distinct from R073 (scope) — this is oracle strength. The brief's canonical "keep separate" pair |
| R075 | "I broke the production line and nothing failed" is a claim about your **selector** until it is proven to select the grading test — establish the baseline count first; baseline-N-passed → mutated-N-passed is the only trustworthy shape; a changed *deselected* count means the selector moved. Print the selected identifiers or drop the selector | testing-ci | A | **IN** | S#109 | |
| R076 | Every **positive presence check** over an append-extensible artifact is loose by construction: `phrase in DOC` is monotone under insertion but "the document asserts P" is not. The antitone dual ("no match found") is safe — which is why forbidden-sets work | testing-ci | A | **IN** | P:rereview-agent(1,3) | ~98 sites, 20 mutation-proven instances. The single most mechanically-grounded rule in the corpus |
| R077 | An assertion is reliable for the property it **names** only if (i) it enumerates its universe and proves the enumeration complete, (ii) it evaluates the artifact the way the **real consumer** does, and (iii) every exemption is granted by something the checked artifact **cannot write** | testing-ci | A | **IN** | P:rereview-agent(6), P:temporal-backbone-design(8) | The master rule; R073/R074/R079 are its three clauses seen separately. Kept because each fires on a different symptom |
| R078 | An invariant a change **asserts in prose** is real only if a mechanism goes RED when it breaks. Five ways it looks enforced and is not: convention/docstring only · an unreachable defensive clause · an adjacent test green for the wrong reason · partial enumeration (3 of 4) · **a centralized helper whose revert reddens everything through every path — mutate each call site, not the helper** | testing-ci | A | **IN** | S#105, P:temporal-backbone-design(1), P:project-hermes-fleet-plan(2) | Merged: "a prediction without a tripwire is a worry" and "guarantees asserted, never exercised" are the same mechanism |
| R079 | Every allowlist entry must point at something reachable from **production** — a guard pinning a dead helper is false confidence while the real path goes unguarded. Trace backwards for call sites (name + open paren, excluding imports); index **nested** definitions | testing-ci | A | **IN** | S#114, S#70, P:reference_review_patterns(P25) | The brief's 2-file duplicate. Distinct from R053 (an inert declaration in production code) |
| R080 | A test that **never ran reads as a pass** — auto-skip on a missing step definition, an unregistered/unbound scenario, a network-gated skip, or a dormant grader makes "passing" and "never ran" indistinguishable. Read PASS vs SKIP for the specific case; never infer from an aggregate count; there can be **more than one** independent silent-skip gate | testing-ci | A | **IN** | S#117, P:feedback_changed_wire_field, P:reference_bdd_harness_patterns(4), P:reference_bdd_harness_pitfalls(4,5), P:feedback_run_full_suite(6) | **6-source merge** |
| R081 | A structural/AST guard on test strength **cannot see circularity** — trace each asserted value to its source. Three vacuity shapes that pass every guard: re-deriving production's own expression against the same source · asserting a harness-constructed invariant · echoing an input literal. A field populated by calling the same helper production calls is lossy | testing-ci | A | **IN** | P:reference_bdd_harness_pitfalls(3), P:reference_review_patterns(P28), S#121 | |
| R082 | Never judge pass/fail from a runner's terminal **tail or exit code** — a runner prints its own success banner whenever *its* environments exit zero, and an aggregating environment can succeed while the suites it aggregates failed. Parse per-suite machine-readable output and enumerate every outcome outside the expected set | testing-ci | A | **IN** | S#120, P:reference_run_all_tests_in_network_artifacts(2), P:no_concurrent_agentdb(2) | |
| R083 | `from X import Y` binds the reference at **import time** — where a name is resolved decides whether a patch is live. Moving a call into a helper in another module makes previously-dead patches live (stale return values now in effect) and hoisting a lazy import kills a live patch; the test still passes via the real call. Grep for patches at **both** sites and run the full suite | testing-ci | A | **IN** | S#95, S#97, P:harness_error_wire(2), P:reference_per_diff_review_detectors(7) | **4-source merge**; SKILL-SET §3a calls these "one rule" |
| R084 | Reloading a module re-executes its `from X import Y`, so under an active patch the **mock binds permanently** — teardown restores the source and knows nothing about the copy the reload left. A mock on a source-module attribute *after* teardown is the tell. Manufactures false findings and vacuous passes simultaneously | testing-ci | A | **IN** | S#99 | |
| R085 | Any allowlist keyed by **(file, line)** breaks on any line-count change — yours or a formatter running mid-commit. Converge formatting first, then derive; **prefer symbol-keyed entries**; more violations in a file you did not structurally change = suspect line shift first | testing-ci | A | **IN** | S#94, P:feedback_run_e2e_locally_before_push(2) | |
| R086 | A test that enters **below the boundary** verifies the layer below it — a test named *wire* / *boundary* / *e2e* that calls the handler directly proves the handler; envelope and serialization assembly sit between handler and transport. Drive the real entry point, or rename the test to match what it verifies. Middleware does not run on a direct in-process call | testing-ci | A | **IN** | P:feedback_a2a_wire_tests, P:feedback_mock_only_tests, P:project-salesagent-lessons(8), P:feedback_check_normalizer(1), D:feedback_a2a_harness_real_auth_chain | **5-source merge** |
| R087 | A **synthesized** wire capture pins content but not framing and can land in the same field as real captured bytes — carry an explicit `synthesized` flag. Assert on the bytes the consumer receives, never on a reconstructed in-process object: reconstruction is lossy, so two distinct internal errors collapse to one and the test grades the reconstruction layer | testing-ci | A | **IN** | P:wire_envelope_policy(1,2,3), P:harness_error_wire(1) | |
| R088 | A compound boolean guard can be fully "covered" while one operand is **never evaluated** — the language short-circuits and both line and branch coverage read as covered. One test per operand; mutate each non-first operand away independently. Inverted in test code: `assert A and B` hides whether B was checked | testing-ci | A | **IN** | S#112 | |
| R089 | A failing oracle is **not permanent** — a later commit adding a redundant mechanism covering the same case silently neuters it; the oracle exists, passes, looks strong and guards nothing. Re-mutation-test after any change to the guarded path; run an on/off matrix when two mechanisms coexist | testing-ci | A | **IN** | S#110 | |
| R090 | A single green run on a timing-sensitive test is the **lucky branch of a race** — run it N≥5 times on the exact shipped artifact, never a reconstruction; a strict expected-failure must fail *reliably*; drain async deliveries to quiescence | testing-ci | A | **IN** | S#107 | |
| R091 | A known-bad self-test must drive the guard's **real entry point end-to-end** — a test calling only the extracted leaf matcher stays green when the mid-chain walker or the file filter is mutated to yield nothing. Prove completeness by mutating **each link** to yield nothing; add a negative case | testing-ci | A | **IN** | S#118, RR SHIP-GATE#1,#4 | |
| R092 | Static analysis yields a reliable **set** and an unreliable per-site **fix list** — three distinguishable failure modes (scanning a head with the new cap counts the inherited population; intersecting with added lines over-reports moved code; a net delta folds in rebases). Rebase onto the target and **run the gate**; verify any config by running it, never by reading it | testing-ci | A | **IN** | S#106, S#100 | The tox/argv case is the same mechanism: a config line depending on shell substitution "verifies" by reading and is broken at runtime |
| R093 | A checkout can **silently fail** and leave you on the previous tree — and the common cause is that the gate itself dirties a tracked file (an auto-ratcheting baseline). Per branch run: discard the dirt, switch, assert the resolved commit **and** a clean tree, abort on mismatch. **Identical test counts across "different" branches is the symptom** | testing-ci | A | **IN** | S#115 | |
| R094 | Jobs gated on a **release or base-branch condition never run on a change request** — a fully green check list is no evidence the gated path works, and the check list having **zero** entries for that job class IS the tell. A stacked PR gets no heavy CI and its scanner alerts stay frozen at the last mainline scan | testing-ci | A | **IN** | S#119, S#35 | S#35 is also in the git draft's CI section — **R2 conflict flagged**: keep one copy. Recommend keeping it here and cutting `GD` "a PR runs only the workflows whose filter its base matches" |
| R095 | **Train == test**: a taxonomy, heuristic, or detector scored on the cases it was built from proves nothing — a 6/6 score on its own corpus had no cell for the out-of-vocabulary case, and a principle abstracted *from* the cases you found and claimed as a bound on all cases is circular. Test on cases the catalog never taught | testing-ci | A | **IN** | P:rereview-agent(15), P:temporal-backbone-design(14,6), P:prompt-harness-goal(4) | **4-source merge** |
| R096 | Fixtures that mirror the parser's own assumptions are a **self-referential oracle** — commit ≥1 fixture from the real corpus, add a completeness oracle asserting a structural invariant over real data, and make a tolerant parser's silent skip **observable** | testing-ci | A | **IN** | S#121 | |
| R097 | Three gate shapes carry **zero information**: byte tripwires (fire on every edit) · never-firing detectors (the error arm has never executed) · saturated advisories (red regardless). The predictor of guard reliability is **both-arms-taken branch coverage**, not line coverage (107 of 1,037 enforcing; p=9e-07) | testing-ci | A | **IN** | P:rereview-agent(4,5) | |
| R098 | Every detector is a **worklist, not a verdict**, and its input is the corpus of **escaped defects**, not imagination — when a human catches something mechanizable that a detector missed, extend the detector rather than noting it | testing-ci | A | **IN** | P:reference_per_diff_review_detectors(1,2), P:reference_harness_freshness(2), RR Gate1-T5 | |
| — | **CUT LINE — 26 rules ≈ 5,000 B. 42 candidates below are OUT.** | | | | | |
| R099 | A **coherence checker** validates a pairing against a table and cannot see whether the pair fits the actual condition — a clean run means coherent, not correct | testing-ci | A | OUT→refs | S#80 | The condition-grounding half is R261 (`prebid-adcp`) |
| R100 | A conditionally-gated optimization silently **no-ops through a working fallback** while everything stays green — verify it *engaged* from the runtime log's per-branch marker; then **engagement ≠ benefit**: measure wall-clock against the no-optimization baseline | testing-ci | A | OUT→refs | S#104 | |
| R101 | A linter's **ignore list can disable the exact check you are relying on** — read it before saying "the linter would have caught it". Asymmetry: the autofixer still prunes *unused* imports; the blind spot is *missing* ones | testing-ci | A | OUT→refs | P:reference_ruff_f821_ignored | |
| R102 | A hook running in an **isolated environment with its own dependency declaration** emits phantom errors when its pin drifts from the runtime pin — exact pinning matched to the runtime, bumped in the same change, cache cleared | testing-ci | A | OUT→refs | D:precommit_mypy_adcp_pin | |
| R103 | A package manager trusting its own **metadata** reports "in sync" over a corrupted environment — an import failure with the package listed installed is a corrupted env, not a lock or code problem; a type-only dependency going unimportable surfaces as spurious "unused ignore" | testing-ci | A | OUT→refs | S#102 | Command → R283 (MACHINE) |
| R104 | When CI fails **twice on the same target with a different error each time**, you are peeling layers of rot — stop pushing speculative fixes and reproduce locally against the full stack | testing-ci | A | OUT→refs | P:feedback_run_e2e_locally_before_push(1) | |
| R105 | Failures clustered in resource-heavy tests that **do not reproduce in isolation** are the contention signature of a shared single-instance resource — prove it with a clean serialized re-run; never conclude "flaky/infra" by assertion | testing-ci | A | OUT→refs | P:no_concurrent_agentdb | |
| R106 | A green run against a **persistent, never-torn-down fixture** is necessary and never sufficient — a long-lived datastore accumulates every migration ever applied, converting a provisioning bug into a false green; re-run against a from-scratch instance | testing-ci | A | OUT→refs | P:agentdb_persistent_schema | |
| R107 | Pick the enforcement channel by **what the invariant depends on**: statically checkable from local files → in-repo AST/config test · external or supply-chain state, or needs a real subprocess → off-the-shelf CI tool · admin scope or runtime measurement → verify script | testing-ci | A | OUT→refs | P:feedback_fitness_functions_pattern | Pairs with RR Gate 1 |
| R108 | The **convenience quality target is a subset of the suite**; a whole-tree invariant check means a one-file edit can fail an unrelated file, so per-file selection structurally cannot catch it; **CI is not a superset of local**; a lower collected count offline is the tell | testing-ci | A | OUT→refs | P:feedback_run_full_suite(1,2,3,5) | |
| R109 | A detector's documented **remedy can clear the detection** — run the remedy before declaring a mutation survivor, and score raw vs semantic kills separately | testing-ci | A | OUT→refs | P:rereview-agent(2,12) | |
| R110 | A check pinned to a **path goes vacuous when content moves**, with no signal — coverage fell 60/60 → 1/60 while the checker reported "clean, 219 items" over a tree with 157 emptied | testing-ci | A | OUT→refs | P:rereview-agent(7) | |
| R111 | A gate depending on a **number** needs the landed script, exact tree, seed, output and hash — the author's own re-derived figure failed to reproduce | testing-ci | A | OUT→refs | P:rereview-agent(8) | |
| R112 | A **keyword detector on self-reported language measures claims, not outcomes** (fired on 83.5% of bodies, wrong about the majority, 59.3% of the language written by the claimant); a self-reported count is gameable by reclassification — check the classification rule, not the count | testing-ci | A | OUT→refs | P:rereview-agent(14), P:temporal-backbone-design(13) | |
| R113 | State a zero-observed result as a **bar plus its power bound** ("zero of 15 ⇒ ~18% upper bound"), never as "never" | testing-ci | A | OUT→refs | P:rereview-agent(20) | |
| R114 | Enable irreversibility only **after** the protective test is green N consecutive times — having the test is not having the gate; the order matters | testing-ci | A | OUT→refs | P:project-hermes-fleet-plan(3) | |
| R115 | Gate logic inside a **CI config heredoc is untestable by construction** — extraction is the prerequisite for coverage, so "add tests" is the wrong ask. Keep pipeline logic in repo scripts with the CI YAML as a thin trigger adapter | testing-ci | A | OUT→refs | S#48(b), P:project-hermes-fleet-plan(17) | **Cross-source merge** |
| R116 | Duplication and quality ratchets scan only **source scopes** — copy-paste inside CI config, and inside new test code, is invisible to them; worst on a security gate with two hand-synced verifiers | testing-ci | A | OUT→refs | S#48(a), P:feedback_readiness_verdict_gate | |
| R117 | A negative/counter assertion whose only check is **set-emptiness passes vacuously** on an empty response — pair it with a non-empty anchor | testing-ci | A | OUT | S#117 | Largely subsumed by R076/R081 |
| R118 | Assert on the **parsed structure**, never a substring of the stringified error, and never on another layer's framework-internal error text — the echoed request body satisfies the substring | testing-ci | A | OUT→refs | P:harness_error_wire(3), P:reference_review_patterns(P40,P17) | **3-source merge** |
| R119 | `raises(SpecificError)` with **no value assertion** still passes when production swaps to a parent class — assert the externally-visible value, not the type | testing-ci | A | OUT→refs | P:reference_review_patterns(P38) | |
| R120 | The change's stated purpose has a **pin test**: a single-line revert of the production line must redden ≥1 test | testing-ci | A | OUT→refs | P:reference_review_patterns(P9,P14) | |
| R121 | An **eagerly-derived table built at import** misses lazily-loaded members — assert completeness at test time | testing-ci | B | OUT | P:reference_review_patterns(P32) | |
| R122 | Pin externally-visible constants (callback URLs, routes, wire values) **byte-immutable** with a test — and an oracle pinning an emitted value to the constant it is *derived from* moves in lockstep and can never fail | testing-ci | A | OUT→refs | P:flask_migration(3), S#116 | |
| R123 | A grounded constant with **no test comparing it to its pinned source** lets a future drift reach the user with nothing red | testing-ci | A | OUT→refs | P:reference_per_diff_review_detectors(6) | |
| R124 | A **runner artifact is not a regression** — a containerized runner sees a build context stripped by the ignore file, so tests scanning excluded paths fail inside and pass on the host. Keep a known-artifact set; prove branch-independence by **both** provenance and environment-specificity | testing-ci | B | OUT | P:reference_run_all_tests_in_network_artifacts, P:reference_bdd_harness_pitfalls(6) | |
| R125 | A **scanner's tooling crash is not a finding** — re-run before owning it; and a scanner reporting "not scanned" is not "zero findings": a tool's no-op mode reads as a clean result | testing-ci | A | OUT→refs | S#75, S#120, P:feedback_run_full_suite(4) | **3-source merge** |
| R126 | **Log-capture assertions** pass in isolation and fail in a full suite because other tests leave global logging state behind — assert on behavior, not captured logs | testing-ci | B | OUT | S#120 | |
| R127 | Trace **comment-vs-string before counting occurrences** — prose *describing* a convention is not an instance of it; join soft-wrapped prose into semantic units so a two-line contradiction is catchable | testing-ci | B | OUT | P:reference_harness_freshness(7), P:corpus-contradictions(4) | |
| R128 | A detector's **standing counts are context against a baseline, not per-run alarms** — the actionable signals are a self-test failure and a stale-snapshot warning | testing-ci | B | OUT | P:reference_harness_freshness(5) | |
| R129 | A **dispatcher routing by key must raise loudly on an unhandled key**, and when two sources can answer a question, rank them by authority and fail loudly on a miss — a silent default is how drift stays invisible | testing-ci | A | OUT→refs | P:reference_bdd_harness_patterns(1), P:project_teal(4) | |
| R130 | A harness supplying **"sane defaults" defeats any test probing the absence of that field** — grep the harness for default-backfill of X before adding a validator for X | testing-ci | A | OUT→refs | P:reference_bdd_harness_pitfalls(1) | |
| R131 | The **guard's failure list IS the work-list** and stays red until done — a shrink-only allowlist ratchet | testing-ci | A | OUT→refs | D:feedback_escalate_recurring_lessons_to_guards | |
| R132 | Never **edit a test to pass**; facing delete-vs-resurrect on a dead or broken test, default to resurrect with strengthened assertions — reducing test surface is a regression | testing-ci | A | OUT→refs | P:project-salesagent-lessons(7), S#103 | **Live tension with R133** — both are real; the discriminator is whether the pinned shape still exists |
| R133 | A test **pinning a dead shape gets deleted, not maintained** | testing-ci | B | OUT | P:reference_review_patterns(P30) | See R132 |
| R134 | Under a parallel runner, **hardcoded resource IDs collide** — allocate unique per-test IDs | testing-ci | B | OUT | P:reference_bdd_harness_patterns(3) | |
| R135 | A test client that **bypasses real auth middleware needs an explicit dependency override** — the bypass is silent | testing-ci | B | OUT | P:reference_bdd_harness_patterns(5) | |
| R136 | **Generated files carry a DO-NOT-EDIT header** naming the regeneration command and the source revision; a hand edit without a source bump is a violation | testing-ci | B | OUT | P:reference_bdd_harness_patterns(2) | |
| R137 | A **rate-limited harness call returns error text** — graders must classify it as FLAKE, not FAIL | testing-ci | B | OUT | P:prompt-harness-goal(7) | |
| R138 | Run workspace suites **from their own directory** — a root-flag invocation misresolves paths and fakes failures | testing-ci | B | OUT | P:prompt-harness-pr-review-method(6) | |
| R139 | Every fixed bug becomes a **blocking hook or guard test** (executable postmortem) | testing-ci | B | OUT | P:project-salesagent-lessons(3) | Largely CM:L176-178 |
| R140 | Every threshold is a number, with **unvalidated defaults explicitly marked unvalidated** | testing-ci | C | OUT | P:temporal-backbone-design(3) | |

---

# 4. `git-workflow` — 20 IN / 8 OUT

Draft body 5,106 B / 17 rules = **300 B per rule**, 106 B over cap. The draft's verbosity, not
its rule count, is the constraint: compressing to the 190 B floor frees ~9 slots. IN below
assumes that compression; `EVICT` marks draft rules cut instead.

| id | principle | dest | rank | IN/OUT | merged-from | notes |
|---|---|---|---|---|---|---|
| R141 | A compound command reports the **last stage's exit code**, so a failed operation inside it reads as success — run the fallible operation bare and verify the STATE it was meant to change (did the ref advance?), never the reported exit code | git-workflow | A | **IN** | GD, S#23 | drafted |
| R142 | A **formatter hook that rewrites a staged file exits non-zero and aborts the commit** — files stay staged, the rewritten one shows `MM`, HEAD never moved | git-workflow | A | **IN** | GD, S#23 | drafted |
| R143 | Chain a mandatory cleanup with `;` or a `trap`, never `&&` — a non-zero exit skips the `stash pop` and the tree silently reverts to base, so a later "verify my changes" reads the wrong content. Better: do not mutate the working tree for a comparison at all | git-workflow | A | **IN** | GD, S#25 | drafted + the don't-mutate clause |
| R144 | After a VCS-staged rename, passing the **old path** to a later stage command fatals and aborts the entire staging — you ship a 100%-similarity rename with 0 insertions. Diff-stat the staged content before committing any rename+edit | git-workflow | A | **IN** | GD, S#32 | drafted |
| R145 | Land a breaking constraint and **every caller and fixture fix in one commit**; enumerate every site it breaks first, modelling every form the matcher must catch. If it must split, state the push order and that the first alone breaks CI | git-workflow | A | **IN** | GD, S#24 | drafted |
| R146 | Cut without `--no-track` and the first push **resolves its destination from the tracked branch's name** and is rejected by protection — `git branch --unset-upstream` before the first push; already edited on main, `checkout -b` from the dirty tree | git-workflow | A | **IN** | GD, S#26 | drafted |
| R147 | A PR at `mergeStateStatus=DIRTY` makes the host **silently skip** `pull_request` workflows — it cannot build the merge ref they check out, so it reads as frozen tests. **After every push assert both** a non-conflicting state and a non-empty run list for the pushed SHA; an empty run list IS the failure | git-workflow | A | **IN** | GD, S#31 | drafted |
| R148 | **Cherry-picking one of the mainline's commits** is how a branch goes DIRTY non-obviously — take the full state by merging, never a slice | git-workflow | A | **IN** | GD, S#31 | drafted |
| R149 | A request authored by an **automation identity** leaves required checks in a pending-approval state that never reports; only a human-attributable event clears it, and a manually-dispatched run's checks do not attach to the required contexts | git-workflow | A | **IN** | GD, S#34 | drafted |
| R150 | Issues and change-requests draw from **one shared counter** and never correspond — confirm the real identifier from the API after the object exists | git-workflow | B | **IN** | GD, S#27 | drafted |
| R151 | Verify a branch's **currency against the mainline before implementing a plan written against it** — including whether the mainline already restructured the files the plan targets; detect "synced" by observation, never wait to be told | git-workflow | A | **IN** | GD, S#30 | drafted |
| R152 | Merging the mainline into a long-lived branch **creates duplication neither side had** — no conflict fires because the files differ. After every merge, sweep both directions matching the **idiom**, not the helper's name | git-workflow | A | **IN** | GD, S#28 | drafted |
| R153 | A **rebase can resurrect the line a relocation change moved**, keeping both — the fix becomes the dead copy while its comment still asserts it. Count the statement per revision; 1→1→2 is the tell | git-workflow | A | **IN** | GD, S#28 | drafted |
| R154 | A **pre-commit hook whose entry re-resolves the dependency lock** modifies a tracked file mid-commit, and the framework fails any hook that modifies tracked files — the commit aborts citing a file unrelated to your change. Force the resolver to use the lock as-is; a post-hoc restore cannot unblock it | git-workflow | A | **IN** | S#101 | **NEW** — SKILL-SET §3a mandates this addition |
| R155 | A **history rewrite does not purge** — pre-rewrite commits stay fetchable by SHA until GC; true erasure needs the host's support or delete-and-recreate | git-workflow | A | **IN** | P:project_review_harness_share_repo(1) | **NEW.** Makes a "we removed it" claim false |
| R156 | Verify a clone's **origin** before treating its layout as the upstream project's — a diverged fork carries the same name and a different structure, and every document grounded against the wrong one inherits the error. On correction, re-ground every artifact, not just the sentence that was caught | git-workflow | A | **IN** | S#90 | **NEW** |
| R157 | The local default-branch ref is **routinely stale** — fetch before rebasing or diffing against it; and with multiple remotes including forks the PR target is **not inferable from the branch**: confirm once and record it | git-workflow | A | **IN** | P:feedback_pr_base_current_main_push_origin | **NEW** |
| R158 | A **notes directory can hold tracked content** — `git ls-files <dir>` before deleting anything in it; `git status` shows only the untracked ones, so `ls` overstates what is safe to remove | git-workflow | A | **IN** | P:feedback_planning_doc_location(2) | **NEW** |
| R159 | Read a branch-only corpus with `git show <branch>:<path>` — a planning corpus can live only on a branch and does not need a checkout | git-workflow | B | **IN** | D:ci_refactor_rollout_state | **NEW** |
| R160 | **Read the hook file's generator header before trusting the configured version** — a globally-installed drop-in replacement can silently take over a repo's hook and install from upstream HEAD, ignoring every pin | git-workflow | A | **IN** | D:prek_pre_commit_replacement_bug | **NEW** |
| — | **CUT LINE — 20 rules at ~250 B/rule ≈ 5,000 B. Requires compressing the 17 drafted rules from 300 B to ~250 B each.** | | | | | |
| R161 | A PR runs only the workflows whose base-branch filter it matches, so a stacked change gets no heavy CI | git-workflow | A | OUT | GD, S#35 | `EVICT` — **R2 with R094 in `testing-ci`.** SKILL-121 §misroutes says it contains no git operation. Keep the `testing-ci` copy |
| R162 | `workflow_dispatch` runs never attach to a PR's required contexts; a superseded check lingers beside the new one and `mergeable` sits at `UNKNOWN` while it recomputes | git-workflow | B | OUT | GD | `EVICT` — merged into R149's second clause |
| R163 | **Two formatters with overlapping scope is a config defect** — neither is idempotent on the other's output, so the second reformats pre-existing lines in any file it touches and aborts commits mid-hook. Converge on one, in lockstep with the checker | git-workflow | A | OUT→refs | D:feedback_black_ruff_format_disagreement | |
| R164 | On the one push confirmation, surface the **target and the identity it goes out under** (which account); restore the tree afterwards | git-workflow | B | OUT | D:feedback_user_owns_git_push | CM:L73-77 has the boundary |
| R165 | Each push is its **own** action needing its own confirmation — an earlier phase-level authorization does not carry | git-workflow | A | OUT | D:feedback_push_policy | Subsumed by R008 (`CLAUDE.md`) at a broader scope |
| R166 | Pre-push scope check: `git diff --stat <base> HEAD` shows only the intended files | git-workflow | B | OUT | P:feedback_pr_base_current_main_push_origin | |
| R167 | A repeated multi-step environment action gets a **named verb**, not a recalled sequence | git-workflow | C | OUT | S#14 | SKILL-SET §3c: pure instance. Editor-window mechanism → R284 (MACHINE) |
| R168 | Enumerate call sites and categorize each before applying any bulk rewrite; run the affected tests before committing it | git-workflow | A | OUT→refs | D:feedback_no_unsafe_autofix | Body of R015 |

---

# 5. `agent-dispatch` — 26 IN / 16 OUT (NEW skill)

| id | principle | dest | rank | IN/OUT | merged-from | notes |
|---|---|---|---|---|---|---|
| R169 | A **synthesizer cannot red-team their own synthesis** — the adversarial pass needs a fresh reader who did not write it; the synthesizer's own fixes "read correct" by mirroring the hardened prose. Confirmed 7×, including recursively on the red team's own output | agent-dispatch | A | **IN** | P:project-reference-agents(5), P:project-real-money-first(6), S#37, P:project-technical-grading(4) | **4-source merge** |
| R170 | **Fresh context ≠ fresh gradients** — an independent observer at the top of the ladder gives context-freshness only; tendencies are weight-level, so a same-family observer shares a common-cause failure. A genuinely independent check needs a different model **family** | agent-dispatch | A | **IN** | P:temporal-backbone-design(9) | Tension with CM:L55 ("omit `model`") — different axis (pinning vs diversity); state both |
| R171 | **No agent writes, or supplies the input to, the instrument that grades it** — the vacuous-oracle check is: were the commands authored by the checked party, and does exit-0 discriminate anything? | agent-dispatch | A | **IN** | P:temporal-backbone-design(2,10), P:project-technical-grading(2), RR Gate1-T2 | **4-source merge**; independently re-derives Gate 1 T2 |
| R172 | Every trust anchor the agent can write is **not a boundary** — receipts, stamps, tiers, hook scripts, an "append-only" ledger and settings are plain text writable by the thing being constrained. A guard is not state-independent while the agent can edit the guard | agent-dispatch | A | **IN** | P:temporal-backbone-design(8) | |
| R173 | **Power-validate the instrument before believing a null**: seed known flaws and require recall ≥2/3 or discard the nulls; use independent, diverse-prior searchers, half under a refute-condition; freeze the novelty criterion before the run; the claimant never authors the acceptance criterion. The strongest permissible claim is "power-validated independent search found nothing" | agent-dispatch | A | **IN** | P:temporal-backbone-design(5,4) | |
| R174 | **Power validation is per-tier and non-transferable** — the same seeded-recall test scored 2.4/5 at one model tier and 5/5 at another; the "blind spot" was a tier artifact | agent-dispatch | A | **IN** | P:temporal-backbone-design(7) | |
| R175 | After an agent does modifying work, run a **second agent whose only job is to audit the first** against an explicit Step-0 read list — the load-bearing variable is the explicit READ plus fresh context, not the model class | agent-dispatch | A | **IN** | S#10 | |
| R176 | **Seed each agent with hypotheses framed to refute**, not confirm; require `file:line` evidence plus an attempted refutation per finding | agent-dispatch | A | **IN** | P:prompt-harness-pr-review-method(3) | |
| R177 | **Reference-first transport**: give a bounded manifest of exact absolute paths **plus why each is authoritative** and let the agent read; never paste diffs or file contents into the prompt | agent-dispatch | A | **IN** | P:prompt-harness-pr-review-method(2) | Extends CM:L55-57 |
| R178 | Recover a stalled agent by **pinging it — the transcript is intact; never re-spawn.** A ping is a second chance to AIM: re-ask the specific contested question plus what you have since verified yourself, and say explicitly what **not** to re-derive | agent-dispatch | A | **IN** | P:prompt-harness-pr-review-method(1), P:rereview-agent(10) | |
| R179 | A subagent inherits **nothing** — not the system prompt, style, or history; a delegation that skips context files gives the child a **default identity**, a persona hole at depth ≥1 | agent-dispatch | A | **IN** | P:project-hermes-fleet-plan(18) | The mechanism behind CM:L55-57's Step-0 rule |
| R180 | State the **stage** in every dispatch — "planning: spec only, no file edits" or "implementation approved: edits in scope". Subagents do not inherit the stage, and an unmarked stage is planning | agent-dispatch | A | **IN** | D:feedback_no_code_in_planning_stage | |
| R181 | **Assign by derivative chain and seam, not by file or dimension** — a defect living on the seam between two dispatched dimensions is owned by neither, and the strongest structural findings come from holding adjacent regions together | agent-dispatch | A | **IN** | P:rereview-agent(9), S#41 | **Cross-source merge** |
| R182 | Require a **baseline assertion before every mutation** — clean status plus a green exit, with stop-and-report on mismatch | agent-dispatch | A | **IN** | P:rereview-agent(9) | |
| R183 | A **cross-verify agent must be forbidden from reading the other agents' work** — otherwise it corroborates rather than checks | agent-dispatch | A | **IN** | P:rereview-agent(9) | |
| R184 | A status-clean check **between another agent's edit and its restore still races** — "revert and verify clean" is the collision path, not the fix; mandate isolation up front, and when the review target is itself a guard, every specialist mutates it concurrently | agent-dispatch | A | **IN** | S#8, S#7 | The brief's 2-file near-verbatim duplicate. Commit-first is CM:L61-64 |
| R185 | **Batch a fan-out by shared context, not per item** — N-per-item designs re-read the same files N times | agent-dispatch | A | **IN** | S#3 | |
| R186 | Budget is a **metered, window-expiring resource, so its value is time-varying** — scarce mid-window, near zero at reset. Waste runs both ways: heavy apparatus on light questions mid-window, and surplus dying unused at reset while pre-approved heavy work sits parked. **Surface the estimate and the window position**; near reset drain the parked queue, never invent work | agent-dispatch | A | **IN** | D:feedback-budget-is-a-resource, S#3 | CM:L39 has "count the cost" and nothing else |
| R187 | A delegate's **confidence figure without a sample size is not a measurement** — require observation-vs-inference labels and an explicit "what I did NOT verify" list in every report | agent-dispatch | A | **IN** | S#5 | Hedging-words half is CM:L66-69 |
| R188 | Do **not generalize a per-instance finding** — one measured cell of a repeated matrix is a hypothesis about the others; over-generalizing one endpoint's reliability once fabricated a figure | agent-dispatch | A | **IN** | P:rereview-agent(13), S#59 | **Cross-source merge** |
| R189 | Reach for the **packaged skill rather than reconstructing it from its parts** — hand-launching the same agent *types* reproduces the fan-out and drops the selection and consolidation discipline that lives in the wrapper, and can silently skip a lane. A harness's value is in the parts that are not agents | agent-dispatch | A | **IN** | P:feedback_use_full_review_skill_not_handrolled_fanout | Sharper mechanism than CM:L34 |
| R190 | Fan-out rounds converge to **finer shades, not zero** — gating on "zero findings" never terminates. Stop on **monotonically decreasing** findings or a severity floor, and always re-trace after heavy edits: a convergence pass catches the errors your own fixes introduced | agent-dispatch | A | **IN** | P:prompt-harness-goal(9), P:adcp-kernel-standalone-decoupled(4) | **Cross-source merge** |
| R191 | Three verification lenses, when a fan-out is authorized: a **critic** (challenge end-to-end, severity-ranked) · a **source-freshness verifier** (re-pull the current state of every cited external anchor) · a **completeness checker** (read every source the artifact claims to distil and name what was lost). Synthesize their findings yourself; never relay, never launder a delegate's output into a public recommendation | agent-dispatch | A | **IN** | D:feedback_opus_verification, D:feedback_verify_remedy_before_public_post | Delete the file's `model: "opus"` pin — contradicts CM:L55 |
| R192 | Workers hold **capability, never credentials** — secrets and orchestration state live in the harness, not the guest; credentials are runtime config, never prompt content. An injected worker can then call a tool but cannot exfiltrate a key it never had | agent-dispatch | A | **IN** | P:project-hermes-fleet-plan(4), P:project-agent-trust-layer(2) | **Cross-source merge** |
| R193 | Autonomy has a **user-owned ceiling**: config can never *raise* autonomy, and a capability absent from the consent registry is unconsented and fails closed | agent-dispatch | A | **IN** | P:rereview-agent(18) | |
| R194 | Work whose only output is **transcript prose must be streamed to a durable file as it is produced** — otherwise the largest surviving artifact is evidence about itself | agent-dispatch | A | **IN** | S#1 | |
| — | **CUT LINE — 26 rules ≈ 5,000 B. 16 candidates below are OUT.** | | | | | |
| R195 | A delegate's **one named cause** for a symptom with several candidates and no isolating experiment is the overconfidence tell — bisect it | agent-dispatch | A | OUT→refs | S#9 | CM:L66-68 has the symptom-vs-hypothesis rule |
| R196 | **Offer** the mechanical block (deny the spawn tool in settings) — never apply it unilaterally; and name where a substituted method is structurally **weaker**, not just "equivalent" | agent-dispatch | A | OUT→refs | D:feedback_no_agent_fanout_by_default | CM:L37 has "flagged up front" without "name the weakness" |
| R197 | A **sandbox certifies conformance and known-bad probes deterministically but cannot certify a non-deterministic agent's future behavior** — pair pre-deploy testing with a production runtime witness; neither alone | agent-dispatch | A | OUT→refs | P:project-agent-trust-layer(4) | |
| R198 | Untrusted autonomous code that **acts** needs a hardware-virtualization boundary; a shared-kernel container is escapable. Never roll your own isolation; two independent layers (cannot escape the box **and** cannot do what the mechanism will not authorize) | agent-dispatch | B | OUT→refs | P:project-agent-trust-layer(1,3,5) | |
| R199 | **Capture at the highest vantage point that sees the work** — the orchestrator spawns the leaf tools and captures their I/O even when the tool exports nothing; vantage order: orchestrator > native telemetry > session-file harvest > provider API | agent-dispatch | B | OUT→refs | P:project-hermes-fleet-plan(1) | |
| R200 | A **bake-off holds the gates constant and varies only the proposer**; one mind per treatment; tune each scaffold per model before comparing | agent-dispatch | B | OUT | P:project-hermes-fleet-plan(14) | CM:L162-164 covers the one-variable half |
| R201 | Report **capability and reliability separately** (pass@k vs pass^k), and cost as $/task **and** $/success | agent-dispatch | B | OUT | P:project-hermes-fleet-plan(15) | |
| R202 | One human approver by design: agent gates do the heavy reading and the human gets **one batched queue where every item carries its evidence**, so ratification is a read, not an investigation | agent-dispatch | B | OUT→refs | P:project-hermes-fleet-plan(6) | |
| R203 | **Read-only beats a sentinel** — an older reader must never retract a newer peer's state | agent-dispatch | B | OUT | P:rereview-agent(17) | |
| R204 | **Regulate situations, not intentions** — self-detection fails exactly when it is needed; the model is the plant, guards are disturbance rejection outside it | agent-dispatch | B | OUT | P:temporal-backbone-design(11) | |
| R205 | Run the **deterministic suites yourself** rather than delegating them, and check them against the change's stated claims | agent-dispatch | B | OUT | P:prompt-harness-pr-review-method(5) | |
| R206 | Reclaim order at disk exhaustion, and never cycle the daemon mid-fan-out | agent-dispatch | B | OUT | S#6 | CM:L46-52. Reclaim specifics → R285 (MACHINE) |
| R207 | Sweep for stray `model` pins under the config directory | agent-dispatch | C | OUT | D:feedback_subagent_model_inherit | CM:L55 |
| R208 | Absolute paths in every dispatch (the persisted-cwd trap) | agent-dispatch | C | OUT | P:prompt-harness-goal(8) | CM:L55-56 |
| R209 | Per-agent **isolated clone pinned to the commit**, with the agent asserting the commit | agent-dispatch | A | OUT | P:rereview-agent(9), S#12 | CM:L61-64 verbatim |
| R210 | A **self-declared convergence is self-attestation** — claimant-authored criterion, self-generated generators, one context; what stands is searcher exhaustion only | agent-dispatch | A | OUT | P:temporal-backbone-design(4) | Folded into R173 |

---

# 6. `outbound-drafts` — 16 IN / 4 OUT (NEW skill, **under budget**)

| id | principle | dest | rank | IN/OUT | merged-from | notes |
|---|---|---|---|---|---|---|
| R211 | Filter an outbound artifact **sentence by sentence**, including any draft handed over to paste: no fan-out counts, no detector names, no "our tooling caught it" scorekeeping, and **strip any "what we learned" section entirely**. Review-**workings** are a category distinct from strategy and motive. **Echoing the user's own framing does not exempt it.** Run a vocabulary gate on the finished draft | outbound-drafts | A | **IN** | D:feedback_no_internal_dialogue_in_public_artifacts (×2 silos) | CM:L113-116 has the rule; this is its executable form |
| R212 | Issue-body contract — **include**: impact, what the contract requires, the current gap with pointers, implementer-beware notes as non-obvious **facts** (not solutions), acceptance criteria as **outcomes** (not steps), open questions, out-of-scope. **Exclude**: pseudocode, design alternatives with pros/cons, file-by-file plans, test inventories, verification dumps. Length signal ~150–250 lines; 700 is too long | outbound-drafts | A | **IN** | D:feedback_github_issue_drafting | CM:L79-81 has delivery and scope only |
| R213 | A report for an **external actor is self-contained** — per item: location, what's wrong, why it matters, the literal tested change, how to verify. Never a status summary; never a pointer to a local path the reader cannot open | outbound-drafts | A | **IN** | S#17 | |
| R214 | The **audience decides the shape**: an artifact surfacing a decision to a **group** presents options and tradeoffs with no recommendation; a 1:1 proposal recommends. The discriminator is the audience, not the artifact type | outbound-drafts | A | **IN** | S#18 | |
| R215 | **Paste-bound text goes in a fenced block, never a quote-prefixed one** — the per-line prefix must be stripped by hand. Discriminate on the request: "draft a comment for" is paste-bound; "what's the status" is read-only | outbound-drafts | A | **IN** | S#19 | |
| R216 | Pick the artifact **shape before writing** — a multi-finding consolidation and a single comment have different structures, and **a rule stated only as a parenthetical exception reads as the rule's absence** | outbound-drafts | A | **IN** | S#22(a) | |
| R217 | The artifact **is** the deliverable, surfaced verbatim in the response — writing it to a file is additive, never the hand-off | outbound-drafts | A | **IN** | S#22(c) | |
| R218 | Authored artifacts describe **roles and patterns, never named individuals** | outbound-drafts | A | **IN** | S#15 | Sibling of CM:L170 (memory-scoped); this is artifact-scoped |
| R219 | An artifact someone else will act on gets **bug-investigation rigor** — prior-session and summary facts are claims, and a published wrong fact transfers the error to an implementer who builds on it in good faith | outbound-drafts | A | **IN** | S#16 | |
| R220 | A **term you coin during consolidation propagates silently as if it were sourced** — a phantom label reached 19 sites and would have been falsely certified | outbound-drafts | A | **IN** | P:rereview-agent(22) | |
| R221 | When publishing internal tooling, **split by class** — the behavioral/diary layer is private, the reference/catalog layer is shareable — and make the shipped artifact **self-contained** so removed files leave no dangling citations (redefine citations as IDs) | outbound-drafts | A | **IN** | P:project_review_harness_share_repo(2), D:project_sovereign_multiprotocol_rail | |
| R222 | A share/publish pipeline is **re-runnable and scripted** (path rewrites, scrub greps, self-tests, install dry-run), never a one-time manual scrub | outbound-drafts | B | **IN** | P:project_review_harness_share_repo(3) | |
| R223 | A task labelled onboarding/easy that contains an **unmade design decision is a hard task wearing an easy label** — say so in the artifact | outbound-drafts | B | **IN** | S#16 | |
| R224 | Plans default to **chat**; a file only when explicitly requested — the bar is "did they ask for a written plan", not "is this big enough". Session working notes stay local; at most one durable maintainer-facing doc per change | outbound-drafts | B | **IN** | P:feedback_planning_doc_location(1,3) | |
| R225 | Never frame a nudge as **low-cost / high-return** — a nudge does not change the state it is nudging, and "wait for the reviewer" is a legitimate answer named directly. Lead a prioritization with what each item **unblocks**, never with what it clears: a queue length is a UI number | outbound-drafts | B | **IN** | S#53, S#55 | The brief's 2-file duplicate |
| R226 | Use the **published name** for a pattern in durable artifacts so they stay legible outside the repo | outbound-drafts | C | **IN** | P:feedback_fitness_functions_pattern(2) | |
| — | **CUT LINE — 16 rules ≈ 3,100 B. 1,900 B of headroom.** | | | | | |
| R227 | Significance is stated as a **fact**, not a claim; reserve trimming for genuine redundancy | outbound-drafts | C | OUT | D:feedback_docs_voice_factual_dense | CM:L118-120 |
| R228 | No **self-deprecation about how the code came to be** in an outbound artifact | outbound-drafts | C | OUT | D:feedback_no_internal_dialogue (PAS twin) | Folded into R211 |
| R229 | Every outbound artifact carries the **verified head id** and a footer split into Ran / Not-run | outbound-drafts | A | OUT | S#22(b) | Already in the `pr-review-method` draft — R2, keep one copy there |
| R230 | Strategy and motivation stay in private notes; the committed document is the **neutralized technical version** | outbound-drafts | A | OUT | D:project_sovereign_multiprotocol_rail, S#88 | CM:L113-116 verbatim |

---

# 7. `craft-skill` — 10 IN / 2 OUT (**under budget**)

| id | principle | dest | rank | IN/OUT | merged-from | notes |
|---|---|---|---|---|---|---|
| R231 | An **installed copy of a skill or plugin is a point-in-time snapshot with a flattened layout** — when reviewing a branch that changes it, the repo tree is the doctrine and anything the loader serves is possibly stale. Say which one you used; if a dogfood run behaves like the old doctrine, suspect the snapshot before the change | craft-skill | A | **IN** | S#11 | SKILL-SET §3c; `review-prompt` cross-references |
| R232 | `allowed-tools` in skill frontmatter is **advisory in this harness — parsed, never enforced** — so a documented read-only stance is prose-enforced only, and any skill claiming tool-level enforcement overclaims | craft-skill | A | **IN** | P:prompt-harness-goal(3) | Distinct object from an *agent*'s `tools:` allowlist (RR Gate 2 A3), which **is** enforced |
| R233 | This harness scans a **flat skills directory** — grouped subdirectories require a plugin manifest entry or symlink installs | craft-skill | A | **IN** | D:norbert-skills-temporal-design | |
| R234 | A third party's skill can hardcode **their** clone paths and a stale version pin — check both before relying on it | craft-skill | A | **IN** | D:reference_verify_spec_skill_not_portable | |
| R235 | A hardening program can be **doctrine-complete and check-incomplete** — a principle with no concrete mechanical check to fire on catches nothing | craft-skill | A | **IN** | S#89(a) | |
| R236 | A fix correct for **one** case becomes a bug when generalized into the template — verify a proposed default against the corpus's **actual distribution** before making it the default | craft-skill | A | **IN** | S#89(b) | |
| R237 | Key a heuristic to the **pattern with a pluggable lexicon**, never to one repo's quirk — a repo-keyed heuristic is one manifestation presented as the rule | craft-skill | A | **IN** | S#15 | |
| R238 | Strip one-off provenance (numbers, dates, round counts) unless load-bearing — the rule extends to **skills, agent definitions and anything publishable**, not just memory | craft-skill | B | **IN** | D:feedback_generalize_memories_and_skills | |
| R239 | **Template adherence decays within hours** — audit the same day it ships | craft-skill | B | **IN** | P:temporal-backbone-design(18) | |
| R240 | Every threshold in a skill is a number, and **unvalidated defaults are explicitly marked unvalidated** | craft-skill | B | **IN** | P:temporal-backbone-design(3) | |
| — | **CUT LINE — 10 rules ≈ 1,900 B. 3,100 B of headroom.** | | | | | |
| R241 | A mechanism **states which tension it resolves, or it is ornament** | craft-skill | C | OUT | P:temporal-backbone-design(15) | |
| R242 | Each maturity level is justified by the **prior level's measured pain** | craft-skill | C | OUT | P:prompt-harness-goal(10) | |

---

# 8. `craft-context-file` — 13 IN / 0 OUT (**under budget**)

| id | principle | dest | rank | IN/OUT | merged-from | notes |
|---|---|---|---|---|---|---|
| R243 | A reference file named `claude.md` **case-collides with `CLAUDE.md` and auto-injects as project instructions** — observed live; disambiguate the filename | craft-context-file | A | **IN** | P:prompt-harness-goal(6) | |
| R244 | The characteristic defect of a **multi-file instruction corpus is one canonical file contradicting another**, and per-artifact linting is structurally blind to it because each rule judges one artifact and each changed file is self-consistent. A green suite plus a clean lint proves nothing about a cross-file invariant | craft-context-file | A | **IN** | P:corpus-contradictions(1) | |
| R245 | A corpus-level check loads the whole set in **one process**, is verified **by injection**, and **fails loud when its own anchors go missing** ("cannot safely enforce X") rather than silently disabling | craft-context-file | A | **IN** | P:corpus-contradictions(2) | |
| R246 | **A skill or check does not fire unprompted** — an imperative routing directive in the always-on file takes embedded firing from 3/28 to 14/14. Recall is not enforcement: wire the check into the instruction that fires it | craft-context-file | A | **IN** | RR Gate 3, P:reference_per_diff_review_detectors(8), S#56 | |
| R247 | Agent sessions are **stateless, so the durable doc IS the handoff** and the bus-factor protection — map every named-role process control to an artifact an agent can execute cold (pattern drift → a cold-context review pass; irreversible-cut safety → a runbook executable from cold context) | craft-context-file | A | **IN** | D:feedback_agent_team_execution_model | CM:L23-24 says "map each to an agent equivalent" without the mapping |
| R248 | Contributors follow the **most legible in-repo authority** — if only the external spec is legible in-repo, every review converges on spec-shape. Install your control as citable in-repo law rather than per-PR argument | craft-context-file | A | **IN** | S#87 | |
| R249 | A plan or design document **drifts from the code faster than the code does** — every load-bearing constant in it is a claim, and a repo's own notes cite artifacts that were never built | craft-context-file | A | **IN** | P:flask_migration(8), P:project-salesagent-lessons(12) | |
| R250 | When a change makes a **standing decision's wording false, amend the decision row** — "spirit survives, letter misleads" is a trap; flag immutable-once-set parameters at the point of setting | craft-context-file | A | **IN** | P:project-hermes-fleet-plan(20) | |
| R251 | When a refactor deletes the **mechanism a rule cites, re-verify the rule** — it may survive with a new reason; do not retire it as stale | craft-context-file | A | **IN** | P:feedback_a2a_wire_tests(2) | Refines RR R1 |
| R252 | In a durable document, **cite a reference by NAME, not by line number** — line citations drift | craft-context-file | A | **IN** | P:feedback_mock_only_tests(3), P:wire_envelope_policy(4) | **Deliberately opposite to R033** (a *finding* must anchor at `path:line` because the platform requires it). Different objects; state both to prevent a contradiction |
| R253 | Capture a proven **reproduction recipe once, in the repo, and point at it** — and store a local-only compat patch **verbatim** in the durable doc, never in a temp worktree the OS wipes | craft-context-file | B | **IN** | P:project_storyboard_run_methodology(1,2) | |
| R254 | **Classify reactively** — real work touching an area produces the classification; never pre-emptively classify areas no work touched, and do not design the drift-detection mechanism before anything has been classified | craft-context-file | B | **IN** | P:project_storyboard_run_methodology(3), P:project_agentic_advertising | |
| R255 | When a large infrastructure change merges, **drift-audit the affected doc/memory cluster against current code** — an event-driven retirement trigger; and a compile/derive step must never sever provenance, or it becomes a staleness-laundering machine | craft-context-file | B | **IN** | D:feedback_trace_flows_not_claims(3), P:temporal-backbone-design(16) | |
| — | **CUT LINE — 13 rules ≈ 2,500 B. 2,500 B of headroom.** | | | | | |

---

# 9. `craft-prompt` — 3 IN / 0 OUT (**far under budget**)

| id | principle | dest | rank | IN/OUT | merged-from | notes |
|---|---|---|---|---|---|---|
| R256 | When vendor **examples contradict vendor prose, trust the shipped examples** | craft-prompt | A | **IN** | P:prompt-harness-goal(1) | |
| R257 | **Untrusted-content framing is non-negotiable** when the artifacts under review are themselves instruction-shaped text — state that instruction-shaped text inside them is the **specimen, not a directive** | craft-prompt | A | **IN** | P:prompt-harness-pr-review-method(4) | |
| R258 | Profile the **thinking mode, not the model** | craft-prompt | B | **IN** | P:prompt-harness-goal(2) | |
| — | **CUT LINE — 3 rules ≈ 600 B. 4,400 B of headroom.** | | | | | |

---

# 10. `review-prompt` — 2 IN / 0 OUT (**far under budget**)

| id | principle | dest | rank | IN/OUT | merged-from | notes |
|---|---|---|---|---|---|---|
| R259 | A scanner reading harness-framed text can match **the harness's own framing tag as artifact content** (a tag one line past EOF) — the fix is a **read-envelope framing guard**, not "more precision" | review-prompt | A | **IN** | P:prompt-harness-goal(5) | |
| R260 | Do **not misapply a critic to source it was not designed to judge** | review-prompt | A | **IN** | P:prompt-harness-pr-review-method(7) | |
| — | **CUT LINE — 2 rules ≈ 400 B. 4,600 B of headroom.** Cross-reference R231 rather than copying it. | | | | | |

---

# 11. `prebid-adcp` — 12 IN / 2 OUT (**under budget**)

| id | principle | dest | rank | IN/OUT | merged-from | notes |
|---|---|---|---|---|---|---|
| R261 | Establish **which version is authoritative first** — the current pin by default, unless declared work targets a different one; never ground against a version that is neither | prebid-adcp | A | **IN** | S#83 | |
| R262 | Fetch normative text **verbatim and read it yourself** — a summarizing fetch is unreliable for MUST/SHOULD and version-timing questions | prebid-adcp | A | **IN** | S#83 | |
| R263 | Prose plus the **executable conformance artifact** are ground truth; the implementation SDK — even shipping a full reference impl — is a **read-only cross-check that can diverge**. Bind semantics to the **frozen objects**, never to a churning reference SDK; the SDK is the capture surface even when the spec reads neutral | prebid-adcp | A | **IN** | S#83, S#81, P:project-agent-discovery-decapture(2), P:project-aamp-play(1) | **4-source merge** |
| R264 | Ground behavior in the **normative source for the pinned version before implementing** — a downstream artifact shipping an error code tells you nothing about *when* to emit it, and an internal contract or gap item is not the spec. Two reviewers and three rounds can polish the wrong feature without questioning the premise | prebid-adcp | A | **IN** | S#78 | |
| R265 | The **SDK↔spec mapping is usually not in package metadata** — it is discoverable only per-artifact (a bundled version file, an accessor). Derive it from the installed artifact, never from release notes | prebid-adcp | A | **IN** | S#82 | The file's own anchor is self-declared unstable (R1) — carry the method, not the table |
| R266 | A citation naming a spec version must name the version where the feature **entered**, not the version you happen to pin | prebid-adcp | A | **IN** | S#82 | |
| R267 | A conformance grader can grade **your own** system fully (you own the internal log) but only a third party's **observable responses** — for a third party it **corroborates, it never clears**, and it cannot distinguish a real implementation from a schema-valid shell | prebid-adcp | A | **IN** | P:project-technical-grading(1) | |
| R268 | **Surface-minimization**: declaring few capabilities makes a slice look conformant, because **undeclared reads as "not tested", not "failed"** — declared breadth must be first-class and cross-checked against observed, and every declaration creates a per-item obligation that must be linked to it | prebid-adcp | A | **IN** | P:project-technical-grading(2), P:project_teal_pr_remediation(2) | **Cross-source merge** |
| R269 | Match the **condition** to a cited precedent's **specific branch** — a surface match is a false premise that a strong reviewer will confirm and be wrong about | prebid-adcp | A | **IN** | S#80 | Coherence-vs-correctness half is R099 |
| R270 | An **umbrella standard that delegates its transport owns only frozen-object semantics** — the object substrate is ratified, the agent-wire layer is reference-code-only; the neutral cross-org primitives are the unowned seat | prebid-adcp | A | **IN** | S#81, P:project-aamp-play(1) | Dated maturity map stays in the silo (R300) |
| R271 | Make extensions **additive-and-ignorable** — strip them and the payload is still valid under the base spec, proven by a guard test | prebid-adcp | A | **IN** | P:project-aamp-play(2) | |
| R272 | A **code generator can diverge from its spec and FORCE a value**, so the wire can carry a spec-questionable value no local choice can fix | prebid-adcp | B | **IN** | S#84 | |
| — | **CUT LINE — 12 rules ≈ 2,300 B. 2,700 B of headroom.** | | | | | |
| R273 | **Forward-compat grading unknown checks as PASS** while the party pins an old version — set a version floor at current-minus-N | prebid-adcp | B | OUT | P:project-technical-grading(2) | |
| R274 | A release-precision identifier space and a full-semver one **false-positive on a naive equality check** — normalize before comparing | prebid-adcp | B | OUT | D:adcp-kernel-empirical-anchors | |

---

# 12. MACHINE — 13 rows (no cap defined; see §15)

Machine/harness-level facts that no repo owns. `SKILL-121-split.md` identifies 21 instances in
this class and calls the missing destination "a gap in the destination taxonomy".

| id | fact | dest | rank | IN/OUT | merged-from | notes |
|---|---|---|---|---|---|---|
| R275 | A launch that **exits 0 while spawning no process** is a stale single-instance lock naming a dead PID or a reboot-cleared socket — check the lock before reinstalling. Signature: `unmarshaling start request: unexpected EOF`; **deleting `backend.lock` does not fix it** | MACHINE | A | **IN** | S#2 | The `rm Singleton{Cookie,Lock,Socket}` fix is CM:L51-52 verbatim — R2, do not re-file |
| R276 | `timeout` is **not installed on this Mac** (`which timeout` → not found) | MACHINE | A | **IN** | P:reference_agentdb_port_mismatch | Verified live in the source pass; re-verified as a constraint on this task |
| R277 | Crash-forensics signature: `*.meta.json` without `agent-*.jsonl` = transcripts lost; a ~100-byte parent transcript is the tell | MACHINE | A | **IN** | S#1 | |
| R278 | Venv corruption: reinstall rather than sync — the manager's own metadata says "audited N packages" over unimportable files | MACHINE | A | **IN** | S#102 | Principle is R103 |
| R279 | Editors reuse the window keyed to the **folder**, so two targets in one repo hijack each other's window — a per-target checkout is what buys isolation | MACHINE | B | **IN** | S#14 | Four zsh functions in one auto-sourced file |
| R280 | Disk preflight reads the **data volume** (`/System/Volumes/Data`), not the sealed root; reclaim order at exhaustion; `TMPDIR` workaround | MACHINE | A | **IN** | S#6 | Command is CM:L43 |
| R281 | The pre-commit **stash cache path** — where a hook parks unstaged work mid-operation | MACHINE | B | **IN** | S#29 | |
| R282 | A **stale exported env from a previous container generation** desyncs silently from the actual listening port — compare the process's env against the listener | MACHINE | A | **IN** | P:reference_agentdb_port_mismatch | |
| R283 | The **system Python fails TLS verification** against some hosts — drive the CLI via subprocess instead | MACHINE | A | **IN** | P:no-real-names-in-db | |
| R284 | **Orphaned children hold pipes past kills** — a runner needs a process-**group** kill | MACHINE | A | **IN** | P:prompt-harness-goal(8) | |
| R285 | The **append-to-subagent-system-prompt flag pierces all nesting depths** and is the only reliable non-negotiables channel headless; hooks receive the agent type, so per-depth capture is free | MACHINE | A | **IN** | P:project-hermes-fleet-plan(18) | Subagent transcript path is CM:L135 |
| R286 | A **buildx cross-compile output path plus `/private/tmp` xattr failure** on this host | MACHINE | B | **IN** | S#75 | |
| R287 | `zsh` treats bare `$r:path` as the `:s` history modifier — braces are load-bearing in a `git show` loop | MACHINE | B | **IN** | S#28 | Currently inline in the git draft; move here or keep as a parenthetical |

---

# 13. REPO — stays in the silo (66 PROJECT files survive as instance-only)

The 66 PROJECT files are **not deleted**. Each keeps its instance; the rows above record where
its principle went. The rows here are principles that are **universal but have no destination in
the fixed set** — they are parked at repo level and are a finding about the skill set, not a
routing decision. Grouped by mechanism family; every source file named.

| id | family (each row = one homeless principle cluster) | dest | rank | IN/OUT | merged-from | notes |
|---|---|---|---|---|---|---|
| R288 | **Mechanism vs authority**: split every capability into a testable coordination mechanism and an authority (trust root, identity, money); own the mechanism, never the authority. The test: is it provable by a test referencing no domain meaning and no party's trust relationship? | REPO:agentic-prebid | A | OUT | P:project-neutral-primitives-charter | **NO-HOME.** Crispest architecture test in the corpus; nothing in the 10-skill set claims design |
| R289 | **Typed boundaries**: one typed internal representation, serialize only at system boundaries, errors are typed models too; an untyped dict boundary silently matched nothing and ran with empty parameters, spending real money invisibly | REPO:agentic-prebid | A | OUT | P:project-salesagent-lessons(1,2,4,5,6,10) | NO-HOME |
| R290 | **Containment and threat modelling for autonomous components**: components PROPOSE, the kernel DISPOSES; gate on witnessed facts never authored state; state the adversary once as a capability set; seam-by-seam verification is blind to cross-seam composition; sequential quorums compose as `min`, not sum; "X happened" ≠ "X was authorized" | REPO:agentic-prebid | A | OUT | P:project-threat-model(1-9) | NO-HOME. (5) is the one clause that reached `agent-dispatch` as R169/R181 |
| R291 | **Authority-layer security invariants**: resolve controller × scope × fact-type not just kind; a feature's headline capability is its attack surface; monotonicity checks are direction-blind; no domain separator ⇒ a re-aimable signature; self-issuance collapse; emit a source×assurance set never a scalar | REPO:agentic-prebid | A | OUT | P:project-authority-layer(1-9) | NO-HOME |
| R292 | **Economic independence**: independence must be economic, not cryptographic — key disjointness does not imply interest-independence; record who funded and who selected any attestation; check disjointness over the union of witnesses and fee beneficiaries; a re-signed reading is two roots, one observation | REPO:agentic-prebid | A | OUT | P:project-reference-agents(1,2,3,4,6,7) | NO-HOME. (5) reached `agent-dispatch` as R169 |
| R293 | **Deferred-action safety**: a durably-committed transition atomically enqueues its reactions; guards evaluated at enqueue and re-checked only for legality at drain are a **TOCTOU** — re-evaluate the full precondition at the commit fence; an approval bound to an ID rather than a content digest permits a post-approval swap | REPO:agentic-prebid | A | OUT | P:project-transition-as-trigger(1-8) | NO-HOME |
| R294 | **Real-money invariants**: a safety check's failure mode is HALT not continue; compensate forward, never edit the old record; act only on ≥2 independently-sourced facts with no single-source fallback; a ceiling without a floor is half an authority model | REPO:agentic-prebid | A | OUT | P:project-real-money-first(1,2,3,4,5,8) | NO-HOME. (6),(7) reached R169/R050 |
| R295 | **Seam illusions and vendor risk**: a "swap X for Y behind a thin seam" hatch can be semantically illusory — the seam ports the interface, not the guarantees; mitigate vendor risk by design not vendor health; usage may grow but **import sites may not** | REPO:agentic-prebid | A | OUT | P:project-positioning-and-core-decisions(1-4) | NO-HOME. Named the sharpest architecture insight in the corpus |
| R296 | **Two-role symmetry / two-seat**: the role is a filter derived from the authenticated principal and narrows, never widens; two parties measuring different events need a structural tolerance band; design corroboration so the two sources have opposed incentives | REPO:agentic-prebid | A | OUT | P:project-two-seat-model(1-7) | NO-HOME |
| R297 | **Unbundling a gatekeeper**: identity at the party's own domain, capability self-published, findability via plural indexes, authority as a signed mandate; being in a registry is not a trust signal; make the dependency deletable and prove it with a test | REPO:agentic-prebid | A | OUT | P:project-agent-discovery-decapture(1,3-7) | NO-HOME. (2) reached R263 |
| R298 | **Config-first / pivot / substrate**: policy becomes schema-validated config with layered precedence and strong defaults; never let a foreign system's identifier be your primary key; when two formats have no lossless translation both project through a superset pivot | REPO:agentic-prebid | A | OUT | P:project-configuration-first, P:project-order-of-record-pivot, P:project-substrate-ownership-strategy | NO-HOME |
| R299 | **Migration sequencing**: freeze the external contract and lock it with protective tests before layer 0; introduce the indirection early so the semantic cutover is a one-line alias flip; each layer gets a machine-checkable exit gate; a paused programme records its resume preconditions | REPO:agentic-prebid | A | OUT | P:flask_to_fastapi_migration_v2, P:flask_migration(6,7), D:project_sovereign_multiprotocol_rail | NO-HOME. `refactor-safety` was correctly refused; this content still has nowhere to go |
| R300 | **Human surface / distribution / fleet architecture**: the surface is a typed API not a UI; choose a CI-distributed tool's language for its distribution properties; per-field provenance; two grains that cannot be joined reconcile at the grain boundary; substitution map; hermetic renderer | REPO:agentic-prebid, REPO:adcp-tooling, REPO:hermes | B | OUT | P:project-human-surface, P:adcp-kernel-tool-is-go, P:project-hermes-fleet-plan(7-13,16) | NO-HOME |
| R301 | **Supply-chain posture**: vendor a thin single-maintainer library behind your own implementation; pin and wrap a package with no release in a year; keep the type-gate on a checker not owned by the same vendor as the toolchain; a hosted model has no reproducibility guarantee, which upgrades record-and-replay from prudent to necessary | REPO:agentic-prebid | A | OUT | D:project-tech-stack-audit | NO-HOME |
| R302 | **Org posture, identity, adapter porting, repo path maps** — 8 files, all Gate-4 repo-level by construction | REPO:agentic-prebid, REPO:prebid-agent-skills, REPO:salesagent | — | OUT | S#86, S#87, S#88, S#91, and 4 more per SKILL-SET §3b | Correctly siloed. Do not promote |
| R303 | **Instance-only remainders** of the 121 SKILL-routed files after their principle travelled: PR numbers, file:line anchors, class and adapter names, version tables, charter section ids | REPO:salesagent (majority), REPO:agentic-prebid, REPO:rereview-agent, REPO:prompt-harness, REPO:adcp-tooling | — | OUT | all 121 | Each source file is rewritten down to its instance and stays in place |
| R304 | Repo-bound library internals: pinning a connection to a validated address must not disable hostname verification; two transports serialize the same model through different paths, so a field excluded only in a dump override still ships on one wire | REPO:salesagent | A | OUT | S#96, S#98 | SKILL-SET §3a: repo-bound by construction. The oracle clause travelled as R077(iii) |
| R305 | Dated external-product facts with a nameable expiry (a vendor capability roadmapped for later 2026; an unratified standard's maturity map) | REPO:salesagent, REPO:agentic-prebid | — | OUT | S#76, S#81 | `SKILL-121` routed these to MEMORY; **there is no MEMORY destination in the fixed set.** Write the expiry event on line 1 of the silo file. Principles travelled as R057, R270 |

---

# 14. DROP — 3 vacuous / 26 already in `CLAUDE.md`

| id | item | dest | notes |
|---|---|---|---|
| R306 | "A reference file the user maintains lives at a known path; open it when relevant" | DROP-vacuous | P:cmux-shortcuts-cheatsheet. Anchor verified to exist; file correctly filed, leave it |
| R307 | "The project is named for a person the user admires; ground explanations in it" | DROP-vacuous | P:user-norbert-wiener |
| R308 | "Its instruction is actively wrong now" — a `model` pin contradicted by inherit-the-session-model | DROP-vacuous | D:feedback_subagent_model — the only DELETE-48 file that is genuinely safe to delete on content |
| R309 | 26 principles already always-on verbatim or near-verbatim | DROP-already-in-CLAUDE.md | S#1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 13, 16, 24, 26, 38, 50, 53, 55, 56, 58, 62, 66, 78, 88, 89, 103 — the R2 list from `SKILL-121-split.md`. **Each is registered above at the clause level where a non-duplicate residue survives**; this row records the duplicate halves that must not be re-written anywhere |

---

# 15. Per-destination summary

| destination | IN | OUT | est. bytes IN | cap | verdict |
|---|---:|---:|---:|---:|---|
| `~/.claude/CLAUDE.md` | 8 | 7 | ~900 B / 11 lines added | ~9 lines (SKILL-SET §5) | **2 lines over** — see §16 |
| `pr-review-method` | 26 | 31 | ~5,000 B | 5,000 B | **AT CAP; 31 A/B-rank rules displaced** |
| `testing-ci` | 26 | 42 | ~5,000 B | 5,000 B | **AT CAP; 42 rules displaced (21 of them rank A)** |
| `git-workflow` | 20 | 8 | ~5,000 B at 250 B/rule | 5,000 B | **AT CAP only if the 17 drafted rules compress from 300 B to 250 B** |
| `agent-dispatch` | 26 | 16 | ~5,000 B | 5,000 B | **AT CAP** |
| `outbound-drafts` | 16 | 4 | ~3,100 B | 5,000 B | 1,900 B headroom |
| `craft-skill` | 10 | 2 | ~1,900 B | 5,000 B | 3,100 B headroom |
| `craft-context-file` | 13 | 0 | ~2,500 B | 5,000 B | 2,500 B headroom |
| `craft-prompt` | 3 | 0 | ~600 B | 5,000 B | 4,400 B headroom |
| `review-prompt` | 2 | 0 | ~400 B | 5,000 B | 4,600 B headroom |
| `prebid-adcp` | 12 | 2 | ~2,300 B | 5,000 B | 2,700 B headroom |
| MACHINE | 13 | 0 | ~2,400 B | none defined | see §16 |
| REPO (incl. NO-HOME) | 0 | 18 rows / ~90 principles | — | — | 14 rows are universal-but-homeless |
| DROP | 4 rows | — | — | — | 3 vacuous + 26 R2 duplicates |
| **totals** | **175 IN** | **130 OUT (80 + 50 →refs) + 4 DROP** | | | **309 rows** |

---

# 16. Findings that are not routing decisions

**1. Two skills are over-subscribed by 2.6× and 1.2×, and the overflow is mostly rank A.**
`testing-ci` has 68 candidates for 26 slots; 21 of the 42 displaced are rank A (a false green
ships). `pr-review-method` has 57 for 26. The `→refs` marking on 34 rows is a recommendation,
not a deferral: a `references/*.md` file in the skill directory costs zero always-on bytes and
zero body bytes, and the 5,000 B cap in `report-structure.md` is a **body** cap. If refs are
not permitted, those 34 rules are lost and the loss should be recorded as such.

**2. Four skills are 66% empty while two are 160% full.** `craft-prompt` (600 B),
`review-prompt` (400 B), `craft-skill` (1,900 B) and `craft-context-file` (2,500 B) hold
4,400 B of unused body between them. This confirms `report-structure.md`'s finding from the
other direction: the craft-* family's cost is in its **descriptions**, not its bodies, and the
corpus has almost nothing to put in them.

**3. `MACHINE` has no defined container, no cap, and no loading mechanism.** 13 rows land
there. `SKILL-121-split.md` called this "a gap in the destination taxonomy" for 21 instances.
The fixed destination set names MACHINE as "the `-Users-quantum` home silo" — a project-memory
directory, which per CM:L14 **does not load across directories**. Three of these rows (R275
docker signature, R276 missing `timeout`, R283 TLS failure) are ones an agent needs *in another
project's directory*. Routing them to a non-loading silo is the exact failure ROUTING-RULE
Gate 0 exists to prevent. **This needs a decision I could not make from the fixed set.**

**4. Fourteen universal principles have no home in the 10-skill set** — R288–R301, roughly 90
sub-principles across 18 PROJECT files: architecture, security design, threat modelling,
authority modelling, migration sequencing, supply-chain posture. `SKILL-SET.md` correctly
refused `refactor-safety` and `python-tooling-traps` on the trigger-surface test, and
`PROJECT-66-and-DELETE-48.md` proposed `system-design` for exactly this content — a container
the fixed set does not include. They are parked at REPO and will not travel. **This is a
finding about the skill set, not a routing failure**, and it is the largest single block of
non-travelling universal content in the corpus.

**5. `MEMORY` is absent from the fixed destination set** but ROUTING-RULE Gate 5 exists and
two files qualify (R305). Their expiry event must be written into the silo file's line 1
instead; nothing is lost, but Gate 5 currently has no destination.

**6. `CLAUDE.md` additions land at 11 lines against SKILL-SET §5's ~9.** I kept R008 (approval
is scoped to the step approved) over R012 (crash scope), which SKILL-SET §3i had already
nominated as the first to drop. R009–R015 are the ranked queue if two more lines are refused.

**7. One deliberate two-channel duplicate survives**: R029 / R073 (a detector's scan set is
part of its claim) is written into both `pr-review-method` and `testing-ci`. ROUTING-RULE R2
says delete the copy — but R2's test is "two channels that both load on the same dispatch", and
these two never do. The 43 PR rules' primary consumers are review lenses whose `tools:`
allowlists omit `Skill` entirely (SKILL-SET §7.1), so for that population `testing-ci` is
invisible. Recorded as an intentional violation with its reason, not an oversight.

**8. One live contradiction between two IN rows, both correct**: R132 ("default to resurrect a
dead test with strengthened assertions") vs R133 ("a test pinning a dead shape gets deleted").
R133 is OUT, so the bodies will not contradict — but if R133 is ever promoted, the
discriminator must ship with it: does the pinned shape still exist in production?

**9. R252 vs R033 is a second apparent contradiction that is not one**: a *finding* anchors at
`path:line` because the platform's API rejects anything else; a *durable document* cites by
name because line citations drift. Both are IN, in different skills. Both bodies must state the
object they apply to or a reader will treat one as a violation of the other.

**10. Anchor failures inherited from the sources, carried forward as corrections**: S#54's
`bd create` (CM:L21 bans it), S#22/S#67's "gold standard" (CM:L115 bans it in output),
S#82's self-declared unstable pin, S#79's fan-out sentence (contradicts CM:L31), and
`feedback_opus_verification`'s `model: "opus"` (contradicts CM:L55). Each is stripped in the
row that carries the principle.

---

# 17. Merges I was least confident about

Ordered by how much a wrong call costs.

1. **R078 absorbs "guarantees asserted, never exercised" (hermes 2) and "a prediction without a
   tripwire is a worry" (temporal 1) into "a claimed invariant needs a failing oracle" (S#105).**
   Same mechanism — an assertion with no red path — but hermes(2) is an *audit class* with five
   named instances (a scrub step never tested, an archive never read back, nothing watching the
   watchdog) and S#105 is a *review checklist* with five different ones. Merging keeps one rule
   and loses one of the two instance lists. **If separated, the second row is "audit your own
   controls for the ones nobody has ever exercised" and it belongs in `testing-ci`.**
2. **R077 (the three-part reliability rule) overlaps R073 (scan set), R074 (matcher), R079
   (production reachability).** R077 is the general form of which the other three are clauses.
   I kept all four because each fires on a *different observed symptom* and the general form has
   never been observed to fire on its own. This is the registry's largest deliberate
   redundancy — ~760 B of `testing-ci` for one mechanism family.
3. **R086 merges five files into "a test entering below the boundary verifies the layer below".**
   The five differ in *which* layer is skipped (handler vs wire, middleware vs in-process, mock
   vs real credential chain, model vs entry point). If any body needs to name the skipped layer
   to be actionable, this merge is too aggressive.
4. **R006 merges the AdCP source ladder (S#79) with the debugging evidence hierarchy
   (`feedback_trace_flows_not_claims`).** Both are ordered source hierarchies with a
   never-let-a-lower-tier-overrule clause, derived independently. The tiers themselves are not
   identical — one is about external systems, one about claims inside your own repo.
5. **R095 merges four train==test statements** including temporal(6)'s "a principle abstracted
   from the cases you found and claimed as a bound on all cases is circular". That one has an
   extra clause the others lack — it is testable **only by searchers not told the principle** —
   which is a dispatch instruction, not a testing one. It may belong in `agent-dispatch` beside
   R173.
6. **R053 merges "find the consumer, not the declaration" with "a declared capability creates a
   per-item obligation".** The first is a verification move, the second is a design obligation.
   Kept as one because both fail the same way: something looks implemented and nothing reads it.
7. **R043 merges the sweep-undercount finding (106 explicit sites ≈ 55–60% of the real surface)
   with "sweep twice: identifier then semantic claim".** Very likely one mechanism. Left merged
   but flagged because the numeric evidence belongs to only one of the two sources.
8. **Kept separate although tempting**: R073/R074 (scope vs oracle strength — the brief's own
   example); R054/R073 (moving code out of a scan set vs stating the scan set); R098/R074
   (build detectors from escaped defects vs prove red on an unmodelled form — the first is about
   the *source* of cases, the second about *coverage* of forms); R132/R133 (resurrect vs delete
   a dead test); R033/R252 (anchor by line vs cite by name).

---

# NOT DONE

- **No file was written except this one.** `~/.claude/` is otherwise untouched: no skill, no
  memory, no config, no source file was read-modified. `claude -p` was not run.
- **No skill body was drafted.** This registry assigns rules and draws cut lines; it does not
  write the 5,000 B bodies. The 190 B/rule floor is inherited from the prior audit, not
  re-measured here — a body written at 250 B/rule holds 20, not 26, and every AT-CAP verdict
  moves.
- **Byte estimates for IN sets are `count × 190 B`, not measured text.** The only measured
  figures are the three whole-file sizes and the two draft body sizes in the header.
- **I did not re-read the 121 SKILL-routed source files, the 66 PROJECT files, or the 48 DELETE
  files.** Every principle statement here derives from the two extraction documents. Where those
  two disagree about a destination (S#35, S#84, S#91, S#111, S#14) I followed `SKILL-SET.md` as
  settled and recorded the dissent in the row's notes; I did not adjudicate any of them against
  the original file.
- **The 500 / 191 / 309 counts are derived from this table**, not an independent recount of the
  sources: 500 = total `merged-from` entries, 191 = entries beyond the first on each row, 309 =
  rows. A `merged-from` pair like `GD, S#23` counts as a collapse even though it is one
  principle traced through two documents rather than two independent derivations; roughly 40 of
  the 191 are of that kind. A different splitting judgement on the multi-part files
  (`project-hermes-fleet-plan` alone carries 20, `rereview-agent-goal-and-decisions` 22,
  `temporal-backbone-design` 19, `reference_review_patterns` ~30) moves the raw number by ±60.
  The dedup count (97) is the number of `merged-from` entries beyond the first on each row.
- **REPO rows R288–R303 are registered at cluster grain, not one row per principle.** ~90
  sub-principles sit behind 16 rows. They compete for no budget and their full text is already
  enumerated in `PROJECT-66-and-DELETE-48.md` §1B/§1C. If the system-design gap (§16.4) is ever
  filled, that block must be re-split at principle grain before it can be routed.
- **No trigger or firing behaviour was tested**, for any destination. Inherited from
  `SKILL-SET.md`'s own NOT MEASURED section: no proposed description has been exercised against
  a fresh session.
- **I did not verify any anchor** cited inside a principle — no `gh` call, no container, no test
  run, no grep against a repo. The five anchor failures in §16.10 are relayed from the source
  documents, not re-checked, with one exception: the draft body sizes and rule counts in the
  header, which I measured.
- **Gate 1 (TOOL) was not run on any row.** R024 is the corpus's one asserted TOOL candidate and
  it is asserted on T1/T2 only, inherited from `SKILL-121-split.md`.
