verified: 2026-07-14 · sources: prompt-craft §7 (commits/PRs), example-corpus §3 (git-commit-formatter), modes-and-composition §3/§7 (default stance, handoff)

# Pattern: commits-prs

**Purpose:** write commit messages and PR bodies that convey intent.
**Default stance:** implement (the tail of a change) — also runs under **operate** for automated/CI commit flows.

## Method
- Follow Conventional Commits: `type(scope): subject`, imperative mood ("add", not "added").
- Convey intent and the "why", not a restatement of the implementation.
- Derive the PR body — what / why / how-to-test — from the actual diff.
- Flag breaking changes with a `BREAKING CHANGE:` footer.

## Output contract
Commit subject in `type(scope): subject` imperative form; body explaining why; PR description covering what / why / how-to-test grounded in the diff; `BREAKING CHANGE:` footer when applicable. Consumes the diff (+ plan) as input.

## Rubric hooks
- Does the subject follow Conventional Commits (type, scope, imperative)?
- Does the message convey intent rather than paraphrase the diff?
- Is the PR body's what/why/how-to-test derived from the real diff?
