verified: 2026-07-14 · sources: example-corpus §1.2 (OpenAI verbatim; Anthropic parallel-tools tag; Codex batching)

# Policy block: context-gathering

Caps exploration appetite so agents act instead of over-searching. Depth is stance-owned: explore stance = broad, implement = early-stop, review = exhaustive-in-scope.

## Canonical text (early-stop variant; implement stance)

```
<context_gathering>
Goal: get enough context fast, then act.
- Start broad, then fan out to focused subqueries; batch independent searches in parallel.
- Early stop: you can name the exact content to change, or top results converge (~70%) on one area.
- If signals conflict, run one refined parallel batch, then proceed.
- Trace only symbols you will modify or whose contracts you rely on.
- Search again only if validation fails or new unknowns appear. Prefer acting over more searching.
</context_gathering>
```

## Parallelism companion (all stances; claude phrasing)

```
If multiple tool calls have no dependencies between them, make them in parallel.
When a call depends on a previous result, run it sequentially. Never guess or
placeholder missing parameters.
```

One-line batching variant (codex-style): `Batch everything: when you need multiple files, read them together.`

## Variants by stance

- explore: replace early-stop with `Stop when additional sources repeat what you already have (saturation), and say what you did not examine.`
- review: replace with `Exhaustive within the declared scope (the diff/artifact); nothing outside it.`

Thresholds stay tilde-hedged ("~70%") — aim-here-not-lawyer-it numbers (house style, corpus §10.4).
