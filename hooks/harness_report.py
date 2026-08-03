#!/usr/bin/env python3
"""harness_report — is the skills harness actually working?

Everything installed on 2026-08-02 is unverified in real use. This reads your own
transcripts and answers the questions that decide it, with the denominators that
earlier passes got wrong.

  harness_report.py                 # last 7 days
  harness_report.py --since 30d     # last 30 days
  harness_report.py --all           # whole corpus
  harness_report.py --selftest      # prove the detectors can go red

UNIT OF ANALYSIS: one transcript FILE = one agent context = one dispatch.
A file is NOT a session (663 sessions, 2,586 files) and 74% of files are subagent
contexts nested at <session-id>/subagents/. Counting per session hides most of the
evidence; counting per session-file misses subagents entirely.

TWO FIRE SIGNALS, DIFFERENT UNITS — both are reported because either alone lies:
  Skill tool_use   an explicit invocation. Misses slash-command loads.
  attributionSkill stamped on every record while a body is active. Counts records,
                   not invocations, so it is a duration measure, not a count.

WHAT IS INFERRED, NOT OBSERVED:
  CLAUDE.md currency. The injected system-reminder is NOT persisted to the
  transcript (verified three ways), so which version a session ran cannot be read
  back. Inferred from session-start timestamp vs the file's mtime, on the measured
  fact that the user-level file is read at session start.
"""
import argparse
import collections
import glob
import json
import os
import re
import sys
import time

VERSION = "1.0.0"
ROOT = os.path.expanduser("~/.claude/projects")
CLAUDE_MD = os.path.expanduser("~/.claude/CLAUDE.md")
SKILLS_DIR = os.path.expanduser("~/.claude/skills")

# Topic-present signals.
#
# EVERY SIGNAL MATCHES AN ACTION, NEVER A MENTION. The first version of this table
# matched prose, and on its first run reported craft-context-file "topic present" in
# 226 of 247 contexts — because the day's conversation was ABOUT CLAUDE.md, not
# because anyone authored one. A mention-based denominator makes capture look terrible
# and is the exact instrument error this harness exists to catch.
#
# Rule: the signal must key on a tool_use — a command that ran, or a file that was
# written — not on any text the model or user emitted.
_CMD = r'"name":"Bash".{0,400}?"command":"[^"]*'
_WROTE = r'"name":"(?:Write|Edit)".{0,400}?"file_path":"[^"]*'

TOPIC = {
    # a git/gh command actually ran
    "git-workflow":     re.compile(_CMD + r'\b(?:git|gh)\b'),
    # a test/CI command actually ran
    "testing-ci":       re.compile(_CMD + r'\b(?:pytest|tox|jest|vitest|go test|cargo test|make test|run_tests|gh run|coverage|mutmut)\b'),
    # a PR-review endpoint was actually called
    "pr-review-method": re.compile(_CMD + r'gh (?:pr\b|api [^"]*(?:pulls|reviewThreads))'),
    # an Agent was actually dispatched
    "agent-dispatch":   re.compile(r'"name":"(?:Agent|Task)","input"'),
    # a context file was actually authored
    "craft-context-file": re.compile(_WROTE + r'(?:CLAUDE|AGENTS|GEMINI)\.md"'),
    # a SKILL.md was actually authored
    "craft-skill":      re.compile(_WROTE + r'SKILL\.md"'),
    # an adcp/prebid PATH was touched, or an adcp command ran — not the words in prose
    "prebid-adcp":      re.compile(_WROTE + r'(?:adcp|prebid)|' + _CMD + r'\b(?:adcp)\b', re.I),
    # NO ACTION SIGNAL EXISTS for these three: they fire on intent, not on a tool call.
    # Reported as "—" rather than guessed at; a fabricated denominator is worse than none.
    "outbound-drafts":  None,
    "system-design":    None,
    "craft-prompt":     None,
    "review-prompt":    None,
}
FIRE = re.compile(r'"name":"Skill".{0,300}?"skill":"([a-z0-9:-]+)"')  # colon: plugin skills
ATTR = re.compile(r'"attributionSkill":"([a-z0-9-]+)"')
READ = re.compile(r'"name":"Read".{0,300}?"file_path":"([^"]+)"')


def parse_since(s):
    if s in (None, "all"):
        return 0.0
    m = re.fullmatch(r"(\d+)([dhw])", s)
    if not m:
        raise ValueError(f"bad --since {s!r}; use 7d, 24h, 2w or all")
    n, u = int(m.group(1)), m.group(2)
    return time.time() - n * {"h": 3600, "d": 86400, "w": 604800}[u]


