#!/usr/bin/env python3
"""claim-provenance — did the claims in this document actually touch their sources?

Two mechanical checks on a finished document. Neither reads the prose; both compare
what the document CITES against what exists on disk and what the session actually opened.

  claim-provenance.py --quotes findings/09.md --root ./src
        Every quoted span must appear in a file the document cites.

  claim-provenance.py --citations findings/09.md --transcript <session>.jsonl
        Every file the document cites must have been opened in that session.

  claim-provenance.py --quotes doc.md --citations doc.md --root . --transcript t.jsonl
        Both checks in one pass.

  claim-provenance.py --selftest
        Prove both detectors can go red. A detector that cannot fail proves nothing.

WHAT THIS CATCHES
  Fabricated or drifted quotations — text between quote marks that is not in the
  cited artifact, including a quote that was accurate before the artifact moved.
  Fabricated citations — a path cited by a document that the session never opened.

WHAT THIS DOES NOT CATCH, and the reason it is stated here rather than in a README:
  A claim that cites NOTHING. The motivating failure for this tool was the sentence
  "get_products takes a refine parameter" — a structural claim, written from a property
  name, citing no path. There is nothing for either check to key on. An unlinted
  document is not a grounded one; absence of findings here is not evidence of grounding.

TWO NORMALISATIONS, both of which trade precision for a usable false-positive rate:
  Quote matching collapses whitespace and strips markdown emphasis before comparing,
  because real quotes are line-wrapped in source. It is therefore NOT raw byte
  equality. Elided quotes (... or the ellipsis character) are split into segments and
  every segment must be found, in the file but not necessarily adjacent.
  Transcript path extraction reads Read/Edit/Write file_path directly, and greps Bash
  command text for path-shaped tokens. Shell access is the common case in this harness
  (measured on one session: 79 Bash vs 10 Read), so a Bash-only heuristic decides most
  of the answer. It can miss a path built by variable expansion, which produces a FALSE
  "never opened". Treat citation findings as leads, quote findings as facts.

Exit codes: 0 clean · 1 findings present or selftest failed · 2 usage error.
"""
import argparse
import glob
import json
import os
import re
import sys

VERSION = "1.0.0"

# A cited path: inside backticks, ending in a known extension. A bare filename counts —
# documents cite `product.json` as often as `schemas/core/product.json`, and dropping the
# bare form silently empties the corpus for whole sections.
PATH_IN_BACKTICKS = re.compile(r"`([A-Za-z0-9_./@\-]*[A-Za-z0-9_\-]+\.[A-Za-z0-9]{1,6})`")

# Quotations are extracted ONLY when markdown emphasis delimits them: *"..."* — including
# inside a blockquote, which still contains that shape.
#
# Why not plain "...": quote marks pair sequentially, so a naive [^"]+ between them captures
# the PROSE BETWEEN two real quotations just as readily as the quotations. On a document with
# an even number of quote marks, half of every match is inter-quote garbage, and each becomes
# a false "unmatched quote". Requiring *" to open and "* to close makes the pairing
# unambiguous. The cost is recall: an undelimited quotation is not checked, and the run
# reports how many it skipped so the gap is visible rather than assumed away.
MIN_QUOTE_CHARS = 24
QUOTED_SPAN_TEMPLATE = r'\*"([^"]{%d,}?)"\*'
UNWRAPPED_QUOTE = re.compile(r'(?<!\*)"[^"\n]{24,}"(?!\*)')
# Path-shaped tokens inside a shell command.
PATH_IN_SHELL = re.compile(r"[A-Za-z0-9_./@\-]*/[A-Za-z0-9_.\-]+\.[A-Za-z0-9]{1,6}")

ELLIPSIS = re.compile(r"…|\.\.\.")
EMPHASIS = re.compile(r"\*\*|\*|`")
WHITESPACE = re.compile(r"\s+")


def normalise(text):
    """Collapse wrapping and strip markdown so a wrapped quote can match its source."""
    return WHITESPACE.sub(" ", EMPHASIS.sub("", text)).strip()


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def cited_paths(doc_text):
    return sorted(set(PATH_IN_BACKTICKS.findall(doc_text)))


