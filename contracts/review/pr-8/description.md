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
`tools/write-mutation-receipt.py` now builds a module-qualified mutation plan across all
three guards, runs each mutation in a private on-disk tree, and emits deterministic shard
fragments. The aggregator rejects incomplete or overlapping evidence and reduces raw suite
receipts to the caught/survived fact and per-result kill reason recorded below.

## What the sweep can express

The element sweep removes members. For a collection that grants an exemption removal makes
the guard stricter, so a removal-only sweep returns a clean result on exactly the sets whose
failure direction it cannot express. Four sets carried a permissive mutation the decision
corpus did not catch: adding one option to the terminal-option set moves a denied engine
hazard to `allow`, and adding `w` to either short-option grammar set does the same through
both the separated and attached spellings. `git grep -n -Ew 'harness\b'` returns no match on
git 2.46.1 while `-Pw` matches, so those denials guard a live silent-wrong-result rather than
a theoretical one.

Two of the four were function-local and lower-case, which the plan's enumeration skips on
both filters, and one duplicated a module-level set that disagreed with it about
`--exec-path`. Bare `--exec-path` ends argument processing rather than taking a value, so the
copy carrying it fed a subcommand scanner no caller invoked and its nine planned mutations
could never be caught. The live path now uses the corrected module-level sets, which moves no
verdict across the recorded corpus, and declared additions cover the direction removal cannot
reach. The addition table is declared rather than generated: it covers the sets it names and
is pinned so an entry cannot be dropped silently.

## What a recorded kill means

A kill is scored when the recorded check count moves. A guard that counts once per element of
the collection under mutation moves that count on any removal, so the kill was decided by
loop structure before any probe ran, and the receipt kept only the outcome. Seventeen of the
twenty-two cross-version alias-proof elements were killed that way, thirteen of them moving a
merged verdict from `deny` to `ask` while every gate stayed green.

The reason is now recorded per result and validated: a survived outcome has one truthful
reason, a crash status is only legitimate where the plan declared it tolerable, and the
separate tally of count-only kills is derived from the results rather than reported. An
arithmetic kill no longer preempts the merged suite where those verdicts are visible, and
composite fixtures assert them there, because each sub-guard grades only its own fixtures and
none could see a verdict that depends on another guard's authority.

`add_group` adds executed plus skipped to the check count and the failure count separately,
so severing a detector's failure return left the count byte-identical while its probes
stopped being able to report. Each group now proves its failure channel by perturbing its own
input and requiring a failure to arrive.

The generator that measures the guards had no external pin; its only digest lived inside the
receipt it writes. It now carries an authored entry in the source registry like the guards
themselves.

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
- `source` and `.` accept a proven literal script path. Computed operands—including shell
  parameters, globs, command/process substitution, descriptors, and active zsh `=name`
  expansion—return `ask`; a hazardous process-substitution producer still returns `deny`.
- Literal zsh aliases are traversed across every body command and the same wrapper grammar
  as direct source. Invoked alias bodies apply ordered `alias`/`unalias` state transitions,
  including wrapper-resolved and caller-completed mutations. A called function, DEBUG trap,
  or `TRAPDEBUG` function—and a bounded, temporally live helper it calls—that can establish
  a source or guarded-Git alias leaves later use unresolved; uncalled functions, helpers
  defined too late, and EXIT-only traps do not. A used zsh global or suffix alias remains
  unresolved executable syntax. An invoked literal alias that contains or reaches a guarded
  Git operation also returns `ask`; explicit `builtin`, `command`, and `exec` lookup prefixes
  retain their non-alias semantics for ordinary command-word aliases.
- Command environment and executable-lookup authority are carried across nested shell,
  alias, heredoc, and here-string boundaries.
- Function definitions are processed in source order. Conditional and short-circuit
  definitions remain uncertain; subshell and non-final pipeline definitions do not replace
  the parent binding. Automatically invoked zsh `TRAP*` definitions are conservatively
  inspected even when a later literal definition or `unfunction` would replace them.
- zsh `=name` expansion is evaluated with the active `EQUALS` state. Startup options are
  parsed only before the first operand. Delimiter-dependent `:W` modifier grammar remains
  unresolved after any stable modifier prefix rather than being guessed literal.
- When multiple predicates or recursive commands apply, `deny` outranks `ask`, which
  outranks `allow`.

