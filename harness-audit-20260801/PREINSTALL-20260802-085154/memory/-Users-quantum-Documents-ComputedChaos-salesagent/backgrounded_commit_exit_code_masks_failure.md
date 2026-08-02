---
name: backgrounded-commit-exit-code-masks-failure
description: "A backgrounded compound command (git commit; echo; git log) reports the LAST stage's exit code, not the commit's. A pre-commit-aborted commit (e.g. black reformatted a staged file) then shows 'exit code 0' while HEAD never advanced. Verify HEAD/tree, never trust the task's reported exit code."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8377e960-8e7a-4aba-8c4d-4aedb89a6629
---

When you run a commit in the background as part of a compound command — e.g.
`git commit -q -m "..."; echo "exit=$?"; git log --oneline -1` — the background
task's reported exit code is the exit of the **last** stage (`git log`, almost
always 0), NOT the `git commit`. So a commit that FAILED can be reported as
"completed (exit code 0)".

The common failure that hides this way: pre-commit's **black** hook reformats a
file you staged (often pre-existing lines in a file you only touched for an
unrelated edit — black disagrees with `ruff format` on `assert long_call(...),
"msg"`), which makes the black hook exit non-zero and ABORTS the commit. The
files stay staged, the reformatted file shows as `MM` in `git status`, and HEAD
never advanced. See [[feedback_black_ruff_format_disagreement]] and
[[feedback_precommit_black_shifts_line_allowlists]].

**How to apply:**
- After any backgrounded commit, confirm success by `git log --oneline -1` /
  `git rev-parse HEAD` (did HEAD advance to a NEW sha?) and `git status` (clean? or
  `MM`/staged leftovers?) — never by the task's "exit code 0".
- Prefer a bare `git commit -q -m "..."` as the backgrounded command (no trailing
  `; echo; git log`) so the task's exit code reflects the commit itself.
- If aborted by black: converge the offending asserts to `msg = ...; assert cond,
  msg` (the form both black and ruff accept; let the formatter paren-wrap a
  >120-char `msg` string — both agree on that), re-stage, recommit. Run
  `uv run black --check <files>` proactively before committing to catch it first.
- Ties [[feedback_no_alarm_mid_operation]] (staged/`MM` state mid-commit is
  transient) and [[feedback_verify_before_asserting]].
