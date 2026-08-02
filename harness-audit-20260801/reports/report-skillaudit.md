Read all 8 skills, `~/.claude/CLAUDE.md`, FINDINGS §6b/§6d, and surveyed all 241 memory files across 12 silos. Report follows.

---

## 0. Measurement reconciliation

My count of description text is **4,916 B** vs the lead's 5,010 B. The delta is the `description: ` YAML key (13 B × 8 = 104 B). Same measurement, different boundary — I use description *text* throughout, since that plus `- <name>: ` is what actually renders in the msg[1] skills listing. Bodies (post-frontmatter) measure 2,182–11,636 B.

| skill | desc B | body B |
|---|---|---|
| craft-context-file | 968 | 7,946 |
| craft-skill | 764 | 8,406 |
| review-prompt | 760 | 7,011 |
| craft-prompt | 626 | 11,636 |
| pr-review-method | 490 | 6,497 |
| testing-ci | 451 | 3,855 |
| git-workflow | 443 | 2,893 |
| prebid-adcp | 414 | 2,182 |

**The distribution is inverted against the cost model.** The three largest descriptions (craft-context-file, craft-skill, review-prompt = 2,492 B, 51% of the tax) are the three whose descriptions contain the most *mechanism narration* — text that describes how the skill works, which never appears in a user's request and therefore contributes nothing to selection. The four operational skills (git/pr/testing/adcp) already have near-optimal descriptions and thin bodies. So the tax is concentrated exactly where it buys least, and the free tier is emptiest where the knowledge is richest.

---

## 1. Per-skill: description rewrites and body assessment

Every rewrite below is a plain YAML scalar, safe to paste as `description: <text>` (no leading quote, no `: ` sequence).

### craft-context-file — 968 B → 570 B (−41%)

```
Writes and prunes always-on agent context files — AGENTS.md, CLAUDE.md, GEMINI.md — keeping only non-derivable facts inside each harness's budget and routing the overflow to skills, hooks, or scoped files. Use to create, write, generate, prune, trim, or regenerate an AGENTS.md, CLAUDE.md, GEMINI.md, repo instructions, or project context file, or when one is bloated, over budget, or ignored. Authoring only — "review our CLAUDE.md" and "why does the agent ignore repo rules" are review-prompt. Not craft-prompt (single prompts) or craft-skill (packaging skills).
```

**Cut (safe):** the 330-B mechanism clause — "Scans the repo for non-derivable facts (exact commands, non-default conventions, repo etiquette, environment gotchas), enforces per-harness budgets (CLAUDE.md-class under 200 lines, AGENTS.md-class under the 32KiB cap) … and reports why every item was kept, moved, or evicted." No user request contains these phrases. The 200-line and 32KiB numbers are Step-4 body content (`SKILL.md:32`) and are *already there*; duplicating them in the always-on tier pays for them on every request in every project to restate what the body says. Also compressed the two anti-trigger sentences into one.

**Kept (load-bearing):** all three filenames, twice — they are the strongest lexical hooks and appear verbatim in requests. The full verb list. Both literal user phrasings in the anti-trigger; those are the disambiguator against review-prompt and removing them is exactly the over-trim that causes wrong-skill selection.

**Body: complete.** Seven ordered steps, failure rules, red flags, verification. Nothing missing.

### craft-prompt — 626 B → 376 B (−40%)

```
Writes a prompt from an intent — outcome contract, stance, policy blocks, style profile — rendered for Claude, GPT, Gemini, or model-neutral. Use to write, create, draft, improve, or tune a prompt, system prompt, or agent instructions, and on "make me a prompt for X". Not for critiquing an existing prompt (review-prompt), packaging a skill (craft-skill), or copywriting.
```

