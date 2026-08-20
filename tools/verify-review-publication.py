#!/usr/bin/env python3
"""Verify an append-only review comment or frozen pull-request publication.

The repository gate can validate a draft's inputs but cannot see what GitHub received.
This tool reads complete REST objects back and binds both modes to the requested repository,
pull request and current head. Comment mode compares raw UTF-8 body bytes and additionally
binds the author, comment identity and unedited timestamps. Snapshot mode compares the live
pull-request body and title to a reviewed frozen digest; it does not rewrite either surface.

Local source files use one canonical form: strict UTF-8, no carriage returns, and exactly
one terminal line feed. GitHub removes that final line feed from issue comments; that is the
only publication transformation accepted.
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


VERSION = "3.0"
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
        manifest = Path(raw) / "frozen-publication.json"
        body.write_bytes(body_bytes)
        manifest.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        expect("matching comment publication verifies", verify_comment(
            repo, pr, comment_id, head, author, body, runner_for()) == 0)
        expect("matching frozen pull-request publication verifies", verify_pr_snapshot(
            repo, pr, head, manifest, runner_for()) == 0)

        changed = dict(comment, body="changed")
        expect("changed comment bytes fail", verify_comment(
            repo, pr, comment_id, head, author, body, runner_for(changed)) == 1)
        crlf_published = dict(comment, body=comment["body"].replace("\n", "\r\n"))
        expect("published CRLF bytes fail", verify_comment(
            repo, pr, comment_id, head, author, body, runner_for(crlf_published)) == 1)
        prefixed_pull = dict(pull, body="prefix\n" + pull["body"])
        expect("a changed frozen pull-request body fails", verify_pr_snapshot(
            repo, pr, head, manifest, runner_for(pull_data=prefixed_pull)) == 1)
        same_length_body = dict(
            pull, body=("X" if not pull["body"].startswith("X") else "Y") + pull["body"][1:])
        expect("a same-length frozen body digest change fails", verify_pr_snapshot(
            repo, pr, head, manifest, runner_for(pull_data=same_length_body)) == 1)
        crlf_pull = dict(pull, body=pull["body"].replace("\n", "\r\n"))
        expect("pull-request CRLF bytes fail", verify_pr_snapshot(
            repo, pr, head, manifest, runner_for(pull_data=crlf_pull)) == 1)
        changed_title = dict(pull, title=title[::-1])
        expect("a same-length frozen title digest change fails", verify_pr_snapshot(
            repo, pr, head, manifest, runner_for(pull_data=changed_title)) == 1)

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
        expect("wrong pull-request number fails", verify_pr_snapshot(
            repo, pr, head, manifest, runner_for(pull_data=wrong_number_pull)) == 1)
        wrong_base_pull = dict(pull, base={"repo": {"full_name": "x/y"}})
        expect("wrong pull-request repository fails", verify_pr_snapshot(
            repo, pr, head, manifest, runner_for(pull_data=wrong_base_pull)) == 1)
        malformed_snapshot = dict(snapshot, body_sha256="not-a-digest")
        manifest.write_text(
            json.dumps(malformed_snapshot, indent=2) + "\n", encoding="utf-8")
        expect("a malformed frozen-publication digest fails", verify_pr_snapshot(
            repo, pr, head, manifest, runner_for()) == 1)
        manifest.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        duplicate_manifest = manifest.read_text(encoding="utf-8").replace(
            '  "schema_version": 1,',
            '  "schema_version": 1,\n  "schema_version": 1,',
            1,
        )
        manifest.write_text(duplicate_manifest, encoding="utf-8")
        expect("duplicate frozen-publication fields fail closed", verify_pr_snapshot(
            repo, pr, head, manifest, runner_for()) == 2)
        manifest.write_bytes(
            (json.dumps(snapshot, indent=2) + "\n").encode().replace(b"\n", b"\r\n"))
        expect("CRLF frozen-publication source bytes fail closed", verify_pr_snapshot(
            repo, pr, head, manifest, runner_for()) == 2)
        manifest.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")

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
