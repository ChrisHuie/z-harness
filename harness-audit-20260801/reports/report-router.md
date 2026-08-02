All 241 routed, verified complete (no unassigned, no phantom filenames). Here is the plan.

---

# Routing plan — 241 memory files

**Buckets:** `SKILL` **121** · `PROJECT` **66** · `DELETE` **48** · `CLAUDE.md` **6**

**What "destination" means:** for `SKILL` and `CLAUDE.md`, the content moves into the target and **the source file is removed from its silo**. That is what shrinks the silos from 241 files to **66**.

## The arithmetic this plan is built on

| line | measured | note |
|---|---|---|
| `~/.claude/CLAUDE.md` | 10,298 B = **3,857 tok**, every call, every project | matches the brief's 3,883 |
| salesagent `MEMORY.md` | 19,633 B = **7,353 tok** per dispatch | reproduces FINDINGS §6b's independently-derived 7,353 exactly — validates the 2.67 c/tok ratio and my method |
| agentic-prebid `MEMORY.md` | 14,219 B = **5,325 tok** per dispatch | **previously unattributed.** 37 lines averaging **384 chars each** — this is not an index, it is content |
| prebid-github-io `MEMORY.md` | 2,345 B = **878 tok** per dispatch | indexes **zero** memory files. Already marked STALE. Pure tax |
| project-plugins `MEMORY.md` | 2,842 B = **1,064 tok** per dispatch | indexes **zero** memory files. Pure tax |

---

# 1. Routing table

Silo keys: `SA`=salesagent · `AP`=agentic-prebid · `PAS`=prebid-agent-skills · `NOR`=norbert-skills · `RRA`=rereview-agent · `AA`=agentic-advertising · `PH`=prompt-harness · `ADT`=adcp-tooling · `CCS`=ComputedChaos-skills · `HP`=hermes-plan · `GAD`=github-activity-db · `HOME`=`~/.claude/projects/-Users-quantum/`

## → SKILL:pr-review-method (42) — *extend existing*

Shared reason: a rule that fires when reviewing a diff or handling reviewer feedback, true in any repo/language. Most are already reflected in the current 125-line skill; this makes the skill their canonical home.

`SA/` feedback_audit_checklist_systematic · feedback_complete_claim_requires_full_pattern_enumeration · feedback_confession_marker_grep_before_ready · feedback_defect_recurrence_is_the_root_cause · feedback_detector_surface_blindness · feedback_diff_scope_hides_duplicate_twin · feedback_duplicate_deletion_needs_reader_enumeration · feedback_evidence_is_not_a_disposition · feedback_exception_class_partition_needs_condition_mapping · feedback_findings_need_anchors_post_as_threads · feedback_grade_remedy_composition_not_checkboxes · feedback_infra_limitation_needs_cost_estimate · feedback_new_abstraction_needs_adoption_completeness · feedback_no_author_filter_on_first_audit_pass · feedback_no_cheap_wins_pings · feedback_no_optional_disposition · feedback_no_pr_count_reduction_framing · feedback_pattern_extraction · feedback_principled_scope_expansion · feedback_prior_round_finding_needs_remeasure · feedback_project_wide_pattern_understanding · feedback_ready_claim_requires_fresh_pr_audit · feedback_rereview_diff_against_current_main_not_mergebase · feedback_reverify_pr_head_before_and_after_fanout · feedback_review_consolidation_drops_findings · feedback_review_deliverable_against_issue_contract · feedback_review_tooling_prs_derive_invariant_and_probe_inputs · feedback_reviewer_first_not_steward · feedback_root_cause_first · feedback_semantic_ssot_defect_class · feedback_single_source_of_truth_requires_deleting_duplicates · feedback_substrate_prs_need_production_callers · feedback_verify_provenance_before_preexisting_claim · feedback_verify_reviewer_fixes_against_code · feedback_verify_worklist_items_real · pr_review_audit_workflow

