#!/usr/bin/env python3
"""credential_reach_guard — who may reach a credential or another model from Bash.

Maintainer rule (2026-10-09): never reach for credentials or call another model without
explicit permission; only the maintainer calls other models, except a harness run as a
workload while testing or building the platform.

The verdict depends on the caller, which only the hook payload carries, so this predicate
takes the caller as input and is run by bash_command_guard.evaluate_payload, not by the
command-only GUARDS list:
  subagent (payload carries agent_id)   any credential or model use found  -> deny
  main thread, claude runtime           another model's CLI, a secret store -> ask
                                        other credential use (gh for PR work) -> allow
  main thread, codex runtime            allow (Codex cannot ask; outside this rule)

Spellings modelled, per simple command after env assignments and the wrappers in WRAPPERS:
a listed CLI at command position; a listed CLI run through npx/bunx/pnpx/uvx/pipx run/
pnpm dlx/npm exec; `sh|bash|zsh -c BODY`, `eval BODY` and heredoc bodies fed to a shell
(judged recursively); command substitutions (the shared tokenizer splits them out);
argv list literals naming a listed CLI (python or node heredocs); credential file paths
anywhere in the text; credential variable assignments; curl/wget/httpie authentication
options; git network subcommands; keychain secret reads.
Not modelled (a stated limit, not a clean verdict): a script file or program that runs a
credentialed command without naming it in this text; aliases or functions defined earlier;
a CLI copied or linked under another name.
"""
import os
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import git_grep_engine_guard as tokenizer   # noqa: E402  (split_commands only)

MODEL_CLIS = {"codex", "hermes", "claude", "gemini", "aider", "opencode", "cursor-agent",
              "llm"}
CREDENTIAL_CLIS = {"gh", "wrangler", "tailscale", "aws", "gcloud", "gsutil", "bq", "az",
                   "op", "doctl", "flyctl", "vercel", "netlify", "heroku", "kubectl", "helm",
                   "twine"}
# package names that run a listed CLI through a package runner
PACKAGE_ALIASES = {"claude-code": "claude", "@anthropic-ai/claude-code": "claude",
                   "@openai/codex": "codex", "@google/gemini-cli": "gemini"}
