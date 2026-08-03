> **RETIRED 2026-08-02 — every proposal below is APPLIED.** Blocks 1–3 and the §Dependency
> amendment are live in `~/.claude/CLAUDE.md`; the `git grep -E` hook shipped as a deny
> guard (`hooks/guards/git_grep_engine_guard.py`, T4/T5 established by its fixture corpus),
> superseding the warn-only verdict below. Block 1's delete-once-live instruction was
> overruled with the reason recorded: the hook fires at command time, after composition —
> the one-line always-on hint pre-empts the denied-call round trip. Derivation record only;
> nothing here is pending.

# Proposed `~/.claude/CLAUDE.md` lines and hook specs

**Not applied. `~/.claude/CLAUDE.md` was NOT edited by this pass.** Carried forward from
`drafts/git/CLAUDE-md-additions.md`, with block 2 shortened to remove an R2 duplicate
against the final body, and the byte accounting recomputed against the 5,000 B body.

Three rules. Each earns always-on placement on one test: **its trigger occurs mostly in
units where the narrowed `git-workflow` skill will NOT fire.** Coverage measured by the
original pass over 2,565 transcript units in `~/.claude/projects/**` (634 main-thread,
1,931 subagent, including the 417 nested at `<session>/subagents/workflows/wf_*/`). Those
unit and firing counts are the earlier pass's measurements, carried forward, not
re-measured here; the byte figures below are re-derived from them.

Insertion points are anchored on lines present in the live file as read on 2026-08-02
(10,368 B, 179 lines).

---

## 1 — append to `## Verification`, after the "Verify with the SAME instrument" paragraph

**Trigger:** `git grep` runs in 681/2,565 units (26.5%); the narrowed skill covers only
21.3% of them. Across 5,629 `git grep` calls the broken form outnumbers the correct one
**208 to 185**.

```markdown
**`git grep -E` silently ignores `\b`** — no error, and an alternation still returns some
hits, so it reads as fine. Use `-P`.
```

**129 B.** Delete this line once the `git grep -E` hook is live (below).

This is registry **R001**, and it is the reason the final body carries no grep rule at all.
Until this line lands, the rule is delivered by nothing — the narrowed description drops the
``git grep -P` vs `-E`` cue the installed one advertises.

## 2 — insert in `## Permission boundaries`, after "Local git (commit, rebase, stash, deleting local-only branches) is pre-authorized."

**Trigger:** an Edit/Write in a repo — 390/2,565 units (15.2%), of which the narrowed skill
covers 45.4%. It also fires too late by construction: the rule must hold *before* the first
edit, which is before any git command exists for a skill to trigger on. **3,323 of 6,133
Edit/Write calls (54.1%) landed while `gitBranch` was `main`/`master`.**

```markdown
**Cut `feature/<slug>` with `--no-track origin/main` before the first edit, not after.**
Editing on main surfaces as `GH013` at push time, when the work is already done.
```

**170 B**, down from the draft's 231 B. **Changed from the draft:** the trailing clause
*"without `--no-track` the push resolves to `refs/heads/main`"* is deleted. The final body's
first Branches bullet carries that mechanism plus its remedy (`git branch --unset-upstream`)
and the dirty-tree recovery, so keeping it here is an R2 duplicate paid on every dispatch.
CLAUDE.md keeps the timing (which a skill cannot deliver in time); the body keeps the
mechanism (which it can). Registry **R002**.

## 3 — extend the existing banned-words sentence in `## Claims and evidence`

**Trigger:** not git-shaped — the rule covers any in-flight git/hook/build/test operation,
so no skill description can reach it. `pre-commit` runs in 41 units, of which the narrowed
skill covers 14.6%. Alarm phrasing appears in assistant text in 46 units (1.8%).

Replace CLAUDE.md:90-91:

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

**Net +166 B.** Registry **R003**.

**Block 3 loses the byte argument on its own:** 166 B × 2,565 = 426 KB always-on, against
~35 skill-uncovered `pre-commit` units × 5,000 B = 175 KB if it stayed in the body. It is
kept on damage, not frequency — the failure is a user-facing panic narrative about state
that was never at risk, and its trigger is not git-shaped, so no skill description reaches
it. **This is the first of the three to cut if always-on bytes get tight.**

---

## Byte accounting

| Block | Bytes |
|---|---|
| 1. `git grep -P` | 129 |
| 2. branch before the first edit | 170 |
| 3. mid-operation alarm words | +166 net |
| **Added to `CLAUDE.md`** | **467** (incl. 2 B blank-line separators) |

`CLAUDE.md`: 10,368 B → **10,835 B (+4.5%)**.

Paid for in the same edit: the description drops **443 B → 256 B (−187 B)**, and a skill
description is always-on in the skills listing on exactly the same footing as `CLAUDE.md`.
**Net always-on: +280 B, i.e. +2.6% on the 10,811 B `CLAUDE.md`-plus-description surface.**

