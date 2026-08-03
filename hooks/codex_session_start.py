#!/usr/bin/env python3
"""Inject z-harness policy and host-local context into Codex sessions.

Codex loads a repository's AGENTS.md itself. An installed plugin does not make the plugin's
root AGENTS.md global, so this SessionStart/SubagentStart adapter supplies the same bytes as
developer context. It suppresses only a byte-identical policy that Codex already discovers.
A repository merely claiming the same plugin name cannot suppress the installed policy.

An optional `$CODEX_HOME/z-harness/AGENTS.local.md` supplies machine-local operating instructions.
It is read at runtime, is never part of the plugin package, and is soft context: an unreadable or
oversized optional section is omitted whole without evicting mandatory policy. The adapter also
injects the resolved Codex accounting-tool command because `PLUGIN_ROOT` exists in hook children
but not in ordinary agent shell calls.

If mandatory policy cannot be emitted, SessionStart returns `continue:false` on stdout and stops
the turn. SubagentStart cannot be stopped by Codex, so it receives an explicit stop-work context.

Exit codes: 0 hook result emitted or nothing applicable; 1 selftest failure; 2 unknown argument.
"""
import io
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile

VERSION = "1.3.0"
SUPPORTED_EVENTS = {"SessionStart", "SubagentStart"}
MAX_CONTEXT_BYTES = 30_000
LOCAL_CONTEXT_RELATIVE = Path("z-harness") / "AGENTS.local.md"


class PolicyDeliveryError(ValueError):
    """Mandatory policy could not be read, decoded, or kept inside its hard budget."""


def ancestors_from(path):
    current = Path(path).resolve()
    yield current
    yield from current.parents


def applicable_agents_matches(cwd, policy_bytes, codex_home=None):
    """True when Codex already discovers an identical global or project AGENTS.md."""
    home = Path(codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    for name in ("AGENTS.override.md", "AGENTS.md"):
        candidate = home / name
        try:
            content = candidate.read_bytes()
        except OSError:
            continue
        if not content.strip():
            continue
        if content == policy_bytes:
            return True
        break
    for directory in ancestors_from(cwd):
        for name in ("AGENTS.override.md", "AGENTS.md"):
            candidate = directory / name
            try:
                content = candidate.read_bytes()
            except OSError:
                continue
            if not content.strip():
                continue
            if content == policy_bytes:
                return True
            break
        if (directory / ".git").exists():
            break
    return False


def machine_local_context(codex_home=None):
    """Return optional host-specific instructions from Codex home, never the package."""
    home = Path(codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    candidate = home / LOCAL_CONTEXT_RELATIVE
    try:
        text = candidate.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read machine-local context {candidate}: {exc}") from exc
    return text.strip()


def joined_context(sections):
    return "\n\n---\n\n".join(sections).strip()


def context_bytes(sections):
    return len(joined_context(sections).encode("utf-8"))


def adapter_context(root):
    cost_tool = shlex.quote(str(root / "tools" / "codex-cost.py"))
    delivery_tool = shlex.quote(str(root / "tools" / "pr-delivery-state.py"))
    return (
        "# z-harness Codex adapter\n\n"
        "For Codex token accounting, run this resolved installed-package command: "
        f"`python3 {cost_tool}`. For PR publication proof, run: "
        f"`python3 {delivery_tool} --pr <number> --repo <owner/repo>`. Do not substitute "
        "`${PLUGIN_ROOT}`; that variable exists in hook children but is empty in ordinary "
        "agent shell calls."
    )


def build_context(root, cwd, codex_home=None):
    policy = root / "AGENTS.md"
    try:
        policy_bytes = policy.read_bytes()
    except OSError as exc:
        raise PolicyDeliveryError(f"cannot read shared policy {policy}: {exc}") from exc
    try:
        policy_text = policy_bytes.decode("utf-8")
    except UnicodeError as exc:
        raise PolicyDeliveryError(f"shared policy is not UTF-8: {policy}") from exc

    mandatory = [adapter_context(root)]
    if not applicable_agents_matches(cwd, policy_bytes, codex_home=codex_home):
        mandatory.insert(0, "# z-harness shared operating policy\n\n" + policy_text)
    if context_bytes(mandatory) > MAX_CONTEXT_BYTES:
        raise PolicyDeliveryError(
            f"mandatory policy is {context_bytes(mandatory)} bytes; cap is {MAX_CONTEXT_BYTES}"
        )

    optional = []
    warnings = []
    try:
        local_context = machine_local_context(codex_home=codex_home)
    except ValueError as exc:
        local_context = ""
        warnings.append(str(exc))
    if local_context:
        optional.append(
            "# z-harness machine-local operating context\n\n"
            "This is host-local soft context loaded from Codex home, not from the plugin "
            "package. Verify drift-prone claims before acting.\n\n" + local_context
        )

    sections = list(mandatory)
    for section in optional:
        if context_bytes(sections + [section]) <= MAX_CONTEXT_BYTES:
            sections.append(section)
        else:
            warnings.append("machine-local context exceeded the remaining context budget")
    if warnings:
        warning_section = (
            "# z-harness adapter warning\n\n"
            "Mandatory policy remains active. Optional context was omitted whole: "
            + "; ".join(warnings)
        )
        if context_bytes(sections + [warning_section]) <= MAX_CONTEXT_BYTES:
            sections.append(warning_section)
    return joined_context(sections)


def stop_result(reason):
    print(json.dumps({"continue": False, "stopReason": reason}))
    return 0


def subagent_failure_result(reason):
    print(json.dumps({
        "systemMessage": reason,
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": (
                "Z-HARNESS POLICY DELIVERY FAILED. Stop work without using tools and report: "
                + reason
            ),
        },
    }))
    return 0


