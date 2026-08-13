# Displaced from the `agent-dispatch` body

The body sits at the 5,000 B cap. Twenty-one of the registry's 26 IN rows
fit; five did not, and six MACHINE rows were judged non-dispatch or duplicative. Nothing
here is retracted — each row is rank-tagged and carries its mechanism, so promoting one into
the body is a straight swap, not a rewrite.

## Rank A — registry rows that did not fit

**R172 — a trust anchor the agent can write is not a boundary.** Receipts, stamps, tiers,
hook scripts, an "append-only" ledger and settings are all plain text writable by the thing
being constrained. A guard is not state-independent while the agent can edit the guard.
*Displaced because it fires when architecting an agent system, not when dispatching one.*
**Landed 2026-08-02 in the `system-design` body** (Containment). Until then it was in no body:
this file displaced it to `system-design` and `system-design`'s own deferred file deferred it
back here. Do not restate it here.

**R192 — workers hold capability, never credentials.** Secrets and orchestration state live
in the harness, not the guest; credentials are runtime config, never prompt content. An
injected worker can then call a tool but cannot exfiltrate a key it never had.
*Same reason as R172: a fleet-design rule sharing this skill's cue but not its moment.*

**R193 — autonomy has a user-owned ceiling.** Config can never *raise* autonomy, and a
capability absent from the consent registry is unconsented and fails closed.

**R174 — power validation is per-tier and non-transferable.** The same seeded-recall test
scored 2.4/5 at one model tier and 5/5 at another; the "blind spot" was a tier artifact.
*Kept out as a clause of the R173 line in the body, which retains the seeded-recall gate
itself. Promote this the moment a null is being carried across tiers.*

**R189 — reach for the packaged skill, not a hand-rolled fan-out of its agent types.**
Relaunching the same lanes by hand reproduces the fan-out and drops the selection and
consolidation discipline that lives in the wrapper, and can silently skip a lane. A
harness's value is in the parts that are not agents. *Nearest always-on coverage:
CLAUDE.md:34 "Named a tool? Run exactly that and stop." The registry notes R189 is the
sharper mechanism; if CLAUDE.md:34 is ever trimmed, promote this.*

**R288 — power-validate a prioritiser BEFORE dispatching on it, not after.** The body's
power-validation rule covers believing a *null*; a *ranking* you act on needs the same proof
and gets it far less often, because a ranking produces work rather than silence and so never
looks suspicious. Score it against a hand-labelled sample before it decides anything.
Observed: a five-file ranking measured **26% recall** only after three agents were already
dispatched against it, and the file it deprioritised produced both of that round's
refutations. *Displaced because the `agent-dispatch` body is at its 5000-char cap with 7
characters spare; this belongs beside the null rule and there is no room for it there.*

## MACHINE rows judged non-dispatch

The MACHINE ruling put the machine facts that are dispatch/environment knowledge into the
body — R285 (append-flag pierces every nesting depth; hooks see the agent type), R277
(crash-forensics signature), R284 (process-group kill). These are not:

**R282 (rank B) — a stale exported env from an earlier container generation desyncs from the
real listening port**; compare the process's env against the listener. *Demoted from the body
2026-08-02 to seat the disagreement-resolution rule, which was in no channel at all and
governs the operation this skill exists for. Promote it back if container work returns.*

**R280 (rank A) — disk preflight reads the data volume, reclaim order, `TMPDIR`.** Cut on a
duplication check, not on value: the lead clause is `~/.claude/CLAUDE.md`:43 verbatim
(`df -h /` shows the sealed volume) and the ENOSPC consequence is CLAUDE.md:48. What
survives is only "have a reclaim order decided in advance" and the `TMPDIR`-on-a-volume-
with-room escape hatch, neither of which the registry states concretely enough to write as
a rule. Resolve the reclaim order empirically, then add it to the CLAUDE.md bullet rather
than here — that is where the rest of the fact already lives.

**R278 (rank A) — venv corruption: reinstall, do not sync.** The package manager's own
metadata reports "audited N packages" over unimportable files, so a green sync is not
evidence the env works. *Its principle already travels as R103 in `testing-ci`'s OUT set.*

**R281 (rank B) — the pre-commit stash cache path**, where a hook parks unstaged work
mid-operation. *Landed 2026-08-02 in `git-workflow/references/deferred.md` (`pre-commit stash
cache`), with the path verified on this machine. Neither half was there before.*

**R279 (rank B) — editors reuse the window keyed to the folder**, so two targets in one repo
hijack each other's window; a per-target checkout is what buys the isolation.

**R286 (rank B) — buildx cross-compile output path plus a `/private/tmp` xattr failure** on
this host.

**R287 (rank B) — `zsh` treats bare `$r:path` as the `:s` history modifier**; braces are
load-bearing inside a `git show` loop. *Moved 2026-08-02 out of the `git-workflow` body into
`git-workflow/references/deferred.md` (`zsh :s brace`), to pay for that body naming its second
reference file. Same skill, one tier down.*

## Not carried anywhere by this skill

Registry §5's OUT block (R195–R210, 16 rows) was already ranked and displaced by the
registry itself and is not re-litigated here. Four of those rows (R206 reclaim order, R207
stray `model` pins, R208 absolute paths, R209 isolated clone pinned to the commit) are OUT
specifically because `~/.claude/CLAUDE.md` already carries them always-on — re-writing them
into this body would be a second copy on the same dispatch, which is the duplication the
routing rule forbids.
