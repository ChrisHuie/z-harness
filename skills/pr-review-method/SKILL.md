---
name: pr-review-method
description: Reviewing a pull request and handling reviewer feedback — what to re-pull before claiming anything is addressed, how to anchor and dispose of findings, how to grade a second round. Use when asked to review or re-review a PR, check what reviewers said, address feedback, judge whether it was addressed, or post findings. Not for a general outbound message (outbound-drafts).
---

# PR review method

## Before any ready / addressed / done claim — on any PR

Re-pull review state on the **current head**, every time, including PRs you are not
editing: `pulls/N/reviews` · `pulls/N/comments` · `issues/N/comments` · GraphQL
`reviewThreads`. Re-checking CI plus prior findings is not a review-state re-check.

- **Never filter by author on the first pass** — inventory every commenter, then narrow.
- **Proof of "addressed" is a code diff at the item's `path:line`** — not a resolved
  marker, a commit message, or recall. A composite comment is two items.
- **Re-earn every verdict on the final head.** The fix commit is the least-reviewed code
  in the PR; an inherited verdict is void, including across a diff you asked for.
- **Run the gate yourself** on the asserted head — assert `HEAD == headRefOid`, clean
  tree, read the summary not the exit code. A green CI rollup is the author's evidence.

## Finding a defect

- **Steelman first.** Read the surrounding paragraphs, decision records, sibling files and
  commit messages. An excerpt is not the file — "X is missing" is a repo-wide
  check.
- **Grep repo-wide and count the copies before writing the Fix, and for every new
  top-level def/class/constant** — the twin lives in a file the diff cannot see. N>1 is a
  missing abstraction, not a site defect: paste zero-hit evidence.
- **Sweep the pattern across every open item, from a written list** — not fixing Y is not
  deciding not to check it.
- **Grep the codebase's own confessions** — *keep in sync*, *only verifies setup*,
  unverified defensive rationales. Extract what they confess; don't document it.
- **Semantic SSOT escapes textual-DRY guards**: one constant as two literals, one
  invariant computed two ways. Sweep siblings by hand.
- **Grade a new helper `N adopted / M eligible`**, name every holdout, and check *which*
  absorbed behavior it kept — it can ship the weakest shape everywhere, or own one of five
  parts and be named for all.
- **A consolidation or SSOT change deletes the duplicate paths in the same commit**, or
  the consolidation is fictional and the canonical docstring is not yet true.
- **Deleting or rewriting one of N duplicate writes is a behavior claim.** Enumerate every
  reader on the success path AND each `except` path, and trace a new value into each
  consumer before rating severity.

## Verifying claims

- **State a detector's scan set with its verdict** (`testing-ci` carries the mechanism) —
  include prose surfaces when the obligation lives there.
- **A finding from your own prior round is a lead, not a fact** — re-derive it on the
  current tree or mark it `[inferred]`.
- **"Pre-existing" needs provenance, not a stable count** — the set churns. Prove it with
  `git log -G` over the PR's range, a byte-identical site-set diff, and blame.
  Pre-existing ≠ harmless: it is a scope decision.
- **Verify a reviewer's proposed FIX and every sibling you extrapolate from it** — against
  the code and any spec or test authority that may *mandate* the flagged behavior.
  Deference is not verification.

## Delivering findings

- **Anchor every finding to `path:line`; an inline thread is its delivery shape.** A
  head-specific handoff (`outbound-drafts`) summarizes evidence; it never owns a finding.
  Never reuse a finding ID.
- **Compute the commentable set from the diff hunks before building the payload.** An
  anchor outside it is a scope signal — never fall back to the nearest commentable line.
  Post as `COMMENT` and verify they landed only once Chris has asked; otherwise stop at the
  payload.
- **Ban "optional" and "non-blocking".** Severity (how wrong) and disposition (what
  happens next) are independent; "non-gating" launders a dropped finding. Every finding
  gets a named action, every deferral a filed owner.
- **A missing-test observation used as evidence is its own finding**, with its own row and
  disposition — "folds into X" only if one edit closes both.
- **De-dup is not synthesis.** Unify same-concept findings at max member severity, keep
  every site, then diff your working-note citations against the delivered artifact.

## Re-review

- **Grade the COMPOSITION of landed remedies against the issue's behavioral
  done-contract** — two individually correct fixes to one path can cancel, and a remedy
  can fix one side of its own mechanism. Mutate the half nobody asked about.
- **Diff two-dot against current main as well as three-dot.** Already-upstream commits are
  invisible in the merge-base diff.
- **Pin every subagent to a fetched head SHA**, re-check the live head after the fan-out,
  and re-base every finding before consolidating — an active PR moves mid-review.

**Read `references/deferred.md` before writing the finding if it turns on derivative
depth, scope of an expansion, an undercounted sweep, an inert declaration, a scan-set
escape, review tooling, a dep bump, a dormant grader, or port norms.**