def resolve(path, root):
    """Every file beneath root that a cited path could denote.

    Returns a list because an artifact routinely vendors the same schema at several
    paths. Giving up on ambiguity — returning nothing when a basename matches more
    than once — empties the corpus for whole sections and turns real quotations into
    false 'unmatched' findings.
    """
    direct = os.path.join(root, path)
    if os.path.isfile(direct):
        return [direct]
    return [
        p
        for p in glob.glob(os.path.join(root, "**", os.path.basename(path)), recursive=True)
        if p.endswith(path) or os.path.basename(p) == os.path.basename(path)
    ]


def check_quotes(doc_path, root, min_quote=MIN_QUOTE_CHARS):
    doc = read_text(doc_path)
    if doc is None:
        return None, [f"cannot read document: {doc_path}"]
    quoted_span = re.compile(QUOTED_SPAN_TEMPLATE % min_quote)

    corpus = {}
    unresolved = []
    for rel in cited_paths(doc):
        hits = resolve(rel, root)
        if not hits:
            unresolved.append(rel)
            continue
        for full in hits:
            body = read_text(full)
            if body is not None:
                # Lowercased: quoting convention permits re-casing a fragment at a sentence
                # boundary, and flagging that as a fabricated quote is noise, not signal.
                corpus[full] = normalise(body).lower()

    findings = []
    checked = 0
    for raw in quoted_span.findall(doc):
        quote = normalise(raw)
        if not quote:
            continue
        checked += 1
        segments = [s.strip().lower() for s in ELLIPSIS.split(quote) if len(s.strip()) >= 12]
        if not segments:
            continue
        hit = any(all(seg in body for seg in segments) for body in corpus.values())
        if not hit:
            excerpt = quote if len(quote) <= 90 else quote[:87] + "..."
            findings.append(f'unmatched quote: "{excerpt}"')

    return {
        "checked": checked,
        "files": len(corpus),
        "unresolved": unresolved,
        "findings": findings,
        # Undelimited quotations the extractor deliberately skipped — recall loss, surfaced.
        "skipped": len(UNWRAPPED_QUOTE.findall(doc)),
        # A run that extracted nothing is not a clean run. Surfaced as its own state so a
        # matcher that selected nothing can never be read as an all-clear.
        "vacuous": checked == 0 or not corpus,
    }, []


def _paths_from_claude(record, opened):
    """Claude Code: {"message": {"content": [{"type": "tool_use", "input": {...}}]}}."""
    message = record.get("message") or {}
    content = message.get("content")
    if not isinstance(content, list):
        return False
    saw = False
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        saw = True
        args = block.get("input") or {}
        fp = args.get("file_path")
        if isinstance(fp, str):
            opened.add(fp)
        command = args.get("command")
        if isinstance(command, str):
            opened.update(PATH_IN_SHELL.findall(command))
    return saw


def _paths_from_codex(record, opened):
    """Codex: {"type": "response_item", "payload": {"type": "function_call"|"custom_tool_call"}}.

    function_call carries `arguments` as a JSON *string*; custom_tool_call carries `input`
    as free text (shell or JS). Both are scanned for path-shaped tokens, and arguments is
    additionally parsed so an explicit path value is taken structurally rather than by regex.
    """
    if record.get("type") != "response_item":
        return False
    payload = record.get("payload") or {}
    kind = payload.get("type")
    if kind not in ("function_call", "custom_tool_call"):
        return False
    for key in ("arguments", "input"):
        blob = payload.get(key)
        if not isinstance(blob, str):
            continue
        opened.update(PATH_IN_SHELL.findall(blob))
        try:
            parsed = json.loads(blob)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            for field in ("file_path", "path", "filename", "file"):
                value = parsed.get(field)
                if isinstance(value, str):
                    opened.add(value)
    return True


