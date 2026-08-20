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
import tempfile
import sys

VERSION = "1.3.0"
SPAWN_TOOLS = {"Agent", "Task", "spawn_agent"}
RUNTIMES = {"claude", "codex"}
# Claude puts the spawn text in tool_input.prompt; Codex uses tool_input.message. Both were
# read from a real payload, not assumed: a live PreToolUse carried
# tool_input keys ['description', 'name', 'prompt', 'subagent_type'] with the full prompt.
PROMPT_FIELDS = ("prompt", "message")
SCRATCH_LINE = re.compile(r"^Scratch:[ \t]+(\S+)[ \t]*$", re.MULTILINE)
# The guard is installed user-wide, so a blanket requirement would impose one repository's
# convention on every unrelated project. A project opts in by carrying the rule itself.
WORKSPACE_RULE_MARKER = "Every dispatched worker owns an exclusive scratch directory"
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
    bad = checks = 0
    for label, pct, want in FIXTURES:
        got, _ = decide(pct)
        ok = got == want
        bad += (not ok)
        checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} want={want:<5} got={got:<5} {label}")
    # --- worker-workspace arm --------------------------------------------------------
    # Every case drives scratch_decision/project_requires_scratch directly, and the two
    # end-to-end rows below drive the real envelope so the wiring is proved, not assumed.
    import tempfile as _tf
    with _tf.TemporaryDirectory(prefix="spawn-guard-") as _root:
        adopted = os.path.join(_root, "adopted")
        plain = os.path.join(_root, "plain")
        os.makedirs(adopted); os.makedirs(plain)
        with open(os.path.join(adopted, "AGENTS.md"), "w", encoding="utf-8") as fh:
            fh.write("policy\n" + WORKSPACE_RULE_MARKER + ", assigned at spawn.\n")
        with open(os.path.join(plain, "AGENTS.md"), "w", encoding="utf-8") as fh:
            fh.write("a project that never adopted the rule\n")
        good = os.path.join(_tf.gettempdir(), "agent-scratch", "s1", "w1")

        for label, want, cwd in (
            ("a project carrying the rule opts in", True, adopted),
            ("a project without the rule is out of scope", False, plain),
            ("a missing cwd is out of scope, never an unchecked deny", False, None),
        ):
            got = project_requires_scratch(cwd)
            ok = got is want
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} {label}")

        # Assert the REASON, not merely that something denied. Every one of these paths also
        # trips a later check, so a decision-only assertion is satisfied by a neighbour and
        # survives neutering the check it names.
        for label, want, named, ti in (
            ("an assigned per-worker directory is allowed", "allow", "",
             {"name": "w1", "prompt": f"do it\nScratch: {good}\n"}),
            ("no Scratch line is denied", "deny", "expected 1",
             {"name": "w1", "prompt": "do it"}),
            ("two Scratch lines are denied", "deny", "expected 1",
             {"name": "w1", "prompt": f"Scratch: {good}\nScratch: {good}\n"}),
            ("a relative scratch path is denied", "deny", "is not absolute",
             {"name": "w1", "prompt": "Scratch: ./w1\n"}),
            ("a scratch path inside the checkout is denied", "deny",
             "inside or above the checkout",
             {"name": "w1", "prompt": f"Scratch: {os.path.join(adopted, 'w1')}\n"}),
            ("a scratch path above the checkout is denied", "deny",
             "inside or above the checkout",
             {"name": "w1", "prompt": f"Scratch: {os.path.dirname(adopted)}\n"}),
            ("a path that does not name the worker is denied", "deny",
             "does not name the worker",
             {"name": "w1", "prompt": f"Scratch: {os.path.join(_tf.gettempdir(), 'shared')}\n"}),
            ("the Codex message field is read like a Claude prompt", "deny", "expected 1",
             {"name": "w1", "message": "do it"}),
            ("a non-object tool_input fails closed", "deny", "fails closed", None),
        ):
            got, why = scratch_decision(ti, adopted, session_id="s1",
                                        agent_name=(ti or {}).get("name")
                                        if isinstance(ti, dict) else None)
            ok = got == want and (named in why)
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} want={want:<5} got={got:<5} {label}")

        payload = {"tool_name": "Agent", "cwd": adopted, "session_id": "s1",
                   "tool_input": {"name": "w1", "prompt": "do it"}}
        rc, out = run_payload(payload, runtime="claude")
        ok = rc == 0 and '"permissionDecision": "deny"' in out and "Scratch:" in out
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} end to end: an unassigned spawn is denied and told the fix")

        payload["tool_input"]["prompt"] = f"do it\nScratch: {good}\n"
        rc, out = run_payload(payload, runtime="claude")
        ok = rc == 0 and out == ""
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} end to end: an assigned spawn passes silently")

        os.environ["SPAWN_GUARD_DF_PCT"] = "99"
        rc, out = run_payload(payload, runtime="claude")
        del os.environ["SPAWN_GUARD_DF_PCT"]
        ok = rc == 0 and "data volume" in out
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} capacity still outranks the workspace check")

    # envelope arm: out-of-scope tool is silent-allow
    payload = {"tool_name": "Bash", "tool_input": {}}
    rc, out = run_payload(payload)
    ok = rc == 0 and out == ""
    bad += (not ok)
    checks += 1
    print(f"  {'PASS' if ok else 'FAIL'} out-of-scope tool: silent exit 0")
    payload = {"tool_name": "Agent", "tool_input": {"prompt": "x"}}
    os.environ["SPAWN_GUARD_DF_PCT"] = "99"
    rc, out = run_payload(payload, runtime="claude")
    del os.environ["SPAWN_GUARD_DF_PCT"]
    ok = rc == 0 and '"permissionDecision": "deny"' in out
    bad += (not ok)
    checks += 1
    print(f"  {'PASS' if ok else 'FAIL'} Agent spawn at 99%: deny JSON on stdout")
    payload = {"tool_name": "spawn_agent", "tool_input": {"message": "x"}}
    os.environ["SPAWN_GUARD_DF_PCT"] = "92"
    rc, out = run_payload(payload, runtime="codex")
    del os.environ["SPAWN_GUARD_DF_PCT"]
    ok = rc == 0 and '"permissionDecision": "deny"' in out and "fails closed" in out
    bad += (not ok)
    checks += 1
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
        checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} {label}: rc={rc}, stderr={bool(err.strip())}")
    os.environ["SPAWN_GUARD_DF_PCT"] = "not-an-integer"
    try:
        rc, _out, err = run_raw(json.dumps({"tool_name": "Agent", "tool_input": {}}),
                                runtime="codex")
    finally:
        del os.environ["SPAWN_GUARD_DF_PCT"]
    ok = rc == 2 and bool(err.strip())
    bad += (not ok)
    checks += 1
    print(f"  {'PASS' if ok else 'FAIL'} unreadable capacity fails closed with reason")
    class BrokenReader:
        def read(self):
            raise UnicodeError("planted stdin decode failure")
    raw, read_error = read_hook_input(BrokenReader())
    ok = raw is None and "stdin read failed" in read_error
    bad += (not ok)
    checks += 1
    print(f"  {'PASS' if ok else 'FAIL'} stdin decode failure has a blocking reason")
    print(f"\n  selftest: {bad} failure(s)")
    print(f"SELFTEST-SUMMARY suite=spawn_preflight_guard checks={checks} failures={bad}")
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
        tool_input = payload.get("tool_input")
        cwd = payload.get("cwd")
        if project_requires_scratch(cwd):
            decision, reason = scratch_decision(
                tool_input, cwd,
                session_id=payload.get("session_id"),
                agent_name=(tool_input or {}).get("name")
                if isinstance(tool_input, dict) else None)
            if decision == "allow":
                return 0
        else:
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


