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
    import tempfile as _tf
    with _tf.TemporaryDirectory(prefix="spawn-guard-") as _root:
        _root = os.path.realpath(_root)
        adopted = os.path.join(_root, "adopted")
        plain = os.path.join(_root, "plain")
        os.makedirs(adopted); os.makedirs(plain)
        # A LITERAL, never WORKSPACE_RULE_MARKER: a fixture built from the constant under test
        # follows it, so the marker could drift out of the shared policy undetected.
        with open(os.path.join(adopted, "AGENTS.md"), "w", encoding="utf-8") as fh:
            fh.write("policy\nEvery dispatched worker owns an exclusive scratch "
                     "directory, assigned at spawn.\n")
        with open(os.path.join(plain, "AGENTS.md"), "w", encoding="utf-8") as fh:
            fh.write("a project that never adopted the rule\n")
        good = os.path.join(_tf.gettempdir(), "agent-scratch", "s1", "w1")

        expect_eq = lambda label, got, want: (label, got, want)
        for label, want, cwd in (
            ("a project carrying the rule opts in", True, adopted),
            ("a project without the rule is out of scope", False, plain),
            ("a missing cwd is out of scope, never an unchecked deny", False, None),
        ):
            got = project_requires_scratch(cwd)
            ok = got is want
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} {label}")

        # The marker the guard matches must be the sentence the shared policy actually carries.
        ok = WORKSPACE_RULE_MARKER == (
            "Every dispatched worker owns an exclusive scratch directory")
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} the activation marker is the reviewed sentence")

        # An unreadable policy must not silently opt the project out.
        unreadable = os.path.join(_root, "locked")
        os.makedirs(unreadable)
        locked_policy = os.path.join(unreadable, "AGENTS.md")
        with open(locked_policy, "w", encoding="utf-8") as fh:
            fh.write("Every dispatched worker owns an exclusive scratch directory.\n")
        def _denied_opener(*_a, **_k):
            raise PermissionError(13, "planted")
        ok = project_requires_scratch(unreadable, opener=_denied_opener) is True
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} an unreadable policy fails closed, never opting out")

        # Assert the REASON, not merely that something denied: every one of these also trips a
        # later check, so a decision-only assertion is satisfied by a neighbour.
        for label, want, named, ti in (
            ("an assigned directory is allowed", "allow", "",
             {"prompt": f"do it\nScratch: {good}\n"}),
            ("no Scratch line is denied", "deny", "expected 1", {"prompt": "do it"}),
            ("two Scratch lines are denied", "deny", "expected 1",
             {"prompt": f"Scratch: {good}\nScratch: {good}\n"}),
            ("a relative scratch path is denied", "deny", "is not absolute",
             {"prompt": "Scratch: ./w1\n"}),
            ("a scratch path inside the checkout is denied", "deny",
             "inside or above the checkout",
             {"prompt": f"Scratch: {os.path.join(adopted, 'w1')}\n"}),
            ("a scratch path above the checkout is denied", "deny",
             "inside or above the checkout",
             {"prompt": f"Scratch: {os.path.dirname(adopted)}\n"}),
            ("a Scratch line with trailing text is not a marker", "deny", "expected 1",
             {"prompt": f"Scratch: {good} and also do Y\n"}),
            ("a Scratch line mid-line is not a marker", "deny", "expected 1",
             {"prompt": f"please use Scratch: {good}\n"}),
            ("the Codex message field is read like a Claude prompt", "allow", "",
             {"message": f"do it\nScratch: {good}\n"}),
            ("a non-object tool_input fails closed", "deny", "fails closed", None),
        ):
            got, why = scratch_decision(ti, adopted, session_id="s1")
            ok = got == want and (named in why)
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} want={want:<5} got={got:<5} {label}")

        # Containment is resolved, not lexical: a symlinked alias of the checkout is the
        # ordinary case wherever /tmp is /private/tmp.
        alias = os.path.join(_root, "alias")
        os.symlink(adopted, alias)
        got, why = scratch_decision(
            {"prompt": f"Scratch: {os.path.join(alias, 'w1')}\n"}, adopted, session_id="s1")
        ok = got == "deny" and "inside or above the checkout" in why
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a symlinked alias of the checkout is denied")

        # ...and the CWD side: the checkout itself reached through an alias.
        got, why = scratch_decision(
            {"prompt": f"Scratch: {os.path.join(adopted, 'w1')}\n"}, alias, session_id="s1")
        ok = got == "deny" and "inside or above the checkout" in why
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a checkout reached through an alias still contains")

        # The guard must accept its own remedy, whatever TMPDIR resolves to.
        suggestion = suggested_scratch(adopted, "s1", "w1")
        got, _ = scratch_decision({"prompt": f"Scratch: {suggestion}\n"}, adopted,
                                  session_id="s1")
        ok = got == "allow"
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} the guard accepts the path it suggests")
        resolved = os.path.realpath(suggestion)
        ok = (not resolved.startswith(os.path.realpath(adopted) + os.sep)
              and "s1" in suggestion and suggestion.endswith("w1")
              and os.path.isabs(suggestion))
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} the suggestion is absolute, outside the checkout, "
              f"and per session and worker")
        ok = suggested_scratch(adopted, "s1", "w1") != suggested_scratch(adopted, "s1", "w2")
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} two workers are suggested different directories")

        # Codex has no `name`; it carries `task_name`.
        for label, want, ti in (
            ("a Claude name is read", "w1", {"name": "w1"}),
            ("a Codex task_name is read", "w2", {"task_name": "w2"}),
            ("an absent worker name is None, never a shared default", None, {"prompt": "x"}),
        ):
            got = worker_name(ti)
            ok = got == want
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} {label}")

        payload = {"tool_name": "Agent", "cwd": adopted, "session_id": "s1",
                   "tool_input": {"name": "w1", "prompt": "do it"}}
        rc, out = run_payload(payload, runtime="claude")
        ok = rc == 0 and '"permissionDecision": "deny"' in out and "Scratch:" in out
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} end to end: an unassigned spawn is denied and told the fix")

        task_payload = dict(payload, tool_name="Task")
        rc, out = run_payload(task_payload, runtime="claude")
        ok = rc == 0 and '"permissionDecision": "deny"' in out
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} the Task spawn tool is in scope too")

        payload["tool_input"]["prompt"] = f"do it\nScratch: {good}\n"
        rc, out = run_payload(payload, runtime="claude")
        ok = rc == 0 and out == ""
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} end to end: an assigned spawn passes silently")

        plain_payload = {"tool_name": "Agent", "cwd": plain, "session_id": "s1",
                         "tool_input": {"name": "w1", "prompt": "do it"}}
        rc, out = run_payload(plain_payload, runtime="claude")
        ok = rc == 0 and out == ""
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a project that never adopted the rule is untouched")

        # The rule must not vanish in the warn band, where the user approves an ask.
        payload["tool_input"]["prompt"] = "do it"
        os.environ["SPAWN_GUARD_DF_PCT"] = "92"
        rc, out = run_payload(payload, runtime="claude")
        del os.environ["SPAWN_GUARD_DF_PCT"]
        ok = rc == 0 and '"permissionDecision": "deny"' in out and "Scratch:" in out
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} the workspace rule outranks a capacity ask")

        payload["tool_input"]["prompt"] = f"do it\nScratch: {good}\n"
        os.environ["SPAWN_GUARD_DF_PCT"] = "99"
        rc, out = run_payload(payload, runtime="claude")
        del os.environ["SPAWN_GUARD_DF_PCT"]
        ok = rc == 0 and "data volume" in out
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} capacity still denies a compliant spawn when full")



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
    # Evaluated independently of the capacity band. Sitting under `allow` meant the whole rule
    # vanished in the 90-94% warn band, where the user approves an `ask` -- the control
    # disappearing exactly when disk pressure makes a collision most likely.
    tool_input = payload.get("tool_input")
    cwd = payload.get("cwd")
    if project_requires_scratch(cwd):
        workspace_decision, workspace_reason = scratch_decision(
            tool_input, cwd,
            session_id=payload.get("session_id"),
            agent_name=worker_name(tool_input))
        if workspace_decision == "deny":
            decision, reason = "deny", workspace_reason
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


