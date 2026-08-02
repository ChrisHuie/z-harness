## Verdict

The plan is **right about the shape and wrong about three of the six additions.** Its own diagnosis — mechanism narration is pure tax — is correct, and it then commits that error in every new description it writes (~800 B of the 2,459 B it proposes is text no user would say). More seriously: one proposed skill (`local-env`) is the exact failure the audit was chartered to hunt, and one (`claude-code-cost`) is a script wearing a skill's clothes.

Cost is not the reason to do any of this. Measured below: the entire 8→14 change is **+0.28% of corpus**, and the whole program including the CLAUDE.md diet nets **−0.37%**. Against §6d's "the program is cost-neutral at best," this is a rounding error. Decide on knowledge travel and enforcement, not bytes.

---

## Per-skill verdicts

| # | skill | verdict | the load-bearing reason |
|---|---|---|---|
| 1 | craft-context-file | **SHIP** (trim as planned) | No stack assumption anywhere. Works on a Rust engine's AGENTS.md unchanged. |
| 2 | craft-prompt | **SHIP** | Universal. |
| 3 | craft-skill | **SHIP** | Universal. |
| 4 | review-prompt | **SHIP** | Universal. |
| 5 | git-workflow | **SHIP + hook two rules up** | Git/GitHub-scoped, zero language or layout assumptions. Clean. |
| 6 | pr-review-method | **SHIP** | GitHub-scoped, correctly. One leak flagged below. |
| 7 | testing-ci | **GENERALISE-FIRST** | The one existing skill with a stack-specific token in its always-on description and salesagent commands in its body. |
| 8 | prebid-adcp | **SHIP at user level** — argued in §4 | Placement is right for a reason the plan doesn't state. |
| 9 | agent-dispatch | **SHIP, but 3 of its rules are hooks** | Best universality of the six; the skill shrinks once mechanized. |
| 10 | local-env | **WRONG-TIER — do not ship** | See §1. This is the failure mode you sent me to find. |
| 11 | writing-for-github | **SHIP, thinner** — 2 rules go up a tier | Genuinely universal-for-this-user; 3 of its rules are mechanical. |
| 12 | test-authoring | **GENERALISE-FIRST** | ~19 KB of its ~24 KB source mass is pytest-bdd. |
| 13 | refactor-safety | **SHIP with a de-dup precondition** | Most universal of the six; but it is a stance-shifted copy of an existing skill section. |
| 14 | claude-code-cost | **SHOULD-BE-A-TOOL** | Highest-confidence finding in this audit. |

---

## 1. Universality — the clauses that assume a repo

### `local-env` — kill it

I scored all 13 cited memories for stack markers. **10 of 13 are Python-flagged, 8 of 13 salesagent-flagged.** Four of the five symptoms named in its own description are stack-specific:

> "a stale **Docker Desktop** singleton after a crash, **port desync against a running container**, a **persistent schema** hiding a **fresh-DB** failure, concurrent **containers** producing spurious setup errors, corrupted or drifted **virtualenvs and lockfiles**"

In a Rust game engine this fires on "cargo build fails for no reason" and delivers Docker Desktop singleton recovery. Worse, two of its named sources cannot go to user level at all:

- `reference_lazy_imports_load_bearing` opens **"In salesagent, most function-local imports are NOT removable style debt"** and cites `src.core.database.repositories.uow.ProductUoW`, `patch("src.core.database.database_session.get_db_session")`, PR #1307. This is maximally repo-bound and the plan lists it as a `local-env` source.
- `prek_pre_commit_replacement_bug` carries **`> STALE as of 2026-08-01. Verified no longer accurate during the memory-consolidation audit. Kept for history; do not act on it.`** The plan cites it twice — once for `local-env`, once for the `git-workflow` body expansion. Promoting a memory that was verified dead *today* into an always-loaded user skill is the single most concrete defect in the plan.

What actually survives promotion is two facts, and neither is about a "local dev environment":
- `docker_desktop_stale_singleton_after_crash` — a **macOS machine** fact.
- `crash_forensics_check_user_scope_first` — a **`~/.claude/projects/` harness** fact.

