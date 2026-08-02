# Memory Index — operating harness
Recall ≠ enforcement. READ the topic file first. Memory is point-in-time — verify against current code; drift-audit on infra merges. `a / b` = sibling memories on one line.
## Tier 0 — posture, every turn
- [truth_over_optimism](feedback_truth_over_optimism.md) — wrong = 100% fail; name optimism bias
- [root_cause_first](feedback_root_cause_first.md) — change→interactions→enforcement first
- [trace_flows_not_claims](feedback_trace_flows_not_claims.md) — comments/PR/memory = CLAIMS; trace the flow
- [thoroughness_over_momentum](feedback_thoroughness_over_momentum.md) — assumption-stack ≥2 = wrong path
- [verify_before_asserting](feedback_verify_before_asserting.md) — no claim without file:line verified NOW
- [no_ready_claims](feedback_no_ready_claims.md) — never "ready/clean"; report raw state
- [session_workflow_rules](feedback_session_workflow_rules.md) — small atomic actions; honest closes
- [no_agent_fanout_by_default](feedback_no_agent_fanout_by_default.md) — 0 agents default; swarm on "go wide"
- [primary_sources_over_press](feedback_primary_sources_over_press_coverage.md) — external systems: introspect the INSTALLED artifact + spec repo; press/vendor blogs are leads, never evidence; resources available → depth is the default
- [escalate_to_guards](feedback_escalate_recurring_lessons_to_guards.md) — violated ≥2× → guard, not more memory
## User & working agreements
- [user_profile](user_profile.md) — Chris @chrishuie; solo + agent team; owns remote ops
- [agent_team_execution_model](feedback_agent_team_execution_model.md) — agent-workflow equivalents, not human roles
- [user_owns_git_push](feedback_user_owns_git_push.md) — no remote ops unprompted; confirm once, report URL
- [verify_remedy_first](feedback_verify_remedy_before_public_post.md) — verify empirically; destructive fix = red flag
- [lean_toward_quality](feedback_lean_toward_quality_not_smaller_option.md) — lead with larger better-end-state
- [no_code_in_planning](feedback_no_code_in_planning_stage.md) / [planning_doc_location](feedback_planning_doc_location.md) — planning = md only; → `.claude/notes/`
- [plan_approval_gate](feedback_plan_approval_gate.md) — present plan + decisions, wait
- [harness_gitignored_only](feedback_personal_harness_gitignored_only.md) — gitignored; never others' CI
- [github_issue_drafting](feedback_github_issue_drafting.md) — issue = chat draft; scope gap+contract
- [no_pointless_comments](feedback_no_pointless_comments.md) / [no_issue_refs_in_comments](feedback_no_issue_refs_in_comments.md) — no explanatory comments; no issue# in comments
- [no_internal_dialogue_public](feedback_no_internal_dialogue_in_public_artifacts.md) / [no_blockquote_pasteable](feedback_no_blockquote_for_pasteable_text.md) — strict-technical; fenced not `>`
- [reports_actionable](feedback_final_reports_must_be_contributor_actionable.md) — location/problem/why/fix/verify
- [evidence_is_not_a_disposition](feedback_evidence_is_not_a_disposition.md) / [no_optional_disposition](feedback_no_optional_disposition.md) — "nothing tests this" is its OWN row; ban "optional", severity≠disposition
- [pr_review_writeup_style](feedback_pr_review_writeup_style.md) — PICK SHAPE FIRST; comment IN THE RESPONSE fenced; Ran/Not-run footer
- [docs_voice_factual_dense](feedback_docs_voice_factual_dense.md) / [no_pr_count_framing](feedback_no_pr_count_reduction_framing.md) / [no_cheap_wins_pings](feedback_no_cheap_wins_pings.md) — factual, no marketing; lead with what a merge UNBLOCKS
- [no_pr_specifics_in_memory](feedback_no_pr_specifics_in_memory.md) / [generalize_memories](feedback_generalize_memories_and_skills.md) — cross-session patterns only; name the pattern, not the individual
## Verification & audit discipline
- [thorough_review](feedback_thorough_review.md) / [use_full_review_skill](feedback_use_full_review_skill_not_handrolled_fanout.md) — multiple subagent rounds; PR review = the full-review SKILL
- [review_tooling_prs_probe_inputs](feedback_review_tooling_prs_derive_invariant_and_probe_inputs.md) — tooling PRs: cardinal invariant + adversarial inputs; run end-to-end
- [consolidation_drops_findings](feedback_review_consolidation_drops_findings.md) — FINDS then DROPS; ledger + SSOT-synthesis
- [findings_need_anchors](feedback_findings_need_anchors_post_as_threads.md) / [gh_inline_comment_anchoring](reference_github_inline_comment_anchoring.md) — post as THREADS, never reuse an ID; anchors must be IN a diff hunk, a REFUSED anchor = scope signal
- [detector_surface_blindness](feedback_detector_surface_blindness.md) — CLEAN over the WRONG surface reads as all-clear; ask "which surface?"
- [subagent_overconfidence](feedback_detecting_subagent_overconfidence.md) / [complete_claim_enumeration](feedback_complete_claim_requires_full_pattern_enumeration.md) — confident-wrong; verify "not found"; every pattern × every PR
- [audit_checklist_systematic](feedback_audit_checklist_systematic.md) / [ready_claim_fresh_pr_audit](feedback_ready_claim_requires_fresh_pr_audit.md) — 8-dimension; readiness never inherited
- [grade_remedy_composition](feedback_grade_remedy_composition_not_checkboxes.md) / [readiness_verdict_gate](feedback_readiness_verdict_gate.md) — grade the COMPOSITION; charter §4c, FRESH pull first
- [pr_review_audit_workflow](pr_review_audit_workflow.md) / [no_author_filter_first_pass](feedback_no_author_filter_on_first_audit_pass.md) — 3 endpoints + diff before "addressed"; inventory ALL commenters
- [pattern_extraction](feedback_pattern_extraction.md) / [semantic_ssot_defect_class](feedback_semantic_ssot_defect_class.md) — sweep the pattern, guard is the deliverable; one concept in 2 places is guard-invisible
- [recurrence_is_root_cause](feedback_defect_recurrence_is_the_root_cause.md) / [abstraction_adoption_completeness](feedback_new_abstraction_needs_adoption_completeness.md) — COUNT copies BEFORE the fix; N adopted/M eligible, kept the WEAKER behaviour?
- [merge_creates_duplication](feedback_merge_creates_duplication_sweep_ssot.md) — main-merge/REBASE can CREATE duplication; count per revision
- [duplicate_deletion_needs_readers](feedback_duplicate_deletion_needs_reader_enumeration.md) / [diff_scope_hides_twin](feedback_diff_scope_hides_duplicate_twin.md) — enumerate readers first; the twin may sit OUTSIDE the diff
- [rereview_diff_vs_current_main](feedback_rereview_diff_against_current_main_not_mergebase.md) / [per_diff_review_detectors](reference_per_diff_review_detectors.md) — stale PR: 2-dot vs current main; which detector, which owner
- [github_ci_review_blind_spots](feedback_github_ci_review_blind_spots.md) / [confession_marker_grep](feedback_confession_marker_grep_before_ready.md) — .github/ ratchet-blind; grep our own confessions
- [invariant_needs_failing_oracle](feedback_claimed_invariant_needs_failing_oracle.md) — prose claims need RED-when-broken mechanism
- [mutation_selector_verified](feedback_mutation_oracle_selector_must_be_verified.md) — "reddens nothing" is a claim about your `-k`; baseline-vs-mutated counts, or drop the selector
- [check_normalizer_first](feedback_check_normalizer_before_input_surface_regression.md) — before "the handler drops field X", trace the request normalizer upstream of EVERY handler
- [short_circuit_coverage_illusion](feedback_short_circuit_coverage_illusion.md) / [oracle_decay](feedback_oracle_decay_from_redundant_mechanism.md) — `A or B` operand dead to the WHOLE suite; co-located mechanism neuters an oracle
- [ci_optimization_silent_noop](feedback_ci_optimization_silent_noop.md) / [project_wide_patterns](feedback_project_wide_pattern_understanding.md) — verify the opt ENGAGED; patterns project-wide
- [verify_worklist_items_real](feedback_verify_worklist_items_real.md) / [provenance_before_preexisting](feedback_verify_provenance_before_preexisting_claim.md) — extrapolated siblings are hypotheses; needs pickaxe + blame
- **Inherited-claim family** — [verify_reviewer_fixes](feedback_verify_reviewer_fixes_against_code.md) (incl. colleagues') / [prior_round_finding_needs_remeasure](feedback_prior_round_finding_needs_remeasure.md) (OUR round-N counts + mechanisms) / [subagent_mechanism_is_a_claim](feedback_subagent_mechanism_is_a_claim.md) (symptom=evidence, "because Y"=hypothesis)
- [empirical_over_static_guards](feedback_empirical_over_static_guard_assessment.md) — verdicts from RUNNING
- [assert_head_before_runs](feedback_verify_branch_runs_assert_head.md) / [reverify_pr_head_around_fanout](feedback_reverify_pr_head_before_and_after_fanout.md) / [branch_currency_first](feedback_verify_branch_currency_before_rebuild.md) — HEAD==SHA + clean; re-check headRefOid; divergence vs origin/main
- [no_alarm_mid_operation](feedback_no_alarm_mid_operation.md) / [crash_forensics_user_scope](crash_forensics_check_user_scope_first.md) — never flag "lost" mid git/hook op; enumerate CWD sessions
- [artifact_rigor](feedback_author_artifacts_with_investigation_rigor.md) — authoring for others needs tracing rigor
- [reviewer_first_not_steward](feedback_reviewer_first_not_steward.md) / [deliverable_vs_issue_contract](feedback_review_deliverable_against_issue_contract.md) — REVIEW severity-rated; grade fix vs issue contract
## Subagent practice
- [subagent_model_inherit](feedback_subagent_model_inherit.md) — never pin a model; inherit session
- [subagents_need_explicit_read](feedback_subagents_need_explicit_read.md) / [two_phase_subagent_audit](feedback_two_phase_subagent_audit.md) — "Step 0 MANDATORY: Read" abs paths; code-modifying sweeps get Phase-2
- [isolate_mutation_reviewers](feedback_isolate_mutation_testing_reviewers_in_worktrees.md) / [no_mutation_on_shared_tree](feedback_no_mutation_agents_on_shared_worktree.md) — mutation → worktrees; COMMIT first
- [bg_agent_report_retrieval](reference_background_agent_report_retrieval.md) / [worktree_may_provision_main](reference_agent_worktree_isolation_may_provision_main.md) — SendMessage, never Read .output; may branch from main, verify+detach SHA
## Scope & change discipline
- [principled_scope_expansion](feedback_principled_scope_expansion.md) — iff more consistent end state AND principal intact
- [infra_limit_needs_cost](feedback_infra_limitation_needs_cost_estimate.md) — "can't host it" needs a prototype/line cost
- [atomic_breaking_changes](feedback_atomic_breaking_changes.md) / [wire_shape_change_sweep](feedback_wire_shape_change_systematic_sweep.md) — land atomically w/ fixtures/callers; schema→tests→grep old forms→run
- [ssot_deletes_duplicates](feedback_single_source_of_truth_requires_deleting_duplicates.md) / [substrate_prs_need_callers](feedback_substrate_prs_need_production_callers.md) — delete duplicates same commit; new helper needs ≥1 production caller
- [always_improve_testing](feedback_always_improve_testing.md) — resurrect dead/skipped; never delete to hide a gap
- [no_unsafe_autofix](feedback_no_unsafe_autofix.md) / [feature_branch_first](feedback_feature_branch_first.md) — never `--unsafe-fixes` mid-migration; cut `feature/<slug> --no-track` FIRST
- [pr_base_current_main](feedback_pr_base_current_main_push_origin.md) / [issue_vs_pr_number](feedback_issue_vs_pr_number.md) — rebase onto CURRENT main; issue# ≠ PR#
## Test execution & infra truths
- [full_suite_before_push](feedback_run_full_suite_before_every_push.md) — `make quality`=unit-only; gate is `./run_all_tests.sh ci`
- [reload_captures_active_mock](reference_reload_captures_active_mock.md) — **never mix tests/unit + tests/integration in ONE pytest process**; `importlib.reload` under a patch bakes the mock in permanently; negative tests then pass VACUOUSLY
- [snowball_to_avalanche](feedback_snowball_to_avalanche.md) / [run_e2e_locally](feedback_run_e2e_locally_before_push.md) — after a CI surprise: full integration+e2e locally
- [congratulations_masks_failures](run_all_tests_congratulations_masks_failures.md) — per-suite JSON authoritative, never tail/exit
- [fanout_preflight_disk_docker](feedback_fanout_preflight_disk_and_docker.md) — disk + Docker UP BEFORE dispatch; full disk masquerades; never cycle Docker mid-fan-out
- [in_network_artifacts](reference_run_all_tests_in_network_artifacts.md) / [flaky_single_green_is_luck](feedback_flaky_test_single_green_run_is_luck.md) — dockerignored dirs → bdd fail; one green on timing = luck, run N×
- [agentdb_masks_fresh_db](agentdb_persistent_schema_masks_fresh_db_failures.md) / [stacked_pr_ci_does_not_run](reference_stacked_pr_ci_does_not_run.md) — agent-db pass ≠ fresh-CI; stacked PR = local Docker only
- [dep_widen_frozen_lock_masks](feedback_dependency_widen_pr_frozen_lock_masks.md) — green CI tested the OLD version
- [agentdb_port_mismatch](reference_agentdb_port_mismatch.md) / [no_concurrent_agentdb](no_concurrent_agentdb_during_full_integration_run.md) — "connection refused" = infra; serial re-run
- [docker_cve_review_gotchas](reference_docker_image_cve_review_gotchas.md) / [uv_venv_corruption](uv_venv_corruption_reinstall.md) — fs≠rootfs, arch-subdir; branch-switch → `uv sync --reinstall`
- [tox_no_shell_substitution](reference_tox_commands_no_shell_substitution.md) / [docker_desktop_stale_singleton](docker_desktop_stale_singleton_after_crash.md) — tox4 execs argv, `$(...)` literal; rm stale `Singleton*`
- [release_jobs_invisible_to_pr_ci](reference_release_jobs_invisible_to_pr_ci.md) / [release_please_ci_mechanics](reference_release_please_pr_ci_mechanics.md) — release_created jobs never in PR CI
## Git & pre-commit mechanics
- [uv_frozen_for_commit_drift](uv_frozen_for_commit_drift.md) — hooks re-resolve uv.lock; `UV_FROZEN=1 git commit`
- [format_shifts_line_allowlists](feedback_precommit_black_shifts_line_allowlists.md) / [backgrounded_commit_masks](backgrounded_commit_exit_code_masks_failure.md) — line shifts break line-keyed allowlists; verify HEAD advanced + clean
- [cleanup_chain_semicolon](feedback_cleanup_chain_use_semicolon_not_ampersand.md) / [git_mv_then_add_aborts](git_mv_then_add_old_path_aborts_commit.md) — `;` not `&&` after a fallible cmd; `git diff --cached --stat` first
- [dirty_merge_skips_workflows](gh_actions_dirty_merge_skips_pull_request_workflows.md) / [prek_replacement_bug](prek_pre_commit_replacement_bug.md) — DIRTY skips `pull_request` workflows; prek ignores `rev:` pins
- [ruff_f821_ignored](reference_ruff_f821_ignored.md) / [git_grep_ere_no_word_boundary](reference_git_grep_ere_no_word_boundary.md) — ruff IGNORES F821; `-E` ignores `\b`, use `-P`
- RESOLVED-historical (were unindexed; both conditions gone, verified — `black`/`additional_dependencies` survive only in explanatory comments): [black_ruff_format_disagreement](feedback_black_ruff_format_disagreement.md) / [precommit_mypy_adcp_pin](precommit_mypy_adcp_pin.md) — durable lesson in the latter: an ISOLATED-env hook with stub-providing deps must pin exactly to the runtime version
## Architecture & code patterns
- [review_patterns](reference_review_patterns.md) — P1-P42 catalog of repeatedly-flagged patterns
- [gam_creative_targeting](reference_gam_creative_level_targeting_exists.md) / [gam_language_silent_drop](reference_gam_language_targeting_silent_drop.md) — creative-level targeting IS built; language dropped
- [a2a_handlers_must_raise](feedback_a2a_skill_handlers_must_raise.md) / [a2a_wire_on_message_send](feedback_a2a_wire_tests_must_drive_on_message_send.md) / [a2a_real_auth_chain](feedback_a2a_harness_real_auth_chain.md) — `raise AdCPError` never dicts; drive `on_message_send`; real token→DB→identity
- [mock_only_no_wiring_proof](feedback_mock_only_tests_dont_prove_wiring.md) / [error_wire_per_transport](harness_error_wire_per_transport_mechanics.md) — ≥1 wire test per transport per error path; real wire only for REST
- [wire_envelope_policy](wire_envelope_policy.md) / [mcp_bypasses_model_dump](reference_mcp_structured_content_bypasses_model_dump.md) — `assert_envelope_shape(wire_error_envelope, code, recovery=)`; MCP honors `exclude=True`, BYPASSES `model_dump()`
- [advisory_on_success](feedback_advisory_on_success_error_pattern.md) / [valueerror_boundary_vs_internal](feedback_valueerror_boundary_vs_internal.md) — advisory Error(code=) in SUCCESS legit; boundary→AdCPError, internal→ValueError
- [uow_detached_after_exit](feedback_uow_detached_after_exit.md) / [dead_patches_go_live](feedback_refactor_makes_dead_patches_live.md) — ORM detaches after `with`; extraction makes dead mock.patch LIVE
- [lazy_imports_load_bearing](reference_lazy_imports_load_bearing.md) / [httpx_ssrf_ip_pinning](reference_httpx_ssrf_ip_pinning.md) — mostly load-bearing, but VERIFY the stated reason; `sni_hostname` BYPASSES cert verify
- [guard_matcher_completeness](feedback_guard_matcher_completeness.md) / [guard_selftest_full_chain](reference_guard_selftest_full_chain_over_leaf.md) — only modeled forms; self-test the REAL entry point + a negative
- [guards_pin_production_paths](feedback_structural_guards_pin_production_paths.md) / [fitness_functions_pattern](feedback_fitness_functions_pattern.md) — allowlists pin production-called fns; zizmor/pinact/Scorecard
## AdCP spec grounding
- [adcp_spec_grounding](reference_adcp_spec_grounding.md) — the pinned spec's PROSE, never SDK codes/types
- [exception_class_needs_condition_map](feedback_exception_class_partition_needs_condition_mapping.md) / [recovery_audit_coherence_blind](feedback_recovery_audit_coherence_blind_to_condition.md) — map CONDITION→class; COHERENCE only, CLEAN ≠ correct
- [harness_freshness](reference_harness_freshness_mechanisms.md) / [ground_protocol_work_in_spec](feedback_ground_protocol_work_in_spec_not_assumptions.md) — the harness ITSELF rots; cite section+version BEFORE implementing
- [sdk_bump_delta_verification](reference_sdk_bump_delta_verification.md) / [adcp_sdk_spec_mapping](reference_adcp_sdk_spec_mapping.md) — introspect BOTH versions and diff; re-check pyproject pin
- [verify_spec_not_portable](reference_verify_spec_skill_not_portable.md) — hardcodes stale clones; introspect installed models
## BDD & harness
- [bdd_harness_patterns](reference_bdd_harness_patterns.md) / [bdd_harness_pitfalls](reference_bdd_harness_pitfalls.md) — 24 patterns + 8 pitfalls
- [bdd_negative_vacuous_on_empty](reference_bdd_negative_scenario_vacuous_on_empty.md) / [bdd_inline_steps_escape_guards](reference_bdd_inline_steps_escape_guards.md) — set-emptiness passes vacuously; inline steps invisible to guards
- [changed_wire_field_dormant_grader_check](feedback_changed_wire_field_dormant_grader_check.md) — map field→grading scenarios (even untouched) + check harnessed
## Active project state
- [review_harness_share_repo](project_review_harness_share_repo.md) — PUBLISHED ChrisHuie/salesagent-review-harness; refresh pipeline in file
- [sovereign_multiprotocol_rail](project_sovereign_multiprotocol_rail.md) — AdCP+AAMP+native rail; READ spec first
- [backlog_triage_2026_07](project_backlog_triage_2026_07.md) / [ci_refactor_rollout_state](ci_refactor_rollout_state.md) — 151-issue cluster plan (2026-07-03); CI-refactor sub-PRs — BOTH need re-verify
- [flask_to_fastapi_migration_v2](flask_to_fastapi_migration_v2.md) / [flask_migration_critical_knowledge](flask_migration_critical_knowledge.md) — PAUSED 2026-06-11, verify currency on resume; 18 non-obvious Flask facts
- [code_quality_no_path_exclusion](reference_github_code_quality_no_path_exclusion.md) — NO path exclusion; re-verify
