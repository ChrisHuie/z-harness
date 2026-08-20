#!/usr/bin/env python3
"""Verify an append-only review comment or frozen pull-request publication.

The repository gate can validate a draft's inputs but cannot see what GitHub received.
This tool reads complete REST objects back and binds both modes to the requested repository,
pull request and current head. Comment mode compares raw UTF-8 body bytes and additionally
binds the author, comment identity and unedited timestamps. Snapshot mode compares the live
pull-request body and title to a reviewed frozen digest; it does not rewrite either surface.

Local source files use one canonical form: strict UTF-8, no carriage returns, and exactly
one terminal line feed. Whether publication keeps that final line feed is a property of the
posting method, not of GitHub: on this repository's own pull request the body field retained
the source's terminal line feed verbatim while the title field dropped it, from one
publication event. Comment mode therefore accepts the published body with or without the
terminal line feed and records which form matched, or `mismatch` when neither did. Interior
bytes are never normalised.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


VERSION = "3.1"
RECEIPT = "REVIEW-PUBLICATION-SUMMARY"
HEAD_LINE = re.compile(rb"^Head: `([0-9a-f]{40})`$", re.MULTILINE)
SNAPSHOT_SCHEMA_VERSION = 1
SNAPSHOT_KIND = "pull-request-frozen-publication"
SNAPSHOT_NOTE = (
    "The body and title bytes were frozen when the append-only publication rule was adopted "
    "at this observed head. Later review narrative, corrections, and exact-head evidence are "
    "append-only pull-request comments."
)
SNAPSHOT_FIELDS = {
    "schema_version", "kind", "repo", "pr", "frozen_at_head",
    "body_bytes", "body_sha256", "title_bytes", "title_sha256", "note",
}


class PublicationError(ValueError):
    """A publication was reachable but violated the requested contract."""


class TransportError(ValueError):
    """The publication could not be read or decoded."""


def _json_object(raw: bytes, label: str) -> dict:
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise TransportError(f"{label} repeats JSON key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransportError(f"cannot decode {label} JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise TransportError(f"{label} response is not a JSON object")
    return value


def _api_object(repo: str, endpoint: str, label: str, runner=None) -> dict:
    runner = subprocess.run if runner is None else runner
    done = runner(
        ["gh", "api", f"repos/{repo}/{endpoint}"],
        capture_output=True, text=False, timeout=60)
    if done.returncode != 0:
        diagnostic = bytes(done.stderr or b"no diagnostic").decode("utf-8", "replace")
        raise TransportError(f"cannot read {label} in {repo}: {diagnostic.strip()[:200]}")
    return _json_object(bytes(done.stdout), label)


def _source_bytes(path: Path) -> bytes:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise TransportError(f"cannot read {path}: {exc}") from exc
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TransportError(f"{path} is not strict UTF-8: {exc}") from exc
    if b"\r" in raw:
        raise TransportError(f"{path} contains a carriage return")
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise TransportError(f"{path} must end in exactly one line feed")
    return raw


def _accepted_form(published: bytes, submitted: bytes) -> tuple[bytes, str]:
    """The source form to compare against and its closed transport classification.

    A canonical source ends in exactly one line feed. Posting with a body file preserves it;
    posting through a shell command substitution strips it before GitHub ever sees the bytes.
    Both are correct publications of the same source, so both are accepted -- and nothing
    else is: every interior byte still has to match exactly.
    """
    if published == submitted:
        return submitted, "retained"
    if published == submitted[:-1]:
        return submitted[:-1], "stripped"
    return submitted, "mismatch"


def _text_bytes(value, label: str) -> bytes:
    if not isinstance(value, str):
        raise TransportError(f"{label} is not a string")
    return value.encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _difference(published: bytes, expected: bytes) -> str:
    if published == expected:
        return ""
    if published.replace(b"\r\n", b"\n") == expected.replace(b"\r\n", b"\n"):
        return "published body differs only in line endings"
    published_lines = published.split(b"\n")
    expected_lines = expected.split(b"\n")
    for index, (left, right) in enumerate(zip(published_lines, expected_lines), 1):
        if left != right:
            return (f"published body differs at line {index}: "
                    f"published {left[:60]!r} != expected {right[:60]!r}")
    return (f"published body has {len(published_lines)} line(s); "
            f"expected {len(expected_lines)}")


def _required(value, label: str):
    if value is None or value == "":
        raise PublicationError(f"publication metadata is missing {label}")
    return value


def _object(value):
    return value if isinstance(value, dict) else {}


def _pr_metadata_error(data: dict, repo: str, pr: int, expected_head: str) -> str:
    if data.get("number") != pr:
        return f"pull request number is {data.get('number')!r}, expected {pr}"
    base_repo = _object(_object(data.get("base")).get("repo")).get("full_name")
    if base_repo != repo:
        return f"pull request base repository is {base_repo!r}, expected {repo!r}"
    head = _object(data.get("head")).get("sha")
    if head != expected_head:
        return f"pull request head is {head!r}, expected {expected_head!r}"
    expected_url = f"https://github.com/{repo}/pull/{pr}"
    if data.get("html_url") != expected_url:
        return f"pull request URL is {data.get('html_url')!r}, expected {expected_url!r}"
    return ""


def _comment_metadata_error(
        data: dict, repo: str, pr: int, comment_id: int, expected_author: str,
        expected_head: str, submitted: bytes) -> str:
    user = _object(data.get("user"))
    required = {
        "id": data.get("id"),
        "issue_url": data.get("issue_url"),
        "html_url": data.get("html_url"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "user.login": user.get("login"),
        "user.id": user.get("id"),
        "author_association": data.get("author_association"),
    }
    try:
        for label, value in required.items():
            _required(value, label)
    except PublicationError as exc:
        return str(exc)
    if data["id"] != comment_id:
        return f"comment id is {data['id']!r}, expected {comment_id}"
    issue_url = f"https://api.github.com/repos/{repo}/issues/{pr}"
    if data["issue_url"] != issue_url:
        return f"comment issue URL is {data['issue_url']!r}, expected {issue_url!r}"
    comment_url = f"https://github.com/{repo}/pull/{pr}#issuecomment-{comment_id}"
    if data["html_url"] != comment_url:
        return f"comment URL is {data['html_url']!r}, expected {comment_url!r}"
    if user["login"] != expected_author:
        return (f"comment author is {user['login']!r}, "
                f"expected {expected_author!r}")
    if data["created_at"] != data["updated_at"]:
        return (f"comment was edited: created_at={data['created_at']!r} "
                f"updated_at={data['updated_at']!r}")
    heads = HEAD_LINE.findall(submitted)
    if len(heads) != 1:
        return f"submitted handoff has {len(heads)} exact Head lines, expected 1"
    if heads[0].decode("ascii") != expected_head:
        return (f"submitted handoff Head is {heads[0].decode('ascii')!r}, "
                f"expected {expected_head!r}")
    return ""


def _snapshot_error(snapshot: dict, repo: str, pr: int, body: bytes,
                    title: bytes) -> str:
    if set(snapshot) != SNAPSHOT_FIELDS:
        return (
            "snapshot manifest fields differ from the closed schema: "
            f"missing={sorted(SNAPSHOT_FIELDS - set(snapshot))} "
            f"unexpected={sorted(set(snapshot) - SNAPSHOT_FIELDS)}"
        )
    expected_scalars = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "kind": SNAPSHOT_KIND,
        "repo": repo,
        "pr": pr,
        "note": SNAPSHOT_NOTE,
    }
    for field, expected in expected_scalars.items():
        if snapshot.get(field) != expected:
            return f"snapshot {field} is {snapshot.get(field)!r}, expected {expected!r}"
    if not re.fullmatch(r"[0-9a-f]{40}", snapshot.get("frozen_at_head") or ""):
        return "snapshot frozen_at_head is not a full lowercase commit SHA"
    for label, published in (("body", body), ("title", title)):
        expected_bytes = snapshot.get(f"{label}_bytes")
        expected_sha = snapshot.get(f"{label}_sha256")
        if not isinstance(expected_bytes, int) or expected_bytes < 0:
            return f"snapshot {label}_bytes is not a non-negative integer"
        if not isinstance(expected_sha, str) or not re.fullmatch(
                r"[0-9a-f]{64}", expected_sha):
            return f"snapshot {label}_sha256 is not a lowercase SHA-256 digest"
        if len(published) != expected_bytes:
            return (
                f"published {label} has {len(published)} bytes, "
                f"snapshot records {expected_bytes}"
            )
        actual_sha = _sha256(published)
        if actual_sha != expected_sha:
            return (
                f"published {label} digest is {actual_sha}, "
                f"snapshot records {expected_sha}"
            )
    return ""


def _frozen_head_error(repo: str, snapshot: dict, runner=None) -> str:
    """Bind frozen_at_head to a commit that actually exists in this repository.

    The shape check accepts any forty hexadecimal characters, so a fabricated head passes
    while naming nothing. Resolve it through the API rather than the local object database:
    a CI checkout is shallow by default and would report a real commit as missing.
    """
    sha = snapshot.get("frozen_at_head")
    try:
        commit = _api_object(repo, f"commits/{sha}", "frozen head commit", runner)
    except TransportError as exc:
        return f"frozen_at_head {sha} is not a commit in {repo}: {exc}"
    if commit.get("sha") != sha:
        return f"frozen_at_head resolved to {commit.get('sha')!r}, expected {sha!r}"
    return ""


def _receipt(kind: str, repo: str, pr: int, expected_head: str, published: bytes,
             expected: bytes, verified: bool, problem: str, **metadata) -> None:
    payload = {
        "kind": kind,
        "repo": repo,
        "pr": pr,
        "expected_head": expected_head,
        "published_bytes": len(published),
        "published_sha256": _sha256(published),
        "expected_bytes": len(expected),
        "expected_sha256": _sha256(expected),
        "verified": verified,
        "problem": problem or "none",
        **metadata,
    }
    print(f"{RECEIPT} kind={kind} verified={int(verified)} problem={problem or 'none'}")
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def verify_comment(repo: str, pr: int, comment_id: int, expected_head: str,
                   expected_author: str, body_path: Path, runner=None) -> int:
    try:
        submitted = _source_bytes(body_path)
        comment = _api_object(repo, f"issues/comments/{comment_id}", "comment", runner)
        published = _text_bytes(comment.get("body"), "comment")
        expected, terminal_line_feed = _accepted_form(published, submitted)
        problem = _comment_metadata_error(
            comment, repo, pr, comment_id, expected_author, expected_head, submitted)
        if not problem:
            problem = _difference(published, expected)
        pull = _api_object(repo, f"pulls/{pr}", "pull request", runner)
        if not problem:
            problem = _pr_metadata_error(pull, repo, pr, expected_head)
    except (OSError, subprocess.SubprocessError, TransportError) as exc:
        print(f"{RECEIPT} kind=comment verified=0 problem={exc}")
        return 2
    _receipt(
        "comment", repo, pr, expected_head, published, expected, not problem, problem,
        comment_id=comment_id, comment_url=comment.get("html_url"),
        author=_object(comment.get("user")).get("login"),
        author_id=_object(comment.get("user")).get("id"),
        author_association=comment.get("author_association"),
        created_at=comment.get("created_at"), updated_at=comment.get("updated_at"),
        edited=comment.get("created_at") != comment.get("updated_at"),
        submitted_bytes=len(submitted), submitted_sha256=_sha256(submitted),
        terminal_line_feed=terminal_line_feed,
    )
    return 1 if problem else 0


def verify_pr_snapshot(repo: str, pr: int, expected_head: str,
                       manifest_path: Path, runner=None) -> int:
    try:
        manifest_raw = _source_bytes(manifest_path)
        manifest = _json_object(manifest_raw, "snapshot manifest")
        pull = _api_object(repo, f"pulls/{pr}", "pull request", runner)
        body = _text_bytes(pull.get("body"), "pull request")
        title = _text_bytes(pull.get("title"), "pull request title")
        problem = _pr_metadata_error(pull, repo, pr, expected_head)
        if not problem:
            problem = _snapshot_error(manifest, repo, pr, body, title)
        if not problem:
            problem = _frozen_head_error(repo, manifest, runner)
    except (OSError, subprocess.SubprocessError, TransportError) as exc:
        print(f"{RECEIPT} kind=pr-snapshot verified=0 problem={exc}")
        return 2
    payload = {
        "kind": "pr-snapshot",
        "repo": repo,
        "pr": pr,
        "expected_head": expected_head,
        "pr_url": pull.get("html_url"),
        "frozen_at_head": manifest.get("frozen_at_head"),
        "manifest_bytes": len(manifest_raw),
        "manifest_sha256": _sha256(manifest_raw),
        "body_bytes": len(body),
        "body_sha256": _sha256(body),
        "snapshot_body_bytes": manifest.get("body_bytes"),
        "snapshot_body_sha256": manifest.get("body_sha256"),
        "title_bytes": len(title),
        "title_sha256": _sha256(title),
        "snapshot_title_bytes": manifest.get("title_bytes"),
        "snapshot_title_sha256": manifest.get("title_sha256"),
        "verified": not problem,
        "problem": problem or "none",
    }
    print(
        f"{RECEIPT} kind=pr-snapshot verified={int(not problem)} "
        f"problem={problem or 'none'}"
    )
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 1 if problem else 0


def selftest() -> int:
    checks = failures = 0

    def expect(label: str, ok: bool) -> None:
        nonlocal checks, failures
        checks += 1
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} {label}")

    def captured_receipt(call):
        """Return the code and JSON receipt payload printed by one verifier call."""
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = call()
        captured = stream.getvalue()
        sys.stdout.write(captured)
        for line in captured.splitlines():
            if line.startswith("{"):
                return code, json.loads(line)
        return code, {}

    def receipt_field(call, field):
        """The named field from the receipt payload the call printed.

        A field the receipt reports is a published claim. Recording which terminal form
        matched while nothing asserts the label lets it be wrong in either direction.
        """
        _code, payload = captured_receipt(call)
        return payload.get(field)

    def denies(call, named: str, code: int = 1) -> bool:
        """True when `call` fails with the NAMED problem, not merely with some problem.

        Every publication mismatch exits 1, so an exit-code assertion cannot say which
        check fired. A case that varies the submitted bytes is satisfied by the body
        comparison whatever rule it targets, which is how four head-line cases passed
        against a build with the head-line rule deleted. The receipt line is the bytes a
        consumer reads, so the assertion is made against that rather than an internal
        return value.
        """
        if not named:
            raise AssertionError(
                "denies() needs the problem text to discriminate: an empty needle matches "
                "every problem and silently restores the exit-code-only assertion that let "
                "four head-line cases pass against a build with the head-line rule deleted")
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            observed = call()
        captured = stream.getvalue()
        sys.stdout.write(captured)
        problem = ""
        for line in captured.splitlines():
            if line.startswith(RECEIPT):
                _, _, problem = line.partition(" problem=")
        return observed == code and named in problem

    repo, pr = "o/r", 8
    head = "a" * 40
    comment_id, author = 123, "owner"
    body_bytes = f"Head: `{head}`\n\nRan: exact check.\n".encode()
    comment = {
        "id": comment_id, "body": body_bytes[:-1].decode(),
        "issue_url": f"https://api.github.com/repos/{repo}/issues/{pr}",
        "html_url": f"https://github.com/{repo}/pull/{pr}#issuecomment-{comment_id}",
        "user": {"login": author, "id": 42}, "author_association": "OWNER",
        "created_at": "2026-08-19T00:00:00Z", "updated_at": "2026-08-19T00:00:00Z",
    }
    title = "Probe title"
    pull = {
        "number": pr, "body": body_bytes.decode(), "title": title,
        "html_url": f"https://github.com/{repo}/pull/{pr}",
        "base": {"repo": {"full_name": repo}}, "head": {"sha": head},
    }
    snapshot = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "kind": SNAPSHOT_KIND,
        "repo": repo,
        "pr": pr,
        "frozen_at_head": head,
        "body_bytes": len(body_bytes),
        "body_sha256": _sha256(body_bytes),
        "title_bytes": len(title.encode()),
        "title_sha256": _sha256(title.encode()),
        "note": SNAPSHOT_NOTE,
    }
    comment_receipt_fields = frozenset({
        "author", "author_association", "author_id", "comment_id", "comment_url",
        "created_at", "edited", "expected_bytes", "expected_head",
        "expected_sha256", "kind", "pr", "problem", "published_bytes",
        "published_sha256", "repo", "submitted_bytes", "submitted_sha256",
        "terminal_line_feed", "updated_at", "verified",
    })

    def comment_receipt_is_closed(payload):
        return set(payload) == comment_receipt_fields

    def expected_comment_receipt(
            published, expected, verified, problem, terminal, comment_data=None):
        comment_data = comment if comment_data is None else comment_data
        comment_user = _object(comment_data.get("user"))
        return {
            "kind": "comment", "repo": repo, "pr": pr, "expected_head": head,
            "published_bytes": len(published),
            "published_sha256": _sha256(published),
            "expected_bytes": len(expected), "expected_sha256": _sha256(expected),
            "verified": verified, "problem": problem or "none",
            "comment_id": comment_id, "comment_url": comment_data.get("html_url"),
            "author": comment_user.get("login"), "author_id": comment_user.get("id"),
            "author_association": comment_data.get("author_association"),
            "created_at": comment_data.get("created_at"),
            "updated_at": comment_data.get("updated_at"),
            "edited": comment_data.get("created_at") != comment_data.get("updated_at"),
            "submitted_bytes": len(body_bytes),
            "submitted_sha256": _sha256(body_bytes),
            "terminal_line_feed": terminal,
        }

    snapshot_receipt_fields = frozenset({
        "body_bytes", "body_sha256", "expected_head", "frozen_at_head", "kind",
        "manifest_bytes", "manifest_sha256", "pr", "pr_url", "problem", "repo",
        "snapshot_body_bytes", "snapshot_body_sha256", "snapshot_title_bytes",
        "snapshot_title_sha256", "title_bytes", "title_sha256", "verified",
    })

    def expected_snapshot_receipt(pull_data, manifest_raw, verified, problem):
        published_body = pull_data["body"].encode()
        published_title = pull_data["title"].encode()
        return {
            "kind": "pr-snapshot", "repo": repo, "pr": pr,
            "expected_head": head, "pr_url": pull_data["html_url"],
            "frozen_at_head": snapshot["frozen_at_head"],
            "manifest_bytes": len(manifest_raw),
            "manifest_sha256": _sha256(manifest_raw),
            "body_bytes": len(published_body), "body_sha256": _sha256(published_body),
            "snapshot_body_bytes": snapshot["body_bytes"],
            "snapshot_body_sha256": snapshot["body_sha256"],
            "title_bytes": len(published_title),
            "title_sha256": _sha256(published_title),
            "snapshot_title_bytes": snapshot["title_bytes"],
            "snapshot_title_sha256": snapshot["title_sha256"],
            "verified": verified, "problem": problem or "none",
        }

    class Done:
        def __init__(self, returncode, stdout=b"", stderr=b""):
            self.returncode, self.stdout, self.stderr = returncode, stdout, stderr

    transport_calls = []

    def runner_for(comment_data=comment, pull_data=pull, commit_data=None,
                   commit_rc=0):
        def run(argv, **kwargs):
            transport_calls.append((tuple(argv), dict(kwargs)))
            endpoint = argv[-1]
            if "issues/comments" in endpoint:
                payload = comment_data
            elif "/commits/" in endpoint:
                if commit_rc:
                    return Done(commit_rc, b"", b"gh: Not Found (HTTP 404)")
                payload = (commit_data if commit_data is not None
                           else {"sha": endpoint.rsplit("/", 1)[-1]})
            else:
                payload = pull_data
            return Done(0, json.dumps(payload).encode())
        return run

    # The helper below replaced an exit-code-only assertion at 23 call sites. An empty needle
    # would restore that defect at every one of them without changing a verdict line.
    empty_needle_refused = False
    try:
        denies(lambda: 1, "")
    except AssertionError:
        empty_needle_refused = True
    expect("an empty problem needle is refused rather than matching everything",
           empty_needle_refused)
    expect("identical bytes have no difference", _difference(b"a\n b", b"a\n b") == "")
    expect("line-ending drift is named", "line endings" in _difference(b"a\r\n", b"a\n"))
    expect("trailing spaces remain significant", _difference(b"a ", b"a") != "")
    expect("interior blank lines remain significant", _difference(b"a\n\nb", b"a\nb") != "")

    with tempfile.TemporaryDirectory(prefix="z-harness-publication-") as raw:
        body = Path(raw) / "body.md"
        manifest = Path(raw) / "frozen-publication.json"
        body.write_bytes(body_bytes)
        manifest.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        expect("matching comment publication verifies", verify_comment(
            repo, pr, comment_id, head, author, body, runner_for()) == 0)
        manifest_raw = manifest.read_bytes()
        matching_snapshot_code, matching_snapshot = captured_receipt(
            lambda: verify_pr_snapshot(repo, pr, head, manifest, runner_for()))
        expect(
            "matching frozen pull-request publication emits the exact closed receipt",
            matching_snapshot_code == 0
            and set(matching_snapshot) == snapshot_receipt_fields
            and matching_snapshot == expected_snapshot_receipt(
                pull, manifest_raw, True, ""),
        )

        # Both publication forms are correct postings of one canonical source. The default
        # comment fixture is the stripped form; this is the retained one.
        retained = dict(comment, body=body_bytes.decode())
        expect("a published body that retains the terminal line feed verifies",
               verify_comment(repo, pr, comment_id, head, author, body,
                              runner_for(retained)) == 0)
        # Accepting either terminal form must not relax the interior comparison. Without
        # this case, a retained-form branch that echoed the published bytes verified clean.
        retained_but_changed = dict(
            comment, body="X" + body_bytes.decode()[1:])
        expect("the receipt names the retained form when the line feed survived",
               receipt_field(lambda: verify_comment(
                   repo, pr, comment_id, head, author, body,
                   runner_for(retained)), "terminal_line_feed") == "retained")
        expect("the receipt names the stripped form when the line feed did not",
               receipt_field(lambda: verify_comment(
                   repo, pr, comment_id, head, author, body,
                   runner_for()), "terminal_line_feed") == "stripped")
        retained_success_code, retained_success = captured_receipt(
            lambda: verify_comment(repo, pr, comment_id, head, author, body,
                                   runner_for(retained)))
        expect(
            "a retained success receipt has the closed schema and canonical source fields",
            retained_success_code == 0
            and comment_receipt_is_closed(retained_success)
            and retained_success == expected_comment_receipt(
                body_bytes, body_bytes, True, "", "retained"),
        )
        stripped_success_code, stripped_success = captured_receipt(
            lambda: verify_comment(repo, pr, comment_id, head, author, body, runner_for()))
        expect(
            "a stripped success receipt distinguishes transport bytes from canonical source",
            stripped_success_code == 0
            and comment_receipt_is_closed(stripped_success)
            and stripped_success == expected_comment_receipt(
                body_bytes[:-1], body_bytes[:-1], True, "", "stripped"),
        )
        expect("a retained-line-feed body whose interior changed still fails", denies(
            lambda: verify_comment(repo, pr, comment_id, head, author, body,
                                   runner_for(retained_but_changed)),
            "published body differs"))
        retained_mismatch_code, retained_mismatch = captured_receipt(
            lambda: verify_comment(repo, pr, comment_id, head, author, body,
                                   runner_for(retained_but_changed)))
        expect(
            "a changed retained-form receipt claims mismatch and canonical source bytes",
            retained_mismatch_code == 1
            and comment_receipt_is_closed(retained_mismatch)
            and retained_mismatch == expected_comment_receipt(
                retained_but_changed["body"].encode(), body_bytes, False,
                _difference(retained_but_changed["body"].encode(), body_bytes),
                "mismatch"),
        )
        stripped_but_changed = dict(
            comment, body=("X" + body_bytes.decode()[1:])[:-1])
        stripped_mismatch_code, stripped_mismatch = captured_receipt(
            lambda: verify_comment(repo, pr, comment_id, head, author, body,
                                   runner_for(stripped_but_changed)))
        expect(
            "a changed stripped-form receipt claims mismatch, never a transport match",
            stripped_mismatch_code == 1
            and comment_receipt_is_closed(stripped_mismatch)
            and stripped_mismatch == expected_comment_receipt(
                stripped_but_changed["body"].encode(), body_bytes, False,
                _difference(stripped_but_changed["body"].encode(), body_bytes),
                "mismatch"),
        )
        expect("a frozen_at_head that names no commit fails", denies(
            lambda: verify_pr_snapshot(
                repo, pr, head, manifest, runner_for(commit_rc=1)),
            "is not a commit in"))
        expect("a frozen_at_head that resolves to another commit fails", denies(
            lambda: verify_pr_snapshot(
                repo, pr, head, manifest, runner_for(commit_data={"sha": "c" * 40})),
            "frozen_at_head resolved to"))

        changed = dict(comment, body="changed")
        expect("changed comment bytes fail", denies(lambda: verify_comment(
            repo, pr, comment_id, head, author, body, runner_for(changed)), 'published body differs', 1))
        crlf_published = dict(comment, body=comment["body"].replace("\n", "\r\n"))
        crlf_code, crlf_receipt = captured_receipt(lambda: verify_comment(
            repo, pr, comment_id, head, author, body, runner_for(crlf_published)))
        expect(
            "published CRLF bytes fail without claiming an accepted terminal form",
            crlf_code == 1 and crlf_receipt.get("verified") is False
            and comment_receipt_is_closed(crlf_receipt)
            and crlf_receipt == expected_comment_receipt(
                crlf_published["body"].encode(), body_bytes, False,
                _difference(crlf_published["body"].encode(), body_bytes), "mismatch"),
        )
        prefixed_pull = dict(pull, body="prefix\n" + pull["body"])
        prefixed_code, prefixed_receipt = captured_receipt(
            lambda: verify_pr_snapshot(
                repo, pr, head, manifest, runner_for(pull_data=prefixed_pull)))
        prefixed_problem = _snapshot_error(
            snapshot, repo, pr, prefixed_pull["body"].encode(), title.encode())
        expect(
            "a changed frozen pull-request body emits the exact closed failure receipt",
            prefixed_code == 1
            and set(prefixed_receipt) == snapshot_receipt_fields
            and prefixed_receipt == expected_snapshot_receipt(
                prefixed_pull, manifest_raw, False, prefixed_problem),
        )
        same_length_body = dict(
            pull, body=("X" if not pull["body"].startswith("X") else "Y") + pull["body"][1:])
        expect("a same-length frozen body digest change fails", denies(lambda: verify_pr_snapshot(
            repo, pr, head, manifest, runner_for(pull_data=same_length_body)), 'published body digest is', 1))
        crlf_pull = dict(pull, body=pull["body"].replace("\n", "\r\n"))
        expect("pull-request CRLF bytes fail", denies(lambda: verify_pr_snapshot(
            repo, pr, head, manifest, runner_for(pull_data=crlf_pull)), 'published body has', 1))
        changed_title = dict(pull, title=title[::-1])
        changed_title_code, changed_title_receipt = captured_receipt(
            lambda: verify_pr_snapshot(
                repo, pr, head, manifest, runner_for(pull_data=changed_title)))
        changed_title_problem = _snapshot_error(
            snapshot, repo, pr, body_bytes, changed_title["title"].encode())
        expect(
            "a same-length title failure emits the exact closed snapshot receipt",
            changed_title_code == 1
            and set(changed_title_receipt) == snapshot_receipt_fields
            and changed_title_receipt == expected_snapshot_receipt(
                changed_title, manifest_raw, False, changed_title_problem),
        )

        for label, named, changed_comment in (
            ("wrong comment repository metadata fails", "comment issue URL is", dict(comment, issue_url="https://api.github.com/repos/x/y/issues/8")),
            ("wrong comment pull request fails", "comment issue URL is", dict(comment, issue_url=f"https://api.github.com/repos/{repo}/issues/9")),
            ("wrong comment identity fails", "comment id is", dict(comment, id=999)),
            ("wrong canonical comment URL fails", "comment URL is", dict(comment, html_url=f"https://github.com/{repo}/pull/9#issuecomment-123")),
            ("wrong comment author fails", "comment author is", dict(comment, user={"login": "other", "id": 42})),
            ("edited comment metadata fails", "comment was edited", dict(comment, updated_at="2026-08-19T00:01:00Z")),
        ):
            expect(label, denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body, runner_for(changed_comment)),
                named))
        wrong_author = dict(comment, user={"login": "other", "id": 42})
        wrong_author_code, wrong_author_receipt = captured_receipt(
            lambda: verify_comment(
                repo, pr, comment_id, head, author, body, runner_for(wrong_author)))
        wrong_author_problem = _comment_metadata_error(
            wrong_author, repo, pr, comment_id, author, head, body_bytes)
        expect(
            "a comment metadata failure emits the exact closed receipt",
            wrong_author_code == 1
            and set(wrong_author_receipt) == comment_receipt_fields
            and wrong_author_receipt == expected_comment_receipt(
                body_bytes[:-1], body_bytes[:-1], False, wrong_author_problem,
                "stripped", wrong_author),
        )
        missing = dict(comment); missing.pop("author_association")
        expect("missing comment metadata fails", denies(lambda: verify_comment(
            repo, pr, comment_id, head, author, body, runner_for(missing)), 'missing author_association', 1))
        missing_user = dict(comment, user=None)
        expect("a malformed comment user object fails closed", denies(lambda: verify_comment(
            repo, pr, comment_id, head, author, body, runner_for(missing_user)), 'missing user.login', 1))

        wrong_head_pull = dict(pull, head={"sha": "b" * 40})
        expect("wrong current pull-request head fails", denies(lambda: verify_comment(
            repo, pr, comment_id, head, author, body, runner_for(pull_data=wrong_head_pull)), 'pull request head is', 1))
        wrong_head_code, wrong_head_receipt = captured_receipt(
            lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(pull_data=wrong_head_pull)))
        wrong_head_problem = _pr_metadata_error(wrong_head_pull, repo, pr, head)
        expect(
            "a pull-request head failure emits the exact closed comment receipt",
            wrong_head_code == 1
            and set(wrong_head_receipt) == comment_receipt_fields
            and wrong_head_receipt == expected_comment_receipt(
                body_bytes[:-1], body_bytes[:-1], False, wrong_head_problem,
                "stripped"),
        )
        wrong_number_pull = dict(pull, number=9)
        wrong_number_code, wrong_number_receipt = captured_receipt(
            lambda: verify_pr_snapshot(
                repo, pr, head, manifest, runner_for(pull_data=wrong_number_pull)))
        wrong_number_problem = _pr_metadata_error(wrong_number_pull, repo, pr, head)
        expect(
            "a pull-request metadata failure emits the exact closed snapshot receipt",
            wrong_number_code == 1
            and set(wrong_number_receipt) == snapshot_receipt_fields
            and wrong_number_receipt == expected_snapshot_receipt(
                wrong_number_pull, manifest_raw, False, wrong_number_problem),
        )
        wrong_base_pull = dict(pull, base={"repo": {"full_name": "x/y"}})
        expect("wrong pull-request repository fails", denies(lambda: verify_pr_snapshot(
            repo, pr, head, manifest, runner_for(pull_data=wrong_base_pull)), 'pull request base repository is', 1))
        wrong_url_pull = dict(pull, html_url=f"https://github.com/{repo}/pull/9")
        expect("wrong canonical pull-request URL fails", denies(
            lambda: verify_pr_snapshot(
                repo, pr, head, manifest, runner_for(pull_data=wrong_url_pull)),
            "pull request URL is"))

        # One case per manifest guard. Each guard rejects a DIFFERENT malformed manifest,
        # so a shared fixture would let one guard stand in for the rest.
        for label, named, bad_snapshot in (
            ("a malformed frozen-publication digest fails",
             "body_sha256 is not a lowercase SHA-256 digest",
             dict(snapshot, body_sha256="not-a-digest")),
            ("an unclosed frozen-publication field set fails",
             "fields differ from the closed schema",
             dict(snapshot, extra_field="present")),
            ("a changed frozen-publication scalar fails",
             "snapshot kind is",
             dict(snapshot, kind="something-else")),
            ("a malformed frozen_at_head fails",
             "frozen_at_head is not a full lowercase commit SHA",
             dict(snapshot, frozen_at_head="Z" * 40)),
            ("a negative frozen body_bytes fails",
             "body_bytes is not a non-negative integer",
             dict(snapshot, body_bytes=-1)),
        ):
            manifest.write_text(
                json.dumps(bad_snapshot, indent=2) + "\n", encoding="utf-8")
            expect(label, denies(
                lambda: verify_pr_snapshot(repo, pr, head, manifest, runner_for()),
                named))
        manifest.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        duplicate_manifest = manifest.read_text(encoding="utf-8").replace(
            '  "schema_version": 1,',
            '  "schema_version": 1,\n  "schema_version": 1,',
            1,
        )
        manifest.write_text(duplicate_manifest, encoding="utf-8")
        expect("duplicate frozen-publication fields fail closed", denies(
            lambda: verify_pr_snapshot(repo, pr, head, manifest, runner_for()),
            "repeats JSON key", 2))
        manifest.write_bytes(
            (json.dumps(snapshot, indent=2) + "\n").encode().replace(b"\n", b"\r\n"))
        expect("CRLF frozen-publication source bytes fail closed", denies(
            lambda: verify_pr_snapshot(repo, pr, head, manifest, runner_for()),
            "contains a carriage return", 2))
        manifest.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")

        for label, named, content in (
            ("missing Head line fails", "has 0 exact Head lines", b"Ran: exact check.\n"),
            ("duplicate Head lines fail", "has 2 exact Head lines", f"Head: `{head}`\nHead: `{head}`\n".encode()),
            ("abbreviated Head line fails", "has 0 exact Head lines", f"Head: `{head[:12]}`\n".encode()),
            ("mismatched Head line fails", "handoff Head is", f"Head: `{'b' * 40}`\n".encode()),
        ):
            body.write_bytes(content)
            expect(label, denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body, runner_for()), named))

        for label, named, content in (
            ("a CRLF source fails before publication comparison", "contains a carriage return", body_bytes.replace(b"\n", b"\r\n")),
            ("a source without terminal LF fails", "must end in exactly one line feed", body_bytes[:-1]),
            ("a source with several terminal LFs fails", "must end in exactly one line feed", body_bytes + b"\n"),
            ("invalid UTF-8 source fails", "is not strict UTF-8", b"Head: `" + head.encode() + b"`\n\xff"),
        ):
            body.write_bytes(content)
            expect(label, denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body, runner_for()), named, 2))

        body.write_bytes(body_bytes)
        def broken_runner(argv, **kwargs):
            return Done(1, stderr=b"gh: Not Found (HTTP 404)")
        def array_runner(argv, **kwargs):
            return Done(0, json.dumps([1, 2]).encode())
        expect("a JSON array where an object is required fails closed", denies(
            lambda: verify_comment(repo, pr, comment_id, head, author, body, array_runner),
            "is not a JSON object", 2))
        expect("a comment carrying no body string fails closed", denies(
            lambda: verify_comment(repo, pr, comment_id, head, author, body,
                                   runner_for(dict(comment, body=None))),
            "comment is not a string", 2))
        expect("transport failure exits 2", denies(
            lambda: verify_comment(repo, pr, comment_id, head, author, body, broken_runner),
            "cannot read comment", 2))
        def invalid_json_runner(argv, **kwargs):
            return Done(0, b"not-json")
        expect("invalid API JSON exits 2", denies(
            lambda: verify_comment(repo, pr, comment_id, head, author, body, invalid_json_runner), "cannot decode comment JSON", 2))

    expect(
        "production API transport is raw JSON without --jq or text mode",
        bool(transport_calls)
        and all("--jq" not in argv and kwargs.get("text") is False
                for argv, kwargs in transport_calls),
    )

    print(f"SELFTEST-SUMMARY suite=verify-review-publication checks={checks} failures={failures}")
    return 1 if failures else 0


def _head(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value or ""):
        raise argparse.ArgumentTypeError("expected a full lowercase 40-hex commit SHA")
    return value


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    subparsers = parser.add_subparsers(dest="mode")
    comment = subparsers.add_parser("comment")
    comment.add_argument("--repo", required=True)
    comment.add_argument("--pr", required=True, type=int)
    comment.add_argument("--comment-id", required=True, type=int)
    comment.add_argument("--expected-head", required=True, type=_head)
    comment.add_argument("--expected-author", required=True)
    comment.add_argument("--body-file", required=True, type=Path)
    pr_snapshot = subparsers.add_parser("pr-snapshot")
    pr_snapshot.add_argument("--repo", required=True)
    pr_snapshot.add_argument("--pr", required=True, type=int)
    pr_snapshot.add_argument("--expected-head", required=True, type=_head)
    pr_snapshot.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.selftest and args.mode is None:
        parser.error("choose comment or pr-snapshot")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.selftest:
        return selftest()
    if args.mode == "comment":
        return verify_comment(args.repo, args.pr, args.comment_id, args.expected_head,
                              args.expected_author, args.body_file)
    return verify_pr_snapshot(
        args.repo, args.pr, args.expected_head, args.manifest)


if __name__ == "__main__":
    raise SystemExit(main())
