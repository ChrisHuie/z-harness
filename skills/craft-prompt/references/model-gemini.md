verified: 2026-07-14 · sources: prompt-craft §1/§3 (Gemini column), example-corpus §1/§6/§10 · official: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/start/gemini-3-prompting-guide · https://ai.google.dev/gemini-api/docs/prompting-strategies · ◐ mirror: https://www.philschmid.de/gemini-3-prompt-practices (re-verify at landscape-refresh)

# Model profile: Gemini 3.x

**Default for:** the Google-side harness (agy). Applies *after* the neutral §2 core.

## Stances
- **CoT:** remove manual CoT scaffolds; use `thinking_level: high` + a *simplified* prompt. Heavy prompt engineering can degrade reasoning.
- **Few-shot:** officially pro-few-shot — a few, rigidly consistent examples. (Conflict: Google "always include" vs OpenAI "zero-shot first".)
- **Emphasis:** avoid blanket negatives ("do not guess") — they cause over-indexing on the forbidden behavior. Caps only on a true invariant.
- **Verbosity:** terse by default — explicitly request depth ("answer comprehensively with details, unless the user asks for concise"). Bound with `max_output_tokens`.
- **Temperature: keep at 1.0** — lowering causes looping/degradation.
- **thinking_level:** minimal → high; high is default on 3.1 Pro.

## Placement + anchor
Instructions AFTER the large context, behind an anchor phrase. Data first, then e.g. "Answer the question using the text below." Transition into analysis with "Based on the information above…".

## Rendering rules
- Markup: XML tags OR Markdown headers — never mix; keep concise (simplicity is itself the technique).
- Persistence shape: use the de-mirrored canonical rendering at `policy-blocks/persistence.md` §Gemini ("You are an autonomous agent. Continue until the task is COMPLETELY resolved. If a tool fails, analyze the error and try another approach. Verify before yielding."). The raw mirrored variant is retired from this profile pending primary re-verification (spike Q7 → landscape-refresh).
- Structured output: `response_format {type, mime_type, schema}` — note naming drift vs `responseSchema`; validate app-side.

## Distinctive techniques
Anchor phrases; knowledge-cutoff/date corrections in system instructions ("Remember it is 2026 this year"; "Your knowledge cutoff date is January 2025" — MUST-register invariant, §1.7); keep 10–20 active tools max.

## Vendor-doc conflicts
Few-shot (Google always vs OpenAI zero-shot-first). ◐-mirrored blocks (persistence, self-critique checklist, ambiguity rule) are philschmid-sourced — re-verify against the official Gemini 3 guide before shipping (spike Q7).

## Probe-claims (testable behavioral claims + source)
1. Temperature < 1.0 induces looping/repetition (§3, Gemini 3 guide). Test: same prompt at 1.0 vs 0.2, measure repetition.
2. Blanket negatives cause over-indexing on the forbidden action (§3/§7). Test: A/B negative vs positive phrasing.
3. Manual CoT degrades output at `thinking_level: high` (§1.1). Test: CoT scaffold vs simplified prompt at high thinking.
4. Instructions-after-context + anchor beats instructions-first on long inputs (§7). Test: swap placement on a multi-doc task.
5. Gemini under-produces without an explicit depth request (§1.5/§3). Test: length with vs without "answer comprehensively".
