---
name: pr-review-method
description: Method for reviewing a pull request and handling reviewer feedback - what to re-pull before claiming anything is addressed, how to anchor and dispose of findings, and how to grade a second round. Use when asked to review or re-review a PR or a diff, check what reviewers said, respond to or address review feedback, judge whether feedback has been addressed, check whether a PR is ready or clean or good to merge, see what is outstanding across PRs, or post review findings.
---

# PR review method

## The gate before any "ready / addressed / done" — on any PR

Re-pull review state on the **current head**, every time, including PRs you are not
editing: `pulls/N/reviews` · `pulls/N/comments` · `issues/N/comments` · GraphQL
`reviewThreads`. Re-checking CI plus prior findings is not a review-state re-check.

- **Never filter by author on the first pass** — inventory every commenter, then narrow.
- **Proof of "addressed" is a code diff at the item's `path:line`** — not a resolved
  marker, a commit message, or recall. A composite comment ("fix X; same for Y") is two
  items.
- **Re-earn every verdict on the final head.** The fix commit is the least-reviewed code
  in the PR; a verdict inherited across a new commit is void.
- **Run the gate yourself** on the asserted head — assert `HEAD == headRefOid`, clean tree,
  read the summary not the exit code. A green CI rollup is the author's evidence, not
  the reviewer's.

## Finding a defect

- **Grep repo-wide and count the copies before writing the Fix.** N>1 is a missing
  abstraction, not a site defect. Fix every instance in one commit; paste the zero-hit
  evidence.
- **Every new top-level def/class/constant gets a repo-wide grep**; the twin lives in a
  file the diff cannot see.
- **Sweep the pattern across every open PR**, from a written list — deciding not to fix
  PR Y is not deciding not to check it.
- **Grep the codebase's own confessions** — *keep in sync*, *only verifies setup*. A sync
  comment is a written DRY violation; fix it, don't document it.
- **Semantic SSOT escapes textual-DRY guards**: one constant as two literals, one
  invariant computed two ways. Sweep siblings by hand.
- **Grade a new helper `N adopted / M eligible`**, name every holdout, and check *which*
  absorbed behavior it kept — it can ship the weakest shape everywhere. Its parts too: a seam can own one of five and be named for the whole.
- **An SSOT or consolidation PR deletes the duplicate paths in the same commit**, or the
  consolidation is fictional.
- **Deleting one of N duplicate writes is a behavior claim.** Enumerate every reader on
  the success path AND each `except` path; a green suite measures the suite, not the
  behavior.

## Verifying claims

- **A detector's scan set is half its verdict** — CLEAN over the wrong surface reads as an
  all-clear. State the set; include prose surfaces when the obligation lives there.
- **A finding from your own prior round is a lead, not a fact** — re-derive it on the
  current tree or mark it `[inferred]`. Binds hardest once an author adopts your wording.
- **"Pre-existing" needs provenance, not a stable count** — the set churns. Prove it with
  `git log -G` over the PR's own range, a byte-identical site-set diff, and blame.
  Pre-existing ≠ harmless — answer as a scope decision.
- **Verify a reviewer's proposed FIX, and every sibling you extrapolate from it, before
  acting** — against the code, and against any spec or test authority that may
  *mandate* the flagged behavior. Deference is not verification, including for items
  inherited from a colleague. Skip a verified non-defect with one line of evidence.

## Delivering findings

- **Anchor every finding to `path:line` and post as inline threads.** A paragraph in one
  PR-level comment has no lifecycle. Never reuse a finding ID across rounds.
- **Compute the commentable set from the diff hunks before building the payload.** An
  anchor outside it is a scope signal — never fall back to the nearest commentable line;
  it belongs in the review body. Post as `COMMENT`; verify they landed.
- **Ban "optional" and "non-blocking".** Severity (how wrong) and disposition (what
  happens next) are independent; every finding resolves to a named action and a deferral
  gets a filed owner.
- **A missing-test observation used as evidence is its own finding**, with its own row and
  disposition — "folds into X" only if one edit closes both.
- **De-dup is not synthesis.** Unify same-concept findings at max member severity,
  preserve every site, then sweep for the site no agent reached.

## Re-review

- **Grade the COMPOSITION of the landed remedies** — two individually correct fixes to one
  path can cancel. Grade each remedy's whole mechanism: construct *and* read,
  extract *and* pin. Mutate the half nobody asked about.
- **Diff two-dot against current main as well as three-dot.** Already-upstream commits are
  invisible in the merge-base diff.
- **Grade against the issue's behavioral done-contract**, and trace the changed value into
  its downstream consumers before rating severity.

## Role

- **On someone else's PR, propose — never author, patch, or push.** Reviewer, not steward:
  severity-rated findings and a Ran / Not-run footer, not encouragement or a curve.
- **Pin every subagent to a fetched head SHA**, re-check the live head after the fan-out,
  and re-base every finding before consolidating; an active PR moves mid-review.
