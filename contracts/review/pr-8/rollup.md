## Review roll-up

Evidence heads. The gate, CI and clean-clone results below were taken at
`fdee797cbea14542145cff3b039b378d77f69f04`. The mutation figures were measured at that same
head: `contracts/goldens/mutation-receipt.json` records a sha256 of each guard source it was
swept against, and the gate rejects the receipt when those bytes no longer match. Any commit
after `fdee797` on this branch adds this document and changes no guard, tool or contract.

The seven inline threads carry each finding and its disposition; this comment carries only
evidence with no single anchor, and is edited in place rather than reposted.

### Disposition of the original six

| finding | state at this head |
|---|---|
| `/usr/bin/git status` denied | fixed, and re-fixed — see below |
| `UNMODELLED_EXEC_WRAPPERS` arm decided nothing | deleted; the reasoning sits on the block that decides |
| zsh `=git` reached both predicates as an unrelated name | resolved in the shared prefix walk, gated on an unquoted leading `=` |
| `REV_PATH_SUBCOMMANDS` had no upper bound | four scope fixtures plus the membership criterion; forcing the gate true reddens 50 |
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

### Cost, and what the timeout means

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

Medians of five runs at this head and three at `94a519e`, one hook process each.

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

`contracts/goldens/mutation-receipt.json` records two mutation classes at this head: every
element of every guarded set removed one at a time, and six single-site edits anchored by
content digest. 30 sets, 251 elements, 6 site edits. No site mutation survives and no mutation
moved a check count.

The table below is included from `contracts/goldens/mutation-summary.md`, written by the same
run that produced the receipt. `tools/ci-gate.py` fails if this copy differs from that file, so
it cannot go stale here while the receipt moves.

Two rows in the previous version of this section were wrong:

| row | previously | measured |
|---|---|---|
| `is_rev_path_git` forced true | zsh 3 | zsh 50 |
| guarded-tail predicate quadratic again | grep 1 | the suite does not finish, exceeding the 180 s bound |

The second is a different claim rather than a larger number: reverting the backward suffix pass
does not redden a check, it stops the suite completing.

Element margins are not uniform, and the weak end is the part worth acting on. 172 of the 251
elements are held by fewer than two checks and 103 by none — for those, removing the element
leaves both the owning suite and the merged Bash suite green. `MOD_MEANING` and `_CLOSED_LIMITS`
are excluded from that count: the first is read only through `.get(mod, mod)` to build reason
text, and the second is the drift check that would have to redden. The ceiling held in
`tools/ci-gate.py` is the shortfall those margins leave against a target of two,
`sum(target - margin)` and currently 275, not the number of elements below it: the twelve
atoms this branch closed moved from no checks to one and left that count unchanged. The
shortfall can fall and cannot rise without failing.

<!-- include: contracts/goldens/mutation-summary.md -->
<!-- generated by tools/write-mutation-receipt.py -- do not edit -->

