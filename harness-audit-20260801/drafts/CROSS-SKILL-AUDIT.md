# Cross-skill audit — 11 bodies, 7 references, 2 versions of the always-on file

Read-only pass. Nothing modified except this file.

## What was audited, and the version problem

| artifact | version audited |
|---|---|
| 11 `SKILL.md` bodies | `drafts/final/*/SKILL.md`, mtimes Aug 2 09:24–09:55 |
| 7 `references/*.md` | same tree |
| live always-on | `~/.claude/CLAUDE.md`, 178 lines, unchanged throughout |
| **candidate always-on** | **`drafts/final/CLAUDE.md`, md5 `b5ac0bf51aae4fd6a52607edaac9bbcf`, 11,596 B, mtime Aug 2 10:04** |

**The candidate is a moving target.** It did not exist when this audit began (first `ls` of
`drafts/final/` at 09:5x returned 11 directories and no file). It appeared at 10:01 and was
rewritten again at 10:04 by another agent while I was reading it. Two findings below
(F14) were true of the 10:01 version and were fixed in the 10:04 version *during* the audit.
**Every candidate-side finding must be re-verified against whatever is actually applied.**

All 8 previously-installed skills differ from their `drafts/final` counterparts — none of
this set is applied yet.

---

# S1 — Breaks a body

## F1. The evidence ladder is INVERTED against `prebid-adcp`'s entire thesis

- `drafts/final/CLAUDE.md:110-112` — "**Evidence ladder for any external system — a lower
  tier never overrules a higher one:** the locally installed artifact (introspect it) → the
  normative repository (MUST vs SHOULD) → the implementation source → …"
- `drafts/final/prebid-adcp/SKILL.md:25-29` — "## What is authoritative / 1. **Spec prose +
  the graded conformance storyboard** for the pinned version. / 2. **The installed artifact**
  — introspect it. / 3. **Source.**"
- `drafts/final/prebid-adcp/SKILL.md:3` (description) — "…SDK types, error codes and
  reference implementations as a read-only cross-check, **never the authority**."
- `drafts/final/prebid-adcp/SKILL.md:31` — "**The SDK is a read-only cross-check that can
  diverge**."

**What breaks.** The two ladders rank tiers 1 and 2 in opposite order, and the always-on line
adds "a lower tier never overrules a higher one" — a precedence clause that makes the conflict
unresolvable rather than merely ambiguous. On the question `prebid-adcp` exists to answer —
*the installed wheel says X, the spec prose says Y* — always-on says the wheel wins and the
skill says the spec wins. Always-on wins. `drafts/final/CLAUDE.md:13` mandates loading
`prebid-adcp` on exactly these turns, so the two always co-arrive.

**Provenance.** `CLAUDE-MD-ASSEMBLY.md:43` justifies adding R006 as "Rerouted out of
`prebid-adcp` as non-AdCP. **Currently written nowhere** — verified absent from the live file
and from every additions draft." That verification did not check `prebid-adcp`'s own body,
which carries the AdCP-scoped form at `:25-29`. The reroute produced an inverted second copy.

**Minimal fix.** Scope the always-on line so it cannot outrank a spec: "…for any external
system **whose normative text you do not have**". Or re-order it to
`normative text → installed artifact → source` and let `prebid-adcp:25-29` specialize it.
Do not ship both orderings.

## F2. `pr-review-method` instructs the act the permission boundary bans

- `drafts/final/pr-review-method/SKILL.md:61` — "**Anchor every finding to `path:line` and
  post as inline threads.**"
- `drafts/final/pr-review-method/SKILL.md:66` — "Post as `COMMENT`; verify they landed."
- `drafts/final/CLAUDE.md:31-33` — "**Never on my own initiative:** `git push`,
  `gh pr create/merge/comment`, `gh issue create`, forking or cloning a repo. **Prepare the
  artifact and stop.**" (live `~/.claude/CLAUDE.md:73-75`, identical in force)

**What breaks.** Both are unconditional imperatives about the same act.
`drafts/final/CLAUDE.md:10` mandates loading `pr-review-method` for "reviewing a PR", so the
co-load is guaranteed, not incidental. The body never gates on an explicit user imperative;
"or post findings" appears only in the description (`:3`), which is routing text, not a gate.
The builder knew the boundary — `pr-review-method/references/deferred.md:97-99` cites the
same always-on line for the never-push half — so this is an omission in the body, not a
disagreement.

