# Codex hook envelope fixtures

Six envelopes captured on 2026-10-15 from codex-cli 0.154.0 under `codex exec`, with a
per-invocation `-c hooks.<Event>` override registering a command hook that teed its stdin
to a log. One file per event, every key and every type verbatim from the capture:

| file | event | notes |
|---|---|---|
| `C1_session_start.json` | SessionStart | `source` is `startup`; no `turn_id` |
| `C2_user_prompt_submit.json` | UserPromptSubmit | carries `prompt`; no `source` field exists in this schema |
| `C3_pre_tool_use.json` | PreToolUse | `tool_input.command` holds the shell command |
| `C4_post_tool_use.json` | PostToolUse | `tool_response` is the captured stdout |
| `C5_stop.json` | Stop | `stop_hook_active` false, `last_assistant_message` a string |
| `C6_session_end.json` | SessionEnd | `reason` only; no `model`, `permission_mode`, or `turn_id` |
| `C7_stop_null_message_synthetic.json` | Stop | SYNTHETIC: `C5_stop.json` with `last_assistant_message` set to `null`, the other value the schema's `NullableString` admits; never observed on a host |

Scrubbing: `transcript_path` keeps its date-partitioned shape and rollout filename under the
placeholder `/PATH/TO/CODEX_HOME/sessions/...`, and `cwd` is `/PATH/TO/CWD`, because the
package gate rejects absolute host paths in package text. Session, turn, and tool-use ids are
the captured values. The model name is the captured value.

The per-event required-field lists these envelopes satisfy are recorded in
`hooks/harness_check.py` (`CODEX_HOOK_INPUT_REQUIRED`), read from the schemas embedded in the
installed binary; `harness_check.py --verify-runtime` compares that table against the binary,
and C15 decodes every fixture here against it.
