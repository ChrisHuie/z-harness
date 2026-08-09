#!/usr/bin/env python3
"""askq_timeout_guard - PostToolUse guard for the AskUserQuestion AFK auto-proceed bug.

WHAT THE HARNESS ACTUALLY SENDS US
----------------------------------
A PostToolUse hook receives ONE JSON object on stdin. Empirically captured from
Claude Code 2.1.220:

    {session_id, transcript_path, cwd, prompt_id, permission_mode,
     hook_event_name, tool_name, tool_input, tool_response, tool_use_id, duration_ms}

`tool_response` is the tool's STRUCTURED result object (byte-identical to the
transcript's `toolUseResult`). It is NOT the English string the model reads.
For AskUserQuestion, CC 2.1.220 declares:

    afkTimeoutMs: z.number().int().positive().optional()
      .describe("Set when the dialog auto-resolved after this many milliseconds of
                 idle (user away from keyboard). Absent on every human-resolved path.")

That field is the discriminator. This guard decides on a typed lookup of a parsed
object -- never on a substring scan of the payload blob.

DECISION CHANNEL
----------------
The verdict is carried on stdout as hook JSON, not by the exit code:
  status 0 + stdout JSON  -> harness parses {continue, stopReason, systemMessage}
  status 2                -> harness raises a blocking error carrying stderr
This guard uses BOTH on the UNRECOGNISED path so a schema change cannot be quiet.

FAIL-CLOSED. If this guard cannot classify the result it HALTS and says exactly what
it saw. A false halt costs one keystroke. A false pass costs an unwanted autonomous
run -- which is the whole reason this file exists.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback

VERSION = "2.0.0"
TOOL = "AskUserQuestion"
EVENT = "PostToolUse"

# ---- keys this guard has been taught. Anything else in tool_response is DRIFT. -----
KNOWN_RESPONSE_KEYS = {"questions", "answers", "response", "annotations", "afkTimeoutMs"}

# Vendor-owned sentinel (CC 2.1.220: `lvo="(notes only)"`). Soft signal only.
NOTES_ONLY_SENTINEL = "(notes only)"

# Prose markers. SECONDARY ONLY -- reached only when the structured shape is already
# gone. ANY match is enough (not ALL), so one reworded word cannot silence the guard.
TIMEOUT_PROSE = [
    re.compile(r"no response after", re.I),
    re.compile(r"away from keyboard", re.I),
    re.compile(r"\bafk\b", re.I),
    re.compile(r"auto[- ]?(advanc|resolv|continu|proceed)", re.I),
    re.compile(r"best\s+judg[e]?ment", re.I),
    re.compile(r"\bidle\b", re.I),
    re.compile(r"time[d]?\s*[- ]?out", re.I),
]
DECLINE_PROSE = [
    re.compile(r"doesn't want to proceed with this tool use", re.I),
    re.compile(r"wants to clarify these questions", re.I),
]

# verdict -> (halts?, exit_code)
VERDICTS = {
    "TIMEOUT_STRUCTURED":      (True, 0),
    "NO_ANSWER_STRUCTURED":    (True, 0),
    "TIMEOUT_PROSE_FALLBACK":  (True, 0),
    "ANSWERED":                (False, 0),
    "DECLINED":                (False, 0),
    "OUT_OF_SCOPE":            (False, 0),
    "UNRECOGNISED":            (True, 2),
}

HELP = f"""askq_timeout_guard {VERSION}

A PostToolUse guard for {TOOL}. Halts the turn when the question dialog
auto-resolved on the AFK timer instead of being answered by a human.

USAGE
  askq_timeout_guard.py                 read a hook payload on stdin (hook mode)
  askq_timeout_guard.py --selftest      run every fixture, assert per fixture
  askq_timeout_guard.py --explain FILE  classify one payload file, print evidence
  askq_timeout_guard.py --verify-harness  re-check this guard's assumptions against
                                          the installed Claude Code binary (R1 anchor)
  askq_timeout_guard.py --version
  askq_timeout_guard.py --help

