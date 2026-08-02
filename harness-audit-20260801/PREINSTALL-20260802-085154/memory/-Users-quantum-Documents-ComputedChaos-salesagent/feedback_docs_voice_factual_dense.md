---
name: feedback_docs_voice_factual_dense
description: "For docs/release-notes/prose — \"easier to read\" means more structure, not less content; voice is factual, never marketing or self-congratulation."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ae91ccf1-288c-4028-aac3-204b50838a29
---

When the user asks to make a document "easier to read" or to "combine" sections, that means improving STRUCTURE and scannability (a short lead, bold-lead bullets, callouts, clear hierarchy) while KEEPING maximum information — NOT stripping content or going minimalist. They explicitly rejected a stripped-down draft ("I never even said leaner... include as much information as possible"). Separately, the voice must be factual and neutral: state what changed and its concrete effect; significance is stated as a fact (e.g. a spec version), not a claim.

**Why:** two wasted iterations on the 1.8.0 release-notes doc — first an over-stripped dense-paragraph version, then a flowery one ("re-establish the project as a conformant reference implementation"). Both missed because I conflated "combine/easier" with "trim" and let marketing language in.

**How to apply:** default to information-dense + well-structured for their documents; reserve trimming for genuine redundancy only. Ban marketing adjectives ("clean", "powerful", "far easier"), self-congratulation ("reference implementation", "in lockstep with the spec"), and editorializing ("drifting behind") in prose, not just code — this extends [[feedback_truth_over_optimism]]'s ban-vendor-words rule to documents. Pairs with [[feedback_lean_toward_quality_not_smaller_option]] (depth over the smaller option).

**Also applies to contributor-facing PR-review comments** (the pasteable artifact, see [[feedback_pr_review_writeup_style]]): NO greeting/thanks opener ("Thanks for this"), NO evaluative praise of the PR ("clean", "well-structured", "nice work"). Lead with the fact (what was checked, what the finding is). Every line = location + fact + fix. The goal is the implementer's code meeting the bar, not social framing. Also NO teaching/"general lesson for next time" framing — stating the principle back to the contributor reads as condescending; give the fix as facts + code, not a tutorial. Flagged 2026-06-23 on a #1473 comment that opened with "Thanks for this — the conversion logic is clean…", 2026-06-24 on a #1475 re-review that appended a "general lesson for next time" section, and AGAIN 2026-06-27 on the #1478 review draft ("Thanks for this — I traced…" + "mechanically sound and low-risk"). Also ban the soft sign-off ("nothing blocking", "a few suggestions below") — state "No blockers; findings below." as fact. 3rd+ recurrence despite this memory existing → recall failed; now wired into the MEMORY.md "Drafting GitHub artifacts" + "Reviewing a PR" triggers to force a read at draft time ([[feedback_escalate_recurring_lessons_to_guards]]).
