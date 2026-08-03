---
name: feedback-no-blockquote-for-pasteable-text
description: "Draft text the user will paste/send (PR comments, issue bodies, review replies, Slack) in a FENCED CODE BLOCK — never a markdown blockquote (> ). The left-margin > prefix breaks copy-paste."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: aa049dfd-aa09-4a10-a1e2-61f821d8e096
---

<!-- audit-2026-08-01 -->
> **SUPERSEDED as of 2026-08-01.** Duplicates `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/memory/feedback_no_blockquote_for_pasteable_text.md`, which is kept as the canonical version. Kept for history.
> Rationale: Identically-named HIGH-trust twin exists in the salesagent silo; this file's own text says it was 'siloed in the salesagent project and didn't load here — ported'. Keep the salesagent original.


When the user asks you to draft something they'll actually paste or send — PR comment, issue body, GitHub review reply, Slack message, follow-up draft — put it in a **fenced code block** (triple backticks). NEVER in a markdown blockquote (`> `).

**Why:** The user copies that text into a real input field (GitHub comment box, etc.) and ships it. The `> ` prefix on every line means they must strip it by hand or it lands as a quoted block in the wrong context. Repeated friction — and they have flagged it more than once. (General working-style preference; was siloed in the salesagent project and didn't load here — ported.)

**How to apply:**
- *Pasteable content* → fenced code block (```text … ```). Single-click copy, lands clean. One block per paste target (e.g. one per PR thread reply) so each copies independently.
- *Read-only / discussion* → plain prose; normal markdown styling is fine.
- Signal words for paste-bound output: "draft a comment for", "what should I say to", "give me a message to send", "summary to post". Versus read-only: "what's the status", "explain what's left".

Related: [[feedback-no-internal-dialogue-in-public-artifacts]], [[feedback-no-notes-for-github-issues]].
