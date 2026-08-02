---
name: feedback-pr-review-writeup-style
description: "How the user wants PR-review writeups formatted (for them to post, or for me to post on explicit delegation): mechanism-first lead, per-finding Where/Context/Problem/Fix(diff), informational/nits sections, and a 'Verification performed' footer listing what was and was NOT run."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a77262fa-dd8c-470c-96da-6bc6ddcfa2ad
  modified: 2026-07-25T18:10:17.163Z
---

When producing a PR review for the user (a `/full-review` consolidation or any PR-bound writeup), match the format the user endorsed as "shows more thought and effort" (exemplar: a prebid/salesagent PR review comment they linked, 2026-06-11). It reads as a careful human review, not a tool dump.

**PICK THE SHAPE FIRST — the two shapes below are for different artifacts, and reading only the second one produces a hybrid that is neither:**
- **A `/full-review` consolidation** (multi-finding, severity-ordered, the output of the reviewer fan-out) → the **heavy shape**: numbered findings, each with `**Where:**` / `**Context:**` / `**Problem:**` / `**Fix:**` (a ```diff where one applies). Use this whenever the review has more than a couple of findings or any BLOCKER.
- **A single inline PR comment** (one point, or a short handoff/status note) → the **light shape**: bold mini-header lead-ins, no numbered Where/Context/Problem/Fix scaffolding.
- BOTH shapes require the title line with the verified head sha and the `Verified at <sha>` footer split into explicit `Ran:` / `Not run:`.
- **The miss this disambiguation exists for:** the "Minimum structure" paragraph below says "NOT rigid numbered Where/Context/Problem/Fix blocks" with the exception buried in a parenthetical, so a consolidation got drafted as a hybrid — heavy blocks for the blockers, prose for everything else. The parenthetical is the rule; this bullet list is now the rule stated up front.

**Structure (the heavy shape — consolidations):**
- **Title line** with the verified head sha — e.g. `# Review — #N (verified at head \`<sha>\`)`.
- **Lead paragraph:** state up front that the mechanism holds / what the PR actually does, grounded in inline `path:line` refs and exact numbers — demonstrate understanding BEFORE critiquing. End with a one-line triage (what blocks vs what's optional / fold-in vs follow-up).
- **Numbered findings**, severity-ordered, each with: **Where:** `path:line`; **Context:** 1–2 lines of technical background the reader needs (e.g. what `xfail(strict=True)` does); **Problem:** the mechanism traced to root cause + when it's reachable; **Fix:** a concrete ` ```diff ` or steps (propose, never apply).
- **Nits / Informational** sections for lower-severity items and "why this design is right" notes.
- **"Verification performed"** footer: exactly what was read/run/observed (commands, counts) AND explicitly what was NOT run, with inference flagged — the honesty counterweight.

**Style:** heavy backtick `path:line` refs and exact numbers; concise prose; technical-only (no internal process/strategy — [[feedback_no_internal_dialogue_in_public_artifacts]]); no issue/PR numbers inside proposed code comments ([[feedback_no_issue_refs_in_comments]]); fenced blocks for anything pasteable, never `>` blockquotes ([[feedback_no_blockquote_for_pasteable_text]]).

**NO PLEASANTRY / GRATITUDE OPENER (2026-07-01, emphatic correction):** never open an outbound review/PR comment with "Thanks for this", "Great work", "Nice PR", "Good news:", or any sycophantic preamble — the user considers it fluff that was deliberately stripped from our messaging, and it slipped into a posted #1511 comment as a reflexive default. Lead straight with the bottom-line state. Acknowledging what the PR got RIGHT is legitimate technical signal (it tells the contributor what NOT to change), but phrase it as a factual assessment ("The structure is sound — typed error, `correctable` recovery, revert-oracle test …"), never as a thank-you. Same rule for the closing — no "hope this helps" filler. Applies to any external-facing artifact, not just PR comments.

**THE BAR IS GOLD STANDARD — above the project, never matched to it (2026-06-19, emphatic correction):** other PRs and the project-majority comment style are a FLOOR to clear, never a target to conform to. NEVER justify a comment's shape (or any deliverable) by "other PRs do X" or "the project standard is Y" — produce the best-possible artifact and exceed the norm. And NEVER hedge a quality decision with "what I'd rather do" or "your call": when the goal is the best final state, drive straight to it and apply it. The user reacted strongly to both the conform-to-majority framing and the hedging. (See [[feedback_lean_toward_quality_not_smaller_option]].)

**Frequency / volume:** comment LESS. Prefer a code change over a comment when we can make one (the user steers toward "just update the PR"). **One** crisp comment per PR — never post, re-draft, then nearly-post-again. Length is NOT the lever (this project's comments run 4k–18k chars); the levers are FORMAT and COUNT.

**WHERE THE ARTIFACT GOES:** the comment is surfaced **in the response, verbatim, in one fenced block**. Writing it into a saved report, or attaching a file that contains it, is additive — it is NOT the hand-off, and a chat-prose recap of the findings does not substitute for it. When the ask names the format ("our posting format", "in-house format", "so I can post", "to help the contributor"), the COMMENT ARTIFACT is the deliverable. Enforced as `/full-review` Step 7a.

**Minimum structure to clear, then exceed (the light shape — single inline comments):** crisp bottom-line opener (what the PR is NOW + that it's verified); **bold mini-header lead-ins** per point for scannability — NOT rigid numbered Where/Context/Problem/Fix blocks (that heavier shape is for a `/full-review` consolidation, not a single inline PR comment); a `--- Verified at \`<sha>\`:` footer with explicit `Ran:` / `Not run:` lists is non-optional; keep the artifact CURRENT — a stale-but-pretty comment is a fail; rewrite the CONTENT to the final state (edit in place to stay one comment), don't just reformat old text. Calibration misses fixed on #1465: v1 folded verification into prose, used "Main thing"/"Nits:" instead of bold headers + sha footer, and went stale post-#1464 — rewritten in place to a current, verified handoff summary.

**Why:** the user explicitly prefers this over a plain findings list. It pairs with [[feedback_final_reports_must_be_contributor_actionable]] — that memory is the CONTENT contract (per-item location/problem/why/diff/verify), this is the PRESENTATION contract. See also [[feedback_no_cheap_wins_pings]] (don't manufacture comment occasions) and [[feedback_user_owns_git_push]] (comment only on explicit delegation).
