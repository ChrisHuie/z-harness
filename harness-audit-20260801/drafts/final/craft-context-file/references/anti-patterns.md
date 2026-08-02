verified: 2026-07-14 · sources: prompt-craft §8 (rows 1–16); security research 2026-07-14 (17–19); modes-and-composition §8.4 (20–24); audit live incidents 2026-07-14 (25–26, docs/reviews/2026-07-14-mvp-implementation-audit.md)

# Anti-pattern catalog (v2 — 26 rows)

The consolidated authoring catalog. `review-prompt`'s checklist derives from THIS file (author/critic independence). Lint tags: ✅ mechanical · ⚠️ judgment. Severity guidance: rows marked ▲ default to critical when present.

## Authoring rows (1–16)

| # | Anti-pattern | Mechanism | Lint |
|---|---|---|---|
| 1▲ | Contradictory instructions | forced triage → token burn, unstable output; poison for literal-followers (gpt) | ✅+⚠️ |
| 2 | Over-constraint | compliance degrades with constraint count; redundant micro-rules dilute all rules | ✅ count/warn |
| 3 | Kitchen-sink prompt | unrelated roles/tasks in one prompt → role confusion, dilution | ⚠️ |
| 4 | Emphasis spam | CAPS/MUST on routine guidance flattens priority; Claude 4.6+ over-triggers | ✅ regex+density |
| 5 | Negative-only rules | "never X" with no positive target → over-indexing, no guardrail when it fires | ✅ ratio |
| 6 | Stale few-shot | examples contradict instructions; examples win | ⚠️ example↔instruction diff |
| 7▲ | Vague trigger description | skill mis-fires or sits idle; description IS the routing signal | ✅ heuristics |
| 8 | Manual CoT on reasoning models | redundant, adds latency, can degrade; "think step by step" is the tell | ✅ regex |
| 9 | Step-prescription to reasoning models | over-constrains the model's search; outcome contracts instead | ⚠️ |
| 10 | Budget blowout | verbose prompt × high effort = cost without quality | ✅ token counts |
| 11 | Kitchen-sink context file | bloated always-on file → rules ignored (>200 lines CLAUDE.md, >32KiB AGENTS.md) | ✅ size |
| 12 | Lost-in-the-middle placement | key rules buried mid-context under-weighted | ✅ structure |
| 13 | Volatile tokens in stable blocks | timestamps/run-values kill prefix caching | ✅ regex |
| 14 | Time-sensitive phrasing | "before August 2025…" rots; use collapsed old-patterns sections | ✅ regex |
| 15 | Mixed markup registers | XML and MD interleaved inconsistently → boundary ambiguity | ✅ structure |
| 16 | Spec violations | name≠dir, description >1024, reserved words, body >500 lines | ✅ skills-ref+checks |

## Injection wing (17–19) — all ▲

| # | Anti-pattern | Mechanism | Lint |
|---|---|---|---|
| 17▲ | Unwrapped untrusted content | external content enters context with no data-not-instructions boundary while agent holds act tools → injection surface. Calibration (2026-07-14): the task's designed input channel co-existing with act tools is not by itself row 17 — the defect is the missing boundary, never the channel's existence | ✅ ingestion-without-block |
| 18▲ | Missing destructive-op gate | irreversible/outward actions (delete, force-push, DROP, send) instructed with no user-approval clause | ✅ verb-list scan |
| 19▲ | Secret echo | credentials placed where untrusted content or outputs can reach them | ✅ secret-shape regex |

## Stance-consistency rows (20–24)

| # | Anti-pattern | Mechanism | Lint |
|---|---|---|---|
| 20▲ | Paired-opposite co-presence | `default_to_action` + `do_not_act_before_instructions` in one render | ✅ |
| 21 | Action blocks in read stances | persistence/Side A rendered into a read stance, or Side B mapped into hard report-only review/pure-read work; cross-file stance sources disagree | ✅ |
| 22 | Write tools in review skills | allowed-tools grants writes to a report-only stance | ✅ |
| 23 | Missing plan approval gate | plan-stance output without an explicit user gate | ✅ |
| 24 | Harness-mode conflict | rendering fights physically-enforced harness state (act-by-default into plan mode) | ✅ |

## Repo/transcript hygiene rows (25–26) — v2, from audit live incidents

| # | Anti-pattern | Mechanism | Lint |
|---|---|---|---|
| 25▲ | Reserved context filename | a shipped/repo file whose basename case-insensitively equals an always-on context filename (CLAUDE.md, AGENTS.md, GEMINI.md) outside its sanctioned location — harnesses auto-load it as instructions (observed live: a model profile named claude.md injected as project context) | ✅ basename scan |
| 26 | Harness framing pasted into artifacts | transcript/envelope tokens (numbered-line gutters, stray `</output>`-style closers, tool-result wrappers) embedded in a prompt read as structure — boundary ambiguity for executors, false structural findings for reviewers | ✅ framing-signature regex |

## Usage

- review-prompt: sweep every row; cite row # + name per finding; ▲ rows severity-critical by default; never invent findings on clean artifacts (precision > recall theater).
- Seeded-defect corpus: ≥1 fixture per row of the current catalog (concepts M9 — the corpus tracks catalog growth). v0 planted rows 1–8/17/18; the v1 extension (fresh-session authored) covers the remainder.
- Legitimate emphasis: a single absolute guarding a true invariant (safety, mode gate, spec compliance) is NOT row 4 — density and routine-ness make the defect.
