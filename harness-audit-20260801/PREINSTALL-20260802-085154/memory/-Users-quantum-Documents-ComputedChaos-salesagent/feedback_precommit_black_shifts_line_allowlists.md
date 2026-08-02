---
name: feedback-precommit-black-shifts-line-allowlists
description: "ANY line-count-changing edit — yours, or a formatter hook reformatting mid-commit — breaks line-keyed guard allowlists (test_architecture_no_model_dump_in_impl KNOWN_VIOLATIONS etc.). Re-derive line numbers AFTER formatting converges; run the guard locally before push, even for comment-only edits."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

(Generalized 2026-06-11: the original culprit — the pre-commit black hook — was removed in #1370. The trap is formatter-agnostic and still live: ruff-format can reformat staged files mid-commit, and YOUR OWN edits shift lines.)

Any test that stores `(file_path, line_number)` tuples — like `tests/unit/test_architecture_no_model_dump_in_impl.py::KNOWN_VIOLATIONS` — sees the SAME violations at NEW positions after any line-count change in a covered file.

**This is broader than formatters.** An innocuous docstring or comment re-wrap (2 lines → 3) shifts every allowlist entry below it. PR #1356: a spec-comment expansion went 2→3 lines and CI reported "20 NEW violations" in a file with zero behavioral change; the fix was compressing back to the original line count.

**The trap sequence:** derive line numbers locally → update allowlist → commit → a hook reformats the file mid-commit → the committed file has post-format lines while the SAME commit's allowlist has pre-format lines → CI fails the guard with "N stale + N new". Hit three rounds on PR #1276.

**How to apply, when editing any file covered by a line-keyed allowlist:**
1. Run the owning guard test locally after the edit, BEFORE pushing — even for comment/docstring-only changes. Line count is the contract.
2. Converge formatting FIRST, then derive: `uv run ruff format <file>` (or `uv run pre-commit run --files <file>`) → re-stage → run the guard → update the allowlist with post-format positions → commit.
3. For your own line-count changes: preserve the original line budget, or shift the allowlist entries by your delta.

**Detection shortcut:** a guard reporting MORE violations than you knew existed, in a file you didn't change structurally → suspect line shift first; `git diff -U0 -- <file>` shows the deltas.

Durable design lesson: line-keyed allowlists are inherently brittle — when touching one, prefer symbol-keyed entries (function/class names) if the guard supports them.

Related: [[feedback_black_ruff_format_disagreement]] (the resolved two-formatter era), [[feedback_run_full_suite_before_every_push]].
