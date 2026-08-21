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
    """Return whether two path spellings identify the same filesystem object."""
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
    if owner_root is None:
        return False
    relative = os.path.relpath(path, owner_root).replace(os.sep, "/")
    if relative == ".." or relative.startswith("../"):
        return False
    staged = run_git(
        runner,
        ["git", "-C", owner_root, "ls-files", "--stage", "-z", "--", relative],
        capture_output=True, text=False)
    if staged.returncode != 0:
        return False
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
    if configured.returncode != 0 or not raw.endswith(b"\0") or raw.count(b"\0") != 1:
        return False
    worktree = os.fsdecode(raw[:-1])
    if not os.path.isabs(worktree):
        worktree = os.path.join(admin, worktree)
    return same_file(worktree, path)


def is_repository_boundary(path, owner_root=None, runner=None):
    """Return true only for a proven independent Git worktree at ``path``."""
    runner = subprocess.run if runner is None else runner
    marker = os.path.join(path, ".git")
    if not os.path.lexists(marker) or os.path.islink(marker):
        return False
    toplevel_problem = git_toplevel_error(path, runner)
    if toplevel_problem.startswith("cannot run git rev-parse"):
        raise RepositoryOwnershipError(toplevel_problem)
    if toplevel_problem:
        return False
    if os.path.isdir(marker):
        return True
    if not os.path.isfile(marker):
        return False
    try:
        return (_indexed_gitlink(path, owner_root, runner)
                or _registered_linked_worktree(path, marker)
                or _bound_separate_gitdir(path, marker, runner))
    except OSError as exc:
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

        def wrong_root(_argv, **_kwargs):
            return Done(stdout=os.fsencode(decoy) + b"\n")

        expect("a successful query that reports another root is rejected",
               "resolved" in git_toplevel_error(owner, wrong_root))
        expect("a silent nonzero Git exit is named",
               "exited 7" in git_toplevel_error(
                   owner, lambda *_a, **_k: Done(7, b"", b"")))

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