def scan(cutoff):
    """-> (rows, scanset). One row per transcript file = one agent context."""
    files = glob.glob(ROOT + "/**/*.jsonl", recursive=True)
    scanset = {"root": ROOT, "files_found": len(files), "cutoff_epoch": cutoff,
               "files_in_window": 0, "subagent_files": 0, "unreadable": 0}
    rows = []
    for f in files:
        try:
            st = os.stat(f)
        except OSError:
            scanset["unreadable"] += 1
            continue
        if st.st_mtime < cutoff:
            continue
        scanset["files_in_window"] += 1
        is_sub = "/subagents/" in f
        scanset["subagent_files"] += is_sub
        fired, active, reads, topics = collections.Counter(), set(), [], set()
        started, session = None, None
        try:
            with open(f, errors="replace") as fh:
                for ln in fh:
                    for m in FIRE.finditer(ln):
                        fired[m.group(1)] += 1
                    for m in ATTR.finditer(ln):
                        active.add(m.group(1))
                    for m in READ.finditer(ln):
                        reads.append(m.group(1))
                    for skill, rx in TOPIC.items():
                        if rx is not None and skill not in topics and rx.search(ln):
                            topics.add(skill)
                    if started is None and '"timestamp"' in ln:
                        try:
                            d = json.loads(ln)
                            started = d.get("timestamp")
                            session = d.get("sessionId") or d.get("session_id")
                        except Exception:
                            pass
        except OSError:
            scanset["unreadable"] += 1
            continue
        rows.append({"file": f, "sub": is_sub, "fired": fired, "active": active,
                     "reads": reads, "topics": topics, "started": started,
                     "session": session})
    return rows, scanset


def report(rows, scanset, out=sys.stdout):
    p = lambda *a: print(*a, file=out)
    p(f"\nSCAN SET  root={scanset['root']}")
    p(f"          {scanset['files_found']} transcript files found, "
      f"{scanset['files_in_window']} in window, "
      f"{scanset['subagent_files']} subagent contexts "
      f"({100*scanset['subagent_files']//max(1,scanset['files_in_window'])}%), "
      f"{scanset['unreadable']} unreadable")
    n = len(rows)
    if n == 0:
        p("\nZERO CONTEXTS IN WINDOW — that is an error, not a clean result.")
        return 2

    # --- 1. firing, against topic-present
    p(f"\n1. DID SKILLS FIRE?   (denominator = {n} agent contexts)")
    p(f"   {'skill':<20}{'topic present':>14}{'fired':>8}{'capture':>9}{'active':>8}")
    installed = sorted(os.path.basename(d) for d in glob.glob(SKILLS_DIR + "/*")
                       if os.path.isdir(d))
    any_fire = 0
    for s in installed:
        has_sig = TOPIC.get(s) is not None
        tp = sum(1 for r in rows if s in r["topics"]) if has_sig else None
        fi = sum(1 for r in rows if r["fired"].get(s))
        ac = sum(1 for r in rows if s in r["active"])
        any_fire += fi
        tps = "no signal" if tp is None else str(tp)
        cap = "—" if tp is None else (f"{100*fi//tp}%" if tp else "—")
        flag = ""
        if tp:
            if not fi:
                flag = "   <-- topic present, never fired"
            elif fi > tp:
                flag = "   <-- fired MORE than topic present (over-firing)"
        p(f"   {s:<20}{tps:>14}{fi:>8}{cap:>9}{ac:>8}{flag}")
    p("   'no signal' = no ACTION distinguishes this skill's topic; capture is not computable.")
    p(f"\n   contexts with >=1 skill fired: {sum(1 for r in rows if r['fired'])}/{n}")

    # --- 2. the unproven link
    p("\n2. DID A references/ FILE GET READ AFTER ITS SKILL FIRED?   (installed skills only)")
    p("   (this is the one link in the chain never observed in real use)")
    opened = collections.Counter()
    chances = collections.Counter()
    inst = set(installed)
    for r in rows:
        for s in r["fired"]:
            if s not in inst:
                continue
            refdir = f"/skills/{s}/references/"
            chances[s] += 1
            if any(refdir in path for path in r["reads"]):
                opened[s] += 1
    if not chances:
        p("   no skill fired in this window — nothing to observe")
    else:
        for s in sorted(chances):
            p(f"   {s:<20}{opened[s]:>4} of {chances[s]:>4} fires opened its references/")
        tot_o, tot_c = sum(opened.values()), sum(chances.values())
        p(f"   {'TOTAL':<20}{tot_o:>4} of {tot_c:>4}"
          f"   <-- 0 here means 55 KB of deferred rules are unreachable in practice")

    # --- 3. CLAUDE.md currency (INFERRED)
    p("\n3. IS THE CURRENT ~/.claude/CLAUDE.md REACHING SESSIONS?   [INFERRED]")
    try:
        md = os.stat(CLAUDE_MD).st_mtime
    except OSError:
        p("   ~/.claude/CLAUDE.md not found")
        md = None
    if md:
        stale = fresh = unknown = 0
        for r in rows:
            if not r["started"]:
                unknown += 1
                continue
            try:
                t = time.mktime(time.strptime(r["started"][:19], "%Y-%m-%dT%H:%M:%S"))
            except Exception:
                unknown += 1
                continue
            fresh += t >= md
            stale += t < md
        p(f"   CLAUDE.md mtime: {time.strftime('%Y-%m-%d %H:%M', time.localtime(md))}")
        p(f"   contexts started AFTER it (got current file): {fresh}")
        p(f"   contexts started BEFORE it (ran a stale copy): {stale}")
        p(f"   undatable: {unknown}")
        p("   NOTE: inferred from session-start vs mtime. The injected block is NOT")
        p("   persisted to transcripts, so this cannot be observed directly.")
    return 0 if any_fire else 1


