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
3. **Adapters at real boundaries.** Hook envelopes, transcript usage records, host-local context,
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

The repository is private, so the marketplace fetch requires existing Git HTTPS credentials with
read access to `ChrisHuie/z-harness`. Authentication remains a user-controlled prerequisite; one
option is to run `gh auth setup-git` after the user completes `gh auth login`. The C9
"credential-free URL" gate checks that the marketplace metadata contains no embedded secret. It does
not make a private repository anonymously readable.

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
| shell guard | `PreToolUse` matcher `Bash`; uncertain patterns may `ask` | `PreToolUse` matcher `Bash`; `ask` maps to `deny` | same predicates, runtime-specific confirmation handling |
| spawn guard | `Agent|Task`; `ask` or `deny` | `Agent` alias over `spawn_agent`; Codex lacks PreToolUse `ask` | warn/unknown maps to deny in Codex |
| question timeout | AskUserQuestion exposes `afkTimeoutMs` | no equivalent contract used here | Claude-only; no parity claim |
| project memory | Claude injects its host-local project `MEMORY.md` | no project memory is packaged; optional Codex-home context only | host-bound data stays runtime-local; no false parity claim |
| subagents | Agent/Task and Claude worktree mechanics | native Codex subagents and SubagentStart hook | shared opt-in policy and capacity gate; runtime orchestration differs |
| cost accounting | requestId/UUID dedupe, max provisional usage | sums per-request `last_token_usage` once, replay dedupe | tokens only; no cross-provider price inference |
| PR delivery state | shared `git`/`gh` evidence command | same command and GitHub API | local commit, remote PR head, and exact-head CI remain separate states |
| skill telemetry | transcript `Skill`/`attributionSkill` evidence | no persisted equivalent asserted | Claude report remains Claude-only |
| status line | `statusLine` in `settings.json` | product UI/CLI status | no emulation |
| permissions/model | `settings.json` | user Codex config and active permission mode | deliberately user-controlled and not translated |

## Policy delivery

Codex normally loads `AGENTS.md` from its global home and from the current repository hierarchy. A
plugin's root `AGENTS.md` is not automatically a global context file, so `hooks/codex_session_start.py`
adds it as SessionStart developer context.

The adapter checks Codex's active global file and the working directory's applicable `AGENTS.md`
chain first. If Codex already sees byte-identical policy, the hook omits the copy. A same-name
`.codex-plugin/plugin.json` in the active repository is not evidence that the bytes are authoritative
and cannot suppress installed policy.

For facts that apply only to one Codex host, the adapter optionally reads
`$CODEX_HOME/z-harness/AGENTS.local.md`. That file lives outside the repository and plugin cache and
is appended only when present. Mandatory policy and the resolved adapter-tool command are budgeted
first. An unreadable or oversized optional file is omitted whole, with a diagnostic section when
space permits; it cannot evict mandatory policy. If mandatory policy itself cannot fit the
30,000-byte hard cap, SessionStart returns `continue:false` and stops before a model request.

The adapter also runs for SubagentStart so a spawned context does not depend on an implicit parent
copy. Its matcherless registration covers every subagent type and constructs the full policy
context on every start. Codex does not mechanically stop SubagentStart on `continue:false`; if
mandatory policy is unavailable, the hook instead injects an explicit stop-work instruction and a
system warning. `wc -c AGENTS.md` regenerates the per-injection policy size, and C9 prints the
current byte count. The adapter never selects a subagent model or widens the parent's
sandbox/approval boundary.

The hook child receives `${PLUGIN_ROOT}`, but an ordinary agent shell call does not. SessionStart
therefore injects fully resolved installed-package commands for `tools/codex-cost.py` and
`tools/pr-delivery-state.py`; shared `AGENTS.md` does not hardcode a Claude path or an unresolvable
Codex placeholder.

## Package hygiene and host-local context

The installable package contains shared policy, skills, hooks, tools, and documentation. It does not
contain `projects/`: those directory names encode absolute authoring-host paths, and their working
notes are neither portable nor suitable for distribution. C9 asserts that a source checkout tracks
zero files under `projects/` and that an installed package contains none.