### Corpus-scale — two regimes, because the body does not ship at the trigger rate

`git-workflow` has existed since 2026-08-01. In that window: **222 units, 126 with a git/gh
call (56.8%), and 12 that actually loaded the skill** — `attributionSkill:"git-workflow"`,
corroborated by 14 `Skill` tool calls. **Capture = 9.5% of trigger-units.** The description
is always-on; the body ships only on a `Skill` call. So 57.9% is the rate at which the body
*would be useful*, not the rate at which it arrives.

Installed baseline, re-measured 2026-08-02: description **443 B**, body **2,893 B**.
Proposed: description **256 B**, body **5,000 B**, always-on **723 B** (256 + 467).

**Regime A — today, no mandatory routing directive (capture 9.5%):**

| | always-on × 2,565 | firings | body × firings | total |
|---|---|---|---|---|
| today | 443 B → 1.14 MB | 141 | 2,893 B → 0.41 MB | **1.54 MB** |
| proposed | 723 B → 1.85 MB | 28 | 5,000 B → 0.14 MB | **1.99 MB** |

**+29%** (the draft's figure was +39%, before block 2 shrank and the body was capped). That
is the honest price. In this regime the body is nearly free *because it is nearly dead* — a
rule parked there is delivered on 9.5% of the occasions it applies. The 467 B buys three
rules moving from 9.5% to 100% delivery.

**Regime B — after the mandatory routing directive lands (`PLAN.md` §7 step 0; measured 5/5
vs 2/10, Fisher p = 0.0070), capture → ~100%:**

| | always-on × 2,565 | firings | body × firings | total |
|---|---|---|---|---|
| today | 443 B → 1.14 MB | 1,485 (57.9%) | 2,893 B → 4.30 MB | **5.43 MB** |
| proposed | 723 B → 1.85 MB | 300 (11.7%) | 5,000 B → 1.50 MB | **3.35 MB** |

**−38%, while the body grows 73%.** The saving is entirely in the trigger: today's
description would deliver the body to 1,240 units (48.3%) that ran only read-only git and
had exactly one applicable rule in it — the grep rule, which block 1 moves out.

**The narrowing is a hedge that pays in B and costs ~0.45 MB in A. The `CLAUDE.md` and hook
moves pay in both**, because delivery, not bytes, is what they buy.

---

## Hook specs

The draft asserted "hooks take four more to 100% at zero bytes" but **specified none of the
four**. Only one hook is concretely identified anywhere in the draft, and it is the only one
carried forward. The other three are an unbacked claim — do not build against it.

### `git grep -E` PreToolUse hook (retires block 1)

A `PreToolUse` matcher on `Bash` that rejects a command containing `git grep` with `-E` (or
no engine flag) **and** a `\b`, `\d`, `\s`, `\w` or `\+` in the pattern, telling the caller
to use `-P`.

Against `ROUTING-RULE.md` Gate 1, on the evidence the draft actually recorded:

| test | status |
|---|---|
| T1 verdict from bytes, no intent judgment | **YES** — it is a flag-and-pattern test on argv. |
| T2 input not chosen by the checked party | **YES** — the hook reads the command being run, not a pattern the agent supplies to a sweep. |
| T3 violated ≥2× with the rule in force | **YES** — 208 broken vs 185 correct across 5,629 `git grep` calls. |
| T4 name the wrong artifact produced | **NOT ESTABLISHED** — the draft records the miscount rate, not a specific wrong artifact it shipped. Gate 1 requires all five; this one is missing. |
| T5 false-red affordable | **NOT ESTIMATED** — precision against legitimate POSIX-ERE uses was never measured. |

**Verdict: not shippable as a verdict hook on the recorded evidence.** Under T5's own
fallback it ships as a **worklist that always exits 0** — warn on stderr, never block —
until T4 and T5 are established. Do not delete block 1 from `CLAUDE.md` until a hook that
can go red is live; a hook that cannot go red certifies failure as success
(`ROUTING-RULE.md` SHIP GATE, 12 of 13 shipped detectors were false-greens).

---

## Dependency — one open contradiction

The body's Commit shape rule says **"Scope is whether the change completes its principal,
not a file count."** That is deliberately inconsistent with the live `~/.claude/CLAUDE.md`
line 107: *"PR scope is a contract; a change touching 3+ source files is its own PR."*

Registry **R145** (land a breaking constraint and every caller and fixture fix in ONE
commit) is unimplementable under a 3-file cap: a type narrowing typically breaks more than
three callers. The body is written against the replacement wording proposed by the
`pr-review-method` builder — scope judged by whether the change completes its principal.

**If `:107` is not amended, the body contradicts always-on text and always-on wins.** The
`git-workflow` body cannot resolve this itself; the amendment has to land in `CLAUDE.md`.
This pass did not verify the exact replacement wording — no file under
`drafts/final/pr-review-method/` contains it, and the collision is only recorded in the
registry's notes. Confirm the wording with that builder before applying either change.
