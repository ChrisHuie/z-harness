# OpenAI/Codex integration

This integration gives Codex the same portable policy and skill bodies as Claude Code while
preserving runtime-specific safety contracts. It promises equivalent operating intent, not
identical wire events, configuration files, transcript schemas, or user interfaces.

The supported OpenAI runtime in this package is Codex CLI and Codex desktop's local plugin layer.
The OpenAI Agents SDK is an application framework rather than a Codex context/plugin host; using
these policies in an SDK application requires an explicit runner adapter and is not claimed here.

## Design contract

1. **One policy source.** Shared operating rules live in root `AGENTS.md`. Claude imports it from a
   short `CLAUDE.md`; Codex discovers it natively in this repository or receives it from the
   plugin's SessionStart hook elsewhere.
2. **One skill source.** Root `skills/` is both Claude's live skill tree and the Codex plugin's
   declared skill directory. No generated copy is authoritative.
3. **Adapters at real boundaries.** Hook envelopes, transcript usage records, memory discovery,
   and status UI remain runtime-specific.
4. **User authority stays external.** The package does not alter authentication, model choice,
   sandbox mode, approval policy, provider configuration, or hook trust.
5. **Unknown safety states do not become passes.** Where Claude can request confirmation from a
   PreToolUse hook but Codex currently cannot, the Codex adapter denies and tells the user what to
   inspect before retrying.

## Installation

Current Codex releases support Git-backed plugin marketplaces. Add this repository as a marketplace,
then install its package:

```text
codex plugin marketplace add ChrisHuie/z-harness --ref main
codex plugin add z-harness@z-harness
```

Open a new Codex task after installation. Use `/hooks` in Codex CLI to review and trust each
z-harness command hook. Non-managed hooks are keyed to their exact definition; after a hook changes,
Codex marks the new hash for review and skips it until the user trusts it.

Inspect the resulting installation without exposing credentials:

```text
codex plugin marketplace list --json
codex plugin list --json
```

The desktop app can also add the marketplace and plugin through its Plugins surface. Installation
does not import Claude chats or settings. If those are also wanted, Codex's separate `/import` flow
can import selected Claude Code setup and recent chats without deleting the existing setup.

## Update or remove

The manifest uses semantic versions. A release that changes packaged bytes should update the
version. Refresh the Git marketplace snapshot and reinstall the selector, then start a new task:

```text
codex plugin marketplace upgrade z-harness
codex plugin add z-harness@z-harness
```

If the installed version remains unchanged, remove that cached install before adding it again:

```text
codex plugin remove z-harness@z-harness
codex plugin add z-harness@z-harness
```

Removal affects the Codex plugin cache/config only. It does not delete this Git checkout or the
Claude Code live tree.

## Compatibility matrix

| capability | Claude Code | Codex | contract |
|---|---|---|---|
| always-on policy | user `CLAUDE.md` imports `AGENTS.md` | native repo `AGENTS.md`; plugin SessionStart elsewhere | same shared policy bytes, runtime addenda separate |
| skill discovery | `~/.claude/skills/` | plugin `skills` entry | same directories and `SKILL.md` bodies |
| skill invocation | `Skill` tool / slash command / implicit routing | explicit `$skill-name` or implicit metadata match | equivalent workflow selection, different invocation surface |
| shell guard | `PreToolUse` matcher `Bash` | `PreToolUse` matcher `Bash` | same input fields and deny output shape |
| spawn guard | `Agent|Task`; `ask` or `deny` | `Agent` alias over `spawn_agent`; Codex lacks PreToolUse `ask` | warn/unknown maps to deny in Codex |
| question timeout | AskUserQuestion exposes `afkTimeoutMs` | no equivalent contract used here | Claude-only; no parity claim |
| project memory | Claude injects project `MEMORY.md` | SessionStart chooses nearest tracked project index | same authored index, labelled soft/stale in Codex |
| subagents | Agent/Task and Claude worktree mechanics | native Codex subagents and SubagentStart hook | shared opt-in policy and capacity gate; runtime orchestration differs |
| cost accounting | requestId/UUID dedupe, max provisional usage | max cumulative snapshot per turn id, replay dedupe | tokens only; no cross-provider price inference |
| skill telemetry | transcript `Skill`/`attributionSkill` evidence | no persisted equivalent asserted | Claude report remains Claude-only |
| status line | `statusLine` in `settings.json` | product UI/CLI status | no emulation |
| permissions/model | `settings.json` | user Codex config and active permission mode | deliberately user-controlled and not translated |

## Policy delivery

Codex normally loads `AGENTS.md` from its global home and from the current repository hierarchy. A
plugin's root `AGENTS.md` is not automatically a global context file, so `hooks/codex_session_start.py`
adds it as SessionStart developer context.