Per-file differences:
- `SA/feedback_github_ci_review_blind_spots` — the three `.github/` blind spots (DRY ratchet skips it, heredoc gate logic untestable, trigger relocation) generalize past this repo's ratchet.
- `SA/reference_docker_image_cve_review_gotchas` — build-both-and-scan is the method for any container CVE PR; Trivy/buildx traps are tool-level.
- `SA/reference_github_code_quality_no_path_exclusion` — GitHub platform fact. **Carries an expiry**: "roadmapped later 2026" — mark it re-verify-before-citing.
- `SA/reference_github_inline_comment_anchoring` — the API constraint that forces the anchored-threads rule; belongs next to it.
- `AP/feedback-mirror-prose-not-enforcement` — reusing a hardened contract's vocabulary ≠ inheriting its mechanisms. Misfiled as project-strategy; it is a general design-review rule.
- `RRA/feedback-adversarial-review-user-adjudicates` — drafter+attacker passes, findings surfaced for Chris to adjudicate rather than silently accepted or dropped. Pairs with the existing "de-dup is not synthesis" rule.

## → SKILL:testing-ci (19) — *extend existing*

Shared reason: proving a test or a green signal is real. Repo-independent.

`SA/` feedback_always_improve_testing · feedback_ci_optimization_silent_noop · feedback_claimed_invariant_needs_failing_oracle · feedback_empirical_over_static_guard_assessment · feedback_flaky_test_single_green_run_is_luck · feedback_guard_matcher_completeness · feedback_mutation_oracle_selector_must_be_verified · feedback_oracle_decay_from_redundant_mechanism · feedback_personal_harness_gitignored_only · feedback_short_circuit_coverage_illusion · feedback_snowball_to_avalanche · feedback_structural_guards_pin_production_paths · feedback_verify_branch_runs_assert_head · feedback_wire_shape_change_systematic_sweep · run_all_tests_congratulations_masks_failures

- `SA/reference_bdd_negative_scenario_vacuous_on_empty` — phrased for BDD, but "set-intersection emptiness passes vacuously on an empty response" is a universal assertion defect.
- `SA/reference_guard_selftest_full_chain_over_leaf` — a guard's known-bad self-test must drive the real entry point, not a decomposed leaf.
- `SA/reference_release_jobs_invisible_to_pr_ci` — `if: release_created` jobs never run on `pull_request`; green CI is no evidence. Universal GH Actions.
- `ADT/synthetic-tests-self-confirm` — fixtures mirroring the parser's own assumptions are a self-referential oracle. **Prior pass had this as T1-UNIVERSAL with no home; this is the home.**

## → SKILL:git-workflow (13) — *extend existing*

Shared reason: a git/gh command that succeeds quietly and reports the wrong thing.

`SA/` backgrounded_commit_exit_code_masks_failure · feedback_atomic_breaking_changes · feedback_cleanup_chain_use_semicolon_not_ampersand · feedback_feature_branch_first · feedback_issue_vs_pr_number · feedback_merge_creates_duplication_sweep_ssot · feedback_no_alarm_mid_operation · feedback_verify_branch_currency_before_rebuild · gh_actions_dirty_merge_skips_pull_request_workflows · git_mv_then_add_old_path_aborts_commit · reference_git_grep_ere_no_word_boundary

- `SA/reference_release_please_pr_ci_mechanics` — `GITHUB_TOKEN`-authored PRs land `action_required` so required contexts never report. Universal GH mechanic, currently filed as repo-specific.
- `SA/reference_stacked_pr_ci_does_not_run` — base-branch-filtered workflows mean a stacked PR gets no heavy CI. Filenames are local; the mechanism is universal.

## → SKILL:agent-harness (14) — *NEW*

Shared reason: mechanics of the Claude Code harness itself — spawning agents, isolating them, retrieving their output, and how skills/hooks/memory actually load.