| guarded set | module | elements | weakest | strongest | at the weakest |
|---|---|---|---|---|---|
| `CONFIG_ENGINE` | git_grep_engine_guard.py | 7 | 0 | 14 | `basic`, `default`, `ere`, `fixed`, `pcre` |
| `CONTROL_KEYWORDS` | git_grep_engine_guard.py | 11 | 0 | 1 | `do`, `elif`, `else`, `nocorrect`, `noglob`, `until`, and 1 more |
| `CROSS_VERSION_ALIAS_PROOF` | git_grep_engine_guard.py | 22 | 0 | 15 | `archive`, `blame`, `branch`, `cat-file`, `checkout`, `commit`, and 12 more |
| `EXEC_WRAPPERS` | git_grep_engine_guard.py | 6 | 1 | 6 | `setsid` |
| `GIT_HAZARD_SUBCOMMANDS` | git_grep_engine_guard.py | 13 | 0 | 37 | `archive`, `blame`, `cat-file`, `checkout`, `diff`, `ls-tree`, and 4 more |
| `GIT_LOG_ENGINE_TOKENS` | git_grep_engine_guard.py | 7 | 0 | 15 | `--basic-regexp`, `--fixed-strings`, `--perl-regexp`, `-F` |
| `GIT_LOG_GREP_SUBCOMMANDS` | git_grep_engine_guard.py | 3 | 2 | 12 | `rev-list` |
| `GIT_LOG_PATTERN_OPTIONS` | git_grep_engine_guard.py | 3 | 0 | 16 | `--committer` |
| `GREP_LONG_BOOLEAN_OPTIONS` | git_grep_engine_guard.py | 37 | 0 | 6 | `--all-match`, `--break`, `--cached`, `--color`, `--column`, `--count`, and 21 more |
| `GREP_LONG_ENGINE` | git_grep_engine_guard.py | 4 | 0 | 5 | `--basic-regexp`, `--fixed-strings`, `--perl-regexp` |
| `GREP_LONG_NEGATED_ENGINE` | git_grep_engine_guard.py | 4 | 1 | 2 | `--no-basic-regexp`, `--no-extended-regexp`, `--no-fixed-strings` |
| `GREP_LONG_OPTIONAL_VALUE` | git_grep_engine_guard.py | 2 | 0 | 0 | `--color`, `--open-files-in-pager` |
| `GREP_LONG_OPTION_NAMES` | git_grep_engine_guard.py | 6 | 0 | 2 | `--and`, `--index`, `--no-index`, `--not`, `--or` |
| `GREP_LONG_REQUIRED_VALUE` | git_grep_engine_guard.py | 6 | 1 | 1 | `--after-context`, `--before-context`, `--context`, `--max-count`, `--max-depth`, `--threads` |
| `GREP_SHORT_ENGINE` | git_grep_engine_guard.py | 4 | 3 | 196 | `F`, `G` |
| `GREP_SHORT_NOARG` | git_grep_engine_guard.py | 17 | 1 | 51 | `H`, `I`, `L`, `a`, `h`, `i`, and 6 more |
| `GREP_SHORT_OPTIONAL_VALUE` | git_grep_engine_guard.py | 1 | 1 | 1 | `O` |
| `GREP_SHORT_PATTERN_ARG` | git_grep_engine_guard.py | 2 | 4 | 22 | `f` |
| `GREP_SHORT_VALUE` | git_grep_engine_guard.py | 4 | 3 | 5 | `B`, `C` |
| `MODS` | zsh_rev_modifier_guard.py | 13 | 1 | 78 | `A`, `P`, `Q`, `c`, `h`, `q` |
| `MOD_MEANING` | zsh_rev_modifier_guard.py | 13 | 0 | 0 | `A`, `P`, `Q`, `a`, `c`, `e`, and 7 more |
| `MOD_PREFIXES` | zsh_rev_modifier_guard.py | 4 | 1 | 6 | `F` |
| `PCRE_ESCAPE_LETTERS` | git_grep_engine_guard.py | 21 | 1 | 194 | `A`, `B`, `D`, `E`, `H`, `Q`, and 10 more |
| `REV_PATH_SUBCOMMANDS` | zsh_rev_modifier_guard.py | 15 | 0 | 94 | `archive`, `blame`, `checkout`, `diff`, `grep`, `log`, and 3 more |
| `SHELLS` | git_grep_engine_guard.py | 5 | 0 | 37 | `dash`, `ksh` |
| `SHELL_NON_FORWARDING_COMMANDS` | git_grep_engine_guard.py | 2 | 1 | 4 | `printf` |
| `TRUSTED_EXTERNAL_NON_FORWARDING_COMMANDS` | git_grep_engine_guard.py | 3 | 1 | 3 | `/usr/bin/printf` |
| `WRAPPER_TERMINAL_OPTIONS` | git_grep_engine_guard.py | 2 | 0 | 1 | `--version` |
| `_CLOSED_LIMITS` | git_grep_engine_guard.py | 5 | 0 | 0 | `MAX_ENV_SPLITS`, `MAX_PREFIX_DEPTH`, `MAX_SOURCE_DEPTH`, `MAX_SUBCOMMANDS`, `MAX_TOKENS` |
| `_GIT_GLOBAL_OPTIONS_WITH_VALUES` | git_grep_engine_guard.py | 9 | 0 | 0 | `--attr-source`, `--config-env`, `--exec-path`, `--git-dir`, `--namespace`, `--super-prefix`, and 3 more |

| site mutation | module | checks that redden |
|---|---|---|
| budget wrap deleted | git_grep_engine_guard.py | 1 |
| candidate_trusted forced true | git_grep_engine_guard.py | 2 |
| decision-budget checkpoint neutered | git_grep_engine_guard.py | 3 |
| equals PATH-lookup cache dropped | git_grep_engine_guard.py | 1 |
| guarded-tail predicate rescans per word | git_grep_engine_guard.py | timed out |
| is_rev_path_git forced true | zsh_rev_modifier_guard.py | 50 |

30 guarded sets, 251 elements swept one at a time. The weakest element in any set is held by 0 checks, which is the margin between deleting it and a silent fail-open.