**Cut (safe):** "high-quality" (empty), "builds an … selects a … applies a …" verb scaffolding around the four nouns (the nouns carry the meaning, the verbs don't), "(rigor, density, depth, voice)" — axis names are Step-3 body content, and a user asking for a prompt never names them. "when they mention prompt quality, style profiles, or model-specific phrasing" collapses into the verb list already present.

**Kept:** the three model family names — a user does say "a prompt for Gemini," and that's a real selection signal. The literal "make me a prompt for X". Explicit `craft-skill` in the anti-trigger, which the original left as bare "packaging full skills" without naming the skill.

**Body: complete, and the largest at 11,636 B — correctly so.** The Step-6 contradiction sweep (`SKILL.md:71-76`) is the single densest piece of real method in the set.

### craft-skill — 764 B → 523 B (−32%)

```
Scaffolds a complete Agent Skill directory from a purpose — evals first, then a trigger-engineered description, SKILL.md, references/, scripts/, portable frontmatter, and a validation report. Use to create, scaffold, package, or build a skill, SKILL.md, slash command, or reusable agent workflow; to turn a repeated workflow or house method into a skill; or on "make the agent do this the same way every time". Not for a single prompt (craft-prompt), critiquing an existing skill (review-prompt), or MCP tool definitions.
```

**Cut (safe):** "a navigation-hub SKILL.md under 500 lines" → "SKILL.md" (the 500-line cap is Step-4 body content, `SKILL.md:42`); "references/ and scripts/ split by determinism" → the two directory names (the split rule is Step 5); "spec-valid … with per-harness overlays" → "portable frontmatter" (overlays are Step 6). ~200 B of pure body restatement.

**Kept:** "evals first" — this is the skill's doctrine and its differentiator, and it survives in three words. All four artifact nouns (skill, SKILL.md, slash command, reusable agent workflow). Both literal phrasings.

**Body: complete.**

### review-prompt — 760 B → 582 B (−23%)

```
Critiques prompts, skills, and agent context files against an anti-pattern catalog and model-fit rules — contradictions, over-constraint, vague triggers, injection surfaces, missing safety gates — returning severity-ranked findings with fixes. Read-only, never edits. Use to review, critique, audit, lint, or check a prompt, system prompt, SKILL.md, AGENTS.md, CLAUDE.md, or GEMINI.md; when asked why an agent misbehaves or a skill won't trigger; or before committing prompt changes. Not for authoring (craft-prompt, craft-context-file), source code or PR diffs, or plan review.
```

**Cut (safe):** "versioned" (no trigger value), "emphasis spam, stale examples" from the catalog list (kept the five with request-shaped phrasings: someone does say "check this for injection" or "why won't it trigger"; nobody says "audit for emphasis spam"), "with mechanisms and concrete fixes" → "with fixes", "governance and experimental plans (use ordinary plan or methodology review)" → "plan review".

**Kept, deliberately:** "Read-only, never edits" promoted to its own short sentence. This is the *only* disambiguator against craft-context-file when both descriptions contain CLAUDE.md/AGENTS.md/GEMINI.md — it is the highest-value 24 B in the entire set and should not be trimmed further. Added `craft-context-file` by name to the anti-trigger; the original named only craft-prompt, leaving the more confusable neighbor unnamed.

**Body: complete.** The false-positive calibration block (`SKILL.md:31-38`) is the strongest part and is the kind of content that only earns its keep because bodies are free.

### git-workflow — 443 B → 438 B (−1%)

```
Git and gh mechanics that fail silently — confirming a commit actually landed, cutting the branch before the first edit, pre-commit hooks stashing your changes mid-run, `git grep -E` dropping `\b`, `git mv` aborting a staged add, a dirty mergeStateStatus making GitHub skip workflow runs. Use before running git or gh, when a git result is ambiguous, when a grep came back unexpectedly empty, or before any claim about repository state.
```

**Essentially no savings available, and that's the correct verdict.** This description is already at the floor: every clause is either a situation the agent can recognize itself or a distinctive token. The only change of substance is "stash/pre-commit-hook interaction" → "pre-commit hooks stashing your changes mid-run", which converts an abstract noun phrase into a recognizable situation at zero net cost. Do not trim this one for bytes.

**Body: THIN — expand to roughly 3×.** 2,893 B for a subject this failure-dense is under-built, and it is free to fix. Missing, all of it evidenced in stranded memories: `git_mv_then_add_old_path_aborts_commit` is present but `feedback_precommit_black_shifts_line_allowlists`, `prek_pre_commit_replacement_bug`, `uv_frozen_for_commit_drift`, `feedback_pr_base_current_main_push_origin`, `feedback_stacked_pr_ci_does_not_run` (via `reference_stacked_pr_ci_does_not_run`), `reference_release_jobs_invisible_to_pr_ci`, `reference_release_please_pr_ci_mechanics`, and `reference_github_code_quality_no_path_exclusion` are not. Also missing entirely: recovery procedures. The body tells you how each failure looks but not what to run once you're in it (detached HEAD, a `git add` aborted halfway, a stash that didn't pop). Add a recovery section.

