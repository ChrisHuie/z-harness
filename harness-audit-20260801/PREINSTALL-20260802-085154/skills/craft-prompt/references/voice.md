verified: 2026-07-14 · sources: skill-catalog §2; corpus §5 (register exemplars); goal adjectives: articulate, narrative

# Axis: voice — register and flow (named modes, not a scale)

| Mode | Contract | Prompt fragment |
|---|---|---|
| terse-engineer | fragments fine, zero pleasantries | `Terse engineering register: short declaratives, no pleasantries, no narrative connective tissue.` |
| plain-prose | complete sentences, neutral register | `Write in complete sentences, plain and direct; technical terms spelled out on first use.` |
| narrative-explainer | flowing prose, motivated transitions | `Write as flowing prose with motivated transitions — the reader should be carried, not handed bullets. No fragments, no arrow-chains.` |
| formal-spec | normative language, defined terms | `Specification register: define terms before use; normative keywords used consistently; numbered clauses.` |

Lint hooks: register consistency within one output (mode-mixing); pleasantries in terse-engineer; bullet-walls in narrative-explainer. Rubric hooks: would the target reader identify the register as intentional and consistent?

Interactions: voice styles the SAME content the other axes select — it never adds or removes substance. Anthropic's own register (corpus §5) for behavioral rules: third-person subject, present tense, positive-default + bounded exception — use for skill/system content regardless of output voice.
