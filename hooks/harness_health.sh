#!/bin/bash
# harness_health — the scheduled weekly health run (launchd: com.zharness.health).
#
# Runs the mechanical gate, the runtime-contract verifier, and the usage report against
# the LIVE install and appends to a dated log under ~/.claude/state/. A failing gate or
# verifier is recorded loudly at the top of the entry — the log is the surface Chris
# reads — and the script's own exit status is non-zero, so launchd and a manual run
# both see the failure instead of a log line that only a reader would notice.
#
# Manual run:  bash ~/.claude/hooks/harness_health.sh
# Install:     cp hooks/com.zharness.health.plist ~/Library/LaunchAgents/ && \
#              launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.zharness.health.plist
#
# ZH_HEALTH_ROOT overrides the install root (default $HOME/.claude) so the exit
# propagation can be proven against a planted tree.

set -u
ROOT="${ZH_HEALTH_ROOT:-$HOME/.claude}"
LOG_DIR="$ROOT/state"
LOG="$LOG_DIR/harness-health.log"
mkdir -p "$LOG_DIR"

CHECK_RC=0
RUNTIME_RC=0
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
  RUNTIME_OUT=$(python3 "$ROOT/hooks/harness_check.py" --verify-runtime 2>&1)
  RUNTIME_RC=$?
  if [ "$RUNTIME_RC" -ne 0 ]; then
    echo "!! harness_check --verify-runtime FAILED (exit $RUNTIME_RC) — failures:"
    echo "$RUNTIME_OUT" | grep -E "FAIL|UNVERIFIED|failure"
  else
    echo "harness_check --verify-runtime: exit 0 ($(echo "$RUNTIME_OUT" | grep -c PASS) anchors)"
  fi
  echo "--- harness_report --since 7d ---"
  python3 "$ROOT/hooks/harness_report.py" --since 7d 2>&1
  echo "--- cc-cost --since 7d ---"
  python3 "$ROOT/tools/cc-cost.py" --since 7d 2>&1
} >> "$LOG" 2>&1

STATUS=0
if [ "$CHECK_RC" -ne 0 ]; then STATUS=1; fi
if [ "$RUNTIME_RC" -ne 0 ]; then STATUS=1; fi
exit "$STATUS"