### pr-review-method — 490 B → 503 B (+3%)

```
Method for reviewing a pull request and handling reviewer feedback — re-pulling all three GitHub comment endpoints plus GraphQL reviewThreads before any addressed/done claim, anchoring findings to path:line inline threads, splitting severity from disposition, grading remedy composition on re-review, consolidating subagent findings without dropping sites. Use when reviewing a PR or a working diff, responding to reviewer feedback, judging whether feedback has been addressed, or writing up findings.
```

**+13 B, spent to buy trigger coverage.** Added "or a working diff". The method applies identically to `/code-review` on an unmerged branch, and the current wording restricts it to PRs — a silent non-fire on the most common case. That's worth 13 B. Everything else is a wash; this description was already tight.

**Body: complete and the best-built of the eight.** 6,497 B, eight sections, every rule traceable to a specific incident. If anything add the `feedback_review_consolidation_drops_findings` mechanism — the body has "De-dup is not synthesis" but not the §6c finding that consolidation demonstrably lost four recommendations in this very audit.

### testing-ci — 451 B → 432 B (−4%)

```
Proving an existing test or CI signal is real — mutation-testing a call site, falsifying an empty red set, checking whether a `-k` selector selected anything, auditing guard matchers and allowlists for false confidence, deciding whether a green verdict can be trusted. Use when verifying a test would actually fail if the behavior broke, when a suite passed suspiciously, or when judging whether a green check means the check ran.
```

**Cut:** "actually" (one of two), "CI" from "green CI verdict" (redundant with "CI signal" in the opening). Trivial savings; this one is near the floor too.

**Body: adequate for its declared scope, but the scope is the problem** — see §6, `test-authoring`. `SKILL.md:8` states the boundary outright: "This is about **verifying strength**, not authoring." That's an honest scope statement, and it leaves the authoring half of a large, well-evidenced body of knowledge with no home anywhere.

### prebid-adcp — 414 B → 518 B (+25%)

```
AdCP and Prebid protocol authority and version resolution — grounds AdCP behavior in spec prose plus the graded conformance storyboard for the version pinned at runtime, treating SDK types, error codes, and reference implementations as a read-only cross-check, never the authority. Use when implementing, reviewing, or verifying AdCP or Prebid protocol behavior, error taxonomy, or recovery semantics; when a task touches the adcp package, a spec version pin, or an AdCP error code; or before citing an AdCP version.
```

**+104 B, and this is the one place I recommend spending.** Two additions:

1. **"Prebid"** — the word appears in the skill *name* but not the description. It reaches the listing via `- prebid-adcp:` so it isn't absent, but it carries no weight in the sentence the model actually reads for relevance.
2. **Situational triggers** — "when a task touches the adcp package, a spec version pin, or an AdCP error code". This is the fix for a **demonstrated** silent non-fire. The body records it (`SKILL.md:25-27`): a change "shipped the **inverse** of the idempotency rule and survived three review rounds because it was grounded in an SDK error code instead of spec prose." Nobody in that sequence asked a question matching "verifying AdCP protocol behavior" — they were editing a handler. An abstract-topic trigger cannot catch that; an artifact-shaped trigger can.

**Body: THIN — the highest-value expansion in the set, roughly 3–4×.** 2,182 B, the smallest body, guarding the most expensive documented failure. Missing: the actual authority-order commands (the body says "fetched verbatim via `gh api`" without the invocation), the introspection recipe from `reference_verify_spec_skill_not_portable` (which contains a *worked* example: verifying `BrandReference.domain` is lowercase-only by reading the Pydantic pattern), the recovery-enum contents referenced at `SKILL.md:48-49` as `error.json` and `transport-errors.mdx` without saying what's in them, and the SDK-bump field-by-field diff procedure (`reference_adcp_sdk_spec_mapping`, `reference_sdk_bump_delta_verification`). All of this is free.

