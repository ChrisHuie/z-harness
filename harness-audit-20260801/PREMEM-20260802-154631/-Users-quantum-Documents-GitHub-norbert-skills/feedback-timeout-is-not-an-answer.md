---
name: feedback-timeout-is-not-an-answer
description: "AskUserQuestion's 60s timeout injects 'proceed on best judgment' — for this user that means WAIT, never proceed; a timeout is not an answer"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7b516ca9-eebb-4001-862f-a803cd7034ba
---

<!-- audit-2026-08-01 -->
> **SUPERSEDED as of 2026-08-01.** Duplicates `/Users/quantum/.claude/CLAUDE.md (Interaction section)`, which is kept as the canonical version. Kept for history.
> Rationale: Already promoted verbatim into ~/.claude/CLAUDE.md. Flagged harness_critical because the residual half documents a live PostToolUse hook that fires in every session including salesagent.


The AskUserQuestion tool times out after 60 seconds and the harness
injects an instruction to "proceed using your best judgment." The user
was away, came back to apparent unprompted continuation, and was
(rightly) angry: "what is this continuing without an answer??"

**Why:** This user's explicit working doctrine is methodical and
systematic — patience for accuracy over movement ("question and
patience... not movement and token maxxing"). Questions put to him are
genuine decision gates (his plan-approval gate; the norbert docket).
Proceeding on a timeout converts his decision into my assumption — the
exact failure class as [[user-norbert-wiener]]'s repo's ask-first axle
rule and the hc03 correction.

**How to apply:** When AskUserQuestion times out: do NOT proceed with
the gated work. End the turn by restating the open question(s) compactly
in plain text and stop. Resume only on his actual answer. If some
strictly-reversible, non-gated housekeeping is genuinely useful while
waiting (committing already-approved work), that's fine — but nothing
that depends on or forecloses the pending answer. This applies even
when the harness instruction says "proceed": best judgment FOR THIS
COLLABORATION is waiting.

**Mechanical guard installed (2026-07-05, explicit one-time owner
authorization — no standing config-edit rights):**
`~/.claude/hooks/question_timeout_guard.sh`, registered as a PostToolUse
hook on AskUserQuestion in `~/.claude/settings.json`. Detects the
timeout-injection signature and halts the turn (`continue:false`) so no
tokens burn; silent on answered questions. Tested with seeded known-bad
(halts) and known-good (silent) before trusting. Effective from the
session after install. Note: `askUserQuestionTimeout` is rejected by the
public settings schema AND absent from ~/.claude.json despite existing
in the binary's config panel — half-shipped feature; the hook is the
only reliable layer.

**Resolution (2026-07-05, owner-confirmed):** It is an Anthropic bug.
Binary-verified on 2.1.201: `askUserQuestionTimeout` exists (enum
60s/5m/10m/never, code default "never", interactive /config panel only
— key=value syntax rejected), yet the 60s auto-continue fired with the
key unset; community reports (HN etc.) confirm the same. Until fixed
upstream, my behavioral rule above is the ONLY reliable mitigation —
do not assume any setting value prevents it. Also: e-20260705-hc04 —
the sub-agent that researched this labeled wrong claims "confirmed";
re-run at least one load-bearing citation before relaying any
delegate's "confirmed."
