## Review roll-up

Historical measurements below were taken on earlier revisions and are context only; some
sections predate exact-head recording. They do not stand in for final-head evidence. The
generated mutation section is bound to the current
guard and generator digests; exact-head CI and delivery state are collected again only
after the final implementation commit is published.

The inline threads carry each finding and its disposition; this comment carries only
evidence with no single anchor, and is edited in place rather than reposted.

### Disposition of the original six

| finding | historical disposition before this remediation |
|---|---|
| `/usr/bin/git status` denied | fixed, and re-fixed — see below |
| `UNMODELLED_EXEC_WRAPPERS` arm decided nothing | deleted; the reasoning sits on the block that decides |
| zsh `=git` reached both predicates as an unrelated name | resolved in the shared prefix walk, gated on an unquoted leading `=` |
| `REV_PATH_SUBCOMMANDS` had no upper bound | scope fixtures plus a documented membership criterion |
| non-shell interpreter edge unstated | named in the module docstring and at the fallback that stops there |
| parser cost at the byte cap | see Cost, below |

### The first finding regressed, and is fixed differently

Between the reviewed head and the previous one, the remedy was replaced: naming a Git other
than the one `PATH` resolves raised again, and a second rule refused on any wrapper that
changes executable lookup. Measured against both `654be2a2` and `ccab71e`:

```
                                          base   ccab71e  before  now
/usr/bin/git status --short               allow  allow    ask     allow
sudo git status --short                   allow  allow    ask     allow
env -i git status --short                 allow  allow    ask     allow
command -p git status --short             allow  allow    ask     allow
/usr/bin/git grep -E 'harness\b'          deny   deny     ask     deny
sudo git grep -nE 'harness\b'             deny   deny     ask     deny
command -p git grep -nE 'harness\b'       deny   deny     ask     deny
```

`ask` maps to `deny` under `--runtime codex`, so the top rows were a hard block there, and
the bottom rows lost a proven deny. The regex engine is selected by argv, not by which
binary runs: `git grep -E 'harness\b'` returns the `harnessb` line and `-P` the intended one
on git 2.46.1 and Apple Git 2.39.5 alike.

One rule replaces both. An unsettled executable may be classified only from
`CROSS_VERSION_ALIAS_PROOF` — names an ambient alias cannot redirect in any supported Git.

The first version of that set was itself unsound, in the same way the remedy before it was.
It was derived from `--list-cmds=builtins`, but git-config(1) ties alias shadowing to the
command EXISTING, not to it being builtin. Asked directly across git 2.7.4, 2.15.4, 2.17.1,
2.20.4, 2.30.6, 2.39.5, 2.45.4 and 2.46.1:

```
stash        builtin only since 2.22, never shadowed anywhere tested
restore      builtin on 2.46.1, SHADOWED on every Git before 2.23
maintenance  builtin on 2.46.1, SHADOWED on every Git before 2.29
```

`restore` is a guarded subcommand, so an alternate Git older than 2.23 with an ambient
`alias.restore` was a fail-open. Both names are removed and the set renamed, because
`stash` belongs in it while not being a builtin.

`check_alias_shadowing_against_installed_gits` asks each `git` on `PATH` the same question
rather than inferring it, prints that scan set including which guarded subcommands are NOT
alias-proof, and treats zero binaries as a failure. It does not depend on `--list-cmds`,
which only exists since git 2.18. Proved end-to-end at the version boundary: with `restore`
re-added, the shipped check reddens under git 2.22.5 naming the name and the binary, and
passes under 2.24.4.

The wrapper rule left behind decided nothing once that set existed — neutering it moved no
verdict across 745 commands — so it is deleted rather than kept as something that reads like
coverage.

### Historical cost measurements and timeout behavior

A PreToolUse `type: "command"` hook that exceeds its registered timeout does not block: five
of five runs executed the tool call, against a control in the same harness that answered
immediately with `deny` and did block. Exceeding five seconds is the guard not applying.

