#!/usr/bin/env python3
"""harness_check — the mechanical gate for this harness's authored surface.

Runs from either clone (repo root auto-detected from this file's location). Checks:

  C1  guard/report/accounting selftests all exit 0
  C2  shared-corpus reference copies are byte-identical across skills, and any
      basename appearing in >=2 skills is either SHARED or explicitly PER_SKILL —
      an unknown multi-skill basename fails loud
  C3  reference resolution, both directions: every references/ path a SKILL.md
      names exists; every file under references/ is named by its SKILL.md,
      literally or via a <param> template family
  C4  every description <= 400 chars (house cap inside the 1024 spec ceiling)
  C5  method-skill bodies <= 5,000 chars after frontmatter; authoring-skill
      bodies <= 500 lines
  C6  stale-claim tripwires: patterns that once shipped false stay at zero in
      live channels (skills/, hooks/, tools/, AGENTS.md, CLAUDE.md)
  C7  anchors: routing-table skills exist; Claude and Codex hook commands resolve;
      [local] original audit paths exist, `timeout` still absent, askq binary
      anchors hold
  C8  reserved context basenames (CLAUDE.md/AGENTS.md/GEMINI.md) exist nowhere
      but the repo root
  C9  Codex package contract: manifest, marketplace, hook config, context bridges,
      and their size budgets are internally consistent

Exit codes: 0 all checks pass · 1 one or more checks failed · 2 usage error or
zero inputs (an empty scan set is an error, never a clean verdict).

  harness_check.py             run every check (local mode)
  harness_check.py --ci        skip [local]-tagged checks (no ~/.claude, no
                               claude binary, no launchd on the runner)
  harness_check.py --selftest  prove each check can go RED on a planted-defect
                               tree, then exit
"""
import json
import os
import re
import subprocess
import sys
import tempfile

VERSION = "2.0.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

METHOD_SKILLS = ["git-workflow", "pr-review-method", "testing-ci", "agent-dispatch",
                 "outbound-drafts", "system-design", "prebid-adcp"]
AUTHORING_SKILLS = ["craft-prompt", "craft-skill", "craft-context-file", "review-prompt"]
BODY_CHAR_CAP = 5000          # chars after frontmatter — the builders' instrument
BODY_LINE_CAP = 500           # authoring skills (spec cap)
DESC_CAP = 400                # house cap (spec ceiling is 1024)

# C2: basenames shared verbatim across skills. A same-basename file NOT listed in
# either set is a loud failure — decide SHARED vs PER_SKILL and add it here.
SHARED_BASENAMES = {
    "anti-patterns.md", "skill-authoring.md", "description-archetypes.md",
    "untrusted-content.md", "uncertainty.md", "scope-discipline.md",
    "persistence.md", "action-default.md", "context-file.md",
    "claude-code.md", "codex.md",
    "stance-explore.md", "stance-implement.md", "stance-operate.md",
    "stance-plan.md", "stance-review.md",
    "model-claude.md", "model-gemini.md", "model-gpt.md", "model-neutral.md",
}
PER_SKILL_BASENAMES = {"deferred.md"}   # same name, deliberately different content

# C6: each of these shipped false at least once. The live channels stay at zero.
# (This file is excluded from its own sweep.)
STALE_PATTERNS = [
    "NOT INSTALLED",            # guards claimed dormant while live
    "NOT applied",              # applied proposals claiming to be pending
    "not in the live file yet", # delivered rule claiming undelivered
    "all 24 rows",              # catalog count drift
    "description >1024",        # row-16 cap drift
    "72 further rank-A",        # deferred-count drift
    "(like this one)",          # birth-repo deictic
    "ph-mcp-server",            # birth-repo tooling
    "docs/research/",           # birth-repo paths
    "claude-md-lines",          # retired reference
    "ph-lint",                  # linter that never existed here
]

ROUTING_SKILLS = ["git-workflow", "pr-review-method", "testing-ci", "agent-dispatch",
                  "prebid-adcp", "system-design", "outbound-drafts",
                  "craft-prompt", "craft-skill", "craft-context-file", "review-prompt"]

RESERVED_BASENAMES = {"claude.md", "agents.md", "gemini.md"}


def body_chars(path):
    t = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n.*?\n---\n", t, re.S)
    return len(t[m.end():]) if m else len(t)