- `SA/feedback_fanout_preflight_disk_and_docker` — the `df /System/Volumes/Data` + `docker info` preflight. **Currently occupying CLAUDE.md lines 41–52.**
- `SA/docker_desktop_stale_singleton_after_crash` — the `Singleton{Cookie,Lock,Socket}` fix. **CLAUDE.md lines 51–52.**
- `SA/crash_forensics_check_user_scope_first` — enumerate the CWD project's sessions first; `meta.json`-without-jsonl = lost transcripts.
- `SA/feedback_isolate_mutation_testing_reviewers_in_worktrees` + `SA/feedback_no_mutation_agents_on_shared_worktree` — two views of one rule; merge on the way in.
- `SA/reference_agent_worktree_isolation_may_provision_main` — `isolation:"worktree"` may branch from main, not the launching HEAD.
- `SA/reference_background_agent_report_retrieval` — background agents idle instead of delivering; SendMessage, never Read the `.output` symlink.
- `SA/feedback_detecting_subagent_overconfidence` + `SA/feedback_subagent_mechanism_is_a_claim` — the falsification technique (find the case where Y is absent and X still happens) is method, not restatement.
- `SA/feedback_two_phase_subagent_audit` — second-pass audit agent after any code-modifying sweep.
- `AP/feedback-agent-token-budget` — the ~10M-token fan-out blowup and the pre-stated-ceiling rule.
- `NOR/feedback-timeout-is-not-an-answer` — **the prior pass filed this DUPLICATE-of-CLAUDE.md. It is not in CLAUDE.md; I grepped all 178 lines, zero matches for `AskUserQuestion`, `timeout`, or `Interaction`.** It is also the only record of why `~/.claude/hooks/question_timeout_guard.sh` exists (verified present, registered as a PostToolUse matcher in `settings.json`). Deleting it orphans a live hook.
- `PH/installed-skills-are-frozen-snapshots` — invoking a skill loads the `~/.claude/skills/` snapshot, not the repo tree. Fires whenever a skill is edited in a repo.
- `HOME/worktree-window-helpers` — `prw`/`iss`/`wt-ls` at `~/.oh-my-zsh/custom/worktree-windows.zsh`. Needed exactly when opening an isolated PR worktree.

## → SKILL:python-tooling-traps (10) — *NEW*

Shared reason: **the prior pass filed all of these T3-REPO. They are Python-ecosystem facts that travel to any Python project** — this is the largest single correction to the prior classification.

- `SA/reference_reload_captures_active_mock` — `importlib.reload` permanently binds an active mock.
- `SA/reference_tox_commands_no_shell_substitution` — tox 4 execs argv without a shell; `$(...)`/`<`/`|` pass as literals.
- `SA/uv_frozen_for_commit_drift` — `entry: uv run` hooks re-resolve `uv.lock` mid-commit; `UV_FROZEN=1`.
- `SA/uv_venv_corruption_reinstall` — `uv sync` trusts its own metadata; corruption needs `--reinstall`.
- `SA/feedback_refactor_makes_dead_patches_live` — moving a call across modules makes previously-dead `mock.patch` targets effective.
- `SA/feedback_dependency_widen_pr_frozen_lock_masks` — a constraint-widening PR tests the OLD version under a frozen lock.
- `SA/feedback_precommit_black_shifts_line_allowlists` — formatter-agnostic: any line-count change breaks line-keyed allowlists.
- `SA/reference_lazy_imports_load_bearing` — the *why* (test-patch strategy, cycles) is universal Python; drop the repo site list.
- `SA/reference_mcp_structured_content_bypasses_model_dump` — `pydantic_core.to_jsonable_python` honors `Field(exclude=True)` but bypasses method-level `model_dump()`. Travels to any fastmcp server.
- `SA/reference_httpx_ssrf_ip_pinning` — `sni_hostname` bypasses cert verification; pin via httpcore's `_network_backend`.

## → SKILL:authoring-artifacts (8) — *NEW*

Shared reason: fires when drafting something Chris will publish, paste, or hand to another person.

- `SA/feedback_author_artifacts_with_investigation_rigor` — artifacts others act on get bug-investigation rigor at HEAD.
- `SA/feedback_final_reports_must_be_contributor_actionable` — a final report is self-contained, never a `/tmp` path.
- `SA/feedback_pr_review_writeup_style` — pick the shape first; the two shapes are for different artifacts.
- `SA/feedback_no_blockquote_for_pasteable_text` — fenced block, never `> `.
- `SA/feedback_no_issue_refs_in_comments` · `SA/feedback_no_pointless_comments` — code comments are an authored artifact.
- `AA/feedback_issue_draft_neutrality` — group-facing artifacts present options with **no "Recommended" section**. Note: this is the *complement* of CLAUDE.md's "lead options with the better end state" (which governs options put to Chris). Recording both together prevents them reading as a contradiction.
- `RRA/feedback-patterns-not-people` — never characterize named individuals in design docs; describe roles.

## → SKILL:prebid-adcp (7) — *extend existing*

