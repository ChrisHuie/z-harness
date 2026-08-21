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

Both shipped registrations also pass `--require-scratch`. In that mode the prompt must
carry exactly one `Scratch: <absolute path>` naming a fresh absent leaf outside the Git
worktree. The hook atomically creates that directory mode 0700 before the spawn proceeds;
two workers naming one leaf cannot both pass. This is collision isolation for workers that
share a uid, not an operating-system security boundary. Without the flag the adapter is a
deliberate capacity-only guard.

Exit codes: 0 decision emitted or out of scope · 1 selftest failure ·
2 usage error / unreadable df.
"""
import json
import hashlib
import os
import re
import secrets
import stat
import subprocess
import tempfile
import sys

VERSION = "1.5.0"
SPAWN_TOOLS = {"Agent", "Task", "spawn_agent"}
RUNTIMES = {"claude", "codex"}
# Claude puts the spawn text in tool_input.prompt; Codex uses tool_input.message. Both were
# read from a real payload, not assumed: a live PreToolUse carried
# tool_input keys ['description', 'name', 'prompt', 'subagent_type'] with the full prompt.
PROMPT_FIELDS = ("prompt", "message")
SCRATCH_LINE = re.compile(r"^Scratch:[ \t]+(\S+)[ \t]*$", re.MULTILINE)
DATA_VOLUME = "/System/Volumes/Data" if sys.platform == "darwin" else "/"


class EnvelopeError(ValueError):
    """The matched PreToolUse envelope cannot be judged safely."""


_ANCESTOR_WALK_LIMIT = 256


class ScratchPolicyError(ValueError):
    """The required scratch assignment could not be validated or reserved safely."""


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
    # --- collision-exclusive scratch arm -------------------------------------------
    import threading
    with tempfile.TemporaryDirectory(prefix="spawn-guard-") as _root:
        _root = os.path.realpath(_root)
        adopted = os.path.join(_root, "adopted")
        nested = os.path.join(adopted, "work", "subdir")
        plain = os.path.join(_root, "plain")
        os.makedirs(nested); os.makedirs(plain)
        subprocess.run(["git", "init", "--quiet", adopted], check=True)

        root = protected_workspace_root(nested)
        ok = _same_file(root, adopted)
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} nested cwd resolves the complete Git worktree root")
        ok = _same_file(protected_workspace_root(plain), plain)
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a plain directory uses its physical cwd as root")
        try:
            protected_workspace_root(None)
            ok = False
        except ScratchPolicyError as exc:
            ok = "no usable cwd" in str(exc)
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a missing cwd has a named fail-closed error")

        class GitDone:
            def __init__(self, returncode=0, stdout=b"", stderr=b""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        def wrong_root_runner(_argv, **_kwargs):
            return GitDone(stdout=os.fsencode(plain) + b"\n")
        try:
            protected_workspace_root(nested, runner=wrong_root_runner)
            ok = False
        except ScratchPolicyError as exc:
            ok = "expected" in str(exc)
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} Git cannot substitute a different worktree root")

        def malformed_root_runner(_argv, **_kwargs):
            return GitDone(stdout=os.fsencode(adopted))
        try:
            protected_workspace_root(nested, runner=malformed_root_runner)
            ok = False
        except ScratchPolicyError as exc:
            ok = "malformed path" in str(exc)
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} malformed Git root output fails closed")

        def broken_root_runner(_argv, **_kwargs):
            raise OSError(5, "planted EIO")
        try:
            protected_workspace_root(nested, runner=broken_root_runner)
            ok = False
        except ScratchPolicyError as exc:
            ok = "planted EIO" in str(exc)
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} Git root I/O errors fail closed")

        def fresh(label):
            return os.path.join(_root, f"scratch-{label}")

        assigned = fresh("assigned")
        got, why = scratch_decision(
            {"prompt": f"do it\nScratch: {assigned}\n"}, root,
            session_id="s1", agent_name="w1", nonce="assigned")
        ok = (got == "allow" and not why and os.path.isdir(assigned)
              and stat.S_IMODE(os.stat(assigned).st_mode) == 0o700)
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} an assigned fresh leaf is atomically reserved mode 0700")
        got, why = scratch_decision(
            {"prompt": f"Scratch: {assigned}\n"}, root,
            session_id="s1", agent_name="w2", nonce="reused")
        ok = got == "deny" and "already exists" in why
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a second spawn cannot reuse one reservation")

        for label, named, ti in (
            ("no Scratch line is denied", "expected 1", {"prompt": "do it"}),
            ("two Scratch lines are denied", "expected 1",
             {"prompt": f"Scratch: {fresh('a')}\nScratch: {fresh('b')}\n"}),
            ("a relative scratch path is denied", "is not absolute",
             {"prompt": "Scratch: ./w1\n"}),
            ("a sibling inside the worktree is denied", "inside the checkout",
             {"prompt": f"Scratch: {os.path.join(adopted, 'sibling')}\n"}),
            ("a path above the worktree is denied", "inside or above the checkout",
             {"prompt": f"Scratch: {os.path.dirname(adopted)}\n"}),
            ("a Scratch line with trailing text is not a marker", "expected 1",
             {"prompt": f"Scratch: {fresh('trailing')} and also do Y\n"}),
            ("a Scratch line mid-line is not a marker", "expected 1",
             {"prompt": f"please use Scratch: {fresh('midline')}\n"}),
            ("a non-object tool_input fails closed", "fails closed", None),
        ):
            got, why = scratch_decision(ti, root, session_id="s1", reserve=False,
                                        nonce=label)
            ok = got == "deny" and named in why
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} {label}")

        missing_parent = os.path.join(_root, "missing-parent", "leaf")
        got, why = scratch_decision(
            {"prompt": f"Scratch: {missing_parent}\n"}, root,
            reserve=False, nonce="missing-parent")
        ok = got == "deny" and "cannot inspect scratch parent component" in why
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a missing scratch parent fails closed")

        root_candidate = fresh("rooted")
        got, why = scratch_decision(
            {"prompt": f"Scratch: {root_candidate}\n"}, os.sep,
            reserve=False, nonce="root")
        ok = got == "deny" and "inside the checkout" in why
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a workspace at filesystem root refuses every scratch")

        existing_dir = fresh("existing-dir"); os.mkdir(existing_dir)
        regular = fresh("regular"); open(regular, "w").write("x")
        symlink = fresh("symlink"); os.symlink(existing_dir, symlink)
        dangling = fresh("dangling"); os.symlink(fresh("missing-target"), dangling)
        for label, path in (
            ("an existing directory is rejected as potentially shared", existing_dir),
            ("a regular file is not a scratch directory", regular),
            ("a directory symlink is not a fresh reservation", symlink),
            ("a dangling symlink is not a fresh reservation", dangling),
            ("a device is not a scratch directory", os.devnull),
        ):
            got, why = scratch_decision(
                {"prompt": f"Scratch: {path}\n"}, root, reserve=False, nonce=label)
            ok = got == "deny" and "already exists" in why
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} {label}")

        alias = os.path.join(_root, "alias")
        os.symlink(adopted, alias)
        got, why = scratch_decision(
            {"prompt": f"Scratch: {os.path.join(alias, 'alias-leaf')}\n"}, root,
            reserve=False, nonce="alias")
        ok = got == "deny" and "symlink component" in why
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a symlink alias of the checkout is denied")

        inside_subdir = os.path.join(adopted, "inside", "existing")
        os.makedirs(inside_subdir)
        subdir_alias = os.path.join(_root, "subdir-alias")
        os.symlink(os.path.join(adopted, "inside"), subdir_alias)
        hidden_inside = os.path.join(subdir_alias, "existing", "worker")
        got, why = scratch_decision(
            {"prompt": f"Scratch: {hidden_inside}\n"}, root,
            nonce="subdir-alias")
        ok = (got == "deny" and "symlink component" in why
              and not os.path.lexists(hidden_inside))
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a symlink to a checkout subdirectory cannot hide containment")

        dotdot_inside = os.path.join(subdir_alias, "..", "worker-dotdot")
        dotdot_resolved = os.path.realpath(dotdot_inside)
        dotdot_normalized = os.path.abspath(dotdot_inside)
        got, why = scratch_decision(
            {"prompt": f"Scratch: {dotdot_inside}\n"}, root,
            nonce="dotdot-alias")
        ok = (got == "deny" and "dot path components" in why
              and not os.path.lexists(dotdot_resolved)
              and not os.path.lexists(dotdot_normalized))
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} dot components cannot change the reserved directory")

        real_samefile = os.path.samefile
        def identity_eio(_left, _right):
            raise OSError(5, "planted identity EIO")
        try:
            os.path.samefile = identity_eio
            got, why = scratch_decision(
                {"prompt": f"Scratch: {fresh('identity-eio')}\n"}, root,
                reserve=False, nonce="identity-eio")
        finally:
            os.path.samefile = real_samefile
        ok = got == "deny" and "planted identity EIO" in why
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} filesystem identity errors fail closed")

        real_reserve = reserve_scratch
        def reserve_value_error(_path, _workspace_root):
            raise ValueError("planted reserve ValueError")
        try:
            globals()["reserve_scratch"] = reserve_value_error
            got, why = scratch_decision(
                {"prompt": f"Scratch: {fresh('reserve-value-error')}\n"}, root,
                nonce="reserve-value-error")
        finally:
            globals()["reserve_scratch"] = real_reserve
        ok = got == "deny" and "planted reserve ValueError" in why
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} reservation value errors fail closed")

        case_alias_supported = False
        case_alias_ok = True
        if sys.platform == "darwin":
            case_alias = adopted.swapcase()
            try:
                case_alias_supported = os.path.samefile(case_alias, adopted)
            except OSError:
                case_alias_supported = False
            if case_alias_supported:
                got, why = scratch_decision(
                    {"prompt": f"Scratch: {os.path.join(case_alias, 'case-leaf')}\n"},
                    root, reserve=False, nonce="case")
                case_alias_ok = got == "deny" and "inside the checkout" in why
        ok = not case_alias_supported or case_alias_ok
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a real macOS case alias cannot narrow containment")

        suggestions = [
            suggested_scratch(root, "../../session", "../../worker") for _ in range(2)
        ]
        unnamed = [suggested_scratch(root, None, None) for _ in range(2)]
        ok = (len(set(suggestions + unnamed)) == 4
              and all(os.path.dirname(path) == os.path.realpath(tempfile.gettempdir())
                      for path in suggestions + unnamed))
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} named and unnamed suggestions are unique and path-safe")
        suggested = suggested_scratch(
            root, "s1", "w1", nonce=os.path.basename(_root))
        got, why = scratch_decision(
            {"message": f"Scratch: {suggested}\n"}, root,
            session_id="s1", agent_name="w1", nonce="unused")
        ok = got == "allow" and not why and os.path.isdir(suggested)
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} the Codex message field can reserve a suggested path")

        simultaneous = fresh("simultaneous")
        barrier = threading.Barrier(2)
        outcomes = []
        def reserve_once():
            barrier.wait()
            try:
                reserve_scratch(simultaneous, root)
                outcomes.append("allow")
            except ScratchPolicyError:
                outcomes.append("deny")
        workers = [threading.Thread(target=reserve_once) for _ in range(2)]
        for worker in workers: worker.start()
        for worker in workers: worker.join()
        ok = sorted(outcomes) == ["allow", "deny"]
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} two concurrent reservations yield one winner")

        # Containment answered from the descriptor, not from the name. The two unit cases
        # pin both directions; the splice below is the reason the helper exists.
        _walk_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        inside_probe = os.path.join(adopted, "inside-probe")
        outside_probe = fresh("outside-probe")
        os.makedirs(inside_probe); os.makedirs(outside_probe)
        for label, probe, want in (("inside the checkout", inside_probe, True),
                                   ("outside the checkout", outside_probe, False)):
            probe_fd = os.open(probe, _walk_flags)
            try:
                ok = _fd_within_workspace(probe_fd, root) is want
            finally:
                os.close(probe_fd)
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} the ancestor walk reports a descriptor {label}")

        # The walk has two independent terminators -- the parent-is-itself test and the
        # depth bound -- and each masks the other, so neither can be killed on its own.
        # Removing BOTH hangs the suite rather than reddening it. This case pins the
        # observable property they jointly produce: a walk that reaches the filesystem
        # root answers, rather than spinning inside a hook that runs on every spawn.
        root_fd = os.open(os.sep, _walk_flags)
        try:
            walked = _fd_within_workspace(root_fd, adopted)
        finally:
            os.close(root_fd)
        ok = walked is False
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} the ancestor walk terminates at the filesystem root")

        root_fd = os.open(os.sep, _walk_flags)
        try:
            try:
                _fd_within_workspace(root_fd, adopted, limit=0)
                limit_problem = ""
            except ScratchPolicyError as exc:
                limit_problem = str(exc)
        finally:
            os.close(root_fd)
        ok = "proof exhausted" in limit_problem
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} an exhausted descriptor walk fails closed")

        ancestry_io_target = fresh("ancestry-io")
        real_open = os.open
        def ancestry_open(path, *args, **kwargs):
            if path == "..":
                raise OSError(5, "planted ancestry EIO")
            return real_open(path, *args, **kwargs)
        try:
            os.open = ancestry_open
            got, why = scratch_decision(
                {"prompt": f"Scratch: {ancestry_io_target}\n"}, root,
                nonce="ancestry-io")
        finally:
            os.open = real_open
        ok = (got == "deny" and "planted ancestry EIO" in why
              and not os.path.lexists(ancestry_io_target))
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} ancestry I/O failure denies without creating scratch")

        stable_open_target = fresh("stable-open-io")
        stable_component = os.path.basename(os.path.dirname(stable_open_target))
        def stable_component_open(path, *args, **kwargs):
            if path == stable_component and kwargs.get("dir_fd") is not None:
                raise OSError(5, "planted stable-open EIO")
            return real_open(path, *args, **kwargs)
        try:
            os.open = stable_component_open
            got, why = scratch_decision(
                {"prompt": f"Scratch: {stable_open_target}\n"}, root,
                nonce="stable-open-io")
        finally:
            os.open = real_open
        ok = (got == "deny" and "planted stable-open EIO" in why
              and not os.path.lexists(stable_open_target))
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} stable-parent open failure denies without creating scratch")

        # A path already reserved is refused, and the refusal has to carry a DIFFERENT path
        # or the parent has no way forward. Without the fresh suggestion this denial is a
        # dead end rather than a retry.
        taken = fresh("already-taken")
        first_decision, _ = scratch_decision(
            {"prompt": f"x\nScratch: {taken}\n"}, root, session_id="s1", agent_name="w1")
        second_decision, second_reason = scratch_decision(
            {"prompt": f"x\nScratch: {taken}\n"}, root, session_id="s1", agent_name="w1")
        suggested_again = re.search(r"Scratch: (\S+)", second_reason)
        ok = (first_decision == "allow" and second_decision == "deny"
              and suggested_again is not None and suggested_again.group(1) != taken)
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a taken path is refused with a different path to retry on")

        # Four rejection conditions in the workspace-root and path helpers had no case: each
        # is reachable from a real input, and each was removable with this suite green.
        try:
            protected_workspace_root(os.path.join(adopted, "README-not-a-dir"))
            cwd_problem = ""
        except ScratchPolicyError as exc:
            cwd_problem = str(exc)
        ok = "not an existing directory" in cwd_problem
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a cwd that is not a directory is refused by name")

        class _GitReply:
            def __init__(self, returncode, stdout):
                self.returncode, self.stdout, self.stderr = returncode, stdout, b"detail"

        try:
            protected_workspace_root(
                nested, lambda *a, **k: _GitReply(128, b""))
            git_problem = ""
        except ScratchPolicyError as exc:
            git_problem = str(exc)
        ok = "exited 128" in git_problem
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a failed worktree-root query is refused by its exit status")

        # Git on a CRLF-configured host terminates the path with CR before LF. Stripping it is
        # what makes the reported root compare equal; without it every spawn there is refused.
        try:
            crlf_root = protected_workspace_root(
                nested, lambda *a, **k: _GitReply(0, os.fsencode(adopted) + b"\r\n"))
        except ScratchPolicyError:
            crlf_root = None
        ok = crlf_root == os.path.realpath(adopted)
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a carriage-returned worktree root still resolves")

        # The empty-leaf branch is reachable only when the path resolves to the filesystem
        # root: os.path.abspath strips a trailing separator, so "/tmp/x/" still has a leaf.
        # An ambient GIT_DIR/GIT_WORK_TREE must not decide which worktree this is. Removing
        # the scrub does not open a hole -- the reported root then fails the marker-root
        # comparison and the spawn is refused -- so what the scrub actually buys is that a
        # developer carrying those variables is served rather than refused.
        _prior_git_dir = os.environ.get("GIT_DIR")
        os.environ["GIT_DIR"] = os.path.join(plain, "not-a-repo")
        try:
            ambient_root = protected_workspace_root(nested)
        except ScratchPolicyError:
            ambient_root = None
        finally:
            if _prior_git_dir is None:
                os.environ.pop("GIT_DIR", None)
            else:
                os.environ["GIT_DIR"] = _prior_git_dir
        ok = ambient_root == os.path.realpath(adopted)
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} an ambient GIT_DIR does not decide the workspace root")

        ok = "has no directory leaf" in _scratch_path_error(os.sep, root)
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a scratch path that is the filesystem root is refused")

        # An unmodelled exception must become a denial. Unhandled, the process exits 1, and
        # this host continues the tool call on any exit other than 2 -- so a crash is an allow.
        def _unmodelled_reserve(path, workspace_root):
            """Raise a type neither OSError nor ValueError covers."""
            raise NotImplementedError("mkdir: dir_fd unavailable on this platform")

        real_reserve = reserve_scratch
        globals()["reserve_scratch"] = _unmodelled_reserve
        try:
            unmodelled_payload = {
                "tool_name": "Agent", "cwd": nested, "session_id": "s1",
                "tool_input": {"name": "w1", "prompt": f"x\nScratch: {fresh('unmodelled')}\n"}}
            rc_u, out_u = run_payload(
                unmodelled_payload, runtime="claude", require_scratch=True)
        finally:
            globals()["reserve_scratch"] = real_reserve
        ok = rc_u == 0 and '"permissionDecision": "deny"' in out_u and "unmodelled" in out_u
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} an unmodelled reservation error denies instead of exiting open")

        # The splice: a name that PASSES the path check, then an ancestor swap, then the
        # reservation. Deterministic rather than raced, because a flaky case proves nothing.
        # Without the descriptor walk the swap is invisible and the directory lands in the
        # checkout, which is the one placement this guard exists to refuse.
        splice_out = fresh("splice-out")
        splice_in = os.path.join(adopted, "splice-in")
        splice_name = os.path.join(_root, "splice-name")
        os.makedirs(os.path.join(splice_name, "sub")); os.makedirs(os.path.join(splice_in, "sub"))
        spliced_target = os.path.join(splice_name, "sub", "w1")
        name_accepted = _scratch_path_error(spliced_target, root) == ""
        os.rename(splice_name, splice_out); os.symlink(splice_in, splice_name)
        try:
            reserve_scratch(spliced_target, root)
            spliced = "reserved"
        except ScratchPolicyError:
            spliced = "refused"
        landed_inside = os.path.isdir(os.path.join(splice_in, "sub", "w1"))
        ok = name_accepted and spliced == "refused" and not landed_inside
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} an ancestor swapped after the path check cannot place scratch in the checkout")

        for label, want, ti in (
            ("a Claude name is read", "w1", {"name": "w1"}),
            ("a Codex task_name is read", "w2", {"task_name": "w2"}),
            ("an absent worker name is None", None, {"prompt": "x"}),
        ):
            ok = worker_name(ti) == want
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} {label}")

        # A registration may pass a flag a older guard build does not know. That must stay a
        # refusal -- accepting it would leave require_scratch False and silently disable the
        # workspace check -- and the refusal has to name the ordering remedy, because the
        # bare "unknown argument" reads as a typo rather than a half-finished install.
        # stdin carries a payload the guard would ALLOW. If an unrecognised flag were to fall
        # through instead of refusing, that payload would be processed and the run would exit 0,
        # so the case separates "refused" from "printed a message and refused for some other
        # reason" -- the diagnostic is written before the return and cannot carry the assertion
        # on its own.
        import io as _io
        _err = _io.StringIO()
        _saved_err, _saved_in = sys.stderr, sys.stdin
        sys.stderr = _err
        sys.stdin = _io.StringIO(json.dumps(
            {"tool_name": "Agent", "cwd": nested, "session_id": "s1",
             "tool_input": {"name": "w1", "prompt": "do it"}}))
        try:
            unknown_rc = main(["spawn_preflight_guard.py", "--flag-from-a-newer-registration"])
        finally:
            sys.stderr, sys.stdin = _saved_err, _saved_in
        unknown_text = _err.getvalue()
        ok = unknown_rc == 2 and "partially synchronised installation" in unknown_text
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} an unrecognised registration flag refuses and names the ordering")
        ok = unknown_rc == 2 and VERSION in unknown_text
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} the refusal reports which guard build rejected the flag")

        payload = {"tool_name": "Agent", "cwd": nested, "session_id": "s1",
                   "tool_input": {"name": "w1", "prompt": "do it"}}
        old_pct = os.environ.get("SPAWN_GUARD_DF_PCT")
        os.environ["SPAWN_GUARD_DF_PCT"] = "50"
        try:
            rc, out = run_payload(payload, runtime="claude", require_scratch=True)
            ok = rc == 0 and '"permissionDecision": "deny"' in out and "Scratch:" in out
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} required mode denies an unassigned plain spawn")

            rc, out = run_payload(
                {"tool_name": "spawn_agent", "cwd": plain, "session_id": "s1",
                 "tool_input": {"message": "do it"}},
                runtime="codex", require_scratch=True)
            ok = ('"permissionDecision": "deny"' in out and "Scratch:" in out)
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} Codex required mode covers a plain project")

            task_payload = dict(payload, tool_name="Task")
            rc, out = run_payload(task_payload, runtime="claude", require_scratch=True)
            ok = rc == 0 and '"permissionDecision": "deny"' in out
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} required mode covers the Task spawn alias")

            rc, out = run_payload(payload, runtime="claude", require_scratch=False)
            ok = rc == 0 and out == ""
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} capacity-only mode stays explicitly available")

            e2e = fresh("e2e")
            payload["tool_input"]["prompt"] = f"do it\nScratch: {e2e}\n"
            rc, out = run_payload(payload, runtime="claude", require_scratch=True)
            ok = rc == 0 and out == "" and os.path.isdir(e2e)
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} required mode reserves an assigned directory")

            rc, out = run_payload(
                {"tool_name": "Agent", "cwd": None, "tool_input": {"prompt": "do it"}},
                runtime="codex", require_scratch=True)
            ok = rc == 0 and '"permissionDecision": "deny"' in out and "usable cwd" in out
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} required mode fails closed on missing cwd")

            nul_payload = {
                "tool_name": "Agent", "cwd": plain, "session_id": "s1",
                "tool_input": {"prompt": f"Scratch: {fresh('nul')}\0leaf\n"},
            }
            rc, out = run_payload(
                nul_payload, runtime="claude", require_scratch=True)
            try:
                receipt = json.loads(out)
                specific = receipt["hookSpecificOutput"]
            except (KeyError, TypeError, json.JSONDecodeError):
                specific = {}
            ok = (rc == 0 and specific.get("permissionDecision") == "deny"
                  and "NUL byte" in specific.get("permissionDecisionReason", ""))
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} an embedded NUL returns a named deny decision")

            surrogate_payload = {
                "tool_name": "Agent", "cwd": plain, "session_id": "s1",
                "tool_input": {
                    "prompt": f"Scratch: {fresh('surrogate')}\ud800\n"},
            }
            rc, out = run_payload(
                surrogate_payload, runtime="claude", require_scratch=True)
            try:
                receipt = json.loads(out)
                specific = receipt["hookSpecificOutput"]
            except (KeyError, TypeError, json.JSONDecodeError):
                specific = {}
            ok = (rc == 0 and specific.get("permissionDecision") == "deny"
                  and "cannot be represented" in
                  specific.get("permissionDecisionReason", ""))
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} an unrepresentable path returns a named deny decision")

            real_reserve = reserve_scratch
            def reserve_os_error(_path, _workspace_root):
                raise OSError(5, "planted reserve OSError")
            try:
                globals()["reserve_scratch"] = reserve_os_error
                raw_oserror_payload = {
                    "tool_name": "Agent", "cwd": plain, "session_id": "s1",
                    "tool_input": {
                        "prompt": f"Scratch: {fresh('reserve-oserror')}\n"},
                }
                rc, out = run_payload(
                    raw_oserror_payload, runtime="claude", require_scratch=True)
            finally:
                globals()["reserve_scratch"] = real_reserve
            try:
                receipt = json.loads(out)
                specific = receipt["hookSpecificOutput"]
            except (KeyError, TypeError, json.JSONDecodeError):
                specific = {}
            ok = (rc == 0 and specific.get("permissionDecision") == "deny"
                  and "planted reserve OSError" in
                  specific.get("permissionDecisionReason", ""))
            bad += (not ok); checks += 1
            print(f"  {'PASS' if ok else 'FAIL'} a raw reservation OSError returns a named deny decision")
        finally:
            if old_pct is None:
                del os.environ["SPAWN_GUARD_DF_PCT"]
            else:
                os.environ["SPAWN_GUARD_DF_PCT"] = old_pct

        codex_warn = fresh("codex-warn")
        payload["tool_input"]["prompt"] = f"Scratch: {codex_warn}\n"
        os.environ["SPAWN_GUARD_DF_PCT"] = "92"
        rc, out = run_payload(payload, runtime="codex", require_scratch=True)
        del os.environ["SPAWN_GUARD_DF_PCT"]
        ok = ('"permissionDecision": "deny"' in out and not os.path.lexists(codex_warn))
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a Codex capacity deny creates no reservation")

        claude_warn = fresh("claude-warn")
        payload["tool_input"]["prompt"] = f"Scratch: {claude_warn}\n"
        os.environ["SPAWN_GUARD_DF_PCT"] = "92"
        rc, out = run_payload(payload, runtime="claude", require_scratch=True)
        del os.environ["SPAWN_GUARD_DF_PCT"]
        ok = ('"permissionDecision": "ask"' in out and os.path.isdir(claude_warn))
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a Claude capacity ask reserves before confirmation")

        full = fresh("full")
        payload["tool_input"]["prompt"] = f"Scratch: {full}\n"
        os.environ["SPAWN_GUARD_DF_PCT"] = "99"
        rc, out = run_payload(payload, runtime="claude", require_scratch=True)
        del os.environ["SPAWN_GUARD_DF_PCT"]
        ok = "data volume" in out and not os.path.lexists(full)
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} a full-volume denial creates no reservation")

        payload["tool_input"]["prompt"] = "do it"
        os.environ["SPAWN_GUARD_DF_PCT"] = "99"
        rc, out = run_payload(payload, runtime="claude", require_scratch=True)
        del os.environ["SPAWN_GUARD_DF_PCT"]
        ok = "data volume" in out and "Scratch:" in out
        bad += (not ok); checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} capacity and assignment failures are both reported")

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


def run_payload(payload, runtime="claude", require_scratch=False):
    """In-process hook-mode run -> (exit_code, stdout_text)."""
    import io
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rc = hook_mode(
            json.dumps(payload), runtime=runtime, require_scratch=require_scratch)
    finally:
        sys.stdout = old
    return rc, buf.getvalue()


def run_raw(raw, runtime="claude", require_scratch=False):
    """In-process raw hook run -> (exit_code, stdout_text, stderr_text)."""
    import io
    out, err = io.StringIO(), io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    try:
        rc = hook_mode(raw, runtime=runtime, require_scratch=require_scratch)
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    return rc, out.getvalue(), err.getvalue()


def hook_mode(raw, runtime="claude", require_scratch=False):
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
    if runtime == "codex" and decision == "ask":
        decision = "deny"
        reason += (" Codex PreToolUse cannot request confirmation, so z-harness "
                   "fails closed; inspect capacity and retry the spawn.")
    # Scratch is an installed-hook contract, not a policy bit controlled by the repository
    # being inspected. Both shipped registrations pass --require-scratch. Keeping the flag
    # explicit preserves capacity-only use for a deliberate standalone installation.
    if require_scratch:
        tool_input = payload.get("tool_input")
        try:
            workspace_root = protected_workspace_root(payload.get("cwd"))
            workspace_decision, workspace_reason = scratch_decision(
                tool_input, workspace_root,
                session_id=payload.get("session_id"),
                agent_name=worker_name(tool_input),
                # Reserve on ask as well as allow. PreToolUse never learns whether the user
                # confirmed, so a reservation taken here can never be reclaimed by this hook;
                # the alternative is to reserve only on allow, which would leave every
                # ask-band spawn without collision exclusivity in exactly the band where a
                # collision is most damaging. The cost of reserving early is that a declined
                # ask leaves a directory under the system temp root and denies that one path
                # on retry. That is recoverable: the refusal carries a fresh path, and a case
                # below pins that it differs from the one already taken.
                reserve=decision != "deny")
        except ScratchPolicyError as exc:
            workspace_decision = "deny"
            workspace_reason = f"scratch policy could not be evaluated safely: {exc}"
        except Exception as exc:
            # Anything unmodelled -- a platform without dir_fd raises NotImplementedError,
            # which is neither OSError nor ValueError. Letting it escape ends the process at
            # exit 1, and this host's PreToolUse contract continues the tool call on any exit
            # other than 2, so an unhandled error here is an allow. Fail closed instead.
            workspace_decision = "deny"
            workspace_reason = (
                f"scratch policy raised an unmodelled {type(exc).__name__}: {exc}; "
                "z-harness fails closed rather than spawning unchecked")
        if workspace_decision == "deny":
            reason = (workspace_reason if decision == "allow"
                      else f"{reason} {workspace_reason}")
            decision = "deny"
    if decision == "allow":
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason}}, indent=1))
    return 0


_GIT_REPOSITORY_ENV = frozenset({
    "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES", "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    "GIT_NAMESPACE",
})


def sanitized_git_environment(source=None):
    """Remove ambient selectors that could substitute another repository."""
    env = dict(os.environ if source is None else source)
    for key in tuple(env):
        if (key in _GIT_REPOSITORY_ENV or key == "GIT_CONFIG"
                or key.startswith("GIT_CONFIG_")):
            del env[key]
    return env


def _same_file(left, right):
    try:
        return os.path.samefile(left, right)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ScratchPolicyError(
            f"cannot compare filesystem identities {left!r} and {right!r}: {exc}") from exc


def protected_workspace_root(cwd, runner=None):
    """Resolve the physical project root that a scratch directory must not overlap."""
    if not isinstance(cwd, str) or not cwd:
        raise ScratchPolicyError("spawn payload has no usable cwd")
    if not os.path.isdir(cwd):
        raise ScratchPolicyError(f"spawn cwd is not an existing directory: {cwd!r}")
    physical_cwd = os.path.realpath(cwd)
    marker_root = physical_cwd
    while not os.path.lexists(os.path.join(marker_root, ".git")):
        parent = os.path.dirname(marker_root)
        if parent == marker_root:
            return physical_cwd
        marker_root = parent

    runner = subprocess.run if runner is None else runner
    try:
        done = runner(
            ["git", "-C", physical_cwd, "rev-parse", "--show-toplevel"],
            capture_output=True, text=False, timeout=2,
            env=sanitized_git_environment())
    except (OSError, subprocess.SubprocessError) as exc:
        raise ScratchPolicyError(f"cannot resolve the Git worktree root: {exc}") from exc
    if done.returncode != 0:
        detail = bytes(done.stderr or b"").decode("utf-8", "replace").strip()
        raise ScratchPolicyError(
            f"git rev-parse --show-toplevel exited {done.returncode}"
            f"{': ' + detail[:200] if detail else ''}")
    raw = bytes(done.stdout)
    if not raw.endswith(b"\n") or b"\0" in raw or b"\n" in raw[:-1]:
        raise ScratchPolicyError("git rev-parse --show-toplevel returned a malformed path")
    value = raw[:-1]
    if value.endswith(b"\r"):
        value = value[:-1]
    reported = os.fsdecode(value)
    if not os.path.isdir(reported) or not _same_file(reported, marker_root):
        raise ScratchPolicyError(
            f"git resolved worktree root {reported!r}, expected {marker_root!r}")
    return os.path.realpath(reported)


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


def _readable_digest(value, fallback):
    text = value if isinstance(value, str) and value else fallback
    label = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()[:20] or fallback
    digest = hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()[:10]
    return f"{label}-{digest}"


def suggested_scratch(cwd, session_id, agent_name, nonce=None):
    """Return a fresh, path-safe reservation candidate beneath the host temp directory."""
    del cwd  # compatibility parameter; the suggestion is deliberately checkout-independent.
    token = secrets.token_hex(16) if nonce is None else str(nonce)
    token = re.sub(r"[^A-Za-z0-9]+", "", token) or secrets.token_hex(16)
    session = _readable_digest(session_id, "session")
    worker = _readable_digest(agent_name, "worker")
    return os.path.join(
        os.path.realpath(tempfile.gettempdir()),
        f"agent-scratch-{session}-{worker}-{token}")


def _path_ancestors(path):
    current = os.path.abspath(path)
    while True:
        yield current
        parent = os.path.dirname(current)
        if parent == current:
            return
        current = parent


def _scratch_path_error(path, workspace_root):
    """Return why `path` cannot be atomically reserved as fresh external scratch."""
    if not os.path.isabs(path):
        return f"the worker's scratch path {path!r} is not absolute"
    if "\0" in path:
        return f"the worker's scratch path {path!r} contains a NUL byte"
    try:
        os.fsencode(path)
    except (UnicodeError, ValueError) as exc:
        return f"the worker's scratch path {path!r} cannot be represented: {exc}"
    if any(part in {".", ".."} for part in path.split(os.sep)):
        return f"the worker's scratch path {path!r} contains dot path components"
    normalized = os.path.abspath(path)
    parent, leaf = os.path.dirname(normalized), os.path.basename(normalized)
    if not leaf:
        return f"the worker's scratch path {path!r} has no directory leaf"

    current = os.sep
    for component in [part for part in parent.split(os.sep) if part]:
        current = os.path.join(current, component)
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            return f"cannot inspect scratch parent component {current!r}: {exc}"
        if stat.S_ISLNK(metadata.st_mode):
            return (
                f"the worker's scratch parent uses symlink component {current!r}; "
                "use the physical path so the marker cannot be rebound after approval")

    # Walk the resolved existing parent ancestry by filesystem identity. This catches symlink
    # aliases to any checkout subdirectory and the case aliases accepted by default macOS
    # volumes without lowercasing case-sensitive paths. An absent candidate cannot be an
    # ancestor of the already-existing workspace.
    for ancestor in _path_ancestors(os.path.realpath(parent)):
        if _same_file(ancestor, workspace_root):
            return (
                f"the worker's scratch path {path!r} is inside the checkout "
                f"at {workspace_root!r}")
    if os.path.lexists(normalized):
        for ancestor in _path_ancestors(workspace_root):
            if _same_file(normalized, ancestor):
                return (
                    f"the worker's scratch path {path!r} is inside or above the checkout "
                    f"at {workspace_root!r}")
        return (
            f"the worker's scratch path {path!r} already exists; each spawn requires a "
            "fresh absent directory so two workers cannot reuse one reservation")
    if os.path.islink(parent) or not os.path.isdir(parent):
        return f"the worker's scratch parent {parent!r} is not a real existing directory"
    return ""


def _fd_within_workspace(parent_fd, workspace_root, limit=None):
    """-> True when the directory behind parent_fd is the workspace root, or below it.

    Answered from the open descriptor rather than from the path. `_scratch_path_error`
    proves containment by resolving names, and a rename or symlink swap between that
    proof and the mkdir moves the answer without changing any name it inspected. Walking
    up from the descriptor that will create the leaf closes that window, because the
    descriptor cannot be redirected once open.

    Failure to complete the proof is not an external-directory verdict. It raises a typed
    error that the public hook converts to a denial.
    """
    try:
        root_stat = os.stat(workspace_root)
    except OSError as exc:
        raise ScratchPolicyError(
            f"cannot identify workspace ancestry root {workspace_root!r}: {exc}") from exc
    root_id = (root_stat.st_dev, root_stat.st_ino)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        fd = os.dup(parent_fd)
    except OSError as exc:
        raise ScratchPolicyError(f"cannot duplicate scratch parent descriptor: {exc}") from exc
    try:
        # Bounded. A filesystem whose root does not report itself as its own parent would
        # otherwise spin here, inside a hook that runs on every spawn.
        for _ in range(_ANCESTOR_WALK_LIMIT if limit is None else limit):
            try:
                here = os.fstat(fd)
            except OSError as exc:
                raise ScratchPolicyError(
                    f"cannot inspect scratch ancestry descriptor: {exc}") from exc
            if (here.st_dev, here.st_ino) == root_id:
                return True
            try:
                up = os.open("..", flags, dir_fd=fd)
            except OSError as exc:
                raise ScratchPolicyError(
                    f"cannot open scratch ancestry parent: {exc}") from exc
            try:
                above = os.fstat(up)
            except OSError as exc:
                os.close(up)
                raise ScratchPolicyError(
                    f"cannot inspect scratch ancestry parent: {exc}") from exc
            if (above.st_dev, above.st_ino) == (here.st_dev, here.st_ino):
                os.close(up)
                return False
            os.close(fd)
            fd = up
        raise ScratchPolicyError(
            f"scratch ancestry proof exhausted {_ANCESTOR_WALK_LIMIT if limit is None else limit} "
            "directory steps")
    finally:
        os.close(fd)


def _open_stable_directory(path):
    """Open an absolute directory one no-follow component at a time."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(os.sep, flags)
    except OSError as exc:
        raise ScratchPolicyError(f"cannot open filesystem root for scratch: {exc}") from exc
    try:
        for component in [part for part in path.split(os.sep) if part]:
            try:
                child = os.open(component, flags, dir_fd=fd)
            except OSError as exc:
                raise ScratchPolicyError(
                    f"cannot open scratch parent component {component!r} beneath {path!r}: "
                    f"{exc}") from exc
            os.close(fd)
            fd = child
        return fd
    except Exception:
        os.close(fd)
        raise


