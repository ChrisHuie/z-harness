# The final skill set — 10 skills

Decided by reading all 121 routed files (342,921 B) plus the 8 existing descriptions and the
15 built-in/plugin descriptions that share the same `msg[1]` listing. Method: Gate 3 of
`ROUTING-RULE.md`, with Gate 0 (SPLIT) applied to every file before routing and the
trigger-surface audit applied to every proposed container.

**Headline: `route.py`'s 8 destinations are wrong in 2 of 8, and PLAN §4's 12 is wrong in 2
of 12. The correct number is 10, and it costs +384 B always-on, not +1,600 B.**

---

## 1. The list

| # | skill | status | files routed to its body |
|---|---|---|---:|
| 1 | `craft-context-file` | unchanged | 0 |
| 2 | `craft-prompt` | unchanged | 0 |
| 3 | `craft-skill` | unchanged description, +1 body rule | 1 |
| 4 | `review-prompt` | unchanged | 0 |
| 5 | `git-workflow` | ship the draft description | 11 |
| 6 | `pr-review-method` | ship the draft description | 43 |
| 7 | `testing-ci` | **rewrite description** | 24 |
| 8 | `prebid-adcp` | **rewrite description** | 4 |
| 9 | **`agent-dispatch`** | **NEW** | 9 |
| 10 | **`outbound-drafts`** | **NEW** | 6 |

98 of the 121 land in a skill body. 23 leave the skill tier (§3).

### Always-on cost, measured

| | B of description text |
|---|---:|
| today, 8 skills | **4,924** |
| this proposal, 10 skills | **5,308** |
| **delta** | **+384 B for +2 skills** |

Two new skills cost less than one description because the four rewrites recover 300 B
(`git-workflow` 444→257, `pr-review-method` 491→475, `testing-ci` 452→378, `prebid-adcp`
415→392). For comparison: `route.py`'s 8 destinations imply 4 new descriptions
(`agent-harness`, `authoring-artifacts`, `python-tooling-traps`, `prebid-repos`) ≈ +1,600 B;
PLAN §4's 12 ≈ +1,400 B over this proposal. **This is the cheapest of the three sets and the
only one where every container passes a trigger-surface audit.**

### The four descriptions that change

All ≤400 chars, all user-sayable, all hazard-named rather than topic-named.

```
agent-dispatch (358)
Running work in parallel subagents — how many to launch, what to check before launching,
and how much of what they report to believe. Use before spawning agents or fanning out
reviewers, when one agent will edit files the others are reading, when a finished
background agent never delivers its report, and before repeating a subagent's explanation
as fact.
```

```
outbound-drafts (324)
Drafting text for someone outside this conversation — an issue body, a PR comment, a report
a contributor will act on, an RFC or briefing, a message to paste and send. Use when asked
to draft, write up, or produce something to post, send, or hand over, and when a draft puts
options in front of a group that has to decide.
```

```
testing-ci (377)
Deciding whether a test or a green check proves anything — mutation-testing the call site,
a suite that passed suspiciously, a selector that may have selected nothing, an allowlist
that reads as an all-clear, a patch or mock that quietly stopped taking effect, a formatter
that shifted the lines a guard keys on. Use before trusting a green run or calling a
behavior covered.
```

```
prebid-adcp (391)
AdCP spec authority and version resolution — what the pinned version's prose and graded
conformance storyboard require, with SDK types, error codes and reference implementations
as a read-only cross-check, never the authority. Use when implementing or reviewing AdCP
behavior, error codes or recovery classes, before citing an AdCP or SDK version, or when
mapping an SDK release to a spec.
```

`git-workflow` and `pr-review-method` ship exactly the draft descriptions in
`drafts/git/SKILL.md` and `drafts/pr/pr-review-method/SKILL.md`. Do not re-litigate them.

### Disjointness — the grep, run

Every proposed cue word `grep -i`'d against the 8 existing descriptions **and** the 15
built-in/plugin descriptions in the same listing (`dataviz`, `update-config`,
`fewer-permission-prompts`, `claude-api`, `simplify`, `review`, `security-review`, `run`,
`init`, `loop`, `schedule`, `keybindings-help`, `claude-in-chrome`, `artifact-*`).