Both belong in the harness skill (§6). The other eight are correctly siloed already; the plan is wrong to move them. **Net: `local-env` deletes, −453 B, no knowledge lost.**

### `test-authoring` — generalise before shipping

> "**BDD step and fixture** pitfalls"

`fixture` is a pytest noun; BDD here means `pytest-bdd`. The two largest sources are `reference_bdd_harness_pitfalls` (10,251 B) and `reference_bdd_harness_patterns` (5,912 B) — 16 KB of a ~24 KB source mass, all pytest-bdd against salesagent's harness. `feedback_a2a_wire_tests_must_drive_on_message_send` is AdCP-specific.

Three rules generalise cleanly and are worth a user skill: drive the real entry point not a mock; negative scenarios go vacuous on empty input; escalate a repeated lesson into a structural guard. **Ship those three. The 16 KB of BDD material goes to a salesagent project skill or a `references/bdd.md` the body routes to on demand — never into the always-on half.**

### `testing-ci` — the existing skill with the same disease

Always-on description:
> "checking whether a **`-k` selector**"

`-k` is a pytest flag, sitting in text paid on every dispatch in every project. Body, `SKILL.md:47-51`:
> "never by adding a guard to a shared repo's **`make quality`**: a **`tests/unit/test_architecture_*.py`** guard runs on every contributor's build"

and `SKILL.md:25`: "**tox** prints its own success banner over failed suites."

`make quality` is a salesagent target — report-diet correctly evicts that exact string from CLAUDE.md as "wrong in most projects this file loads into," then leaves it in a user skill body. Generalise: `-k` → "a test selector"; `make quality` → "the shared quality gate"; keep tox as one named instance of the class "runners that print their own success banner."

### `agent-dispatch` — two nouns

> "preflight disk and **Docker** … agents contend for a shared checkout, **database**, or disk"

Generalise both to "the services your agents depend on." Everything else is harness-level and travels.

### `refactor-safety` — universal, but already written down

Cleanest of the six on universality: no language, no GitHub, no layout. But four of its thirteen rules are already in `pr-review-method/SKILL.md:96-112` — new-abstraction-needs-a-production-caller, SSOT-deletes-duplicates-in-the-same-commit, deleting-one-of-N-writes, exception-class-tuple-reuse. Shipping it as written creates two copies that will drift.

**Precondition:** `refactor-safety` gets the authoring-time content and `pr-review-method`'s `## Scope and refactors` is cut to a pointer. One copy. The plan's own alternative (fold into pr-review-method) is worse — it loses the authoring-time trigger, which is where these defects are introduced.

### `writing-for-github` and `prebid-adcp`
No stack assumptions. Both travel.

---

## 2. Trigger text — mechanism narration in all six new descriptions

The plan cuts mechanism narration from the existing eight and writes it into every new one. Quoting the pure tax:

| skill | text no user would ever say | B |
|---|---|---|
| claude-code-cost | "deduping JSONL records by requestId, finding subagent transcripts one level down, taking max output_tokens across split records, and the cache-tier multipliers" | ~165 |
| agent-dispatch | "cap concurrency, isolate mutation-testing agents in a worktree, open every prompt with a mandatory Step 0 read list" | ~120 |
| writing-for-github | "Technical fact only, no provenance or internal quality labels, fenced blocks for anything to be pasted, location + fact + fix per line" | ~130 |
| test-authoring | "negative scenarios that go vacuous on empty input … escalating a repeated lesson into a structural guard" | ~105 |
| refactor-safety | "an SSOT consolidation that leaves the old paths live, deleting one of N writes without enumerating readers" | ~105 |

**~625 B, 25% of the proposed addition, is body content restated in the tier that charges per dispatch.** Every one of these is the *rule*, and a rule belongs in the free half.

Rewritten, same triggers, no mechanism (measured):