The parser declares closed bounds for command bytes, subcommands, tokens, command
wrappers, nested `env -S` sources, expansion depth, shell depth, Git aliases, and function
declarations. Their exact current values and enforcement cases live in the guard and its
registered suites rather than being retyped as final-head measurements here.

## Historical cost measurements

These published timings were taken on the prior reviewed implementation and are retained
as context; this remediation did not remeasure them on the final head.

Per-call latency, one hook process each, on the authoring host:

| input | at `94a519e` | prior reviewed head |
|---|---|---|
| 1,047,552-character legal source | deny at 4.27 s | allow at 2.31 s |
| 80,004 characters of repeated `git` | ask at 33.5 s | ask at 0.29 s |
| 300,004 characters of repeated `=git` | not finished inside 100 s | ask at 0.97 s |

Medians of five runs on the prior reviewed head and three at `94a519e`, one hook process
each.

The first two exceeded the registered timeout, which the measurement above shows is a
fail-open. A fixture at the byte cap holds the 1 MiB limit to being reachable: budget
exhaustion returns `ask`, so `allow` there is only true while a maximum-size command still
classifies inside the budget.

## Verification

The offline acceptance command is `python3 tools/ci-gate.py`. It validates the exact
decision corpus, mutation receipt schema and plan, review includes, workflow bytes, suite
sources, exact guard check cardinalities, and every terminal child receipt.
The decision corpus unions fixed-base and current fixtures with a closed retained-command
manifest, binds its writer source, and enforces an independent 975-command floor, so squash
or rebase topology cannot discard commands that originated in intermediate branch commits.
The ordinary workflow first runs the source-bound harness bootstrap: the harness binds
`ci-gate.py`, and the gate independently binds the harness. This rejects an isolated stub
of either runner only while the declared workflow invokes both. The in-repository workflow
files are trust roots: a workflow-only edit can bypass both runners, and edits to both
workflows can fabricate both in-repo job classes. Reviewer inspection or an externally
administered required workflow must govern that boundary.

The `mutation-proof` pull-request workflow checks out
`github.event.pull_request.head.sha`, runs six deterministic shards, and aggregates their
artifacts with `if: always()`. Missing, duplicated, overlapping, foreign, or stale mutation
IDs fail aggregation. Final publication evidence is collected only after the final commit
is pushed; a prior exact-head run is not evidence for a later fix.

<!-- include: contracts/goldens/mutation-summary.md -->
<!-- generated by tools/write-mutation-receipt.py -- do not edit -->

