#!/usr/bin/env python3
"""spawn_preflight_guard — PreToolUse gate on the agent-spawn tools (Agent|Task).

The rule this mechanizes (previously prose-only in CLAUDE.md): preflight EVERY
dispatch. At 100% disk every command fails ENOSPC on unrelated paths and
mutation agents emit false findings — infra failure is neither pass nor fail.
`agent-dispatch`'s own body: "a preflight written as prose is a reminder, not a
gate."

What it gates: the DATA volume (`/System/Volumes/Data` on macOS — `df /` shows
the sealed system volume, not where files land; elsewhere `/`).
  use% >= DENY_PCT (default 95)  -> deny the spawn, name the reclaim rule
  use% >= WARN_PCT (default 90)  -> ask (user confirms the spawn knowingly)
  else                           -> allow, silent

Docker is deliberately NOT probed here: the hook cannot know whether the agent
needs a DB, and `docker info` adds latency to every spawn. The CLAUDE.md
preflight line keeps `docker info` for DB-needing dispatches.

Env overrides (selftest + tuning):
  SPAWN_GUARD_DF_PCT   integer 0-100, replaces the live df reading
  SPAWN_GUARD_DENY_PCT / SPAWN_GUARD_WARN_PCT

Contract (same as bash_command_guard, verified in-binary 2.1.220): stdout JSON
{"hookSpecificOutput": {"hookEventName": "PreToolUse",
 "permissionDecision": "deny|ask|allow", "permissionDecisionReason": "..."}}

Exit codes: 0 decision emitted or out of scope · 1 selftest failure ·
2 usage error / unreadable df.
"""
import json
import os
import re
import subprocess
import sys

VERSION = "1.0.0"
SPAWN_TOOLS = {"Agent", "Task"}
DATA_VOLUME = "/System/Volumes/Data" if sys.platform == "darwin" else "/"


def data_volume_use_pct():
    """-> int use%% of the data volume, or None if unreadable."""
    override = os.environ.get("SPAWN_GUARD_DF_PCT")
    if override is not None:
        return int(override)
    try:
        out = subprocess.run(["df", "-P", DATA_VOLUME], capture_output=True,
                             text=True, timeout=3).stdout
    except Exception:
        return None
    lines = out.strip().splitlines()
    if len(lines) < 2:
        return None
    m = re.search(r"(\d+)%", lines[1])
    return int(m.group(1)) if m else None


def decide(pct):
    """-> (decision, reason)."""
    deny_at = int(os.environ.get("SPAWN_GUARD_DENY_PCT", "95"))
    warn_at = int(os.environ.get("SPAWN_GUARD_WARN_PCT", "90"))
    if pct is None:
        return ("ask",
                "spawn_preflight_guard could not read the data volume (`df -P "
                f"{DATA_VOLUME}` gave no parseable use%). Disk state is UNKNOWN — "
                "confirm the fan-out knowingly or check the volume by hand.")
    if pct >= deny_at:
        return ("deny",
                f"data volume at {pct}% (deny >= {deny_at}%). At 100% every command "
                "fails ENOSPC on unrelated paths and mutation agents emit false "
                "findings — infra failure is neither pass nor fail. Decide the "
                "reclaim order and clear space, or point TMPDIR at a volume with "
                "room, before dispatching.")
    if pct >= warn_at:
        return ("ask",
                f"data volume at {pct}% (warn >= {warn_at}%). A fan-out writes "
                "worktrees and transcripts; confirm knowingly or reclaim first.")
    return ("allow", "")


FIXTURES = [
    # (label, pct, expected)
    ("RED  at 100%: deny", 100, "deny"),
    ("RED  at deny threshold 95: deny", 95, "deny"),
    ("ASK  at 92%: ask", 92, "ask"),
    ("ASK  df unreadable: unknown is not a pass", None, "ask"),
    ("GREEN at 50%: allow", 50, "allow"),
    ("GREEN at 89%: allow", 89, "allow"),
]


def selftest():
    print(f"spawn_preflight_guard {VERSION} --selftest")
    live = data_volume_use_pct()
    print(f"  live data-volume reading: {live}%  (volume: {DATA_VOLUME})")
    bad = 0
    for label, pct, want in FIXTURES:
        got, _ = decide(pct)
        ok = got == want
        bad += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} want={want:<5} got={got:<5} {label}")
    # envelope arm: out-of-scope tool is silent-allow
    payload = {"tool_name": "Bash", "tool_input": {}}
    rc, out = run_payload(payload)
    ok = rc == 0 and out == ""
    bad += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} out-of-scope tool: silent exit 0")
    payload = {"tool_name": "Agent", "tool_input": {"prompt": "x"}}
    os.environ["SPAWN_GUARD_DF_PCT"] = "99"
    rc, out = run_payload(payload)
    del os.environ["SPAWN_GUARD_DF_PCT"]
    ok = rc == 0 and '"permissionDecision": "deny"' in out
    bad += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} Agent spawn at 99%: deny JSON on stdout")
    print(f"\n  selftest: {bad} failure(s)")
    return 1 if bad else 0


def run_payload(payload):
    """In-process hook-mode run -> (exit_code, stdout_text)."""
    import io
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rc = hook_mode(json.dumps(payload))
    finally:
        sys.stdout = old
    return rc, buf.getvalue()


def hook_mode(raw):
    if not raw.strip():
        sys.stderr.write("spawn_preflight_guard: empty stdin\n")
        return 2
    try:
        payload = json.loads(raw)
    except Exception as e:
        sys.stderr.write(f"spawn_preflight_guard: stdin not JSON ({e})\n")
        return 2
    if payload.get("tool_name") not in SPAWN_TOOLS:
        return 0
    decision, reason = decide(data_volume_use_pct())
    if decision == "allow":
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason}}, indent=1))
    return 0


def main(argv):
    args = argv[1:]
    if args:
        if args[0] in ("-h", "--help"):
            print(__doc__)
            return 0
        if args[0] == "--version":
            print(f"spawn_preflight_guard {VERSION}")
            return 0
        if args[0] == "--selftest":
            return selftest()
        sys.stderr.write(f"unknown argument: {args[0]!r}\nrun --help\n")
        return 2
    return hook_mode(sys.stdin.read())


if __name__ == "__main__":
    sys.exit(main(sys.argv))
