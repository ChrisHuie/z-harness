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

CAPTURE IS A PER-CONTEXT INTERSECTION. An earlier version divided the number of
contexts where a skill fired by the number of contexts where its topic appeared,
without requiring both in the SAME context: a fire in one dispatch and a topic in
another read as 100%. Capture now means: of the contexts whose topic signal appeared,
how many also fired the skill. Three refinements travel with it:
  eligibility  only topic-present contexts form the denominator; a fire with no topic
               in its context is reported as over-firing, never as capture;
  ordering     the routing rule is "load it first", so a fire is split by whether the
               Skill call precedes the first topic action in that context or follows it;
  namespace    a plugin-form fire such as `zh:git-workflow` counts for `git-workflow`;
               the namespace is tallied separately so the mapping stays visible.

WHAT IS INFERRED, NOT OBSERVED:
  CLAUDE.md currency. The injected system-reminder is NOT persisted to the
  transcript (verified three ways), so which version a session ran cannot be read
  back. Inferred from session-start timestamp vs the file's mtime, on the measured
  fact that the user-level file is read at session start. Transcript timestamps are
  ISO-8601 in UTC (a trailing Z); they are parsed as UTC and compared to the file's
  epoch mtime. An earlier version parsed them with time.mktime, which reads the wall
  clock as LOCAL time, so every context started on a UTC-6 host appeared six hours
  later than it did.