**Net across all 8: 4,916 B → 3,942 B (−974 B, −365 tok/request), with 117 B of that budget re-spent on trigger coverage where it was demonstrably missing.**

---

## 2. Trigger reliability, ranked

Ranked by P(fires | should fire). The question is silent non-firing, not over-firing — an over-firing skill costs one body injection; a silent non-firing skill costs the defect it was written to prevent.

| # | skill | reliability | why |
|---|---|---|---|
| 1 | **craft-context-file** | very high | The request contains the literal filename. Near-certain lexical match. Its risk is losing *selection* to review-prompt, not silence. |
| 2 | **craft-skill** | high | "skill", "SKILL.md", "slash command" are distinctive, low-collision tokens. |
| 3 | **git-workflow** | high | "Use before running git or gh" matches nearly every repo session. Effectively always-on-by-invocation. At 2,893 B that is a fine trade; it is the one skill where broad firing is correct. |
| 4 | **review-prompt** | high to fire, medium to be *chosen* | Same filename hooks as #1 plus review/critique/audit/lint. But it is the read-stance twin of all three craft-* skills, so it competes on every noun it owns. |
| 5 | **craft-prompt** | medium | "improve this prompt" is authoring by craft-prompt's own rule, but reads as review. Genuine 50/50 on a common phrasing. |
| 6 | **pr-review-method** | medium | Lexically strong, but it competes with the built-in `review` and `/code-review`, which the user invokes *directly* — and a direct slash-command invocation may never consult the skill listing at all. |
| 7 | **testing-ci** | medium-low | Its trigger is introspective: "when a suite passed suspiciously." The agent that would fire it is the agent that already noticed — which is the moment it least needs the reminder. Fires reliably only on an explicit user ask. |
| 8 | **prebid-adcp** | **low, with a documented miss** | Abstract-topic trigger against work that presents as ordinary Python. The inverted-idempotency-rule incident in its own body is a recorded instance of this skill failing to fire when it should have. The rewrite above is the fix. |

---

## 3. Overlap — every colliding pair

**Cluster A — the four authoring/review skills. This is a genuine four-way collision, not four pairs.**

| pair | shared trigger surface | current disambiguator | verdict |
|---|---|---|---|
| craft-context-file ↔ review-prompt | AGENTS.md, CLAUDE.md, GEMINI.md — **all three filenames in both descriptions** | stance: "Authors and prunes" vs "read-only, never edits", plus explicit cross-reference in both | **Worst pair in the set.** Adequate but load-bearing on a single clause. Both my rewrites make the stance word an unmissable standalone sentence. |
| craft-skill ↔ review-prompt | "skill", "SKILL.md" | craft-skill names review-prompt; review-prompt says "skills" but did **not** name craft-context-file back | Fixed by adding `craft-context-file` to review-prompt's anti-trigger. |
| craft-prompt ↔ review-prompt | "prompt", "system prompt", "agent instructions" | "improve or tune" vs "review, critique" — thin, because *improve* is what a user says when they want a critique | Real residual risk. Mitigation is craft-prompt's own Step-1 gate, not the description. |
| craft-prompt ↔ craft-context-file | "agent instructions" (craft-prompt) vs "repo instructions" (craft-context-file) | one word apart | Low real-world risk; the filenames dominate. Leave it. |

**Cluster B — collisions with built-in skills, which share the same msg[1] listing and were not in scope but matter:**

- **`review-prompt` ↔ built-in `review` ("Review a GitHub pull request") ↔ `pr-review-method`.** Three entries whose leading token is "review". Worse: the name `review-prompt` parses two ways — "review [a] prompt" (correct) or "[the] review prompt" (a prompt used for reviews). This is the one *naming* problem in the set. Renaming to `prompt-critique` or `critique-prompt` would eliminate it, at the cost of breaking `/review-prompt` muscle memory. Flagging, not recommending.
- **`craft-context-file` ↔ built-in `init` ("Initialize a new CLAUDE.md file")** — direct functional overlap on the same filename. `init` will win on the word "init" and `craft-context-file` on everything else. Acceptable; worth knowing they both exist.
- **`testing-ci` ↔ built-in `run`** — mild, on "does this work". Not actionable.

