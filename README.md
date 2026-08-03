# z-harness

The Claude Code harness for this machine, version-controlled in place: **the live working
tree IS `~/.claude`**, a clone of this repo. `~/Documents/GitHub/z-harness` is a second
clone used as a mirror. The two sync by local fetch (`git pull <other-clone-path> main`) —
pushing to origin is a separate, deliberate act.

Prefer doing harness work in the `~/.claude` clone: a session opened in the mirror loads
the identical `CLAUDE.md` twice (user-global + project), ~3.2k tokens of measured
duplication per dispatch.

## Layout

| path | what |
|---|---|
| `CLAUDE.md` | the always-on file, injected into every dispatch in every project (read at session start — edits reach the *next* session, not a running one) |
| `skills/` | 11 user skills; method bodies capped at 5,000 chars after frontmatter, authoring bodies at 500 lines; shared `references/` copies must stay byte-identical |
| `hooks/` | PreToolUse guards (`bash_command_guard` → `guards/`, `spawn_preflight_guard`), the AskUserQuestion AFK guard, `harness_check`, `harness_report`, the weekly health wrapper |
| `tools/` | `cc-cost.py` — token accounting with the four verified traps closed |
| `settings.json` | hook wiring (all entries carry timeouts), permissions, model. `/model` writes here — commit the churn deliberately |
| `harness-audit-20260801/` | the record: every measurement and decision behind the 2026-08-01/02 rebuild. Read `STATE.md` first; `ROUTING-RULE.md` is the where-does-a-fact-go procedure; `drafts/split2/PRINCIPLE-REGISTRY.md` maps every rule to its destination |
| `projects/*/memory/` | the authored memory layer (tracked); transcripts and the rest of `projects/` stay ignored |

## Health

```
python3 hooks/harness_check.py            # the mechanical gate — 8 check families,
                                          # each proven red on planted defects (--selftest)
python3 hooks/bash_command_guard.py --selftest
python3 hooks/askq_timeout_guard.py --selftest
python3 hooks/askq_timeout_guard.py --verify-harness   # after every CLI upgrade
python3 hooks/harness_report.py --since 7d             # did skills fire, were refs read
python3 tools/cc-cost.py --since 7d                    # deduped token accounting
```

CI runs `harness_check --ci` on every push (`.github/workflows/check.yml`). A weekly
launchd job (`com.zharness.health`, Monday 09:00) runs the full set and appends to
`~/.claude/state/harness-health.log`.

Skill contract evals: `python3 tools/run-skill-evals.py --validate` is free and offline;
`--run` executes scenarios headless against the live harness and spends API budget —
manual only.

## Mechanics worth knowing

- Skills fire through the imperative routing table in `CLAUDE.md` (measured 14/14 with it,
  2/14 without, n=9/arm). Editing an installed skill hot-reloads mid-session; a brand-new
  skill directory needs a session restart.
- `git clean -fdx` in `~/.claude` would delete every ignored file — transcripts included.
  Plain `-fd` is safe. Never `-x` here.
- The `.gitignore` is an allowlist: new authored surface must be opted in or git cannot
  see it.