"""
import argparse
import collections
import datetime
import glob
import json
import os
import re
import sys
import time

VERSION = "2.0.0"
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
#
# THESE ARE ACTION CLASSIFIERS, NOT INTENT DETECTORS. They answer "did a git command
# run in this context", after the fact, from serialized tool calls; they say nothing
# about what the user asked for, and a read-only `git status` matches as readily as a
# commit. They must not be reused to decide what gets injected on a user prompt: a
# routing detector keys on prompt text and is validated on a hand-labeled sample
# before it decides anything. Reusing this table for routing would disable routing
# on every prompt that has not yet produced a tool call, which is all of them.
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


def parse_transcript_timestamp(value):
    """ISO-8601 transcript timestamp -> UTC epoch seconds, or None.

    A trailing Z and explicit offsets are honored. A naive string is read as UTC,
    because that is what the transcript writer emits; it is never read as local time.
    """
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.timestamp()


def context_freshness(started, md_epoch):
    """-> 'fresh' (started at or after the file's mtime), 'stale', or 'unknown'."""
    epoch = parse_transcript_timestamp(started)
    if epoch is None or md_epoch is None:
        return "unknown"
    return "fresh" if epoch >= md_epoch else "stale"


def normalize_skill_name(name):
    """-> (namespace or '', bare skill name). `zh:git-workflow` -> ('zh', 'git-workflow')."""
    if ":" in name:
        namespace, bare = name.rsplit(":", 1)
        return namespace, bare
    return "", name


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
        try:
            with open(f, errors="replace") as fh:
                row = scan_lines(fh)
        except OSError:
            scanset["unreadable"] += 1
            continue
        row.update({"file": f, "sub": is_sub})
        rows.append(row)
    return rows, scanset


def scan_lines(lines):
    """Scan one context's records. Line order is event order.

    fired         skill -> count of Skill tool_use records (namespace stripped)
    first_fire    skill -> index of the first Skill tool_use record
    namespaces    namespace -> count, for plugin-form fires
    topics        skill -> index of the first record carrying its topic action
    active        skills seen on attributionSkill stamps
    reads         file paths read
    started       the first record timestamp (ISO-8601, as written)
    """
    fired, first_fire = collections.Counter(), {}
    namespaces = collections.Counter()
    active, reads, topics = set(), [], {}
    started, session = None, None
    for index, ln in enumerate(lines):
        for m in FIRE.finditer(ln):
            namespace, bare = normalize_skill_name(m.group(1))
            fired[bare] += 1
            first_fire.setdefault(bare, index)
            if namespace:
                namespaces[namespace] += 1
        for m in ATTR.finditer(ln):
            active.add(m.group(1))
        for m in READ.finditer(ln):
            reads.append(m.group(1))
        for skill, rx in TOPIC.items():
            if rx is not None and skill not in topics and rx.search(ln):
                topics[skill] = index
        if started is None and '"timestamp"' in ln:
            try:
                d = json.loads(ln)
                started = d.get("timestamp")
                session = d.get("sessionId") or d.get("session_id")
            except Exception:
                pass
    return {"fired": fired, "first_fire": first_fire, "namespaces": namespaces,
            "active": active, "reads": reads, "topics": topics,
            "started": started, "session": session}


def capture_table(rows, installed):
    """Per-skill capture as a per-context intersection.

    topic        contexts whose topic action appeared (the only eligible denominator)
    fired        contexts where the skill fired at all
    captured     contexts with BOTH topic and fire -- the numerator
    before       captured contexts where the first fire precedes the first topic action
    late         captured contexts where the fire followed the action
    over_fired   contexts that fired with no topic action: outside the denominator
    capture_pct  100 * captured / topic, or None when the skill has no action signal
    """
    table = {}
    for s in installed:
        has_signal = TOPIC.get(s) is not None
        topic = fired = captured = before = over = 0
        for r in rows:
            in_topic = s in r["topics"]
            did_fire = bool(r["fired"].get(s))
            topic += in_topic and has_signal
            fired += did_fire
            if did_fire and in_topic and has_signal:
                captured += 1
                if r["first_fire"][s] <= r["topics"][s]:
                    before += 1
            elif did_fire and has_signal:
                over += 1
        table[s] = {
            "signal": has_signal,
            "topic": topic if has_signal else None,
            "fired": fired,
            "captured": captured if has_signal else None,
            "before": before if has_signal else None,
            "late": (captured - before) if has_signal else None,
            "over_fired": over if has_signal else None,
            "capture_pct": (100 * captured // topic) if has_signal and topic else None,
        }
    return table


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

    # --- 1. firing, as a per-context intersection with topic-present
    p(f"\n1. DID SKILLS FIRE?   (denominator = topic-present contexts, out of {n} agent contexts)")
    p(f"   {'skill':<20}{'topic':>7}{'fired':>7}{'captured':>10}{'before':>8}"
      f"{'late':>6}{'over':>6}{'capture':>9}{'active':>8}")
    installed = sorted(os.path.basename(d) for d in glob.glob(SKILLS_DIR + "/*")
                       if os.path.isdir(d))
    table = capture_table(rows, installed)
    any_fire = 0
    for s in installed:
        t = table[s]
        ac = sum(1 for r in rows if s in r["active"])
        any_fire += t["fired"]
        if not t["signal"]:
            p(f"   {s:<20}{'no signal':>7}{t['fired']:>7}{'—':>10}{'—':>8}{'—':>6}{'—':>6}{'—':>9}{ac:>8}")
            continue
        cap = f"{t['capture_pct']}%" if t["capture_pct"] is not None else "—"
        flag = ""
        if t["topic"] and not t["captured"]:
            flag = "   <-- topic present, never fired in the same context"
        elif t["over_fired"]:
            flag = f"   <-- fired in {t['over_fired']} context(s) with no topic action"
        p(f"   {s:<20}{t['topic']:>7}{t['fired']:>7}{t['captured']:>10}{t['before']:>8}"
          f"{t['late']:>6}{t['over_fired']:>6}{cap:>9}{ac:>8}{flag}")
    p("   'no signal' = no ACTION distinguishes this skill's topic; capture is not computable.")
    p("   captured = topic AND fired in the SAME context; before/late = fire precedes/follows")
    p("   the first topic action; over = fired with no topic action (outside the denominator).")
    namespaces = collections.Counter()
    for r in rows:
        namespaces.update(r["namespaces"])
    if namespaces:
        p(f"   plugin-form fires normalized to bare names: {dict(namespaces)}")
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
            verdict = context_freshness(r["started"], md)
            fresh += verdict == "fresh"
            stale += verdict == "stale"
            unknown += verdict == "unknown"
        p(f"   CLAUDE.md mtime: {datetime.datetime.fromtimestamp(md, datetime.timezone.utc):%Y-%m-%d %H:%M}Z")
        p(f"   contexts started AFTER it (got current file): {fresh}")
        p(f"   contexts started BEFORE it (ran a stale copy): {stale}")
        p(f"   undatable: {unknown}")
        p("   NOTE: inferred from session-start (UTC) vs mtime. The injected block is NOT")
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
        print(f"  {'PASS' if ok else 'FAIL'} {label:<60} got={got!r}")

    def first(rx, text):
        m = rx.search(text)
        return m.group(1) if m else None

    fire_line = '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill","input":{"skill":"git-workflow"}}]}}'
    chk("FIRE matches a real Skill tool_use", first(FIRE, fire_line), "git-workflow")
    chk("FIRE does NOT match a mention of the word skill",
        FIRE.search('{"text":"I should use the git-workflow skill"}'), None)
    plug = '{"type":"tool_use","name":"Skill","input":{"skill":"myplugin:deploy"}}'
    chk("FIRE matches a plugin-form skill name", first(FIRE, plug), "myplugin:deploy")
    chk("ATTR matches attributionSkill", first(ATTR, '{"attributionSkill":"testing-ci"}'), "testing-ci")
    read_line = '{"type":"tool_use","name":"Read","input":{"file_path":"/opt/example/.claude/skills/testing-ci/references/deferred.md"}}'
    chk("READ extracts the path", "references/deferred.md" in (first(READ, read_line) or ""), True)
    gitcmd = '{"type":"tool_use","name":"Bash","input":{"command":"git status --porcelain"}}'
    chk("TOPIC git matches a git command that RAN", bool(TOPIC["git-workflow"].search(gitcmd)), True)
    chk("TOPIC git does NOT match prose about git",
        bool(TOPIC["git-workflow"].search('{"text":"explain what git rebase does"}')), False)
    chk("TOPIC git does NOT match a prompt asking for a commit (action, not intent)",
        bool(TOPIC["git-workflow"].search('{"type":"user","message":{"content":"Commit this change with git"}}')), False)
    ccf = '{"type":"tool_use","name":"Write","input":{"file_path":"/r/CLAUDE.md","content":"x"}}'
    chk("TOPIC craft-context-file matches an authored CLAUDE.md",
        bool(TOPIC["craft-context-file"].search(ccf)), True)
    chk("TOPIC craft-context-file does NOT match talking about CLAUDE.md",
        bool(TOPIC["craft-context-file"].search('{"text":"our CLAUDE.md is too long"}')), False)
    chk("skills with no action signal are None, not a guess", TOPIC["system-design"], None)

    # --- timestamps are UTC, never local wall-clock
    chk("timestamp: trailing Z parses as UTC",
        parse_transcript_timestamp("2026-10-15T20:00:00.000Z"), 1792094400.0)
    chk("timestamp: explicit offset is honored",
        parse_transcript_timestamp("2026-10-15T22:00:00+02:00"), 1792094400.0)
    chk("timestamp: naive string reads as UTC, not local",
        parse_transcript_timestamp("2026-10-15T20:00:00"), 1792094400.0)
    chk("timestamp: garbage is None, not an exception", parse_transcript_timestamp("yesterday"), None)
    chk("timestamp: non-string is None", parse_transcript_timestamp(1792094400), None)
    # The planted case: a context started at 20:00Z against a file written at 20:30Z is
    # STALE. Under a UTC-6 wall clock, time.mktime(strptime(...)) reads "20:00" as local,
    # which is 02:00Z the next day, and reports the context FRESH. Pin the zone so the
    # control discriminates on every host, and prove that the legacy formula disagrees
    # here -- otherwise this fixture could pass on a UTC runner with the defect intact.
    started, md_epoch = "2026-10-15T20:00:00.000Z", 1792096200.0   # 20:30:00Z
    previous_tz = os.environ.get("TZ")
    os.environ["TZ"] = "Etc/GMT+6"
    try:
        time.tzset()
        legacy = time.mktime(time.strptime(started[:19], "%Y-%m-%dT%H:%M:%S"))
        legacy_verdict = "fresh" if legacy >= md_epoch else "stale"
        verdict = context_freshness(started, md_epoch)
    finally:
        if previous_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous_tz
        time.tzset()
    chk("freshness control: the legacy local-time formula misreads the planted UTC case",
        legacy_verdict, "fresh")
    chk("freshness: a context started before the file's mtime is stale under any zone",
        verdict, "stale")
    chk("freshness: started after the mtime is fresh",
        context_freshness("2026-10-15T21:00:00Z", md_epoch), "fresh")
    chk("freshness: an undatable context is unknown, never counted either way",
        context_freshness(None, md_epoch), "unknown")

    # --- capture is a per-context intersection
    def context(lines):
        return scan_lines(lines)

    topic_only = context([gitcmd])
    fire_only = context([fire_line])
    both_late = context([gitcmd, '{"text":"x"}', fire_line])
    both_before = context([fire_line, gitcmd])
    installed = ["git-workflow", "system-design"]
    elsewhere = capture_table([topic_only, fire_only], installed)["git-workflow"]
    # The old formula divided fired-anywhere by topic-anywhere; on this pair that is 1/1.
    chk("capture control: the fired-anywhere formula reads this planted pair as 100%",
        100 * elsewhere["fired"] // elsewhere["topic"], 100)
    chk("capture: a fire in one context and a topic in another is 0% captured",
        (elsewhere["captured"], elsewhere["capture_pct"]), (0, 0))
    chk("capture: the topic-less fire is reported as over-firing, outside the denominator",
        (elsewhere["topic"], elsewhere["fired"], elsewhere["over_fired"]), (1, 1, 1))
    same = capture_table([both_late], installed)["git-workflow"]
    chk("capture: topic and fire in the same context count once",
        (same["topic"], same["fired"], same["captured"], same["capture_pct"]), (1, 1, 1, 100))
    chk("ordering: a fire after the first topic action is late, not before",
        (same["before"], same["late"]), (0, 1))
    early = capture_table([both_before], installed)["git-workflow"]
    chk("ordering: a fire before the first topic action counts as before",
        (early["before"], early["late"]), (1, 0))
    chk("eligibility: a skill with no action signal has no denominator",
        capture_table([both_late], installed)["system-design"]["capture_pct"], None)

    # --- namespace normalization
    plug_fire = '{"type":"tool_use","name":"Skill","input":{"skill":"z-harness:git-workflow"}}'
    namespaced = context([plug_fire, gitcmd])
    chk("namespace: a plugin-form fire counts for the bare skill name",
        namespaced["fired"]["git-workflow"], 1)
    chk("namespace: the namespace is tallied, not discarded",
        dict(namespaced["namespaces"]), {"z-harness": 1})
    chk("namespace: a bare name has no namespace", normalize_skill_name("git-workflow"), ("", "git-workflow"))
    chk("scan records the first timestamp as written",
        context(['{"timestamp":"2026-10-15T20:00:00.000Z","sessionId":"s1"}'])["started"],
        "2026-10-15T20:00:00.000Z")

    # zero-input arm
    rows, ss = [], {"root": ROOT, "files_found": 0, "cutoff_epoch": 0,
                    "files_in_window": 0, "subagent_files": 0, "unreadable": 0}
    import io
    buf = io.StringIO()
    rc = report(rows, ss, out=buf)
    chk("zero contexts exits 2, not 0", rc, 2)
    chk("zero contexts says so out loud", "ZERO CONTEXTS" in buf.getvalue(), True)
    print(f"\n  {checks} checks, {bad} failures")
    print(f"SELFTEST-SUMMARY suite=harness_report checks={checks} failures={bad}")
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
