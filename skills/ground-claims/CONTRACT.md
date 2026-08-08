# ground-claims — contract

## Inputs

Arguments arrive as free text plus optional `key=value` tokens.

| Input | Default | Meaning |
|---|---|---|
| *(positional)* | required | The claim to ground, or the question whose answer will become a claim |
| `artifact=` | resolve from the question | Path, URL, or package holding the authority. Multiple allowed |
| `scope=` | `claim` | `claim` grounds one assertion. `doc` audits every load-bearing claim in an existing document |

Report unknown keys; never silently ignore them.

## Question type governs the instrument

Resolved before any search runs. The type is stated in the output.

| Type | Question shape | Licensed instrument | Forbidden |
|---|---|---|---|
| **absence** | does X exist / does Y lack Z | sweep, **plus a positive control** | a sweep with no control |
| **location** | where is X | sweep to locate | sweep to conclude |
| **structure** | what shape is X / what values / which fields | open the object, enumerate fields and enums | any sweep; any name-level read |
| **behavior** | what does X do at runtime | run it, or read the implementation | the declaration alone |

## Output sections, in order

1. `## Grounding` — one row per claim: instrument run · artifact `@` version-or-digest · tier · positive control (absence only).
2. `## Finding` — the claim. Every load-bearing claim carries a **falsifier**: the observation that would refute it.
3. `## Residuals` — what was not checked, and every place a weaker instrument was substituted.

A claim is **load-bearing** when reversing it would change a decision. Only load-bearing claims need a falsifier; tagging everything defeats the signal.

## Tiers

| Tier | Meaning |
|---|---|
| `[V]` | The artifact was opened in this session and the quoted or enumerated content read directly |
| `[D]` | Taken from a prior report, another agent, or a delegated pass; not re-read here |
| `[I]` | Inference from something adjacent — a name, a listing, a sibling field, a summary |

Tier is per claim, never per document. A document-scope tier launders `[I]` into `[V]` and is the failure this skill exists to prevent.

## Failure behaviors

- **If** the artifact cannot be resolved, is not on disk, and is not reachable → ask which artifact and which version is authoritative. Emit no `## Finding`. Never answer from memory of the artifact.
- **If** the question type is `structure` or `behavior` and only a name, a path listing, a search-result line, or a sibling description was read → do not emit the claim. Open the object first, or emit `[I]` and say the object was not opened.
- **If** an absence sweep has no positive control → emit `matcher unproven`, not an absence claim. An empty result tests the matcher until a control says otherwise.
- **If** a quote cannot be matched byte-for-byte in the cited artifact → downgrade it to a paraphrase and mark it as one. Never present unmatched text between quotation marks.
- **If** two candidate copies of the artifact disagree (installed vs repo, dist vs source, mirror vs origin) → say which one was read and that they diverge, before the claim.
- **If** the question is whether a test, suite, selector, guard, or green check proves something → decline and route to `testing-ci`.
- **If** the claim rests on what a subagent reported → decline and route to `agent-dispatch`.
- **If** the request is to author or critique a prompt, skill, or context file → decline and route to `craft-prompt`, `craft-skill`, `craft-context-file`, or `review-prompt`.

## Stance

Read-only. This skill grounds claims; it never edits the artifact it reads and never writes the document the claim lands in.