- `SA/reference_adcp_spec_grounding` · `SA/reference_adcp_sdk_spec_mapping` · `SA/reference_sdk_bump_delta_verification` · `SA/feedback_ground_protocol_work_in_spec_not_assumptions` · `SA/feedback_recovery_audit_coherence_blind_to_condition` — already reflected in the skill; this is their canonical home.
- `SA/feedback_primary_sources_over_press_coverage` — installed artifact > spec repo > source; press is a lead. Already the skill's "External claims" section.
- `AP/reference-aamp-maturity-mid2026` — AAMP ratified at the object layer, unspecified at the agent-wire layer; which repos are spec vs code-only. Protocol authority, travels.

## → SKILL:prebid-repos (8) — *NEW*

Shared reason: fires when working in or contributing to any `prebid/*` repository — identity constraints on output, cross-repo confusion, and upstream contribution norms.

- `AP/reference-salesagent-python-in-legacy` — **which clone is which repo.** The local `GitHub/salesagent` is a diverged StellarPOC fork with a TS top level; `prebid/salesagent` is top-level Python. Prevents a concrete cross-repo error in any session.
- `AP/project-scope3-interchange-posture` — Scope3/Interchange power map; motive internal-only, mechanisms public.
- `AP/project-non-commercial-identity` — Prebid never transacts for itself; governs what may be asserted in output under the Prebid name.
- `AP/user-chrishuie-role` — attribute governance/maintainership to "Prebid", not to Chris personally; he is not an officer.
- `AP/feedback-firsthand-intel-outranks-docs` — Chris is a firsthand primary source on AdCP/AAO/Scope3 dynamics; a public-docs pass must not silently demote an established premise.
- `AP/project-salesagent-wire-vs-engine-control` — conform at the wire, own the engine. Doctrine spanning salesagent + agentic-prebid.
- `PAS/reference_port_fidelity_vs_target_norms` — target-repo review norms beat literal source fidelity on a Java→Go port.
- `PAS/project_port_skills_hardening` — lean-conformance + ADR doctrine for adapter ports.

**Also absorbs the durable half of `project-plugins/MEMORY.md`** (see §3): `jsonutil.Marshal`/`Unmarshal` not `encoding/json`; no `omitempty` on required schema fields; `jsonutil.StringInt` for `["integer","string"]`; `EndpointTemplateParams` has 19 fields; use the API `pulls/N/files` endpoint, not `.diff` URLs.

## → CLAUDE.md (6) — 1 new line, 5 amendments

| file | how it lands |
|---|---|
| `PAS/feedback_no_claude_coauthor_trailer` | **NEW LINE.** The only one. |
| `AP/feedback-dont-reference-time` | *amend* the §Output ban list — append *time estimates, durations, timeframes*. |
| `AP/feedback-dont-be-eager-to-advance` + `RRA/feedback-pace-and-presentation` | *amend* §Output "Work in single verified steps" — append: end on the outcome; never tee up the next step. |
| `AP/user-plain-language-for-infra` | *amend* §Who — generalize "Docker novice" to "not deep-infra: plain English on backend/plumbing; dense on strategy, market, protocol." |
| `NOR/feedback-no-self-declared-convergence` | *amend* §Claims banned-words list — append *converged, complete, exhaustive, nothing left*. Exhaustion of my search is a fact about me, not the space. |

## → DELETE — superseded by CLAUDE.md (27)

Every operative sentence is already injected into every call in every project. What remains in the file is dated incident detail (PR numbers, session dates) that CLAUDE.md deliberately stripped — and per CLAUDE.md's own §Claims, memory files are claims that decay.

