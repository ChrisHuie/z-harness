## Headline

**178 lines → 100. 10,368 B → 5,656 B. 3,883 → 2,118 tokens. Saves 1,765 tokens per dispatch (45.5%) with nothing load-bearing lost.**

One correction to your framing before the audit, because it changes the arithmetic in your favour: this file is **not** paid per session. `FINDINGS.md:207-219` proves the injection is per *dispatch* — auto-injected verbatim into every agent's first user message, confirmed on a subagent with zero tools and a custom system prompt, so it is unconditional. Every subagent you spawn pays the full 3,883 tokens again. In the salesagent corpus that is 41,859 payers, not ~hundreds. That also means the file is currently being injected into agents that structurally cannot act on most of it — a research subagent with no Bash tool is billed for the Docker Singleton recovery command.

---

## 1. Line-by-line assignment

| Lines | Block | Verdict | Reason |
|---|---|---|---|
| 1-6 | H1 + "distilled from 255 memories" + editorial policy | **CUT** | Provenance about the file, not a rule. The retention bar is `craft-context-file`'s job — its description already says "enforces per-harness budgets (CLAUDE.md-class under 200 lines)". |
| 7-13 | Skill routing table | **CUT — duplicated in the same request** | `FINDINGS.md:428` found `msg[1]`, a `role:"system"` message on every request carrying the **skills listing** — with full trigger descriptions. I received it in this session. Your table is a lossy paraphrase of text already injected 4 lines away. ~350 B for negative value. |
| 14-15 | "Per-project memory does NOT load across directories" | **CUT here** | Verbatim duplicate of lines 172-174. Kept once, in Memory. |
| 19 | "Chris, @chrishuie — solo maintainer… agent team" | **KEEP** | Not derivable; sets the frame every other rule depends on. |
| 20 | Docker novice | **KEEP (compressed)** | Communication contract, fires whenever infra comes up — not only on dispatch. |
| 21-22 | No beads/`bd`; **`make quality` / `./run_all_tests.sh`** | **KEEP first half / CUT the commands** | The negative constraint is cheap and non-derivable. The commands are project-specific and **wrong in most projects this file loads into** — a global file asserting a Makefile target that does not exist is an active hazard. → the relevant project's own `CLAUDE.md`. |
| 23-24 | Strip named roles/rosters/handoffs | **KEEP (folded into persona)** | Direct consequence of solo+agents; costs one clause there. |
| 25-26 | `@chrishuie`, git author name is not proof | **KEEP (compressed)** | Outward-facing error (CODEOWNERS, @-mentions), and the trap is genuinely non-obvious. |
| 27 | Never fork or clone without permission | **KEEP → moved to Boundaries** | Passes all three. Belongs with the other ops the user owns, not in a persona block. |
| 31-39 | "Default is a SINGLE pass… ZERO agents", cost, latitude, named-tool | **KEEP — strongest block in the file** | This is the only rule that counteracts a pressure injected in the *same context window*: the Agent tool description tells you to fan out, and the harness system prompt says to send parallel agents in one message. Without it the default flips. |
| 35-36 | `/code-review ultra` is user-launched and billed | **CUT — duplicated in the harness system prompt** | Verbatim in my session prompt: "It is user-triggered and billed; you cannot launch it yourself, so do not attempt to via Bash or otherwise." |
| 41-45 | Preflight `df -h` / `docker info` | **MOVE → `agent-dispatch`** | Fails #2 outright. A `df` command is not costly to forget in a writing session. The sealed-volume gotcha is good and must survive — just not here. |
| 46-47 | Cap at 3-4 concurrent | **KEEP as a routing gate, depth moves** | The cap only binds after you have already decided to fan out — so make that decision the trigger. One line: "when I do, load the `agent-dispatch` skill first". This is your own leverage ladder (line 176) applied to the file itself. |
| 48-52 | ENOSPC, never cycle Docker, Singleton recovery | **MOVE → `agent-dispatch`** | Pure runbook. Reachable only mid-fan-out. |
| 53 | Two corrections = re-verify from scratch | **KEEP → moved to Claims** | Misfiled — this is not a dispatch rule. Universal, non-obvious (the default is a third attempt at the same fix). |
| 55-59 | Dispatch hygiene (omit `model`, Step 0 reads, SendMessage, never Read `.output`) | **MOVE → `agent-dispatch`** | All four are unreachable without a subagent. |
| 61-64 | Mutation agents get an isolated worktree | **MOVE → `testing-ci` (primary) + `agent-dispatch`** | `testing-ci` already triggers on "mutation-testing a call site" — that fires *before* the dispatch, which is the right moment. |
| 66-69 | Subagent output gets the same scrutiny | **SPLIT** | Universal half ("a symptom is evidence; its because-Y is a hypothesis") → Claims. Subagent-specific half (hedging words, resolve to evidence not confidence) → `agent-dispatch`. |
| 73-77 | Never push / `gh pr` / `gh issue` unprompted | **KEEP** | Irreversible + outward-facing. The harness prompt covers push only; `gh pr comment` and `gh issue create` are uncovered, and the "publish the PR = prep request" discriminator is the non-obvious part that does the work. |
| 79-80 | "Create an issue" = fenced block | **KEEP (compressed)** | Specific output contract preventing an outward-facing action. |
| 82-86 | Research-complete is not authorization | **KEEP, minus the recovery command** | Highest-value rule after dispatch: auto-accept mode actively invites the violation and the edit lands silently. `git checkout -- <paths>` is self-evident recovery → cut. |
| 90-94 | Wrong claim = 100% fail, banned words | **KEEP** | The banned-word list is the mechanical gate; it earns its bytes. |
| 92-93 | "origin head, `git log @{u}..HEAD`, `gh pr checks`" | **CUT — duplicated in `git-workflow`** | `git-workflow/SKILL.md:47-48`: "Before any state claim, run `git log @{u}..HEAD` and cite the origin head." |
| 93-94 | "Name the optimism bias out loud"; "Confident-wrong spends trust irrecoverably" | **CUT** | The first is unactionable; the second restates line 90. |
| 96-101 | Citation in the moment, premise re-verification, "redundant/covered" | **KEEP (compressed)** | Core. "Memory files are claims" is the non-obvious clause and survives. |
| 100 | "merge/rebase/wire-shape → full quality gate" | **MOVE → `git-workflow` + `testing-ci`** | Situational by construction. |
| 105-107 | Never bulk auto-rewrite | **KEEP** | Destroys work; `--unsafe-fixes` is one keystroke from convenient. |
| 107 | "PR scope is a contract; 3+ files is its own PR" | **MOVE → `pr-review-method`** | It already has a `## Scope and refactors` section. |
| 108 | Never propose delete/revert/discard first | **KEEP** | Destroys work; task-independent. |
| 109 | "Public remedies must be idiomatic, empirically run" | **MOVE → `pr-review-method`** | |
| 113-116 | GitHub-bound output carries only technical fact | **KEEP (compressed)** | Narrow-ish, but the leak is irreversible once posted and `pr-review-method` fires for *reviewing*, not for issue bodies or commit messages. "Even when Chris's own request used the words" is a non-obvious override — kept. |
| 118-120, 122-126 | Style, single verified steps, open with the finding, larger option, close with untested | **KEEP (compressed 9 lines → 8)** | Highest-frequency block in the file — fires every turn, so it is maximally task-independent. "Close with what was not tested" is a gate that catches the overclaim. |
| **128-146** | **Four measurement traps + pipeline + pricing** | **MOVE → out entirely. Biggest win.** | **You asked: reference, or rule? Reference — and already on disk.** `FINDINGS.md:13-38` holds all four traps *in richer form*, and the CLAUDE.md copy is **lossy in a way that matters**: it states trap 3 and trap 4 as universal, when §0 records trap 3 as version/project dependent and trap 4 as **subagents only** (main threads 0.0% affected in every project). So the always-on copy is the *less correct* one. 19 lines, ~700 tok, every dispatch, forever, for an analysis that ran once and whose output is two directories away. Cut the pointer too — forgetting it costs one `ls ~/.claude/`. |
| 149-152 | "Verify with the SAME instrument…" | **KEEP — the best rule in the file** | **You asked: behavioural or situational? Behavioural.** It names a *direction* of error ("fails toward the reassuring answer"), which no situation makes self-evident, and it is the mechanism behind every confident-wrong result. |
| 152-156 | "Observed 8 times: grep for MENTION vs CONTENT, 91.6%, phantom citations, all-digit SHA…" | **CUT** | Five worked examples + a statistic = evidence *for* the rule, not the rule. This is exactly the reference/rule line you asked me to draw. They live in the audit dir. |
| 158-160 | Measure before reconstructing | **KEEP first two sentences, CUT the incident** | The default is to reason rather than look; genuinely non-obvious. |
| 162-164 | A/B changing two things | **KEEP one line, CUT the incident** | **Weakest KEEP in my rewrite — flagging it for you.** The premise is close to self-evident (test #3 is marginal); what survives is the operationalization ("if the recommendation is remove X, run the arm that removes ONLY X"). Justified by frequency for this user, not by non-obviousness. Cut it if you disagree — costs 2 lines. |
| 168-170 | Memory holds cross-session patterns only | **KEEP (compressed)** | Partially duplicated by the harness's own memory instructions; kept the non-dup parts (names stripped, staleness). |
| 172-174 | Universal facts go HERE, not a silo | **KEEP, argument upgraded** | Replaced the "255 memories / 14 silos" anecdote with the *measured* consequence from `FINDINGS.md:224`: a silo `MEMORY.md` is injected into every dispatch in that project, so a misfiled memory is invisible elsewhere **and** billed forever. Same length, strictly stronger. |
| 176-178 | Never promise to remember — build the gate | **KEEP** | Prevents the model saying "I'll remember that", which is a lie. |

**Rule I applied consistently on incidents:** cut *lists* of worked examples (the 5-example Verification block, the "255 memories", the "3 arms" A/B story); keep single short blast-radius clauses that calibrate severity (`--unsafe-fixes` rewrote 3 production schema files). If you want full consistency, that last one goes too — 11 words.

---

## 2. The rewritten `CLAUDE.md` — verbatim and complete

**5,656 B · 100 lines · ~2,118 tokens.** Staged at `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/CLAUDE.candidate.md` (not written to `/Users/quantum/.claude/CLAUDE.md`, per your read-only constraint).

```markdown
# Core rules — every project, every dispatch

## Chris (@chrishuie)

Solo maintainer; all implementation runs through an agent team. Strip named roles, on-call
rosters, handoffs and sign-offs from process docs — map each to an agent equivalent. Docker
novice: explain what a step does and why, never just hand over commands. No beads / `bd` /
formula tooling — standalone skills and standard git. Use `@chrishuie` for CODEOWNERS,
reviewers and @-mentions; the local git author name has varied and is not proof of the account.

## Boundaries — Chris's to authorize, not mine

**Never on my own initiative:** `git push`, `gh pr create/merge/comment`, `gh issue create`,
forking or cloning a repo. Prepare the artifact and stop. "Publish the PR" / "let's push it"
are prep requests; the discriminator is an explicit imperative aimed at a specific op. On
explicit delegation: confirm once, execute, report the URL. Local git (commit, rebase, stash,
deleting local-only branches) is pre-authorized.

**"Create an issue"** = print the body in a fenced block to paste. Never `gh issue create`,
never a notes file. Scope the gap and the contract, not my solution.

**Research-complete is not authorization.** Present the plan with every `[DECISION]` flagged
and wait for approval before the first code edit; auto/accept-edits mode is not plan approval.
While planning, zero edits to source, tests, scripts, CI or config — a config bump is a code
change. Ambiguous stage means planning.

## Agent dispatch — opt-in, never the default

**Default is a SINGLE pass, done myself, with ZERO spawned agents.** Each agent is real money
on Chris's tab; count the cost before spawning. The harness's "dispatch independent work in
parallel" guidance optimizes wall-clock and knows nothing about the bill or the RAM.

Fan out only when Chris says go wide / deep / exhaustive, or the invoked skill prescribes it —
and when I do, **load the `agent-dispatch` skill first** (preflight, concurrency cap, worktree
isolation, prompt shape, reading reports back). Named a tool? Run **exactly that and stop** —
never wrap it in a self-directed swarm. Method latitude exists for **equivalent-or-better**,
flagged up front; the cardinal sin is the hidden downgrade.

## Claims and evidence

**A wrong claim is 100% fail regardless of speed or framing.** Banned: *ready, clean, verified,
looks good, should work, all set, solid, perfect, done*. Report raw state and the exact scope of
what ran. **"I don't know" is a full answer.**

**No factual claim without a citation verified in the moment**, at the claim's scope — not just
the cases I expected. Comments, docstrings, PR text, reviewer prose **and memory files** are
claims; evidence is observed output, the test I ran, the call path read end-to-end, spec prose.
Re-verify the premise first: an assumption stack two deep is the wrong-path tell. A symptom is
evidence; its because-Y is a hypothesis — falsify it before it enters an artifact.
**"Redundant / covered / can't be done" needs the same proof as "it's a bug".**

**Two corrections from Chris on one point = stop and re-verify from scratch**, not a third
attempt at the same fix.

## Verification

**Verify with the SAME instrument as the thing you are checking, or say plainly that you did
not.** A looser check is a new, weaker measurement — and it fails toward the reassuring answer,
which is the direction that ends inquiry.

**Measure before reconstructing.** Check whether the quantity is already recorded somewhere I have
not looked, before reasoning my way to it.

**An A/B that changes two things tells you the pair matters, not which one.** If the
recommendation is "remove X", run the arm that removes ONLY X.

## Destructive operations

**Never bulk auto-rewrite source** (`ruff --fix --unsafe-fixes`, pyupgrade, isort) without
per-site review — `--unsafe-fixes` once rewrote 3 production schema files and broke runtime.
**Never propose delete / revert / discard before finding the non-destructive fix.**

## Output

**Anything bound for GitHub** — including drafts handed over to paste — carries only technical
fact. No strategy, motive, internal quality-bar labels, detector names, or how the work was
produced. Strip "gold standard" and "meets our bar" even when Chris's own request used the
words. The empirical result is fair game; the provenance is not.

**"Easier to read" means more structure, not less content.** Short lead, bold-lead bullets,
clear hierarchy; every line = location + fact + fix. No marketing adjectives, praise, gratitude
openers, teaching framing or soft sign-offs. Open with the finding — if the first sentence could
be deleted with zero information loss, delete it. Close with what was **not** tested.

**Work in single verified steps.** Restate the contract before executing; never pre-commit to
multi-step plans. "I'll do A; after you see A we decide B." Lead options with the better end
state, not the smaller one — Chris consistently picks the larger.

## Memory

**Universal facts go HERE.** `~/.claude/projects/<project>/memory/` does not load across
directories, and its `MEMORY.md` index is injected verbatim into every dispatch in that
project — a misfiled memory is both invisible elsewhere and billed forever.

Memory holds **cross-session patterns only** — never per-PR audits, file lists or status
snapshots, which go stale within hours. Capture WHAT was learned, never WHO said it.

**Never promise to remember — build the gate.** Leverage runs `soft memory < turn instruction <
CLAUDE.md < a mechanical gate that FAILS`. A lesson violated twice needs the gate, not a
restatement.
```

---

## 3. What moved where — nothing is lost

### BLOCKING PREREQUISITE — `~/.claude/skills/agent-dispatch/SKILL.md` does not exist

The rewrite's dispatch section routes to it. **Create it before pasting the new file**, or that line points at nothing. Suggested description (trigger-engineered to fire on the decision, not after it): *"Mechanics of spawning subagents — preflight checks before a fan-out, concurrency caps and RAM/disk failure modes, worktree isolation for code-modifying agents, prompt shape that makes a subagent actually read its inputs, and scrutinising the reports that come back. Use before dispatching any subagent, when a fan-out is planned, when an agent reports something odd, or when consolidating subagent findings."*

Content to place in it, from the old file — the moved text verbatim:

```markdown
## Preflight EVERY dispatch — before, not after the first odd report
```bash
df -h /System/Volumes/Data   # `df -h /` shows the SEALED volume, not the data volume
docker info --format '{{.ServerVersion}}'   # must already be UP if any agent needs a DB
```
- **Cap at 3–4 concurrent and wait for a batch to return.**
- At 100% disk every command fails `ENOSPC` on unrelated paths and mutation agents emit
  false findings. **Infra failure is neither pass nor fail — stop and reclaim.**
- Never cycle Docker mid-fan-out; agents polling for it read the restart as contention.
- Docker dead after a hard crash = stale Electron singleton:
  `rm ~/Library/Application\ Support/Docker\ Desktop/Singleton{Cookie,Lock,Socket}` then `open -a Docker`.

## Dispatch hygiene
Omit `model` (inherit the session model — pinning ages badly). Open every prompt with a
**MANDATORY Step 0 Read list** of absolute paths; citing filenames does not make a subagent
read them. Tell background agents to SendMessage their report — a finished agent may idle
instead of delivering. Never Read its `.output` symlink; it is the full JSONL transcript and
overflows context.

## Isolation for code-modifying agents
**Mutation-testing agents get an isolated worktree or an in-memory copy — never a shared
checkout.** Their revert discards uncommitted work permanently. Commit first so a
`git checkout --` lands on your commit. `isolation: "worktree"` may branch from main rather
than the launching HEAD — pass the target SHA and have the agent verify.

## Reading the reports back
**Subagent output gets the same scrutiny Chris gives mine.** Cited file:line or command
output? Hedging words ("appears to", "consistent with") mean inference. Resolve
disagreements to evidence, never to the more confident agent.
```

### Into existing skills

| Destination | Exists? | Moved text |
|---|---|---|
| `testing-ci` | yes | The isolation block above (dup it — `testing-ci` triggers on mutation testing, which is *before* the dispatch). Plus: "For a merge, rebase, or wire-shape change the floor is the full quality gate." |
| `pr-review-method` | yes, `## Scope and refactors` | "PR scope is a contract; a change touching 3+ source files is its own PR." + "Public remedies must be the idiomatic one, empirically run." |
| `git-workflow` | yes | "For a merge or rebase the floor is the full quality gate." |
| Relevant project `CLAUDE.md` | n/a | "validate with `make quality` or `./run_all_tests.sh`" — belongs to the repo that has them. |

### Deleted as already-on-disk, no new home needed

- **The four measurement traps + pipeline + pricing** → `~/.claude/harness-audit-20260801/FINDINGS.md:13-38` (§0), which is more complete and more correct.
- **The five verification examples** ("grep for MENTION vs CONTENT", 91.6%, phantom citations, all-digit SHA) → same audit dir.
- **Skill routing table** → the harness injects the skills listing with full descriptions on every request (`FINDINGS.md:428`).
- **`/code-review ultra`** → harness system prompt.
- **`git log @{u}..HEAD` / origin head** → `git-workflow/SKILL.md:47-48`.

---

## 4. What the saving is worth

Per dispatch: **1,765 tokens**. Calibrating "units" against the audit's own MEMORY.md figure (7,353 tok × 41,859 dispatches = 30.8M units ⇒ 0.100x, i.e. cache-read rate):

| | tok/dispatch | raw over 41,859 dispatches | units | % of corpus |
|---|---|---|---|---|
| old | 3,883 | 162.5M | 16.25M | 1.16% |
| new | 2,118 | 88.7M | 8.87M | 0.63% |
| **saved** | **1,765** | **73.9M** | **7.39M** | **0.53%** |

≈ **$22 per salesagent-sized corpus at Sonnet-class rates, ≈$111 at Opus-class** (rate back-derived from the §6d compaction capture: 30,504×$3/M + 95,666×$0.30/M + 1,288×$15/M = $0.1395 vs the measured $0.140102).

The number that matters is the comparison: §6d puts the *entire* efficiency program at **7.1-10.0%** total savings, offset by a 2-10% cost it had not priced — "cost-neutral at best". This edit is **0.53% of every project's bill, permanently, with zero offsetting cost and zero behavioural risk** — roughly 5-7% of the program's whole measured upside, delivered by one file edit. It is the highest-certainty line item in the audit, because unlike the enumeration mandate its cost side is exactly zero.

Two multipliers I did not price, both pushing the real figure up: the first dispatch of each session pays the **cache-write** rate (main thread `ephemeral_1h` = 2.0x, i.e. 20x the cached rate) rather than 0.10x; and the file is paid in **every project**, so 0.53% is the per-project rate, not a one-off.

---

## Judgment calls you may want to overrule

1. **The A/B rule (2 lines)** — my weakest KEEP. Justified by this user's frequency, not by non-obviousness.
2. **The `--unsafe-fixes` incident clause (11 words)** — I cut every other worked example. Keeping this one is a deliberate exception on severity-calibration grounds, not a consistent application of the rule.
3. **The GitHub-provenance rule** — arguably `pr-review-method` material, kept global because that skill triggers on *reviewing*, and the leak can happen in an issue body or commit message with no review in sight. If you disagree, it is 4 lines back.
4. **`agent-dispatch` as a routing gate** — this trades a guaranteed cost (20 lines always-on) for a conditional one (the skill loads only on fan-out, and per `FINDINGS.md:431` invoking a skill injects the whole SKILL.md). If fan-outs are frequent in a given project, the skill body will be injected often enough that the saving narrows — but never below zero, since single-pass sessions pay nothing.

**Not tested:** I did not verify on the wire that the rewritten file is injected identically to the original (no capture run); the byte/token figures are static measurements plus the audit's own 2.67 chars/token text estimator. I did not create the `agent-dispatch` skill or edit any skill — all moves above are specifications, not applied changes. I did not check whether any project-level `CLAUDE.md` already duplicates the blocks I cut.