# Deferred — rank-A git rules displaced by the 5,000 B body cap

Every rule here is rank **A**: violating it produces a wrong artifact that ships — an
aborted commit reported as landed, a push nobody authorized, a bulk rewrite that breaks
runtime. They are out of `SKILL.md` because the body is full, not because they are weaker.

Read this file when a commit is aborting inside a hook you did not write, when a push is
about to happen, or before running any tool that rewrites source across many files.

The five names cited from the body are marked `[body]`.

**Read-only convenience, moved out of the body 2026-08-02** (the body's scope is operations that
CHANGE a repo and misreport it): read a branch-only corpus with `git show <branch>:<path>` — no
checkout needed.

---

## overlapping formatters `[body]`

**Two formatters with overlapping scope is a config defect**, not a sequencing problem —
neither is idempotent on the other's output, so the second reformats pre-existing lines in
any file it touches and aborts commits mid-hook on files your change never named. Converge
on one, and move the checker in lockstep with it. Registry R163.

Pairs with the body's *"a hook that rewrites a staged file exits non-zero and ABORTS the
commit"*: that rule tells you what the symptom is, this one tells you the symptom is
permanent until the config is fixed.

## per-push confirmation `[body]`

**Each push is its own action needing its own confirmation** — an authorization given at
the start of a phase does not carry to the next push in that phase. Registry R165.

Its parent is always-on: `~/.claude/CLAUDE.md` bans `git push` and `gh pr create/merge/
comment` on your own initiative. What is *not* in that line is the per-instance scoping, so
this is the only home for it. Two adjuncts, both rank B, both registry-OUT:

- On the one push confirmation, surface the **target and the identity it goes out under**
  (which account), and restore the working tree afterwards. Registry R164.
- Pre-push scope check: `git diff --stat <base> HEAD` shows only the intended files.
  Registry R166.

## bulk-rewrite sweep `[body]`

**Enumerate the call sites and categorize each one before applying any bulk rewrite**, and
run the affected tests before committing it. Registry R168.

The mechanism, from registry R015: an autofixer's own safe/unsafe classification is
semantics-preserving **only under the usages it can see** — a re-exported name defeats it,
because the tool cannot see the consumer. Recovery is `git checkout -- <paths>`, never a
hard reset.

The ban itself is always-on in `~/.claude/CLAUDE.md` ("Never run a bulk auto-rewriter …
over source without per-site review"). This is the procedure that ban implies and does not
state.

## pre-commit stash cache `[body]`

**A hook that stashes unstaged work parks the patch at `~/.cache/pre-commit/patch<epoch>-<pid>`**
— if the run dies mid-hook the tree sits at HEAD and the work is in that file, recoverable with
`git apply`. Registry R281 (rank B). Path observed on this machine 2026-08-02
(`ls ~/.cache/pre-commit/` → `patch1779420209-42688` and 100+ siblings); confirm before relying
on it elsewhere, and never conclude "reverted / lost" while a hook is still in flight — that is
the always-on banned-words rule this path is the recovery for.

## zsh `:s` brace `[body]`

**`zsh` treats a bare `$r:path` as the `:s` history modifier**, so braces are load-bearing inside
a `git show` loop: brace `${r}:path` and git goes fatal on a bogus argument instead of silently
reading the wrong object. Registry R287 (rank B) — moved here from the body 2026-08-02 to keep
the body at cap.

---

## Displaced rank C

**A repeated multi-step environment action gets a named verb, not a recalled sequence.**
Registry R167 — routed OUT as a pure instance; its machine-specific half went to the
machine bucket.

---

## Evicted from the draft body, and where each went

Neither of these is lost; do not re-add them here.

- **"A PR runs only the workflows whose `pull_request: branches:` filter its BASE matches,
  so a stacked PR gets no heavy CI and its scanner alerts stay frozen."** Registry R161 —
  R2 duplicate of R094, which is IN the `testing-ci` body ("a job gated on a release or
  base-branch condition never runs on a change request … **zero entries for that job class
  IS the tell**"). One copy, kept there because the rule contains no git operation.
- **"`workflow_dispatch` runs never attach to a PR's required contexts; a superseded check
  lingers beside the new one and `mergeable` sits at `UNKNOWN` while it recomputes."**
  Registry R162 — folded into the body's automation-identity bullet as its second clause.
  The `mergeable=UNKNOWN` recompute detail is the part that did not survive the fold.

## Deliberately absent — already always-on in `~/.claude/CLAUDE.md`

Verified against the live file on 2026-08-02. Re-adding any of these is an R2 defect: both
channels load on the same request, so the copy is paid twice.

- `:61-64` — mutation-testing agents get an isolated worktree or an in-memory copy, never a
  shared checkout; commit first so `git checkout --` lands on your commit.
- `:73-77` — never run `git push`, `gh pr create/merge/comment`, or `gh issue create` on
  your own initiative; local git is pre-authorized.
- `:92` — report raw state: origin head, `git log @{u}..HEAD` for local-only commits,
  `gh pr checks` for CI's actual verdict.
- `:105-109` — never run a bulk auto-rewriter over source without per-site review.

**Delivered twice as of 2026-08-02, and this body deliberately carries neither copy:** the
empty-grep rule (*an empty result set is a hypothesis about your matcher; POSIX-ERE silently
ignores `\b`*) is always-on in `~/.claude/CLAUDE.md` (Verification), and a `git grep -E` with
a PCRE-only atom is DENIED at command time by `hooks/guards/git_grep_engine_guard.py` via
`bash_command_guard.py`. The always-on line stays deliberately: the hook fires after the
command is composed; the line pre-empts the denied-call round trip. Do not re-add the rule
here — a third copy is the R2 defect.