Not swept, and why: `ALIAS_GUARDED` (a repeated character, so an enum value spelled as a word rather than a membership charset); `ALIAS_HARMLESS` (a repeated character, so an enum value spelled as a word rather than a membership charset); `ALIAS_UNCERTAIN` (a repeated character, so an enum value spelled as a word rather than a membership charset); `ZSH_EQUALS_OFF` (a repeated character, so an enum value spelled as a word rather than a membership charset); `ZSH_EQUALS_UNKNOWN` (a repeated character, so an enum value spelled as a word rather than a membership charset).
<!-- end include -->

### Verified elsewhere

The full gate runs green on macOS 15 and on ubuntu-24.04 in CI, and the guard suites run
green on linux/arm64 under zsh 5.9 and git 2.43.0. A first draft of
the log-grammar probe used `\b` as its engine oracle and failed on ubuntu-24.04: Git reads it
as a word boundary under ERE on Linux and as a literal `b` on macOS. It turns on syntax now —
`a{2}b` is an interval under ERE and PCRE and five literal characters under BRE, and
`(?:aab)` is a PCRE group and an invalid ERE repeat.

### Verified from a clean clone

`tools/ci-gate.py` was run from a fresh `git clone` of this head, not the authoring
worktree: 10 suites / 0 failures on macOS 15.6.1 with git 2.46.1. The two exact-head CI runs
cover ubuntu-24.04 and macos-15 from their own fresh checkouts, and the guard suites were run
separately on linux/arm64. Eight
equivalence properties check each optimisation against the implementation it replaced,
including the two tail predicates exhaustively for argvs up to length 3 and over 4,000
random ones. Twenty-four `--grep`/`--author`/`--committer` shapes were checked for a
dropped pattern: none. On a machine whose first `git` is a forwarding shim the suite passes
and enumerates three binaries; on one whose `git` is not git at all every affected fixture
degrades to `ask` and the suite reddens.

### Reproduce

From a clean clone, `python3` and `git` only:

```
git clone https://github.com/ChrisHuie/z-harness && cd z-harness
git checkout fdee797cbea14542145cff3b039b378d77f69f04
python3 tools/ci-gate.py                                    # 10 suites / 0 failures
python3 hooks/harness_check.py --selftest                   # 75
python3 hooks/guards/git_grep_engine_guard.py --selftest    # 583
python3 hooks/guards/zsh_rev_modifier_guard.py --selftest   # 239
python3 hooks/bash_command_guard.py --selftest              # 1100
```

Single decisions, without a hook envelope:

```
python3 hooks/guards/git_grep_engine_guard.py --check "git grep -E 'harness\b'"
python3 hooks/guards/zsh_rev_modifier_guard.py --check '=git show $SHA:src/f.py'
```

`tools/write-decision-golden.py` takes no arguments and rewrites
`contracts/goldens/guard-decisions.json` in place. At this head it regenerates byte-identically,
and `tools/ci-gate.py` verifies it as the `decision-golden` step.

No mutation-battery script ships; each row was applied by hand to a copy of the tree. The three
re-measured rows, so they can be repeated:

- **identity block** — in `unwrap_command_prefix`, replace the `errors.append(...)` /
  `guarded_prefix_hazard = True` / `break` arm reached when a command word is neither an
  explicit builtin nor a verified harmless external, with a bare `break`.
- **`is_rev_path_git`** — insert `return True` as the function's first statement.
- **`MODS`** — delete one character from the `MODS` string literal, once per letter.

Ran: `tools/ci-gate.py` (10 suites / 0 failures) from a clean clone on macOS 15, and on
ubuntu-24.04 and macos-15 in CI from their own fresh checkouts; the three guard suites and
the harness suite; the guard suites on linux/arm64; three of the twenty battery rows
re-measured at this head, the other seventeen not; the equivalence properties; the
731-command differential against `654be2a2`; the alias-shadow probe, which re-runs against
every `git` on `PATH` and so covered 2.46.1 and Apple 2.39.5 locally, 2.43.0 on linux/arm64
and 2.54.0 and 2.55.0 on the CI images; the modifier enumeration against zsh 5.9 as built for
arm64-apple-darwin, x86_64-ubuntu-linux and aarch64-unknown-linux; the hook-timeout
experiment on Claude Code 2.1.233.
Not-run: the seventeen unverified battery rows; interception inside a live session; Codex's
hook-timeout behaviour; the shipped alias check under Git older than 2.22.5; Git or shell
versions outside those named above; `-f PATTERNFILE` contents.
