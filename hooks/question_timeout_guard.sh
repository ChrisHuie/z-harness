#!/bin/bash
# question_timeout_guard.sh — kill the AskUserQuestion auto-proceed bug.
#
# Anthropic bug (confirmed 2026-07-05, Claude Code 2.1.201): AskUserQuestion
# auto-continues after ~60s idle and injects "proceed using your best
# judgment", even though askUserQuestionTimeout defaults to "never" and is
# unset. A timeout is not an answer. This PostToolUse hook detects the
# timeout signature in the tool result and halts the turn (continue:false)
# so no tokens burn on unwanted autonomous continuation.
#
# Installed 2026-07-05 with explicit one-time owner authorization.
# Registered in ~/.claude/settings.json -> hooks.PostToolUse (matcher:
# AskUserQuestion). Silent when the user actually answered.

input=$(cat)

if printf '%s' "$input" | grep -q "No response after" && \
   printf '%s' "$input" | grep -q "away from keyboard"; then
  printf '%s' '{"continue": false, "stopReason": "AskUserQuestion timed out with no answer - halted by guard hook (timeout is not an answer; known auto-proceed bug). The question is still open: answer it to resume.", "suppressOutput": true}'
fi

exit 0
