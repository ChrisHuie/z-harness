---
name: pr-review-method
description: Method for reviewing a pull request and handling reviewer feedback - re-pulling all three GitHub comment endpoints plus GraphQL reviewThreads before any addressed/done claim, anchoring findings to path:line as inline threads, splitting severity from disposition, grading remedy composition on re-review, and consolidating subagent findings without dropping sites. Use when reviewing a PR, responding to reviewer feedback, judging whether feedback has been addressed, or writing up findings.
---

# PR review method

## The hard gate before any "ready / addressed / done"

**Re-pull review state on the current head. Every time. Including for PRs you are not
editing.**

```
pulls/N/reviews        pulls/N/comments        issues/N/comments
+ GraphQL reviewThreads
```

A re-review that only re-checks CI plus prior findings is **not** a review-state re-check.
Skipping this is the documented miss.

**Never filter review activity by author on the first pass** — inventory every commenter
across all three endpoints, then narrow.

## Finding a defect

- **Before fixing a cited site, grep the repo for the pattern and count the copies.** Fix
  every instance in the same commit and paste the zero-hit evidence. **N>1 means a missing
  abstraction, not a site defect.**
- **For every new top-level def/class/constant in a diff, grep repo-wide first.** "Does an
  equivalent already exist?" is never a diff-local question — the twin may live in an
  untouched file the diff cannot see.
- **Grep the diff for the codebase's own confessions** — *"keep in sync"*, *"only verifies
  setup"* — before any ready claim. Fix them; don't document them.
- **Treat a pattern learned in one area as a hypothesis about the rest:** map where it
  holds, where it diverges, and what enforces it.
- **Before proposing a fix, walk all four derivative levels:** the change, its interactions,
  what masks or proves them, and what keeps it true.

## Findings hygiene

- **Anchor every finding to `path:line` and post as inline review threads, never
  paragraphs.** GitHub only accepts an inline comment inside a diff hunk. Prose in one
  PR-level comment has no lifecycle and gets dropped.
- **Never reuse a finding ID across rounds.**
- **A missing-test observation used as evidence inside a production finding still needs its
  own ledger row and its own disposition.**
- **Ban "optional" and "non-blocking" as dispositions.** Split *severity* from
  *disposition* and resolve every finding to a named action. A review can find a real
  defect and still drop it by rating it a nit.
- **De-dup is not synthesis.** Unify same-concept findings across agents, **preserve every
  site**, and resolve each to a named disposition.

## Verification discipline

- **Verify "clean" agent verdicts as hard as "violation" ones.** Before any "complete"
  claim, sweep every known pattern across every open PR.
- **State a detector's scan set alongside its verdict.** A CLEAN result over the wrong
  surface is a true sentence that reads as an all-clear.
- **Re-derive every number and every because-X from your own prior round** before it
  reappears in an artifact, or downgrade it to `[inferred]`. Compaction summaries and
  prior-session facts are claims, not evidence.
- **Never call a flagged pattern "pre-existing" on a stable count alone** — the set can
  churn (remove N, add N). Prove it with `git log -G` over the PR's own commit range, a
  byte-identical site-set diff, and blame. "Pre-existing" is also not the same as "harmless".
- **Verify a reviewer's proposed FIX against the code** — and against spec/env authorities —
  before applying it. Deference is not verification, including for items inherited from
  colleagues. **Sibling patterns extrapolated from a reviewer's meta-pattern are
  hypotheses**: verify each, and skip verified non-defects with one line of evidence.

## Re-review

- **Grade the COMPOSITION of the landed remedies**, and each remedy's whole mechanism — two
  individually correct fixes to one path can cancel.
- **Diff two-dot against current main as well as three-dot.** Already-upstream commits are
  invisible in the merge-base diff.
- **Grade a fix against the issue's behavioral done-contract** and trace the changed value
  into its downstream consumers before rating severity.
- **Never frame a re-review ping as a "cheap win", "free move", or "high-leverage"** —
  pinging does not change review state. Lead merge recommendations with **what a merge
  unblocks**, never with reducing the open-PR count.

## Using subagents in a review

- **Pin every subagent to a fetched head SHA**, then re-check the live head after the fan-out
  returns and re-base each finding before consolidating.
- **After any code-modifying subagent sweep, run a second-pass audit subagent** with
  explicit memory reads before pushing.

## Reviewing someone else's PR

**Never author on it.** Propose fixes, run the gate yourself on the asserted head, and
never push or patch for them.

## Scope and refactors

- **Expand PR scope only when the expansion completes the principal and leaves it intact.**
  Size is not the test.
- **A new shared helper ships with at least one PRODUCTION caller in the same PR.** Grade
  the extraction *N adopted / M eligible*, name every holdout, and check which unified
  behaviors it actually kept.
- **An SSOT PR deletes the duplicate paths in the same commit** — otherwise the
  consolidation is fictional and the next person uses the wrong path. Semantic SSOT (same
  rule, different words) is invisible to textual-DRY guards: sweep siblings and re-earn
  clean verdicts on the final head.
- **Deleting one of N duplicate writes is a behavior claim.** Enumerate every reader on the
  success path AND on each except path first; a green suite does not prove it.
- **Never reuse an exception-class tuple across consumers** — map condition to class for the
  new consumer's own question. One constant answering N questions is the tell.
- **"The harness can't host this" needs a prototype or a line-level cost from real call
  sites.** A true premise does not license the deferral.
- **On a tooling or CLI PR**, state the tool's cardinal invariant, adversarially enumerate
  the inputs that defeat it, and run it end-to-end.

## Writing it up

- **A final report is self-contained and contributor-actionable**: `file:line`, the problem,
  why it matters, a tested diff, and the verification. Never reference `/tmp` paths as the
  deliverable.
- **Pick the review shape first** — heavy consolidation vs light inline. Lead with
  mechanism, no gratitude opener, close with a **Ran / Not-run** footer.
- **Comment only genuinely non-obvious logic** — never explain standard language patterns —
  and **never embed issue or PR numbers in code comments**; git history and PR descriptions
  carry traceability.
- **Put anything Chris will paste or send in a fenced code block, never a blockquote.** The
  `> ` prefix has to be stripped by hand.