INFO_ONLY = {"--version", "-V", "-v", "--help", "-h", "help", "version"}
GIT_NETWORK = {"push", "pull", "fetch", "clone", "ls-remote"}
GIT_REMOTE_NETWORK = {"update", "prune", "show"}
KEYCHAIN_READS = {"find-generic-password", "find-internet-password", "dump-keychain",
                  "export"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
RUNNERS = {"npx", "bunx", "pnpx", "uvx"}
# wrapper -> options that consume the next word; the first other word is the command
WRAPPERS = {
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"},
    "command": set(), "exec": {"-a"}, "nohup": set(), "time": set(), "doas": {"-u"},
    "nice": {"-n", "--adjustment"}, "ionice": {"-c", "-n"},
    "timeout": {"-k", "--kill-after", "-s", "--signal"},
    "gtimeout": {"-k", "--kill-after", "-s", "--signal"},
    "sudo": {"-u", "--user", "-g", "--group", "-C", "-D", "--chdir", "-h", "--host",
             "-p", "--prompt", "-r", "--role", "-t", "--type", "-U", "--other-user"},
    "caffeinate": {"-t", "-w"}, "stdbuf": {"-i", "-o", "-e"}, "setsid": set(),
    "xargs": {"-I", "-L", "-n", "-P", "-s", "-d", "-E", "-a"}, "unbuffer": set(),
}
NUMERIC_FIRST = {"timeout", "gtimeout"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
CREDENTIAL_VARS = re.compile(
    r"(?<![A-Za-z0-9_])(GH_TOKEN|GITHUB_TOKEN|GH_ENTERPRISE_TOKEN|ANTHROPIC_API_KEY|"
    r"OPENAI_API_KEY|CLAUDE_CODE_OAUTH_TOKEN|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN|"
    r"CLOUDFLARE_API_TOKEN|TS_AUTHKEY|TAILSCALE_AUTHKEY)=")
CREDENTIAL_PATH = re.compile(
    r"\.(?:codex/auth\.json|hermes/auth\.json|hermes/\.env|config/gh/hosts\.yml|"
    r"claude/\.credentials\.json|aws/credentials|config/anthropic|wrangler/config|"
    r"docker/config\.json|kube/config|git-credentials|npmrc|pypirc)\b"
    r"|/\.netrc\b|\.ssh/id_[A-Za-z0-9_]+(?!\.pub)\b")
ARGV_LITERAL = re.compile(
    r"[\[\(,]\s*[\"'](?:gh|codex|hermes|claude|wrangler|tailscale|aws|gcloud)[\"']\s*[,\]\)]")
AUTH_HEADER = re.compile(r"(?i)^\s*(?:proxy-)?authorization\s*:|^\s*x-api-key\s*:|"
                         r"^\s*api-key\s*:|^\s*cookie\s*:")
CURL_AUTH_FLAGS = {"-u", "--user", "--oauth2-bearer", "--aws-sigv4", "-n", "--netrc",
                   "--netrc-file", "--netrc-optional", "-b", "--cookie", "-E", "--cert"}
WGET_AUTH_FLAGS = {"--http-user", "--http-password", "--user", "--password",
                   "--load-cookies", "--ask-password"}
HEREDOC = re.compile(r"(?m)^(?P<lead>[^\n]*?)<<-?\s*'?\"?(?P<tag>[A-Za-z_][A-Za-z0-9_]*)'?\"?"
                     r"[^\n]*\n(?P<body>.*?)\n(?P=tag)\b", re.S)
MAX_DEPTH = 4
# Main-thread fallback when the tokenizer cannot read the command: a model CLI name as a word.
MODEL_WORD = re.compile(r"(?<![\w./-])(?:codex|hermes|claude|gemini|aider|opencode|cursor-agent)"
                        r"(?![\w-])")


def _split(text):
    """Tokenize, or None when the shared tokenizer cannot read the text."""
    try:
        return tokenizer.split_commands(text)
    except Exception:                              # CommandParseError and kin
        return None


def _base(word):
    return os.path.basename(word)


def _command_word(words):
    """Strip env assignments and wrappers -> (assignments, remaining words)."""
    assigns, i, guard = [], 0, 0
    while i < len(words) and guard < 32:
        guard += 1
        while i < len(words) and ASSIGNMENT.match(words[i]):
            assigns.append(words[i])
            i += 1
        if i >= len(words):
            break
        name = _base(words[i])
        if name == "command" and i + 1 < len(words) and words[i + 1] in {"-v", "-V"}:
            return assigns, []                      # a lookup, not an execution
        if name in WRAPPERS:
            consumes = WRAPPERS[name]
            i += 1
            while i < len(words) and words[i].startswith("-") and words[i] != "-":
                i += 2 if words[i] in consumes else 1
            if name in NUMERIC_FIRST and i < len(words):
                i += 1                              # the duration operand
            continue
        if name in {"python", "python3"} and i + 1 < len(words) \
                and _base(words[i + 1]) == "bounded.py":
            i += 3 if i + 2 < len(words) else 2     # interpreter, script, seconds
            continue
        break
    return assigns, words[i:]


def _runner_target(name, rest):
    """For a package runner, the package it runs, mapped to a CLI name."""
    args = list(rest)
    if name == "pipx" and args[:1] == ["run"]:
        args = args[1:]
    elif name == "pnpm" and args[:1] == ["dlx"]:
        args = args[1:]
    elif name == "npm" and args[:1] in (["exec"], ["x"]):
        args = args[1:]
    elif name not in RUNNERS:
        return None
    for word in args:
        if word == "--":
            continue
        if word.startswith("-"):
            continue
        pkg = re.sub(r"(?<=.)@[^/@]*$", "", word)   # drop a trailing @version
        return PACKAGE_ALIASES.get(pkg, _base(pkg))
    return None


def _findings_for(words, depth):
    """Findings for one simple command as (kind, detail). kind: model|secret|cred."""
    out = []
    assigns, rest = _command_word(words)
    for item in assigns:
        if CREDENTIAL_VARS.match(item):
            out.append(("cred", f"credential variable {item.split('=', 1)[0]}"))
    if not rest:
        return out
    name, args = _base(rest[0]), rest[1:]
    target = _runner_target(name, args)
    if target is not None:
        name, args = target, []
    if name in SHELLS:
        for j, word in enumerate(args):
            if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", word) and j + 1 < len(args):
                out.extend(_scan(args[j + 1], depth + 1))
                break
        return out
    if name == "eval" and args:
        return out + _scan(" ".join(args), depth + 1)
    if name in MODEL_CLIS:
        if not (args and all(a in INFO_ONLY for a in args)):
            out.append(("model", f"{name} (another model's CLI)"))
        return out
    if name in CREDENTIAL_CLIS:
        if not (args and all(a in INFO_ONLY for a in args)):
            out.append(("cred", f"{name} (uses a stored credential)"))
        return out
    if name == "git":
        sub = [a for a in args if not a.startswith("-")]
        k = 0
        while k + 1 < len(args) and args[k] in {"-C", "-c", "--git-dir", "--work-tree"}:
            k += 2
        verb = args[k] if k < len(args) else (sub[0] if sub else "")
        nxt = args[k + 1] if k + 1 < len(args) else ""
        if verb in GIT_NETWORK or (verb == "remote" and nxt in GIT_REMOTE_NETWORK):
            out.append(("cred", f"git {verb} (network operation using a credential helper)"))
        return out
    if name == "security" and args[:1] and args[0] in KEYCHAIN_READS:
        out.append(("secret", f"security {args[0]} (keychain secret read)"))
        return out
    if name == "curl":
        for j, word in enumerate(args):
            value = args[j + 1] if j + 1 < len(args) else ""
            if word in {"-H", "--header"} and AUTH_HEADER.search(value):
                out.append(("cred", "curl with an authentication header"))
            elif word.startswith("-H") and len(word) > 2 and AUTH_HEADER.search(word[2:]):
                out.append(("cred", "curl with an authentication header"))
            elif word.startswith("--header=") and AUTH_HEADER.search(word[9:]):
                out.append(("cred", "curl with an authentication header"))
            elif word in CURL_AUTH_FLAGS or word.split("=", 1)[0] in CURL_AUTH_FLAGS - {"-u", "-n", "-b", "-E"}:
                out.append(("cred", f"curl {word.split('=', 1)[0]} (credential option)"))
        return out
    if name == "wget":
        for j, word in enumerate(args):
            value = args[j + 1] if j + 1 < len(args) else ""
            head = word.split("=", 1)
            if (word == "--header" and AUTH_HEADER.search(value)) or \
                    (head[0] == "--header" and len(head) == 2 and AUTH_HEADER.search(head[1])):
                out.append(("cred", "wget with an authentication header"))
            elif head[0] in WGET_AUTH_FLAGS:
                out.append(("cred", f"wget {head[0]} (credential option)"))
        return out
    if name in {"http", "https", "xh"}:
        if any(AUTH_HEADER.search(a) for a in args) or any(a in {"-a", "--auth"} for a in args):
            out.append(("cred", f"{name} with authentication"))
        return out
    return out


def _scan(text, depth=0):
    """All findings in a command text, judged recursively up to MAX_DEPTH."""
    if depth > MAX_DEPTH:
        return [("cred", "nesting deeper than the guard follows")]
    findings = []
    for m in CREDENTIAL_PATH.finditer(text):
        findings.append(("secret", f"credential file {m.group(0)}"))
    for m in ARGV_LITERAL.finditer(text):
        findings.append(("cred", f"argv literal naming {m.group(0).strip('[(, ')}"))
    for m in HEREDOC.finditer(text):
        lead = _split(m.group("lead") or ":")
        if lead is None:
            findings.append(("unparsed", "a heredoc whose consumer the tokenizer cannot read"))
            continue
        _assigns, rest = _command_word([w for w, _q in sum(lead, [])])
        if rest and _base(rest[0]) in SHELLS:
            findings.extend(_scan(m.group("body"), depth + 1))
    simples = _split(text)
    if simples is None:
        findings.append(("unparsed", "command source the shared tokenizer cannot read"))
        if MODEL_WORD.search(text):
            findings.append(("model", "a model CLI name in unreadable command source"))
        return findings
    for simple in simples:
        findings.extend(_findings_for([w for w, _q in simple], depth))
    return findings


def decide(command, *, subagent, runtime="claude"):
    """-> (decision, reason) for this caller."""
    findings = _scan(command)
    if not findings:
        return "allow", ""
    seen, details = set(), []
    for kind, detail in findings:
        if (kind, detail) not in seen:
            seen.add((kind, detail))
            details.append((kind, detail))
    if subagent:
        return "deny", ("credential_reach: subagents may not use a credential or call another "
                        "model without the maintainer's explicit permission. Found: "
                        + "; ".join(d for _k, d in details)
                        + ". Report what you need to the main thread instead.")
    # "unparsed" alone does not ask on the main thread: the command guards already grade
    # unreadable source, and the MODEL_WORD fallback above covers a model CLI inside it.
    asks = [d for k, d in details if k in {"model", "secret"}]
    if runtime == "claude" and asks:
        return "ask", ("credential_reach: this calls another model or reads a stored secret ("
                       + "; ".join(asks) + "). Only the maintainer approves that.")
    return "allow", ""


# (label, command, caller, runtime, expected)
FIXTURES = [
    # subagent: every modelled spelling is denied
    ("RED  sub gh at command position", "gh pr list --repo o/r", "sub", "claude", "deny"),
    ("RED  sub gh api read", "gh api repos/o/r/contents/x -H 'Accept: application/vnd.github.raw'", "sub", "claude", "deny"),
    ("RED  sub token in substitution", "GH_TOKEN=$(gh auth token --user x) curl -sS https://api.github.com", "sub", "claude", "deny"),
    ("RED  sub substitution inside quotes", 'echo "$(gh auth token)"', "sub", "claude", "deny"),
    ("RED  sub codex behind sudo", 'cd a && sudo -n codex exec "hi"', "sub", "claude", "deny"),
    ("RED  sub codex behind bounded wrapper", "python3 /x/bounded.py 300 codex --search exec -s read-only 'p'", "sub", "claude", "deny"),
    ("RED  sub codex through npx", "npx -y @openai/codex@latest exec 'hi'", "sub", "claude", "deny"),
    ("RED  sub claude through pnpm dlx", "pnpm dlx @anthropic-ai/claude-code -p hi", "sub", "claude", "deny"),
    ("RED  sub claude print", "claude -p 'summarise' < notes.md", "sub", "claude", "deny"),
    ("RED  sub hermes chat", "hermes chat -q hello", "sub", "claude", "deny"),
    ("RED  sub nested bash -lc", 'bash -lc "gh api user"', "sub", "claude", "deny"),
    ("RED  sub nested zsh -c with wrapper", "env FOO=1 zsh -c 'timeout 30 codex exec x'", "sub", "claude", "deny"),
    ("RED  sub eval body", 'eval "gh repo view"', "sub", "claude", "deny"),
    ("RED  sub heredoc fed to bash", "bash <<'EOF'\nset -e\ngh api user\nEOF", "sub", "claude", "deny"),
    ("RED  sub python argv literal", "python3 - <<'EOF'\nimport subprocess\nsubprocess.run(['gh', 'api', 'user'])\nEOF", "sub", "claude", "deny"),
    ("RED  sub reads codex auth file", "cat ~/.codex/auth.json | head -c 50", "sub", "claude", "deny"),
    ("RED  sub python reads hermes auth", "python3 - <<'EOF'\nimport json,os\njson.load(open(os.path.expanduser('~/.hermes/auth.json')))\nEOF", "sub", "claude", "deny"),
    ("RED  sub reads gh hosts file", "sed -n 1,5p $HOME/.config/gh/hosts.yml", "sub", "claude", "deny"),
    ("RED  sub reads netrc", "grep machine ~/.netrc", "sub", "claude", "deny"),
    ("RED  sub reads ssh private key", "cat ~/.ssh/id_ed25519", "sub", "claude", "deny"),
    ("RED  sub curl bearer header", "curl -sS -H 'Authorization: Bearer abc' https://api.example.com", "sub", "claude", "deny"),
    ("RED  sub curl attached header", "curl -sS -H'x-api-key: abc' https://api.example.com", "sub", "claude", "deny"),
    ("RED  sub curl user", "curl -u user:pass https://example.com", "sub", "claude", "deny"),
    ("RED  sub wget header", "wget --header='Authorization: token x' https://example.com/f", "sub", "claude", "deny"),
    ("RED  sub keychain read", "security find-generic-password -s svc -w", "sub", "claude", "deny"),
    ("RED  sub git push", "git push origin main", "sub", "claude", "deny"),
    ("RED  sub git -C fetch", "git -C /repo fetch -q origin", "sub", "claude", "deny"),
    ("RED  sub git remote update", "git remote update", "sub", "claude", "deny"),
    ("RED  sub credential variable", "env GH_TOKEN=abc make release", "sub", "claude", "deny"),
    ("RED  sub wrangler", "wrangler r2 bucket list", "sub", "claude", "deny"),
    ("RED  sub tailscale", "tailscale status --json", "sub", "claude", "deny"),
    ("RED  sub aws", "aws s3 ls --endpoint-url https://x.r2.cloudflarestorage.com", "sub", "claude", "deny"),
    ("RED  sub subagent in codex runtime", "gh pr list", "sub", "codex", "deny"),
    # subagent: look-alikes stay allowed
    ("GREEN sub grep for the word codex", "grep -n codex PLAN.md | head", "sub", "claude", "allow"),
    ("GREEN sub rg for a gh command string", "rg -n 'gh api' docs/", "sub", "claude", "allow"),
    ("GREEN sub strings of a binary", "strings ~/.local/share/claude/versions/2.1.295 | grep -c allowedProviders", "sub", "claude", "allow"),
    ("GREEN sub version only", "codex --version", "sub", "claude", "allow"),
    ("GREEN sub lookup only", "command -v gh; which codex", "sub", "claude", "allow"),
    ("GREEN sub local git", "git status --short && git log -3 && git diff --stat && git remote -v", "sub", "claude", "allow"),
    ("GREEN sub anonymous curl", "curl -sS -H 'Accept: application/json' https://example.com/a", "sub", "claude", "allow"),
    ("GREEN sub codex config not auth", "sed -n 1,5p ~/.codex/config.toml", "sub", "claude", "allow"),
    ("GREEN sub public key", "cat ~/.ssh/id_ed25519.pub", "sub", "claude", "allow"),
    ("GREEN sub echo a word", 'echo "gh" codex', "sub", "claude", "allow"),
    ("GREEN sub heredoc to cat is data", "cat > notes.md <<'EOF'\ngh api user\nEOF", "sub", "claude", "allow"),
    ("GREEN sub variable name without value", "echo GH_TOKEN is unset", "sub", "claude", "allow"),
    # source the shared tokenizer cannot read
    ("RED  sub unreadable source fails closed", "/bin/echo \"$(case x in x) git grep -E 'h' -- R;; esac)\"", "sub", "claude", "deny"),
    ("GREEN main unreadable source without a model name", "/bin/echo \"$(case x in x) git grep -E 'h' -- R;; esac)\"", "main", "claude", "allow"),
    ("ASK  main unreadable source naming codex", "/bin/echo \"$(case x in x) codex exec y;; esac)\"", "main", "claude", "ask"),
    # main thread, claude runtime
    ("ASK  main codex exec", "codex exec -s read-only 'review'", "main", "claude", "ask"),
    ("ASK  main codex behind bounded wrapper", "nohup python3 /x/bounded.py 3300 codex --search exec -m m 'p' < /dev/null > log 2>&1 &", "main", "claude", "ask"),
    ("ASK  main claude print", "claude -p hi", "main", "claude", "ask"),
    ("ASK  main hermes", "hermes chat -q hi", "main", "claude", "ask"),
    ("ASK  main reads codex auth", "cat ~/.codex/auth.json", "main", "claude", "ask"),
    ("ASK  main keychain read", "security find-internet-password -s github.com", "main", "claude", "ask"),
    ("GREEN main gh for PR work", "GH_TOKEN=$(gh auth token --user agentzyx) gh pr view 18 --json headRefOid", "main", "claude", "allow"),
    ("GREEN main git push", "git push -q origin feature/x", "main", "claude", "allow"),
    ("GREEN main claude version", "claude --version", "main", "claude", "allow"),
    ("GREEN main grep", "grep -rn codex docs | head", "main", "claude", "allow"),
    # main thread, codex runtime
    ("GREEN codex-runtime main codex", "codex exec 'x'", "main", "codex", "allow"),
    ("GREEN codex-runtime main reads auth", "cat ~/.codex/auth.json", "main", "codex", "allow"),
]
# Each name here must have a fixture whose verdict changes when the name is removed from
# its collection; selftest proves it, so a deleted entry cannot pass silently.
MUTATION_PROBES = [("MODEL_CLIS", n) for n in ("codex", "hermes", "claude")] + \
    [("CREDENTIAL_CLIS", n) for n in ("gh", "wrangler", "tailscale", "aws")] + \
    [("GIT_NETWORK", n) for n in ("push", "fetch")] + \
    [("KEYCHAIN_READS", "find-generic-password")] + \
    [("SHELLS", n) for n in ("bash", "zsh")]


def _graded(cmd, subagent, runtime="claude"):
    """A raising predicate is a failed case with its error, never a crash or an allow."""
    try:
        return decide(cmd, subagent=subagent, runtime=runtime)
    except BaseException as exc:
        return "<error>", f"{type(exc).__name__}: {exc}"


def _run_fixtures():
    results = []
    for label, cmd, caller, runtime, want in FIXTURES:
        got, _reason = _graded(cmd, caller == "sub", runtime)
        results.append((label, want, got))
    return results


def selftest():
    total = failures = 0
    if not FIXTURES:
        print("  NO FIXTURES — a suite that cannot go red proves nothing")
        return 2
    baseline = _run_fixtures()
    for label, want, got in baseline:
        ok = got == want
        total += 1
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} want={want:<5} got={got:<5} {label}")
    for coll, name in MUTATION_PROBES:
        target = globals()[coll]
        target.discard(name)
        try:
            mutated = _run_fixtures()
        finally:
            target.add(name)
        flipped = sum(1 for (_l, _w, a), (_l2, _w2, b) in zip(baseline, mutated) if a != b)
        ok = flipped > 0
        total += 1
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} mutation  removing {name!r} from {coll} "
              f"changes {flipped} verdict(s)")
    sub_deny, _ = _graded("gh pr list", True)
    main_allow, _ = _graded("gh pr list", False)
    ok = sub_deny == "deny" and main_allow == "allow"
    total += 1
    failures += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} caller    the same command is denied for a subagent "
          "and allowed on the main thread")
    print(f"\n  {total} checks, {failures} failures")
    print(f"SELFTEST-SUMMARY suite=credential_reach_guard checks={total} failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(selftest())
    print(__doc__)
    sys.exit(0)