| module | guarded set | elements | caught | of which unasserted | survived |
|---|---|---:|---:|---:|---:|
| `bash_command_guard.py` | `GUARDS` | 2 | 2 | 0 | 0 |
| `bash_command_guard.py` | `RANK` | 3 | 3 | 0 | 0 |
| `bash_command_guard.py` | `RUNTIMES` | 2 | 1 | 0 | 1 |
| `git_grep_engine_guard.py` | `CONFIG_ENGINE` | 7 | 2 | 0 | 5 |
| `git_grep_engine_guard.py` | `CONTROL_KEYWORDS` | 12 | 7 | 0 | 5 |
| `git_grep_engine_guard.py` | `CROSS_VERSION_ALIAS_PROOF` | 22 | 22 | 0 | 0 |
| `git_grep_engine_guard.py` | `EXEC_WRAPPERS` | 6 | 6 | 0 | 0 |
| `git_grep_engine_guard.py` | `GIT_HAZARD_SUBCOMMANDS` | 17 | 17 | 0 | 0 |
| `git_grep_engine_guard.py` | `GIT_LOG_ENGINE_TOKENS` | 7 | 4 | 0 | 3 |
| `git_grep_engine_guard.py` | `GIT_LOG_GREP_SUBCOMMANDS` | 3 | 3 | 0 | 0 |
| `git_grep_engine_guard.py` | `GIT_LOG_PATTERN_OPTIONS` | 3 | 2 | 0 | 1 |
| `git_grep_engine_guard.py` | `GREP_LONG_BOOLEAN_OPTIONS` | 37 | 10 | 0 | 27 |
| `git_grep_engine_guard.py` | `GREP_LONG_ENGINE` | 4 | 1 | 0 | 3 |
| `git_grep_engine_guard.py` | `GREP_LONG_NEGATED_ENGINE` | 4 | 4 | 0 | 0 |
| `git_grep_engine_guard.py` | `GREP_LONG_OPTIONAL_VALUE` | 2 | 0 | 0 | 2 |
| `git_grep_engine_guard.py` | `GREP_LONG_OPTION_NAMES` | 6 | 1 | 0 | 5 |
| `git_grep_engine_guard.py` | `GREP_LONG_REQUIRED_VALUE` | 6 | 6 | 0 | 0 |
| `git_grep_engine_guard.py` | `GREP_SHORT_ENGINE` | 4 | 4 | 0 | 0 |
| `git_grep_engine_guard.py` | `GREP_SHORT_NOARG` | 17 | 17 | 0 | 0 |
| `git_grep_engine_guard.py` | `GREP_SHORT_OPTIONAL_VALUE` | 2 | 2 | 0 | 0 |
| `git_grep_engine_guard.py` | `GREP_SHORT_PATTERN_ARG` | 3 | 3 | 0 | 0 |
| `git_grep_engine_guard.py` | `GREP_SHORT_VALUE` | 4 | 4 | 0 | 0 |
| `git_grep_engine_guard.py` | `PCRE_ESCAPE_LETTERS` | 21 | 21 | 0 | 0 |
| `git_grep_engine_guard.py` | `REV_PATH_SUBCOMMANDS` | 15 | 14 | 0 | 1 |
| `git_grep_engine_guard.py` | `SHELLS` | 5 | 5 | 0 | 0 |
| `git_grep_engine_guard.py` | `SHELL_NON_FORWARDING_COMMANDS` | 2 | 2 | 0 | 0 |
| `git_grep_engine_guard.py` | `TRUSTED_EXTERNAL_NON_FORWARDING_COMMANDS` | 3 | 3 | 0 | 0 |
| `git_grep_engine_guard.py` | `WRAPPER_TERMINAL_OPTIONS` | 2 | 1 | 0 | 1 |
| `git_grep_engine_guard.py` | `_CLOSED_LIMITS` | 5 | 0 | 0 | 5 |
| `git_grep_engine_guard.py` | `_GIT_GLOBAL_OPTIONS_WITH_VALUES` | 9 | 6 | 0 | 3 |
| `git_grep_engine_guard.py` | `_GIT_TERMINAL_OPTIONS` | 9 | 4 | 0 | 5 |
| `zsh_rev_modifier_guard.py` | `MODS` | 13 | 13 | 0 | 0 |
| `zsh_rev_modifier_guard.py` | `MOD_MEANING` | 13 | 0 | 0 | 13 |
| `zsh_rev_modifier_guard.py` | `MOD_PREFIXES` | 4 | 4 | 0 | 0 |
| `zsh_rev_modifier_guard.py` | `MOD_UNMODELLED` | 1 | 1 | 0 | 0 |

