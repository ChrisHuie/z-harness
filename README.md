# z-harness

A version-controlled operating harness for coding agents. One shared policy and one skill tree now
serve both Claude Code and OpenAI Codex; runtime-specific files exist only where the products have
different discovery, hook, transcript, or UI contracts.

The live Claude working tree can remain `~/.claude`. Codex consumes this repository as a plugin, so
the two runtimes do not need copied skill directories that drift independently.

## Install in Codex

```text
codex plugin marketplace add ChrisHuie/z-harness --ref main
codex plugin add z-harness@z-harness
```

Start a new Codex task, open `/hooks`, review the z-harness hook definitions, and trust them. Codex
requires explicit trust for new or changed non-managed hooks; installing the plugin does not bypass
that boundary.

Confirm the installed surface:

```text
codex plugin list --json
python3 <path-to-z-harness>/hooks/harness_check.py --ci
python3 <path-to-z-harness>/tools/codex-cost.py --since 7d
```

The plugin does not select a model, change sandbox/approval policy, copy authentication, or trust
its own hooks. Those remain user-controlled Codex settings.

See [OpenAI/Codex integration](docs/openai-agents.md) for the architecture, compatibility matrix,
update flow, hook semantics, memory projection, and troubleshooting.

## Claude Code installation

The original installation remains supported: the live working tree is `~/.claude`, cloned from
this repository. `~/Documents/GitHub/z-harness` may be a second mirror. Synchronize the clones by
local fetch (`git pull <other-clone-path> main`); pushing to origin remains a separate action.

Prefer harness work in the `~/.claude` clone. A session opened in a mirror may otherwise load the
same shared policy at both user and project scope.

## Shared and runtime-specific surfaces

| path | runtime | purpose |
|---|---|---|
| `AGENTS.md` | shared | canonical always-on operating policy; native project context for Codex |
| `CLAUDE.md` | Claude | thin `@AGENTS.md` bridge plus Claude-only mechanics |
| `skills/` | shared | eleven portable skills; Claude discovers them in place, Codex through the plugin |
| `.codex-plugin/plugin.json` | Codex | plugin identity, install metadata, and skill entry point |
| `.agents/plugins/marketplace.json` | Codex | Git-backed marketplace entry for CLI/app installation |
| `hooks/hooks.json` | Codex | SessionStart/SubagentStart policy injection and PreToolUse guard wiring |
| `settings.json` | Claude | Claude hooks, permissions, model, status line, and UI settings |
| `hooks/bash_command_guard.py` | shared | identical deny predicates over the shared PreToolUse Bash envelope |
| `hooks/spawn_preflight_guard.py` | shared adapter | disk-capacity gate; maps unsupported Codex `ask` decisions to fail-closed `deny` |
| `hooks/askq_timeout_guard.py` | Claude | AskUserQuestion AFK guard; no claimed Codex equivalent |
| `hooks/codex_session_start.py` | Codex | injects shared policy and nearest tracked project memory without duplicate policy |
| `hooks/harness_check.py` | shared | mechanical gate over skills, hooks, context files, and plugin packaging |
| `hooks/harness_report.py` | Claude | transcript evidence for Claude skill firing/reference reads |
| `tools/cc-cost.py` | Claude | Claude request-deduplicated token accounting |
| `tools/codex-cost.py` | Codex | Codex turn-deduplicated cumulative token accounting |
| `projects/*/memory/` | shared data | authored Claude memory indexes; Codex receives the nearest index as soft context |
| `harness-audit-20260801/` | record | measurements and decisions behind the original Claude rebuild |

## Health

```text
python3 hooks/harness_check.py
python3 hooks/harness_check.py --selftest
python3 hooks/bash_command_guard.py --selftest
python3 hooks/spawn_preflight_guard.py --selftest
python3 hooks/codex_session_start.py --selftest
python3 hooks/askq_timeout_guard.py --selftest
python3 hooks/askq_timeout_guard.py --verify-harness
python3 hooks/harness_report.py --selftest
python3 tools/cc-cost.py --selftest
python3 tools/codex-cost.py --selftest
python3 tools/run-skill-evals.py --validate
```

CI runs `python3 hooks/harness_check.py --ci` on every push and pull request. Local mode adds
machine-specific Claude anchors. `--selftest` plants defects and proves each check family can turn
red; a zero-input scan is an error, not a clean verdict.

Skill contract eval validation is free and offline. `tools/run-skill-evals.py --run` executes
headless model scenarios and spends API budget, so it remains manual.

## Mechanics worth knowing

- `AGENTS.md` is the shared source. `CLAUDE.md` must remain a bridge plus Claude-specific addendum;
  duplicating shared policy across both files is a regression.
- Codex plugins are installed into a cache. Refresh the marketplace and reinstall after changing a
  plugin version, then use a new task so skill and hook discovery starts from fresh state.
- Codex will skip changed plugin hooks until the user reviews their new hash in `/hooks`.
- Claude skills fire through the imperative routing rule in the shared policy. Editing an existing
  installed skill hot-reloads in Claude; a new skill directory requires a new session.
- `git clean -fdx` in a live `~/.claude` clone deletes ignored transcripts. Plain `-fd` preserves
  them. Never use `-x` there.
- `.gitignore` is an allowlist. New authored surfaces must be explicitly included or git cannot see
  them.