**Cluster C — the operational four (git / pr / testing / adcp): no overlap.** Their trigger surfaces are genuinely disjoint despite firing in the same *session*. This is the correctly-structured half of the set.

---

## 4. Is 8 the right number?

**8 is not the wrong count. It is the wrong *set*.** Judged by distinct trigger conditions:

**No merges.** The obvious candidate — collapsing the four authoring skills — is wrong on the cost model. Their combined bodies are 34,999 B (~13,100 tok). Merging means paying all four bodies to get one, on every invocation. Four separate bodies at ~2,600–4,400 tok each is strictly cheaper, and their output contracts are genuinely different artifacts. The collision is confined to the description tier, where the fix is disjoint wording (§3), not consolidation.

**No splits.** `git-workflow` looks splittable into git-mechanics vs gh/PR-plumbing, but both halves fire at the same moment — you are in a repo doing repo things — so splitting buys a second permanent description tax and no trigger precision. Keep as one and grow the body.

**The real finding is the shape.** Four skills cover *authoring agent instructions*. Four cover *doing engineering work*. Zero cover the operational middle where the accumulated knowledge actually lives:

- 17 memories on agent dispatch → no skill
- 15 on local environment failures → no skill
- 12 on output and artifact style → no skill
- 10 on test *authoring* → explicitly out of scope of the only testing skill
- 13 on cross-file defect classes → partially in pr-review-method, and only reachable in review stance

That is ~67 memories of durable, cross-repo method with no path into any project but the one they were written in. The set should be **13–14**, not 8, and the additions are almost all in the operational tier.

---

## 5. What is missing — the six skills that should exist

Ranked by value. Each is grounded in specific stranded memories; counts are from the 241-file survey.

### 1. `agent-dispatch` — highest value in this list

```
Dispatching subagents safely — preflight disk and Docker before the fan-out, cap concurrency, isolate mutation-testing agents in a worktree, open every prompt with a mandatory Step 0 read list, and scrutinize what comes back. Use before spawning any agent or parallel fan-out, when a subagent report looks wrong, or when agents contend for a shared checkout, database, or disk.
```
379 B. **Absorbs 2,017 B from CLAUDE.md** (the single largest movable block) **plus 17 stranded memories**: `feedback_fanout_preflight_disk_and_docker`, `feedback_no_mutation_agents_on_shared_worktree`, `feedback_isolate_mutation_testing_reviewers_in_worktrees`, `reference_agent_worktree_isolation_may_provision_main`, `feedback_subagents_need_explicit_read`, `feedback_subagent_model_inherit`, `feedback_detecting_subagent_overconfidence`, `feedback_subagent_mechanism_is_a_claim`, `feedback_two_phase_subagent_audit`, `feedback_reverify_pr_head_before_and_after_fanout`, `reference_background_agent_report_retrieval`, `feedback-agent-token-budget`, `feedback_use_full_review_skill_not_handrolled_fanout`, `feedback_agent_team_execution_model`, `feedback_no_agent_fanout_by_default`, `feedback_detecting_subagent_overconfidence`, `feedback_snowball_to_avalanche`. Target body: 6–8 KB.

**Critical constraint on this one:** the *default* — "single pass, zero spawned agents, fan out only on explicit instruction" — **must stay in CLAUDE.md**. The agent about to fan out unnecessarily is precisely the agent that doesn't think it needs a dispatch skill. Keep the trigger sentence always-on; move the mechanics to the body. That split rule governs every recommendation in §6 below.

### 2. `local-env`

