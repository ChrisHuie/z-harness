---
name: feedback-no-blockquote-for-pasteable-text
description: "When drafting text the user will actually paste/send (PR comments, issue bodies, Slack messages), put it in a fenced code block — never blockquote (lines starting with \"> \") — the left-margin prefix breaks copy-paste"
metadata:
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

When the user asks you to draft something they'll actually paste or send — PR comment, issue body, Slack message, GitHub review reply, follow-up draft — put it in a **fenced code block** (triple backticks). Never in a markdown blockquote (`> `).

**Why:** The user copies that text into a real input field (GitHub comment box, etc.) and ships it. The `> ` prefix on every line means they have to strip it manually before sending or it lands as a quoted block in the wrong context. Repeated friction.

**How to apply:**
- *Pasteable content* — fenced code block (```text ... ```). Single-click copy, lands clean.
- *Read-only / discussion context* — plain prose, normal markdown styling is fine. The user just reads it; nothing to paste.

Distinguish by whether the user said something like "draft a comment for", "what should I say to", "give me a message to send" — those signal paste-bound output. Versus "what's the status" or "explain what's left" — those are read-only.

Failure mode example: drafting "Here's the re-review comment to add to PR #1312:" then using `> @reviewer — ...` — user has to fight the indent line to paste cleanly.

Correct: put the draft inside ```text ... ``` fences.
