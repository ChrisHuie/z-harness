#!/usr/bin/env python3
"""Repository-ownership predicates shared by inventory and evidence tools.

A lexical ``.git`` entry is not an ownership boundary.  A boundary is accepted only
when Git resolves the candidate as its own worktree and its metadata proves an ordinary
repository, registered linked worktree, indexed gitlink, or separately-bound gitdir.

Exit codes: 0 selftest passed · 1 selftest failed · 2 usage error.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile


VERSION = "1.1.0"


class RepositoryOwnershipError(RuntimeError):
    """A repository boundary could not be proved or disproved reliably."""


def git_command_failure(returncode, stderr, command="git ls-files"):
    if isinstance(stderr, (bytes, bytearray)):
        detail = bytes(stderr).decode("utf-8", "replace").strip()
    else:
        detail = (stderr or "").strip()
    if detail:
        return f"{command} exited {returncode}: {detail}"
    return f"{command} exited {returncode} with no diagnostic on stderr"


_GIT_REPOSITORY_ENV = frozenset({
    "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE", "GIT_NO_REPLACE_OBJECTS",
    "GIT_REPLACE_REF_BASE", "GIT_PREFIX", "GIT_INTERNAL_SUPER_PREFIX",
    "GIT_SHALLOW_FILE", "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM", "GIT_NAMESPACE",
    "GIT_LITERAL_PATHSPECS", "GIT_GLOB_PATHSPECS",
    "GIT_NOGLOB_PATHSPECS", "GIT_ICASE_PATHSPECS",
})


def sanitized_git_environment(source=None):
    """Remove ambient selectors that could substitute another repository."""
    env = dict(os.environ if source is None else source)
    for key in tuple(env):
        if (key in _GIT_REPOSITORY_ENV or key == "GIT_CONFIG"
                or key.startswith("GIT_CONFIG_")):
            del env[key]
    return env


def run_git(runner, argv, **kwargs):
    """Run Git with repository and config selectors removed from the environment."""
    kwargs["env"] = sanitized_git_environment(kwargs.get("env"))
    return runner(argv, **kwargs)


def same_file(left, right):
    """Return whether two path spellings identify the same filesystem object.

    OSError only. A NUL byte in a candidate path raises ValueError from stat, and
    swallowing that here would answer -- silently, as "not the same object" -- for every
    operand upstream that rejects such a record on purpose. is_repository_boundary converts
    it into the modelled error instead, so a malformed record stays loud and the operand
    that refuses it keeps deciding.
    """
    try:
        return os.path.samefile(left, right)
    except OSError:
        return False


def git_toplevel_error(root, runner=None):
    """Return why Git did not resolve exactly the repository root it was given."""
    runner = subprocess.run if runner is None else runner
    try:
        done = run_git(
            runner, ["git", "-C", root, "rev-parse", "--show-toplevel"],
            capture_output=True, text=False)
    except OSError as exc:
        return f"cannot run git rev-parse --show-toplevel: {exc}"
    if done.returncode != 0:
        return git_command_failure(
            done.returncode, done.stderr, "git rev-parse --show-toplevel")
    raw = bytes(done.stdout)
    if not raw.endswith(b"\n") or b"\0" in raw:
        return "git rev-parse --show-toplevel returned a malformed path"
    value = raw[:-1]
    if value.endswith(b"\r"):
        value = value[:-1]
    reported = os.fsdecode(value)
    if not same_file(reported, root):
        return (
            "git rev-parse --show-toplevel resolved "
            f"{reported!r}, expected {os.path.realpath(root)!r}"
        )
    return ""


def _git_path_line(path, prefix=b""):
    try:
        with open(path, "rb") as source:
            raw = source.read()
    except OSError:
        return None
    if not raw.startswith(prefix):
        return None
    value = raw[len(prefix):]
    if not value.endswith(b"\n") or b"\0" in value:
        return None
    value = value[:-1]
    if value.endswith(b"\r"):
        value = value[:-1]
    return os.fsdecode(value)


def _gitdir_from_marker(path, marker):
    if os.path.isdir(marker):
        return os.path.realpath(marker)
    if not os.path.isfile(marker):
        return None
    pointer = _git_path_line(marker, b"gitdir: ")
    if pointer is None:
        return None
    return os.path.realpath(
        pointer if os.path.isabs(pointer) else os.path.join(path, pointer))


def _git_common_dir(admin):
    pointer = _git_path_line(os.path.join(admin, "commondir"))
    if pointer is None:
        return admin
    return os.path.realpath(
        pointer if os.path.isabs(pointer) else os.path.join(admin, pointer))


def _indexed_gitlink(path, owner_root, runner):
    # A markerless installed-package root has no Git index and therefore cannot own a
    # gitlink. Do not manufacture an operational failure by asking Git for an index that
    # the caller already knows does not exist.
    if owner_root is None or not os.path.lexists(os.path.join(owner_root, ".git")):
        return False
    relative = os.path.relpath(path, owner_root).replace(os.sep, "/")
    if relative == ".." or relative.startswith("../"):
        return False
    try:
        staged = run_git(
            runner,
            ["git", "-C", owner_root, "ls-files", "--stage", "-z", "--", relative],
            capture_output=True, text=False)
    except (OSError, ValueError) as exc:
        raise RepositoryOwnershipError(
            f"cannot inspect indexed gitlink {path!r}: "
            f"cannot run git ls-files --stage: {exc}") from exc
    if staged.returncode != 0:
        raise RepositoryOwnershipError(
            f"cannot inspect indexed gitlink {path!r}: "
            + git_command_failure(
                staged.returncode, staged.stderr, "git ls-files --stage"))
    for record in bytes(staged.stdout).split(b"\0"):
        metadata, separator, recorded_path = record.partition(b"\t")
        if (separator and metadata.startswith(b"160000 ")
                and recorded_path.decode("utf-8", "surrogateescape") == relative):
            return True
    return False


def _registered_linked_worktree(path, marker):
    admin = _gitdir_from_marker(path, marker)
    if admin is None:
        return False
    common_pointer = _git_path_line(os.path.join(admin, "commondir"))
    if common_pointer is None:
        return False
    common = _git_common_dir(admin)
    if not same_file(os.path.dirname(admin), os.path.join(common, "worktrees")):
        return False
    backlink = _git_path_line(os.path.join(admin, "gitdir"))
    if backlink is None:
        return False
    backlink = os.path.realpath(
        backlink if os.path.isabs(backlink) else os.path.join(admin, backlink))
    return same_file(backlink, marker)


def _bound_separate_gitdir(path, marker, runner):
    admin = _gitdir_from_marker(path, marker)
    if admin is None or not os.path.isdir(admin):
        return False
    if (os.path.lexists(os.path.join(admin, "commondir"))
            or os.path.lexists(os.path.join(admin, "gitdir"))):
        return False
    configured = run_git(
        runner,
        ["git", "--git-dir", admin, "config", "--local", "--path", "--null",
         "--get-all", "core.worktree"], capture_output=True, text=False)
    raw = bytes(configured.stdout)
    # The terminator count refuses a multi-valued record where the record is read. Without
    # it the joined value reaches os.path.samefile carrying a NUL, which is a raised error
    # rather than a decision -- so the operand is what makes this a refusal.
    if configured.returncode != 0 or not raw.endswith(b"\0") or raw.count(b"\0") != 1:
        return False
    worktree = os.fsdecode(raw[:-1])
    if not os.path.isabs(worktree):
        worktree = os.path.join(admin, worktree)
    return same_file(worktree, path)


def _plausible_repository_marker(path, marker, owner_root):
    """Return whether marker has repository metadata that makes probe failure unknown.

    A malformed lexical marker stays outer-owned and must be scanned. Once a marker names
    a distinct Git administration directory with a HEAD, however, a nonzero Git probe no
    longer proves that no boundary exists. Treating that operational failure as ``False``
    lets a genuine nested repository disappear into the outer scan set.
    """
    if os.path.isdir(marker):
        return os.path.isfile(os.path.join(marker, "HEAD"))
    if not os.path.isfile(marker):
        return False
    admin = _gitdir_from_marker(path, marker)
    if admin is None or not os.path.isfile(os.path.join(admin, "HEAD")):
        return False
    if owner_root is None:
        return True
    owner_marker = os.path.join(owner_root, ".git")
    owner_admin = (_gitdir_from_marker(owner_root, owner_marker)
                   if os.path.isfile(owner_marker) else owner_marker)
    return owner_admin is None or not same_file(admin, owner_admin)


def is_repository_boundary(path, owner_root=None, runner=None):
    """Return true only for a proven independent Git worktree at ``path``."""
    runner = subprocess.run if runner is None else runner
    marker = os.path.join(path, ".git")
    if not os.path.lexists(marker) or os.path.islink(marker):
        return False
    toplevel_problem = git_toplevel_error(path, runner)
    if (toplevel_problem.startswith("cannot run git rev-parse")
            or (toplevel_problem.startswith("git rev-parse --show-toplevel exited")
                and _plausible_repository_marker(path, marker, owner_root))):
        raise RepositoryOwnershipError(toplevel_problem)
    if toplevel_problem:
        return False
    if os.path.isdir(marker):
        return True
    if not os.path.isfile(marker):
        return False
    try:
        indexed_problem = None
        try:
            if _indexed_gitlink(path, owner_root, runner):
                return True
        except RepositoryOwnershipError as exc:
            # A failed index read makes this operand unknown, not false. Another ownership
            # arm may still prove the boundary independently; only re-raise when neither
            # does, preserving the three-valued rule ``unknown OR true == true``.
            indexed_problem = exc
        if (_registered_linked_worktree(path, marker)
                or _bound_separate_gitdir(path, marker, runner)):
            return True
        if indexed_problem is not None:
            raise indexed_problem
        return False
    except RepositoryOwnershipError:
        raise
    except (OSError, ValueError) as exc:
        # ValueError as well as OSError: a malformed record reaching os.path.samefile with
        # an embedded NUL raises it, and callers model RepositoryOwnershipError alone, so
        # letting it through would surface the ownership layer as an unhandled exception.
        # Converted here rather than absorbed in same_file, which would turn every such
        # record into a silent "not a boundary" and retire the operands that reject one.
        raise RepositoryOwnershipError(
            f"cannot resolve Git ownership for {path!r}: {exc}") from exc


def boundary_between(root, candidate, runner=None):
    """Return the first proven nested repository root owning ``candidate``, if any."""
    root_real = os.path.realpath(root)
    current = os.path.dirname(os.path.realpath(candidate))
    while current != root_real:
        try:
            if os.path.commonpath([current, root_real]) != root_real:
                return None
        except ValueError:
            return None
        if is_repository_boundary(current, root_real, runner):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent
    return None


def selftest():
    checks = failures = 0

    def expect(label, ok):
        nonlocal checks, failures
        checks += 1
        failures += not ok
        print(f"  {'PASS' if ok else 'FAIL'} {label}")

    hostile = {
        "PATH": "/bin", "SENTINEL": "kept", "GIT_AUTHOR_NAME": "kept",
        "GIT_DIR": "/wrong", "GIT_WORK_TREE": "/wrong",
        "GIT_CONFIG": "/wrong", "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.worktree", "GIT_LITERAL_PATHSPECS": "1",
    }
    cleaned = sanitized_git_environment(hostile)
    expect("repository selectors are removed while benign variables remain",
           cleaned.get("SENTINEL") == "kept"
           and cleaned.get("GIT_AUTHOR_NAME") == "kept"
           and not any(key in cleaned for key in (
               "GIT_DIR", "GIT_WORK_TREE", "GIT_CONFIG", "GIT_CONFIG_COUNT",
               "GIT_CONFIG_KEY_0", "GIT_LITERAL_PATHSPECS")))

    with tempfile.TemporaryDirectory(prefix="repository-ownership-") as tmp:
        owner = os.path.join(tmp, "owner")
        nested = os.path.join(owner, "nested")
        decoy = os.path.join(tmp, "decoy")
        os.makedirs(owner); os.makedirs(decoy)
        subprocess.run(["git", "init", "--quiet", owner], check=True)
        subprocess.run(["git", "init", "--quiet", decoy], check=True)
        expect("the exact owner root resolves", git_toplevel_error(owner) == "")

        previous = {key: os.environ.get(key) for key in ("GIT_DIR", "GIT_WORK_TREE")}
        os.environ["GIT_DIR"] = os.path.join(decoy, ".git")
        os.environ["GIT_WORK_TREE"] = decoy
        try:
            ambient = git_toplevel_error(owner)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        expect("ambient repository selectors cannot substitute a decoy", ambient == "")

        class Done:
            def __init__(self, rc=0, stdout=b"", stderr=b""):
                self.returncode, self.stdout, self.stderr = rc, stdout, stderr

        markerless_owner = os.path.join(tmp, "markerless-owner")
        markerless_candidate = os.path.join(markerless_owner, "candidate")
        os.makedirs(markerless_candidate)
        markerless_called = False
        def markerless_runner(*_args, **_kwargs):
            nonlocal markerless_called
            markerless_called = True
            raise AssertionError("a markerless owner has no index to query")
        expect("a markerless package root is a known non-gitlink without a Git query",
               not _indexed_gitlink(
                   markerless_candidate, markerless_owner, markerless_runner)
               and not markerless_called)

        def wrong_root(_argv, **_kwargs):
            return Done(stdout=os.fsencode(decoy) + b"\n")

        expect("a successful query that reports another root is rejected",
               "resolved" in git_toplevel_error(owner, wrong_root))
        expect("a silent nonzero Git exit is named",
               "exited 7" in git_toplevel_error(
                   owner, lambda *_a, **_k: Done(7, b"", b"")))
        nested_probe_root = os.path.join(tmp, "probe-root")
        os.makedirs(nested_probe_root)
        with open(os.path.join(nested_probe_root, ".git"), "w", encoding="utf-8") as fh:
            fh.write("gitdir: nowhere\n")
        # The other failure channel: Git could not be launched at all. It is a distinct arm
        # from a nonzero exit, and is_repository_boundary raises on it rather than returning
        # a verdict, because an unlaunchable Git is not evidence that no boundary exists.
        def unlaunchable_git(*_args, **_kwargs):
            raise OSError(2, "planted unlaunchable git")
        expect("an unlaunchable Git is named rather than read as a clean answer",
               "planted unlaunchable git" in git_toplevel_error(owner, unlaunchable_git))
        unlaunchable_problem = ""
        try:
            is_repository_boundary(nested_probe_root, owner, unlaunchable_git)
        except RepositoryOwnershipError as exc:
            unlaunchable_problem = str(exc)
        expect("an unlaunchable Git fails closed at the ownership boundary",
               "planted unlaunchable git" in unlaunchable_problem)

        os.makedirs(nested)
        with open(os.path.join(nested, ".git"), "w", encoding="utf-8") as fh:
            fh.write("not a repository\n")
        expect("an invalid .git file is not an ownership boundary",
               not is_repository_boundary(nested, owner))
        os.remove(os.path.join(nested, ".git"))
        os.mkdir(os.path.join(nested, ".git"))
        expect("an invalid .git directory is not an ownership boundary",
               not is_repository_boundary(nested, owner))
        os.rmdir(os.path.join(nested, ".git"))
        subprocess.run(["git", "init", "--quiet", nested], check=True)
        expect("an ordinary nested repository is a boundary",
               is_repository_boundary(nested, owner))
        plausible_problem = ""
        try:
            is_repository_boundary(
                nested, owner,
                lambda *_a, **_k: Done(
                    128, b"", b"fatal: detected dubious ownership in repository\n"))
        except RepositoryOwnershipError as exc:
            plausible_problem = str(exc)
        expect("a normal Git failure on a plausible nested repository fails closed",
               "dubious ownership" in plausible_problem)
        nested_file = os.path.join(nested, "evidence.md")
        with open(nested_file, "w", encoding="utf-8") as fh:
            fh.write("evidence\n")
        expect("a candidate inside the nested repository names that boundary",
               same_file(boundary_between(owner, nested_file), nested))

        linked_marker = os.path.join(tmp, "marker-link")
        os.symlink(os.path.join(nested, ".git"), linked_marker)
        linked_candidate = os.path.join(tmp, "linked-candidate")
        os.mkdir(linked_candidate)
        os.symlink(linked_marker, os.path.join(linked_candidate, ".git"))
        expect("a symlinked .git marker is not an ownership boundary",
               not is_repository_boundary(linked_candidate, owner))

        forged = os.path.join(owner, "forged")
        os.mkdir(forged)
        with open(os.path.join(forged, ".git"), "w", encoding="utf-8") as fh:
            fh.write(f"gitdir: {os.path.join(owner, '.git')}\n")
        expect("a marker borrowing the owner gitdir is rejected",
               not is_repository_boundary(forged, owner))

        separate = os.path.join(tmp, "separate")
        separate_admin = os.path.join(tmp, "separate-admin")
        subprocess.run(
            ["git", "init", "--quiet", "--separate-git-dir", separate_admin, separate],
            check=True)
        subprocess.run(
            ["git", "--git-dir", separate_admin, "config", "core.worktree", separate],
            check=True)
        expect("a separately-bound gitdir is an ownership boundary",
               is_repository_boundary(separate, owner))
        # The comparison the accept depends on. Without it any administration directory
        # recording any single core.worktree becomes a boundary, and the accept above cannot
        # tell that apart because it accepts either way.
        foreign_bound = os.path.join(tmp, "foreign-bound")
        os.makedirs(foreign_bound)
        with open(os.path.join(foreign_bound, ".git"), "w", encoding="utf-8") as fh:
            fh.write(f"gitdir: {separate_admin}\n")
        expect("a gitdir whose config binds another worktree is not a boundary here",
               not _bound_separate_gitdir(
                   foreign_bound, os.path.join(foreign_bound, ".git"), subprocess.run))

        calls = 0
        def late_git_failure(argv, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return subprocess.run(argv, **kwargs)
            raise OSError(5, "planted late ownership EIO")
        late_problem = ""
        try:
            is_repository_boundary(separate, owner, late_git_failure)
        except RepositoryOwnershipError as exc:
            late_problem = str(exc)
        expect("a late ownership-probe I/O failure is named and fails closed",
               "planted late ownership EIO" in late_problem)

        recorded = []
        def recording_runner(argv, **kwargs):
            recorded.append(kwargs.get("env", {}))
            return subprocess.run(argv, **kwargs)
        expect("injected runners receive the sanitized environment",
               git_toplevel_error(owner, recording_runner) == ""
               and recorded and all("GIT_DIR" not in env for env in recorded))

        expect("a path owned by the outer repository has no nested boundary",
               boundary_between(owner, os.path.join(owner, "outer.md")) is None)
        expect("an unrelated path does not manufacture a boundary",
               boundary_between(owner, os.path.join(tmp, "elsewhere.md")) is None)

        # The escape guard, with a discriminating fixture. The case above is answered by
        # the walk running out of repositories, so it stayed green with the guard removed.
        # Here the escaping candidate's own directory IS a proven boundary, so returning
        # None can only come from refusing to leave the root.
        outside_repo = os.path.join(tmp, "outside-repo")
        os.makedirs(outside_repo)
        subprocess.run(["git", "init", "--quiet", outside_repo], check=True)
        outside_file = os.path.join(outside_repo, "evidence.md")
        with open(outside_file, "w", encoding="utf-8") as fh:
            fh.write("evidence\n")
        expect("a candidate outside the root never names a boundary outside it",
               is_repository_boundary(outside_repo, owner)
               and boundary_between(owner, outside_file) is None)

        # A probe failure is unknown only where the marker carries repository metadata. A
        # .git directory with no HEAD carries none, so the outer scan keeps the directory
        # instead of failing closed on it; the dubious-ownership case above proves the
        # other arm, and only the pair separates them.
        hollow = os.path.join(tmp, "hollow")
        os.makedirs(os.path.join(hollow, ".git"))
        def hollow_marker_stays_outer_owned():
            try:
                return not is_repository_boundary(
                    hollow, owner,
                    lambda *_a, **_k: Done(7, b"", b"planted hollow probe failure\n"))
            except RepositoryOwnershipError:
                return False
        expect("a .git directory with no HEAD stays outer-owned when the probe fails",
               hollow_marker_stays_outer_owned())

        # Registered-worktree metadata, forged. Each of these three fixtures satisfies every
        # part of the linked-worktree contract except one, so each names one operand.
        registered = os.path.join(tmp, "registered")
        subprocess.run(
            ["git", "-C", owner, "-c", "user.name=fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "--quiet",
             "--allow-empty", "-m", "base"], check=True)
        subprocess.run(
            ["git", "-C", owner, "worktree", "add", "--quiet", "--detach", registered],
            check=True)
        expect("a registered linked worktree is an ownership boundary",
               is_repository_boundary(registered, owner))
        registered_admin = _gitdir_from_marker(registered, os.path.join(registered, ".git"))
        backlink_path = os.path.join(registered_admin, "gitdir")
        original_backlink = open(backlink_path, encoding="utf-8").read()
        with open(backlink_path, "w", encoding="utf-8") as fh:
            fh.write(os.path.join(tmp, "some-other-worktree", ".git") + "\n")
        expect("a linked worktree whose backlink names another worktree is refused",
               not _registered_linked_worktree(
                   registered, os.path.join(registered, ".git")))
        with open(backlink_path, "w", encoding="utf-8") as fh:
            fh.write(original_backlink)
        expect("the restored backlink is accepted again",
               _registered_linked_worktree(registered, os.path.join(registered, ".git")))

        # Without the commondir requirement, an administration directory that is not a
        # registered worktree at all can be dressed to satisfy the parent comparison: point
        # its `worktrees` entry at its own parent and add a backlink. The separately-bound
        # arm refuses it on the sibling-key exclusion, so only this operand stops it.
        forged_link = os.path.join(tmp, "forged-link")
        forged_link_admin = os.path.join(tmp, "forged-link-admin")
        subprocess.run(
            ["git", "init", "--quiet", "--separate-git-dir", forged_link_admin,
             forged_link], check=True)
        subprocess.run(
            ["git", "--git-dir", forged_link_admin, "config", "core.worktree",
             forged_link], check=True)
        with open(os.path.join(forged_link_admin, "gitdir"), "w", encoding="utf-8") as fh:
            fh.write(os.path.join(forged_link, ".git") + "\n")
        os.symlink(os.path.dirname(forged_link_admin),
                   os.path.join(forged_link_admin, "worktrees"))
        expect("an administration directory with no commondir is not a linked worktree",
               not _registered_linked_worktree(
                   forged_link, os.path.join(forged_link, ".git")))
        expect("the sibling-key exclusion refuses the same forged administration directory",
               not _bound_separate_gitdir(
                   forged_link, os.path.join(forged_link, ".git"), subprocess.run))
        expect("the forged administration directory is not an ownership boundary",
               not is_repository_boundary(forged_link, owner))

        # A worktrees parent that is not the common directory's own `worktrees` entry.
        strayed = os.path.join(tmp, "strayed-admin")
        shutil.copytree(registered_admin, strayed, symlinks=True)
        with open(os.path.join(strayed, "commondir"), "w", encoding="utf-8") as fh:
            fh.write(os.path.join(owner, ".git") + "\n")
        strayed_worktree = os.path.join(tmp, "strayed")
        os.makedirs(strayed_worktree)
        # The backlink names THIS worktree, so the backlink comparison accepts it and the
        # parent comparison is the only operand left to refuse the administration
        # directory's location.
        with open(os.path.join(strayed, "gitdir"), "w", encoding="utf-8") as fh:
            fh.write(os.path.join(strayed_worktree, ".git") + "\n")
        with open(os.path.join(strayed_worktree, ".git"), "w", encoding="utf-8") as fh:
            fh.write(f"gitdir: {strayed}\n")
        expect("an administration directory outside the common worktrees entry is refused",
               not _registered_linked_worktree(
                   strayed_worktree, os.path.join(strayed_worktree, ".git")))

        # core.worktree must resolve to exactly one value, and the refusal is the
        # terminator count alone: with it removed the joined record reaches samefile and
        # raises instead of returning a verdict.
        subprocess.run(
            ["git", "--git-dir", separate_admin, "config", "--add", "core.worktree",
             owner], check=True)
        def doubly_recorded_is_refused():
            # Reported rather than raised: with the terminator count removed this call
            # raises, and an uncaught raise ends the suite instead of naming the operand.
            try:
                return not _bound_separate_gitdir(
                    separate, os.path.join(separate, ".git"), subprocess.run)
            except (OSError, ValueError):
                return False
        expect("a doubly-recorded core.worktree is not a separately-bound gitdir",
               doubly_recorded_is_refused())
        subprocess.run(
            ["git", "--git-dir", separate_admin, "config", "--unset-all",
             "core.worktree"], check=True)
        subprocess.run(
            ["git", "--git-dir", separate_admin, "config", "core.worktree", separate],
            check=True)
        expect("one recorded core.worktree is accepted again",
               _bound_separate_gitdir(
                   separate, os.path.join(separate, ".git"), subprocess.run))

        # A ValueError raised anywhere under the ownership probes is the modelled error,
        # not a raised one: every consumer catches RepositoryOwnershipError and nothing
        # else, so an unconverted one surfaces as an unhandled exception. Injected through
        # the same runner seam the OSError case above uses, because with every operand in
        # place no record reaches the filesystem call malformed -- the arm exists for the
        # state where one of those operands is gone.
        def raises_value_error(argv, **kwargs):
            # Only the config read: the toplevel probe runs before the guarded block, so
            # raising there would prove the wrong thing by escaping a different way.
            if "config" in argv:
                raise ValueError("planted malformed ownership record")
            return subprocess.run(argv, **kwargs)
        malformed_problem = ""
        try:
            is_repository_boundary(separate, owner, raises_value_error)
        except RepositoryOwnershipError as exc:
            malformed_problem = str(exc)
        except ValueError:
            # Reported, not propagated: an unconverted error would otherwise end the suite
            # rather than naming the arm that was supposed to convert it.
            malformed_problem = "escaped unconverted"
        expect("a malformed ownership record is named as the modelled error",
               "planted malformed ownership record" in malformed_problem)

        # An indexed gitlink is a 160000 entry. A tracked ordinary file at the same path is
        # not a repository boundary, and only the mode comparison separates them.
        gitlinked = os.path.join(owner, "gitlinked")
        subprocess.run(["git", "init", "--quiet", gitlinked], check=True)
        subprocess.run(
            ["git", "-C", gitlinked, "-c", "user.name=fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "--quiet",
             "--allow-empty", "-m", "nested"], check=True)
        subprocess.run(["git", "-C", owner, "add", "--", "gitlinked"], check=True)
        expect("an indexed gitlink is an ownership boundary",
               _indexed_gitlink(gitlinked, owner, subprocess.run))
        # ...and that it is the arm is_repository_boundary reaches for a submodule, whose
        # .git is a FILE. Dropping that arm left this module green because the other two
        # answered every fixture; only a marker no other arm accepts separates them.
        submodule = os.path.join(owner, "submodule")
        submodule_admin = os.path.join(tmp, "submodule-admin")
        subprocess.run(
            ["git", "init", "--quiet", "--separate-git-dir", submodule_admin, submodule],
            check=True)
        subprocess.run(
            ["git", "-C", submodule, "-c", "user.name=fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "--quiet",
             "--allow-empty", "-m", "sub"], check=True)
        subprocess.run(["git", "-C", owner, "add", "--", "submodule"], check=True)
        expect("a file-marked submodule is a boundary through the indexed-gitlink arm",
               not _registered_linked_worktree(
                   submodule, os.path.join(submodule, ".git"))
               and not _bound_separate_gitdir(
                   submodule, os.path.join(submodule, ".git"), subprocess.run)
               and is_repository_boundary(submodule, owner))

        def failed_index_query(argv, **kwargs):
            if "ls-files" in argv and "--stage" in argv:
                return Done(128, b"", b"planted unreadable owner index\n")
            return subprocess.run(argv, **kwargs)

        direct_problem = boundary_problem = ""
        try:
            _indexed_gitlink(submodule, owner, failed_index_query)
        except RepositoryOwnershipError as exc:
            direct_problem = str(exc)
        try:
            is_repository_boundary(submodule, owner, failed_index_query)
        except RepositoryOwnershipError as exc:
            boundary_problem = str(exc)
        expect("a failed indexed-gitlink query is typed at the helper and public boundary",
               all("git ls-files --stage exited 128" in problem
                   and "planted unreadable owner index" in problem
                   for problem in (direct_problem, boundary_problem)))

        def unlaunchable_index_query(argv, **kwargs):
            if "ls-files" in argv and "--stage" in argv:
                raise OSError(5, "planted unlaunchable index query")
            return subprocess.run(argv, **kwargs)

        direct_problem = boundary_problem = ""
        try:
            _indexed_gitlink(submodule, owner, unlaunchable_index_query)
        except RepositoryOwnershipError as exc:
            direct_problem = str(exc)
        try:
            is_repository_boundary(submodule, owner, unlaunchable_index_query)
        except RepositoryOwnershipError as exc:
            boundary_problem = str(exc)
        expect("an unlaunchable indexed-gitlink query has the same typed boundary",
               all("cannot run git ls-files --stage" in problem
                   and "planted unlaunchable index query" in problem
                   for problem in (direct_problem, boundary_problem)))

        # One unknown operand cannot erase a positive sibling. This separately-bound
        # worktree lives under the owner so the planted index failure is reached, while its
        # own core.worktree binding independently proves the boundary.
        separate_inside = os.path.join(owner, "separate-inside")
        separate_inside_admin = os.path.join(tmp, "separate-inside-admin")
        subprocess.run(
            ["git", "init", "--quiet", "--separate-git-dir", separate_inside_admin,
             separate_inside], check=True)
        subprocess.run(
            ["git", "--git-dir", separate_inside_admin, "config", "core.worktree",
             separate_inside], check=True)
        expect("a positive separate-gitdir proof survives an unknown index operand",
               is_repository_boundary(separate_inside, owner, failed_index_query))

        plain = os.path.join(owner, "plain")
        os.makedirs(plain)
        with open(os.path.join(plain, "note.md"), "w", encoding="utf-8") as fh:
            fh.write("note\n")
        subprocess.run(["git", "-C", owner, "add", "--", "plain/note.md"], check=True)
        expect("a tracked ordinary path is not an indexed gitlink",
               not _indexed_gitlink(plain, owner, subprocess.run))
        # The index is not the filesystem. A path recorded as an ordinary blob and later
        # replaced by a separately-bound worktree matches the recorded path exactly, so the
        # 160000 comparison is the only thing separating a stale entry from a gitlink.
        stale = os.path.join(owner, "stale-entry")
        with open(stale, "w", encoding="utf-8") as fh:
            fh.write("was a file\n")
        subprocess.run(["git", "-C", owner, "add", "--", "stale-entry"], check=True)
        os.remove(stale)
        stale_admin = os.path.join(tmp, "stale-admin")
        subprocess.run(
            ["git", "init", "--quiet", "--separate-git-dir", stale_admin, stale],
            check=True)
        expect("a stale ordinary index entry is not an indexed gitlink",
               not _indexed_gitlink(stale, owner, subprocess.run))

    print(f"SELFTEST-SUMMARY suite=repository-ownership checks={checks} failures={failures}")
    return 1 if failures else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    parser.error("nothing to do: pass --selftest")


if __name__ == "__main__":
    raise SystemExit(main())
