#!/usr/bin/env python3
"""Verify a published review comment or pull-request body against its source bytes.

The repository gate can validate a draft's inputs but cannot see what GitHub received.
This tool reads complete REST objects back, binds both modes to the requested repository,
pull request and head, and compares raw UTF-8 body bytes. Comment mode additionally binds
the author, comment identity and unedited timestamps.

Local source files use one canonical form: strict UTF-8, no carriage returns, and exactly
one terminal line feed. GitHub removes that final line feed from issue comments but retains
it in pull-request bodies; those are the only publication transformations accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


VERSION = "2.0"
RECEIPT = "REVIEW-PUBLICATION-SUMMARY"
HEAD_LINE = re.compile(rb"^Head: `([0-9a-f]{40})`$", re.MULTILINE)


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


def _body_bytes(value, label: str) -> bytes:
    if not isinstance(value, str):
        raise TransportError(f"{label} body is not a string")
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
        published = _body_bytes(comment.get("body"), "comment")
        expected = submitted[:-1]
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
    )
    return 1 if problem else 0


def verify_pr_body(repo: str, pr: int, expected_head: str, body_path: Path,
                   runner=None) -> int:
    try:
        expected = _source_bytes(body_path)
        pull = _api_object(repo, f"pulls/{pr}", "pull request", runner)
        published = _body_bytes(pull.get("body"), "pull request")
        problem = _pr_metadata_error(pull, repo, pr, expected_head)
        if not problem:
            problem = _difference(published, expected)
    except (OSError, subprocess.SubprocessError, TransportError) as exc:
        print(f"{RECEIPT} kind=pr-body verified=0 problem={exc}")
        return 2
    _receipt("pr-body", repo, pr, expected_head, published, expected, not problem, problem,
             pr_url=pull.get("html_url"))
    return 1 if problem else 0


def selftest() -> int:
    checks = failures = 0

    def expect(label: str, ok: bool) -> None:
        nonlocal checks, failures
        checks += 1
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} {label}")

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
    pull = {
        "number": pr, "body": body_bytes.decode(),
        "html_url": f"https://github.com/{repo}/pull/{pr}",
        "base": {"repo": {"full_name": repo}}, "head": {"sha": head},
    }

    class Done:
        def __init__(self, returncode, stdout=b"", stderr=b""):
            self.returncode, self.stdout, self.stderr = returncode, stdout, stderr

    transport_calls = []

    def runner_for(comment_data=comment, pull_data=pull):
        def run(argv, **kwargs):
            transport_calls.append((tuple(argv), dict(kwargs)))
            payload = comment_data if "issues/comments" in argv[-1] else pull_data
            return Done(0, json.dumps(payload).encode())
        return run

    expect("identical bytes have no difference", _difference(b"a\n b", b"a\n b") == "")
    expect("line-ending drift is named", "line endings" in _difference(b"a\r\n", b"a\n"))
    expect("trailing spaces remain significant", _difference(b"a ", b"a") != "")
    expect("interior blank lines remain significant", _difference(b"a\n\nb", b"a\nb") != "")

    with tempfile.TemporaryDirectory(prefix="z-harness-publication-") as raw:
        body = Path(raw) / "body.md"
        body.write_bytes(body_bytes)
        expect("matching comment publication verifies", verify_comment(
            repo, pr, comment_id, head, author, body, runner_for()) == 0)
        expect("matching pull-request body verifies", verify_pr_body(
            repo, pr, head, body, runner_for()) == 0)

        changed = dict(comment, body="changed")
        expect("changed comment bytes fail", verify_comment(
            repo, pr, comment_id, head, author, body, runner_for(changed)) == 1)
        crlf_published = dict(comment, body=comment["body"].replace("\n", "\r\n"))
        expect("published CRLF bytes fail", verify_comment(
            repo, pr, comment_id, head, author, body, runner_for(crlf_published)) == 1)
        prefixed_pull = dict(pull, body="prefix\n" + pull["body"])
        expect("an untracked pull-request body prefix fails", verify_pr_body(
            repo, pr, head, body, runner_for(pull_data=prefixed_pull)) == 1)
        crlf_pull = dict(pull, body=pull["body"].replace("\n", "\r\n"))
        expect("pull-request CRLF bytes fail", verify_pr_body(
            repo, pr, head, body, runner_for(pull_data=crlf_pull)) == 1)

        for label, changed_comment in (
            ("wrong comment repository metadata fails", dict(comment, issue_url="https://api.github.com/repos/x/y/issues/8")),
            ("wrong comment pull request fails", dict(comment, issue_url=f"https://api.github.com/repos/{repo}/issues/9")),
            ("wrong comment identity fails", dict(comment, id=999)),
            ("wrong canonical comment URL fails", dict(comment, html_url=f"https://github.com/{repo}/pull/9#issuecomment-123")),
            ("wrong comment author fails", dict(comment, user={"login": "other", "id": 42})),
            ("edited comment metadata fails", dict(comment, updated_at="2026-08-19T00:01:00Z")),
        ):
            expect(label, verify_comment(
                repo, pr, comment_id, head, author, body, runner_for(changed_comment)) == 1)
        missing = dict(comment); missing.pop("author_association")
        expect("missing comment metadata fails", verify_comment(
            repo, pr, comment_id, head, author, body, runner_for(missing)) == 1)
        missing_user = dict(comment, user=None)
        expect("a malformed comment user object fails closed", verify_comment(
            repo, pr, comment_id, head, author, body, runner_for(missing_user)) == 1)

        wrong_head_pull = dict(pull, head={"sha": "b" * 40})
        expect("wrong current pull-request head fails", verify_comment(
            repo, pr, comment_id, head, author, body, runner_for(pull_data=wrong_head_pull)) == 1)
        wrong_number_pull = dict(pull, number=9)
        expect("wrong pull-request number fails", verify_pr_body(
            repo, pr, head, body, runner_for(pull_data=wrong_number_pull)) == 1)
        wrong_base_pull = dict(pull, base={"repo": {"full_name": "x/y"}})
        expect("wrong pull-request repository fails", verify_pr_body(
            repo, pr, head, body, runner_for(pull_data=wrong_base_pull)) == 1)

        for label, content in (
            ("missing Head line fails", b"Ran: exact check.\n"),
            ("duplicate Head lines fail", f"Head: `{head}`\nHead: `{head}`\n".encode()),
            ("abbreviated Head line fails", f"Head: `{head[:12]}`\n".encode()),
            ("mismatched Head line fails", f"Head: `{'b' * 40}`\n".encode()),
        ):
            body.write_bytes(content)
            expect(label, verify_comment(
                repo, pr, comment_id, head, author, body, runner_for()) == 1)

        for label, content in (
            ("a CRLF source fails before publication comparison", body_bytes.replace(b"\n", b"\r\n")),
            ("a source without terminal LF fails", body_bytes[:-1]),
            ("a source with several terminal LFs fails", body_bytes + b"\n"),
            ("invalid UTF-8 source fails", b"Head: `" + head.encode() + b"`\n\xff"),
        ):
            body.write_bytes(content)
            expect(label, verify_comment(
                repo, pr, comment_id, head, author, body, runner_for()) == 2)

        body.write_bytes(body_bytes)
        def broken_runner(argv, **kwargs):
            return Done(1, stderr=b"gh: Not Found (HTTP 404)")
        expect("transport failure exits 2", verify_comment(
            repo, pr, comment_id, head, author, body, broken_runner) == 2)
        def invalid_json_runner(argv, **kwargs):
            return Done(0, b"not-json")
        expect("invalid API JSON exits 2", verify_comment(
            repo, pr, comment_id, head, author, body, invalid_json_runner) == 2)

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
    pr_body = subparsers.add_parser("pr-body")
    pr_body.add_argument("--repo", required=True)
    pr_body.add_argument("--pr", required=True, type=int)
    pr_body.add_argument("--expected-head", required=True, type=_head)
    pr_body.add_argument("--body-file", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.selftest and args.mode is None:
        parser.error("choose comment or pr-body")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.selftest:
        return selftest()
    if args.mode == "comment":
        return verify_comment(args.repo, args.pr, args.comment_id, args.expected_head,
                              args.expected_author, args.body_file)
    return verify_pr_body(args.repo, args.pr, args.expected_head, args.body_file)


if __name__ == "__main__":
    raise SystemExit(main())