That reclassifies the parser cost. Two tail predicates rescanned the whole argv per candidate
word:

```
80,004 characters of repeated `git`     ask 33.5 s      -> ask 0.29 s
300,004 characters of repeated `=git`   >100 s, killed  -> ask 0.97 s
1,047,552-character legal source        deny 4.27 s     -> allow 2.31 s
```

Medians of five runs on the prior reviewed implementation and three at `94a519e`, one hook
process each. They are retained as historical context, not final-head timing evidence.

Both of the first two exceeded the timeout, so both were commands the guard would not have
judged. One backward suffix pass, a memoised `=name` PATH walk, and five scan early-outs
close it, with counted rather than timed controls: four times the tokens must cost about four
times the work, and a repeated live `=name` must cost one PATH walk.

### Three defects found while closing the above

- Budget exhaustion returned `deny`, not `ask`. `_check_decision_budget` raises from about
  twenty parser call sites; two were wrapped and the rest were not, so an exhausted budget
  escaped into the merged guard's `except BaseException` arm. `echo` at 768 KiB and above
  denied, five of five. The mechanism had no control at all: replacing the checkpoint body
  with `return None` left all four suites green.
- Exceeding `MAX_ENV_SPLITS` allowed. The walk stopped with an unread blob and set no hazard
  hint, so a fifth `env -S` layer wrapping a live `git grep -E 'harness\b'` was allowed.
  Depth 4 denied, depth 5 allowed.
- `log`, `shortlog` and `rev-list` were parsed with `git grep`'s option table. Any option
  carrying a separated value that the table does not model donated that value to the
  positional-pattern slot and the real `--grep` pattern was dropped: 16 of 69 hazard-carrying
  spellings allowed, including `-n 5`, `--since`, `--skip`, `--date`, `-l`, `-I`, `-O`,
  `--glob`, `--exclude`, `--encoding`, `--inter-hunk-context`, `--diff-algorithm`,
  `--word-diff-regex`, `--ws-error-highlight`, `--anchored` and `--output-indicator-new`.

### Controls that were asserting their own inputs

Four of the closed limits could be raised to effectively unbounded with every suite green;
each now has a boundary pair, with literal sizes and a drift check, because sizes derived
from the constants under test moved with the mutation. The registered Bash suite timeout was
asserted against its own table entry — setting it below the suite's runtime left the harness
selftest green — and is now a literal plus a measured-margin requirement in C1. The gate's
hook-timeout mutation selected `PreToolUse[0]` by position and reddened on an unrelated
reorder; it selects by command now.

### What the suites catch

`contracts/goldens/mutation-receipt.json` records a deterministic, module-qualified plan:
every eligible guarded-set element is removed once, and selected repaired adoption seams are
edited once at content-hashed anchors. Each mutation runs the real suite from a private on-disk
tree. The pull-request workflow shards the same plan and rejects incomplete, duplicated,
overlapping, foreign, or stale fragments.

The table below is included from `contracts/goldens/mutation-summary.md`, written by the same
run that produced the receipt. `tools/ci-gate.py` derives the canonical summary bytes from the
strict receipt and then requires this copy and the description copy to match, so a coordinated
summary/include edit cannot detach the published figures from the receipt.

Two rows in the previous version of this section were wrong:

| row | previously | measured |
|---|---|---|
| `is_rev_path_git` forced true | zsh 3 | zsh 50 |
| guarded-tail predicate quadratic again | grep 1 | the suite does not finish, exceeding the 180 s bound |

The second is a different claim rather than a larger number: reverting the backward suffix pass
does not redden a check, it stops the suite completing.

Raw fragments retain terminal counts and typed process outcomes. The tracked receipt uses
the cross-platform caught/survived fact and exact mutation IDs. Surviving set-element
mutations are explicit coverage debt; no site mutation may survive, and the debt ceiling
may fall but not rise.