ENVIRONMENT
  ASKQ_GUARD_LOG              events JSONL path
                              (default $XDG_STATE_HOME/askq-guard/events.jsonl)
  ASKQ_GUARD_FIXTURES         fixture dir for --selftest (default ./fixtures)
  ASKQ_GUARD_KNOWN_EXTRA_KEYS comma-separated tool_response keys to accept as known,
                              for when the vendor adds a benign field
  ASKQ_GUARD_FAIL_OPEN=1      do NOT halt on UNRECOGNISED (still logs + warns).
                              Off by default: unclassifiable input must not pass.
  ASKQ_GUARD_CLI              path to the claude binary for --verify-harness

EXIT CODES (hook mode)
  0  verdict delivered on stdout as hook JSON (pass, or a structured halt)
  2  UNRECOGNISED input, or zero input -- harness raises a blocking error
"""


# ====================================================================================
# classification
# ====================================================================================
def known_keys():
    extra = os.environ.get("ASKQ_GUARD_KNOWN_EXTRA_KEYS", "")
    return KNOWN_RESPONSE_KEYS | {k.strip() for k in extra.split(",") if k.strip()}


def prose_hit(text, patterns):
    return sorted({p.pattern for p in patterns if p.search(text)})


def has_real_answer(tr):
    """True only if a human demonstrably supplied something."""
    ans = tr.get("answers")
    if isinstance(ans, dict):
        for v in ans.values():
            if isinstance(v, list):
                if [x for x in v if str(x).strip() and str(x).strip() != NOTES_ONLY_SENTINEL]:
                    return True
            elif str(v).strip() and str(v).strip() != NOTES_ONLY_SENTINEL:
                return True
    if isinstance(tr.get("response"), str) and tr["response"].strip():
        return True
    ann = tr.get("annotations")
    if isinstance(ann, dict):
        for v in ann.values():
            if isinstance(v, dict) and str(v.get("notes", "")).strip():
                return True
    return False


def classify(payload):
    """-> (verdict, reason, evidence dict). Pure; no I/O."""
    ev = {
        "payload_keys": sorted(payload.keys()) if isinstance(payload, dict) else None,
        "tool_name": None,
        "hook_event_name": None,
        "tool_response_type": None,
        "tool_response_keys": None,
        "unknown_response_keys": [],
        "prose_markers_hit": [],
        "drift": False,
    }
    if not isinstance(payload, dict):
        return "UNRECOGNISED", f"stdin parsed to {type(payload).__name__}, expected a JSON object", ev

    ev["tool_name"] = payload.get("tool_name")
    ev["hook_event_name"] = payload.get("hook_event_name")

    if "tool_name" not in payload:
        ev["drift"] = True
        return "UNRECOGNISED", "envelope has no 'tool_name' key -- hook payload schema changed", ev
    if payload["tool_name"] != TOOL:
        return "OUT_OF_SCOPE", f"tool_name={payload['tool_name']!r}, not {TOOL}", ev
    if payload.get("hook_event_name") not in (EVENT, None):
        return "OUT_OF_SCOPE", f"hook_event_name={payload.get('hook_event_name')!r}", ev
    if "tool_response" not in payload:
        ev["drift"] = True
        return "UNRECOGNISED", "envelope has no 'tool_response' key -- hook payload schema changed", ev

    tr = payload["tool_response"]
    ev["tool_response_type"] = type(tr).__name__

    # ---- dict shape: the modelled world -------------------------------------------
    if isinstance(tr, dict):
        ev["tool_response_keys"] = sorted(tr.keys())
        ev["unknown_response_keys"] = sorted(set(tr.keys()) - known_keys())

        if "afkTimeoutMs" in tr:
            v = tr["afkTimeoutMs"]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
                ev["drift"] = True
                return ("UNRECOGNISED",
                        f"afkTimeoutMs present but value is {v!r} "
                        f"({type(v).__name__}); schema says positive int", ev)
            if ev["unknown_response_keys"]:
                ev["drift"] = True
            return ("TIMEOUT_STRUCTURED",
                    f"tool_response.afkTimeoutMs={v} -- vendor schema: "
                    f"'Absent on every human-resolved path'", ev)

        if ev["unknown_response_keys"]:
            ev["drift"] = True
            return ("UNRECOGNISED",
                    "tool_response carries key(s) this guard was never taught: "
                    f"{ev['unknown_response_keys']}. A renamed or added timeout field "
                    "would look exactly like this, and a timeout CAN carry partial "
                    "answers, so no pass verdict is safe here.", ev)

        if "questions" not in tr:
            ev["drift"] = True
            return "UNRECOGNISED", "tool_response has no 'questions' key", ev
        if "answers" not in tr:
            ev["drift"] = True
            return "UNRECOGNISED", "tool_response has no 'answers' key", ev

        if has_real_answer(tr):
            return "ANSWERED", "a human supplied at least one answer/response/note", ev
        return ("NO_ANSWER_STRUCTURED",
                "no afkTimeoutMs, but answers/response/annotations are all empty -- "
                "no answer is not an answer", ev)

    # ---- string shape: already drifted, or the decline path ------------------------
    if isinstance(tr, str):
        dec = prose_hit(tr, DECLINE_PROSE)
        if dec:
            ev["prose_markers_hit"] = dec
            return "DECLINED", "user declined / asked to clarify; harness already stopped", ev
        hits = prose_hit(tr, TIMEOUT_PROSE)
        if hits:
            ev["prose_markers_hit"] = hits
            ev["drift"] = True
            return ("TIMEOUT_PROSE_FALLBACK",
                    "tool_response is a bare string and matched timeout prose "
                    f"{hits}. The structured afkTimeoutMs signal is GONE -- this "
                    "guard is running on its fallback layer and must be re-anchored "
                    "(run --verify-harness).", ev)
        ev["drift"] = True
        return ("UNRECOGNISED",
                f"tool_response is a bare string matching no known form: "
                f"{tr[:200]!r}", ev)

    ev["drift"] = True
    return "UNRECOGNISED", f"tool_response is a {type(tr).__name__}, not an object or string", ev


# ====================================================================================
# reporting
# ====================================================================================
def cli_build():
    for p in (os.environ.get("ASKQ_GUARD_CLI"),
              os.path.expanduser("~/.local/bin/claude"),
              "/usr/local/bin/claude"):
        if p and os.path.exists(p):
            try:
                return os.path.realpath(p)
            except OSError:
                return p
    return "unknown"


def scan_set(ev):
    """SHIP GATE 4: the evidence set behind the verdict, always printed on a halt."""
    return (
        f"guard={VERSION} cli={os.path.basename(cli_build())} "
        f"event={ev.get('hook_event_name')} tool={ev.get('tool_name')} "
        f"tool_response_type={ev.get('tool_response_type')} "
        f"tool_response_keys={ev.get('tool_response_keys')} "
        f"unknown_keys={ev.get('unknown_response_keys')} "
        f"prose_markers={ev.get('prose_markers_hit')}"
    )


def log_event(verdict, reason, ev):
    path = os.environ.get("ASKQ_GUARD_LOG") or os.path.join(
        os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
        "askq-guard", "events.jsonl")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as fh:
            fh.write(json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "guard_version": VERSION, "cli": cli_build(),
                "verdict": verdict, "reason": reason, "evidence": ev,
            }) + "\n")
    except Exception:
        pass  # never let logging change the verdict


def build_output(verdict, reason, ev):
    """-> (stdout_json_or_None, stderr_text_or_None, exit_code)"""
    halts, code = VERDICTS[verdict]
    fail_open = os.environ.get("ASKQ_GUARD_FAIL_OPEN") == "1"

    if verdict in ("ANSWERED", "DECLINED", "OUT_OF_SCOPE"):
        return None, None, 0

    if verdict == "UNRECOGNISED":
        head = (f"askq_timeout_guard {VERSION} NO LONGER RECOGNISES THE "
                f"{TOOL} RESULT. It cannot tell a timeout from an answer, so it "
                f"stopped rather than guess.")
        body = f"{head}\n\nWHY: {reason}\n\nSAW: {scan_set(ev)}\n\n" \
               f"FIX: run `askq_timeout_guard.py --verify-harness`; if the vendor " \
               f"merely added a benign field, set " \
               f"ASKQ_GUARD_KNOWN_EXTRA_KEYS={','.join(ev.get('unknown_response_keys') or ['<key>'])}"
        if fail_open:
            return ({"continue": True,
                     "systemMessage": head + " (ASKQ_GUARD_FAIL_OPEN=1, not halting) " + scan_set(ev)},
                    body, 0)
        return ({"continue": False, "stopReason": body,
                 "systemMessage": head},
                body, 2)

    # structured halts
    label = {
        "TIMEOUT_STRUCTURED": "timed out with no human answer",
        "NO_ANSWER_STRUCTURED": "returned with no human answer",
        "TIMEOUT_PROSE_FALLBACK": "timed out (detected on the PROSE FALLBACK layer)",
    }[verdict]
    stop = (f"{TOOL} {label} - halted by askq_timeout_guard {VERSION}. "
            f"A timeout is not an answer. The question is still open: answer it to resume.\n"
            f"BASIS: {reason}\nSAW: {scan_set(ev)}")
    out = {"continue": False, "stopReason": stop}
    if ev.get("drift"):
        out["systemMessage"] = (f"askq_timeout_guard: SCHEMA DRIFT while halting. {scan_set(ev)} "
                                f"-- run --verify-harness.")
    return out, None, 0


# ====================================================================================
# modes
# ====================================================================================
def run_hook(raw):
    if not raw.strip():
        # SHIP GATE 4: zero inputs is an error, never a clean verdict.
        ev = {"tool_response_type": None}
        log_event("UNRECOGNISED", "empty stdin", ev)
        sys.stderr.write(f"askq_timeout_guard {VERSION}: ZERO INPUT on stdin. A "
                         f"{EVENT} hook must receive a JSON payload; receiving nothing "
                         f"means the guard is not wired to what it thinks it is. "
                         f"{scan_set(ev)}\n")
        return 2
    try:
        payload = json.loads(raw)
    except Exception as e:
        ev = {"tool_response_type": None, "drift": True}
        log_event("UNRECOGNISED", f"stdin is not JSON: {e}", ev)
        sys.stderr.write(f"askq_timeout_guard {VERSION}: stdin is not JSON ({e}). "
                         f"first 120 bytes: {raw[:120]!r}\n")
        print(json.dumps({"continue": False,
                          "stopReason": f"askq_timeout_guard could not parse its own "
                                        f"hook payload ({e}). Halting rather than guess."}))
        return 2

    verdict, reason, ev = classify(payload)
    log_event(verdict, reason, ev)
    out, err, code = build_output(verdict, reason, ev)
    if out is not None:
        print(json.dumps(out))
    if err:
        sys.stderr.write(err + "\n")
    return code


def run_explain(path):
    raw = open(path).read()
    try:
        payload = json.loads(raw)
    except Exception as e:
        print(f"NOT JSON: {e}")
        return 2
    verdict, reason, ev = classify(payload)
    halts, code = VERDICTS[verdict]
    out, err, ecode = build_output(verdict, reason, ev)
    print(f"file      : {path}")
    print(f"verdict   : {verdict}   halts={halts}  exit={ecode}")
    print(f"reason    : {reason}")
    print(f"scan set  : {scan_set(ev)}")
    print(f"stdout    : {json.dumps(out) if out else '(silent)'}")
    return 0


# ---- expectations. One row per fixture, asserted field by field. -------------------
EXPECT = {
    "01_timeout_afk.json":                  ("TIMEOUT_STRUCTURED",     False, 0, False),
    "02_answered_with_annotations.json":    ("ANSWERED",               None,  0, False),
    "03_answered_no_annotations.json":      ("ANSWERED",               None,  0, False),
    "04_declined_clarify.json":             ("DECLINED",               None,  0, False),
    "06_other_tool.json":                   ("OUT_OF_SCOPE",           None,  0, False),
    "U1_unmodelled_renamed_field.json":     ("UNRECOGNISED",           False, 2, True),
    "U2_unmodelled_prose_payload.json":     ("TIMEOUT_PROSE_FALLBACK", False, 0, True),
    "U3_unmodelled_alien_shape.json":       ("UNRECOGNISED",           False, 2, True),
    "U4_unmodelled_empty_no_afk.json":      ("NO_ANSWER_STRUCTURED",   False, 0, False),
    "U5_afk_on_tool_input_too.json":        ("TIMEOUT_STRUCTURED",     False, 0, False),
    "U6_envelope_drift_no_tool_response.json": ("UNRECOGNISED",        False, 2, True),
    "U7_not_json.txt":                      ("UNRECOGNISED",           False, 2, True),
    "U8_empty.txt":                         ("ZERO_INPUT",             None,  2, True),
}
# tuple = (verdict, expected `continue` in stdout JSON or None for silent,
#          expected process exit code, expects a drift/unrecognised marker in output)


def run_selftest():
    fixdir = os.environ.get("ASKQ_GUARD_FIXTURES") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "fixtures")
    print(f"askq_timeout_guard {VERSION} --selftest")
    print(f"  fixture dir : {fixdir}")
    if not os.path.isdir(fixdir):
        print(f"  FATAL: fixture dir does not exist -> exit 2")
        return 2
    files = sorted(f for f in os.listdir(fixdir) if not f.startswith("."))
    print(f"  fixtures    : {len(files)}")
    print(f"  cli build   : {cli_build()}")
    if not files:
        print("  FATAL: zero fixtures. Zero inputs is an error, never a clean verdict -> exit 2")
        return 2

    me = os.path.abspath(__file__)
    env = dict(os.environ)
    event_log = os.path.join(
        tempfile.gettempdir(), f"z-harness-askq-selftest-{os.getpid()}.jsonl"
    )
    env["ASKQ_GUARD_LOG"] = event_log
    env.pop("ASKQ_GUARD_FAIL_OPEN", None)
    env.pop("ASKQ_GUARD_KNOWN_EXTRA_KEYS", None)

    unexpected = [f for f in files if f not in EXPECT]
    missing = [f for f in EXPECT if f not in files]
    failures = []
    print()
    print(f"  {'FIXTURE':44s} {'VERDICT':24s} {'exit':>4s} {'cont':>5s}  RESULT")
    print("  " + "-" * 92)

    for f in files:
        if f not in EXPECT:
            print(f"  {f:44s} {'-':24s} {'-':>4s} {'-':>5s}  FAIL (no expectation row)")
            failures.append((f, "no expectation row"))
            continue
        exp_verdict, exp_continue, exp_code, exp_loud = EXPECT[f]
        raw = open(os.path.join(fixdir, f), "rb").read()
        # SHIP GATE 3: exit code comes from the child's returncode, both streams read.
        p = subprocess.run([sys.executable, me], input=raw,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        code = p.returncode
        so = p.stdout.decode("utf-8", "replace").strip()
        se = p.stderr.decode("utf-8", "replace").strip()

        # SHIP GATE 3: parse the structured value; never `"TOKEN" in output`.
        parsed, cont = None, None
        if so:
            try:
                parsed = json.loads(so)
                cont = parsed.get("continue")
            except Exception as e:
                failures.append((f, f"stdout is not valid JSON: {e}"))

        # independent re-derivation of the verdict from the parsed payload
        if f.endswith(".json"):
            try:
                got_verdict = classify(json.loads(raw.decode()))[0]
            except Exception:
                got_verdict = "UNRECOGNISED"
        else:
            got_verdict = "ZERO_INPUT" if not raw.strip() else "UNRECOGNISED"

        probs = []
        if got_verdict != exp_verdict:
            probs.append(f"verdict {got_verdict} != {exp_verdict}")
        if code != exp_code:
            probs.append(f"exit {code} != {exp_code}")
        if exp_continue is None:
            if so:
                probs.append(f"expected silent stdout, got {so[:80]!r}")
        else:
            if cont != exp_continue:
                probs.append(f"stdout.continue {cont!r} != {exp_continue!r}")
        if exp_loud:
            blob = so + " " + se
            if not blob.strip():
                probs.append("expected a loud report on stdout or stderr, got nothing")
            elif not ("NO LONGER RECOGNISES" in blob or "DRIFT" in blob
                      or "FALLBACK" in blob or "ZERO INPUT" in blob or "not JSON" in blob):
                probs.append("output does not name the form as out of scope")

        res = "pass" if not probs else "FAIL: " + "; ".join(probs)
        if probs:
            failures.append((f, "; ".join(probs)))
        cs = "-" if cont is None else str(cont)
        print(f"  {f:44s} {got_verdict:24s} {code:>4d} {cs:>5s}  {res}")

    print("  " + "-" * 92)
    print(f"  arms covered : HALT={sum(1 for v in EXPECT.values() if v[1] is False)}  "
          f"PASS={sum(1 for v in EXPECT.values() if v[1] is None and v[2] == 0)}")
    if unexpected:
        print(f"  UNEXPECTED fixtures (no expectation row): {unexpected}")
    if missing:
        print(f"  MISSING fixtures (expectation with no file): {missing}")
        failures.append(("<missing>", str(missing)))
    try:
        os.unlink(event_log)
    except FileNotFoundError:
        pass
    if failures:
        print(f"\n  {len(failures)} FAILURE(S):")
        for f, why in failures:
            print(f"    - {f}: {why}")
        print(f"SELFTEST-SUMMARY suite=askq_timeout_guard checks={len(files) + len(missing)} failures={len(failures)}")
        return 1
    print("\n  all fixtures pass, both arms exercised")
    print(f"SELFTEST-SUMMARY suite=askq_timeout_guard checks={len(files)} failures=0")
    return 0


ANCHORS = [
    ("afkTimeoutMs discriminator",
     b'afkTimeoutMs', True),
    ("vendor guarantee 'Absent on every human-resolved path'",
     b"Absent on every human-resolved path", True),
    ("timeout prose template (fallback layer only)",
     b"No response after ${Math.round(", False),
    ("notes-only sentinel",
     b'"(notes only)"', False),
]


def run_verify_harness():
    """R1 mechanized: re-check this guard's assumptions against the binary it guards."""
    path = cli_build()
    print(f"askq_timeout_guard {VERSION} --verify-harness")
    print(f"  binary : {path}")
    if not os.path.exists(path):
        print("  FATAL: no claude binary found; set ASKQ_GUARD_CLI -> exit 2")
        return 2
    size = os.path.getsize(path)
    print(f"  size   : {size} bytes")
    if size == 0:
        print("  FATAL: zero-byte binary -> exit 2")
        return 2
    data = open(path, "rb").read()
    print()
    critical_missing = False
    for name, needle, critical in ANCHORS:
        ok = needle in data
        tag = "PRESENT" if ok else "MISSING"
        crit = " [CRITICAL]" if critical else ""
        print(f"  {tag:8s}{crit:12s} {name}")
        if critical and not ok:
            critical_missing = True
    print()
    if critical_missing:
        print("  A CRITICAL ANCHOR IS GONE. The structured discriminator this guard")
        print("  depends on is no longer in the shipped binary. The guard is running")
        print("  blind -- re-derive the discriminator before trusting it. -> exit 1")
        return 1
    print("  all critical anchors hold -> exit 0")
    return 0


def main(argv):
    args = argv[1:]
    if not args:
        return run_hook(sys.stdin.read())
    a = args[0]
    if a in ("-h", "--help"):
        print(HELP)
        return 0
    if a == "--version":
        print(VERSION)
        return 0
    if a == "--selftest":
        if len(args) > 1:
            sys.stderr.write("--selftest takes no arguments\n")
            return 2
        return run_selftest()
    if a == "--verify-harness":
        return run_verify_harness()
    if a == "--explain":
        if len(args) != 2:
            sys.stderr.write("--explain needs exactly one FILE\n")
            return 2
        return run_explain(args[1])
    sys.stderr.write(f"unknown argument: {a!r}\nrun --help\n")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except SystemExit:
        raise
    except Exception:
        # Fail closed: a crashing guard must be loud, never silent.
        tb = traceback.format_exc()
        sys.stderr.write(f"askq_timeout_guard {VERSION} CRASHED -- treating as "
                         f"UNRECOGNISED and halting.\n{tb}\n")
        try:
            print(json.dumps({"continue": False,
                              "stopReason": "askq_timeout_guard crashed; it cannot "
                                            "certify that the user answered. Halting."}))
        except Exception:
            pass
        sys.exit(2)
