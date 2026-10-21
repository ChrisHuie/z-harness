#!/usr/bin/env python3
"""artifact_publish_guard — PreToolUse gate denying an Artifact publish.

WHY THIS IS A GATE AND NOT A RULE. Publishing an Artifact arms a background
live-update subscription, whose only job is to notice another session
republishing the same page. It renders in the client as a running task. On
2026-08-17 one such subscription showed as running work for roughly an hour on a
private page no other session could touch, and it was read as active work. There
is no control exposed to cancel it.

An indicator that claims work with nothing behind it is the same defect class as
a turn that ends "Starting the audit." with no tool calls after it, which this
harness already gates at Stop. The difference is that the announcement is
something the model emits and can be checked, while the subscription is a side
effect of a tool call. The only reachable control is not to make the call.

AGENTS.md ranks the remedies: memory < turn instruction < context file < a
failing mechanical control. A note to remember not to publish is the weakest of
those, so this is the strongest one instead.

WHAT IT DOES NOT DENY. The read-only Artifact actions - listing what exists,
reading comment threads, replying to one, resolving one - start no subscription
and are left alone. Only a publish is denied.

    python3 ~/.claude/hooks/artifact_publish_guard.py            # as a hook
    python3 ~/.claude/hooks/artifact_publish_guard.py --selftest # controls

PreToolUse hooks receive {"tool_name": str, "tool_input": {...}, ...} and answer
on stdout with
{"hookSpecificOutput": {"hookEventName": "PreToolUse",
 "permissionDecision": "deny|ask|allow", "permissionDecisionReason": "..."}}.
A tool this guard does not own produces no output and exit 0, which is out of
scope rather than drift. An envelope it cannot read fails CLOSED, matching
spawn_preflight_guard: a gate that allows because it read nothing is worse than
no gate, because it still reads as installed.

Exit codes: 0 always for a readable envelope, decision on stdout · 1 selftest
failure · 2 unreadable envelope, denied on stderr.
"""
import json
import sys

VERSION = "1.0.0"

TOOL = "Artifact"

# Actions that only read. A publish is `action` absent, or "publish".
READ_ONLY_ACTIONS = frozenset({"list", "comments", "reply", "resolve"})

REASON = (
    "Denied by artifact_publish_guard {v}: an Artifact publish arms a background "
    "live-update subscription that renders as a running task in the client and "
    "cannot be cancelled. It has shown as active work for an hour on a page no "
    "other session could republish. Deliver the document instead: write the file, "
    "then hand it over with SendUserFile, or put the content in the reply. The "
    "read-only Artifact actions are not affected. If a published page is genuinely "
    "required, say so and remove this hook deliberately rather than working around "
    "it."
)


def decide(payload):
    """-> (decision, reason) for a readable envelope. Raises ValueError otherwise."""
    if not isinstance(payload, dict):
        raise ValueError(f"stdin parsed to {type(payload).__name__}, expected a JSON object")
    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name:
        raise ValueError("PreToolUse payload has no string tool_name")
    if tool_name != TOOL:
        return None, None                       # out of scope, which is not drift
    tool_input = payload.get("tool_input")
    action = tool_input.get("action") if isinstance(tool_input, dict) else None
    if isinstance(action, str) and action.strip().lower() in READ_ONLY_ACTIONS:
        return None, None                       # reads start no subscription
    return "deny", REASON.format(v=VERSION)


def emit(decision, reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason}}, indent=1))


def selftest():
    cases = [
        ("publish with no action is denied",
         {"tool_name": "Artifact", "tool_input": {"file_path": "x.html"}}, "deny"),
        ("explicit publish is denied",
         {"tool_name": "Artifact", "tool_input": {"action": "publish",
                                                  "file_path": "x.html"}}, "deny"),
        ("updating an existing artifact is still a publish",
         {"tool_name": "Artifact", "tool_input": {"file_path": "x.html",
                                                  "url": "https://example/a"}}, "deny"),
        ("case and whitespace do not evade it",
         {"tool_name": "Artifact", "tool_input": {"action": " PUBLISH "}}, "deny"),
        ("a non-string action is treated as a publish",
         {"tool_name": "Artifact", "tool_input": {"action": 7}}, "deny"),
        ("absent tool_input is treated as a publish",
         {"tool_name": "Artifact"}, "deny"),

        # Reads arm nothing and must pass, or the gate stops the only way to
        # answer a comment on a page that already exists.
        ("listing is allowed", {"tool_name": "Artifact",
                                "tool_input": {"action": "list"}}, None),
        ("reading comments is allowed", {"tool_name": "Artifact",
                                         "tool_input": {"action": "comments"}}, None),
        ("replying to a thread is allowed", {"tool_name": "Artifact",
                                             "tool_input": {"action": "reply"}}, None),
        ("resolving a thread is allowed", {"tool_name": "Artifact",
                                           "tool_input": {"action": "resolve"}}, None),

        # Every other tool must be untouched. A gate that answers for tools it
        # does not own is a gate that breaks the session it was added to protect.
        ("Bash is out of scope", {"tool_name": "Bash",
                                  "tool_input": {"command": "ls"}}, None),
        ("Write is out of scope", {"tool_name": "Write",
                                   "tool_input": {"file_path": "x"}}, None),
        ("SendUserFile is out of scope - it is the replacement",
         {"tool_name": "SendUserFile", "tool_input": {"files": ["x"]}}, None),

        # Drift fails closed.
        ("missing tool_name fails closed", {"tool_input": {}}, "drift"),
        ("non-string tool_name fails closed", {"tool_name": 7}, "drift"),
        ("empty tool_name fails closed", {"tool_name": ""}, "drift"),
        ("non-object stdin fails closed", ["Artifact"], "drift"),
    ]
    failures = 0
    for name, payload, want in cases:
        try:
            got, _reason = decide(payload)
        except ValueError:
            got = "drift"
        if got != want:
            failures += 1
        print(f"  {'PASS' if got == want else 'FAIL'} {name} -> {got or 'out of scope'}")
    print(f"\n  selftest: {failures} failure(s)")
    print(f"SELFTEST-SUMMARY suite=artifact_publish_guard checks={len(cases)} "
          f"failures={failures}")
    return failures == 0


def main(argv):
    if "--selftest" in argv:
        return 0 if selftest() else 1
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception as exc:
        sys.stderr.write(f"artifact_publish_guard {VERSION}: stdin is not JSON ({exc}); "
                         "denying rather than passing on an unread envelope\n")
        return 2
    try:
        decision, reason = decide(payload)
    except ValueError as exc:
        sys.stderr.write(f"artifact_publish_guard {VERSION}: {exc}; denying rather than "
                         "passing on an unread envelope\n")
        return 2
    if decision:
        emit(decision, reason)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