**Minimal fix.** One clause at `:61`: "**When Chris has asked you to post**, anchor every
finding to `path:line` and post as inline threads; otherwise emit the thread payloads for
him to post."

## F3. The cost-measurement section is evicted with no home anywhere

- Live `~/.claude/CLAUDE.md:128-146` — "## Measuring Claude Code cost — four traps, verified
  universal" (19 lines: the `requestId` dedupe, the `<session-id>/subagents/` path, empty
  `thinking`, max-`output_tokens`, the pipeline, and the `ephemeral_1h`/`ephemeral_5m`/cache-
  read/output multipliers).
- Absent from `drafts/final/CLAUDE.md` at both 10:01 and 10:04.
- Verified absent from **all 11 bodies and all 7 reference files**: `requestId`,
  `output_tokens`, `ephemeral`, `chars/token`, `synthetic` each return 0 matches across
  `*/SKILL.md` and `*/references/*.md`.
- The project memory index (`~/.claude/projects/.../memory/MEMORY.md`) points *at* CLAUDE.md
  for these: "Universal facts from the 2026-08-01 harness audit were moved to
  ~/.claude/CLAUDE.md — they are not project-scoped."

**What breaks.** Largest single eviction in the candidate, and the only channel that would
still carry it is `harness-audit-20260801/FINDINGS.md`, which nothing loads. `CLAUDE-MD-
ASSEMBLY.md` §D enumerates the cuts it sanctions (`/code-review ultra`, `make quality`,
`git log @{u}..HEAD`) and **does not mention this section at all** — so this is an
unrecorded cut, not a decided one. The four traps are the ones that produce 3x, 90.8% and
56–85% errors when forgotten; they are pure recall content with no cue that would summon a
skill.

**Minimal fix.** Either keep a ≤3-line always-on residue (dedupe by `requestId`, take max
`output_tokens`, subagents live one level down) pointing at `FINDINGS.md`, or create the
home first and cite it. Do not cut it silently.

---

# S2 — Contradictions, narrower scope

## F4. Two incompatible PR-comment shapes, and both skills fire on the same turn

- `drafts/final/pr-review-method/SKILL.md:61-63` — "post as inline threads. **A paragraph in
  one PR-level comment has no lifecycle and drops out unaddressed and undeclined.**"
- `drafts/final/outbound-drafts/SKILL.md:68` — "**One comment per PR, edited in place across
  rounds** — never a new one each round."

