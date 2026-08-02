---
name: User owns git push and remote ops
description: User prefers to execute `git push` (including force-push) and other remote-facing git ops themselves rather than having me run them
type: feedback
originSessionId: 052244c0-3a26-479e-b6aa-c33a034b1939
---
User pushes to origin themselves by default. **Do not run `git push`, `gh pr create`, `gh pr merge`, `gh pr comment/review`, or any remote-mutating op on your own initiative — and do NOT treat an ambiguous mention as a green light.** Phrases like "publish the PR" / "open the draft PR" / "let's push it" are usually requests to PREPARE materials (commit message, PR body, branch state); the user executes the remote step.

**Exception — explicit delegation (honor it).** When the user directly and unambiguously tells you to perform a *specific* remote op ("post this for me on #1420", "go ahead and push it"), execute it — after ONE quick confirmation for public/irreversible/outward-facing actions (surface the target + the identity it goes out under, e.g. which `gh` account). Pattern is **confirm-once-then-execute**: never fire unilaterally, but never refuse or endlessly re-deliberate a clear delegation either. Use the local-branch reviewing setup, restore the tree after, and report the resulting URL.

**Why:** The default was confirmed three times where an ambiguous mention was NOT delegation: (1) #1213 — user chose "you open the PR". (2) #1213 — user interrupted a push tool call with "i pushed". (3) #1246 — user said "lets first publish the draft pr"; I ran `git push`; user interrupted with "already did." BUT the counter-case is real: (4) 2026-06-11 — after a full PR review, user said "can you post this for me on 1420?"; I confirmed via one AskUserQuestion (flagging it reverses this agreement + posts under their account), user chose "post top-level comment", I posted as ChrisHuie and returned the URL. The discriminator is **explicitness**: a mention of push/publish embedded in a prep request → prepare + ask; a direct "you do it" imperative aimed at a specific op → confirm once, then do it.

**How to apply:**
- Default (ambiguous / prep-shaped request): prepare the PR body / commit message / comment draft, output it inline (no `gh` invocation), optionally output the command to copy, and STOP.
- Explicit delegation of a specific remote op: confirm once (target + identity for public/irreversible ones), then execute and report the URL. Do not re-deliberate past the single confirm.
- If unsure whether the user is asking for action vs. preparation, default to preparation and ask.

Does NOT apply to: local git ops (commit, rebase, cherry-pick on local branches, branch deletion of local-only branches, stash). User has explicitly authorized local destructive ops many times.