def reserve_scratch(path, workspace_root):
    """Atomically create one mode-0700 directory; EEXIST is a collision, never success."""
    normalized = os.path.abspath(path)
    parent, leaf = os.path.dirname(normalized), os.path.basename(normalized)
    parent_fd = _open_stable_directory(parent)
    try:
        opened = os.fstat(parent_fd)
        current = os.stat(parent, follow_symlinks=False)
        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            raise ScratchPolicyError(f"scratch parent changed while being reserved: {parent!r}")
        if _fd_within_workspace(parent_fd, workspace_root):
            raise ScratchPolicyError(
                f"the scratch parent {parent!r} resolved inside the checkout at "
                f"{workspace_root!r} at the moment the directory would be created")
        try:
            os.mkdir(leaf, 0o700, dir_fd=parent_fd)
        except OSError as exc:
            raise ScratchPolicyError(
                f"cannot reserve fresh scratch directory {normalized!r}: {exc}") from exc
        created = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISDIR(created.st_mode):
            raise ScratchPolicyError(f"reserved scratch is not a directory: {normalized!r}")
        os.chmod(leaf, 0o700, dir_fd=parent_fd, follow_symlinks=False)
    finally:
        os.close(parent_fd)


def scratch_decision(
        tool_input, workspace_root, session_id=None, agent_name=None, reserve=True,
        nonce=None):
    """Deny a spawn without one fresh collision-exclusive external directory.

    The path must be absent, have a real external parent, and is created atomically mode 0700.
    Thus two concurrent spawns naming the same path cannot both pass. This prevents accidental
    cross-worker file collisions; it is not an OS security sandbox because workers share a uid.

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
    suggestion = suggested_scratch(workspace_root, session_id, agent_name, nonce=nonce)
    fix = f"Add a line reading exactly: Scratch: {suggestion}"
    found = SCRATCH_LINE.findall(prompt)
    if len(found) != 1:
        return ("deny",
                f"this installation's spawn-hook registration requires every dispatched "
                f"worker to own an exclusive scratch directory, and the spawn prompt has "
                f"{len(found)} 'Scratch:' lines, expected "
                f"1. Concurrent workers sharing one directory overwrite each other silently "
                f"and the loser measures the wrong thing. {fix}")
    path = found[0]
    try:
        problem = _scratch_path_error(path, workspace_root)
        if problem:
            return "deny", f"{problem}. {fix}"
        if reserve:
            reserve_scratch(path, workspace_root)
    except (OSError, ValueError) as exc:
        return "deny", f"scratch reservation failed closed: {exc}. {fix}"
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
    require_scratch = False
    while args and args[0] in {"--runtime", "--require-scratch"}:
        if args[0] == "--require-scratch":
            require_scratch = True
            args = args[1:]
            continue
        if len(args) < 2:
            sys.stderr.write("--runtime requires claude or codex\n")
            return 2
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
        # Fail closed, and name the likeliest cause. Accepting an unrecognised flag would
        # be worse: a typo such as --requre-scratch would leave require_scratch False and
        # silently disable the workspace check. A registration passing a flag this build
        # does not know means the guard source is older than the registration that calls
        # it, so the remedy is an ordering one.
        sys.stderr.write(
            f"unknown argument: {args[0]!r}\n"
            f"this build is spawn_preflight_guard {VERSION}; a registration passing a flag "
            f"it does not recognise indicates a partially synchronised installation. "
            f"Install the guard source before the registration that calls it.\n"
            f"run --help\n")
        return 2
    raw, error = read_hook_input(sys.stdin)
    if raw is None:
        print(error, file=sys.stderr)
        return 2
    return hook_mode(raw, runtime=runtime, require_scratch=require_scratch)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
