---
name: testing-ci
description: Proving an existing test or CI signal is real - mutation-testing a call site, falsifying an empty red set, checking whether a `-k` selector actually selected anything, auditing guard matchers and allowlists for false confidence, and deciding whether a green CI verdict can be trusted. Use when verifying that a test would actually fail if the behavior broke, when a suite passed suspiciously, or when judging whether a green check means the check ran.
---

# Proving a test or CI signal is real

This is about **verifying strength**, not authoring. Scope: does this test fail when the
behavior breaks, and does this green mean anything?

## The core obligation

**Every invariant claimed in prose needs a mechanism that goes red when it breaks.**
Mutation-test each **call site**, not just the shared helper.

The five failure classes: docstring-only, dead defensive clause, adjacent-green test,
partial enumeration, helper-revert masking.

## An empty red set is a hypothesis, not a result

**"I broke it and nothing failed" is a claim about your `-k` selector.** Baseline the
count, print node ids, or drop `-k` and run the whole file. Prove the selector selects the
scenario under test before concluding anything is ungraded.

**Never judge pass/fail from a test runner's terminal tail** — tox prints its own success
banner over failed suites. Read the structured per-suite record and enumerate every
non-passing outcome.

**Before trusting any per-branch run**, assert `git rev-parse HEAD` equals the expected SHA
and `git status --porcelain` is empty. Abort on mismatch.

## Guards

- **A guard catches only the forms its matcher models.** Enumerate every equivalent syntax
  and add positive **and** negative self-tests. An empty allowlist reads as "every site
  caught" when the matcher may simply not model an equivalent form.
- **Every guard-allowlist entry must name a function reachable from production.** Trace it
  backwards with a call-site grep, or the guard is false confidence.
- **For every compound `and`/`or` guard, name which operand each test actually evaluates**
  and require one test per operand. Coverage lies here: both line and branch coverage read
  as covered while one operand is never evaluated.
- **Re-mutation-test an oracle after ANY change to its guarded path** — a later redundant
  mechanism can silently neuter it.

### Where guards belong

**Your own** review and harness artifacts stay gitignored — run `git check-ignore <path>`
before creating any file under `tests/` or `src/`. Enforce **your personal** conventions in
a private detector, never by adding a guard to a shared repo's `make quality`: a
`tests/unit/test_architecture_*.py` guard runs on every contributor's build, and gating
other people's builds is a shared-repo decision.

> This rule scopes personal tooling only. **A project's own sanctioned guard-authoring
> workflow is out of scope** — where a repo has a guard-authoring skill and already runs
> guards on `make quality`, use it.

## Existing tests

**Default to resurrecting dead or broken tests with stronger assertions and edge cases.
Never delete a test to close a gap without confirming first.**

(This governs *deleting a test*. Removing a skip marker or reconciling an xfail is a
different operation and is not covered here.)

## Trusting green

- **One green run on a timing-sensitive or strict-xfail test is luck.** Run it 5+ times, on
  the exact shipped artifact — never on a reconstruction.
- **A gated CI optimization can no-op through a working fallback while checks stay green.**
  Read the job log for the branch marker, then measure. Never infer engagement from the
  check's pass/fail.
- **One skipped full-suite run is fine.** After the FIRST CI surprise in a session, the next
  push runs the full suite.
- **When changing a wire shape, payload shape, or any cross-cutting test contract, do the
  whole systematic sweep BEFORE the first push** — never one CI failure at a time. Read the
  schema; never build payloads from memory.

## Project-specific false greens

Where a repo documents its own masking gotchas — stale port desync, concurrent-container
contention producing spurious setup errors, persistent schema hiding a fresh-DB failure —
**defer to that list**. It knows failure modes this file does not.