```
agent-dispatch (398 → 329 B)
Spawning subagents — what to check before a fan-out, how many to run at once, keeping
code-modifying agents out of your working tree, and how far to trust what they report back.
Use before spawning any agent or fan-out, when a subagent's report looks wrong, or when
parallel agents interfere with each other.

writing-for-github (396 → 260 B)
House style for anything Chris will paste, publish, or hand to another person — PR bodies,
issue drafts, review write-ups, commit messages, code comments, docs. Use when drafting any
of those, or any report meant to leave this session.

test-authoring (429 → 376 B)
Writing a test that can actually fail — driving the real entry point rather than a mock,
negative cases that pass vacuously on empty input, and turning a repeated lesson into an
enforced check. Use when adding or strengthening a test, building a harness or fixture, or
making an invariant enforceable. To judge an existing test's strength, use testing-ci.

refactor-safety (405 → 305 B)
Defects a diff-local view cannot see — a twin of your new helper in an untouched file, a
consolidation that leaves the old paths live, an abstraction with no caller, deleting one of
N writes. Use when refactoring, extracting, deduplicating, deleting code, or changing a
shared shape.

claude-code-harness (replaces claude-code-cost, 378 → 369 B)
How Claude Code itself loads, caches, and bills context — what is injected per dispatch, when
a skill body or nested context file gets pulled in, where subagent transcripts live, and how
to measure a session's real cost. Use when asked what a session or fan-out cost, when a rule
seems not to be loading, or before any claim about the harness.
```

---

## 3. The tool finding — this is the most valuable thing in the audit

`~/.claude/settings.json` has **no `deny` array and no `PreToolUse` hooks.** Two hooks exist (`Stop`, `PostToolUse:AskUserQuestion`). The enforcement tier is essentially unused, while prose in the per-dispatch tier is doing work the harness would do for free and unskippably.

**Six things in this plan are mechanically checkable and belong one tier up:**

1. **`claude-code-cost` is a script, not a skill.** The pipeline is fully deterministic — dedupe by `requestId`, union content blocks, max `output_tokens`, drop `<synthetic>`, drop repeat `uuid`, apply 2.0x main / 1.25x sub. `craft-skill`'s own Step 5 rule: *"deterministic or fragile work becomes exact scripts."* And §0 records what happens when a human or model executes it from prose: **~3x inflation and a 90.8% undercount.** A prose description of a pipeline is precisely the artifact that gets re-implemented wrong. → `~/.claude/tools/cc-cost.py`, invoked. Description tax: **zero.**

2. **CLAUDE.md's Boundaries block is a `permissions.ask` array.** 1,009 B of always-on prose × 41,859 dispatches enforcing: never `git push`, `gh pr create/merge/comment`, `gh issue create`, fork, clone. Those are seven glob patterns. `ask` (not `deny`) is right — it produces exactly the confirm-once gate the prose describes, at the moment of the act rather than 40 turns earlier. The *discriminator* ("publish the PR" = a prep request) is genuine judgment and stays in prose — so the paragraph shrinks, it doesn't vanish.

3. **`git-workflow`'s "cut the branch before the first edit"** → `PreToolUse` on `Edit|Write`. Its documented failure is `GH013` at push time *after the work is done*. That is the canonical too-late failure: prose fires when the model remembers, a hook fires on the first edit. Make it **ask**, not block — this user is a solo maintainer and legitimately works on main.

4. **`feedback_no_claude_coauthor_trailer` cannot be fixed by a skill at all.** It contradicts an instruction present in every context window: *"End git commit messages with: Co-Authored-By: Claude Opus 5."* A skill loads only after the model decides it's relevant; the harness instruction is always there. This has to be a `PreToolUse` matcher on `Bash(git commit:*)` — or, at minimum, CLAUDE.md. It is currently filed in **one** project silo, which means the harness default wins in every other repo.

5. **Three of `agent-dispatch`'s rules** → `PreToolUse` on `Agent`: reject a `model` parameter, run the disk preflight and block under threshold, count concurrent agents. Leaves the actual judgment (Step 0 read lists, report scrutiny) in the skill, which is what a skill is for.

6. **"Never Read the `.output` symlink"** → one `permissions.deny` glob. Absolute rule, zero exceptions, currently prose.