def description_of(path):
    t = open(path, encoding="utf-8").read()
    m = re.search(r"^description: (.+)$", t, re.M)
    return m.group(1) if m else ""


class Run:
    def __init__(self, root, ci):
        self.root, self.ci, self.failures, self.checks = root, ci, [], 0

    def result(self, check, ok, detail):
        self.checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} {check:4s} {detail}")
        if not ok:
            self.failures.append((check, detail))

    # ---- C1 ----------------------------------------------------------------
    def c1_selftests(self):
        suites = [("bash_command_guard", ["hooks/bash_command_guard.py", "--selftest"]),
                  ("askq_timeout_guard", ["hooks/askq_timeout_guard.py", "--selftest"]),
                  ("harness_report", ["hooks/harness_report.py", "--selftest"]),
                  ("cc-cost", ["tools/cc-cost.py", "--selftest"]),
                  ("codex-cost", ["tools/codex-cost.py", "--selftest"]),
                  ("codex_session_start", ["hooks/codex_session_start.py", "--selftest"]),
                  ("spawn_preflight_guard", ["hooks/spawn_preflight_guard.py", "--selftest"])]
        for name, cmd in suites:
            p = subprocess.run([sys.executable, os.path.join(self.root, cmd[0])] + cmd[1:],
                               capture_output=True, cwd=self.root)
            self.result("C1", p.returncode == 0, f"selftest {name}: exit {p.returncode}")

    # ---- C2 ----------------------------------------------------------------
    def c2_shared_identity(self):
        import hashlib
        by_base = {}
        skills_dir = os.path.join(self.root, "skills")
        for skill in sorted(os.listdir(skills_dir)):
            refdir = os.path.join(skills_dir, skill, "references")
            if not os.path.isdir(refdir):
                continue
            for f in sorted(os.listdir(refdir)):
                p = os.path.join(refdir, f)
                if os.path.isfile(p):
                    by_base.setdefault(f, []).append(p)
        multi = {b: ps for b, ps in by_base.items() if len(ps) > 1}
        for base, paths in sorted(multi.items()):
            if base in PER_SKILL_BASENAMES:
                continue
            if base not in SHARED_BASENAMES:
                self.result("C2", False,
                            f"{base}: in {len(paths)} skills but in neither SHARED nor "
                            f"PER_SKILL — classify it")
                continue
            hs = {hashlib.md5(open(p, 'rb').read()).hexdigest() for p in paths}
            self.result("C2", len(hs) == 1,
                        f"{base}: {len(paths)} copies "
                        f"{'identical' if len(hs) == 1 else 'DIVERGED'}")
        missing = SHARED_BASENAMES - set(by_base)
        if missing:
            self.result("C2", False, f"SHARED basenames absent from tree: {sorted(missing)}")

    # ---- C3 ----------------------------------------------------------------
    def c3_reference_resolution(self):
        skills_dir = os.path.join(self.root, "skills")
        for skill in sorted(os.listdir(skills_dir)):
            body_path = os.path.join(skills_dir, skill, "SKILL.md")
            if not os.path.isfile(body_path):
                continue
            body = open(body_path, encoding="utf-8").read()
            refdir = os.path.join(skills_dir, skill, "references")
            cited = set(re.findall(r"references/([\w<>.\-]+\.(?:md|yaml))", body))
            literal = {c for c in cited if "<" not in c}
            template_res = [re.compile("^" + re.sub(r"<[^>]*>", r"[\\w.\\-]+", re.escape(c)) + "$")
                            for c in cited if "<" in c]
            # direction 1: cited -> exists
            for c in sorted(literal):
                p = os.path.join(refdir, c)
                self.result("C3", os.path.isfile(p), f"{skill}: cites references/{c}")
            # direction 2: exists -> cited (literal or template family)
            if os.path.isdir(refdir):
                for f in sorted(os.listdir(refdir)):
                    if not os.path.isfile(os.path.join(refdir, f)):
                        continue
                    ok = f in literal or any(t.match(f) for t in template_res)
                    self.result("C3", ok, f"{skill}: references/{f} "
                                          f"{'reachable' if ok else 'NAMED NOWHERE in SKILL.md'}")

    # ---- C4 / C5 -----------------------------------------------------------
    def c4_descriptions(self):
        for skill in METHOD_SKILLS + AUTHORING_SKILLS:
            p = os.path.join(self.root, "skills", skill, "SKILL.md")
            n = len(description_of(p))
            self.result("C4", 0 < n <= DESC_CAP, f"{skill}: description {n} chars (cap {DESC_CAP})")

    def c5_bodies(self):
        for skill in METHOD_SKILLS:
            n = body_chars(os.path.join(self.root, "skills", skill, "SKILL.md"))
            self.result("C5", n <= BODY_CHAR_CAP,
                        f"{skill}: body {n} chars (cap {BODY_CHAR_CAP})")
        for skill in AUTHORING_SKILLS:
            p = os.path.join(self.root, "skills", skill, "SKILL.md")
            n = len(open(p, encoding="utf-8").read().splitlines())
            self.result("C5", n <= BODY_LINE_CAP, f"{skill}: {n} lines (cap {BODY_LINE_CAP})")

    # ---- C6 ----------------------------------------------------------------
    def c6_stale_patterns(self):
        me = os.path.abspath(__file__)
        targets = []
        for rel in ("skills", "hooks", "tools"):
            for dirpath, _dirs, files in os.walk(os.path.join(self.root, rel)):
                if "__pycache__" in dirpath:
                    continue
                targets += [os.path.join(dirpath, f) for f in files
                            if not f.endswith((".pyc", ".jsonl"))]
        targets += [os.path.join(self.root, name) for name in ("AGENTS.md", "CLAUDE.md")
                    if os.path.isfile(os.path.join(self.root, name))]
        targets = [t for t in targets if os.path.abspath(t) != me]
        if not targets:
            print("  FATAL C6: zero files in scan set")
            self.failures.append(("C6", "zero files"))
            return
        for pat in STALE_PATTERNS:
            hits = [t for t in targets
                    if pat in open(t, encoding="utf-8", errors="replace").read()]
            self.result("C6", not hits,
                        f"tripwire {pat!r}: {len(hits)} hit(s)"
                        + (f" e.g. {os.path.relpath(hits[0], self.root)}" if hits else ""))

    # ---- C7 ----------------------------------------------------------------
    def c7_anchors(self):
        for skill in ROUTING_SKILLS:
            p = os.path.join(self.root, "skills", skill)
            self.result("C7", os.path.isdir(p), f"routing-table skill exists: {skill}")
        st = json.load(open(os.path.join(self.root, "settings.json")))
        for event, entries in st.get("hooks", {}).items():
            for entry in entries:
                for h in entry.get("hooks", []):
                    cmd = h.get("command", "")
                    m = re.search(r"~/[\w./\-]+\.(?:py|sh)", cmd)
                    if not m:
                        continue
                    rel = m.group(0).replace("~/.claude/", "")
                    p = os.path.join(self.root, rel)
                    self.result("C7", os.path.isfile(p), f"settings {event} -> {rel}")
                    self.result("C7", "timeout" in h,
                                f"settings {event} {rel}: timeout set")
        codex_hooks_path = os.path.join(self.root, "hooks", "hooks.json")
        try:
            codex_hooks = json.load(open(codex_hooks_path))
        except Exception as exc:
            self.result("C7", False, f"Codex hooks config parses: {exc}")
            codex_hooks = {}
        codex_commands = 0
        for event, entries in codex_hooks.get("hooks", {}).items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    command = hook.get("command", "")
                    match = re.search(r"\$\{PLUGIN_ROOT\}/([\w./\-]+\.(?:py|sh))", command)
                    if not match:
                        self.result("C7", False,
                                    f"Codex {event}: command has no PLUGIN_ROOT script anchor")
                        continue
                    codex_commands += 1
                    rel = match.group(1)
                    self.result("C7", os.path.isfile(os.path.join(self.root, rel)),
                                f"Codex {event} -> {rel}")
                    self.result("C7", "timeout" in hook,
                                f"Codex {event} {rel}: timeout set")
        self.result("C7", codex_commands > 0,
                    f"Codex hook commands discovered: {codex_commands}")
        if not self.ci:
            fp = os.path.expanduser("~/.claude/harness-audit-20260801/FINDINGS.md")
            self.result("C7", os.path.isfile(fp),
                        "[local] original harness-audit FINDINGS.md exists")
            w = subprocess.run(["which", "timeout"], capture_output=True)
            self.result("C7", w.returncode != 0,
                        "[local] `timeout` still absent (AGENTS.md claims it is)")
            v = subprocess.run([sys.executable,
                                os.path.join(self.root, "hooks/askq_timeout_guard.py"),
                                "--verify-harness"], capture_output=True)
            self.result("C7", v.returncode == 0,
                        f"[local] askq --verify-harness: exit {v.returncode}")

    # ---- C8 ----------------------------------------------------------------
    def c8_reserved_basenames(self):
        hits = []
        for dirpath, dirs, files in os.walk(self.root):
            if ".git" in dirpath:
                continue
            for f in files:
                if f.lower() in RESERVED_BASENAMES:
                    p = os.path.join(dirpath, f)
                    if os.path.dirname(os.path.abspath(p)) != os.path.abspath(self.root):
                        hits.append(os.path.relpath(p, self.root))
        self.result("C8", not hits, f"reserved basenames outside root: {hits or 'none'}")

    # ---- C9 ----------------------------------------------------------------
    def c9_codex_package(self):
        manifest_path = os.path.join(self.root, ".codex-plugin", "plugin.json")
        marketplace_path = os.path.join(self.root, ".agents", "plugins", "marketplace.json")
        try:
            manifest = json.load(open(manifest_path))
        except Exception as exc:
            self.result("C9", False, f"plugin manifest parses: {exc}")
            manifest = {}
        plugin_name = manifest.get("name")
        self.result("C9", bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",
                                           str(plugin_name or ""))),
                    f"manifest name is kebab-case: {plugin_name!r}")
        self.result("C9", bool(re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?",
                                           str(manifest.get("version", "")))),
                    f"manifest version is semver: {manifest.get('version')!r}")
        self.result("C9", manifest.get("skills") == "./skills/",
                    "manifest skills path is ./skills/")
        self.result("C9", os.path.isfile(os.path.join(self.root, "hooks", "hooks.json")),
                    "default plugin hook config exists")

        try:
            marketplace = json.load(open(marketplace_path))
        except Exception as exc:
            self.result("C9", False, f"marketplace parses: {exc}")
            marketplace = {}
        entries = [entry for entry in marketplace.get("plugins", [])
                   if entry.get("name") == plugin_name]
        self.result("C9", len(entries) == 1,
                    f"marketplace has one {plugin_name!r} entry: {len(entries)}")
        if entries:
            source = entries[0].get("source") or {}
            url = source.get("url", "")
            self.result("C9", source.get("source") == "url" and
                        url.startswith("https://github.com/") and "@" not in url.split("//", 1)[-1],
                        "marketplace uses a credential-free GitHub URL source")
            policy = entries[0].get("policy") or {}
            self.result("C9", policy.get("installation") == "AVAILABLE" and
                        policy.get("authentication") == "ON_INSTALL",
                        "marketplace install/auth policy is explicit")

        agents_path = os.path.join(self.root, "AGENTS.md")
        claude_path = os.path.join(self.root, "CLAUDE.md")
        try:
            agents_bytes = open(agents_path, "rb").read()
        except OSError:
            agents_bytes = b""
        try:
            claude_text = open(claude_path, encoding="utf-8").read()
        except OSError:
            claude_text = ""
        self.result("C9", 0 < len(agents_bytes) < 32 * 1024,
                    f"AGENTS.md {len(agents_bytes)} bytes (cap <32768)")
        self.result("C9", claude_text.startswith("@AGENTS.md\n") and
                    len(claude_text.splitlines()) < 200,
                    f"CLAUDE.md bridges AGENTS.md in {len(claude_text.splitlines())} lines")

    def run(self):
        print(f"harness_check {VERSION}  root={self.root}  mode={'ci' if self.ci else 'local'}")
        self.c1_selftests()
        self.c2_shared_identity()
        self.c3_reference_resolution()
        self.c4_descriptions()
        self.c5_bodies()
        self.c6_stale_patterns()
        self.c7_anchors()
        self.c8_reserved_basenames()
        self.c9_codex_package()
        print(f"\n  {self.checks} checks, {len(self.failures)} failure(s)")
        if self.checks == 0:
            print("  ZERO CHECKS RAN — error, not a clean verdict")
            return 2
        if self.failures:
            for c, d in self.failures:
                print(f"    - {c}: {d}")
            return 1
        return 0


