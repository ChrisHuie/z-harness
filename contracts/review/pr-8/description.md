Head: `fdee797cbea14542145cff3b039b378d77f69f04` for every figure below. Later commits on this branch add
only review documents under `contracts/review/`, changing no guard, tool or contract.

## Summary

The registered `PreToolUse(Bash)` predicates share a bounded parser for shell and Git
execution paths that can reach two guarded hazards:

- a PCRE-only pattern interpreted by Git's ERE engine;
- a zsh modifier changing a Git `rev:path` operand before Git receives it.

The parser returns `deny` for a proven guarded hazard, `ask` when a relevant executable,
authority source, regex engine, alias, stdin edge, function binding, or shell source is
unresolved, and `allow` only when the guarded hazard is absent.

This branch also carries the mechanism that produces the mutation figures below.
`guard-decisions.json` pinned what the guards decide; nothing pinned what their suites catch,
so that evidence was run by hand and its counts retyped into review text no check could read.
Three published counts were the subset under attention rather than the total they claimed.
`tools/write-mutation-receipt.py` now generates the receipt and a summary table, the gate
fails when a declared set element carries no recorded evidence, and outbound review text under
`contracts/review/` includes the generated table rather than restating it.

## The timeout is a fail-open boundary

Measured on Claude Code 2.1.233 in an isolated scratch project: a PreToolUse
`type: "command"` hook that does not answer within its registered timeout does not block
the tool call. Five of five runs executed, against a control in the same harness whose
hook answered immediately with `deny` and did block.

Exceeding the registered five seconds is therefore the guard not applying, not the guard
being slow. `GUARD_BUDGET_SECONDS` keeps the process inside that window, and budget
exhaustion returns `ask`.

## Boundaries enforced at this head

- Git option, engine, pattern, alias, subcommand, executable, configuration, and exec-path
  authority are classified before a positive decision.
- `log`, `shortlog` and `rev-list` are parsed with their own argv grammar. Measured on git
  2.46.1 they take no positional pattern, do not cluster short flags, accept no long-option
  abbreviation, and have no `--no-*-regexp` negation, so the engine tokens are matched
  exactly and patterns are carried explicitly.
- An executable that is not settled — a Git named by a different path, or a wrapper that
  changed executable lookup — may be classified only from a set of names an ambient alias
  cannot redirect. The property is that the command EXISTS in that Git, not that it is
  builtin: measured across git 2.7.4 to 2.46.1, `stash` is not a builtin on 2.20.4 and is
  never shadowed, while `restore` and `maintenance` are builtins on 2.46.1 and do run the
  alias on every Git before 2.23 and 2.29. Both are excluded. `restore` is a guarded
  subcommand, so an alternate binary running it is a question rather than a verdict.
  Everything outside the set is unresolved.
- Static command substitutions, backticks, parameter and arithmetic expansions, literal
  `eval`, supported shell `-c` sources, heredocs, here-strings, pipelines, process
  substitutions, and file-input redirects are recursively classified.
- Command environment and executable-lookup authority are carried across nested shell,
  alias, heredoc, and here-string boundaries.
- Function definitions are processed in source order. Conditional and short-circuit
  definitions remain uncertain; subshell and non-final pipeline definitions do not replace
  the parent binding.
- zsh `=name` expansion is evaluated with the active `EQUALS` state. Startup options are
  parsed only before the first operand.
- When multiple predicates or recursive commands apply, `deny` outranks `ask`, which
  outranks `allow`.

Closed size and recursion limits are 1 MiB of command source, 16,384 subcommands, 65,536
tokens, eight command-prefix wrappers, four nested `env -S` splits, sixteen nested
expansion levels, four nested shell-command levels, eight nested Git aliases, and 512
function declarations. Each reddens when raised. Six carry a fixture pair in the guard's
own corpus; the 1 MiB cap has its at-limit fixture there and its past-limit check in the
merged Bash suite.

## Cost

Per-call latency, one hook process each, on the authoring host:

| input | at `94a519e` | at this head |
|---|---|---|
| 1,047,552-character legal source | deny at 4.27 s | allow at 2.31 s |
| 80,004 characters of repeated `git` | ask at 33.5 s | ask at 0.29 s |
| 300,004 characters of repeated `=git` | not finished inside 100 s | ask at 0.97 s |