```
Local dev-environment failures that masquerade as code bugs — a stale Docker Desktop singleton after a crash, port desync against a running container, a persistent schema hiding a fresh-DB failure, concurrent containers producing spurious setup errors, corrupted or drifted virtualenvs and lockfiles. Use when a command fails for no reason the diff explains, a container or DB will not come up, or a test passes locally and nowhere else.
```
439 B. **15 memories, zero current coverage**: `docker_desktop_stale_singleton_after_crash`, `reference_agentdb_port_mismatch`, `no_concurrent_agentdb_during_full_integration_run`, `agentdb_persistent_schema_masks_fresh_db_failures`, `uv_venv_corruption_reinstall`, `uv_frozen_for_commit_drift`, `reference_tox_commands_no_shell_substitution`, `prek_pre_commit_replacement_bug`, `reference_lazy_imports_load_bearing`, `crash_forensics_check_user_scope_first`, `reference_run_all_tests_in_network_artifacts`, `run_all_tests_congratulations_masks_failures`, `reference_docker_image_cve_review_gotchas`. Several are salesagent-flavored, but the *classes* are universal: stale container singletons, port desync, persistent state masking a clean-slate failure, lockfile drift. Also picks up the `df -h /System/Volumes/Data` gotcha and the Docker Desktop singleton recovery from CLAUDE.md, and CLAUDE.md's "Docker novice — explain what the step does" instruction, which is situational and currently always-on.

### 3. `writing-for-github`

```
House style for anything bound for GitHub or a human — PR bodies, issue drafts, review write-ups, code comments, docs. Technical fact only, no provenance or internal quality labels, fenced blocks for anything to be pasted, location + fact + fix per line. Use when drafting a PR description, issue, review comment, commit message, or report the user will paste or publish.
```
373 B. **12 memories across 4 silos, and two of them are duplicated across silos** — `feedback_no_blockquote_for_pasteable_text` and `feedback_no_internal_dialogue_in_public_artifacts` each exist in both salesagent and prebid-agent-skills. Independent re-teaching in two projects is the strongest available evidence that a rule is universal and that the silo is the wrong tier. Plus `feedback_docs_voice_factual_dense`, `feedback_github_issue_drafting`, `feedback_issue_draft_neutrality`, `feedback_no_issue_refs_in_comments`, `feedback_no_pointless_comments`, `feedback_final_reports_must_be_contributor_actionable`, `feedback_pr_review_writeup_style`, `feedback_no_claude_coauthor_trailer`, `feedback-mirror-prose-not-enforcement`.

### 4. `test-authoring`

```
Writing tests that can actually fail — driving the real entry point instead of a mock, negative scenarios that go vacuous on empty input, BDD step and fixture pitfalls, and escalating a repeated lesson into a structural guard. Use when adding or strengthening a test, building a test harness or fixture, or turning an invariant into an enforced check. For judging an existing test's strength, use testing-ci.
```
410 B. Fills the gap `testing-ci` declares at its own line 8. **10 memories**: `reference_bdd_harness_patterns`, `reference_bdd_harness_pitfalls`, `reference_bdd_negative_scenario_vacuous_on_empty`, `reference_bdd_inline_steps_escape_guards`, `feedback_mock_only_tests_dont_prove_wiring`, `feedback_a2a_wire_tests_must_drive_on_message_send`, `synthetic-tests-self-confirm`, `feedback_fitness_functions_pattern`, `feedback_escalate_recurring_lessons_to_guards`, `feedback_always_improve_testing`. Note the explicit cross-reference in the last sentence — this pair needs it, since "test" is in both descriptions.

### 5. `refactor-safety`

```
Defect classes that a diff-local view cannot see — a duplicate twin in an untouched file, an SSOT consolidation that leaves the old paths live, a new abstraction with no production caller, deleting one of N writes without enumerating readers, a refactor reviving dead code. Use when refactoring, extracting a helper, deduplicating, deleting code, or changing a wire or payload shape.
```
385 B. **13 memories.** Partial overlap with pr-review-method's "Scope and refactors" section — but the trigger is genuinely distinct and that distinction is the whole point: these defects must be caught while *authoring*, and pr-review-method fires only in review stance. Sources: `feedback_semantic_ssot_defect_class`, `feedback_single_source_of_truth_requires_deleting_duplicates`, `feedback_duplicate_deletion_needs_reader_enumeration`, `feedback_exception_class_partition_needs_condition_mapping`, `feedback_new_abstraction_needs_adoption_completeness`, `feedback_substrate_prs_need_production_callers`, `feedback_diff_scope_hides_duplicate_twin`, `feedback_refactor_makes_dead_patches_live`, `feedback_check_normalizer_before_input_surface_regression`, `feedback_advisory_on_success_error_pattern`, `feedback_valueerror_boundary_vs_internal`, `feedback_defect_recurrence_is_the_root_cause`, `feedback_root_cause_first`.

