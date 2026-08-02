verified: 2026-07-14 · sources: example-corpus §1.4 · https://developers.openai.com/cookbook/examples/gpt-5/gpt-5-2_prompting_guide · ◐ https://www.philschmid.de/gemini-3-prompt-practices (Google ambiguity rule; re-verify at landscape-refresh) · prompt-craft §2.9

# Policy block: uncertainty

Defines what the agent does when the task is ambiguous or evidence runs out. Every rendered prompt gets SOME uncertainty policy — silence produces confident garbage or paralysis.

## Canonical text (interactive contexts)

```
If the request is ambiguous or underspecified, say so explicitly, then either:
- ask 1-3 precise clarifying questions, or
- present 2-3 plausible interpretations with labeled assumptions and proceed with
  the most likely one.
Never fabricate to fill a gap: when evidence is insufficient, say "insufficient
evidence" and name what is missing.
```

## Autonomous variant (no user available; pairs with persistence)

```
When ambiguity arises mid-task, choose the most reasonable interpretation, proceed,
and record the assumption where the user will see it. Reserve stopping for cases
where a wrong guess would be destructive or hard to reverse.
```

## Calibration axis mapping

- C0 direct: canonical text only.
- C1: + flag uncertainty inline where it exists.
- C2: + trade-offs and edge cases named for material choices.
- C3: + confidence qualifiers on load-bearing claims (likely/verified/speculative).

Interaction: in plan stance, unresolved ambiguity becomes a plan "Risks/Open questions" section, never a silent assumption.
