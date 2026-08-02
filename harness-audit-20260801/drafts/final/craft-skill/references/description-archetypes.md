verified: 2026-07-14 · sources: example-corpus §2 (verbatim production sweep); prompt-craft §4

# Description archetypes (fill-in templates)

## Archetype A — consumer / file-type skills (trigger-first imperative)

```
Use this skill whenever the user wants to do anything with <domain/file type>. This
includes <operation 1>, <operation 2>, <operation 3>, … and <operation N>. Trigger
when the user mentions <literal phrasings: "<casual phrase>", "<synonym>", a
<.ext> filename> — regardless of what they plan to do with it afterward. Do NOT
use for <adjacent-but-different cases>.
```

Production example (Anthropic pdf, abridged): "Use this skill whenever the user wants to do anything with PDF files. This includes reading or extracting text/tables…, merging…, splitting…, rotating…, watermarks…, forms…, OCR…. If the user mentions a .pdf file or asks to produce one, use this skill."

## Archetype B — developer / method skills (capability + use-when)

```
<Noun-phrase capability statement — what it produces/does and to what standard>.
Use when <trigger context 1>, when <trigger context 2>, or when the user mentions
<keywords>. Do NOT use for <near-miss>.
```

Production example (Anthropic mcp-builder, abridged): "Guide for creating high-quality MCP servers…. Use when building MCP servers to integrate external APIs or services, whether in Python (FastMCP) or Node/TypeScript (MCP SDK)."

## Rules that override taste

- One archetype per description; never mix first/second/third person mid-description.
- Front-load the strongest trigger words (index truncation); enumerate operations even when it feels repetitive — long and trigger-dense is correct; ≤1024 chars, no XML.
- Anti-triggers are not optional for skills with plausible near-misses (the #1 community failure is their absence).
- Write for two readers at once: the routing model AND the human at a consent gate.