*Alternative worth weighing:* fold this into pr-review-method's body instead. Cheaper (no new description tax, no overlap hazard) but loses the authoring-time trigger, which is where the defects are actually introduced. I recommend the separate skill; the cross-reference in both anti-trigger clauses handles the overlap.

### 6. `claude-code-cost`

```
Measuring what a Claude Code session actually cost — deduping JSONL records by requestId, finding subagent transcripts one level down, taking max output_tokens across split records, and the cache-tier multipliers. Use when asked how much a session, agent, or fan-out cost, when analyzing token usage or transcripts, or before any claim about harness cost.
```
357 B. **Absorbs 1,226 B from CLAUDE.md verbatim** and routes to the existing 28-report audit at `/Users/quantum/.claude/harness-audit-20260801/`. This section is 100% situational — it is dead weight in every session that isn't a cost audit, which is nearly all of them. Body should also carry the §6d facts the CLAUDE.md summary omits: msg[1] is a per-request `role:"system"` message invisible to transcripts (~7,926 tok, a 3.7× undercount); invoking a skill injects the whole SKILL.md; reading one file in a directory pulls that directory's CLAUDE.md for the rest of the session; a compaction costs less than one normal turn.

### Not recommended as skills

- **`plan-approval` / work staging.** `feedback_no_code_in_planning_stage`, `feedback_plan_approval_gate`, `feedback-explicit-go-before-building`, `feedback-dont-be-eager-to-advance` and five more cluster cleanly — but they are pre-action gates. They must fire *before* the first edit, and a skill loads only after the model decides it's relevant. Correctly always-on; leave in CLAUDE.md.
- **`security-patterns`.** Only 4–5 memories (`reference_httpx_ssrf_ip_pinning`, `feedback_a2a_harness_real_auth_chain`, `reference_mcp_structured_content_bypasses_model_dump`, `reference_docker_image_cve_review_gotchas`), and a built-in `/security-review` already occupies the trigger surface. Too thin to earn a permanent description tax. Fold the pieces into `refactor-safety` and `local-env`.
- **The ~28 `project-*` memories in agentic-prebid** (`project-two-seat-model`, `project-threat-model`, `project-aamp-play`, positioning and charter docs). Genuinely project-scoped strategy. Correctly siloed. Do not promote.

### On `prebid-adcp` being the one domain-scoped skill

