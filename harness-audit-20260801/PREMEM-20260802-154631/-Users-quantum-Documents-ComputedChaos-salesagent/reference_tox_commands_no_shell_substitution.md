---
name: reference-tox-commands-no-shell-substitution
description: "tox 4 execs `commands` as argv without a shell — `$(...)`, `<`, `|` pass as literal tokens and fail at runtime. Any substitution-dependent tox.ini line must be verified by RUNNING the env (or `tox config -e <env> -k commands`), never by reading the diff."
metadata: 
  node_type: memory
  type: reference
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

tox 4 does not run `commands` through `/bin/sh`. A line like
`coverage report --fail-under=$(tr -d '[:space:]' < {toxinidir}/.coverage-baseline)`
is shlex-split into literal argv tokens (`'--fail-under=$(tr'`, `-d`, `'[:space:]'`, `'<'`, …)
and fails at runtime (`invalid floating-point value: '$(tr'`). tox substitutes only its own
`{...}` forms and `{env:...}`.

**Why it matters:** a reviewer verified such a line statically ("the line now reads the baseline ✅")
and the defect shipped past two review rounds. CI was unaffected (its copy ran in a real shell
`run:` block), so the breakage was local-only and silent behind a `|| echo non-fatal` wrapper.

(Status note 2026-06-11: current tox.ini no longer contains the offending pattern — the coverage
threshold is a hardcoded `--fail-under=30`. The tox-4 behavior fact and the verify-by-running rule
are what this memory carries.)

**How to apply:**
- Any tox `commands` line needing shell syntax → wrap explicitly (`bash -c '...'` + `allowlist_externals = bash`) or move into a script / `python -c`.
- Reviewing tox.ini changes → run the env (`tox -e <env>`) or at minimum `tox config -e <env> -k commands` to see the real argv tokenization.
- Instance of [[feedback_empirical_over_static_guard_assessment]] — empirical over static, applied to config.
