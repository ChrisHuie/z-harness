#!/usr/bin/env python3
"""Verify a document's local quotes and citations against exact source evidence.

Quotes pass only when ``[source: `<path>`]`` binds the extracted span to one uniquely
resolved cited file and the span is byte-identical to that file. A ``[elided]`` quote
passes when its byte-identical segments occur in source order. Case, whitespace, or
markdown-emphasis normalization is advisory and never clears.

A citation is a backticked token carrying a path separator or a known file extension.
A dotted prose identifier is not a citation, so the check does not manufacture blockers
on ordinary technical writing.

Citations pass only when a Claude Code or Codex transcript contains a direct read call,
a correlated successful result, and a path that resolves to the same file inside
``--root``. Shell mentions, writes, failed calls, and uncorrelated calls are reported but
never clear a citation. Paths the session really read that fall outside ``--root`` are
reported ``OUT_OF_ROOT`` -- scope, distinct from ``AMBIGUOUS`` doubt.

Exit codes: 0 verified · 1 findings, advisory-only matches, or inconclusive/vacuous
evidence · 2 usage or I/O error.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

VERSION = "3.0.0"
MIN_QUOTE_CHARS = 24
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fixtures", "claim-provenance")

# A citation is inferred from backticks, so the inferrer decides what the document is held
# to. Accepting any dotted token makes ordinary prose identifiers -- `client.decline`,
# `billing_measurement.vendor`, `v3.1.11` -- into citations that can never resolve, and a
# check that always reports blockers gets muted, which is the same end state as no check.
# A citation must therefore carry a path separator or a known file extension, and never
# whitespace. Extend CITATION_EXTENSIONS rather than loosening the shape.
CITATION_EXTENSIONS = (
    "c cc cfg conf cpp cs css csv env go graphql h hpp html ini java js json jsonl jsx kt "
    "lock lua m md mdx mjs php pl proto py pyi r rb rs rst scala sh sql svg swift toml ts "
    "tsx txt vue xml yaml yml zsh"
).split()
PATH_SEPARATED_CITATION = r"(?:[^`\s]*[\\/][^`\s]+)"
BARE_KNOWN_CITATION = (
    r"(?:[^`\s]+\.(?:" + "|".join(CITATION_EXTENSIONS) + r"))"
)
CITATION_TOKEN_PATTERN = (
    r"(?:" + PATH_SEPARATED_CITATION + r"|" + BARE_KNOWN_CITATION + r")"
)
PATH_IN_BACKTICKS = re.compile(r"`(" + CITATION_TOKEN_PATTERN + r")`")
CITATION_TOKEN = re.compile(r"^(?:" + CITATION_TOKEN_PATTERN + r")$")
PATH_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_])(?:[A-Za-z]:[\\/]|/|\.\.?/)?"
    r"[A-Za-z0-9_@.\\/\-]+\.[A-Za-z0-9]{1,16}"
)
QUOTED_SPAN_TEMPLATE = rb'(?P<elided>\[elided\]\s*)?\*"(?P<quote>[^\"]{%d,}?)"\*'
BOUND_QUOTED_SPAN_TEMPLATE = (
    rb'\[source:\s*`(?P<source>[^`\r\n]+)`\]\s*'
    rb'(?P<elided>\[elided\]\s*)?\*"(?P<quote>[^\"]{%d,}?)"\*'
)
UNWRAPPED_QUOTE = re.compile(r'(?<!\*)"[^"\n]{24,}"(?!\*)')
ELLIPSIS = re.compile(rb"\xe2\x80\xa6|\.\.\.")
EMPHASIS = re.compile(r"\*\*|\*|`")
WHITESPACE = re.compile(r"\s+")

CONFIRMED_READ = "CONFIRMED_READ"
HEURISTIC_TOUCH = "HEURISTIC_TOUCH"
FAILED_ATTEMPT = "FAILED_ATTEMPT"
OUT_OF_ROOT = "OUT_OF_ROOT"
AMBIGUOUS = "AMBIGUOUS"
UNSEEN = "UNSEEN"
# OUT_OF_ROOT is scope, not doubt: the session touched a real file that this --root cannot
# describe. Pooling it into AMBIGUOUS drowns genuine uncertainty -- on one real transcript it
# was 293 of 313 evidence rows -- and the EVIDENCE receipt is exactly what a reader uses to
# judge whether provenance was thin. Neither status clears a citation.
STATUSES = (CONFIRMED_READ, HEURISTIC_TOUCH, FAILED_ATTEMPT, OUT_OF_ROOT, AMBIGUOUS, UNSEEN)

READ_TOOLS = {"read", "read_file", "read_text_file", "readfile", "view_image"}
WRITE_TOOLS = {"write", "edit", "write_file", "apply_patch", "patch"}
SHELL_TOOLS = {"bash", "shell", "exec", "exec_command", "run_command"}
PATH_FIELDS = {"file_path", "path", "filename", "file"}


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _document_text(body):
    return body.decode("utf-8", errors="surrogateescape")


def cited_paths(doc_text):
    return sorted({path.strip() for path in PATH_IN_BACKTICKS.findall(doc_text)})


def _citation_token(value):
    return bool(CITATION_TOKEN.fullmatch(value))


def _inside(candidate, root):
    try:
        return os.path.commonpath([candidate, root]) == root
    except ValueError:
        return False


def _root(root):
    resolved = os.path.realpath(root)
    if not os.path.isdir(resolved):
        return None, f"--root is not a readable directory: {root}"
    return resolved, None


def resolve_citation(path, root):
    """Resolve one citation without discarding directory identity.

    Qualified paths resolve only at that path. A bare basename is accepted only when it
    has exactly one in-root match. ``realpath`` containment rejects absolute, ``..``, and
    symlink escapes.
    """
    root_real, error = _root(root)
    if error:
        return None, "io", error
    # A trailing :line makes the token a location, not a file, and the path half may well
    # exist. Reporting it as a path that was not found is a false statement about the
    # repository. It is refused rather than stripped: stripping resolves the file and then
    # verifies nothing about the line, so a [source: `doc.md:1`] binding would pass against a
    # quote living on line 4 -- a binding that reads more precise while checking less.
    suffixed = re.fullmatch(r"(.+?):(\d+)", path)
    if suffixed and not os.path.exists(os.path.join(root, path)):
        return None, "malformed", (
            f"cited token {path!r} names a file and a line; a citation names a file, and "
            f"the line is not verified here. Cite {suffixed.group(1)!r} instead")
    portable = path.replace("\\", os.sep)
    qualified = os.path.isabs(portable) or os.sep in portable
    if qualified:
        candidate = os.path.realpath(
            portable if os.path.isabs(portable) else os.path.join(root_real, portable)
        )
        if not _inside(candidate, root_real):
            return None, "outside", f"cited path escapes --root: {path}"
        if not os.path.isfile(candidate):
            return None, "missing", f"cited path not found under --root: {path}"
        return candidate, "resolved", None

    matches = []
    outside = []
    for dirpath, dirs, files in os.walk(root_real, followlinks=False):
        dirs.sort()
        if portable not in files:
            continue
        candidate = os.path.realpath(os.path.join(dirpath, portable))
        (matches if _inside(candidate, root_real) else outside).append(candidate)
    matches = sorted(set(matches))
    if len(matches) == 1:
        return matches[0], "resolved", None
    if len(matches) > 1:
        shown = ", ".join(os.path.relpath(item, root_real) for item in matches[:4])
        return None, "ambiguous", f"ambiguous cited basename: {path} -> {shown}"
    if outside:
        return None, "outside", f"cited basename resolves outside --root: {path}"
    return None, "missing", f"cited path not found under --root: {path}"


def _advisory_normalize(text):
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return WHITESPACE.sub(" ", EMPHASIS.sub("", text)).strip().casefold()


def _ordered(segments, body, transform=lambda value: value):
    cursor = 0
    haystack = transform(body)
    for segment in segments:
        needle = transform(segment)
        index = haystack.find(needle, cursor)
        if index < 0:
            return False
        cursor = index + len(needle)
    return True


def check_quotes(doc_path, root, min_quote=MIN_QUOTE_CHARS):
    doc = read_bytes(doc_path)
    if doc is None:
        return None, [f"cannot read document: {doc_path}"]
    root_real, error = _root(root)
    if error:
        return None, [error]

    corpus = {}
    resolution_findings = []
    quoted_span = re.compile(QUOTED_SPAN_TEMPLATE % min_quote)
    bound_span = re.compile(BOUND_QUOTED_SPAN_TEMPLATE % min_quote)
    bindings = {match.span("quote"): match for match in bound_span.finditer(doc)}
    findings = []
    advisories = []
    checked = compared = verified = 0
    for match in quoted_span.finditer(doc):
        raw = match.group("quote")
        checked += 1
        binding = bindings.get(match.span("quote"))
        if binding is None:
            findings.append(
                "UNBOUND_SOURCE quote lacks explicit source binding [source: `<path>`]: "
                + repr(raw[:90])
            )
            continue
        cited = _document_text(binding.group("source")).strip()
        if not _citation_token(cited):
            findings.append(
                f"quote source is not a path-separated or known-extension citation: {cited}"
            )
            continue
        if cited not in corpus:
            full, state, detail = resolve_citation(cited, root_real)
            if state != "resolved":
                resolution_findings.append(detail)
                corpus[cited] = (None, None)
                continue
            body = read_bytes(full)
            if body is None:
                return None, [f"cannot read cited file: {full}"]
            corpus[cited] = (full, body)
        _full, body = corpus[cited]
        if body is None:
            continue
        if ELLIPSIS.search(raw):
            if not match.group("elided"):
                findings.append(
                    "ellipsis is not verification syntax without a preceding [elided] label: "
                    + repr(raw[:90])
                )
                continue
            segments = ELLIPSIS.split(raw)
            if not segments or any(not segment.strip() for segment in segments):
                findings.append("invalid [elided] quote: every segment must be non-empty")
                continue
            compared += len(segments)
            if _ordered(segments, body):
                verified += 1
            elif _ordered(segments, body, _advisory_normalize):
                advisories.append(
                    f"NORMALIZED_ONLY ordered elision in {cited}; case, whitespace, or "
                    f"emphasis differs: {raw[:90]!r}"
                )
            else:
                findings.append(
                    f"unmatched or out-of-order [elided] quote in {cited}: {raw[:90]!r}"
                )
            continue

        compared += 1
        if raw in body:
            verified += 1
        elif _advisory_normalize(raw) in _advisory_normalize(body):
            advisories.append(
                f"NORMALIZED_ONLY quote in {cited}; case, whitespace, or emphasis differs: "
                f"{raw[:90]!r}"
            )
        else:
            findings.append(f"unmatched exact quote in {cited}: {raw[:90]!r}")

    return {
        "checked": checked,
        "compared": compared,
        "verified": verified,
        "files": len({full for full, _body in corpus.values() if full is not None}),
        "resolution_findings": resolution_findings,
        "findings": findings,
        "advisories": advisories,
        "skipped": len(UNWRAPPED_QUOTE.findall(_document_text(doc))),
        "vacuous": checked == 0 or compared == 0,
    }, []


def _tool_kind(name):
    base = name.casefold().rsplit(".", 1)[-1] if isinstance(name, str) else ""
    if base in READ_TOOLS:
        return "read"
    if base in WRITE_TOOLS:
        return "write"
    if base in SHELL_TOOLS:
        return "shell"
    return "unknown"


def _structured_paths(value, parent=None):
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in PATH_FIELDS and isinstance(child, str):
                found.append(child)
            else:
                found.extend(_structured_paths(child, key))
    elif isinstance(value, list):
        for child in value:
            found.extend(_structured_paths(child, parent))
    return found


def _shell_paths(value):
    if not isinstance(value, str):
        return []
    return PATH_TOKEN.findall(value)


def _arguments(payload):
    for key in ("arguments", "input"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value, json.dumps(value, sort_keys=True)
        if not isinstance(value, str):
            continue
        try:
            parsed = json.loads(value)
        except ValueError:
            parsed = None
        return parsed, value
    return {}, ""


def _result_failed(result):
    if not isinstance(result, dict):
        return True
    if result.get("is_error") is True or result.get("isError") is True:
        return True
    if result.get("error") not in (None, "", False):
        return True
    if str(result.get("status", "")).casefold() in {"error", "failed", "cancelled"}:
        return True
    # An explicit success flag is authoritative. Runtimes are inconsistent about emitting
    # it -- a real Claude session carried is_error on 125 of 203 tool results -- so the
    # text heuristics below still run whenever no explicit signal is present.
    if result.get("is_error") is False or result.get("isError") is False:
        return False
    output = result.get("output", result.get("content", ""))

    def flatten(value):
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            if value.get("isError") is True or value.get("is_error") is True:
                return "ERROR: flagged result"
            return " ".join(flatten(child) for child in value.values())
        if isinstance(value, list):
            return " ".join(flatten(child) for child in value)
        return ""

    text = flatten(output).strip()
    # Both patterns are anchored to the start. A read's payload IS the cited file's contents,
    # so an unanchored search reports a successful read as a failure whenever the file itself
    # discusses a missing-file error -- which is exactly the error-handling source most likely
    # to be cited. A failing result leads with its error; a source file does not.
    return bool(re.match(r"(?is)^(?:error|failed|exception)\s*:", text)
                or re.match(r"(?is)^\s*(?:no such file|file does not exist)", text))


def _resolve_tool_path(raw_path, cwd, root):
    """-> (resolved, code, detail). `code` distinguishes out-of-scope from unknown."""
    root_real, error = _root(root)
    if error:
        return None, "io", error
    portable = raw_path.replace("\\", os.sep)
    if os.path.isabs(portable):
        candidate = os.path.realpath(portable)
    else:
        if not cwd:
            return None, "no_cwd", "relative tool path has no recorded cwd"
        base = cwd if os.path.isabs(cwd) else os.path.join(root_real, cwd)
        candidate = os.path.realpath(os.path.join(base, portable))
    if not _inside(candidate, root_real):
        return None, "outside", "tool path resolves outside --root"
    return candidate, None, None


def _make_call(runtime, call_id, name, args, raw_blob, cwd):
    operation = _tool_kind(name)
    if operation == "shell":
        paths = _shell_paths(raw_blob)
    else:
        paths = _structured_paths(args)
    return {
        "runtime": runtime,
        "call_id": call_id,
        "name": name or "<unnamed>",
        "operation": operation,
        "paths": sorted(set(paths)),
        "cwd": cwd if isinstance(cwd, str) else None,
    }


def _finish_call(call, result, root, evidence):
    failed = result is None or _result_failed(result)
    for raw_path in call["paths"]:
        resolved, path_code, path_error = _resolve_tool_path(raw_path, call["cwd"], root)
        if result is None:
            status, detail = AMBIGUOUS, "call has no correlated result"
        elif failed:
            status, detail = FAILED_ATTEMPT, "correlated result reports failure"
        elif path_code == "outside":
            status, detail = OUT_OF_ROOT, path_error
        elif path_error:
            status, detail = AMBIGUOUS, path_error
        elif call["operation"] == "read":
            status, detail = CONFIRMED_READ, "direct read with successful correlated result"
        elif call["operation"] in {"shell", "write"}:
            status = HEURISTIC_TOUCH
            detail = f"successful {call['operation']} is not proof of a read"
        else:
            status, detail = AMBIGUOUS, "tool semantics are not classified as a direct read"
        evidence.append({
            "raw_path": raw_path,
            "resolved_path": resolved,
            "cwd": call["cwd"],
            "runtime": call["runtime"],
            "operation": call["operation"],
            "tool": call["name"],
            "call_id": call["call_id"],
            "status": status,
            "detail": detail,
        })


def transcript_evidence(transcript_path, root):
    """Parse real Claude/Codex call-result pairs into typed path evidence."""
    try:
        fh = open(transcript_path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return None, [f"cannot read transcript: {transcript_path}"]

    pending = {}
    evidence = []
    runtime_calls = {"claude-code": 0, "codex": 0}
    total_records = malformed_records = unmatched_results = duplicate_calls = 0
    codex_cwd = None
    with fh:
        for line in fh:
            if not line.strip():
                continue
            total_records += 1
            try:
                record = json.loads(line)
            except ValueError:
                malformed_records += 1
                continue
            if not isinstance(record, dict):
                malformed_records += 1
                continue
            record_type = record.get("type")
            if record_type is not None and not isinstance(record_type, str):
                malformed_records += 1
                continue

            raw_payload = record.get("payload")
            if raw_payload is None:
                payload = {}
            elif isinstance(raw_payload, dict):
                payload = raw_payload
            else:
                malformed_records += 1
                continue
            raw_message = record.get("message")
            if raw_message is None:
                message = {}
            elif isinstance(raw_message, dict):
                message = raw_message
            else:
                malformed_records += 1
                continue
            record_cwd = record.get("cwd")
            if record_cwd is not None and not isinstance(record_cwd, str):
                malformed_records += 1
                continue
            if record_type in {"turn_context", "session_meta"}:
                candidate_cwd = payload.get("cwd")
                if isinstance(candidate_cwd, str):
                    codex_cwd = candidate_cwd
                elif candidate_cwd is not None:
                    malformed_records += 1
                    continue

            content = message.get("content")
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use":
                        runtime_calls["claude-code"] += 1
                        call_id = block.get("id")
                        if not isinstance(call_id, str):
                            malformed_records += 1
                            continue
                        if call_id in pending:
                            duplicate_calls += 1
                            _finish_call(pending.pop(call_id), None, root, evidence)
                        raw_args = block.get("input", {})
                        if not isinstance(raw_args, dict):
                            malformed_records += 1
                            continue
                        args = raw_args
                        pending[call_id] = _make_call(
                            "claude-code", call_id, block.get("name"), args,
                            json.dumps(args, sort_keys=True), record_cwd
                        )
                    elif block.get("type") == "tool_result":
                        call_id = block.get("tool_use_id")
                        if not isinstance(call_id, str):
                            malformed_records += 1
                            continue
                        call = pending.pop(call_id, None)
                        if call is None:
                            unmatched_results += 1
                        else:
                            _finish_call(call, block, root, evidence)

            if record_type != "response_item":
                continue
            kind = payload.get("type")
            if kind is not None and not isinstance(kind, str):
                malformed_records += 1
                continue
            if kind in {"function_call", "custom_tool_call"}:
                runtime_calls["codex"] += 1
                call_id = payload.get("call_id")
                if not isinstance(call_id, str):
                    malformed_records += 1
                    continue
                if call_id in pending:
                    duplicate_calls += 1
                    _finish_call(pending.pop(call_id), None, root, evidence)
                args, raw_blob = _arguments(payload)
                pending[call_id] = _make_call(
                    "codex", call_id, payload.get("name"), args, raw_blob, codex_cwd
                )
            elif kind in {"function_call_output", "custom_tool_call_output"}:
                call_id = payload.get("call_id")
                if not isinstance(call_id, str):
                    malformed_records += 1
                    continue
                call = pending.pop(call_id, None)
                if call is None:
                    unmatched_results += 1
                else:
                    _finish_call(call, payload, root, evidence)

    for call in pending.values():
        _finish_call(call, None, root, evidence)

    active = [runtime for runtime, count in runtime_calls.items() if count]
    runtime = active[0] if len(active) == 1 else ("mixed" if active else None)
    counts = {status: 0 for status in STATUSES}
    for item in evidence:
        counts[item["status"]] += 1
    return {
        "evidence": evidence,
        "runtime": runtime,
        "runtime_calls": runtime_calls,
        "calls": sum(runtime_calls.values()),
        "total_records": total_records,
        "malformed_records": malformed_records,
        "unmatched_results": unmatched_results,
        "duplicate_calls": duplicate_calls,
        "status_counts": counts,
    }, []


def _raw_path_may_name(raw_path, cited):
    raw = os.path.normpath(raw_path.replace("\\", os.sep))
    target = os.path.normpath(cited.replace("\\", os.sep))
    if os.sep in target or os.path.isabs(target):
        return raw == target or raw.endswith(os.sep + target)
    return os.path.basename(raw) == target


def check_citations(doc_path, transcript_path, root):
    doc = read_text(doc_path)
    if doc is None:
        return None, [f"cannot read document: {doc_path}"]
    report, errors = transcript_evidence(transcript_path, root)
    if report is None:
        return None, errors

    findings = []
    cited = cited_paths(doc)
    for rel in cited:
        resolved, state, detail = resolve_citation(rel, root)
        if state != "resolved":
            findings.append(detail)
            continue
        matching = [item for item in report["evidence"]
                    if item["resolved_path"] == resolved]
        if any(item["status"] == CONFIRMED_READ for item in matching):
            continue
        if not matching:
            matching = [item for item in report["evidence"]
                        if _raw_path_may_name(item["raw_path"], rel)]
        observed = sorted({item["status"] for item in matching}) or [UNSEEN]
        findings.append(
            f"citation not confirmed by a successful direct read: {rel} "
            f"(evidence: {', '.join(observed)})"
        )

    if report["malformed_records"]:
        findings.append(
            f"transcript contains {report['malformed_records']} malformed record(s); "
            "provenance is incomplete"
        )
    if report["unmatched_results"]:
        findings.append(
            f"transcript contains {report['unmatched_results']} result(s) without a call"
        )
    if report["duplicate_calls"]:
        findings.append(
            f"transcript reuses {report['duplicate_calls']} call id(s); correlation is ambiguous"
        )
    return {
        "cited": len(cited),
        "findings": findings,
        "report": report,
        "vacuous": len(cited) == 0 or report["calls"] == 0,
    }, []


def selftest():
    """Exercise real-format fixtures and CLI boundaries, including red cases."""
    results = []

    def record(label, ok):
        results.append((label, bool(ok)))

    def invoke(*args):
        return subprocess.run(
            [sys.executable, os.path.abspath(__file__), *args],
            capture_output=True, text=True, timeout=10,
        )

    with tempfile.TemporaryDirectory() as tmp:
        schemas = os.path.join(tmp, "schemas")
        os.makedirs(schemas)
        source = "A binding reporting contract protects ordered evidence"
        with open(os.path.join(schemas, "order.json"), "w", encoding="utf-8") as fh:
            fh.write(source)

        # A file-and-line token is refused with a diagnosis naming the reason. It previously
        # reported the path as not found, which is false whenever the file half exists, and
        # accepting it by stripping the suffix would verify the file while claiming a line.
        _suffix_target = os.path.join(schemas, "order.json")
        _, _suffix_state, _suffix_detail = resolve_citation("schemas/order.json:1", tmp)
        record("a file-and-line citation is refused",
               _suffix_state != "resolved")
        record("the refusal names the line suffix rather than a missing path",
               _suffix_detail is not None
               and "names a file and a line" in _suffix_detail
               and "not found" not in _suffix_detail)
        record("the unsuffixed form of the same citation still resolves",
               resolve_citation("schemas/order.json", tmp)[1] == "resolved")

        def document(name, text):
            path = os.path.join(tmp, name)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            return path

        def document_bytes(name, body):
            path = os.path.join(tmp, name)
            with open(path, "wb") as fh:
                fh.write(body)
            return path

        exact = document(
            "exact.md", f'[source: `schemas/order.json`] *"{source}"*.'
        )
        run = invoke("--quotes", exact, "--root", tmp)
        record("exact quote clears", run.returncode == 0 and "verified=1" in run.stdout)

        bound = document(
            "bound.md", f'[source: `schemas/order.json`] *"{source}"*.'
        )
        run = invoke("--quotes", bound, "--root", tmp)
        record("explicit source binding clears",
               run.returncode == 0 and "verified=1" in run.stdout)
        unbound = document(
            "unbound.md", f'`schemas/order.json` says *"{source}"*.'
        )
        run = invoke("--quotes", unbound, "--root", tmp)
        record("quote without explicit source binding goes red",
               run.returncode == 1 and "explicit source binding" in run.stdout)

        other_source = "A different source contains this otherwise exact quotation"
        with open(os.path.join(schemas, "other.txt"), "w", encoding="utf-8") as fh:
            fh.write(other_source)
        wrong_source = document(
            "wrong-source.md",
            f'[source: `schemas/order.json`] *"{other_source}"*. '
            "The comparison source is `schemas/other.txt`.",
        )
        run = invoke("--quotes", wrong_source, "--root", tmp)
        record("quote cannot clear against a separately cited source",
               run.returncode == 1 and "schemas/order.json" in run.stdout)

        crlf_source = b"A first source line with enough bytes\r\nA second source line stays distinct"
        with open(os.path.join(schemas, "crlf.txt"), "wb") as fh:
            fh.write(crlf_source)
        crlf_doc = document_bytes(
            "crlf.md",
            b'[source: `schemas/crlf.txt`] *"A first source line with enough bytes\n'
            b'A second source line stays distinct"*.',
        )
        run = invoke("--quotes", crlf_doc, "--root", tmp)
        record("CRLF and LF quotes are not byte-identical", run.returncode == 1)

        invalid_source = b"An invalid byte \xff must not equal a different invalid byte in evidence"
        with open(os.path.join(schemas, "invalid.bin"), "wb") as fh:
            fh.write(invalid_source)
        invalid_doc = document_bytes(
            "invalid.md",
            b'[source: `schemas/invalid.bin`] *"An invalid byte \xfe must not equal a '
            b'different invalid byte in evidence"*.',
        )
        run = invoke("--quotes", invalid_doc, "--root", tmp)
        record("replacement decoding cannot manufacture byte identity", run.returncode == 1)

        fabricated = document(
            "fabricated.md",
            '[source: `schemas/order.json`] '
            '*"A legally binding settlement guarantee exists"*.'
        )
        record("fabricated quote goes red",
               invoke("--quotes", fabricated, "--root", tmp).returncode == 1)

        for label, quote in (
            ("case-only quote does not clear", source.lower()),
            ("whitespace-only quote does not clear", source.replace(" ", "  ")),
        ):
            path = document(label.replace(" ", "-") + ".md",
                            f'[source: `schemas/order.json`] *"{quote}"*.')
            run = invoke("--quotes", path, "--root", tmp)
            record(label, run.returncode == 1 and "NORMALIZED_ONLY" in run.stdout)

        emphasis_source = os.path.join(schemas, "emphasis.md")
        with open(emphasis_source, "w", encoding="utf-8") as fh:
            fh.write("A binding **reporting** contract protects ordered evidence")
        emphasis = document(
            "emphasis.md",
            '[source: `schemas/emphasis.md`] '
            '*"A binding reporting contract protects ordered evidence"*.'
        )
        run = invoke("--quotes", emphasis, "--root", tmp)
        record("emphasis-normalized quote does not clear",
               run.returncode == 1 and "NORMALIZED_ONLY" in run.stdout)

        ordered = document(
            "ordered.md",
            '[source: `schemas/order.json`] '
            '[elided] *"A binding reporting … ordered evidence"*.'
        )
        record("labeled ordered elision clears",
               invoke("--quotes", ordered, "--root", tmp).returncode == 0)
        reversed_elision = document(
            "reversed.md",
            '[source: `schemas/order.json`] '
            '[elided] *"ordered evidence … A binding reporting"*.'
        )
        record("reversed elision goes red",
               invoke("--quotes", reversed_elision, "--root", tmp).returncode == 1)
        unlabeled = document(
            "unlabeled.md",
            '[source: `schemas/order.json`] '
            '*"A binding reporting … ordered evidence"*.'
        )
        run = invoke("--quotes", unlabeled, "--root", tmp)
        record("unlabeled elision goes red",
               run.returncode == 1 and "without a preceding [elided]" in run.stdout)
        empty_elision = document(
            "empty-elision.md",
            '[source: `schemas/order.json`] [elided] *"... ... ..."*.',
        )
        record("zero-segment elision goes red",
               invoke("--quotes", empty_elision, "--root", tmp,
                      "--min-quote", "5").returncode == 1)

        no_quotes = document("no-quotes.md", "See `schemas/order.json` for the contract.")
        run = invoke("--quotes", no_quotes, "--root", tmp)
        record("zero extracted quotes are vacuous",
               run.returncode == 1 and "VACUOUS" in run.stdout)

        os.makedirs(os.path.join(schemas, "v1"))
        os.makedirs(os.path.join(schemas, "v2"))
        with open(os.path.join(schemas, "v1", "order.json"), "w", encoding="utf-8") as fh:
            fh.write("A version one quotation that must not cross directories")
        with open(os.path.join(schemas, "v2", "order.json"), "w", encoding="utf-8") as fh:
            fh.write("A version two quotation with different exact contents")
        wrong_version = document(
            "wrong-version.md",
            '[source: `schemas/v2/order.json`] '
            '*"A version one quotation that must not cross directories"*.'
        )
        record("qualified citation cannot fall back to another basename",
               invoke("--quotes", wrong_version, "--root", tmp).returncode == 1)
        ambiguous = document(
            "ambiguous.md",
            '[source: `order.json`] '
            '*"A binding reporting contract protects ordered evidence"*.',
        )
        run = invoke("--quotes", ambiguous, "--root", tmp)
        record("ambiguous bare basename goes red",
               run.returncode == 1 and "ambiguous cited basename" in run.stdout)

        with tempfile.TemporaryDirectory() as outside:
            outside_file = os.path.join(outside, "outside.json")
            with open(outside_file, "w", encoding="utf-8") as fh:
                fh.write(source)
            absolute = document(
                "absolute.md", f'[source: `{outside_file}`] *"{source}"*.'
            )
            run = invoke("--quotes", absolute, "--root", tmp)
            record("absolute path outside root goes red",
                   run.returncode == 1 and "escapes --root" in run.stdout)
            traversal = document(
                "traversal.md",
                f'[source: `../{os.path.basename(outside)}/outside.json`] *"{source}"*.',
            )
            record("dot-dot escape goes red",
                   invoke("--quotes", traversal, "--root", tmp).returncode == 1)
            link = os.path.join(schemas, "linked.json")
            try:
                os.symlink(outside_file, link)
                linked = document(
                    "linked.md", f'[source: `schemas/linked.json`] *"{source}"*.'
                )
                run = invoke("--quotes", linked, "--root", tmp)
                record("symlink escape goes red",
                       run.returncode == 1 and "escapes --root" in run.stdout)
            except OSError:
                record("symlink escape goes red", True)

        citation_doc = document("citation.md", "See `schemas/order.json`.")
        for runtime, fixture in (
            ("claude", "claude-read-success.jsonl"),
            ("codex", "codex-read-success.jsonl"),
        ):
            run = invoke("--citations", citation_doc, "--root", tmp, "--transcript",
                         os.path.join(FIXTURES, fixture))
            record(f"{runtime} successful correlated read clears",
                   run.returncode == 0 and "CONFIRMED_READ=1" in run.stdout)

        os.makedirs(os.path.join(tmp, "docs"))
        with open(os.path.join(tmp, "docs", "Makefile"), "w", encoding="utf-8") as fh:
            fh.write("all:\n\t@true\n")
        extensionless = document(
            "extensionless.md", "See `schemas/order.json` and `docs/Makefile`."
        )
        run = invoke("--citations", extensionless, "--root", tmp, "--transcript",
                     os.path.join(FIXTURES, "claude-read-success.jsonl"))
        record("path-separated extensionless citations are checked",
               run.returncode == 1 and "cited=2" in run.stdout
               and "docs/Makefile" in run.stdout)

        run = invoke("--quotes", bound, "--root", tmp)
        record("quotes-only success receipt stays in scope",
               run.returncode == 0
               and "successful correlated direct read" not in run.stdout)
        run = invoke("--citations", citation_doc, "--root", tmp, "--transcript",
                     os.path.join(FIXTURES, "claude-read-success.jsonl"))
        record("citations-only success receipt stays in scope",
               run.returncode == 0 and "extracted quotes" not in run.stdout)

        for label, fixture, status in (
            ("failed read does not clear", "claude-read-failed.jsonl", FAILED_ATTEMPT),
            ("write-only access does not clear", "claude-write-success.jsonl", HEURISTIC_TOUCH),
            ("shell path sighting does not clear", "codex-shell-success.jsonl", HEURISTIC_TOUCH),
        ):
            run = invoke("--citations", citation_doc, "--root", tmp, "--transcript",
                         os.path.join(FIXTURES, fixture))
            record(label, run.returncode == 1 and status in run.stdout)

        wrong_citation = document("wrong-citation.md", "See `schemas/v2/order.json`.")
        run = invoke("--citations", wrong_citation, "--root", tmp, "--transcript",
                     os.path.join(FIXTURES, "claude-read-success.jsonl"))
        record("same basename in another directory does not clear",
               run.returncode == 1 and UNSEEN in run.stdout)

        # A read's payload is the cited file's own contents. Error-shaped prose inside a
        # legitimately-read source file must not be read as a failed call, including when the
        # runtime omits an explicit success flag -- real transcripts omit it on many results.
        error_prose = os.path.join(schemas, "loader.py")
        with open(error_prose, "w", encoding="utf-8") as fh:
            fh.write('def load(p):\n    # raises when there is no such file at p\n    ...\n')
        prose_doc = document("prose.md", "See `schemas/loader.py`.")
        for label, extra in (("with is_error false", {"is_error": False}),
                             ("without an explicit flag", {})):
            unflagged = document(
                f"unflagged-{len(extra)}.jsonl",
                "\n".join([
                    json.dumps({"type": "assistant", "cwd": tmp, "message": {"content": [
                        {"type": "tool_use", "id": "prose", "name": "Read",
                         "input": {"file_path": error_prose}}]}}),
                    json.dumps({"type": "user", "cwd": tmp, "message": {"content": [
                        dict({"type": "tool_result", "tool_use_id": "prose",
                              "content": read_text(error_prose)}, **extra)]}}),
                ]) + "\n",
            )
            run = invoke("--citations", prose_doc, "--root", tmp, "--transcript", unflagged)
            record(f"file content naming a missing-file error still clears ({label})",
                   run.returncode == 0 and "CONFIRMED_READ=1" in run.stdout)

        leading_error = "Error: this is literal source content, not a failed tool call"
        with open(os.path.join(schemas, "leading-error.txt"), "w", encoding="utf-8") as fh:
            fh.write(leading_error)
        leading_error_doc = document(
            "leading-error.md", "See `schemas/leading-error.txt`."
        )
        for label, extra, expected_code, expected_status in (
            ("explicit success", {"is_error": False}, 0, CONFIRMED_READ),
            ("no success flag", {}, 1, FAILED_ATTEMPT),
        ):
            leading_error_transcript = document(
                f"leading-error-{len(extra)}.jsonl",
                "\n".join([
                    json.dumps({"type": "assistant", "cwd": tmp, "message": {"content": [
                        {"type": "tool_use", "id": "leading-error", "name": "Read",
                         "input": {"file_path": os.path.join(schemas, "leading-error.txt")}}
                    ]}}),
                    json.dumps({"type": "user", "cwd": tmp, "message": {"content": [
                        dict({"type": "tool_result", "tool_use_id": "leading-error",
                              "content": leading_error}, **extra)
                    ]}}),
                ]) + "\n",
            )
            run = invoke("--citations", leading_error_doc, "--root", tmp,
                         "--transcript", leading_error_transcript)
            record(f"leading Error text respects {label}",
                   run.returncode == expected_code and expected_status in run.stdout)

        # A dotted prose identifier is not a citation; treating it as one guarantees a
        # blocker on any technical document, and a check that always fails gets muted.
        identifiers = document(
            "identifiers.md",
            "The field `billing_measurement.vendor` at `v3.1.11` calls `client.decline`.",
        )
        run = invoke("--citations", identifiers, "--root", tmp, "--transcript",
                     os.path.join(FIXTURES, "claude-read-success.jsonl"))
        record("dotted prose identifiers are not citations",
               "cited=0" in run.stdout and "not found under --root" not in run.stdout)

        # Scope is not doubt: a real file the root cannot describe is OUT_OF_ROOT.
        with tempfile.TemporaryDirectory() as elsewhere:
            far = os.path.join(elsewhere, "far.json")
            with open(far, "w", encoding="utf-8") as fh:
                fh.write(source)
            far_transcript = document(
                "far.jsonl",
                "\n".join([
                    json.dumps({"type": "assistant", "cwd": tmp, "message": {"content": [
                        {"type": "tool_use", "id": "far", "name": "Read",
                         "input": {"file_path": far}}]}}),
                    json.dumps({"type": "user", "cwd": tmp, "message": {"content": [
                        {"type": "tool_result", "tool_use_id": "far",
                         "content": source, "is_error": False}]}}),
                ]) + "\n",
            )
            run = invoke("--citations", citation_doc, "--root", tmp,
                         "--transcript", far_transcript)
            record("path outside the root is scoped, not ambiguous",
                   f"{OUT_OF_ROOT}=1" in run.stdout and f"{AMBIGUOUS}=0" in run.stdout)

        relative_transcript = document(
            "relative.jsonl",
            '\n'.join([
                json.dumps({"type": "assistant", "cwd": "nested", "message": {
                    "content": [{"type": "tool_use", "id": "relative", "name": "Read",
                                 "input": {"file_path": "../schemas/order.json"}}]}}),
                json.dumps({"type": "user", "cwd": "nested", "message": {
                    "content": [{"type": "tool_result", "tool_use_id": "relative",
                                 "content": source, "is_error": False}]}}),
            ]) + '\n'
        )
        record("relative path uses recorded cwd",
               invoke("--citations", citation_doc, "--root", tmp,
                      "--transcript", relative_transcript).returncode == 0)

        malformed = document(
            "malformed.jsonl",
            read_text(os.path.join(FIXTURES, "claude-read-success.jsonl")) + "{truncated\n"
        )
        run = invoke("--citations", citation_doc, "--root", tmp, "--transcript", malformed)
        record("malformed transcript goes red",
               run.returncode == 1 and "malformed record" in run.stdout)
        wrong_shapes = document(
            "wrong-shapes.jsonl",
            read_text(os.path.join(FIXTURES, "claude-read-success.jsonl"))
            + json.dumps({"type": "turn_context", "payload": [{"cwd": tmp}]}) + "\n"
            + json.dumps({"type": "assistant", "message": [{"content": []}]}) + "\n"
            + json.dumps({"type": [], "message": {"content": []}}) + "\n"
            + json.dumps({"type": "response_item", "payload": {"type": []}}) + "\n",
        )
        run = invoke("--citations", citation_doc, "--root", tmp,
                     "--transcript", wrong_shapes)
        record("valid JSON with wrong record shapes is inconclusive, not a crash",
               run.returncode == 1 and "malformed=4" in run.stdout
               and "malformed record" in run.stdout)
        pending = document(
            "pending.jsonl",
            json.dumps({"type": "assistant", "cwd": ".", "message": {"content": [{
                "type": "tool_use", "id": "pending", "name": "Read",
                "input": {"file_path": "schemas/order.json"}
            }]}}) + "\n"
        )
        run = invoke("--citations", citation_doc, "--root", tmp, "--transcript", pending)
        record("uncorrelated read request goes red",
               run.returncode == 1 and AMBIGUOUS in run.stdout)
        empty = document("empty.jsonl", "")
        run = invoke("--citations", citation_doc, "--root", tmp, "--transcript", empty)
        record("zero-record transcript is vacuous",
               run.returncode == 1 and "VACUOUS" in run.stdout)
        no_citations = document("no-citations.md", "No local paths are cited.")
        run = invoke("--citations", no_citations, "--root", tmp, "--transcript",
                     os.path.join(FIXTURES, "claude-read-success.jsonl"))
        record("zero citations are vacuous",
               run.returncode == 1 and "VACUOUS" in run.stdout)
        record("I/O errors exit two",
               invoke("--quotes", os.path.join(tmp, "missing.md"),
                      "--root", tmp).returncode == 2)

    failed = sum(not ok for _label, ok in results)
    print("selftest")
    for label, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    print(f"SELFTEST-SUMMARY suite=claim-provenance checks={len(results)} failures={failed}")
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify local quotes and citations using exact source evidence.",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--quotes", metavar="DOC")
    parser.add_argument("--citations", metavar="DOC")
    parser.add_argument("--root", default=".")
    parser.add_argument("--transcript")
    parser.add_argument("--min-quote", type=int, default=MIN_QUOTE_CHARS)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.quotes and not args.citations:
        parser.error("nothing to do: pass --quotes, --citations, or --selftest")
    if args.citations and not args.transcript:
        parser.error("--citations requires --transcript")
    if args.min_quote < 1:
        parser.error("--min-quote must be positive")
    _resolved_root, root_error = _root(args.root)
    if root_error:
        print(f"error: {root_error}", file=sys.stderr)
        return 2

    blockers = 0
    vacuous = False
    if args.quotes:
        result, errors = check_quotes(args.quotes, args.root, args.min_quote)
        if result is None:
            for error in errors:
                print(f"error: {error}", file=sys.stderr)
            return 2
        print(
            "quotes  "
            f"selected={result['checked']} compared_segments={result['compared']} "
            f"verified={result['verified']} cited_files={result['files']}"
        )
        for finding in result["resolution_findings"] + result["findings"]:
            print(f"  FAIL  {finding}")
        for advisory in result["advisories"]:
            print(f"  ADVISORY  {advisory}")
        if result["skipped"]:
            print(f"  NOTE  skipped_unwrapped_quotes={result['skipped']}")
        if result["vacuous"]:
            vacuous = True
            print("  VACUOUS  no quote/source comparison was possible; this is not verified")
        blockers += (len(result["resolution_findings"]) + len(result["findings"])
                     + len(result["advisories"]))
        print()

    if args.citations:
        result, errors = check_citations(args.citations, args.transcript, args.root)
        if result is None:
            for error in errors:
                print(f"error: {error}", file=sys.stderr)
            return 2
        report = result["report"]
        status_receipt = " ".join(
            f"{status}={report['status_counts'][status]}" for status in STATUSES
        )
        print(
            "citations  "
            f"cited={result['cited']} runtime={report['runtime'] or 'UNRECOGNISED'} "
            f"records={report['total_records']} malformed={report['malformed_records']} "
            f"calls={report['calls']} evidence={len(report['evidence'])}"
        )
        print(f"  EVIDENCE  {status_receipt}")
        for finding in result["findings"]:
            print(f"  FAIL  {finding}")
        if result["vacuous"]:
            vacuous = True
            print("  VACUOUS  zero citations or zero recognised calls; this is not verified")
        blockers += len(result["findings"])
        print()

    print(f"{blockers} blocker(s)")
    if vacuous:
        print("At least one check was VACUOUS. Treat it as unperformed.")
    elif blockers == 0:
        if args.quotes:
            print("Verified quotes: every selected quote has an explicit source binding and "
                  "is byte-exact or a labeled ordered elision.")
        if args.citations:
            print("Verified citations: every cited path has a successful correlated direct "
                  "read.")
    return 1 if blockers or vacuous else 0


if __name__ == "__main__":
    sys.exit(main())
