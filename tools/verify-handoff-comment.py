#!/usr/bin/env python3
"""Verify a posted review handoff against the bytes it was built from.

`contracts/review/README.md` requires a handoff to be POSTED as a new comment and then read
back, because the repository gate can only validate the sources used to build one -- never
the comment that was actually published. Before this tool that read-back was an instruction
with no artifact: a handoff could carry a hand-typed figure contradicting the generated
summary and every gate stayed green, because nothing in the repository ever fetched a
comment. This is the missing half.

It reads the published comment through `gh` and compares it against the submitted file, then
prints a receipt line. GitHub strips trailing newlines when it stores a body -- measured on
this tool's first real use, where a file ending in one newline came back one line shorter --
so trailing newlines are normalized on both sides before comparing. Nothing else is: a body
differing anywhere else is a body the reviewer did not approve, and interior blank lines,
indentation and line endings all still compare.

  tools/verify-handoff-comment.py --repo owner/name --comment-id 123 --body-file draft.md
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


VERSION = "1.0"
RECEIPT = "HANDOFF-READBACK-SUMMARY"


def fetch_comment_body(repo: str, comment_id: str, runner=None) -> str:
    """Return the published body, or raise with the transport's own diagnostic."""
    runner = subprocess.run if runner is None else runner
    done = runner(
        ["gh", "api", f"repos/{repo}/issues/comments/{comment_id}", "--jq", ".body"],
        capture_output=True, text=True, timeout=60)
    if done.returncode != 0:
        raise ValueError(
            f"cannot read comment {comment_id} in {repo}: "
            f"{(done.stderr or 'no diagnostic').strip()[:200]}")
    # `--jq .body` emits the body followed by one newline of its own. Strip exactly that,
    # not whitespace generally: trailing blank lines are part of a body and must compare.
    body = done.stdout
    return body[:-1] if body.endswith("\n") else body


def readback_error(published: str, submitted: str) -> str:
    """Return the first way the published bytes differ from the submitted ones."""
    # GitHub does not store a trailing newline, so requiring one to survive would make every
    # file that ends the way text files end permanently unverifiable. Normalize only that,
    # and only at the very end of the body.
    published = published.rstrip("\n")
    submitted = submitted.rstrip("\n")
    if published == submitted:
        return ""
    if published.replace("\r\n", "\n") == submitted.replace("\r\n", "\n"):
        return "published body differs only in line endings"
    published_lines = published.split("\n")
    submitted_lines = submitted.split("\n")
    for index, (left, right) in enumerate(zip(published_lines, submitted_lines), 1):
        if left != right:
            return (f"published body differs from the submitted bytes at line {index}: "
                    f"published {left[:60]!r} != submitted {right[:60]!r}")
    return (f"published body has {len(published_lines)} line(s) where the submitted bytes "
            f"have {len(submitted_lines)}")


def verify(repo: str, comment_id: str, body_path: Path, runner=None) -> int:
    submitted = body_path.read_text(encoding="utf-8")
    try:
        published = fetch_comment_body(repo, comment_id, runner=runner)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"{RECEIPT} comment={comment_id} verified=0 problem={exc}")
        return 2
    problem = readback_error(published, submitted)
    print(f"{RECEIPT} comment={comment_id} bytes={len(published)} "
          f"verified={0 if problem else 1} problem={problem or 'none'}")
    return 1 if problem else 0


def selftest() -> int:
    checks = failures = 0

    def expect(label: str, ok: bool) -> None:
        nonlocal checks, failures
        checks += 1
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} {label}")

    expect("identical bytes verify", readback_error("a\nb", "a\nb") == "")
    expect("a changed line is reported with its number",
           "at line 2" in readback_error("a\nX", "a\nb"))
    expect("a truncated publication is reported",
           "line(s) where the submitted" in readback_error("a", "a\nb"))
    expect("an appended line is reported",
           "line(s) where the submitted" in readback_error("a\nb", "a"))
    expect("a line-ending-only difference is named, not normalized away",
           readback_error("a\r\nb", "a\nb") == "published body differs only in line endings")
    expect("a trailing newline is normalized, because GitHub does not store one",
           readback_error("a\nb", "a\nb\n") == "")
    expect("several trailing newlines are normalized the same way",
           readback_error("a\nb", "a\nb\n\n\n") == "")
    expect("an interior blank line is still part of the body",
           readback_error("a\n\nb", "a\nb") != "")
    expect("trailing spaces are not whitespace to be normalized away",
           readback_error("a\nb ", "a\nb") != "")

    class Done:
        def __init__(self, returncode, stdout, stderr=""):
            self.returncode, self.stdout, self.stderr = returncode, stdout, stderr

    def ok_runner(argv, **kwargs):
        return Done(0, "posted body\n")

    def broken_runner(argv, **kwargs):
        return Done(1, "", "gh: Not Found (HTTP 404)")

    expect("the transport's trailing newline is stripped, not the body's content",
           fetch_comment_body("o/r", "1", runner=ok_runner) == "posted body")
    transport_failed = False
    try:
        fetch_comment_body("o/r", "1", runner=broken_runner)
    except ValueError as exc:
        transport_failed = "Not Found" in str(exc)
    expect("a transport failure raises with its own diagnostic", transport_failed)

    import tempfile
    with tempfile.TemporaryDirectory(prefix="z-harness-readback-") as raw:
        body = Path(raw) / "body.md"
        body.write_text("posted body", encoding="utf-8")
        expect("a matching publication exits 0",
               verify("o/r", "1", body, runner=ok_runner) == 0)
        body.write_text("different body", encoding="utf-8")
        expect("a mismatched publication exits 1",
               verify("o/r", "1", body, runner=ok_runner) == 1)
        expect("an unreachable comment exits 2, never silently clean",
               verify("o/r", "1", body, runner=broken_runner) == 2)

    print(f"SELFTEST-SUMMARY suite=verify-handoff-comment checks={checks} "
          f"failures={failures}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo")
    parser.add_argument("--comment-id")
    parser.add_argument("--body-file", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv[1:] if argv else None)
    if args.selftest:
        return selftest()
    if not (args.repo and args.comment_id and args.body_file):
        parser.error("--repo, --comment-id and --body-file are required")
    return verify(args.repo, args.comment_id, args.body_file)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