One says N inline threads and names the single PR-level comment as the failure mode; the
other says exactly one comment per PR. **Both descriptions carry `post` in their positive
half** (`pr-review-method:3` "or post findings"; `outbound-drafts:3` "something to post or
send"), so a turn like *"write up my review findings to post"* loads both. Neither body
carries the reconciling clause (inline threads for findings **plus** one tracking comment for
the roll-up).

**Provenance.** `pr-review-method/references/deferred.md:137` lists registry **R063** "one
tracking comment edited in place, with the head SHA" as displaced rank B/C — the
`pr-review-method` builder ruled it OUT of the body; the `outbound-drafts` builder put it IN
as an unqualified rule. Same registry row, two skills, incompatible framings.

**Minimal fix.** In `outbound-drafts:68`, scope it: "One **tracking/roll-up** comment per PR,
edited in place across rounds — individual findings are inline threads (`pr-review-method`)."

## F5. Four closed output contracts vs "Close with what was not tested"

- `drafts/final/CLAUDE.md:161` (live `:126`) — "Close with what was **not** tested."
- `craft-prompt/SKILL.md:12` — "the output ends with Verify's last check … **no trailing
  notes**"; `## Verify` is defined at `:84` as "2–3 concrete checks: specific input → expected
  observable behavior" — forward-looking, not a not-tested list.
- Same shape in `craft-skill/SKILL.md:12`, `craft-context-file/SKILL.md:12`,
  `review-prompt/SKILL.md:12`.

`review-prompt`'s `## Checked` and the two `## Validation` sections do carry scope-of-what-ran
and so substantially satisfy the always-on rule. **`craft-prompt` does not** — it has no slot
for a not-tested statement and explicitly forbids adding one. Always-on loads on every
dispatch; a literal-following model cannot satisfy both.

**Minimal fix.** One clause in `craft-prompt:84`: "`## Verify` — 2–3 concrete checks … and one
line naming what the prompt was **not** exercised against."

## F6. "Content migrates down the ladder, never up" contradicts the memory rule and inverts the routing ladder

- `craft-context-file/SKILL.md:36` — "always-on rule → this file; on-demand knowledge or
  workflow → a skill; **must-happen-every-time → a hook** … **Content migrates down the
  ladder, never up.**"
- `drafts/final/CLAUDE.md:173` (live `:172-174`) — "**Universal facts go HERE**" — an
  explicit instruction to move a fact *up* out of a project silo.
- `ROUTING-RULE.md:3` — "Five destinations, **strongest first: TOOL → CLAUDE.md → SKILL →
  repo → MEMORY**", with Gate 1 (TOOL) run *before* Gate 2 (CLAUDE.md) and Gate 3 (SKILL).

Two defects in one line. (a) On a "prune our CLAUDE.md" turn — the exact turn
`craft-context-file` owns — always-on says pull universal facts up into the file and the body
says content never moves up. (b) `craft-context-file` places hooks **below** skills while
`ROUTING-RULE` places TOOL **above everything**; routing a must-happen-every-time rule to a
hook is a demotion in one frame and a promotion in the other, so "never up" is unevaluable.

**Minimal fix.** Replace with "Content moves to the channel the routing gates select; it never
moves to a *weaker* channel to make the budget close." State the ladder in `ROUTING-RULE`'s
order.

## F7. Two live description caps differ by 2.6x, and 5 of 11 descriptions violate the tighter one

- `craft-skill/SKILL.md:38` and `:54` (row 16) — "**≤1024 chars**".
- `ROUTING-RULE.md:99` — "the description fits in **≤400 chars** of **user-sayable text**".

Measured character counts of the 11 descriptions:

| skill | chars | vs 400 |
|---|---|---|
| `craft-context-file` | 964 | **over** |
| `craft-skill` | 762 | **over** |
| `review-prompt` | 758 | **over** |
| `craft-prompt` | 624 | **over** |
| `outbound-drafts` | 417 | **over** |
| `prebid-adcp` | 389 | ok |
| `testing-ci` | 367 | ok |
| `pr-review-method` | 366 | ok |
| `system-design` | 359 | ok |
| `agent-dispatch` | 340 | ok |
| `git-workflow` | 256 | ok |

`ROUTING-RULE.md:101-104` also names the exact failure mode: "no mechanism narration.
'**Scans the repo for non-derivable facts**' is a sentence no one says — pure tax."
That string is `craft-context-file`'s description verbatim (`:3`). `craft-skill:3` has the
same shape ("eval scenarios first, then a trigger-engineered description, a navigation-hub
SKILL.md under 500 lines, references/ and scripts/ split by determinism…").

**Minimal fix.** Decide which cap governs and record it in one place. If 400 stands, the four
authoring descriptions need their mechanism-narration clauses cut — roughly 1.6 KB of
always-on tax across every dispatch in every project.

## F8. Roles: strip them, or use them

- `drafts/final/CLAUDE.md:18-19` (live `:23-24`) — "**Strip named roles**, on-call rosters,
  handoffs and sign-offs from process docs — map each to an agent equivalent."
- `outbound-drafts/SKILL.md:42` — "**Roles and patterns, never named individuals.**"

Both fire on an outbound process doc. One says remove the role; the other says the role is the
correct level of abstraction. Reconcilable in intent (always-on targets *process-control*
roles; `outbound-drafts` targets *anonymization*) but neither says so.

**Minimal fix.** `outbound-drafts:42` → "Anonymize to roles, never named individuals — and
strip role-based process controls entirely (see always-on)."

---

# S3 — Orphaned rules

Method: every "already in / kept in / covered by / folded into / lives in / deliberately
absent" claim in every body and every `deferred.md` was checked **against the current target
file**, not against the registry.

## F9. R206 "reclaim order" — claimed always-on by the same file that says it is not

- `agent-dispatch/references/deferred.md:70-73` — "Four of those rows (**R206 reclaim
  order**, R207 …, R208 …, R209 …) are OUT specifically because `~/.claude/CLAUDE.md` already
  carries them always-on."
- `agent-dispatch/references/deferred.md:44-48`, 25 lines earlier — "What survives is only
  '**have a reclaim order decided in advance**' and the `TMPDIR`-on-a-volume-with-room escape
  hatch, **neither of which the registry states concretely enough to write as a rule**."
- Live `~/.claude/CLAUDE.md:48-49` and `drafts/final/CLAUDE.md:65-67` both say only
  "stop and reclaim" — **no order**. `grep -i reclaim` over all 11 bodies returns nothing.

R207/R208/R209 verified present always-on (`:69` model pins, `:70` absolute paths, `:74-77`
worktree/SHA) — those three claims hold. **R206 does not.** The reclaim order exists in no
channel.

## F10. R172 "a trust anchor the agent can write is not a boundary" — each skill points at the other

- `system-design/references/deferred.md:42-43` — "Already homed elsewhere, **do not restate
  here**: *every trust anchor the constrained thing can write is not a boundary* **lives in
  `agent-dispatch`**."
- Its actual location: `agent-dispatch/references/deferred.md:10-13`, i.e. `agent-dispatch`'s
  *displaced* set, not its body — and the entry reads "*Displaced because it fires **when
  architecting an agent system**, not when dispatching one.*"

`system-design` suppressed the rule on the grounds `agent-dispatch` carries it;
`agent-dispatch` displaced it on the grounds it belongs to design-time work, which is
`system-design`'s cue. The rule is in **no body**. `grep -i "trust anchor"` over all 11 bodies
returns nothing.

The sibling claim in the same sentence — "*the synthesizer cannot red-team their own
synthesis* likewise" — **holds**: `agent-dispatch/SKILL.md:48-49`.

## F11. R281 pre-commit stash cache path — claimed home carries neither half

- `agent-dispatch/references/deferred.md:55-56` — "**R281 (rank B) — the pre-commit stash
  cache path**, where a hook parks unstaged work mid-operation. *Belongs with
  `git-workflow`'s stash/hook material, not here.*"
- `git-workflow/SKILL.md` mentions `stash` once, at `:24` (`stash pop` skipped by `&&`) — a
  different mechanism. `git-workflow/references/deferred.md` has no stash-cache entry.
- The *consequence* has since landed always-on at `drafts/final/CLAUDE.md:83-84`
  ("pre-commit stashes unstaged changes, so a mid-run `Read` returns HEAD content"), but the
  **cache path** — the recovery mechanism — is nowhere.

## F12. "Resolve disagreements to evidence, never to the more confident agent" — evicted, no home

- Live `~/.claude/CLAUDE.md:66-69` — "**Subagent output gets the same scrutiny Chris gives
  mine.** … Cited file:line or command output? **Hedging words ("appears to", "consistent
  with") mean inference. Resolve disagreements to evidence, never to the more confident
  agent.**"
- `grep -i "more confident" / "hedging"` → 0 in `drafts/final/CLAUDE.md`, 0 across all 11
  bodies, 0 across all 7 references.
- `agent-dispatch/SKILL.md:43-44` covers the adjacent half only ("observation-vs-inference
  labels and an explicit 'what I did NOT verify' list"). Neither the hedging-word tell nor
  the disagreement-resolution rule survives anywhere.

This is the rule that governs consolidating N subagent reports — the operation this whole
session is performing.

## F13. "Name the optimism bias out loud when felt" — evicted, no home

Live `~/.claude/CLAUDE.md:93-94`. Absent from the candidate and from all 11 bodies. The single
`optimism` hit in the corpus is `pr-review-method/references/deferred.md:95`, a different rule
("calling the area clean is the over-optimism").

## F14. Two orphans landed and were repaired mid-audit — the pattern, not the instance

At the 10:01 candidate, **`git log @{u}..HEAD`, `gh pr checks`, "origin head"** and
**"for a merge, rebase, or wire-shape change the floor is the full quality gate"** were all
absent from the candidate, from all 11 bodies, and from all 7 references. Both were restored
by the 10:04 rewrite (`drafts/final/CLAUDE.md:89-90` and `:92-93`). **No action needed** — but
the eviction rationale that produced it is still on record and still false:

## F15. `CLAUDE-MD-ASSEMBLY.md:75` states a false "kept elsewhere"

> "Verified duplicate cuts that do stand: … `git log @{u}..HEAD` (**now in the `git-workflow`
> body**)."

`grep '@{u}' */SKILL.md` returns **zero hits across all 11 bodies.** Its only appearance in
the tree is `git-workflow/references/deferred.md:86`, in a list titled "**Deliberately absent
— already always-on in `~/.claude/CLAUDE.md`**" — i.e. the body omitted it *because*
CLAUDE.md carried it, and the assembly proposed cutting it from CLAUDE.md *because* the body
carried it. Textbook circular eviction. The line is currently restored; **the justification
must be struck from the assembly or the next diet pass re-cuts it.**

Same paragraph: "`/code-review ultra` (**in the harness system prompt**)". I cannot confirm
this. The command listing available in this session (`init`, `review`, `security-review`,
`run`, `loop`, `schedule`, `simplify`, …) contains no `code-review`. Not asserted false —
**asserted unverified**, and it is the same claim shape as the one that failed above.

---

# S4 — Same-request duplication (R2)

**Verbatim duplication is essentially clean.** A 6-gram overlap sweep of every body against
both versions of the always-on file returns exactly **one** shared phrase — "a breaking
constraint and every caller" (F21 below). Builders did not copy text. **Every R2 defect below
is a paraphrase duplicate**, which the mechanical check cannot see; each was found by reading.

| # | body | always-on | what is duplicated |
|---|---|---|---|
| F17 | `agent-dispatch/SKILL.md:35-36` "A subagent inherits nothing … **Step 0 patches that hole**" | `drafts/final/CLAUDE.md:69-71` (live `:55-57`) "Open every prompt with a **MANDATORY Step 0 Read list** of absolute paths; citing filenames does not make a subagent read them" | the Step-0 mandate itself |
| F18 | `agent-dispatch/SKILL.md:39-40` "Stage is not inherited; **unmarked means planning**" | `drafts/final/CLAUDE.md:50` (live `:85-86`) "**Ambiguous stage means planning**" | the default |
| F19 | `agent-dispatch/SKILL.md:28-30` "**Mandate isolation up front**" | `drafts/final/CLAUDE.md:74-77` (live `:61-64`) "**Code-modifying and mutation agents get an isolated worktree … never a shared checkout**" | the isolation mandate. The candidate *widened* its scope from "mutation-testing" to "code-modifying and mutation", increasing the overlap |
| F20 | `outbound-drafts/SKILL.md:48` "no **detector names**"; `:50-51` "**Echoing the user's own framing does not exempt it**" | `drafts/final/CLAUDE.md:151-152` (live `:114-116`) "No strategy, motive, internal quality-bar labels, **detector names** …  Strip 'gold standard' … **even when Chris's own request used the words**" | both clauses, near-verbatim in sense |
| F21 | `git-workflow/SKILL.md:32` "Land a breaking constraint and every caller and fixture fix in ONE commit … not a file count" + `pr-review-method/SKILL.md:29` "fix every instance in one commit" | `drafts/final/CLAUDE.md:143-146` "A breaking constraint and every caller it breaks, or one defect and its N-1 twins, **ship in one commit**" | **new**, created by the `:107` amendment landing. The bodies' unique content (red-tree-in-between, enumerate-the-spellings, paste zero-hit evidence) should stay; the lead sentences are now a second copy |

`agent-dispatch/SKILL.md:8-16` deliberately declines to restate the preflight and explains
why — that is the correct pattern and the only body that does it explicitly.

## F22. The sanctioned scan-set duplicate — the justification does not hold

- `testing-ci/SKILL.md:23-25` — "**A detector's scan set is part of its claim.** Print roots,
  file count, base ref and resolved commit with the verdict; **zero inputs is an error, not a
  clean verdict**."
- `pr-review-method/SKILL.md:48-49` — "**A detector's scan set is half its verdict** — CLEAN
  over the wrong surface reads as an all-clear. State the set."

The stated justification is that a PR-review turn loads one and not the other. **Test it
against the descriptions.** `testing-ci:3` fires on "a suite that passed suspiciously … an
allowlist or detector that reads as an all-clear … **Use before trusting a green run**".
`pr-review-method:3` fires on "**ask whether a PR is ready to merge**". The turn *"is this PR
ready to merge, CI is green?"* satisfies both, and `pr-review-method`'s own body at `:19-21`
("Run the gate yourself … A green CI rollup is the author's evidence") is precisely a
before-trusting-a-green-run moment. The two descriptions share `check` and `anything` in
their positive halves and neither carries an anti-trigger against the other.

**Verdict: this is a defect under R2, not a sanctioned exception.** It is one sentence — low
cost — but the *justification* is what should not survive, because it is the same reasoning
that will be used for the next duplicate.

## F23. `review-prompt` restates the rule it attributes

`review-prompt/SKILL.md:29` restates the snapshot/flattened-layout rule in full and then
writes "(`craft-skill` carries the rule)" — pointing at `craft-skill/SKILL.md:62-64`, which
carries it. The pointer is correct; the restatement is the duplicate. Low cost, trivially
fixed by keeping the pointer and cutting the sentence.

## F24. ~1.5 KB of shared scaffolding across the four authoring bodies

`craft-context-file` × `craft-skill` share 76 distinct 6-gram runs — the whole Step-1 parse
block ("Arguments arrive as `key=value` tokens in the invocation text (or `$ARGUMENTS`) …
Report unknown keys; never silently ignore them"), the Red-flags tail, and the Validation
tail ("the gates you name but do not claim: `ph-lint` …, a review-prompt critique, and a
fresh-session …"). `craft-prompt` and `review-prompt` share smaller runs of the same.

This is template prose, not rules, and the four rarely co-fire — **informational, not a
defect.** Recorded because it is real always-off bytes that a shared reference would remove.

---

# S5 — Cue collisions (positive halves only)

Method: descriptions split at "Do NOT use" / "Not for"; every content token of each positive
half word-matched against the other ten positive halves.

## F25. `post` — `outbound-drafts` × `pr-review-method` (drives F4)

`outbound-drafts:3` "something to **post** or send" vs `pr-review-method:3` "or **post**
findings". Neither carries an anti-trigger against the other, and the content they deliver on
that shared cue is contradictory (F4). **The most consequential collision in the set.**

## F26. `draft` — the fix landed one-way only

`outbound-drafts:3` now carries the negative routing as reported: "Not for text that instructs
a model — a prompt, system prompt, or agent instructions is `craft-prompt`." **Confirmed
landed.**

Residual: `craft-prompt:3`'s positive half claims "write, create, **draft**, improve, or tune
a prompt" and its anti-trigger list is "critiquing an existing prompt (use `review-prompt`),
packaging full skills, or copywriting unrelated to instructing agents" — **it never names
`outbound-drafts`**. "Draft a PR comment" hits `craft-prompt`'s positive half with nothing
deflecting it. The fix is symmetric-by-halves and needs the other half.

## F27. `instructions` — `craft-prompt` × `craft-context-file`, asymmetric

`craft-prompt:3` "a prompt, system prompt, or agent **instructions**" vs `craft-context-file:3`
"AGENTS.md, CLAUDE.md, GEMINI.md, repo **instructions**". `craft-context-file` routes back
("Not for single prompts (`craft-prompt`)"); `craft-prompt` does not route forward. Same shape
as F26. Note `craft-skill:3` and `outbound-drafts:3` *both* carry `instructions` in their
negative halves — three of four skills route away from the word, the fourth claims it and
never releases it.

## F28. Two of the eleven skills are absent from the mandatory routing table

`drafts/final/CLAUDE.md:7-14` lists `git-workflow`, `pr-review-method`, `testing-ci`,
`agent-dispatch`, `prebid-adcp`, `craft-*`, `review-prompt`. **`system-design` and
`outbound-drafts` appear nowhere in the candidate always-on file** (`grep` returns zero hits
for either name).

These are the two skills with no installed predecessor — the two whose reachability depends
entirely on the new routing directive. `outbound-drafts` is also the sole home of the
`Ran:`/`Not-run:` footer (F-clean-3), so its unreachability re-opens a defect that was
already fixed once.

**Minimal fix.** Two table rows: `outbound-drafts` — "drafting anything that leaves this
machine: issue body, PR comment, briefing"; `system-design` — "threat models, trust
boundaries, irreversible effects, migration cutover".

## Collisions checked and found benign

`merge` (`git-workflow` × `pr-review-method`) — both firing on "is this PR ready to merge" is
correct; their bodies carry disjoint content. `committing` (`git-workflow` ×
`review-prompt` "before committing prompt changes") — qualified, disjoint content. `review` /
`findings` / `ask` (`pr-review-method` × `review-prompt`) — `review-prompt:3` carries the
anti-trigger "application source code or PR diffs", which deflects correctly. `agent` (5
skills) — disambiguated by "parallel / spawning / fanning out" in `agent-dispatch`.
`reviewing` (`pr-review-method` × `prebid-adcp`) — `prebid-adcp` is anchored on "AdCP".

---

# S6 — References

## F29. `system-design` points at a section that does not exist

`system-design/SKILL.md:8-9` — "More rank-A rules in `references/deferred.md` — exception
migration, **approval queues**, config surfaces, human consoles, supply-chain posture,
per-field provenance."

`grep -i "approval"` over `system-design/references/deferred.md` returns **zero hits**. The
nearest content is "Deferred actions, transitions, cascades" (`:46`), which is about
transactional enqueue of *reactions*, not approvals. The approval-queue rule the pointer
describes is in the **body itself** at `:65-67` ("Guards evaluated at enqueue and re-checked
only for legality at drain are a TOCTOU … **An approval bound to an ID, not a content digest,
permits a post-approval swap**"). The pointer sends the reader to a reference for something
they have already read.

## F30. `testing-ci` — 0 of 5 pointer names resolve to a heading

`testing-ci/SKILL.md:80-82` names: *contention and persistent-fixture false greens · linter
and pre-commit blind spots · error-assertion and pinned-constant shapes · path-keyed and
self-clearing detectors · not editing a test to pass.*

`testing-ci/references/deferred.md` headings: *Environment: the green came from the wrong
machine · Runner and CI verdicts · Detectors that clear themselves, go vacuous, or measure the
wrong thing · Assertion shapes · Harness and fixtures · Choosing and ordering the enforcement
· Existing tests.*

All five topics **exist** in the file (R105/R106, R101+R102, R118-R123, R109/R110, R132) but
**no pointer name matches any heading**, and two of the five ("linter and pre-commit") span
two different sections. Compare `pr-review-method/SKILL.md:85-87`, whose ten names match ten
headings exactly, and `git-workflow/SKILL.md:84`, whose three match three. Two builders used
heading names; two used prose topics.

## F31. `system-design` — 0 of 6 pointer names resolve to a heading

Beyond F29: *exception migration* → `## Typed boundaries and errors`; *config surfaces* →
`## Config as policy`; *human consoles* → `## Human-facing surface`; *supply-chain posture* →
`## Dependencies, vendors, supply chain`; *per-field provenance* → a bullet inside
`## Fleet and tooling architecture`. Five resolve by content, none by name.

**Minimal fix for F30/F31.** Rename the pointers to the headings, or the headings to the
pointers. Same edit, either direction.

## F32. `git-workflow/references/claude-md-lines.md` is orphaned from its body

`git-workflow/SKILL.md:84` names only `references/deferred.md`. The second reference file is
reachable only from a sibling reference (`git-workflow/references/deferred.md:94` "see
`claude-md-lines.md` block 1") — you must already be reading one reference to learn the other
exists. `agent-dispatch/SKILL.md:86` names **both** of its reference files; `git-workflow`
names one of two.

This file contains the three proposed always-on lines, the hook spec, and the recorded
`:107` contradiction — it is the highest-stakes reference in the tree.

## F33. `craft-context-file` has an unreachable installed reference

`~/.claude/skills/craft-context-file/references/skill-authoring.md` exists on disk and is
named nowhere in `craft-context-file/SKILL.md` (which names `context-file.md`,
`claude-code.md`, `codex.md`, `anti-patterns.md`). Every other reference in every other skill
resolves: `craft-prompt` 38/38 reachable, `craft-skill` 5/5, `review-prompt` 19/19,
`craft-context-file` 4/5.

Note: the four authoring skills have **no `references/` directory under `drafts/final/`** —
their pointers resolve only against the installed `~/.claude/skills/<name>/references/`. If
`drafts/final` is deployed as a self-contained tree, all 71 of those pointers break at once.

---

# Verified clean

Stated explicitly, per the reporting bar.

1. **Verbatim R2 against the always-on file: CLEAN.** A 6-gram sweep of all 11 bodies against
   both the live and candidate always-on files returns one shared phrase, and that one is the
   deliberate reconciliation (F21). No builder copied always-on text.
2. **The `:107` contradiction: RESOLVED IN THE CANDIDATE.** `drafts/final/CLAUDE.md:143-146`
   carries the replacement wording verbatim as specified in `CLAUDE-MD-ASSEMBLY.md:28-30`.
   `git-workflow:32` and `pr-review-method:29` are now consistent with it. **It remains live
   in `~/.claude/CLAUDE.md:107`** — both bodies contradict the file that is actually loading
   today, and will until the candidate is applied.
3. **The `Ran:` / `Not-run:` footer: FIXED and single-homed.** Present only at
   `outbound-drafts/SKILL.md:65-67`; zero hits in the candidate always-on file, zero in the
   other ten bodies. (Caveat: F28 — `outbound-drafts` is not in the routing table.)
4. **The `draft` anti-trigger: LANDED** at `outbound-drafts/SKILL.md:3` (one-way — F26).
5. **The "adversarial multi-lens panel" contradiction: FIXED.** `agent-dispatch/SKILL.md:68`
   reads "Three lenses **once a fan-out is authorized**", correctly subordinate to
   `drafts/final/CLAUDE.md:54` "Default is a SINGLE pass … ZERO spawned agents". No unguarded
   fan-out default survives in any body.
6. **`git-workflow`'s four "deliberately absent — already always-on" claims: ALL HOLD**
   against the live file (`:61-64`, `:73-77`, `:92`, `:105-109` — `deferred.md:82-88`). This
   builder verified, and the verification reproduces.
7. **R001 empty-grep / `git grep -P`: RESOLVED.** `git-workflow/references/deferred.md:90-93`
   flagged it as delivered by nothing; `drafts/final/CLAUDE.md:123-124` now carries it, and
   the narrowed description correctly drops the cue.
8. **Remaining "kept elsewhere" claims that hold:** R207/R208/R209 always-on
   (`agent-dispatch/references/deferred.md:70-73`); R278→R103 in `testing-ci`'s OUT set
   (`:52`); R287 zsh brace inline in `git-workflow:63-64` (`:65`); R189→`CLAUDE.md:34` (`:31`);
   R161→R094 in `testing-ci/SKILL.md:76-78` (`git-workflow/references/deferred.md:69-71`);
   R162 folded into `git-workflow/SKILL.md:79-80` (`:74`); R098/R096/R139 in
   `testing-ci/references/deferred.md:77,113,146`; "synthesizer cannot red-team" in
   `agent-dispatch/SKILL.md:48`; "`craft-skill` carries the rule" → `craft-skill:62-64`.
9. **Reference resolution for the three method skills: CLEAN by name.**
   `pr-review-method` 10/10, `git-workflow` 3/3, `agent-dispatch` 2/2 files named.
10. **No missing reference files.** Every `references/…` path named by any of the 11 bodies
    exists on disk (against the installed tree for the four authoring skills). Zero dangling
    filenames.

---

# NOT CHECKED

- **`PRINCIPLE-REGISTRY.md` and `REGISTRY-GAP-R310.md`.** Every registry-id claim (R001–R319)
  was verified against the **target file**, per the brief. Whether the registry's own rank and
  routing verdicts are correct was not re-derived.
- **The 28 reports under `reports/`, `FINDINGS.md`, `PLAN.md`, `INVERSIONS.md`, `PATCHES.md`.**
  Not read. Measurements quoted inside bodies and references (3/28 → 14/14, 208 vs 185,
  9.5% capture, 54.1% edits on main, Fisher p-values, the 2,565-unit corpus) were **taken as
  given** — no experimental claim was re-run.
- **Body-internal quality.** Anti-pattern rows, emphasis density, line budgets, stance
  consistency, frontmatter validity. That is `review-prompt`'s pass, not this one — with the
  exception of the description-length measurement in F7.
- **Whether each rule is true.** This pass checked consistency and reachability across bodies,
  not the correctness of any individual rule.
- **`drafts/split2/`** (13 entries, mtime 09:47) and `drafts/git/`, `drafts/pr/`. Not opened —
  the brief scoped this to `drafts/final/`. If `split2` is a competing final set, none of the
  above applies to it.
- **Eval scenarios and trigger firing.** No description was exercised against a live session.
  F25–F28 are static analyses of description text; measured firing rates would supersede them.
- **The candidate always-on file after 10:04.** It changed twice during this audit. Findings
  F1, F3, F12, F13, F17–F21 and F28 are against md5 `b5ac0bf51aae4fd6a52607edaac9bbcf`.