def project_requires_scratch(cwd, marker=WORKSPACE_RULE_MARKER, opener=None):
    """True when the project containing `cwd` declares the worker-workspace rule."""
    opener = open if opener is None else opener
    if not isinstance(cwd, str) or not cwd:
        return False
    here = os.path.abspath(cwd)
    while True:
        try:
            with opener(os.path.join(here, "AGENTS.md"), encoding="utf-8",
                        errors="replace") as handle:
                if marker in re.sub(r"\s+", " ", handle.read()):
                    return True
        except OSError:
            pass
        parent = os.path.dirname(here)
        if parent == here:
            return False
        here = parent


def suggested_scratch(cwd, session_id, agent_name):
    """An absolute, per-worker path that is never inside the checkout."""
    leaf = agent_name if isinstance(agent_name, str) and agent_name else "worker"
    session = session_id if isinstance(session_id, str) and session_id else "session"
    return os.path.join(tempfile.gettempdir(), "agent-scratch", session, leaf)


def scratch_decision(tool_input, cwd, session_id=None, agent_name=None):
    """-> (decision, reason). Deny a spawn that names no exclusive worker directory.

    The reason carries the exact line to add, so a denial hands back the fix rather than only
    refusing. The parent cannot be given the directory any other way: a PreToolUse hook returns
    a decision and cannot write into the child, and no per-subagent prompt channel exists in
    the installed CLI.
    """
    if not isinstance(tool_input, dict):
        return ("deny", "spawn payload carries no tool_input object, so the worker's scratch "
                        "directory cannot be checked; z-harness fails closed.")
    prompt = ""
    for field in PROMPT_FIELDS:
        value = tool_input.get(field)
        if isinstance(value, str) and value:
            prompt = value
            break
    suggestion = suggested_scratch(cwd, session_id, agent_name)
    fix = f"Add a line reading exactly: Scratch: {suggestion}"
    found = SCRATCH_LINE.findall(prompt)
    if len(found) != 1:
        return ("deny",
                f"this project requires every dispatched worker to own an exclusive scratch "
                f"directory, and the spawn prompt has {len(found)} 'Scratch:' lines, expected "
                f"1. Concurrent workers sharing one directory overwrite each other silently "
                f"and the loser measures the wrong thing. {fix}")
    path = found[0]
    if not os.path.isabs(path):
        return ("deny", f"the worker's scratch path {path!r} is not absolute, so it resolves "
                        f"against whatever directory the worker happens to start in. {fix}")
    root = os.path.abspath(cwd) if isinstance(cwd, str) and cwd else None
    target = os.path.abspath(path)
    if root and (target == root
                 or target.startswith(root + os.sep)
                 or root.startswith(target + os.sep)):
        return ("deny", f"the worker's scratch path {path!r} is inside or above the checkout "
                        f"at {root!r}. Scratch never shares a tree with the code under "
                        f"measurement. {fix}")
    if (isinstance(agent_name, str) and agent_name
            and agent_name not in os.path.basename(target)):
        return ("deny", f"the worker's scratch path {path!r} does not name the worker "
                        f"{agent_name!r}, so two workers can be handed the same directory. "
                        f"{fix}")
    return ("allow", "")


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