Medians of five runs at this head and three at `94a519e`, one hook process each.

The first two exceeded the registered timeout, which the measurement above shows is a
fail-open. A fixture at the byte cap holds the 1 MiB limit to being reachable: budget
exhaustion returns `ask`, so `allow` there is only true while a maximum-size command still
classifies inside the budget.

## Verification

At `fdee797cbea14542145cff3b039b378d77f69f04`, with zero workspace changes:

- `python3 tools/ci-gate.py`: 10 suites, 0 failures;
- harness CI 225 checks, harness selftest 75, renderer 192;
- Bash guard 1,100; Git guard 583; zsh guard 239; ci-gate 55;
- skill-eval validation 22 scenarios across 6 skills; fresh render and verify 5 targets.

`contracts/goldens/guard-decisions.json` records the verdict for 752 commands — 233 allow,
216 ask, 303 deny — and the gate verifies it on every run. Source digests pin bytes and
floors ratchet counts; this pins decisions, so a verdict change appears as its own
reviewable line.

`contracts/goldens/mutation-receipt.json` records what those suites catch, regenerated by
`tools/write-mutation-receipt.py`: every element of every guarded set removed one at a
time, and six single-site edits anchored by content digest. 30 sets, 251 elements, 6 site
edits, verdicts read from `SELFTEST-SUMMARY` rather than exit codes. No site mutation
survives and none moved a check count, so the mutations broke behaviour rather than the
selector.

Element margins are uneven. 172 of the 251 elements are held by fewer than two checks and
103 by none; for those, removing the element leaves both the owning suite and the merged
Bash suite green. `MOD_MEANING` and `_CLOSED_LIMITS` are excluded, the first being read
only to build reason text and the second being the drift check itself. The shrink-only
ceiling in `tools/ci-gate.py` is the shortfall those margins leave against a target of two,
`sum(target - margin)` and currently 275, rather than the number of elements below it: an
element moving from no checks to one leaves that count unchanged, so a closed gap did not
register. The shortfall can fall, and cannot rise without failing.

Behavioural footprint against `654be2a2`, over a 731-command fixture corpus: 414
commands change decision — 182 allow→deny and 187 allow→ask, all carrying hazard text
except 38; 29 deny→allow and 11 deny→ask where the branch point was over-strict; 3
ask→allow and 2 ask→deny. No hazard-free command becomes `deny`.

GitHub completed both exact-head workflow events successfully. `pr-delivery-state.py --pr 8`
reports PR head equal to this commit, 6/6 checks passed, 2/2 exact-head runs passed, and
merge state `CLEAN`.

## Limits and not run

The margin ceiling records current coverage rather than a target met: the recorded shortfall is
275, with 172 elements held by fewer than two checks. Raising them is not attempted here.

This is a conservative model of relevant shell grammar, not a complete shell interpreter.
Non-shell interpreter bodies — `python3 -c`, `perl -e`, `ruby -e`, `node -e`, `awk` program
bodies — are outside this guard. Dynamic or malformed relevant shell sources are not
executed to discover their value; they return `ask`.

`env -S` nesting past its limit, `command -p`, `sudo`, `env -i`, `env -u PATH` and a changed
`PATH` ahead of a subcommand outside the alias-proof set all return `ask`, which
maps to `deny` under `--runtime codex`.

The alias-proof set is verified against every `git` the running machine's PATH selects. A
Git reachable only by absolute path is never probed and never executed, so the set's
soundness there rests on the version range it was measured over: git 2.7.4 through 2.46.1
by direct alias probe, and git 2.22.5 through 2.47.3 by the shipped check. A Git older than
2.7.4 is outside that range, and argv inspection cannot detect one.

Not run: interception inside a live Claude or Codex session; Codex's own hook-timeout
behaviour, which was not measured; the shipped alias check under Git older than 2.22.5,
where the interpreter this repository targets is unavailable; Git and shell versions
outside git 2.7.4–2.47.3, Apple Git 2.39.5, zsh 5.9, and the current Ubuntu and macOS CI
images; pattern-file contents supplied through `-f`. No merge was performed, and installed
user-home packages were not modified.
