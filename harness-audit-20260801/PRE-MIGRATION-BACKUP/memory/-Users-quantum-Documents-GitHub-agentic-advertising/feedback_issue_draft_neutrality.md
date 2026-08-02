---
name: feedback-issue-draft-neutrality
description: "User wants draft issue bodies (and any artifact meant to surface a decision to a group) to present options neutrally — no \"Recommended\" section, no advocacy"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3d30656b-34d1-4d41-9c9a-91f0ececdc7e
---

When drafting an issue body, RFC document, briefing, or any artifact that will be reviewed by a group making a decision: present the options and their tradeoffs neutrally. Do NOT include a "Recommendation" or "Why we recommend" section. State observations and tradeoffs; let the group decide.

**Why**: User instructed 2026-05-12 mid-conversation while reviewing Q-006 and Q-008 issue drafts — both had "Recommended: Option X" sections that pre-framed the meeting outcome. Quote: "can you not add any recommended language in the draft issues so we aren't framing the meetings decision".

**How to apply**:
- Issue drafts (the `findings/YYYY-MM-DD-q*-issue-draft.md` shape): no "Recommendation" section; options + tradeoffs only.
- PMC briefings or anything written for a group decision: same.
- Atom files (`stance_rationale_summary`, etc.) — separate concern; stance IS a recommendation by design, so this rule doesn't apply to atoms.
- Chat-level analysis or proposals to the user (1:1) is fine to include recommendations — they're choosing in the moment, not arriving at a pre-framed meeting.

Related: [[project_storyboard_run_methodology]], [[feedback_iterative_planning]].
