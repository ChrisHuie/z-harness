#!/usr/bin/env python3
"""Verify an append-only review comment or frozen pull-request publication.

The repository gate can validate a draft's inputs but cannot see what GitHub received.
This tool reads complete REST objects back and binds both modes to the requested repository,
pull request and current head. Comment mode compares raw UTF-8 body bytes and additionally
binds the author, comment identity, unedited timestamps, and append-only predecessor records.
Snapshot mode compares the live
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
from datetime import datetime
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


VERSION = "3.4"
RECEIPT = "REVIEW-PUBLICATION-SUMMARY"
HEAD_LINE = re.compile(rb"^Head: `([0-9a-f]{40})`$", re.MULTILINE)
COMMENT_URL = re.compile(
    r"^https://github\.com/([^/]+/[^/]+)/pull/([1-9][0-9]*)#issuecomment-([1-9][0-9]*)$")
SNAPSHOT_SCHEMA_VERSION = 1
SNAPSHOT_KIND = "pull-request-frozen-publication"
# The note a generated snapshot fixture carries. It is NOT the note every manifest must
# carry: the field is that manifest's own provenance prose, and a publication frozen at
# creation cannot truthfully say it was frozen when the rule was adopted. Its exact bytes are
# pinned per manifest by FROZEN_PUBLICATIONS in tools/ci-gate.py, so requiring one wording
# here was a second source of truth for the same text and rejected an accurate note.
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


def _json_array(raw: bytes, label: str) -> list:
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
    if not isinstance(value, list):
        raise TransportError(f"{label} response is not a JSON array")
    return value


def _api_paginated_array(repo: str, endpoint: str, label: str, runner=None) -> list:
    """Read every REST page as one closed list using gh's slurped pagination mode."""
    runner = subprocess.run if runner is None else runner
    done = runner(
        ["gh", "api", "--paginate", "--slurp", f"repos/{repo}/{endpoint}"],
        capture_output=True, text=False, timeout=60)
    if done.returncode != 0:
        diagnostic = bytes(done.stderr or b"no diagnostic").decode("utf-8", "replace")
        raise TransportError(f"cannot read {label} in {repo}: {diagnostic.strip()[:200]}")
    pages = _json_array(bytes(done.stdout), label)
    items = []
    for index, page in enumerate(pages):
        if not isinstance(page, list):
            raise TransportError(f"{label} page {index} is not a JSON array")
        items.extend(page)
    return items


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