The `update-config` built-in skill exists for exactly this. **Caveat I cannot resolve read-only:** this profile runs `defaultMode: "auto"` with `skipAutoPermissionPrompt: true`, and I have not verified how an explicit `ask` entry interacts with those. Test one pattern live before writing seven.

---

## 4. `prebid-adcp` at user level — yes, and the plan's argument is the weaker one

The plan argues from a portability incident (`reference_verify_spec_skill_not_portable`: a project skill hardcoding `/Users/konst/projects/adcp` and a stale `3.0.0-beta.3` pin). That's real but it argues for *a* canonical copy, not for *user-level*.

The actual argument is **precedence**, and the skill states it itself at `SKILL.md:10-13`:

> "When a project skill or repo doc names a different source of truth for AdCP behavior, **this rule wins on the authority question.**"

A project skill cannot override another project skill. Only a user-level skill can sit above the project tier and adjudicate which source is authoritative. The content is not domain facts — it is a **precedence order over sources of truth**, and precedence rules must live above the things they order. Move it down a tier and it becomes one opinion among four.

The scale check confirms the need: AdCP/Prebid facts appear in **9 separate silos** (57 salesagent, 27 agentic-prebid, 4 adcp-tooling, 3 prebid-agent-skills, 3 agentic-advertising, and 4 more). Nine independent copies of a domain whose central failure mode is version drift.

**Price:** 430 B listing = 161 tok/dispatch = 0.67M units = **0.05% of corpus.** For that you get one non-drifting authority in nine places. Correct trade, easily.

Two corrections to the plan's handling:
- Its rewrite adds "or before citing an AdCP version" and the artifact triggers — **agree, ship it.** The inverted-idempotency incident is a recorded silent non-fire and an abstract-topic trigger cannot catch someone editing a handler.
- Its "expand the body 3-4×" is right and under-argued: 45 AdCP memories are stranded across those 9 silos right now, which is the drift the skill exists to prevent, already happening one tier down.

---

## 5. Aggregate cost, measured

Descriptions are not the whole listing. The built-in skills contribute **~6,014 B** to the same `msg[1]` block (measured: 4,864 B across 14 built-ins, plus ~1,150 B for `claude-api`). Your eight are 46% of what's already there.

| | user skills | + built-ins | tok @2.67 c/tok | units over 41,859 dispatches @0.10x | % of 1,376.1M corpus |
|---|---|---|---|---|---|
| today (8) | 5,059 B | 11,073 B | 4,147 | 17.4M | 1.26% |
| plan (14) | 7,518 B | 13,532 B | 5,068 | 21.2M | 1.54% |
| **delta** | **+2,459 B** | **+22%** | **+921** | **+3.86M** | **+0.28%** |

Full program: skills +0.28%, rewrites of the eight −0.11%, CLAUDE.md diet −0.54% → **net −0.37% of corpus.** §6d puts the entire efficiency program at 7.1–10.0% savings against a 2–10% unpriced cost. **This is one-twentieth of the smaller side of a program you already judged cost-neutral.** Do not sell it on cost.

**Is 14 optimal?** The tradeoff, priced:
- One more skill ≈ 400 B ≈ 150 tok/dispatch ≈ **0.63M units ≈ 0.046% of corpus** over the full corpus.
- One *wrong* body injection of a large skill (craft-prompt, 11,636 B = 4,358 tok) at main-thread cache-write 2.0x ≈ **8,716 units.**
- Break-even: a skill's whole-corpus description tax equals ~72 spurious injections — a **0.17% misfire rate.**

So neither term dominates, and both are dwarfed by one shipped defect. The conclusion is not "fewer, broader skills": broad descriptions raise the misfire rate on the wrong side of a 0.17% threshold. **Precision of the description beats parsimony of the count.** The plan optimizes the wrong variable, then reaches roughly the right answer anyway.

**My count: 13, not 14** — drop `local-env`, fold cost into `claude-code-harness`, and tighten all five new descriptions. **6,698 B (10.50M units, 0.76% corpus) vs the plan's 7,518 B (11.79M, 0.86%)** — 820 B cheaper with strictly better coverage.

---

## 6. Residue

