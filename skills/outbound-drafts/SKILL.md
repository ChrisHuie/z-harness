---
name: outbound-drafts
description: Drafting text that leaves this machine for a reader who cannot see the session — an issue body, a PR comment, a briefing, a message to paste and send. Use when asked to draft, write up, or hand over something to post or send, or when a draft puts a decision to a group. Not for a prompt or agent instructions (craft-prompt), nor finding-by-finding PR review (pr-review-method).
---

# Outbound drafts

For a reader with no access to this session. `~/.claude/CLAUDE.md` carries the always-on
filter — technical fact only, no provenance, more structure not less content. This is its
executable form, plus the rules that only fire once there is a draft.

## Before the first sentence

- **Pick the shape first.** A multi-finding consolidation, a single comment and an issue body
  are different structures. **A rule stated only as a parenthetical exception reads as the
  rule's absence** — give it its own line.
- **The audience decides whether you recommend.** Surfacing a decision to a **group** = options
  and tradeoffs, no recommendation. A 1:1 proposal recommends. The discriminator is the
  audience, never the artifact type.
- **Display facts, not endorsements — mirror, don't judge.** Report what a third party's
  artifact does; grading it puts your voice into their record.
- **The artifact IS the deliverable**, surfaced verbatim in the response — and when asked to
  "see" or "show" something with structure, a rendered artifact, never a terminal dump.
  Writing it to a file is additive, never the hand-off.
- **Paste-bound text goes in a fenced block, never a quote-prefixed one** — a per-line prefix
  has to be stripped by hand. Discriminate on the request: "draft a comment for" is
  paste-bound; "what's the status" is read-only.
- **Plans default to chat**, a file only when explicitly asked. The bar is "did they ask for a
  written plan", not "is this big enough". At most one durable maintainer-facing doc per change.

## What the reader gets

- **A report for an external actor is self-contained** — per item: location, what is wrong, why
  it matters, the literal tested change, how to verify. Never a status summary, never a pointer
  to a local path they cannot open.
- **Issue body — include**: impact, what the contract requires, the current gap with pointers,
  implementer-beware notes as non-obvious **facts** (not solutions), acceptance criteria as
  **outcomes** (not steps), open questions, out-of-scope. **Exclude**: pseudocode, design
  alternatives with pros/cons, file-by-file plans, test inventories, verification dumps.
  ~150–250 lines is the signal; 700 is too long.
- **A task labelled onboarding or easy that holds an unmade design decision is a hard task
  wearing an easy label** — say so in the body.
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

## Publishing tooling

- **Split by class**: the behavioral / diary layer is private, the reference / catalog layer is
  shareable. Make the shipped set **self-contained** — removed files must leave no dangling
  citations, so redefine citations as IDs.
- **The share pipeline is scripted and re-runnable** (path rewrites, scrub greps, self-tests,
  install dry-run), never a one-time manual scrub.
