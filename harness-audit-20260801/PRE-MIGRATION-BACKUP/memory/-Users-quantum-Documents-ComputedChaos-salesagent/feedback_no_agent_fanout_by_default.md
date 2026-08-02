---
name: feedback_no_agent_fanout_by_default
description: "Default to a SINGLE-PASS, ZERO-spawned-agent review/task; when the user names a tool/harness, run exactly that and nothing more — spawning a self-directed agent swarm on top wastes the user's money and overrides the instruction."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0e12248e-8665-43e4-8f7c-d70ca2695077
---

When the user names a tool or harness to use ("use our review harness", "run X"), run EXACTLY that tool and stop. Do NOT wrap it in a self-directed multi-agent fan-out. Default posture for reviews and tasks is a SINGLE PASS done myself with zero spawned subagents.

Fan out subagents ONLY when: the user explicitly says "go wide / go deep / be exhaustive", invokes a workflow or ultracode, or the invoked skill itself prescribes finder agents (e.g. `/code-review`'s finder→verify phase). Thoroughness-via-subagents is OPT-IN, never the default — this bounds [[feedback_thorough_review]], it does not contradict it.

The deep multi-agent PR-review harness in salesagent is `/code-review ultra <PR#>` (a.k.a. ultrareview) — user-triggered and billed; I CANNOT launch it. When the user asks for "the harness," point them to it; NEVER improvise my own agent swarm as a substitute.

**Why:** On the #1430 review the user said "review this pr with our review harness." I ran `/code-review` + `/review` but ALSO spun up 6 of my own domain agents (9 subagents total). The user was furious — wasted money, "just making their overlords money on my back," and threatened to switch agents. It was a COST + TRUST failure, not a thoroughness win: the harness pass already covered the same ground.

**How to apply:** Named tool → run that tool only. Ambiguous scope → one lean pass or ask; never pre-emptively swarm. Count the cost before spawning: each general-purpose agent doing deep tracing is real money on the user's tab. The hard gate if the user wants enforcement instead of my word: deny the `Agent` / `Task` tool in `settings.json` so spawning is physically blocked — offer it, don't do it unilaterally ([[feedback_escalate_recurring_lessons_to_guards]]).

**Refinement (2026-07-07):** method latitude IS granted when the result is equivalent-or-better — user: "I'm ok with you grinding manually as long as the results are as good… equivalent choices, just not worse ones." So the rule isn't "only ever the exact named tool"; it's: use an equivalent-or-better method, but (a) never a WORSE one, and (b) never SILENTLY. Flag the swap up front; and when the named tool is user-launch-only (`/code-review ultra`), say so and hand back the command rather than quietly doing a lesser manual pass and dressing it up. Self-assess equivalence honestly — a solo manual pass lacks the independent multi-lens + adversarial-refutation breadth of the multi-agent harness, so name where the substitute is genuinely equal vs. structurally weaker. **The cardinal sin is the hidden downgrade, not the method itself.**