def hook_mode(raw, root=None):
    if not raw.strip():
        return stop_result(
            "z-harness SessionStart received empty input; mandatory policy state is unknown"
        )
    try:
        payload = json.loads(raw)
    except Exception as exc:
        return stop_result(f"z-harness SessionStart input is not JSON: {exc}")
    if not isinstance(payload, dict):
        return stop_result("z-harness SessionStart payload is not an object")
    event = payload.get("hook_event_name")
    if event not in SUPPORTED_EVENTS:
        return 0
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        reason = "z-harness hook payload has no usable cwd; mandatory policy scope is unknown"
        return subagent_failure_result(reason) if event == "SubagentStart" else stop_result(reason)
    plugin_root = Path(root or os.environ.get("PLUGIN_ROOT") or Path(__file__).parent.parent)
    try:
        context = build_context(plugin_root.resolve(), cwd)
    except PolicyDeliveryError as exc:
        reason = f"z-harness mandatory policy unavailable: {exc}"
        return subagent_failure_result(reason) if event == "SubagentStart" else stop_result(reason)
    if context:
        print(context)
    return 0


def captured_hook(raw, root=None):
    """Run hook mode in-process for selftest and return (rc, stdout)."""
    buf, old = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        rc = hook_mode(raw, root=root)
    finally:
        sys.stdout = old
    return rc, buf.getvalue()