def selftest():
    """A detector that cannot go red proves nothing. Prove each one red."""
    checks, bad = 0, 0

    def chk(label, got, want):
        nonlocal checks, bad
        checks += 1
        ok = got == want
        bad += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} {label:<52} got={got!r}")

    fire_line = '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill","input":{"skill":"git-workflow"}}]}}'
    chk("FIRE matches a real Skill tool_use", FIRE.search(fire_line).group(1), "git-workflow")
    chk("FIRE does NOT match a mention of the word skill",
        FIRE.search('{"text":"I should use the git-workflow skill"}'), None)
    plug = '{"type":"tool_use","name":"Skill","input":{"skill":"myplugin:deploy"}}'
    chk("FIRE matches a plugin-form skill name", FIRE.search(plug).group(1), "myplugin:deploy")
    chk("ATTR matches attributionSkill", ATTR.search('{"attributionSkill":"testing-ci"}').group(1), "testing-ci")
    read_line = '{"type":"tool_use","name":"Read","input":{"file_path":"/opt/example/.claude/skills/testing-ci/references/deferred.md"}}'
    chk("READ extracts the path", "references/deferred.md" in READ.search(read_line).group(1), True)
    gitcmd = '{"type":"tool_use","name":"Bash","input":{"command":"git status --porcelain"}}'
    chk("TOPIC git matches a git command that RAN", bool(TOPIC["git-workflow"].search(gitcmd)), True)
    chk("TOPIC git does NOT match prose about git",
        bool(TOPIC["git-workflow"].search('{"text":"explain what git rebase does"}')), False)
    ccf = '{"type":"tool_use","name":"Write","input":{"file_path":"/r/CLAUDE.md","content":"x"}}'
    chk("TOPIC craft-context-file matches an authored CLAUDE.md",
        bool(TOPIC["craft-context-file"].search(ccf)), True)
    chk("TOPIC craft-context-file does NOT match talking about CLAUDE.md",
        bool(TOPIC["craft-context-file"].search('{"text":"our CLAUDE.md is too long"}')), False)
    chk("skills with no action signal are None, not a guess", TOPIC["system-design"], None)
    # zero-input arm
    rows, ss = [], {"root": ROOT, "files_found": 0, "cutoff_epoch": 0,
                    "files_in_window": 0, "subagent_files": 0, "unreadable": 0}
    import io
    buf = io.StringIO()
    rc = report(rows, ss, out=buf)
    chk("zero contexts exits 2, not 0", rc, 2)
    chk("zero contexts says so out loud", "ZERO CONTEXTS" in buf.getvalue(), True)
    print(f"\n  {checks} checks, {bad} failures")
    print(f"SELFTEST-SUMMARY checks={checks} failures={bad}")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(add_help=True, description="is the skills harness working?")
    ap.add_argument("--since", default="7d", help="7d | 24h | 2w | all (default 7d)")
    ap.add_argument("--all", action="store_true", help="whole corpus")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--version", action="store_true")
    try:
        args = ap.parse_args()
    except SystemExit:
        return 2
    if args.version:
        print(f"harness_report {VERSION}")
        return 0
    if args.selftest:
        return selftest()
    try:
        cutoff = parse_since("all" if args.all else args.since)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    rows, scanset = scan(cutoff)
    return report(rows, scanset)


if __name__ == "__main__":
    sys.exit(main())