The plan's ~67 target is met on its own terms — all 81 memories it names exist and are assigned. Of the 238 memory files, the true residue is 127, which decomposes:

- **~35 already in existing skill bodies** — `feedback_findings_need_anchors_post_as_threads`, `feedback_no_optional_disposition`, `git_mv_then_add_old_path_aborts_commit`, `reference_git_grep_ere_no_word_boundary`, `feedback_guard_matcher_completeness` etc. are already written into pr-review-method / git-workflow / testing-ci. Not stranded.
- **~20 already in CLAUDE.md** — truth-over-optimism, verify-before-asserting, no-ready-claims, no-unsafe-autofix, the plan gates. Not stranded.
- **~30 genuinely salesagent-domain** — Flask→FastAPI migration, GAM targeting, UoW detachment, ruff F821, wire envelope policy. Correctly siloed; do not promote.
- **~30 project/persona for other repos.** Correctly siloed.
- **~12–15 genuinely stranded and universal**, and they cluster on **one theme: harness mechanics.** `installed-skills-are-frozen-snapshots`, `reference_harness_freshness_mechanisms`, `crash_forensics_check_user_scope_first`, `worktree_window_helpers`, `cmux_shortcuts_cheatsheet`, plus the §6d facts (skill invocation injects the whole SKILL.md; reading one file pulls that directory's CLAUDE.md for the session; `msg[1]` is invisible to transcripts).

**That is why `claude-code-cost` should be `claude-code-harness`** — cost is one slice of a coherent cluster that is otherwise homeless, and the loading/caching mechanics are the knowledge this entire restructure depends on being correct about.

**Two cross-silo duplicate pairs worth noting**, since independent re-teaching is your strongest promote signal: `feedback_no_blockquote_for_pasteable_text` and `feedback_no_internal_dialogue_in_public_artifacts` (both salesagent + prebid-agent-skills) — the plan catches these. A third, `feedback_no_pr_specifics_in_memory`, is also duplicated across those two silos **and is already a CLAUDE.md rule** ("Memory holds cross-session patterns only — never per-PR audits"). Re-taught twice despite an always-on rule. That is evidence the always-on rule isn't firing — which is a leverage-ladder argument for a hook, not for another skill.

---

## Changes needed before this ships

1. **Delete `local-env`.** Move `docker_desktop_stale_singleton_after_crash` + `crash_forensics_check_user_scope_first` to `claude-code-harness`. Leave the other eight in the salesagent silo.
2. **Do not migrate `prek_pre_commit_replacement_bug` anywhere.** It is marked stale as of today.
3. **`claude-code-cost` → `~/.claude/tools/cc-cost.py`.** Fold the remaining harness-mechanics knowledge into `claude-code-harness`.
4. **Rewrite all five new descriptions** to remove ~625 B of mechanism narration (text above, measured).
5. **`test-authoring`:** ship the three universal rules; route the 16 KB of pytest-bdd to a project skill or an on-demand reference.
6. **`refactor-safety`:** cut `pr-review-method/SKILL.md:96-112` to a pointer in the same change, or you ship two copies.
7. **`testing-ci`:** `-k` → "a test selector" in the description; `make quality` and `tests/unit/test_architecture_*.py` generalised in the body.
8. **Open `settings.json`:** seven `permissions.ask` globs for the push/PR/issue/fork boundary, one `deny` for `.output`, `PreToolUse` on `Edit|Write` (branch check, ask-not-block), on `Agent` (model param, disk preflight), on `Bash(git commit:*)` (co-author trailer). Test one against `defaultMode: "auto"` + `skipAutoPermissionPrompt: true` before writing all of them.

## What I did not verify

I did not exercise any description against a fresh session — trigger behavior is unfalsifiable from inside the authoring session, and it is the correct gate before any of this lands. I did not test whether `permissions.ask` overrides `auto` mode on this profile; that is a one-command check and it gates finding #8. The built-in listing figure (~6,014 B) is transcribed from this session's own prompt with `claude-api` estimated, so the "+22% listing growth" figure carries roughly ±5%. Read-only throughout — nothing written outside the scratchpad.