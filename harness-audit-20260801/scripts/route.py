import glob,os,collections
R={}
def a(sil,names,dest):
    for n in names.split():
        R.setdefault(sil,{})[n]=dest

# ---------------- salesagent (SA)
a('SA',"""backgrounded_commit_exit_code_masks_failure feedback_atomic_breaking_changes
feedback_cleanup_chain_use_semicolon_not_ampersand feedback_feature_branch_first
feedback_issue_vs_pr_number feedback_merge_creates_duplication_sweep_ssot feedback_no_alarm_mid_operation
feedback_verify_branch_currency_before_rebuild gh_actions_dirty_merge_skips_pull_request_workflows
git_mv_then_add_old_path_aborts_commit reference_git_grep_ere_no_word_boundary
reference_release_please_pr_ci_mechanics reference_stacked_pr_ci_does_not_run""",'SKILL:git-workflow')
a('SA',"""feedback_audit_checklist_systematic feedback_complete_claim_requires_full_pattern_enumeration
feedback_confession_marker_grep_before_ready feedback_defect_recurrence_is_the_root_cause
feedback_detector_surface_blindness feedback_diff_scope_hides_duplicate_twin
feedback_duplicate_deletion_needs_reader_enumeration feedback_evidence_is_not_a_disposition
feedback_exception_class_partition_needs_condition_mapping feedback_findings_need_anchors_post_as_threads
feedback_github_ci_review_blind_spots feedback_grade_remedy_composition_not_checkboxes
feedback_infra_limitation_needs_cost_estimate feedback_new_abstraction_needs_adoption_completeness
feedback_no_author_filter_on_first_audit_pass feedback_no_cheap_wins_pings feedback_no_optional_disposition
feedback_no_pr_count_reduction_framing feedback_pattern_extraction feedback_principled_scope_expansion
feedback_prior_round_finding_needs_remeasure feedback_project_wide_pattern_understanding
feedback_ready_claim_requires_fresh_pr_audit feedback_rereview_diff_against_current_main_not_mergebase
feedback_reverify_pr_head_before_and_after_fanout feedback_review_consolidation_drops_findings
feedback_review_deliverable_against_issue_contract feedback_review_tooling_prs_derive_invariant_and_probe_inputs
feedback_reviewer_first_not_steward feedback_root_cause_first feedback_semantic_ssot_defect_class
feedback_single_source_of_truth_requires_deleting_duplicates feedback_substrate_prs_need_production_callers
feedback_verify_provenance_before_preexisting_claim feedback_verify_reviewer_fixes_against_code
feedback_verify_worklist_items_real pr_review_audit_workflow reference_docker_image_cve_review_gotchas
reference_github_code_quality_no_path_exclusion reference_github_inline_comment_anchoring""",'SKILL:pr-review-method')
a('SA',"""feedback_always_improve_testing feedback_ci_optimization_silent_noop
feedback_claimed_invariant_needs_failing_oracle feedback_empirical_over_static_guard_assessment
feedback_flaky_test_single_green_run_is_luck feedback_guard_matcher_completeness
feedback_mutation_oracle_selector_must_be_verified feedback_oracle_decay_from_redundant_mechanism
feedback_personal_harness_gitignored_only feedback_short_circuit_coverage_illusion feedback_snowball_to_avalanche
feedback_structural_guards_pin_production_paths feedback_verify_branch_runs_assert_head
feedback_wire_shape_change_systematic_sweep reference_bdd_negative_scenario_vacuous_on_empty
reference_guard_selftest_full_chain_over_leaf reference_release_jobs_invisible_to_pr_ci
run_all_tests_congratulations_masks_failures""",'SKILL:testing-ci')
a('SA',"""crash_forensics_check_user_scope_first docker_desktop_stale_singleton_after_crash
feedback_detecting_subagent_overconfidence feedback_fanout_preflight_disk_and_docker
feedback_isolate_mutation_testing_reviewers_in_worktrees feedback_no_mutation_agents_on_shared_worktree
feedback_subagent_mechanism_is_a_claim feedback_two_phase_subagent_audit
reference_agent_worktree_isolation_may_provision_main reference_background_agent_report_retrieval""",'SKILL:agent-harness')
a('SA',"""feedback_author_artifacts_with_investigation_rigor feedback_final_reports_must_be_contributor_actionable
feedback_no_blockquote_for_pasteable_text feedback_no_issue_refs_in_comments feedback_no_pointless_comments
feedback_pr_review_writeup_style""",'SKILL:authoring-artifacts')
a('SA',"""feedback_dependency_widen_pr_frozen_lock_masks feedback_precommit_black_shifts_line_allowlists
feedback_refactor_makes_dead_patches_live reference_httpx_ssrf_ip_pinning reference_lazy_imports_load_bearing
reference_mcp_structured_content_bypasses_model_dump reference_reload_captures_active_mock
reference_tox_commands_no_shell_substitution uv_frozen_for_commit_drift uv_venv_corruption_reinstall""",'SKILL:python-tooling-traps')
a('SA',"""feedback_ground_protocol_work_in_spec_not_assumptions feedback_primary_sources_over_press_coverage
feedback_recovery_audit_coherence_blind_to_condition reference_adcp_sdk_spec_mapping
reference_adcp_spec_grounding reference_sdk_bump_delta_verification""",'SKILL:prebid-adcp')
a('SA',"""agentdb_persistent_schema_masks_fresh_db_failures feedback_a2a_skill_handlers_must_raise
feedback_a2a_wire_tests_must_drive_on_message_send feedback_advisory_on_success_error_pattern
feedback_changed_wire_field_dormant_grader_check feedback_check_normalizer_before_input_surface_regression
feedback_fitness_functions_pattern feedback_mock_only_tests_dont_prove_wiring feedback_planning_doc_location
feedback_pr_base_current_main_push_origin feedback_readiness_verdict_gate feedback_run_e2e_locally_before_push
feedback_run_full_suite_before_every_push feedback_uow_detached_after_exit
feedback_use_full_review_skill_not_handrolled_fanout feedback_valueerror_boundary_vs_internal
harness_error_wire_per_transport_mechanics no_concurrent_agentdb_during_full_integration_run
project_review_harness_share_repo reference_agentdb_port_mismatch reference_bdd_harness_patterns
reference_bdd_harness_pitfalls reference_gam_creative_level_targeting_exists
reference_gam_language_targeting_silent_drop reference_harness_freshness_mechanisms
reference_per_diff_review_detectors reference_review_patterns reference_ruff_f821_ignored
reference_run_all_tests_in_network_artifacts wire_envelope_policy""",'PROJECT:salesagent[IDX]')
a('SA',"""flask_migration_critical_knowledge flask_to_fastapi_migration_v2
reference_bdd_inline_steps_escape_guards""",'PROJECT:salesagent[unindexed]')
a('SA',"""ci_refactor_rollout_state feedback_a2a_harness_real_auth_chain feedback_black_ruff_format_disagreement
precommit_mypy_adcp_pin prek_pre_commit_replacement_bug project_backlog_triage_2026_07
project_sovereign_multiprotocol_rail reference_verify_spec_skill_not_portable""",'DELETE:stale-or-dup')
a('SA',"""feedback_agent_team_execution_model feedback_docs_voice_factual_dense
feedback_escalate_recurring_lessons_to_guards feedback_generalize_memories_and_skills
feedback_github_issue_drafting feedback_lean_toward_quality_not_smaller_option
feedback_no_agent_fanout_by_default feedback_no_code_in_planning_stage
feedback_no_internal_dialogue_in_public_artifacts feedback_no_pr_specifics_in_memory feedback_no_ready_claims
feedback_no_unsafe_autofix feedback_plan_approval_gate feedback_session_workflow_rules
feedback_subagent_model_inherit feedback_subagents_need_explicit_read feedback_thorough_review
feedback_thoroughness_over_momentum feedback_trace_flows_not_claims feedback_truth_over_optimism
feedback_user_owns_git_push feedback_verify_before_asserting feedback_verify_remedy_before_public_post
user_profile""",'DELETE:superseded-by-CLAUDE.md')
# ---------------- others
a('GAD',"no-real-names-in-db",'PROJECT:github-activity-db[IDX]')
a('CCS',"pr1389-property-list-context salesagent-worktree-layout",'DELETE:stale-or-dup')
a('ADT',"adcp-kernel-empirical-anchors",'DELETE:stale-or-dup')
a('ADT',"adcp-kernel-standalone-decoupled adcp-kernel-tool-is-go",'PROJECT:adcp-tooling[IDX]')
a('ADT',"synthetic-tests-self-confirm",'SKILL:testing-ci')
a('AA',"feedback_issue_draft_neutrality",'SKILL:authoring-artifacts')
a('AA',"feedback_iterative_planning feedback_opus_verification",'DELETE:superseded-by-CLAUDE.md')
a('AA',"project_agentic_advertising project_storyboard_run_methodology",'PROJECT:agentic-advertising[IDX]')
a('AP',"feedback-agent-token-budget",'SKILL:agent-harness')
a('AP',"feedback-dont-be-eager-to-advance feedback-dont-reference-time user-plain-language-for-infra",'CLAUDE.md')
a('AP',"feedback-explicit-go-before-building",'DELETE:superseded-by-CLAUDE.md')
a('AP',"project-tech-stack-audit",'DELETE:stale-or-dup')
a('AP',"feedback-mirror-prose-not-enforcement",'SKILL:pr-review-method')
a('AP',"""feedback-firsthand-intel-outranks-docs project-non-commercial-identity
project-salesagent-wire-vs-engine-control project-scope3-interchange-posture
reference-salesagent-python-in-legacy user-chrishuie-role""",'SKILL:prebid-repos')
a('AP',"reference-aamp-maturity-mid2026",'SKILL:prebid-adcp')
a('AP',"""project-aamp-play project-configuration-first project-neutral-primitives-charter
project-order-of-record-pivot project-positioning-and-core-decisions project-real-money-first
project-substrate-ownership-strategy project-transport-and-comms project-two-seat-model""",'PROJECT:agentic-prebid[IDX]')
a('AP',"""project-agent-discovery-decapture project-agent-trust-layer project-authority-layer
project-human-surface project-reference-agents project-salesagent-lessons project-technical-grading
project-threat-model project-transition-as-trigger""",'PROJECT:agentic-prebid[unindexed]')
a('HP',"project-hermes-fleet-plan",'PROJECT:hermes-plan[IDX]')
a('NOR',"feedback-budget-is-a-resource norbert-skills-temporal-design",'DELETE:stale-or-dup')
a('NOR',"feedback-no-self-declared-convergence",'CLAUDE.md')
a('NOR',"feedback-timeout-is-not-an-answer",'SKILL:agent-harness')
a('NOR',"temporal-backbone-design user-norbert-wiener",'PROJECT:norbert-skills[IDX]')
a('PAS',"feedback_no_claude_coauthor_trailer",'CLAUDE.md')
a('PAS',"""feedback_multi_phase_workflow feedback_no_blockquote_for_pasteable_text
feedback_no_internal_dialogue_in_public_artifacts feedback_no_pr_specifics_in_memory feedback_push_policy
feedback_review_rigor feedback_subagent_model""",'DELETE:stale-or-dup')
a('PAS',"project_port_skills_hardening reference_port_fidelity_vs_target_norms",'SKILL:prebid-repos')
a('PAS',"project_teal_pr_remediation",'PROJECT:prebid-agent-skills[unindexed]')
a('PH',"installed-skills-are-frozen-snapshots",'SKILL:agent-harness')
a('PH',"corpus-contradictions-are-cross-file-and-untooled prompt-harness-goal",'PROJECT:prompt-harness[IDX]')
a('PH',"prompt-harness-pr-review-method",'PROJECT:prompt-harness[unindexed]')
a('RRA',"feedback-adversarial-review-user-adjudicates",'SKILL:pr-review-method')
a('RRA',"feedback-pace-and-presentation",'CLAUDE.md')
a('RRA',"feedback-patterns-not-people",'SKILL:authoring-artifacts')
a('RRA',"rereview-agent-goal-and-decisions rereview-preimage-underdetermination",'PROJECT:rereview-agent[IDX]')
a('HOME',"cmux-shortcuts-cheatsheet",'PROJECT:home[unindexed]')
a('HOME',"worktree-window-helpers",'SKILL:agent-harness')