| module | site mutation | outcome |
|---|---|---|
| `bash_command_guard.py` | merged guard function cache scope dropped | caught |
| `git_grep_engine_guard.py` | DEBUG trap alias state dropped | caught |
| `git_grep_engine_guard.py` | TRAPDEBUG function alias state dropped | caught |
| `git_grep_engine_guard.py` | attached exec argv-zero grammar dropped | caught |
| `git_grep_engine_guard.py` | budget wrap deleted | caught |
| `git_grep_engine_guard.py` | builtin trap wrapper adoption dropped | caught |
| `git_grep_engine_guard.py` | called function alias state dropped | caught |
| `git_grep_engine_guard.py` | candidate authority forced trusted | caught |
| `git_grep_engine_guard.py` | decision-budget checkpoint neutered | caught |
| `git_grep_engine_guard.py` | declared helper function alias traversal dropped | caught |
| `git_grep_engine_guard.py` | dynamic source adoption removed | caught |
| `git_grep_engine_guard.py` | dynamic source command identity dropped | caught |
| `git_grep_engine_guard.py` | exec single-dash terminator dropped | caught |
| `git_grep_engine_guard.py` | executed alias Git traversal dropped | caught |
| `git_grep_engine_guard.py` | function record cache cap raised | caught |
| `git_grep_engine_guard.py` | function record decision cache dropped | caught |
| `git_grep_engine_guard.py` | git config count cap dropped | caught |
| `git_grep_engine_guard.py` | git config loop budget dropped | caught |
| `git_grep_engine_guard.py` | git hazard union adoption dropped | caught |
| `git_grep_engine_guard.py` | guarded-tail predicate rescans per word | caught |
| `git_grep_engine_guard.py` | invoked alias body state transition dropped | caught |
| `git_grep_engine_guard.py` | native command checked after alias | caught |
| `git_grep_engine_guard.py` | nested source shell identity dropped | caught |
| `git_grep_engine_guard.py` | nonordinary alias mode tracking dropped | caught |
| `git_grep_engine_guard.py` | nonordinary alias use detection dropped | caught |
| `git_grep_engine_guard.py` | ordinary shell alias Git classification dropped | caught |
| `git_grep_engine_guard.py` | process substitution loses typed operand | caught |
| `git_grep_engine_guard.py` | repeat zero execution boundary dropped | caught |
| `git_grep_engine_guard.py` | same-shell alias mutation wrapper resolution dropped | caught |
| `git_grep_engine_guard.py` | shell alias cycle context reset | caught |
| `git_grep_engine_guard.py` | shell alias forwarding dropped | caught |
| `git_grep_engine_guard.py` | source alias body traversal dropped | caught |
| `git_grep_engine_guard.py` | source alias dynamic command detection dropped | caught |
| `git_grep_engine_guard.py` | source alias embedded operand classification dropped | caught |
| `git_grep_engine_guard.py` | source alias invocation dropped | caught |
| `git_grep_engine_guard.py` | source alias invocation lookup bypass dropped | caught |
| `git_grep_engine_guard.py` | source alias state lookup bypass dropped | caught |
| `git_grep_engine_guard.py` | source alias wrapper resolution dropped | caught |
| `git_grep_engine_guard.py` | source command wrapper omitted | caught |
| `git_grep_engine_guard.py` | source exec wrapper omitted | caught |
| `git_grep_engine_guard.py` | trap action traversal dropped | caught |
| `git_grep_engine_guard.py` | zsh trap function source traversal dropped | caught |
| `zsh_rev_modifier_guard.py` | zsh shared resolver bypassed | caught |
| `zsh_rev_modifier_guard.py` | zsh trap function traversal dropped | caught |
| `zsh_rev_modifier_guard.py` | zsh unmodelled modifier prefix grammar dropped | caught |
| `zsh_rev_modifier_guard.py` | zsh unmodelled modifier uncertainty dropped | caught |

241 of 321 planned mutations are caught; 80 exact mutation IDs remain recorded coverage debt.

Of the 241 caught, 0 were scored only because the recorded check count moved: no assertion failed. A guard whose counter increments once per element of the collection under mutation moves that count on any removal, so those kills are decided by loop structure rather than by detection, and they are not evidence that the suites observe the change.

Not swept: `hooks/guards/git_grep_engine_guard.py::ALIAS_GUARDED` (repeated characters identify an enum word, not a membership charset); `hooks/guards/git_grep_engine_guard.py::ALIAS_HARMLESS` (repeated characters identify an enum word, not a membership charset); `hooks/guards/git_grep_engine_guard.py::ALIAS_UNCERTAIN` (repeated characters identify an enum word, not a membership charset); `hooks/guards/git_grep_engine_guard.py::FIXTURES` (fixture corpus; removing a fixture measures the grader); `hooks/guards/git_grep_engine_guard.py::GREP_LONG_PATTERN_ARG` (empty grammar collection has no element mutation; absence is fixture-pinned); `hooks/guards/git_grep_engine_guard.py::ZSH_EQUALS_OFF` (repeated characters identify an enum word, not a membership charset); `hooks/guards/git_grep_engine_guard.py::ZSH_EQUALS_UNKNOWN` (repeated characters identify an enum word, not a membership charset); `hooks/guards/git_grep_engine_guard.py::_EQUALS_LOOKUP_CACHE` (runtime memoization map, not a guarded membership collection); `hooks/guards/git_grep_engine_guard.py::_GIT_AUTHORITY_CACHE` (runtime memoization map, not a guarded membership collection); `hooks/guards/zsh_rev_modifier_guard.py::FIXTURES` (fixture corpus; removing a fixture measures the grader); `hooks/guards/zsh_rev_modifier_guard.py::UNRESOLVED_GIT` (repeated characters identify an enum word, not a membership charset).
<!-- end include -->

## Limits and not run

The generated mutation summary records current coverage debt rather than presenting it as
a completed target. Surviving set-element mutations remain explicit IDs; site mutations
are not permitted to survive, and neither are declared additions, whose survival would be a
fail-open rather than debt.

The addition set is declared rather than generated, so it covers the collections it names
and is not a claim that every exemption-shaped collection in the tree carries one. The
summary's per-collection unasserted column counts kills scored only by a moved check count,
which are not evidence that the suites observe the change.

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