`SA/` feedback_truth_over_optimism *(§Claims ¶1, verbatim)* · feedback_verify_before_asserting *(§Claims ¶2)* · feedback_trace_flows_not_claims *(§Claims ¶2 — source of "memory files are claims")* · feedback_no_ready_claims *(§Claims banned-words)* · feedback_thoroughness_over_momentum *(§Claims "re-verify the premise / assumption stack two deep")* · feedback_thorough_review *(dup of the above)* · feedback_plan_approval_gate + feedback_no_code_in_planning_stage *(§Permission "Research-complete is not authorization")* · feedback_user_owns_git_push *(§Permission ¶1 incl. the delegation carve-out)* · feedback_github_issue_drafting *(§Permission "Create an issue")* · feedback_no_unsafe_autofix + feedback_verify_remedy_before_public_post *(§Destructive)* · feedback_no_internal_dialogue_in_public_artifacts *(§Output ¶1)* · feedback_docs_voice_factual_dense *(§Output ¶2)* · feedback_session_workflow_rules *(§Output ¶3)* · feedback_lean_toward_quality_not_smaller_option *(§Output ¶3)* · feedback_no_pr_specifics_in_memory + feedback_generalize_memories_and_skills *(§Memory ¶1)* · feedback_escalate_recurring_lessons_to_guards *(§Memory ¶3)* · feedback_agent_team_execution_model *(§Who)* · user_profile *(§Who, whole section)* · feedback_no_agent_fanout_by_default *(§Dispatch ¶1 — **and** `permissions.ask` already gates `Agent`/`Task`)* · feedback_subagent_model_inherit + feedback_subagents_need_explicit_read *(§Dispatch hygiene)*

`AP/feedback-explicit-go-before-building` *(§Permission approval gate)* · `AA/feedback_iterative_planning` *(same; its residual "expect 2–3 plan passes" should be four words appended to that CLAUDE.md line)*

## → DELETE — stale or duplicate (21)