def transcript_paths(transcript_path):
    """Every file path a session demonstrably touched, across both runtimes.

    Returns (paths, runtime). Both extractors run on every record rather than sniffing the
    format up front: a detector that guesses wrong yields an empty set, and an empty set is
    indistinguishable from a session that opened nothing — the all-clear failure this tool
    exists to refuse.
    """
    opened = set()
    seen = {"claude-code": 0, "codex": 0}
    try:
        fh = open(transcript_path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return None, None
    with fh:
        for line in fh:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if _paths_from_claude(record, opened):
                seen["claude-code"] += 1
            if _paths_from_codex(record, opened):
                seen["codex"] += 1
    runtime = max(seen, key=lambda k: seen[k]) if any(seen.values()) else None
    return opened, runtime


def check_citations(doc_path, transcript_path):
    doc = read_text(doc_path)
    if doc is None:
        return None, [f"cannot read document: {doc_path}"]
    opened, runtime = transcript_paths(transcript_path)
    if opened is None:
        return None, [f"cannot read transcript: {transcript_path}"]

    findings = []
    cited = cited_paths(doc)
    for rel in cited:
        base = os.path.basename(rel)
        touched = any(rel in seen or seen.endswith(rel) or os.path.basename(seen) == base
                      for seen in opened)
        if not touched:
            findings.append(f"cited but never opened in this session: {rel}")
    return {
        "cited": len(cited),
        "opened": len(opened),
        "findings": findings,
        "runtime": runtime,
    }, []


def selftest():
    """Both detectors must go red on planted defects and stay green on clean input."""
    import tempfile

    results = []
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "schemas")
        os.makedirs(src)
        with open(os.path.join(src, "order.json"), "w") as fh:
            fh.write('{"title": "Order", "description": "A binding reporting contract"}')

        clean = os.path.join(tmp, "clean.md")
        with open(clean, "w") as fh:
            fh.write('See `schemas/order.json` — *"A binding reporting contract"* is the phrase.')
        planted = os.path.join(tmp, "planted.md")
        with open(planted, "w") as fh:
            fh.write('See `schemas/order.json` — *"A legally binding settlement guarantee"* it says.')

        got, _ = check_quotes(clean, tmp)
        results.append(("quotes stay green on a true quote",
                        bool(got and not got["findings"] and not got["vacuous"])))
        got, _ = check_quotes(planted, tmp)
        results.append(("quotes go red on a fabricated quote", bool(got and got["findings"])))

        # The defect this tool exists to catch, planted in the tool itself: a document
        # whose quotes all fall below the extraction floor must report vacuous, never clean.
        below_floor = os.path.join(tmp, "below.md")
        with open(below_floor, "w") as fh:
            fh.write('`schemas/order.json` uses the word *"contract"* throughout.')
        got, _ = check_quotes(below_floor, tmp)
        results.append(("zero extracted spans report vacuous, not clean",
                        bool(got and got["vacuous"])))

        # A wrapped, elided quote must still match — the normalisation's whole purpose.
        wrapped = os.path.join(tmp, "wrapped.md")
        with open(wrapped, "w") as fh:
            fh.write('`schemas/order.json` says *"A binding\n   reporting\n   contract"*.')
        got, _ = check_quotes(wrapped, tmp)
        results.append(("wrapped quote matches after normalisation",
                        bool(got and not got["findings"])))

        # Regression: two adjacent quotations must not yield a phantom finding built from
        # the prose BETWEEN them. Sequential quote-mark pairing produced exactly that.
        adjacent = os.path.join(tmp, "adjacent.md")
        with open(adjacent, "w") as fh:
            fh.write('`schemas/order.json` says *"A binding reporting contract"* and also '
                     'describes it as *"A binding reporting contract"* elsewhere.')
        got, _ = check_quotes(adjacent, tmp)
        results.append(("adjacent quotations yield no inter-quote phantom",
                        bool(got and not got["findings"] and got["checked"] == 2)))

        transcript = os.path.join(tmp, "t.jsonl")
        with open(transcript, "w") as fh:
            rec = {"message": {"content": [
                {"type": "tool_use", "name": "Read",
                 "input": {"file_path": os.path.join(src, "order.json")}}]}}
            fh.write(json.dumps(rec) + "\n")
        got, _ = check_citations(clean, transcript)
        results.append(("citations stay green on an opened file",
                        bool(got and not got["findings"])))

        uncited = os.path.join(tmp, "uncited.md")
        with open(uncited, "w") as fh:
            fh.write("Per `schemas/ghost.json` the field is required.")
        got, _ = check_citations(uncited, transcript)
        results.append(("citations go red on a never-opened file", bool(got and got["findings"])))
        results.append(("claude-code transcript is identified as such",
                        bool(got and got["runtime"] == "claude-code")))

        # Codex writes rollout records, not message/content blocks. An adapter with no
        # red-going test is an assumption, so both shapes it reads are planted here:
        # function_call carrying JSON arguments, and custom_tool_call carrying free text.
        codex = os.path.join(tmp, "codex.jsonl")
        with open(codex, "w") as fh:
            fh.write(json.dumps({"type": "response_item", "payload": {
                "type": "function_call", "name": "read_file",
                "arguments": json.dumps({"file_path": os.path.join(src, "order.json")})}}) + "\n")
            fh.write(json.dumps({"type": "response_item", "payload": {
                "type": "custom_tool_call", "name": "exec",
                "input": "grep -n title schemas/order.json"}}) + "\n")
        got, _ = check_citations(clean, codex)
        results.append(("codex transcript is identified and its paths extracted",
                        bool(got and got["runtime"] == "codex" and not got["findings"])))

        # An unreadable format must not resolve to "opened nothing", which would silently
        # mark every citation as fabricated.
        alien = os.path.join(tmp, "alien.jsonl")
        with open(alien, "w") as fh:
            fh.write(json.dumps({"kind": "something-else", "data": [1, 2, 3]}) + "\n")
        got, _ = check_citations(clean, alien)
        results.append(("unrecognised transcript reports no runtime rather than empty",
                        bool(got and got["runtime"] is None)))

    print("selftest")
    failed = 0
    for label, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        failed += 0 if ok else 1
    print(f"\n  {len(results)} checks, {failed} failure(s)")
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(
        description="Check a document's quotes and citations against their sources.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--quotes", metavar="DOC", help="verify quoted spans appear in cited files")
    ap.add_argument("--citations", metavar="DOC", help="verify cited files were opened")
    ap.add_argument("--root", default=".", help="root for resolving cited paths (default: .)")
    ap.add_argument("--transcript", help="session .jsonl for --citations")
    ap.add_argument("--min-quote", type=int, default=MIN_QUOTE_CHARS,
                    help=f"minimum quoted-span length to check (default: {MIN_QUOTE_CHARS}); "
                         f"lower catches short normative fragments at the cost of noise")
    ap.add_argument("--selftest", action="store_true", help="prove the detectors can go red")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.quotes and not args.citations:
        ap.error("nothing to do: pass --quotes, --citations, or --selftest")
    if args.citations and not args.transcript:
        ap.error("--citations requires --transcript")

    total = 0
    vacuous = False
    if args.quotes:
        got, errs = check_quotes(args.quotes, args.root, args.min_quote)
        if got is None:
            for e in errs:
                print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"quotes  {got['checked']} quoted span(s) against {got['files']} cited file(s)")
        for rel in got["unresolved"]:
            print(f"  SKIP  cited path not found under --root: {rel}")
        for f in got["findings"]:
            print(f"  FAIL  {f}")
        if got["vacuous"]:
            vacuous = True
            print(f"  VACUOUS  nothing was compared — {got['checked']} span(s) at or above "
                  f"--min-quote {args.min_quote}, {got['files']} resolved file(s). This is "
                  f"not a pass; the matcher selected nothing.")
        if got["unresolved"]:
            print(f"  note  {len(got['unresolved'])} cited path(s) unresolved under --root — "
                  f"quotes with no candidate file cannot be called verified")
        if got["skipped"]:
            print(f"  note  {got['skipped']} undelimited quotation(s) skipped — only *\"…\"* "
                  f"is extracted, so these were neither checked nor cleared")
        total += len(got["findings"])
        print()

    if args.citations:
        got, errs = check_citations(args.citations, args.transcript)
        if got is None:
            for e in errs:
                print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"citations  {got['cited']} cited path(s) against {got['opened']} path(s) "
              f"touched in a {got['runtime'] or 'UNRECOGNISED'} transcript")
        for f in got["findings"]:
            print(f"  FAIL  {f}")
        if got["cited"] == 0:
            vacuous = True
            print("  VACUOUS  the document cites no backticked paths — there was nothing "
                  "to reconcile. This is not a pass.")
        if got["runtime"] is None or got["opened"] == 0:
            vacuous = True
            print("  VACUOUS  no tool calls were recognised in this transcript. Either the "
                  "format is not claude-code or codex, or the session opened nothing. "
                  "Every citation would read as never-opened, so this is not a pass.")
        print("  note  shell-derived paths are heuristic; a variable-expanded path reads "
              "as never-opened")
        total += len(got["findings"])
        print()

    print(f"{total} finding(s)")
    if vacuous:
        print("At least one check was VACUOUS. Treat this run as unperformed, not clean.")
    elif total == 0:
        print("A clean run means nothing cited was fabricated. It says nothing about "
              "claims that cite no source at all.")
    return 1 if (total or vacuous) else 0


if __name__ == "__main__":
    sys.exit(main())
