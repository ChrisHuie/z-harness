#!/usr/bin/env python3
"""spawn_preflight_guard — PreToolUse gate on Claude and Codex agent-spawn tools.

The shared AGENTS.md rule this mechanizes: preflight EVERY
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
needs a DB, and `docker info` adds latency to every spawn. The shared AGENTS.md
preflight line keeps `docker info` for DB-needing dispatches.

Env overrides (selftest + tuning):
  SPAWN_GUARD_DF_PCT   integer 0-100, replaces the live df reading
  SPAWN_GUARD_DENY_PCT / SPAWN_GUARD_WARN_PCT

Claude contract (verified in-binary 2.1.220): stdout JSON
{"hookSpecificOutput": {"hookEventName": "PreToolUse",
 "permissionDecision": "deny|ask|allow", "permissionDecisionReason": "..."}}

Codex does not support `permissionDecision: "ask"` in PreToolUse. With
`--runtime codex`, both the warn and deny bands therefore emit `deny`; the user can
inspect capacity and retry. Silently proceeding would turn an unreadable safety check
into a pass.

Exit codes: 0 decision emitted or out of scope · 1 selftest failure ·
2 usage error / unreadable df.
"""
import json
import os
import re
import subprocess
import sys

VERSION = "1.3.0"
SPAWN_TOOLS = {"Agent", "Task", "spawn_agent"}
RUNTIMES = {"claude", "codex"}
DATA_VOLUME = "/System/Volumes/Data" if sys.platform == "darwin" else "/"


class EnvelopeError(ValueError):
    """The matched PreToolUse envelope cannot be judged safely."""


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
    rc, out = run_payload(payload, runtime="claude")
    del os.environ["SPAWN_GUARD_DF_PCT"]
    ok = rc == 0 and '"permissionDecision": "deny"' in out
    bad += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} Agent spawn at 99%: deny JSON on stdout")
    payload = {"tool_name": "spawn_agent", "tool_input": {"message": "x"}}
    os.environ["SPAWN_GUARD_DF_PCT"] = "92"
    rc, out = run_payload(payload, runtime="codex")
    del os.environ["SPAWN_GUARD_DF_PCT"]
    ok = rc == 0 and '"permissionDecision": "deny"' in out and "fails closed" in out
    bad += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} Codex spawn at 92%: unsupported ask maps to deny")
    for label, raw in (
        ("empty stdin", ""),
        ("malformed JSON", "{"),
        ("non-object payload", "false"),
        ("missing tool_name", json.dumps({"tool_input": {"prompt": "x"}})),
        ("non-string tool_name", json.dumps({"tool_name": 7, "tool_input": {}})),
    ):
        rc, _out, err = run_raw(raw, runtime="codex")
        ok = rc == 2 and bool(err.strip())
        bad += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} {label}: rc={rc}, stderr={bool(err.strip())}")
    os.environ["SPAWN_GUARD_DF_PCT"] = "not-an-integer"
    try:
        rc, _out, err = run_raw(json.dumps({"tool_name": "Agent", "tool_input": {}}),
                                runtime="codex")
    finally:
        del os.environ["SPAWN_GUARD_DF_PCT"]
    ok = rc == 2 and bool(err.strip())
    bad += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} unreadable capacity fails closed with reason")
    class BrokenReader:
        def read(self):
            raise UnicodeError("planted stdin decode failure")
    raw, read_error = read_hook_input(BrokenReader())
    ok = raw is None and "stdin read failed" in read_error
    bad += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} stdin decode failure has a blocking reason")
    print(f"\n  selftest: {bad} failure(s)")
    return 1 if bad else 0


def run_payload(payload, runtime="claude"):
    """In-process hook-mode run -> (exit_code, stdout_text)."""
    import io
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rc = hook_mode(json.dumps(payload), runtime=runtime)
    finally:
        sys.stdout = old
    return rc, buf.getvalue()


def run_raw(raw, runtime="claude"):
    """In-process raw hook run -> (exit_code, stdout_text, stderr_text)."""
    import io
    out, err = io.StringIO(), io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    try:
        rc = hook_mode(raw, runtime=runtime)
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    return rc, out.getvalue(), err.getvalue()


def hook_mode(raw, runtime="claude"):
    if not raw.strip():
        sys.stderr.write("spawn_preflight_guard: empty stdin\n")
        return 2
    try:
        payload = json.loads(raw)
    except Exception as e:
        sys.stderr.write(f"spawn_preflight_guard: stdin not JSON ({e})\n")
        return 2
    if not isinstance(payload, dict):
        sys.stderr.write("spawn_preflight_guard: PreToolUse payload is not an object\n")
        return 2
    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name:
        sys.stderr.write("spawn_preflight_guard: PreToolUse payload has no string tool_name\n")
        return 2
    if tool_name not in SPAWN_TOOLS:
        return 0
    try:
        decision, reason = decide(data_volume_use_pct())
    except Exception as exc:
        sys.stderr.write(
            f"spawn_preflight_guard: capacity check failed ({exc!r}); refusing to spawn blind\n"
        )
        return 2
    if decision == "allow":
        return 0
    if runtime == "codex" and decision == "ask":
        decision = "deny"
        reason += (" Codex PreToolUse cannot request confirmation, so z-harness "
                   "fails closed; inspect capacity and retry the spawn.")
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason}}, indent=1))
    return 0


def read_hook_input(stream):
    """Return (text, error); stdin failures must never become a silent allow."""
    try:
        return stream.read(), ""
    except Exception as exc:
        return None, f"spawn_preflight_guard: stdin read failed ({exc!r}); refusing to spawn blind"


def main(argv):
    args = argv[1:]
    runtime = "claude"
    if len(args) >= 2 and args[0] == "--runtime":
        runtime = args[1]
        args = args[2:]
        if runtime not in RUNTIMES:
            sys.stderr.write(f"unknown runtime: {runtime!r}; choose claude or codex\n")
            return 2
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
    raw, error = read_hook_input(sys.stdin)
    if raw is None:
        print(error, file=sys.stderr)
        return 2
    return hook_mode(raw, runtime=runtime)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
