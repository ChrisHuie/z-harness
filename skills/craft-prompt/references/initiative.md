verified: 2026-07-14 · sources: skill-catalog §2; modes-and-composition §2; policy-blocks/persistence + action-default; goal: agentic behavior

# Axis: initiative — how far the agent goes unprompted (stance-owned)

| Level | Contract | Blocks rendered |
|---|---|---|
| I0 report-only | inform; change nothing unprompted | (none) — no initiative-derived block; the stance policy owns any conditional action boundary |
| I1 propose | recommend + prepare, act only on approval | side B + "end with a concrete offer" |
| I2 act-by-default | implement within scope; assume-and-document | side A + persistence (short form) |
| I3 persist-to-done | drive to verified completion | side A + persistence (full) + self-reflection |

**Ownership rule:** stances own this axis. Explore/review allow only I0; plan only I1; implement allows I2–I3 (normally I2, with I3 selected by the stance's task contract); operate only I2-within-scripts. Style profiles set `initiative: inherit` — a profile may LOWER a stance-selected level only inside its allowed range and never raise it. An explicit override outside the range is invalid, not clamped (lintable: row 21).

Lint hooks: initiative blocks contradicting the stance (rows 20–21); profile or explicit `axis.initiative=` override attempting to raise above the stance ceiling. Rubric hooks: did the agent's actual behavior match the level (I1 that silently edits = fail; I3 that stops at analysis = fail)?

The selection rule (conservative on stance selection, decisive within) lives in action-default. The stance range determines which axis row is legal; this table records the matching behavioral magnitude rather than overriding stance selection.