<!-- include: contracts/goldens/mutation-summary.md -->
<!-- generated by tools/write-mutation-receipt.py -- do not edit -->

| module | guarded set | elements | caught | survived |
|---|---|---:|---:|---:|
| `bash_command_guard.py` | `GUARDS` | 2 | 2 | 0 |
| `bash_command_guard.py` | `RANK` | 3 | 3 | 0 |
| `bash_command_guard.py` | `RUNTIMES` | 2 | 1 | 1 |
| `git_grep_engine_guard.py` | `CONFIG_ENGINE` | 7 | 2 | 5 |
| `git_grep_engine_guard.py` | `CONTROL_KEYWORDS` | 12 | 7 | 5 |
| `git_grep_engine_guard.py` | `CROSS_VERSION_ALIAS_PROOF` | 22 | 22 | 0 |
| `git_grep_engine_guard.py` | `EXEC_WRAPPERS` | 6 | 6 | 0 |
| `git_grep_engine_guard.py` | `GIT_HAZARD_SUBCOMMANDS` | 17 | 17 | 0 |
| `git_grep_engine_guard.py` | `GIT_LOG_ENGINE_TOKENS` | 7 | 4 | 3 |
| `git_grep_engine_guard.py` | `GIT_LOG_GREP_SUBCOMMANDS` | 3 | 3 | 0 |
| `git_grep_engine_guard.py` | `GIT_LOG_PATTERN_OPTIONS` | 3 | 2 | 1 |
| `git_grep_engine_guard.py` | `GREP_LONG_BOOLEAN_OPTIONS` | 37 | 10 | 27 |
| `git_grep_engine_guard.py` | `GREP_LONG_ENGINE` | 4 | 1 | 3 |
| `git_grep_engine_guard.py` | `GREP_LONG_NEGATED_ENGINE` | 4 | 4 | 0 |
| `git_grep_engine_guard.py` | `GREP_LONG_OPTIONAL_VALUE` | 2 | 0 | 2 |
| `git_grep_engine_guard.py` | `GREP_LONG_OPTION_NAMES` | 6 | 1 | 5 |
| `git_grep_engine_guard.py` | `GREP_LONG_REQUIRED_VALUE` | 6 | 6 | 0 |
| `git_grep_engine_guard.py` | `GREP_SHORT_ENGINE` | 4 | 4 | 0 |
| `git_grep_engine_guard.py` | `GREP_SHORT_NOARG` | 17 | 17 | 0 |
| `git_grep_engine_guard.py` | `GREP_SHORT_OPTIONAL_VALUE` | 1 | 1 | 0 |
| `git_grep_engine_guard.py` | `GREP_SHORT_PATTERN_ARG` | 2 | 2 | 0 |
| `git_grep_engine_guard.py` | `GREP_SHORT_VALUE` | 4 | 4 | 0 |
| `git_grep_engine_guard.py` | `PCRE_ESCAPE_LETTERS` | 21 | 21 | 0 |
| `git_grep_engine_guard.py` | `REV_PATH_SUBCOMMANDS` | 15 | 6 | 9 |
| `git_grep_engine_guard.py` | `SHELLS` | 5 | 5 | 0 |
| `git_grep_engine_guard.py` | `SHELL_NON_FORWARDING_COMMANDS` | 2 | 2 | 0 |
| `git_grep_engine_guard.py` | `TRUSTED_EXTERNAL_NON_FORWARDING_COMMANDS` | 3 | 3 | 0 |
| `git_grep_engine_guard.py` | `WRAPPER_TERMINAL_OPTIONS` | 2 | 1 | 1 |
| `git_grep_engine_guard.py` | `_CLOSED_LIMITS` | 5 | 0 | 5 |
| `git_grep_engine_guard.py` | `_GIT_GLOBAL_OPTIONS_WITH_VALUES` | 9 | 0 | 9 |
| `zsh_rev_modifier_guard.py` | `MODS` | 13 | 13 | 0 |
| `zsh_rev_modifier_guard.py` | `MOD_MEANING` | 13 | 0 | 13 |
| `zsh_rev_modifier_guard.py` | `MOD_PREFIXES` | 4 | 4 | 0 |
| `zsh_rev_modifier_guard.py` | `MOD_UNMODELLED` | 1 | 1 | 0 |

