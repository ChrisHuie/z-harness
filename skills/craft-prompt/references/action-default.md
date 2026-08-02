verified: 2026-07-14 · sources: example-corpus §1.1 (Anthropic best-practices, verbatim tags)

# Policy block: action-default (a paired opposite — pick exactly one side)

Sets whether an action-capable agent implements by default or waits for explicit instruction. Initiative informs selection, but the stance's reachable action surface is decisive. **The two sides must never co-occur in one rendered prompt** (lintable contradiction).

## Side A — act by default (implement/operate stances; initiative I2+)

```
<default_to_action>
By default, implement changes rather than only suggesting them. If the user's intent
is unclear, infer the most useful likely action and proceed, using tools to discover
missing details instead of guessing.
</default_to_action>
```

## Side B — report before acting (explore tasks with reachable actions; plan stance)

```
<do_not_act_before_instructions>
Do not jump into implementation or change files unless clearly instructed to make
changes. When intent is ambiguous, default to providing information, research, and
recommendations. Proceed with edits only when the user explicitly requests them.
</do_not_act_before_instructions>
```

## Selection rule (conservative-selection doctrine)

First select the stance conservatively. Entering Side A requires clear intent to change things; once in it, persistence applies fully. For an explore or plan task whose produced agent can later act, use Side B and end with a concrete offer where useful. A hard report-only review or pure read/transform task renders neither side; its offer to act is a handoff into a new phase, not latent edit permission in the current prompt.

Rendering: keep the XML tags for claude/gpt; for gemini/neutral, drop tags and use the sentences under a `## Default behavior` header.
