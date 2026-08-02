# `~/.claude/CLAUDE.md` — exact lines to add

Three rules. Each earns always-on placement on one test: **its trigger occurs mostly in
units where the narrowed `git-workflow` skill will NOT fire.** Coverage measured over 2,565
transcript units in `~/.claude/projects/**` (634 main-thread, 1,931 subagent, including the
417 nested at `<session>/subagents/workflows/wf_*/`).

Everything else goes to the skill body or a hook. Insertion points are anchored on lines
already in the file.

---

## 1 — append to `## Verification`, after the "Verify with the SAME instrument" paragraph

**Trigger:** `git grep` runs in 681/2,565 units (26.5%); the narrowed skill covers only
21.3% of them. Across 5,629 `git grep` calls the broken form outnumbers the correct one
**208 to 185**.

```markdown
**`git grep -E` silently ignores `\b`** — no error, and an alternation still returns some
hits, so it reads as fine. Use `-P`.
```

**129 B.** Delete this line once the `git grep -E` hook is live.

---

## 2 — insert in `## Permission boundaries`, after "Local git (commit, rebase, stash, deleting local-only branches) is pre-authorized."

**Trigger:** an Edit/Write in a repo — 390/2,565 units (15.2%), of which the narrowed skill
covers 45.4%. It also fires too late by construction: the rule must hold *before* the first
edit, which is before any git command exists for a skill to trigger on.
**3,323 of 6,133 Edit/Write calls (54.1%) landed while `gitBranch` was `main`/`master`.**

```markdown
**Cut `feature/<slug>` with `--no-track origin/main` before the first edit, not after.**
Editing on main surfaces as `GH013` at push time, when the work is already done; without
`--no-track` the push resolves to `refs/heads/main`.
```

**231 B.**

---

## 3 — extend the existing banned-words sentence in `## Claims and evidence`

**Trigger:** not git-shaped — the rule covers any in-flight git/hook/build/test operation,
so no skill description can reach it. `pre-commit` runs in 41 units, of which the narrowed
skill covers 14.6%. Alarm phrasing appears in assistant text in 46 units (1.8%).

Replace:

```markdown
**A wrong claim is 100% fail regardless of speed or framing.** Banned: *ready, clean,
verified, looks good, should work, all set, solid, perfect, done*.
```

with:

```markdown
**A wrong claim is 100% fail regardless of speed or framing.** Banned: *ready, clean,
verified, looks good, should work, all set, solid, perfect, done* — and, while any
git/hook/build op is still in flight, *reverted, lost, gone, broke*: pre-commit stashes
unstaged changes, so a mid-run `Read` returns HEAD content.
```

**net +166 B.**

---

## Byte accounting

| Block | Bytes |
|---|---|
| 1. `git grep -P` | 129 |
| 2. branch before the first edit | 231 |
| 3. mid-operation alarm words | +166 net |
| **Added to `CLAUDE.md`** | **528** (incl. 2 B blank-line separators) |

`CLAUDE.md`: 10,368 B → **10,896 B (+5.1%)**.

Paid for in the same edit: the `git-workflow` description drops **443 B → 256 B (−187 B)**,
and a skill description is always-on in the skills listing on exactly the same footing as
`CLAUDE.md`. **Net always-on: +341 B, i.e. +3.2% on the 10,811 B `CLAUDE.md`-plus-description surface.**

### Corpus-scale — two regimes, because the body does not ship at the trigger rate

`git-workflow` has existed since 2026-08-01. In that window: **222 units, 126 with a git/gh
call (56.8%), and 12 that actually loaded the skill** — `attributionSkill:"git-workflow"`,
corroborated by 14 `Skill` tool calls. **Capture = 9.5% of trigger-units.** The description
is always-on; the body ships only on a `Skill` call. So the 57.9% figure is the rate at
which the body *would be useful*, not the rate at which it arrives.

**Regime A — today, no mandatory routing directive (capture 9.5%):**

| | always-on × 2,565 | firings | body × firings | total |
|---|---|---|---|---|
| today | 443 B → 1.14 MB | 141 | 2,894 B → 0.41 MB | **1.55 MB** |
| proposed | 784 B → 2.01 MB | 28 | 5,107 B → 0.14 MB | **2.15 MB** |

**+39%.** That is the honest price. In this regime the body is nearly free *because it is
nearly dead* — a rule parked there is delivered on 9.5% of the occasions it applies. The
528 B buys three rules moving from 9.5% to 100% delivery, and hooks take four more to 100%
at zero bytes.

**Regime B — after the mandatory routing directive lands (`PLAN.md` §7 step 0; measured
5/5 vs 2/10, Fisher p = 0.0070), capture → ~100%:**

| | always-on × 2,565 | firings | body × firings | total |
|---|---|---|---|---|
| today | 443 B → 1.14 MB | 1,485 (57.9%) | 2,894 B → 4.30 MB | **5.43 MB** |
| proposed | 784 B → 2.01 MB | 300 (11.7%) | 5,107 B → 1.53 MB | **3.54 MB** |

**−35%, while the body grows 76%.** The saving is entirely in the trigger: today's
description would deliver the body to 1,240 units (48.3%) that ran only read-only git and
had exactly one applicable rule in it — the grep rule, which this file moves out.

**The narrowing is a hedge that pays in B and costs ~0.6 MB in A. The `CLAUDE.md` and hook
moves pay in both**, because delivery, not bytes, is what they buy.

---

## What block 3 does not clear

Block 3 loses the byte argument on its own: 166 B × 2,565 = 426 KB always-on, against ~35
skill-uncovered `pre-commit` units × 5,107 B = 179 KB if it stayed in the body. It is kept
on damage, not frequency — the failure is a user-facing panic narrative about state that
was never at risk, and its trigger is not git-shaped, so no skill description reaches it.
**This is the first of the three to cut if always-on bytes get tight.**