| module | site mutation | outcome |
|---|---|---|
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

218 of 307 planned mutations are caught; 89 exact mutation IDs remain recorded coverage debt.

Not swept: `hooks/guards/git_grep_engine_guard.py::ALIAS_GUARDED` (repeated characters identify an enum word, not a membership charset); `hooks/guards/git_grep_engine_guard.py::ALIAS_HARMLESS` (repeated characters identify an enum word, not a membership charset); `hooks/guards/git_grep_engine_guard.py::ALIAS_UNCERTAIN` (repeated characters identify an enum word, not a membership charset); `hooks/guards/git_grep_engine_guard.py::FIXTURES` (fixture corpus; removing a fixture measures the grader); `hooks/guards/git_grep_engine_guard.py::GREP_LONG_PATTERN_ARG` (empty grammar collection has no element mutation; absence is fixture-pinned); `hooks/guards/git_grep_engine_guard.py::ZSH_EQUALS_OFF` (repeated characters identify an enum word, not a membership charset); `hooks/guards/git_grep_engine_guard.py::ZSH_EQUALS_UNKNOWN` (repeated characters identify an enum word, not a membership charset); `hooks/guards/git_grep_engine_guard.py::_EQUALS_LOOKUP_CACHE` (runtime memoization map, not a guarded membership collection); `hooks/guards/git_grep_engine_guard.py::_GIT_AUTHORITY_CACHE` (runtime memoization map, not a guarded membership collection); `hooks/guards/zsh_rev_modifier_guard.py::FIXTURES` (fixture corpus; removing a fixture measures the grader); `hooks/guards/zsh_rev_modifier_guard.py::UNRESOLVED_GIT` (repeated characters identify an enum word, not a membership charset).
<!-- end include -->

### Reproduce and final-head evidence

The offline acceptance command is:

```
python3 tools/ci-gate.py
```

`tools/write-decision-golden.py` normally verifies byte identity and refuses a changed
corpus or verdict unless `--accept-decision-changes` is supplied. The mutation plan can be
inspected without executing it:

```
python3 tools/write-decision-golden.py
python3 tools/write-mutation-receipt.py --list-plan
```

The `mutation-proof` pull-request workflow runs the full plan in private trees, uploads raw
fragments, and aggregates them at the exact pull-request head. The aggregator recomputes
every raw caught/survived classification, rejects incomplete shard evidence, and compares
the result with the tracked receipt and summary. The ordinary offline gate separately
requires byte-identical summary includes in this roll-up and the PR description.

The ordinary workflow runs the source-bound harness bootstrap before `ci-gate.py`; each
runner binds the other's reviewed source. That detects an isolated runner stub only while
the declared workflow invokes both. The in-repository workflows are trust roots: a
workflow-only edit can bypass both runners, and edits to both workflows can fabricate both
job classes. Reviewer inspection or an externally administered required workflow must
govern that boundary.

Final-head publication evidence is deliberately not claimed in this tracked draft. Before
the roll-up is published, the exact head must have non-empty successful ordinary and
mutation workflow runs, all expected shard jobs, and a successful aggregate job. A prior
head's clean-clone or CI results do not establish those facts for the final fix.

Not run by the repository gate: interception inside a live Claude or Codex session;
Codex's hook-timeout behaviour; the shipped alias check under Git older than 2.22.5; Git or
shell versions outside the ranges named above; pattern-file contents supplied through
`-f`.