# ---- selftest: every check proves it can go red -------------------------------
def selftest():
    bad = 0

    def expect_red(label, fn):
        nonlocal bad
        try:
            ok = fn()
        except Exception as e:
            ok = False
            print(f"  FAIL {label}: raised {e!r}")
            bad += 1
            return
        print(f"  {'PASS' if ok else 'FAIL'} {label}")
        bad += (not ok)

    with tempfile.TemporaryDirectory() as td:
        # minimal planted-defect tree
        sk = os.path.join(td, "skills")
        for s, desc in [("alpha", "x" * 500), ("beta", "ok")]:   # alpha desc over cap
            os.makedirs(os.path.join(sk, s, "references"))
            open(os.path.join(sk, s, "SKILL.md"), "w").write(
                f"---\nname: {s}\ndescription: {desc}\n---\n\nRead references/present.md\n"
                + ("z" * 6000 if s == "alpha" else ""))
        # C2 red: shared basename diverges
        open(os.path.join(sk, "alpha/references/anti-patterns.md"), "w").write("v1")
        open(os.path.join(sk, "beta/references/anti-patterns.md"), "w").write("v2")
        # C3 red: cited file absent in alpha; orphan file in beta
        open(os.path.join(sk, "beta/references/present.md"), "w").write("ok")
        open(os.path.join(sk, "beta/references/orphan.md"), "w").write("named nowhere")
        # C6 red: stale pattern planted
        os.makedirs(os.path.join(td, "hooks"))
        open(os.path.join(td, "hooks/stale.md"), "w").write("this guard is NOT INSTALLED")
        # C8 red: nested reserved basename
        os.makedirs(os.path.join(td, "sub"))
        open(os.path.join(td, "CLAUDE.md"), "w").write("root")
        open(os.path.join(td, "AGENTS.md"), "w").write("root")
        open(os.path.join(td, "sub", "claude.md"), "w").write("collision")
        open(os.path.join(td, "settings.json"), "w").write("{}")

        r = Run(td, ci=True)
        r.c2_shared_identity()
        expect_red("C2 goes red on diverged copies",
                   lambda: any(c == "C2" and "DIVERGED" in d for c, d in r.failures))
        r.c3_reference_resolution()
        expect_red("C3 goes red on missing cited file",
                   lambda: any(c == "C3" and "alpha" in d for c, d in r.failures))
        expect_red("C3 goes red on orphan file",
                   lambda: any(c == "C3" and "orphan.md" in d for c, d in r.failures))
        r2 = Run(td, ci=True)
        r2.checks = 0
        for s in ["alpha"]:
            n = len(description_of(os.path.join(sk, s, "SKILL.md")))
            r2.result("C4", 0 < n <= DESC_CAP, f"{s}: {n}")
            b = body_chars(os.path.join(sk, s, "SKILL.md"))
            r2.result("C5", b <= BODY_CHAR_CAP, f"{s}: {b}")
        expect_red("C4 goes red on 500-char description",
                   lambda: any(c == "C4" for c, d in r2.failures))
        expect_red("C5 goes red on 6,000-char body",
                   lambda: any(c == "C5" for c, d in r2.failures))
        r3 = Run(td, ci=True)
        r3.c6_stale_patterns()
        expect_red("C6 goes red on planted stale pattern",
                   lambda: any(c == "C6" and "NOT INSTALLED" in d for c, d in r3.failures))
        r4 = Run(td, ci=True)
        r4.c8_reserved_basenames()
        expect_red("C8 goes red on nested claude.md",
                   lambda: any(c == "C8" for c, d in r4.failures))
        r5 = Run(td, ci=True)
        r5.c9_codex_package()
        expect_red("C9 goes red on absent plugin package",
                   lambda: any(c == "C9" for c, d in r5.failures))

    print(f"\n  selftest: {bad} failure(s)")
    return 1 if bad else 0


def main(argv):
    args = argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if args and args[0] == "--version":
        print(f"harness_check {VERSION}")
        return 0
    if args and args[0] == "--selftest":
        return selftest()
    ci = False
    if args and args[0] == "--ci":
        ci = True
        args = args[1:]
    if args:
        sys.stderr.write(f"unknown argument: {args[0]!r}\nrun --help\n")
        return 2
    return Run(ROOT, ci).run()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