def _positive_int(value, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise PublicationError(f"publication metadata has invalid {label}: {value!r}")
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
        _positive_int(data.get("id"), "id")
        _positive_int(user.get("id"), "user.id")
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


def _github_time(value, label):
    if not isinstance(value, str):
        raise PublicationError(f"publication metadata is missing {label}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PublicationError(f"publication metadata has invalid {label}: {value!r}") from exc
    if parsed.utcoffset() is None:
        raise PublicationError(f"publication metadata has timezone-free {label}: {value!r}")
    return parsed


def _handoff_inventory(
        current: dict, repo: str, pr: int, expected_author: str, runner=None):
    """Return the latest prior handoff and closed comment map from the PR inventory."""
    comments = _api_paginated_array(
        repo, f"issues/{pr}/comments?per_page=100", "pull request comments", runner)
    try:
        current_created = _github_time(current.get("created_at"), "created_at")
    except PublicationError as exc:
        return str(exc), None, {}
    try:
        current_id = _positive_int(current.get("id"), "id")
        current_user_id = _positive_int(
            _object(current.get("user")).get("id"), "user.id")
    except PublicationError as exc:
        return str(exc), None, {}
    current_matches = 0
    prior = []
    by_id = {}
    for item in comments:
        if not isinstance(item, dict):
            raise TransportError("pull request comments contains a non-object item")
        try:
            item_id = _positive_int(item.get("id"), "handoff comment id")
        except PublicationError as exc:
            return str(exc), None, {}
        if item_id in by_id:
            return f"pull-request comment inventory repeats comment id {item_id}", None, {}
        by_id[item_id] = item
        if item_id == current_id:
            current_matches += 1
            compared_fields = (
                "body", "html_url", "issue_url", "created_at", "updated_at")
            item_user = _object(item.get("user"))
            current_user = _object(current.get("user"))
            try:
                inventory_user_id = _positive_int(
                    item_user.get("id"), "inventory current user.id")
            except PublicationError as exc:
                return str(exc), None, {}
            if (any(item.get(field) != current.get(field) for field in compared_fields)
                    or item_user.get("login") != current_user.get("login")
                    or inventory_user_id != current_user.get("id")):
                return (
                    "current publication differs between its comment object and the "
                    "complete pull-request comment inventory", None, {})
            continue
        item_user = _object(item.get("user"))
        try:
            item_user_id = _positive_int(
                item_user.get("id"), "inventory user.id")
        except PublicationError as exc:
            return str(exc), None, {}
        same_login = item_user.get("login") == expected_author
        same_identity = item_user_id == current_user_id
        if not same_login and not same_identity:
            continue
        body = _text_bytes(item.get("body"), "pull request comment")
        if len(HEAD_LINE.findall(body)) != 1:
            continue
        if same_login and not same_identity:
            return (
                "same-login handoff comment has a different numeric author identity: "
                f"{item_user_id!r} != {current_user_id!r}", None, {})
        try:
            created = _github_time(item.get("created_at"), "earlier handoff created_at")
        except PublicationError as exc:
            return str(exc), None, {}
        if (created, item_id) < (current_created, current_id):
            prior.append(((created, item_id), item))
    if current_matches != 1:
        return (
            "initial publication comment was not listed exactly once in the complete "
            f"pull-request comment inventory: {current_matches}", None, {})
    latest = max(prior, key=lambda record: record[0])[1] if prior else None
    return "", latest, by_id


def _initial_publication_error(
        current: dict, repo: str, pr: int, expected_author: str, runner=None) -> str:
    """Prove that no prior same-author handoff exists on the pull request."""
    problem, latest, _inventory = _handoff_inventory(
        current, repo, pr, expected_author, runner)
    if problem:
        return problem
    if latest is not None:
        return (
            "initial publication has an older same-author handoff comment: "
            f"{latest.get('html_url') or latest.get('id')!r}")
    return ""


def _predecessor_contract(
        current: dict, submitted: bytes, repo: str, pr: int, expected_author: str,
        initial_publication: bool, predecessor_urls, runner=None):
    """Return (problem, closed predecessor records) for one append-only handoff."""
    urls = tuple(predecessor_urls or ())
    if initial_publication:
        if urls:
            return "an initial publication cannot name predecessor comments", []
        return _initial_publication_error(
            current, repo, pr, expected_author, runner), []
    if not urls:
        return "a later publication must name at least one predecessor comment", []
    if len(set(urls)) != len(urls):
        return "predecessor comment URLs are not unique", []
    try:
        current_created = _github_time(current.get("created_at"), "created_at")
    except PublicationError as exc:
        return str(exc), []
    parsed_urls = []
    for url in urls:
        matched = COMMENT_URL.fullmatch(url)
        if not matched:
            return f"predecessor comment URL is not canonical: {url!r}", []
        linked_repo, linked_pr, linked_id = matched.groups()
        if linked_repo != repo or int(linked_pr) != pr:
            return f"predecessor comment URL is outside {repo} pull request {pr}: {url!r}", []
        predecessor_id = int(linked_id)
        if predecessor_id == current.get("id"):
            return "a comment cannot name itself as its predecessor", []
        if submitted.count(url.encode("utf-8")) != 1:
            return f"submitted handoff must link predecessor exactly once: {url}", []
        parsed_urls.append((url, predecessor_id))
    inventory_problem, latest, inventory = _handoff_inventory(
        current, repo, pr, expected_author, runner)
    if inventory_problem:
        return inventory_problem, []
    if latest is None:
        return "a later publication has no prior handoff in the complete comment inventory", []
    latest_url = (
        f"https://github.com/{repo}/pull/{pr}#issuecomment-{latest.get('id')}")
    if latest_url not in urls:
        return (
            "later publication does not link the latest prior handoff comment: "
            f"{latest_url}"), []
    current_author_id = _object(current.get("user")).get("id")
    records = []
    for url, predecessor_id in parsed_urls:
        predecessor = _api_object(
            repo, f"issues/comments/{predecessor_id}", "predecessor comment", runner)
        predecessor_user = _object(predecessor.get("user"))
        expected_issue = f"https://api.github.com/repos/{repo}/issues/{pr}"
        required = {
            "id": predecessor.get("id"),
            "issue_url": predecessor.get("issue_url"),
            "html_url": predecessor.get("html_url"),
            "created_at": predecessor.get("created_at"),
            "updated_at": predecessor.get("updated_at"),
            "user.login": predecessor_user.get("login"),
            "user.id": predecessor_user.get("id"),
            "body": predecessor.get("body"),
        }
        try:
            for label, value in required.items():
                _required(value, f"predecessor {label}")
            _positive_int(predecessor.get("id"), "predecessor id")
            _positive_int(predecessor_user.get("id"), "predecessor user.id")
            predecessor_created = _github_time(
                predecessor.get("created_at"), "predecessor created_at")
        except PublicationError as exc:
            return str(exc), records
        if predecessor.get("id") != predecessor_id:
            return (f"predecessor comment id is {predecessor.get('id')!r}, "
                    f"expected {predecessor_id}"), records
        if predecessor.get("issue_url") != expected_issue:
            return "predecessor comment belongs to another pull request", records
        if predecessor.get("html_url") != url:
            return f"predecessor comment URL is {predecessor.get('html_url')!r}, expected {url!r}", records
        if predecessor_user.get("id") != current_author_id:
            return (
                "predecessor comment numeric author identity is "
                f"{predecessor_user.get('id')!r}, expected {current_author_id!r}"), records
        if predecessor.get("created_at") != predecessor.get("updated_at"):
            return "predecessor comment was edited", records
        if ((predecessor_created, predecessor_id)
                >= (current_created, current.get("id"))):
            return "predecessor comment is not older than the current publication", records
        predecessor_body = _text_bytes(predecessor.get("body"), "predecessor comment")
        if len(HEAD_LINE.findall(predecessor_body)) != 1:
            return "predecessor comment does not contain exactly one full Head line", records
        inventory_predecessor = inventory.get(predecessor_id)
        if inventory_predecessor is None:
            return "predecessor comment is absent from the complete comment inventory", records
        compared_fields = (
            "id", "body", "issue_url", "html_url", "created_at", "updated_at")
        inventory_user = _object(inventory_predecessor.get("user"))
        if (any(inventory_predecessor.get(field) != predecessor.get(field)
                for field in compared_fields)
                or inventory_user.get("login") != predecessor_user.get("login")
                or inventory_user.get("id") != predecessor_user.get("id")):
            return (
                "predecessor comment differs between its direct object and the complete "
                "pull-request comment inventory"), records
        records.append({
            "id": predecessor_id,
            "url": url,
            "author": predecessor_user.get("login"),
            "author_id": predecessor_user.get("id"),
            "created_at": predecessor.get("created_at"),
            "updated_at": predecessor.get("updated_at"),
            "edited": False,
        })
    return "", records


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
    }
    for field, expected in expected_scalars.items():
        if snapshot.get(field) != expected:
            return f"snapshot {field} is {snapshot.get(field)!r}, expected {expected!r}"
    if not isinstance(snapshot.get("note"), str) or not snapshot["note"].strip():
        return "snapshot note is missing or empty"
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
    commit = _api_object(repo, f"commits/{sha}", "frozen head commit", runner)
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
                   expected_author: str, body_path: Path, runner=None, *,
                   initial_publication=True, predecessor_urls=()) -> int:
    try:
        submitted = _source_bytes(body_path)
        comment = _api_object(repo, f"issues/comments/{comment_id}", "comment", runner)
        published = _text_bytes(comment.get("body"), "comment")
        expected, terminal_line_feed = _accepted_form(published, submitted)
        problem = _comment_metadata_error(
            comment, repo, pr, comment_id, expected_author, expected_head, submitted)
        if not problem:
            problem = _difference(published, expected)
        predecessors = []
        if not problem:
            problem, predecessors = _predecessor_contract(
                comment, submitted, repo, pr, expected_author,
                initial_publication, predecessor_urls, runner)
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
        initial_publication=initial_publication, predecessors=predecessors,
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
        "created_at": "2026-08-19T00:01:00Z", "updated_at": "2026-08-19T00:01:00Z",
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
        "expected_sha256", "initial_publication", "kind", "pr", "predecessors",
        "problem", "published_bytes",
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
            "initial_publication": True,
            "predecessors": [],
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
                   commit_rc=0, predecessor_data=None, issue_comment_pages=None):
        def run(argv, **kwargs):
            transport_calls.append((tuple(argv), dict(kwargs)))
            endpoint = argv[-1]
            if f"issues/{pr}/comments?" in endpoint:
                pages = (issue_comment_pages if issue_comment_pages is not None
                         else [[comment_data] + (
                             [predecessor_data] if predecessor_data is not None else [])])
                payload = (pages if "--paginate" in argv and "--slurp" in argv
                           else pages[:1])
            elif "issues/comments" in endpoint:
                if (predecessor_data is not None
                        and not endpoint.endswith(f"/{comment_data.get('id')}")):
                    payload = predecessor_data
                else:
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

        predecessor_id = 122
        predecessor_url = (
            f"https://github.com/{repo}/pull/{pr}#issuecomment-{predecessor_id}")
        predecessor = {
            "id": predecessor_id,
            "body": f"Head: `{'b' * 40}`\n\nEarlier handoff.",
            "issue_url": f"https://api.github.com/repos/{repo}/issues/{pr}",
            "html_url": predecessor_url,
            "user": {"login": author, "id": 42},
            "author_association": "OWNER",
            "created_at": "2026-08-19T00:00:00Z",
            "updated_at": "2026-08-19T00:00:00Z",
        }
        later_bytes = (
            f"Head: `{head}`\n\nSupersedes {predecessor_url}.\n").encode()
        later_comment = dict(comment, body=later_bytes[:-1].decode())
        body.write_bytes(later_bytes)
        later_code, later_receipt = captured_receipt(lambda: verify_comment(
            repo, pr, comment_id, head, author, body,
            runner_for(later_comment, predecessor_data=predecessor),
            initial_publication=False, predecessor_urls=(predecessor_url,)))
        expect(
            "a later handoff verifies one canonical older unedited predecessor link",
            later_code == 0 and comment_receipt_is_closed(later_receipt)
            and later_receipt.get("initial_publication") is False
            and later_receipt.get("predecessors") == [{
                "id": predecessor_id, "url": predecessor_url, "author": author,
                "author_id": 42,
                "created_at": predecessor["created_at"],
                "updated_at": predecessor["updated_at"], "edited": False,
            }],
        )
        body.write_bytes(later_bytes)
        expect(
            "a later handoff cannot restart the lineage by declaring itself initial",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(
                    later_comment,
                    issue_comment_pages=[[later_comment], [predecessor]]),
                initial_publication=True),
                "initial publication has an older same-author handoff"),
        )
        equal_time_predecessor = dict(
            predecessor, created_at=later_comment["created_at"],
            updated_at=later_comment["created_at"])
        expect(
            "a same-second lower-id handoff prevents a later comment declaring itself initial",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(
                    later_comment,
                    issue_comment_pages=[[later_comment], [equal_time_predecessor]]),
                initial_publication=True),
                "initial publication has an older same-author handoff"),
        )
        expect(
            "a same-second lower-id handoff is a valid immediate predecessor",
            verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(
                    later_comment, predecessor_data=equal_time_predecessor,
                    issue_comment_pages=[[later_comment, equal_time_predecessor]]),
                initial_publication=False,
                predecessor_urls=(predecessor_url,)) == 0,
        )
        newest_id = 123
        newest_url = f"https://github.com/{repo}/pull/{pr}#issuecomment-{newest_id}"
        newest = dict(
            predecessor, id=newest_id, html_url=newest_url,
            body=f"Head: `{'c' * 40}`\n\nNewer handoff.",
            created_at="2026-08-19T00:01:00Z",
            updated_at="2026-08-19T00:01:00Z")
        current_id = 124
        current_bytes = (
            f"Head: `{head}`\n\nIncorrectly skips to {predecessor_url}.\n").encode()
        current_comment = dict(
            comment, id=current_id,
            html_url=f"https://github.com/{repo}/pull/{pr}#issuecomment-{current_id}",
            body=current_bytes[:-1].decode(),
            created_at="2026-08-19T00:02:00Z",
            updated_at="2026-08-19T00:02:00Z")
        body.write_bytes(current_bytes)
        expect(
            "a later handoff cannot omit the latest prior handoff from its links",
            denies(lambda: verify_comment(
                repo, pr, current_id, head, author, body,
                runner_for(
                    current_comment, predecessor_data=predecessor,
                    issue_comment_pages=[[current_comment, predecessor, newest]]),
                initial_publication=False, predecessor_urls=(predecessor_url,)),
                "does not link the latest prior handoff"),
        )
        body.write_bytes(later_bytes)
        different_id_predecessor = dict(
            predecessor, user={"login": author, "id": 99})
        expect(
            "a predecessor login cannot stand in for a different numeric author identity",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(
                    later_comment, predecessor_data=different_id_predecessor,
                    issue_comment_pages=[[later_comment, predecessor]]),
                initial_publication=False, predecessor_urls=(predecessor_url,)),
                "predecessor comment numeric author identity"),
        )
        expect(
            "a string predecessor user id is not a numeric author identity",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(
                    later_comment,
                    predecessor_data=dict(
                        predecessor, user={"login": author, "id": "42"}),
                    issue_comment_pages=[[later_comment, predecessor]]),
                initial_publication=False, predecessor_urls=(predecessor_url,)),
                "invalid predecessor user.id"),
        )
        inventory_float_identity = dict(
            predecessor, user={"login": author, "id": 42.0})
        expect(
            "a float inventory user id cannot equal the direct numeric identity",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(
                    later_comment, predecessor_data=predecessor,
                    issue_comment_pages=[[
                        later_comment, inventory_float_identity]]),
                initial_publication=False, predecessor_urls=(predecessor_url,)),
                "invalid inventory user.id"),
        )
        body.write_bytes(body_bytes)
        expect(
            "a later handoff without a predecessor is rejected",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body, runner_for(),
                initial_publication=False), "must name at least one predecessor"),
        )
        expect(
            "an initial handoff cannot smuggle a predecessor list",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body, runner_for(),
                initial_publication=True, predecessor_urls=(predecessor_url,)),
                "initial publication cannot name predecessor"),
        )
        expect(
            "a predecessor URL absent from the submitted handoff is rejected",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(predecessor_data=predecessor),
                initial_publication=False, predecessor_urls=(predecessor_url,)),
                "must link predecessor exactly once"),
        )
        body.write_bytes(later_bytes)
        edited_predecessor = dict(
            predecessor, updated_at="2026-08-19T00:00:30Z")
        expect(
            "an edited predecessor comment is rejected",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(later_comment, predecessor_data=edited_predecessor),
                initial_publication=False, predecessor_urls=(predecessor_url,)),
                "predecessor comment was edited"),
        )
        inventory_edited_predecessor = dict(
            predecessor, updated_at="2026-08-19T00:00:30Z")
        expect(
            "a predecessor direct object cannot contradict the inventory used for lineage",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(
                    later_comment, predecessor_data=predecessor,
                    issue_comment_pages=[[
                        later_comment, inventory_edited_predecessor]]),
                initial_publication=False, predecessor_urls=(predecessor_url,)),
                "predecessor comment differs between its direct object"),
        )
        not_older = dict(
            predecessor, created_at="2026-08-19T00:02:00Z",
            updated_at="2026-08-19T00:02:00Z")
        expect(
            "a predecessor newer than the current handoff is rejected",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(
                    later_comment, predecessor_data=not_older,
                    issue_comment_pages=[[later_comment, predecessor]]),
                initial_publication=False, predecessor_urls=(predecessor_url,)),
                "not older than the current publication"),
        )
        expect(
            "duplicate predecessor CLI values are rejected",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(later_comment, predecessor_data=predecessor),
                initial_publication=False,
                predecessor_urls=(predecessor_url, predecessor_url)),
                "predecessor comment URLs are not unique"),
        )
        repeated_link_bytes = later_bytes + (
            f"Repeated link: {predecessor_url}.\n").encode()
        body.write_bytes(repeated_link_bytes)
        expect(
            "a predecessor URL repeated in the submitted handoff is rejected",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(dict(later_comment, body=repeated_link_bytes[:-1].decode()),
                           predecessor_data=predecessor),
                initial_publication=False, predecessor_urls=(predecessor_url,)),
                "must link predecessor exactly once"),
        )
        noncanonical_url = predecessor_url + "/extra"
        noncanonical_bytes = (
            f"Head: `{head}`\n\nSupersedes {noncanonical_url}.\n").encode()
        body.write_bytes(noncanonical_bytes)
        expect(
            "a predecessor URL with a canonical prefix and trailing suffix is rejected",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(
                    dict(later_comment, body=noncanonical_bytes[:-1].decode()),
                    predecessor_data=dict(predecessor, html_url=noncanonical_url)),
                initial_publication=False, predecessor_urls=(noncanonical_url,)),
                "predecessor comment URL is not canonical"),
        )
        outside_url = (
            f"https://github.com/Other/repo/pull/99#issuecomment-{predecessor_id}")
        outside_bytes = f"Head: `{head}`\n\nSupersedes {outside_url}.\n".encode()
        body.write_bytes(outside_bytes)
        expect(
            "a predecessor URL naming another repository or pull request is rejected",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(dict(later_comment, body=outside_bytes[:-1].decode()),
                           predecessor_data=dict(
                               predecessor, html_url=outside_url,
                               issue_url="https://api.github.com/repos/Other/repo/issues/99")),
                initial_publication=False, predecessor_urls=(outside_url,)),
                "is outside"),
        )
        self_url = comment["html_url"]
        self_bytes = f"Head: `{head}`\n\nSupersedes {self_url}.\n".encode()
        body.write_bytes(self_bytes)
        expect(
            "a handoff cannot name its own comment as predecessor",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(dict(later_comment, body=self_bytes[:-1].decode())),
                initial_publication=False, predecessor_urls=(self_url,)),
                "cannot name itself"),
        )
        body.write_bytes(later_bytes)
        expect(
            "the fetched predecessor id must match the requested comment id",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(
                    later_comment, predecessor_data=dict(predecessor, id=999),
                    issue_comment_pages=[[later_comment, predecessor]]),
                initial_publication=False, predecessor_urls=(predecessor_url,)),
                "predecessor comment id"),
        )
        expect(
            "a float predecessor id cannot impersonate the requested integer id",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(
                    later_comment,
                    predecessor_data=dict(predecessor, id=float(predecessor_id)),
                    issue_comment_pages=[[later_comment, predecessor]]),
                initial_publication=False, predecessor_urls=(predecessor_url,)),
                "invalid predecessor id"),
        )
        expect(
            "the fetched predecessor must belong to the same pull request",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(later_comment, predecessor_data=dict(
                    predecessor,
                    issue_url=f"https://api.github.com/repos/{repo}/issues/{pr + 1}")),
                initial_publication=False, predecessor_urls=(predecessor_url,)),
                "belongs to another pull request"),
        )
        expect(
            "the fetched predecessor canonical URL must match the submitted URL",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(later_comment, predecessor_data=dict(
                    predecessor, html_url=predecessor_url + "/wrong")),
                initial_publication=False, predecessor_urls=(predecessor_url,)),
                "predecessor comment URL is"),
        )
        renamed_predecessor = dict(
            predecessor, user={"login": "earlier-login", "id": 42})
        renamed_code, renamed_receipt = captured_receipt(lambda: verify_comment(
            repo, pr, comment_id, head, author, body,
            runner_for(
                later_comment, predecessor_data=renamed_predecessor,
                issue_comment_pages=[[later_comment, renamed_predecessor]]),
            initial_publication=False, predecessor_urls=(predecessor_url,)))
        expect(
            "numeric identity keeps a renamed predecessor in the same handoff lineage",
            renamed_code == 0
            and renamed_receipt.get("predecessors", [{}])[0].get("author")
            == "earlier-login"
            and renamed_receipt.get("predecessors", [{}])[0].get("author_id") == 42,
        )
        expect(
            "the predecessor must contain exactly one full Head line",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(
                    later_comment, predecessor_data=dict(
                        predecessor, body="Earlier handoff without a head."),
                    issue_comment_pages=[[later_comment, predecessor]]),
                initial_publication=False, predecessor_urls=(predecessor_url,)),
                "does not contain exactly one full Head line"),
        )
        expect(
            "the current handoff timestamp must carry a timezone",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(dict(
                    later_comment, created_at="2026-08-19T00:01:00",
                    updated_at="2026-08-19T00:01:00"),
                           predecessor_data=predecessor),
                initial_publication=False, predecessor_urls=(predecessor_url,)),
                "timezone-free created_at"),
        )
        expect(
            "the predecessor timestamp must carry a timezone",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(
                    later_comment, predecessor_data=dict(
                        predecessor, created_at="2026-08-19T00:00:00",
                        updated_at="2026-08-19T00:00:00"),
                    issue_comment_pages=[[later_comment, predecessor]]),
                initial_publication=False, predecessor_urls=(predecessor_url,)),
                "timezone-free predecessor created_at"),
        )
        body.write_bytes(body_bytes)
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
        spaced_source = body_bytes[:-1] + b" \n"
        body.write_bytes(spaced_source)
        spaced_stripped = dict(comment, body=spaced_source[:-1].decode())
        expect(
            "stripped publication removes only the one canonical terminal line feed",
            verify_comment(repo, pr, comment_id, head, author, body,
                           runner_for(spaced_stripped)) == 0,
        )
        overstripped = dict(comment, body=spaced_source.rstrip().decode())
        expect(
            "stripping significant trailing space is a mismatch, not an accepted form",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body, runner_for(overstripped)),
                "published body differs", 1)
            and receipt_field(lambda: verify_comment(
                repo, pr, comment_id, head, author, body, runner_for(overstripped)),
                "terminal_line_feed") == "mismatch",
        )
        body.write_bytes(body_bytes)
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
        expect("an unreachable frozen_at_head commit is a transport failure", denies(
            lambda: verify_pr_snapshot(
                repo, pr, head, manifest, runner_for(commit_rc=1)),
            "cannot read frozen head commit", 2))
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
        # Same shape: pin the title branch's own diagnosis, or a message mutation scoped to
        # `title` alone passes while the body arm carries the case.
        expect("a same-length frozen title digest change fails", denies(
            lambda: verify_pr_snapshot(
                repo, pr, head, manifest, runner_for(pull_data=changed_title)),
            'published title digest is', 1))
        expect("a manifest may carry its own frozen-publication note", _snapshot_error(
            dict(snapshot, note="Frozen at creation under the append-only rule."),
            repo, pr, body_bytes, title.encode()) == "")
        expect("a blank frozen-publication note fails", _snapshot_error(
            dict(snapshot, note="   "), repo, pr, body_bytes, title.encode()) != "")
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
            ("edited comment metadata fails", "comment was edited", dict(comment, updated_at="2026-08-19T00:02:00Z")),
        ):
            expect(label, denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body, runner_for(changed_comment)),
                named))
        expect(
            "a float comment id cannot impersonate the requested integer id",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(dict(comment, id=float(comment_id)))),
                "invalid id"),
        )
        expect(
            "a string current user id is not a numeric author identity",
            denies(lambda: verify_comment(
                repo, pr, comment_id, head, author, body,
                runner_for(dict(comment, user={"login": author, "id": "42"}))),
                "invalid user.id"),
        )
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
        # The receipt-equality check below derives its expectation from production, so it
        # cannot say WHICH guard fired. This literal is what makes the branch's content
        # assertable; without it, renaming the message to name the wrong surface survives.
        expect("wrong pull-request number fails", denies(lambda: verify_pr_snapshot(
            repo, pr, head, manifest, runner_for(pull_data=wrong_number_pull)),
            'pull request number is', 1))
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

    comment_cli = [
        "comment", "--repo", repo, "--pr", str(pr), "--comment-id", str(comment_id),
        "--expected-head", head, "--expected-author", author,
        "--body-file", "/tmp/handoff.md",
    ]
    initial_args = parse_args(comment_cli + ["--initial-publication"])
    expect(
        "the comment CLI explicitly marks the initial publication",
        initial_args.initial_publication is True and initial_args.predecessor_url == [],
    )
    later_args = parse_args(comment_cli + [
        "--predecessor-url", "https://github.com/o/r/pull/8#issuecomment-1",
        "--predecessor-url", "https://github.com/o/r/pull/8#issuecomment-2",
    ])
    expect(
        "the comment CLI preserves every repeatable predecessor URL",
        later_args.initial_publication is False
        and later_args.predecessor_url == [
            "https://github.com/o/r/pull/8#issuecomment-1",
            "https://github.com/o/r/pull/8#issuecomment-2",
        ],
    )
    missing_predecessor_rejected = False
    both_modes_rejected = False
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            parse_args(comment_cli)
        except SystemExit as exc:
            missing_predecessor_rejected = exc.code == 2
        try:
            parse_args(comment_cli + [
                "--initial-publication", "--predecessor-url",
                "https://github.com/o/r/pull/8#issuecomment-1",
            ])
        except SystemExit as exc:
            both_modes_rejected = exc.code == 2
    expect("the comment CLI rejects an implicit publication mode",
           missing_predecessor_rejected)
    expect("the comment CLI rejects contradictory publication modes",
           both_modes_rejected)

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
    predecessor = comment.add_mutually_exclusive_group(required=True)
    predecessor.add_argument("--initial-publication", action="store_true")
    predecessor.add_argument("--predecessor-url", action="append", default=[])
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
                              args.expected_author, args.body_file,
                              initial_publication=args.initial_publication,
                              predecessor_urls=args.predecessor_url)
    return verify_pr_snapshot(
        args.repo, args.pr, args.expected_head, args.manifest)


if __name__ == "__main__":
    raise SystemExit(main())