The adapter checks Codex's active global file and the working directory's applicable `AGENTS.md`
chain first. If Codex already sees byte-identical policy, the hook omits the copy. This prevents
the harness source tree or a linked global install from receiving the same policy twice.

The adapter also runs for SubagentStart so a spawned context does not depend on an implicit parent
copy. It never selects a subagent model or widens the parent's sandbox/approval boundary.

## Project-memory projection

Tracked memory lives at `projects/<claude-project-slug>/memory/MEMORY.md`. On SessionStart, the
adapter walks from the active `cwd` toward the filesystem root and selects the nearest matching
index. The injected section says that memory is potentially stale data, not instructions or
current-state proof.

Only the index is injected. Referenced memory files remain on disk and can be read when needed.
Credentials, untracked transcripts, and native Codex memory are not copied. The combined policy and
memory context has a 30,000-byte fail-closed cap.

## Hook semantics

`hooks/hooks.json` is discovered by Codex as the plugin's default lifecycle configuration. Commands
resolve scripts through `${PLUGIN_ROOT}`, which points at the installed plugin cache rather than an
assumed checkout path.

Configured events:

- `SessionStart` and `SubagentStart` call `codex_session_start.py`.
- `PreToolUse` on `Bash` calls the shared `bash_command_guard.py`.
- `PreToolUse` on the `Agent` alias calls `spawn_preflight_guard.py --runtime codex`.

Codex and Claude accept the same `hookSpecificOutput.permissionDecision: "deny"` shape for a Bash
PreToolUse block. Codex does not currently support `permissionDecision: "ask"` at this event. The
spawn adapter therefore changes a Claude warning/unknown decision into a Codex deny, with a reason
that tells the user to inspect capacity and retry.

Hooks are guardrails, not a complete security boundary: specialized tool paths can opt out, and a
PostToolUse hook cannot undo completed side effects. Sandbox and approval policy remain the primary
Codex authority boundary.

## Codex token accounting

Codex session JSONL emits cumulative `total_token_usage` snapshots during a turn. Adding all of
those snapshots overcounts. `tools/codex-cost.py`:

1. walks every JSONL below `$CODEX_HOME/sessions`;
2. keys observations by persisted turn id across files;
3. takes the maximum value of each cumulative usage field per turn;
4. deduplicates copied/replayed turns;
5. classifies persisted subagent sessions separately; and
6. treats zero accounted turns as an error.

Cached input is a subset of input and reasoning output is a subset of output. The report does not
sum those subsets into total tokens again and does not infer dollar cost from a hard-coded price
table.

## Validation

Run the shared mechanical gate and its planted-defect proof:

```text
python3 hooks/harness_check.py --ci
python3 hooks/harness_check.py --selftest
```

Run focused Codex adapter selftests:

```text
python3 hooks/codex_session_start.py --selftest
python3 hooks/bash_command_guard.py --selftest
python3 hooks/spawn_preflight_guard.py --selftest
python3 tools/codex-cost.py --selftest
```

Validate the package manifest with the bundled Codex plugin validator when available:

```text
python3 <plugin-creator-skill>/scripts/validate_plugin.py .
```

The authoring session cannot prove fresh-session discovery. After installing, use a new task and
exercise at least one request for `git-workflow`, one Bash command that the planted guard rejects,
and one project with a tracked memory index.

## Troubleshooting

**Skills do not appear**

1. Confirm `codex plugin list --json` reports `z-harness` installed and enabled.
2. Refresh the marketplace and reinstall after a version change.
3. Start a new task; skill discovery is session-scoped.

**Hooks do not run**

1. Open `/hooks` and look for an untrusted or changed definition.
2. Confirm the plugin remains enabled.
3. Run the hook's `--selftest` directly from the source checkout.
4. Do not use `--dangerously-bypass-hook-trust` for ordinary interactive setup.

**Project memory does not load**

1. Resolve the active task's exact `cwd`.
2. Confirm a tracked `projects/<slug>/memory/MEMORY.md` exists for that directory or an ancestor.
3. Run `codex_session_start.py --selftest`; do not infer success from the absence of an error.

**A Codex spawn is denied in the warning band**

Codex PreToolUse cannot return `ask`. Check the data-volume percentage, reclaim space or choose a
roomier `TMPDIR`, then retry. This is an intentional fail-closed translation, not protocol parity.

## Source contracts

- [Codex `AGENTS.md` discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md.md)
- [Codex hooks](https://learn.chatgpt.com/docs/hooks.md)
- [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins)
- [OpenAI skill model](https://developers.openai.com/plugins/concepts/skills)
- [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents.md)
- [Import from another agent](https://learn.chatgpt.com/docs/import.md)