**User-level is correct, and there is direct evidence for it.** The skill spans at least four repos (salesagent, adcp-tooling, agentic-prebid, agentic-advertising). The alternative — a `.claude/skills/` copy per repo — has already been tried and failed: `reference_verify_spec_skill_not_portable` records a project-level `verify-spec/SKILL.md` that hardcoded `/Users/konst/projects/adcp` (another machine's clones), pinned spec `3.0.0-beta.3` against a repo pinning `3.1.0-beta.3`, and mutated test files during review. The skill's own body was written against exactly this: "Some project skills hardcode a stale spec pin or a local clone path belonging to another machine; the authority order below supersedes those regardless."

414 B on every request in every project is the correct price for one canonical, non-drifting copy. The structural change I *would* make is the trigger fix in §1 — the placement is right, the trigger is what failed.

---

## 6. What in `~/.claude/CLAUDE.md` should be a skill

Total 10,368 B / ~3,883 tok. Measured by section:

| section | B | tok | verdict |
|---|---|---|---|
| preamble + skill table (1–15) | 739 | 277 | **Keep.** The routing table is what makes the skill tier discoverable. |
| Who I'm working with (17–27) | 643 | 241 | **Keep**, minus line 21 ("Docker novice…", 88 B) → `local-env`. |
| **Agent dispatch (29–69)** | **2,639** | **988** | **Split. Keep 29–39 (618 B); move 41–69 (2,017 B) → `agent-dispatch`.** |
| Permission boundaries (71–86) | 1,009 | 378 | **Keep entirely.** Pre-action gates; no skill can load in time. |
| Claims and evidence (88–102) | 978 | 366 | **Keep.** Core standing rule, governs every response. |
| Destructive operations (104–109) | 443 | 166 | **Keep.** Standing prohibition. |
| Output (111–126) | 992 | 372 | **Mostly keep.** Lines 113–116 (348 B, the GitHub provenance-stripping rule) → `writing-for-github`, replaced by a one-line always-on version — it's a leak gate and needs *some* always-on presence. |
| **Measuring Claude Code cost (128–146)** | **1,226** | **459** | **Move entirely → `claude-code-cost`.** Zero of it applies outside a cost audit. |
| Verification (148–164) | 1,001 | 375 | **Split.** The instrument rule (148–151) is universal — keep. Lines 152–156, the five enumerated observed instances (378 B), are illustrations → `claude-code-cost` body. |
| Memory (166–179) | 690 | 258 | **Keep.** The "universal facts go HERE not in a silo" routing rule is precisely what stops the 241-memory sprawl from recurring. |

**Movable: 3,969 B / ~1,487 tok — 38% of the file.**

The three biggest offenders are all situational depth that got written into the permanent tier because there was nowhere else to put it: the fan-out preflight commands (938 B — two shell commands you need only when about to dispatch), the entire cost-measurement section (1,226 B), and the five verification-failure instances (378 B — case studies, not rules).

**The general rule I'd apply, and would keep applying:** a rule whose job is to *stop* something that happens without deliberation stays always-on, because the skill tier can't fire before the deliberation it's waiting for. Everything that answers "how do I do this well, now that I've decided to do it" is skill-tier. Under that test, permission boundaries, destructive operations, and the dispatch *default* stay; every preflight command, recovery procedure, and worked example goes.

---

## 7. Bottom line

```
skills tier   4,916 B → 3,942 B  (8 rewritten)          −974 B
              3,942 B → 6,285 B  (+6 new)             +2,343 B
CLAUDE.md    10,368 B → 6,399 B                       −3,969 B
                                                      ─────────
NET always-on                                −2,600 B ≈ −974 tok/request
```

Roughly 2% of a typical always-on floor, on every request in every project, forever — while ~67 memories of durable method stop being reachable in exactly one directory each.

The savings are real but secondary. **The load-bearing change is that six categories of knowledge move from a tier where they don't travel into a tier where they do, and they do it in the free half of the budget.** Two rules in that set were independently re-taught in two different silos, which is what a knowledge routing failure looks like from the inside.

Three caveats on my own numbers. The +2,343 B for new skills is description text only; the `- <name>: ` listing framing adds roughly 110 B more. The 3,969 B of CLAUDE.md moves assumes the skill-table rows in the preamble absorb the routing at negligible cost — realistically add ~150 B back for six new table rows. And the body-expansion recommendations (git-workflow ~3×, prebid-adcp ~3–4×) are free only under the measured model where bodies inject on invocation; if `git-workflow` fires on nearly every session as its description invites, tripling its body is a real recurring cost of roughly +2,200 tok per firing session, and that one deserves a deliberate decision rather than the blanket "bodies are free."

**Files read:** all 8 at `/Users/quantum/.claude/skills/*/SKILL.md`, `/Users/quantum/.claude/CLAUDE.md`, `/Users/quantum/.claude/harness-audit-20260801/FINDINGS.md` (§6b lines 205–262, §6d lines 350–464), 241 memory files under `/Users/quantum/.claude/projects/*/memory/`, and three read in full: `/Users/quantum/.claude/projects/-Users-quantum-Documents-GitHub-prompt-harness/memory/installed-skills-are-frozen-snapshots.md`, `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/memory/feedback_generalize_memories_and_skills.md`, `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/memory/reference_verify_spec_skill_not_portable.md`.

**Not done:** read-only as instructed — no files edited. I did not exercise any rewritten description against a fresh session to confirm it still triggers; that check is the one thing this audit cannot do from inside the authoring session, and it's the correct next step before any of these land.