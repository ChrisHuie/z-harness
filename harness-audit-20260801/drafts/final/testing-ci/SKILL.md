---
name: testing-ci
description: Deciding whether a test, a guard, or a green check proves anything — mutation-testing a call site, a suite that passed suspiciously, a selector that may have selected nothing, an allowlist or detector that reads as an all-clear, a patch or mock that quietly stopped taking effect, a check that never ran. Use before trusting a green run or calling a behavior covered.
---

# Proving a test or CI signal is real

## The empty red set

- **"I broke it and nothing failed" is a claim about your selector.** `baseline N passed →
  mutated N passed` is the only trustworthy shape; a changed *deselected* count means the
  selector moved.
- **A prose-asserted invariant needs something that goes RED.** Looks enforced, is not: docstring
  only · dead defensive clause · a neighbor green for another reason · partial enumeration (3 of
  4) · a helper whose revert reddens every path. **Mutate each call site, not the helper.**
- **A passing oracle can stop guarding without failing**: a later redundant mechanism over the
  same case neuters it. Re-mutate after any change to the guarded path.
- **Mutate each link, not the leaf.** A self-test calling the extracted matcher stays green
  while the mid-chain walker or the file filter is mutated to yield nothing.

## Guards, detectors, allowlists

- **A detector's scan set is part of its claim.** Print roots, file count, base ref and
  resolved commit with the verdict; **zero inputs is an error, not a clean verdict**.
- **A guard catches only the spellings its matcher models.** Enumerate every equivalent form,
  or name what is out of scope *in its output*. Positive **and** negative self-tests.
- **Every allowlist entry must reach production** — trace back to call sites (name + open
  paren, not imports); index nested defs. An exemption must come from something the artifact
  cannot write.
- **A `(file,line)`-keyed allowlist breaks on any line shift**, a formatter's included. Converge
  formatting first, then derive; prefer symbol keys. New violations in a file you did not
  restructure = line shift.
- **Three gate shapes carry zero information**: a byte tripwire · a detector whose error arm has
  never executed · an advisory red regardless. Reliability tracks **both-arms-taken branch**
  coverage, not line.

## Assertions that cannot fail

- **A positive presence check over an append-extensible artifact is loose**: `phrase in DOC` is
  monotone under insertion, "the document asserts P" is not. Its dual, "no match found", is
  safe: hence forbidden-sets.
- **A structural/AST guard cannot see circularity** — trace each asserted value to its source.
  Three vacuity shapes: re-deriving production's own expression from the same source ·
  asserting a harness-built invariant · echoing an input literal.
- **A compound boolean reads "covered" while one operand is never evaluated** — short-circuit
  satisfies line *and* branch coverage. One test per operand; `assert A and B` hides B.
- **Train == test**: a heuristic or detector scored on the cases it was built from proves
  nothing; a bound abstracted *from* the cases you found is circular.

## Not the code you think ran

- **A test that never ran reads as a pass** — a missing step def, an unregistered scenario, a
  network gate, a dormant grader. Read PASS vs SKIP for the case, not an aggregate; more than
  one gate can apply.
- **`from X import Y` binds at import time; where a name resolves decides whether a patch is
  live.** Moving a call into another module's helper makes stale patches live; hoisting a lazy
  import kills a live one and the test still passes. A reload under an active patch binds the
  mock permanently — teardown restores the source, not the copy. Grep both sites.
- **A test entering below the boundary verifies the layer below**: a *wire*/*e2e* test calling
  the handler proves the handler; envelope, serialization and middleware sit above. Assert on
  the bytes the consumer receives — reconstruction is lossy and collapses two errors into one.

## Green that is not evidence

- **Never judge pass/fail from a runner's tail or exit code** — it prints its own banner when
  *its* environments exit zero, and an aggregator can succeed over failed suites. Parse
  per-suite machine output.
- **One green run on a timing-sensitive test is the lucky branch of a race** — N≥5 on the exact
  shipped artifact, never a reconstruction.
- **Static analysis gives a reliable set and an unreliable per-site fix list**: a head scan counts
  inherited population, added-line intersection over-reports moved code, a net delta folds in
  rebases. Rebase onto the target and run the gate; verify a config by running it.
- **A checkout can silently fail and leave you on the old tree**, often because the gate dirties
  a tracked file. Discard, switch, then assert the resolved commit **and** a clean tree.
  **Identical test counts across branches is the symptom.**
- **A job gated on a release or base-branch condition never runs on a change request** — a green
  check list is no evidence the gated path works, and **zero entries for that job class IS the
  tell**.

**Read `references/deferred.md` before answering if the green turns on the environment,
the runner's own verdict, a self-clearing detector, an assertion shape, a fixture, or an
enforcement channel.**
