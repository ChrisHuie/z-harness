# `~/.claude/CLAUDE.md` — the assembly. NOT APPLIED.

> **APPLIED 2026-08-02.** The live file carries §A, every §B row, §C's absentees, and §D's
> surviving cuts; §E's diet remainder stayed open (file shipped at 219 lines). The header
> above is historical.

Live file: 10,368 B, mtime Aug 1 21:35. Untouched.
Revert point: `PREINSTALL-20260802-085154/CLAUDE.md`.

Everything below is proposed. Sources are the built skills' `references/claude-md-lines.md`,
the registry (`PRINCIPLE-REGISTRY.md`, `REGISTRY-GAP-R310.md`), and the diet
(`reports/report-diet.md` §2).

---

## A. The amendment that unblocks two skills — `CLAUDE.md:107`

**Current (live):**
> PR scope is a contract; a change touching 3+ source files is its own PR.

**Problem — three-way, verified by two independent builders.** `git-workflow`'s R145 ("land a
breaking constraint and every caller and fixture fix in one commit") and `pr-review-method`'s
R021 ("fix every instance in one commit") both instruct the act `:107` forbids whenever N≥3.
`git-workflow`'s body now reads *"scope is whether the change completes its principal, not a
file count"* — **deliberately inconsistent with the live line.** If `:107` is not amended,
always-on wins and both bodies contradict it.

**Replacement — this wording existed only in conversation until now; it is the dependency both
builders wrote against:**

> PR scope is a contract: the test is whether the expansion completes the principal change and
> leaves it intact, not how many files it touches. A breaking constraint and every caller it
> breaks, or one defect and its N-1 twins, ship in one commit — that is completing the
> principal. Unrelated work found along the way is its own PR at any size.

---

## B. Additions — with the reason each must be always-on rather than in a skill

Gate 2 (ARRIVAL) is the test: needed before the first tool call · no cue will appear · a
consumer is skill-blind. **Not** cost — a body fired at turn 1 costs 96–98% of the same bytes
always-on.

| # | rule | why always-on |
|---|---|---|
| **R317** | No `Co-Authored-By: Claude` trailer on commits | **Counteracts a live always-on harness default** — this session's own system prompt instructs the opposite. A skill firing on a git cue arrives *after* the default is obeyed, and the artifact is an irreversible public commit under the user's name. Gate 2 strengthener. |
| **R006** | Evidence ladder: installed artifact → normative repo → source → never the README | Rerouted out of `prebid-adcp` as non-AdCP. **Currently written nowhere** — verified absent from the live file and from every additions draft. Lost unless written here. |
| git-1 | `git grep -E` has no `\b`; use `-P` | 208 broken vs 185 correct calls. **Keep until a hook that can go red is live** — the identifiable hook fails Gate 1 T4/T5 and ships warn-only. |
| git-2 | Cut the branch before the first edit | Must hold before the first `Write`; a skill fires at turn 1 of the agent, too late. 3,323 of 6,133 edit calls (54.1%) ran on `main`/`master`. |
| git-3 | No alarm narrative mid-operation | Trigger is not git-shaped, so no git cue reaches it. |
| mach-1 | `timeout` is not installed on this machine | Needed unprompted in every project directory. Was being pasted into agent briefs by hand all session. |
| mach-2 | Docker stale-Electron-singleton signature | **Amend the existing `:51-52` bullet in place** — the `rm Singleton{Cookie,Lock,Socket}` fix is already there. Add: launch exits 0 spawning no process; `unmarshaling start request: unexpected EOF`; deleting `backend.lock` does NOT fix it. |
| mach-3 | System Python fails TLS verification | A cert error from `/usr/bin/python3` is an instrument failure, not a remote one. Belongs under Claims and evidence, not dispatch. |
| R005 | No issue/PR refs in code comments; no comment restating code | The two rules `route.py` misfiled into `authoring-artifacts`. Disjoint cue class from outbound prose — they fire while writing *code*. |
| R319 | Register matches the domain | Rewrites `:20`, net +1 line. |
| **routing** | **The imperative skill-routing directive** | The precondition for every skill above. Measured: no-directive 3/28 vs directive 14/14, `p = 1.29e-08`. Without it the 11 bodies fire ~10% of the time and this whole migration reduces reachability. |

## C. Session-workflow clauses that are NOT superseded — 5 of 9

Verified by reading the live file, correcting both the extraction doc and my own brief (which
listed W1 and W7 as absent; W1 is at `:122`, W7 largely at `:93-94`).

Genuinely absent, **including the named worst case**:
- **W3 — verification authority lives outside the model**
- W4, W6, M4, M5

Plus from `feedback_verify_before_asserting`, 1 of 4 absent: *read the WHOLE file, not the diff
hunk.*
Plus from `feedback_thoroughness_over_momentum`: *the bar rises after the first surprise*
(same principle as S#113, merged at R310), and the momentum/sunk-cost bias, missing from R011's six.

## D. Cuts — from the diet, minus the one it got wrong

`report-diet.md` §2 proposes 178 → 100 lines. **All cuts stand except the routing table.**
Measured: the passive table was present in *every* arm of the firing experiment, including both
1/5 arms. It is insufficient — but no arm ever ran imperative-without-table, so "cut it" is
unsupported. **Replace it with the imperative directive; do not delete it outright.**

Duplicate cuts that stand: `make quality` / `./run_all_tests.sh` (project-specific and wrong
in most projects this file loads into).

**Corrected 2026-08-02 — two claims in this paragraph were wrong.**

- **`git log @{u}..HEAD` — the "now in the `git-workflow` body" justification is FALSE.**
  `grep '@{u}' drafts/final/*/SKILL.md` returns zero hits. Its only occurrence in the skill
  tree is `git-workflow/references/deferred.md:86`, in a list headed *"Deliberately absent —
  already always-on in `~/.claude/CLAUDE.md`"*: the body omitted it **because** CLAUDE.md
  carried it, and this document proposed cutting it from CLAUDE.md **because** the body
  carried it. Circular eviction. **The line is not cut** — it is at
  `drafts/final/CLAUDE.md:92` and stays there. Do not re-cut it on this reasoning.
- **`/code-review ultra` — "in the harness system prompt" is UNVERIFIED, not verified.** The
  command listing available in the session that checked (`init`, `review`, `security-review`,
  `run`, `loop`, `schedule`, `simplify`, …) contains no `code-review` entry. Same claim shape
  as the one that failed above. Establish it against an actual system prompt capture before
  the cut is made.

---

## E. The arithmetic problem — unresolved

**Additions ≈ 22 lines / +18%. The diet cuts 78 lines / −45%.** Both cannot be described as
"the plan" without saying which wins. Net is a cut, but the additions are load-bearing:
`R317` and `R006` have no other home, and the routing directive is the precondition for
everything else.

**Not yet done:** no line-by-line assembly of the final file, no byte measurement of the
result, and no check that the additions survive the diet's own rewrite of the sections they
land in.
