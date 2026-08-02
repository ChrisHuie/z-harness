verified: 2026-07-14 · sources: prompt-craft §4; example-corpus §2/§3/§10; anti-patterns rows 7/16

# Checklist: authoring a skill

## Description (the API — do this hardest)

- [ ] Archetype chosen: A trigger-first imperative ("Use this skill whenever…", exhaustive operation+phrasing enumeration) for consumer/file-type skills; B capability+use-when ("<Noun-phrase capability>. Use when…") for developer/method skills. Never mix POV within one description.
- [ ] Triggers front-loaded (Codex truncates); literal user phrasings included ("the xlsx in my downloads").
- [ ] Anti-triggers present: `Do NOT use for/when …` naming the near-miss cases.
- [ ] Honest + human-legible (consent gates show it); ≤1024 chars; no XML; long-and-dense is correct.
- [ ] Name: verb-first (ours) or gerund; lowercase-hyphen; == directory name; never helper/utils; no reserved words (anthropic/claude).

## Body (a navigation hub, not a textbook)

- [ ] <500 lines; quick-start or contract first; imperative steps with explicit inputs/outputs.
- [ ] Section order: Overview → When to use → Method → Anti-patterns/Red flags → Verification (self-check tail is house standard).
- [ ] Copy-able checklists for multi-step flows; task→outcome table where the skill covers many operations.
- [ ] Degrees-of-freedom split: judgment → prose; deterministic/fragile → exact scripts ("Run exactly…, do not modify"); scripts solve-don't-punt, no voodoo constants, `--help`-first.
- [ ] References: one level deep; ToC for any reference >100 lines; domain-partitioned so only the relevant one loads; no time-sensitive phrasing.
- [ ] Frontmatter: portable core only in canonical source (name, description, license, compatibility, metadata.version); harness extras (allowed-tools, argument-hint) via per-target overlay — now real: `skills/<name>/overlays/<target>.yaml`, merged by @prompt-harness/emitters (plan 2026-07-14-phase-2 DoD-5).

## Quality gates

- [ ] Eval scenarios existed BEFORE this body (evals-first); baseline captured.
- [ ] Sweep against references/anti-patterns.md (all 24 rows).
- [ ] Fresh-session exercise (Claude A/B): author never grades their own trigger behavior.
- [ ] Budgets: description within listing caps; body within compaction re-attach budgets.
- [ ] Security: ingests external content? → untrusted-content block present. Destructive tools? → approval gate. Narrowest tool/dir scope declared.
