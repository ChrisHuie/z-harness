# Should `Skill` go into the salesagent lens allowlists? No.

Measured 2026-08-02. Repo read-only throughout — dirty-file count 55 at start and 55 at end.

## Decision

**Do not add `Skill` to the lens `tools:` allowlists. Port the 6 genuinely-new rules into
`review-charter.md`, which every lens already reads at Step 0, at zero always-on cost.**

## Why — three measurements

**1. The overlap is 18 of 25.** `pr-review-method`'s 25 body rules against the charter:
**18 already there · 1 contradicts · 6 new.** The 18 are not paraphrases; several are
near-verbatim, and the charter's version is consistently stronger because it carries the
worked example and a detector (`disposition_ledger.py`, `review_completeness.py`).

**2. The skill never fires in a lens. 0 `Skill` calls across 59 and 65 turns**, with
`"MODE: PR re-review"` in the dispatch — the skill's own strongest trigger — and the listing
present in the wire. The lens reads its charter Step-0 and never considers a skill. Tool
census: `Bash` 46/52/60, `Read` 4/6/4, `Skill` **0/0**.

**3. The cost is real and almost entirely unrelated to the skill you want.**
`msg[1]` goes **94 B → 12,341 B**; `pr-review-method`'s own entry is **393 B — 3.2%** of that.
The other 96.8% is `dataviz`, `update-config`, `keybindings-help` and 30 more. Plus the
`Skill` tool schema at +1,877 B. Wire delta **14,398 B**, billed prefix delta **4,883 tok**,
sitting in the cached prefix and re-read every turn: **+249k–288k cache-read tok ≈
$0.155–$0.175 per lens**, and **6.39 lenses per review** (median 7, max 8 — measured from 18
shipped reports; `executor` and `qc-validator` are not review lenses). **$0.99–$1.40 per
review for zero uses.**

## The 6 rules to port — none has a single hit anywhere in the charter, tooling, or the 8 lens bodies

1. **Consumer / except-path enumeration** — *a value newly introduced into a request body is a
   behavior claim; enumerate every sink it reaches — success path, each `except` path, every
   log/audit/feed/webhook consumer — before rating severity.* `"consumer"` = **0** hits.
   §1.5b/§1.5c/§11 sweep *implementations of one operation*; none sweeps *sinks of one value*.
   **This is the exact shape of the real miss** (below). Add as §1.5e.
2. **Steelman first** — surrounding paragraphs, decision records, sibling files, commit
   messages, before filing. → §1
3. **Grep the codebase's own confessions** — *keep in sync*, *only verifies setup*. §12
   adjudicates a confession once found; nothing tells you to hunt for them. → §1
4. **Two-dot as well as three-dot.** Every lens and `full-review.md:20` prescribe only
   `git diff origin/main...HEAD`. pr1682 round 4's own header reads *"PR is 6 commits behind
   `origin/main`"* — exactly when they diverge. → `full-review.md` Step 1
5. **A missing-test observation used as evidence is its own finding**, own ledger row. → §1
6. **Grade the COMPOSITION of landed remedies** against a behavioral done-contract; two
   correct fixes to one path can cancel. → §4c

**Do NOT port the contradicting rule.** `pr-review-method` says *"Post as `COMMENT` and verify
they landed once Chris has asked."* Charter §1.7: *"You NEVER edit files, push, comment on
GitHub, resolve threads, or run `gh pr create`."* At lens tier the skill reads as conditional
authorization the charter denies absolutely. Its safe half — *compute the commentable set from
the diff hunks first; an anchor outside it is a scope signal* — goes to `full-review.md` Step 7,
**orchestrator tier only.**

## Two false claims this corrected, both of which had been repeated

- **`"Contract met"` appears in no report.** It is `disposition_ledger.py:372`'s clean-exit
  banner — detector stdout, not artifact text.
- **`full-review-pr1682-rereview-20260729.md` FOUND the credential BLOCKER** (1 BLOCKER /
  13 SHOULD-FIX / 21 NIT, disposed at :223-225). **The real miss is one round earlier** —
  `…-20260722.md`, head `cf0d5da32`, 7 specialists including `review-security`, shipped
  **0 BLOCKER** and credited the PR with *"hardening a latent credential-leak path"* while all
  three defect sites existed at that head.

## Not tested

Only `review-security` was A/B'd; the other 7 lens bodies were read, not run · the `Task`-spawn
path (measured `claude -p --agent <lens>`) · N=1 charter-only, N=2 skill arm · whether porting
the 6 rules improves outcomes — only the overlap gap was measured, not the effect of closing it
· nothing in the repo was executed.