def project_requires_scratch(cwd, marker=WORKSPACE_RULE_MARKER, opener=None):
    """True when the project containing `cwd` declares the worker-workspace rule."""
    opener = open if opener is None else opener
    if not isinstance(cwd, str) or not cwd:
        return False
    here = os.path.abspath(cwd)
    while True:
        candidate = os.path.join(here, "AGENTS.md")
        try:
            with opener(candidate, encoding="utf-8", errors="replace") as handle:
                if marker in re.sub(r"\s+", " ", handle.read()):
                    return True
        except PermissionError:
            # Every other unreadable input in this file fails closed. A policy we cannot read
            # must not become a silent opt-out, which is the one direction that disables the
            # control without saying so.
            return True
        except OSError:
            pass
        parent = os.path.dirname(here)
        if parent == here:
            return False
        here = parent


def worker_name(tool_input):
    """The worker's name where the runtime supplies one, else None.

    Claude's Agent tool carries `name` and marks it optional; Codex's spawn tool has no `name`
    at all and uses `task_name`, read from the installed binary's SpawnAgentArgs. Used only to
    make the suggested path per-worker; nothing is enforced on it.
    """
    if not isinstance(tool_input, dict):
        return None
    for field in ("name", "task_name"):
        value = tool_input.get(field)
        if isinstance(value, str) and value:
            return value
    return None


def suggested_scratch(cwd, session_id, agent_name):
    """An absolute, per-worker path that is never inside the checkout."""
    leaf = agent_name if isinstance(agent_name, str) and agent_name else "worker"
    session = session_id if isinstance(session_id, str) and session_id else "session"
    return os.path.join(tempfile.gettempdir(), "agent-scratch", session, leaf)


def scratch_decision(tool_input, cwd, session_id=None, agent_name=None):
    """-> (decision, reason). Deny a spawn that assigns the worker no directory of its own.

    What this proves: the spawn names exactly one directory, it is absolute, and it resolves
    outside the checkout. What it does NOT prove is that two workers were given DIFFERENT
    directories. Neither runtime carries a dependable per-worker identifier -- Claude's `name`
    is optional and Codex's spawn tool has `task_name` instead -- so a uniqueness check here
    would be inert on one runtime and bypassable on the other while reading as protection.
    Distinctness is the parent's obligation under the shared policy, and the suggested path
    below is per-worker wherever a name is available.

    The reason carries the exact line to add, so a denial hands back the fix rather than only
    refusing. A PreToolUse hook returns a decision and cannot write into the child, so the
    denial's reason is the only channel that reaches the parent.

    Out of scope, deliberately: a `Scratch:` line inside a fenced block or a quoted sub-prompt
    is matched like any other, and a prompt that both assigns a directory and shows an example
    line is refused as ambiguous.
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
    # realpath, not abspath: abspath normalises ".." but leaves symlinks, and a symlinked
    # alias of the checkout is the ordinary case on a host where /tmp is /private/tmp.
    root = os.path.realpath(cwd)
    target = os.path.realpath(path)
    if target.startswith(root + os.sep) or root.startswith(target + os.sep):
        return ("deny", f"the worker's scratch path {path!r} is inside or above the checkout "
                        f"at {root!r}. Scratch never shares a tree with the code under "
                        f"measurement. {fix}")
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
