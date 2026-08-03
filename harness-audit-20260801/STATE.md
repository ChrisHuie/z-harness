# Harness state — 2026-08-02, end of build

**Read this first.** `PLAN.md` is the PRE-execution plan and is stale in places; where the two
disagree, this file wins. Full evidence: `EXP-skill-delivery.md` (Parts 1–12). Forward-looking
procedure: `ROUTING-RULE.md`. Why claims kept reversing: `INVERSIONS.md`.

---

## Installed and verified

| | state |
|---|---|
| `~/.claude/skills/` | **11 skills** — 8 rewritten, 3 new (`agent-dispatch`, `outbound-drafts`, `system-design`) |
| `~/.claude/CLAUDE.md` | 13,430 B / 219 lines |
| `~/.claude/settings.json` | `PreToolUse` + `PostToolUse` + `Stop` registered; `permissions.ask` **removed** |
| `~/.claude/hooks/` | `bash_command_guard.py`, `askq_timeout_guard.py`, `harness_report.py` (+ inert `stop_hook.sh`, dead `question_timeout_guard.sh` — **both deleted 2026-08-03**, preserved in git history and `PREHOOKS-*`; `harness_check.py`, `spawn_preflight_guard.py`, `harness_health.sh` added) |
| memory | **242 files, 23 silos, nothing deleted.** Indexes cut 49,889 → 29,335 B (−41%) |

**Verified from a fresh temp dir with no repo and no project `CLAUDE.md`:** the user file
arrives verbatim in `msg[0]`, the imperative routing table with it, and **11/11 skill
descriptions in `msg[1]`**. The harness loads at user level regardless of directory. Hooks too.

## The five facts that took two days to establish

1. **Skills do not fire unprompted in embedded work** — 3/28. An imperative paragraph in
   `~/.claude/CLAUDE.md` takes it to 14/14, **Fisher p = 1.29e-08**, replicated at the
   permutation floor.
2. **Nothing decays within a session.** A fired body and the always-on file sit in the same
   message array; a body still governed the work at turn 18 with `Skill` blocked. Routing fires
   per topic at any depth measured (turn 22, 270K context).
3. **Compaction is the only real failure.** A body is annihilated — **0 of 19 rules**. The
   always-on file survives and re-fires the skill through a summary that claims it already
   loaded. The paragraph earns its place on **turn-1 firing** (LIVE 4/4 vs FLOOR 2/4), not on
   post-compaction recovery.
4. **The user-level `CLAUDE.md` is read at session start, NOT on file change.** Editing it does
   not reach a running session. Project-level files DO refresh per dispatch — that difference
   caused a wrong conclusion for hours.
5. **A `tools:` allowlist omitting `Skill` strips both the tool and the listing.** All 10
   salesagent lenses do this; skills are invisible there. Measured decision: **do not add
   `Skill`** — the overlap with their charter is 18 of 25 and the skill never fires anyway
   (`LENS-DECISION.md`).

## Open — in the order I would take them

1. **Re-run `python3 ~/.claude/hooks/harness_report.py --since 7d`.** Day-one baseline is
   `baselines/20260802-day1.txt`. The number that decides something: **`references/` opened
   after a fire = 0 of 57.** If it is still 0 in a week *with the condition met*, that tier is
   decorative and its ~55 KB belongs back in memories. Do not act on one day.
2. **`pr-review-method` over-fires — 137%** (11 fires, 8 PR-endpoint contexts). Likely matching
   talk about review rather than review. Tighten the description if it persists.
3. **`craft-skill` fired 0 times across 11 contexts that authored a `SKILL.md`.** Real routing
   gap, found on day one.
4. **6 rules to port into salesagent's `review-charter.md`** — prepared, not applied, gated repo
   (`LENS-DECISION.md`). Rule 1 is the named shape of a real miss.
5. **Left alone deliberately:** `stop_hook.sh` (inert, has a confirmed false-green at line 102);
   the four `craft-*` bodies (7.5–12.5 KB, over cap before this work began); untested cells
   (other skills under compaction, subagent multi-turn, whether a reloaded body changes output).

## Revert

> **Amended 2026-08-02 (post-git):** `~/.claude` is now a clone of `ChrisHuie/z-harness` —
> git history is the primary revert net (baseline tag `pre-remediation-20260802`). The
> tables below are the pre-git nets.

Nothing was destroyed. These are the pre-git nets:

| backup | covers |
|---|---|
| `PREINSTALL-20260802-085154` (339 files) | skills, `CLAUDE.md`, `settings.json`, hooks, all memory — pre-install |
| `PREHOOKS-20260802-154226` | hooks + `settings.json` before the hook install |
| `PREMEM-20260802-154631` (256 files) | every `MEMORY.md` before the index work |
| `PRE-MIGRATION-BACKUP` (257 files) | the original memory tree |

## Health check — all four must exit 0

```
python3 ~/.claude/hooks/bash_command_guard.py --selftest
python3 ~/.claude/hooks/askq_timeout_guard.py --selftest
python3 ~/.claude/hooks/askq_timeout_guard.py --verify-harness
python3 ~/.claude/hooks/harness_report.py --selftest
```

`--verify-harness` is the one that matters after a CLI upgrade: it re-checks the guard's own
premise against the binary it guards, and exits 1 saying *"a critical anchor is gone"* rather
than passing blind.

## The discipline that produced the durable half

**Twelve of my claims reversed across two days.** Every survivor was measured on the wire or by
direct execution; every reversal came from relaying a number instead of reproducing it. The
last one was this project's own measurement tool matching *mentions* instead of *actions* — the
exact trap it was built to detect. Assume the next one is live and un-caught.