Ignored Claude project memory can remain on the authoring machine. Codex-specific host facts belong
in `$CODEX_HOME/z-harness/AGENTS.local.md`, outside Git and the plugin cache. Removing host-bound
files from the current tree does not remove older Git objects; repository history must be audited
and scrubbed before changing a private repository to public visibility.

## Hook semantics

`hooks/hooks.json` is discovered by Codex as the plugin's default lifecycle configuration. Commands
resolve scripts through `${PLUGIN_ROOT}`, which points at the installed plugin cache rather than an
assumed checkout path.

Configured events:

- `SessionStart` and `SubagentStart` call `codex_session_start.py`.
- `PreToolUse` on `Bash` calls the shared `bash_command_guard.py`.
- `PreToolUse` on the `Agent` alias calls `spawn_preflight_guard.py --runtime codex`.

Codex and Claude accept the same `hookSpecificOutput.permissionDecision: "deny"` shape for a Bash
PreToolUse block. Codex does not currently support `permissionDecision: "ask"` at this event. Both
the Bash guard and spawn adapter therefore change a Claude confirmation decision into a Codex deny,
with a reason that tells the user what to inspect before retrying. This mapping prevents an invalid
hook response from failing open and allowing the underlying command.

Both PreToolUse adapters validate the top-level object and their matched tool envelope. A malformed
matched payload or internal predicate failure exits 2 only after writing a non-empty blocking reason
to stderr; a bare exit 2 is not treated as a block by Codex. C9 pins the exact package event set,
requires command handlers, rejects async handlers, validates timeout types and matcher regexes, and
C7 pins every required `(event, matcher, script, flags)` tuple including `--runtime codex`.

Hooks are guardrails, not a complete security boundary: specialized tool paths can opt out, and a
PostToolUse hook cannot undo completed side effects. Sandbox and approval policy remain the primary
Codex authority boundary.

## Codex token accounting

Codex session JSONL emits cumulative `total_token_usage` across turns and a per-request
`last_token_usage` alongside each token-count record. Taking a cumulative maximum per turn and then
summing turns overcounts prior work. `tools/codex-cost.py`:

1. walks every JSONL below `$CODEX_HOME/sessions`;
2. sums each valid `last_token_usage` record once;
3. normalizes version-specific missing counters and deduplicates by session plus cumulative and
   per-request identity, independently of the turn where a replay appears;
4. assigns each request its earliest observed timestamp before applying `--since`, so a re-stamped
   fork copy cannot move old usage into a newer window;
5. reports orphan snapshot count and raw token mass, reconciles copies of requests already accounted
   inside turns, and explicitly reports any remaining unattributed mass as excluded;
6. classifies persisted subagent sessions separately and uses session cwd as a project-attribution
   fallback when an embedded turn has no `turn_context`; and
7. treats zero accounted turns as an error.

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
python3 tools/pr-delivery-state.py --selftest
```

For an active PR, run the live publication gate after the push:

```text
python3 tools/pr-delivery-state.py --pr <number> --repo <owner/repo>
```

The command exits zero only when there are no workspace changes, local HEAD equals the GitHub PR
head, the PR is non-conflicting, and both exact-head check and workflow-run lists are non-empty and
successful. Pending CI exits 3; unpublished, conflicting, or failed state exits 1; missing evidence
exits 2.

Validate the package manifest with the bundled Codex plugin validator when available:

```text
python3 <plugin-creator-skill>/scripts/validate_plugin.py .
```

The authoring session cannot prove fresh-session discovery. After installing, use a new task and
exercise at least one request for `git-workflow`, one Bash command that the planted guard rejects,
and one SessionStart with optional Codex-home context both present and absent.

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

**Policy appears twice or disagrees with the checkout**

1. Compare the active global/project `AGENTS.md` bytes with the installed package policy.
2. Run `codex_session_start.py --selftest` to exercise exact-byte suppression.
3. Start a new task after changing an installed plugin; existing task context cannot be retracted.

**Machine-specific guidance does not load**

1. Put host-only instructions in `$CODEX_HOME/z-harness/AGENTS.local.md`.
2. Keep it concise. If the full section does not fit the remaining 30,000-byte budget, the adapter
   drops that section whole while preserving mandatory policy.
3. Start a new task and run `codex_session_start.py --selftest` if the context is still absent.

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
