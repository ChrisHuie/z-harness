@AGENTS.md

# Claude Code adapter

The shared policy lives in `AGENTS.md`. Keep this file limited to Claude Code mechanics so Claude
and Codex cannot silently develop different copies of the same rule.

Before substantive action, use the `Skill` tool for every matching skill. A compaction summary that
says a skill was loaded is not the body; call `Skill` again. Do not load `claude-api` unless the task
is writing or debugging code that calls the Anthropic API.

This repository's live Claude installation is `~/.claude`. Skills, `settings.json`, hooks, status
line, and tracked project memories are active in place. A mirror clone is only a synchronization
source. Edits to the user-level `CLAUDE.md` reach the next session or compaction, not the running
context; edits to an existing installed skill hot-reload, while a new skill directory needs a new
session.

Claude's spawn tools are `Agent` and `Task`. Background agents must send their report with
`SendMessage`; never read an agent's `.output` symlink because it is the full JSONL transcript.
Worktree isolation may branch from `main`, so pass the target SHA and make the worker verify it.

The AskUserQuestion AFK control is Claude-specific. After every Claude Code upgrade run:

```text
python3 ~/.claude/hooks/askq_timeout_guard.py --verify-harness
```

Use `python3 ~/.claude/hooks/harness_report.py --since 7d` for Claude skill-delivery evidence and
`python3 ~/.claude/tools/cc-cost.py --since 7d` for Claude token accounting. Claude project memory
lives under `~/.claude/projects/<project>/memory/`; the index is injected into that project.

## Authoring machine

These facts apply to Chris's current macOS authoring host, not to every machine that installs this
repository as a plugin:

- `timeout` is not installed. Commands needing a wall-clock bound must implement their own.
- The system Python fails TLS verification against some hosts. A certificate error from
  `/usr/bin/python3` is an instrument failure; use the vendor CLI instead of the stdlib client.
- After a hard Docker crash, stale Electron singleton files can prevent launch. The symptom is that
  launch exits 0 with no process; the backend reports `unmarshaling start request: unexpected EOF`.
  Deleting `backend.lock` does not fix it. Remove
  `~/Library/Application\ Support/Docker\ Desktop/Singleton{Cookie,Lock,Socket}` and run
  `open -a Docker`. Never cycle Docker during fan-out; polling workers will misread it as
  contention.