def selftest():
    checks = failures = 0

    def check(label, condition):
        nonlocal checks, failures
        checks += 1
        failures += not condition
        print(f"  {'PASS' if condition else 'FAIL'} {label}")

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        plugin = base / "plugin"
        work = base / "work" / "repo" / "subdir"
        plugin.mkdir(parents=True)
        (plugin / "tools").mkdir()
        work.mkdir(parents=True)
        policy = "# policy\n\nrun the exact gate\n"
        (plugin / "AGENTS.md").write_text(policy, encoding="utf-8")
        (base / "work" / "repo" / ".git").mkdir()

        context = build_context(plugin, work)
        check("shared policy is emitted outside an identical AGENTS tree", policy.strip() in context)
        check("resolved Codex accounting path is emitted", str(plugin / "tools/codex-cost.py") in context)
        check("resolved PR delivery path is emitted",
              str(plugin / "tools/pr-delivery-state.py") in context)

        (base / "work" / "repo" / "AGENTS.md").write_text(policy, encoding="utf-8")
        context = build_context(plugin, work)
        check("identical applicable AGENTS.md suppresses duplicate policy",
              "# z-harness shared operating policy" not in context)
        check("adapter context remains when policy is already native",
              "# z-harness Codex adapter" in context)

        (base / "work" / "repo" / "AGENTS.md").unlink()
        (base / "work" / "repo" / "AGENTS.override.md").write_text(policy, encoding="utf-8")
        context = build_context(plugin, work)
        check("identical applicable AGENTS.override.md suppresses duplicate policy",
              "# z-harness shared operating policy" not in context)

        global_home = base / "codex-home"
        global_home.mkdir()
        (base / "work" / "repo" / "AGENTS.override.md").unlink()
        (global_home / "AGENTS.md").write_text(policy, encoding="utf-8")
        context = build_context(plugin, work, codex_home=global_home)
        check("identical global AGENTS.md suppresses duplicate policy",
              "# z-harness shared operating policy" not in context)

        local_context = global_home / LOCAL_CONTEXT_RELATIVE
        local_context.parent.mkdir()
        local_context.write_text("`timeout` is unavailable on this host.\n", encoding="utf-8")
        context = build_context(plugin, work, codex_home=global_home)
        check("machine-local Codex-home context is emitted when present",
              "`timeout` is unavailable on this host." in context)
        check("machine-local context does not revive duplicate plugin policy",
              "# z-harness shared operating policy" not in context)

        planted = base / "planted" / "repo" / "subdir"
        planted.mkdir(parents=True)
        (base / "planted" / "repo" / ".git").mkdir()
        (base / "planted" / "repo" / ".codex-plugin").mkdir()
        (base / "planted" / "repo" / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"name": "z-harness"}), encoding="utf-8"
        )
        context = build_context(plugin, planted, codex_home=base / "empty-codex-home")
        check("same-name manifest cannot suppress installed policy", policy.strip() in context)

        local_context.write_bytes(b"bad utf8: \xff\n")
        context = build_context(plugin, work, codex_home=global_home)
        check("unreadable optional context preserves adapter", "# z-harness Codex adapter" in context)
        check("unreadable optional context is diagnosed", "Optional context was omitted" in context)

        local_context.write_text("x" * MAX_CONTEXT_BYTES, encoding="utf-8")
        context = build_context(plugin, work, codex_home=global_home)
        check("oversized optional context is dropped whole", "x" * 100 not in context)
        check("oversized optional context preserves mandatory adapter",
              "# z-harness Codex adapter" in context)

        payload = json.dumps({"hook_event_name": "SessionStart", "cwd": str(work)})
        rc, output = captured_hook(payload, root=plugin)
        check("SessionStart envelope exits zero", rc == 0)
        check("SessionStart envelope emits mandatory adapter", "z-harness Codex adapter" in output)
        check("out-of-scope hook is silent", captured_hook(json.dumps({
            "hook_event_name": "PreToolUse", "cwd": str(work)}), root=plugin) == (0, ""))

        rc, output = captured_hook(payload, root=base / "missing-plugin")
        stopped = json.loads(output)
        check("missing mandatory policy stops SessionStart",
              rc == 0 and stopped["continue"] is False)

        subagent = json.dumps({"hook_event_name": "SubagentStart", "cwd": str(work)})
        rc, output = captured_hook(subagent, root=base / "missing-plugin")
        failed = json.loads(output)
        check("missing mandatory policy tells subagent to stop",
              rc == 0 and "Stop work" in failed["hookSpecificOutput"]["additionalContext"])

        (plugin / "AGENTS.md").write_text("x" * MAX_CONTEXT_BYTES, encoding="utf-8")
        rc, output = captured_hook(payload, root=plugin)
        check("oversized mandatory policy stops SessionStart",
              rc == 0 and json.loads(output)["continue"] is False)

    rc, output = captured_hook("not-json")
    check("malformed JSON stops rather than failing open",
          rc == 0 and json.loads(output)["continue"] is False)
    print(f"\n  {checks} checks, {failures} failures")
    return 1 if failures else 0


def main(argv):
    args = argv[1:]
    if args:
        if args[0] in ("-h", "--help"):
            print(__doc__)
            return 0
        if args[0] == "--version":
            print(f"codex_session_start {VERSION}")
            return 0
        if args[0] == "--selftest":
            return selftest()
        sys.stderr.write(f"unknown argument: {args[0]!r}\n")
        return 2
    return hook_mode(sys.stdin.read())


if __name__ == "__main__":
    sys.exit(main(sys.argv))