Verified-stale (evidence recorded in the prior pass and spot-checked): `SA/ci_refactor_rollout_state` *(all 4 PRs merged, #1234 closed)* · `SA/feedback_a2a_harness_real_auth_chain` *(#1312 merged; pattern landed)* · `SA/precommit_mypy_adcp_pin` · `SA/prek_pre_commit_replacement_bug` *(`which prek` → not found)* · `SA/feedback_black_ruff_format_disagreement` *(resolved by #1370; the durable lesson survives in feedback_precommit_black_shifts_line_allowlists → python-tooling-traps)* · `CCS/pr1389-property-list-context` · `CCS/salesagent-worktree-layout` · `ADT/adcp-kernel-empirical-anchors` *(every anchor moved)* · `AA/feedback_opus_verification` *(contradicted by the no-fanout default)* · `AP/project-tech-stack-audit` *(both "pending" decisions landed)* · `PAS/feedback_subagent_model` *(reversed by the inherit rule)*

Duplicates: `NOR/feedback-budget-is-a-resource` · `NOR/norbert-skills-temporal-design` *(strict subset of temporal-backbone-design)* · `PAS/feedback_no_blockquote_for_pasteable_text` · `PAS/feedback_no_internal_dialogue_in_public_artifacts` · `PAS/feedback_no_pr_specifics_in_memory` · `PAS/feedback_push_policy` · `PAS/feedback_review_rigor` · `PAS/feedback_multi_phase_workflow` *(approval gate + branch-first covered; the `/compact` step is session-specific)*

Two more I am adding beyond the prior pass:
- `SA/project_backlog_triage_2026_07` — a 151-issue status snapshot. **Violates CLAUDE.md §Memory's own ban on status snapshots**; the artifact URL it cites is the durable record.
- `SA/project_sovereign_multiprotocol_rail` — cross-filed in the wrong silo; `AP/project-substrate-ownership-strategy` + `AP/project-order-of-record-pivot` carry it and live in the repo they describe.
- `SA/reference_verify_spec_skill_not_portable` — a warning that another dev's `verify-spec` skill hardcodes their clones and a stale pin. The `prebid-adcp` skill's **Precedence** section already handles exactly this class ("some project skills hardcode a stale spec pin or a local clone path belonging to another machine; the authority order supersedes those").

## → PROJECT (66: 51 indexed, 15 unindexed)

**salesagent — 30 indexed.** Genuinely bound to this repo's code, transports, CI, harness, or schema: `agentdb_persistent_schema_masks_fresh_db_failures` · `feedback_a2a_skill_handlers_must_raise` · `feedback_a2a_wire_tests_must_drive_on_message_send` · `feedback_advisory_on_success_error_pattern` · `feedback_changed_wire_field_dormant_grader_check` · `feedback_check_normalizer_before_input_surface_regression` · `feedback_fitness_functions_pattern` · `feedback_mock_only_tests_dont_prove_wiring` · `feedback_planning_doc_location` · `feedback_pr_base_current_main_push_origin` · `feedback_readiness_verdict_gate` · `feedback_run_e2e_locally_before_push` · `feedback_run_full_suite_before_every_push` · `feedback_uow_detached_after_exit` · `feedback_use_full_review_skill_not_handrolled_fanout` · `feedback_valueerror_boundary_vs_internal` · `harness_error_wire_per_transport_mechanics` · `no_concurrent_agentdb_during_full_integration_run` · `project_review_harness_share_repo` · `reference_agentdb_port_mismatch` · `reference_bdd_harness_patterns` · `reference_bdd_harness_pitfalls` · `reference_gam_creative_level_targeting_exists` · `reference_gam_language_targeting_silent_drop` · `reference_harness_freshness_mechanisms` · `reference_per_diff_review_detectors` · `reference_review_patterns` · `reference_ruff_f821_ignored` · `reference_run_all_tests_in_network_artifacts` · `wire_envelope_policy`

**salesagent — 3 unindexed** (file stays, index line does not): `flask_migration_critical_knowledge` + `flask_to_fastapi_migration_v2` (migration PAUSED — nobody reads these until it resumes) · `reference_bdd_inline_steps_escape_guards` (single-UC fact).

**agentic-prebid — 9 indexed:** `project-two-seat-model` · `project-order-of-record-pivot` · `project-configuration-first` · `project-neutral-primitives-charter` · `project-positioning-and-core-decisions` · `project-real-money-first` · `project-substrate-ownership-strategy` · `project-transport-and-comms` · `project-aamp-play`.
**agentic-prebid — 9 unindexed:** `project-agent-discovery-decapture` · `project-agent-trust-layer` · `project-authority-layer` · `project-human-surface` · `project-reference-agents` · `project-salesagent-lessons` · `project-technical-grading` · `project-threat-model` · `project-transition-as-trigger`. **Each of these says in its own text "repo is source of truth; this is a recall-pointer."** A recall-pointer to a doc does not earn a permanent per-dispatch tax when `docs/design/` is right there.

**Remaining silos:** `adcp-tooling` 2 indexed (`adcp-kernel-standalone-decoupled` — promote the doctrine paragraph, drop the 2026-06-21 worklog half; `adcp-kernel-tool-is-go`) · `agentic-advertising` 2 indexed · `norbert-skills` 2 indexed · `prompt-harness` 2 indexed + 1 unindexed (`prompt-harness-pr-review-method`) · `rereview-agent` 2 indexed · `github-activity-db` 1 indexed · `hermes-plan` 1 indexed · `prebid-agent-skills` 1 unindexed (`project_teal_pr_remediation` — largely landed) · `HOME` 1 unindexed (`cmux-shortcuts-cheatsheet`).

---

# 2. Proposed skill set

| skill | status | trigger text (goes in `description`) | files | est. body |
|---|---|---|---|---|
| `pr-review-method` | extend | reviewing a PR, handling reviewer feedback, judging whether feedback was addressed, writing findings | 42 | 125 → **~260 lines / 16 KB** |
| `testing-ci` | extend | proving a test would fail if behavior broke; a suite passed suspiciously; judging whether green means the check ran | 19 | 82 → **~150 lines / 9 KB** |
| `agent-harness` | **NEW** | before spawning any subagent or fan-out; when a harness behavior surprises you; when editing a skill, hook, or memory file | 14 | **~140 lines / 8 KB** |
| `git-workflow` | extend | running git/gh; a git result is ambiguous; a grep came back empty; before claiming repo state | 13 | 66 → **~110 lines / 6 KB** |
| `python-tooling-traps` | **NEW** | running pytest/tox/uv/pre-commit; reviewing a dependency-bump or lockfile PR; a Python import or mock behaves impossibly | 10 | **~90 lines / 5 KB** |
| `authoring-artifacts` | **NEW** | drafting anything Chris will publish, paste, or hand to someone — issue bodies, PR text, reports, docs, code comments | 8 | **~90 lines / 5 KB** |
| `prebid-repos` | **NEW** | working in or contributing to any `prebid/*` repo; anything asserted under the Prebid name | 8 | **~110 lines / 6.5 KB** |
| `prebid-adcp` | extend | implementing/reviewing AdCP behavior, error taxonomy, recovery semantics, SDK↔spec version | 7 | 55 → **~110 lines / 6 KB** |

**Total body ≈ 61 KB / ~23K tok — all free until invoked, and normally one skill loads.**

**The honest cost:** 4 new `description` fields ride in `msg[1]` on **every call in every project**. Held to ≤45 words each that is **~250 tok always-on, forever**. This is the only recurring price of the plan, and it is paid even in projects with zero memory. It buys 121 files that today travel nowhere.

I deliberately did **not** create: a `verification-discipline` skill (its rules have no invocation trigger — that is precisely why they belong in CLAUDE.md, where they already are), a `working-with-chris` skill (same reason), or a separate `prebid-server-adapters` skill (3 items — folded into `prebid-repos`).

---

# 3. Per-project `MEMORY.md`

Index-line discipline: **`- [Title](file.md) — hook`, hard cap 100 chars.** agentic-prebid currently averages 384.

| project | now | recommend | per-dispatch tokens |
|---|---|---|---|
| salesagent | 119 L / 19,633 B | **~33 lines** (30 index + headings) | 7,353 → **~1,300** (−82%) |
| agentic-prebid | 37 L / 14,219 B | **~11 lines** (9 index + headings) | 5,325 → **~400** (−92%) |
| prebid-github-io | 35 L / 2,345 B | **delete the file** — 0 memory files; already marked STALE | 878 → **0** |
| project-plugins | 40 L / 2,842 B | **delete the file**; extract the durable PBS-Go rules to `prebid-repos` first | 1,064 → **0** |
| github-activity-db | 31 L / 1,902 B | **1 line** | 712 → **~40** |
| prebid-agent-skills | 12 L / 1,853 B | **delete** (sole survivor is unindexed) | 694 → **0** |
| hermes-plan | 4 L / 1,388 B | **1 line** | 520 → **~40** |
| rereview-agent | 8 L / 1,154 B | **2 lines** | 432 → **~75** |
| agentic-advertising | 6 L / 1,005 B | **2 lines** | 376 → **~75** |
| norbert-skills | 8 L / 987 B | **2 lines** | 370 → **~75** |
| prompt-harness | 7 L / 964 B | **2 lines** | 361 → **~75** |
| adcp-tooling | 7 L / 807 B | **2 lines** | 302 → **~75** |
| ComputedChaos-skills | 5 L / 346 B | **delete dir** — both files DELETE | 130 → **0** |
| `-Users-quantum` (HOME) | 3 L / 267 B | **delete** (sole file unindexed) | 100 → **0** |
| agenticads-sim-plan | 4 L / 177 B | **delete** — 0 memory files | 66 → **0** |

**Six `MEMORY.md` files disappear entirely.** Two of them (prebid-github-io, project-plugins) index **zero** memory files today and are billed on every dispatch in those projects — that is 1,942 tok/dispatch of pure tax nobody had attributed.

---

# 4. CLAUDE.md: **1 new line**

### The one addition, and the case against it

`PAS/feedback_no_claude_coauthor_trailer` — *do not append the `Co-Authored-By: Claude` trailer.*

**Against it — the strongest version:** it is repo etiquette, not a universal truth. Its evidence comes from **one silo** and its stated rationale is narrow ("the user's own contributions to public/upstream OSS repos under their name") — so "universal" is my inference, not a measurement. Chris has 17 project silos and I verified the rule in one. Per-repo `CLAUDE.md` would be the precise home. And every line here is paid on every call in every project forever, which is the most expensive real estate that exists.

**Why it survives anyway:** the harness system prompt carries an always-on instruction to *add* that trailer. A skill body cannot beat an always-on instruction, because the skill will not be loaded at the moment a commit message is composed. Only an equally always-on line can. The failure is also asymmetric — a pushed trailer needs amend + force-push, and Chris owns pushes, so my mistake becomes his cleanup.

**The right end state is not a line at all.** By CLAUDE.md's own §Memory doctrine — *"Never promise to remember — build the gate"* — this is a `PreToolUse` hook on `git commit` that strips the trailer. Treat the line as the interim. **And confirm with Chris that it covers all repos, not only upstream contributions**, before writing it.

### Everything else I considered and rejected

- **`feedback-dont-reference-time`** — I initially wanted this as a second line. It is a style tic whose violation costs one correction, and §Output already bans a list of phrasings. Three words appended to that list, not a line.
- **`feedback-no-self-declared-convergence`** — sharp and genuinely absent. But it is the same family as the banned-words line already present. Four words appended, not a line.
- **`NOR/feedback-timeout-is-not-an-answer`** — looks like a strong candidate: universal, costly, and I verified it is in **no** always-on location. I still did not add it, because `~/.claude/hooks/question_timeout_guard.sh` is installed and registered in `settings.json` — **the gate already exists**, and restating a rule that a hook already enforces is exactly what CLAUDE.md tells me not to do. It routes to `agent-harness` as the record of why the hook is there.
- **All 27 "superseded" files** — nothing to add; the rules are already there.

### The larger CLAUDE.md move: evict ~60 lines

The additions are noise next to this. Two blocks are **trigger-bearing mechanics paying always-on rent**:

| block | lines | cost | replace with |
|---|---|---|---|
| §Agent dispatch (L29–69) | 41 | **980 tok/call** | ~5 lines: the default-single-pass posture, the money framing, and *"before any fan-out, load `agent-harness`."* `permissions.ask` already gates `Agent`/`Task`, so the decision point is already interrupted. |
| §Measuring Claude Code cost (L128–146) | 19 | **452 tok/call** | ~2 lines: the audit-dir pointer + the three traps that cause silent 3x/90% errors. |

**Net effect: −53 lines, ~−1,150 tok on every call in every project**, against ~+250 tok of new skill descriptions. Net **~−900 tok/call always-on**, plus ~−6,000/dispatch in salesagent and ~−4,900/dispatch in agentic-prebid.

---

# 5. Where I overrode the prior classification

1. **`NOR/feedback-timeout-is-not-an-answer` was marked DUPLICATE of "CLAUDE.md (Interaction section)". No such section exists** — zero matches for `AskUserQuestion`, `timeout`, or `Interaction` in all 178 lines. Deleting it would have orphaned a live hook.
2. **10 files marked T3-REPO are Python-ecosystem-universal** (tox argv, uv lock/venv, `importlib.reload`+mock, frozen-lock masking, `pydantic_core` serialization, httpx pinning). They were stranded by a project-centric frame.
3. **T1-UNIVERSAL ≠ CLAUDE.md.** The prior pass produced 115 T1s under a model where universal meant promote-to-always-on. Under the tier model, 121 go to skill bodies and 27 are already covered.
4. **Six AP files marked LEAVE-IN-PLACE actually travel** (which-repo-is-which, Scope3 posture, Prebid identity, attribution, firsthand-source, wire-vs-engine) — they are needed in *any* prebid repo, not just agentic-prebid.
5. **Three additional DELETEs** the prior pass kept: the 151-issue triage snapshot, the cross-filed sovereign-rail duplicate, and the verify-spec portability warning.

---

# 6. Preconditions and what I did not verify

- **`~/.claude` is not a git repository** (`git rev-parse` → fatal). 48 deletions are unrecoverable. **Tar the tree or `git init` before executing any DELETE** — one command, and it makes the whole DELETE bucket safe.
- I routed from a full read of every file's frontmatter + first 480 chars of body, plus the prior pass's verified stale/duplicate evidence. **I did not re-verify the prior pass's staleness evidence for each of the 11 stale files** — I spot-checked `prek` (confirmed absent) and the `AskUserQuestion` claim (confirmed wrong). The other nine rest on the prior pass's citations.
- Six PROJECT files carry known-stale sub-claims that should be corrected as they are re-indexed, not silently kept: `SA/feedback_uow_detached_after_exit` (site moved to `:334`, no longer uses the UoW) · `SA/feedback_run_full_suite_before_every_push` (`test.yml` no longer exists; ci.yml does run `tests/admin/`) · `SA/feedback_valueerror_boundary_vs_internal` (dangling `.claude/notes/` pointer; counts drifted 44→2, 82→61) · `AP/project-salesagent-lessons` (`_legacy/src/core/models.py` does not exist) · `AP/project-transport-and-comms` (its 2026-07-28 MCP RC date has passed unverified) · `AA/project_storyboard_run_methodology` (pinned to adcp 4.3; live pin is 6.6.0).
- I did not open the ~60 files whose full body exceeded my 480-char digest window; for those the routing rests on description + lead paragraph + the prior pass's `one_line`. The buckets most exposed are the salesagent `reference_*` catalogs, and all of those route to PROJECT, where a misroute is cheap.

Assignment file with the exact 241 mappings: `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/route.py` (running it re-validates coverage against the live tree).