| cue word | hits | verdict |
|---|---:|---|
| spawn · fan out · parallel · background agent | 0 | clean |
| issue body · PR comment · post · briefing · paste · hand over | 0 | clean |
| mutation · selector · green | 1 each (`testing-ci` itself) | clean |
| conformance · spec version | 1 each (`prebid-adcp` itself) | clean |
| **subagent** | **1 — `pr-review-method` (SHIPPED)** | **blocked; see below** |
| draft | 1 — `craft-prompt` | separable by object (a *prompt*) |
| allowlist | 1 — `fewer-permission-prompts` | different sense (permissions vs guards); accepted |

**`agent-dispatch`'s disjointness is conditional on the `pr-review-method` draft shipping.**
The *shipped* description contains "consolidating subagent findings"; the *draft* does not.
If the draft is not applied, `agent-dispatch` and `pr-review-method` both claim "subagent"
and Gate 3 says merge, not two skills. Ship the draft first.

Two instrument notes, because both directions of this grep have already failed once in this
project: my first pass reported `SKILL.md` in 8 of 8 descriptions — it was matching the
`…/SKILL.md:` **filename prefix**, not description text. Re-run with the prefix stripped:
`SKILL.md` appears in exactly **2** descriptions, `craft-skill` and `review-prompt`. That
correction is what routes `installed-skills-are-frozen-snapshots` (§3).

---

## 2. Trigger-surface audit — every skill, including the ones I am keeping

The test: *does the description match far MORE situations than the content actually serves?*

| skill | surface named | content served | verdict |
|---|---|---|---|
| `git-workflow` (draft) | commit/branch/stash/rebase/merge/`git mv`/PR-through-CI | write-side mechanics only | **PASS** — 57.9%→11.7% already measured in `drafts/git/CLAUDE-md-additions.md`; read-only git left behind, its one rule moved to `CLAUDE.md` |
| `pr-review-method` (draft) | review / re-review / addressed / ready / outstanding | 43 rules, all review-shaped | **PASS** |
| `testing-ci` (rewrite) | green run, suspicious pass, selector, allowlist, dead patch | 24 rules on false greens and false reds | **PASS** after `-k`→"a selector" and dropping "guard matchers" (salesagent vocabulary) |
| `prebid-adcp` (rewrite) | AdCP behavior, error codes, version citation | 4 rules on spec authority + version resolution | **PASS** |
| `agent-dispatch` | spawning, fanning out, shared trees, agent reports | 9 rules | **PASS** — names the ACT of dispatching, not the `Agent` tool |
| `outbound-drafts` | drafting something to post/send/hand over | 6 rules | **PASS** — the discriminator is "the reader is not in this conversation" |
| `craft-*` ×4 | authoring prompts/skills/context files | unchanged | not re-audited; `report-structure.md` flags they are 62% of the always-on skill budget for one topic family. Out of scope here, and I agree with its decision not to touch them in this migration. |

**The three containers that FAIL this test are exactly the three I am refusing to build:**

- `python-tooling-traps` — a description naming Python/`uv`/pytest/tox/pre-commit matches
  essentially every unit of work in a Python repo while serving ~6 specific traps. This is
  the `git-workflow` failure one domain over: **it names the TOOLCHAIN, not the operation.**
- `prebid-repos` — would have to cover org posture, adapter porting, and a repo path map.
  For this user "prebid" is the surface of nearly all work; the content is 8 unrelated
  project files.