SIL={'-Users-quantum-Documents-ComputedChaos-salesagent':'SA','-Users-quantum-Documents-GitHub-agentic-prebid':'AP',
'-Users-quantum-Documents-GitHub-prebid-agent-skills':'PAS','-Users-quantum-Documents-GitHub-norbert-skills':'NOR',
'-Users-quantum-Documents-GitHub-rereview-agent':'RRA','-Users-quantum-Documents-GitHub-agentic-advertising':'AA',
'-Users-quantum-Documents-GitHub-prompt-harness':'PH','-Users-quantum-Documents-GitHub-adcp-tooling':'ADT',
'-Users-quantum-Documents-ComputedChaos-skills':'CCS','-Users-quantum':'HOME',
'-Users-quantum-Documents-GitHub-hermes-plan':'HP','-Users-quantum-Documents-ComputedChaos-github-activity-db':'GAD'}
actual=collections.defaultdict(set)
for f in glob.glob('/Users/quantum/.claude/projects/*/memory/*.md'):
    if f.endswith('MEMORY.md'): continue
    actual[SIL[f.split('/projects/')[1].split('/memory/')[0]]].add(os.path.basename(f)[:-3])
tot=0;miss=[];extra=[]
for s in actual:
    got=set(R.get(s,{}))
    miss+= [(s,x) for x in sorted(actual[s]-got)]
    extra+=[(s,x) for x in sorted(got-actual[s])]
    tot+=len(actual[s])
print("actual files:",tot,"assigned:",sum(len(v) for v in R.values()))
print("UNASSIGNED:",miss)
print("PHANTOM:",extra)
c=collections.Counter(d for v in R.values() for d in v.values())
for k,v in sorted(c.items(),key=lambda x:-x[1]): print(f"{v:4d}  {k}")
print("--- by bucket")
b=collections.Counter(('SKILL' if d.startswith('SKILL') else 'PROJECT' if d.startswith('PROJECT') else d.split(':')[0]) for v in R.values() for d in v.values())
print(b)
