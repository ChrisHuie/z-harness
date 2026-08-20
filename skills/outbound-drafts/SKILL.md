---
name: outbound-drafts
description: Drafting text that leaves this machine for a reader who cannot see the session — an issue body, a PR comment, a briefing, a message to paste and send. Use when asked to draft, write up, or hand over something to post or send, or when a draft puts a decision to a group. Not for a prompt or agent instructions (craft-prompt), nor finding-by-finding PR review (pr-review-method).
---

# Outbound drafts

For a reader with no access to this session. `~/.claude/CLAUDE.md` carries the always-on
filter — technical fact only, no provenance, more structure not less content. This is its
executable form, plus the rules that only fire once there is a draft.

## Before the first sentence

- **Pick the shape first.** A consolidation, comment, and issue body need different structures.
  **A parenthetical-only exception reads as absent** — give it its own line.
- **The audience decides whether you recommend.** Surfacing a decision to a **group** = options
  and tradeoffs, no recommendation. A 1:1 proposal recommends. The discriminator is the
  audience, never the artifact type.
- **Display facts, not endorsements — mirror, don't judge.** Report what a third party's
  artifact does; grading it puts your voice into their record.
- **The artifact IS the deliverable**; show it verbatim. When asked to "see" structured work,
  render it rather than showing a terminal dump. A file is additive, not the handoff.
- **Paste-bound text goes in a fenced block, never a quote-prefixed one** — a per-line prefix
  has to be stripped by hand. Discriminate on the request: "draft a comment for" is
  paste-bound; "what's the status" is read-only.
- **Plans default to chat**, a file only when explicitly asked. The bar is "did they ask for a
  written plan", not "is this big enough". At most one durable maintainer-facing doc per change.

## What the reader gets

- **A report for an external actor is self-contained** — per item: location, what is wrong, why
  it matters, the literal tested change, how to verify. Never a status summary, never a pointer
  to a local path they cannot open.
- **Issue body:** include impact, contract, gap with pointers, implementer-beware facts,
  outcome-based acceptance, open questions, and out-of-scope. Exclude pseudocode, solution
  tradeoffs, file plans, test inventories, and verification dumps. Target 150–250 lines, not 700.
- **An onboarding or easy label cannot hide an unmade design decision** — name the hard work.
- **Anonymize to roles, never named individuals** — and strip role-based *process controls*
  (on-call rosters, sign-offs, handoffs) entirely, per always-on. The two are different acts:
  anonymizing keeps the role as the abstraction, the always-on rule deletes the control.
- **Use a pattern's published name** so the artifact stays legible outside this repo.

## The filter

- **Filter sentence by sentence, including a draft handed over to paste**: no fan-out counts,
  no "our tooling caught it" scorekeeping, no self-deprecation about how the code came to be,
  and **strip any "what we learned" section entirely**. Review *workings* are their own
  category, distinct from the strategy and motive always-on already bans. Run a vocabulary gate
  over the finished draft, never over your intent.
- **Rewrite the body down to the residuals' altitude.** If the caveats contradict the headline,
  the headline is wrong — fix the headline; do not append the caveat.
- **Never frame a nudge as low-cost / high-return** — a nudge does not change the state it is
  nudging, and "wait for the reviewer" is a legitimate answer, named directly. Lead a
  prioritization with what each item **unblocks**, never with what it clears: a queue length is
  a UI number.

## Claims someone else will act on

- **Bug-investigation rigor.** Prior-session facts and summary facts are claims. A published
  wrong fact transfers the error to an implementer who builds on it in good faith.
- **A term you coin while consolidating propagates as if it were sourced** — one phantom label
  reached 19 sites and would have been certified. Mark coined vocabulary as coined.
- **Every outbound artifact carries the verified head id and a footer split `Ran:` /
  `Not-run:`** — the head you asserted against, not the one you fetched first, and the scope of
  what actually executed.
- **Review handoffs are append-only, one exact head per comment.** Never edit, replace, or
  delete a posted handoff; post a linked correction. Re-read the full object: raw body, repo,
  PR, head, author, id, URL,
  and unedited timestamps must match. Findings stay in inline `path:line` threads with their own
  lifecycle (`pr-review-method`).
- **Published PR narrative is append-only.** Freeze the body and title after creation; publish
  later summaries, corrections, and exact-head evidence as new comments. Before a final handoff,
  verify that the frozen publication still matches its reviewed snapshot.

## Publishing tooling

- **Split by class**: the behavioral / diary layer is private, the reference / catalog layer is
  shareable. Make the shipped set **self-contained** — removed files must leave no dangling
  citations, so redefine citations as IDs.
- **The share pipeline is scripted and re-runnable** (path rewrites, scrub greps, self-tests,
  install dry-run), never a one-time manual scrub.
