---
name: no-claude-coauthor-trailer
description: "Don't add the Co-Authored-By Claude trailer to commit messages"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: cefe78de-3dff-4ad7-bc67-a4dc4776cdec
---

Do NOT append the `Co-Authored-By: Claude ...` trailer to git commit messages, even though the harness default adds it.

**Why:** These are the user's own contributions to public/upstream OSS repos under their name; they don't want an AI co-author trailer on them.

**How to apply:** Omit the `Co-Authored-By: Claude` line when composing new commits. If one was already pushed, offer to remove it (amend + `git push --force-with-lease`) but don't assume — they may not want the force-push churn. Relates to [[feedback-push-policy]].