- `refactor-safety` — its description ("refactoring, extracting a helper, deduplicating,
  deleting code, changing a wire shape") matches a large fraction of all code work, and its
  entire content compresses to one rule stated eight ways.

---

## 3. The corrected file→skill assignment — 23 of 121 move

`route.py` assigns 121 files to 8 destinations. I am moving **23**, deleting **2** of its
destinations, renaming **2**, and leaving 98 files where a skill body is the right home.
Every reason below comes from reading the file body, not the filename.

### 3a. Kill `python-tooling-traps` — 10 files, 4 destinations

| file | → | why (from the body) |
|---|---|---|
| `feedback_precommit_black_shifts_line_allowlists` | `testing-ci` | It is not about black. It is: *any line-count change breaks a line-keyed guard allowlist; converge formatting first, then derive; prefer symbol-keyed.* `testing-ci` already owns allowlists that read as an all-clear. |
| `reference_tox_commands_no_shell_substitution` | `testing-ci` | Its own last line says it: *"Instance of `feedback_empirical_over_static_guard_assessment`"* — which is already in the `testing-ci` bucket. Principle: a runner that execs argv without a shell passes `$(...)` as literal tokens; verify config by RUNNING it. |
| `reference_reload_captures_active_mock` | `testing-ci` | Manufactures **false findings and vacuous coverage simultaneously** (11 passed → 7 failed/4 vacuous). That is `testing-ci`'s charter verbatim. |
| `reference_lazy_imports_load_bearing` | `testing-ci` | The universal half is *where a name is resolved decides whether a patch is live*; hoisting silently kills the patch and the test passes via the real call. A false green. |
| `feedback_refactor_makes_dead_patches_live` | `testing-ci` | Same principle, opposite direction: the refactor makes a previously-**dead** patch live and its stale return value takes effect. These three are one rule and belong in one place. |
| `uv_venv_corruption_reinstall` | `testing-ci` | `uv sync` reports "Audited N packages" over a corrupted env and mypy emits spurious `Unused "type: ignore"`. A **false red** produced by the environment, not the diff. |
| `uv_frozen_for_commit_drift` | `git-workflow` | The mechanism is *a pre-commit hook that rewrites a tracked file aborts the commit*. The draft `git-workflow` body already carries the formatter case; this adds the lock-re-resolve case and the `UV_FROZEN=1` remedy. |
| `feedback_dependency_widen_pr_frozen_lock_masks` | `pr-review-method` | It is a **PR review method for a dependency PR**. Gate 3: the cue is "review this dependabot PR" → grep hits `pr-review-method` → add to that body. Stop. |
| `reference_httpx_ssrf_ip_pinning` | PROJECT (salesagent) | Names `httpcore._backends`, `src/core/security/url_validator.py`, `property_list_resolver`. Nothing survives the proper-noun rewrite except "pin the TCP target, not the SNI" — one fact, no cue. `report-skillaudit.md:234` independently rejected `security-patterns` as too thin. |
| `reference_mcp_structured_content_bypasses_model_dump` | PROJECT (salesagent) | fastmcp 3.2.0 + salesagent transports + "CLAUDE.md Pattern #4". Repo-bound by construction. |

### 3b. Kill `prebid-repos` — all 8 files stay in their silos

None of the 8 is a technique. They are org identity, competitive posture, a governance
attribution rule, a two-repo path map, and an adapter-porting program:
`feedback-firsthand-intel-outranks-docs`, `project-non-commercial-identity`,
`project-salesagent-wire-vs-engine-control`, `project-scope3-interchange-posture`,
`project_port_skills_hardening`, `reference-salesagent-python-in-legacy`,
`reference_port_fidelity_vs_target_norms`, `user-chrishuie-role`.

Gate 4 on each: *would this be false, or name a thing that does not exist, in a repo you have
never seen?* **Yes for all 8** — Scope3/Interchange/AAO, PR #1546, the `StellarPOC` fork,
prebid-server adapter conventions, `agentic-advertising/GOVERNANCE.md`. Repo level.
`report-skillaudit.md` reached the same verdict independently for this class:
*"genuinely project-scoped strategy. Correctly siloed. Do not promote."*

**One split (Gate 0):** `feedback-firsthand-intel-outranks-docs`'s principle —
*a grounding pass refines the mechanism; it never re-litigates a premise the user set from
the inside* — survives the proper-noun rewrite and is universal. One line to
`~/.claude/CLAUDE.md`. The instance (Scope3/AAO/BOK) stays in the agentic-prebid silo.

### 3c. `agent-harness` → `agent-dispatch`, 14 files → 9

**Ships:** `feedback-agent-token-budget`, `feedback_detecting_subagent_overconfidence`,
`feedback_fanout_preflight_disk_and_docker`,
`feedback_isolate_mutation_testing_reviewers_in_worktrees`,
`feedback_no_mutation_agents_on_shared_worktree`, `feedback_subagent_mechanism_is_a_claim`,
`feedback_two_phase_subagent_audit`, `reference_agent_worktree_isolation_may_provision_main`,
`reference_background_agent_report_retrieval`.

**Five leave:**

| file | → | why |
|---|---|---|
| `installed-skills-are-frozen-snapshots` | `craft-skill` body | Gate 3 default, and the grep is decisive: "SKILL.md" appears in exactly 2 descriptions, `craft-skill` and `review-prompt`. Hit → that skill's body. One copy, in `craft-skill`; `review-prompt` cross-references. |
| `worktree-window-helpers` | stays machine-level | Gate 0: pure instance. After the proper-noun rewrite nothing survives but "the user has shell aliases that open a PR in an isolated editor window." Four zsh functions in one auto-sourced file. Gate 4: instance is never user level. |
| `docker_desktop_stale_singleton_after_crash` | **R2 delete**, 1 line to `agent-dispatch` body | The fix (`rm …/Singleton{Cookie,Lock,Socket}` then `open -a Docker`) is **already verbatim in `~/.claude/CLAUDE.md`**. R2: same content, two channels, same request → delete the copy, keep the strongest tier. What is *not* in CLAUDE.md and is worth 2 lines of body: the `unmarshaling start request: unexpected EOF` signature, and the negative result that deleting `backend.lock` does **not** fix it. |
| `crash_forensics_check_user_scope_first` | `~/.claude/CLAUDE.md`, 1 line | Gate 2 A1+A2: it must govern the *first* answer after a crash, and nothing in "did anything survive?" names it. Its second half ("two corrections on one point = re-verify from scratch") is already in CLAUDE.md — R2, do not restate. The line: *After a crash, enumerate `~/.claude/projects/<CWD-project>/` before answering what survived; `*.meta.json` without `agent-*.jsonl` = transcripts lost.* |
| `feedback-timeout-is-not-an-answer` | `~/.claude/CLAUDE.md`, 3 lines — **and do not delete the file** | Gate 2 A1/A2/A3 all fire. PLAN §8 already records that its claimed duplicate — a CLAUDE.md "Interaction section" — **does not exist**; I confirmed it is absent from the live file. It documents `~/.claude/hooks/question_timeout_guard.sh`, which is live and registered. Deleting it orphans the hook; leaving it marked "SUPERSEDED" inside a live channel is an R1 defect. Fix the marker, add the rule to CLAUDE.md, keep the file as the hook's documentation. |

**Do NOT build `claude-code-harness`** (`report-planaudit.md` §6's proposal). I disagree with
it. After `installed-skills…` goes to `craft-skill`, `worktree-window-helpers` is recognised
as an instance, cost goes to `~/.claude/tools/cc-cost.py`, and the four cost traps stay in
`CLAUDE.md`, what remains is one crash-forensics procedure — under 1 KB of non-duplicated
content. And its description would `grep`-collide with the built-in `update-config`
("configure the Claude Code **harness** via settings.json"), which is in the same listing.
Naming a skill after the harness is naming the tool, not the operation.

### 3d. `authoring-artifacts` → `outbound-drafts`, 8 files → 6

**Ships:** `feedback-patterns-not-people`,
`feedback_author_artifacts_with_investigation_rigor`,
`feedback_final_reports_must_be_contributor_actionable`, `feedback_issue_draft_neutrality`,
`feedback_no_blockquote_for_pasteable_text`, `feedback_pr_review_writeup_style`.

**Two leave — and it is two, not one.** The brief flagged `feedback_no_pointless_comments`.
`feedback_no_issue_refs_in_comments` is the same misfile and was not flagged: its body is
*"Do not add issue numbers, PR numbers, or ticket references in **code comments**"*. Both
fire while writing code; the bucket's cue class is outbound prose. Disjoint cue classes in
one skill dilute the trigger for both.

Their destination is not another skill — it is `~/.claude/CLAUDE.md`, and all three Gate-2
arrival tests fire:
- **A1** — must be true before the first `Edit`, not after.
- **A2** — nothing in "fix this bug" will name comments.
- **A3** — the consumers are the 10 salesagent review lenses, every one of which carries a
  `tools:` allowlist without `Skill` (PLAN §0a). Skills are invisible there; always-on
  arrives.

One line: *No explanatory comments on standard patterns, and no issue/PR numbers in code
comments — git history is the traceability.*

### 3e. `pr-review-method`, 42 → 43

**Out (2):**

| file | → | why |
|---|---|---|
| `feedback-adversarial-review-user-adjudicates` | PROJECT (rereview-agent) | Not a review method — a collaboration-stance fact ("the user likes adversarial review of ideas and adjudicates relevance"). Its actionable half is already carried by CLAUDE.md's "Claims and evidence" and "Work in single verified steps". |
| `reference_github_code_quality_no_path_exclusion` | MEMORY, with the expiry event written in | Gate 5, the one thing that qualifies: volatile external state with a nameable expiry — *"as of 2026-07, roadmapped later 2026"*. Write "expires when GitHub ships path exclusion" on line 1. It is an R1 anchor failure waiting to happen inside a skill body. |

**In (4):** `feedback_personal_harness_gitignored_only` (from `testing-ci` — it is a
reviewer-boundary rule, the same rule as `feedback_reviewer_first_not_steward` one level
down: gitignored tooling that reviews others' code must never gate their CI);
`feedback_dependency_widen_pr_frozen_lock_masks`; `reference_sdk_bump_delta_verification`
(from `prebid-adcp` — the technique is *introspect both versions, diff the model surface,
trace every unhandled change*, which is a bump-PR review method, not AdCP authority).

**Two rules to generalise on the way in** (Gate 0, and PLAN §4 asks for it):
`feedback_root_cause_first` cites "the gold-standard PRs (#1306/#1307/#1312/#1389)" — strip
the list and the phrase; CLAUDE.md bans "gold standard" in output.
`feedback_project_wide_pattern_understanding` says "all 3 transports, all adapters, all 5
test suites" — generalise to *every surface the pattern could hold on*.

### 3f. `testing-ci`, 19 → 24

**Out (1):** `feedback_personal_harness_gitignored_only` → `pr-review-method` (above).
**In (6):** the six from §3a.

### 3g. `prebid-adcp`, 7 → 4

**Keeps:** `feedback_ground_protocol_work_in_spec_not_assumptions`,
`feedback_recovery_audit_coherence_blind_to_condition`, `reference_adcp_sdk_spec_mapping`,
`reference_adcp_spec_grounding`.

| file | → | why |
|---|---|---|
| `reference_sdk_bump_delta_verification` | `pr-review-method` | See §3e. |
| `feedback_primary_sources_over_press_coverage` | `~/.claude/CLAUDE.md` (1 clause) + PROJECT | Nothing in it is AdCP-specific — it is a source-priority ladder for any external system. CLAUDE.md's "Claims and evidence" already covers most of it; the missing clause is the ordering: *an installed artifact outranks its docs; docs outrank press.* **Delete the fan-out sentence before it moves anywhere:** "depth is the default, not the escalation — fan out one agent per load-bearing claim" **directly contradicts** CLAUDE.md's always-on "Default is a SINGLE pass, ZERO spawned agents." R1: the anchor fails; correct it or delete it. |
| `reference-aamp-maturity-mid2026` | PROJECT (agentic-prebid) + 1 line | A dated snapshot of a moving target — "SDKs release-tagged v2.0 though pyproject still 0.1.0", "comment closed Jan 2026", "ARTF DRAFT". Every anchor is a scheduled R1 failure inside an always-loadable body. One durable line to the `prebid-adcp` body: *AAMP delegates the transport wire to MCP/A2A/REST and owns only frozen-object semantics; the object substrate is ratified, the agent-wire layer is reference-code-only.* The strategic "open seat" paragraph stays in the silo. |

### 3h. `git-workflow`, 13 → 11 body + 3 to `CLAUDE.md`

No change from me. `drafts/git/SKILL.md` + `drafts/git/CLAUDE-md-additions.md` already
resolve this bucket: `feedback_feature_branch_first`, `reference_git_grep_ere_no_word_boundary`
and `feedback_no_alarm_mid_operation` go always-on (measured: their triggers land in units
where the narrowed skill will not fire); the other 10 are in the draft body. **+1 in:**
`uv_frozen_for_commit_drift` (§3a).

### 3i. Where the 121 end up

| destination | files |
|---|---:|
| `pr-review-method` body | 43 |
| `testing-ci` body | 24 |
| `git-workflow` body | 11 |
| `agent-dispatch` body | 9 |
| `outbound-drafts` body | 6 |
| `prebid-adcp` body | 4 |
| `craft-skill` body | 1 |
| **skill total** | **98** |
| `~/.claude/CLAUDE.md` (whole file) | 7 |
| PROJECT silo (stay) | 14 |
| memory, with an expiry event | 1 |
| R2 delete (already in CLAUDE.md) | 1 |
| **total** | **121** |

The 7 whole-file promotions are `feedback_feature_branch_first`,
`reference_git_grep_ere_no_word_boundary`, `feedback_no_alarm_mid_operation`,
`crash_forensics_check_user_scope_first`, `feedback-timeout-is-not-an-answer`,
`feedback_no_pointless_comments`, `feedback_no_issue_refs_in_comments`. Two of the 14
PROJECT files additionally donate **one clause each** to `CLAUDE.md` and keep their remainder
in the silo: `feedback_primary_sources_over_press_coverage` (the source-priority ladder) and
`feedback-firsthand-intel-outranks-docs` (the premise-vs-mechanism rule). Net always-on
addition: ~9 lines against §5's 100-line target — **9%, and it must be priced against the
diet, not waved through.** Ranked by strength if it has to be cut: the two code-comment rules
and the timeout rule are load-bearing (a live hook, and a consumer class that cannot see
skills at all); the crash-scope line is the first to drop.

---

## 4. The three verdicts you asked for, stated flat

**`python-tooling-traps` — DO NOT BUILD. Disperse the 10 files across four existing homes.**
PLAN §4 is right that the container is dead; `route.py` is right that the files are not all
project-local. §4's stated reason does not transfer cleanly (its "10 of 13 Python-flagged"
counts `local-env`'s 13-file set, which overlaps `route.py`'s 10 by only 4 —
`uv_venv_corruption_reinstall`, `uv_frozen_for_commit_drift`,
`reference_tox_commands_no_shell_substitution`, `reference_lazy_imports_load_bearing`). The
reason that does transfer is the trigger-surface audit: **a skill named after a toolchain
matches every unit of work in a repo using that toolchain.** 8 of the 10 files carry a real
universal principle; each has a *different* cue, and every one of those cues already hits an
existing description. Gate 3's default — "any hit → add to that skill's BODY" — resolves the
whole bucket without a new description.

**`prebid-repos` — DROP. All 8 stay in their silos; no skill is built.** It has no §4
counterpart because it should not exist. Not one of the 8 is a technique, and the container
would need three unrelated cue classes (org posture, adapter porting, a repo path map) in
one description. Zero knowledge is lost: these files are already sitting in the silo of the
project they describe. This is a *don't move*, not a *move*.

**`refactor-safety` and `test-authoring` — DO NOT BUILD. Both fail the split test on the
same clause.** PLAN §4 wants both; `route.py` routes zero files to either.
- `refactor-safety`: the cue is disjoint, but **"grep repo-wide and count the copies before
  writing the fix" is required by BOTH halves** — by the reviewer and by the author — and it
  is the entire content. `report-skillaudit.md` itself names the alternative ("fold this into
  pr-review-method's body… cheaper, no new description tax, no overlap hazard") and then
  recommends against it on the authoring-time trigger. I take the alternative: an
  authoring-time trigger you cannot state without matching most code work is not a trigger.
  The one durable rule already sits in the `pr-review-method` draft under *Finding a defect*.
- `test-authoring`: **"a test that cannot fail is not a test" is required by both halves.**
  §4 itself scopes it to "3 rules only" — `feedback_always_improve_testing`,
  `synthetic-tests-self-confirm`, `reference_bdd_negative_scenario_vacuous_on_empty` — and
  all three are phrased as *detection* rules, so the `testing-ci` verification cue already
  reaches them. Three rules do not buy a permanent description.

**`claude-code-cost` → TOOL.** Agreed with §4 and `report-planaudit.md`, no change. It is a
deterministic pipeline whose prose execution is recorded producing 3× inflation and a 90.8%
undercount.

---

## 5. Scope boundary between each adjacent pair — one sentence each

| pair | boundary |
|---|---|
| `git-workflow` ↔ `pr-review-method` | `git-workflow` is everything up to and including the push and whether CI will run; `pr-review-method` starts once there is a PR with comments on it. |
| `git-workflow` ↔ `testing-ci` | `git-workflow` owns commands that change the repo and lie about it; `testing-ci` owns commands that report a verdict and lie about it. |
| `git-workflow` ↔ `agent-dispatch` | `git-workflow` is what one actor does to a tree; `agent-dispatch` is what happens when several actors share one. |
| `pr-review-method` ↔ `testing-ci` | `pr-review-method` decides whether a *change* is right; `testing-ci` decides whether the *evidence* that it is right would have gone red. |
| `pr-review-method` ↔ `outbound-drafts` | `pr-review-method` decides what is true and where it anchors (the API will 422 an anchor outside the diff); `outbound-drafts` decides how it reads and whether it is safe to send. |
| `pr-review-method` ↔ `agent-dispatch` | `pr-review-method` owns pinning a fan-out to a PR head and not dropping a site on consolidation; `agent-dispatch` owns whether to fan out at all and whether to believe what came back. |
| `testing-ci` ↔ `agent-dispatch` | `testing-ci` is why a red or green is false; `agent-dispatch` is why the agent that produced it was in a position to be wrong (shared tree, ENOSPC, no isolation). |
| `agent-dispatch` ↔ `craft-skill` | `agent-dispatch` is about running an agent; `craft-skill` is about authoring the artifact an agent loads — including the fact that the installed copy is a frozen snapshot. |
| `outbound-drafts` ↔ `craft-prompt` / `craft-context-file` | `outbound-drafts` shapes text a *person* will read and act on; the craft-* skills shape text a *model* will be conditioned on. |
| `outbound-drafts` ↔ `~/.claude/CLAUDE.md` | CLAUDE.md holds the rules that must hold before the first token of any output (no provenance, no marketing adjectives, code comments); `outbound-drafts` holds the shape decisions you make once you know what artifact you are producing. |
| `prebid-adcp` ↔ `pr-review-method` | `prebid-adcp` says what the spec requires; `pr-review-method` says how to prove a diff meets it — including the technique for a version-bump PR. |
| `prebid-adcp` ↔ `testing-ci` | `prebid-adcp` is the authority a conformance check is graded against; `testing-ci` is whether that check would fail if the behavior broke. |
| `prebid-adcp` ↔ PROJECT silos | `prebid-adcp` carries version-resolution and precedence over sources of truth; every posture, org-identity, and repo-path fact stays in the repo it describes. |
| `craft-skill` ↔ `review-prompt` ↔ `craft-prompt` ↔ `craft-context-file` | Unchanged and not re-examined here. |

---

## 6. Where I disagree, explicitly

**With `route.py`:**
1. `python-tooling-traps` should not exist — 10 files, 4 correct homes, 0 new descriptions.
2. `prebid-repos` should not exist — 8 files, all correctly siloed already.
3. `agent-harness` is 5 files too wide; 3 of the 5 belong always-on or in `craft-skill`, and
   one is a pure instance.
4. `authoring-artifacts` misfiles **two** code-comment rules, not one.
5. `feedback_personal_harness_gitignored_only` is in `testing-ci` and is a reviewer-boundary
   rule.
6. `reference_sdk_bump_delta_verification` is in `prebid-adcp` and is a PR-review technique.
7. `reference_github_code_quality_no_path_exclusion` is a dated external-product fact routed
   into a skill body, where its anchor will fail silently.

**With PLAN §4:**
1. `refactor-safety` — do not build. Fails the split test's "no rule required by both halves".
2. `test-authoring` — do not build. Same clause; §4's own "3 rules only" is the tell.
3. `writing-for-github` is the wrong name and the wrong boundary: two of its six files are
   not GitHub (a Slack message, a PMC briefing), and the name points at a *destination*
   rather than the operation. `outbound-drafts` is the same content with a cue that survives
   the trigger-surface test.
4. §4's `local-env` reasoning is cited in the brief as contradicting
   `python-tooling-traps`. It does not contradict it cleanly — the two source sets overlap by
   4 of 10. The conclusion is the same; **the stated reason does not carry it**, and the
   reason that does is the trigger-surface audit.
5. §4 is silent on `installed-skills-are-frozen-snapshots`, `worktree-window-helpers`,
   `crash_forensics_check_user_scope_first` and `feedback-timeout-is-not-an-answer`. All four
   need a decision; all four are made above.

**With `report-planaudit.md`:** `claude-code-harness` should not be built (§3c). Its content
disperses to `craft-skill`, `CLAUDE.md`, a tool, and one machine-level file, and its name
`grep`-collides with the built-in `update-config` in the same listing.

**With `report-skillaudit.md`:** it routes `feedback_snowball_to_avalanche` and
`feedback_reverify_pr_head_before_and_after_fanout` into the dispatch skill. The first is a
full-suite rule with no dispatch content (`testing-ci` is right); the second is two different
rules that both survive — "an active PR moves mid-review" (`pr-review-method`) and "pass the
target SHA and make the agent verify it" (`agent-dispatch`) — so it is not a duplicate.

---

## 7. Preconditions — this assignment is void without them

1. **PLAN §0a must land first.** 43 of the 98 routed rules go to `pr-review-method`, whose
   primary consumers are the 10 salesagent review lenses, and **none of their `tools:`
   allowlists includes `Skill`** — measured. In that population a skill is invisible in both
   channels. Moving 43 rules out of files those agents *can* `Read` and into a body they
   cannot load is a net loss. One token per file, ten files.
2. **The mandatory routing directive must land first** (PLAN §7 step 0). Without it, measured
   embedded firing is 1/5. `report-trigger.md` Part 2: 100% miss on every surface definition
   tried, for all 8 skills.
3. **Ship the `pr-review-method` draft description before `agent-dispatch`**, or the two
   collide on "subagent" and Gate 3 says merge.
4. **The 8.6× compression is real and unaddressed.** 98 files at ~340 KB into 6 bodies capped
   at 5 KB each (`report-structure.md:127`) is selection, not preservation. This document
   assigns **rules**, not file contents. PLAN §3's "content moves to skill bodies" is not what
   any of these routes do, and §8b already names the contradiction.
   **Measured, and it already bites the two exemplar drafts:** `drafts/pr/pr-review-method/SKILL.md`
   is **5,519 B** and `drafts/git/SKILL.md` is **5,403 B** — both over the 5 KB cap before a
   single one of my four additions lands. Either the cap moves or the drafts lose content;
   that is a decision, not a rounding error.

---

## NOT MEASURED

- **No proposed description was exercised against a fresh session.** Trigger behaviour is
  unfalsifiable from inside the authoring session. The 4 rewrites and 2 new descriptions are
  reasoned, not tested. `report-trigger.md` Part 3 shows isolated-prompt eval scores 24/24 on
  descriptions that fire 0/78 in real work — so an eval pass would not settle it either.
- **No firing-rate measurement exists for `agent-dispatch` or `outbound-drafts`.** Their
  trigger-surface verdicts are structural arguments, not the 57.9%→11.7% style measurement
  that settled `git-workflow`. That measurement requires a corpus scan I did not run.
- **I did not verify the 8.6× compression per-skill.** I did not count how many of the 43
  rules routed to `pr-review-method` survive a 5 KB body, nor which are already in the draft.
  The draft is 5,519 B (already over cap) and contains ~25 of them; the remaining ~18 have no
  measured budget.
- **`route.py` was read only in its first 60 lines** — enough to confirm the salesagent block
  verbatim. Its 8 destinations *were* confirmed mechanically across the whole file
  (`grep -o "'SKILL:[a-z-]*'" | sort | uniq -c` → agent-harness 5, authoring-artifacts 3,
  git-workflow 1, pr-review-method 3, prebid-adcp 2, prebid-repos 2, python-tooling-traps 1,
  testing-ci 2 — 8 distinct names, 19 `a(...)` calls). I did not re-run the script.

### Measured after first draft, now settled — recorded because the claims are load-bearing

- `~/.claude/CLAUDE.md` is **10,368 B**. The Docker singleton fix is present **verbatim at
  line 52** → the R2 delete in §3c stands.
- `AskUserQuestion`, `timeout`, and `Interaction` return **zero hits** in that file. PLAN §8's
  finding reproduces exactly: `feedback-timeout-is-not-an-answer` is marked SUPERSEDED against
  a section that does not exist. Do not delete it.
- "Two user corrections on one point" is at line 53 (so `crash_forensics`' second half is a
  genuine R2 duplicate) and "gold standard" is banned at line 115 (so the
  `feedback_root_cause_first` strip in §3e is required, not stylistic).
- **I did not test whether "write a test for X" ever co-occurs with the three
  `test-authoring` rules' conditions.** That is the one measurement that could overturn §4's
  `test-authoring` and my rejection of it; the decision above rests on the split test alone.
- **The craft-\* four were not audited.** `report-structure.md` flags them at 62% of the
  always-on skill budget for one topic family with ~40% negative routing text. I left them
  untouched, matching its recommendation, but that is a deferral, not a verdict.
- **Read-only throughout.** Nothing under `~/.claude/` or any repo was modified; the only
  writes are in this scratchpad.
