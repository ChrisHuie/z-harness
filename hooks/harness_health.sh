#!/bin/bash
# harness_health — the scheduled weekly health run (launchd: com.zharness.health).
#
# Runs the mechanical gate plus the usage report against the LIVE clone and appends
# to a dated log under ~/.claude/state/. Non-zero harness_check exit is recorded
# loudly at the top of the entry — the log is the surface Chris reads.
#
# Manual run:  bash ~/.claude/hooks/harness_health.sh
# Install:     cp hooks/com.zharness.health.plist ~/Library/LaunchAgents/ && \
#              launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.zharness.health.plist

set -u
ROOT="$HOME/.claude"
LOG_DIR="$ROOT/state"
LOG="$LOG_DIR/harness-health.log"
mkdir -p "$LOG_DIR"

{
  echo "════════════════════════════════════════════════════════════════"
  echo "harness_health $(date '+%Y-%m-%d %H:%M:%S')  HEAD=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo no-git)"
  CHECK_OUT=$(python3 "$ROOT/hooks/harness_check.py" 2>&1)
  CHECK_RC=$?
  if [ "$CHECK_RC" -ne 0 ]; then
    echo "!! harness_check FAILED (exit $CHECK_RC) — failures:"
    echo "$CHECK_OUT" | grep -E "FAIL|failure"
  else
    echo "harness_check: exit 0 ($(echo "$CHECK_OUT" | grep -c PASS) checks)"
  fi
  echo "--- harness_report --since 7d ---"
  python3 "$ROOT/hooks/harness_report.py" --since 7d 2>&1
  echo "--- cc-cost --since 7d ---"
  python3 "$ROOT/tools/cc-cost.py" --since 7d 2>&1
} >> "$LOG" 2>&1

exit 0
