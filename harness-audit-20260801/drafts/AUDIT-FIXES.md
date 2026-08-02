# Cross-skill audit — fix pass, 2026-08-02

Applied against `drafts/final/`. Nothing outside `drafts/` was touched; `~/.claude/CLAUDE.md`
and `~/.claude/skills/` are unchanged. Findings are `CROSS-SKILL-AUDIT.md` F-numbers.

Body byte cap = 5,000 B measured **after the frontmatter**, the same instrument the builders
used (`agent-dispatch/references/deferred.md` records its body as 4,984 B; that reproduces).
The cap governs the seven method skills. The four authoring skills (`craft-*`,
`review-prompt`) were built to a ≤500-line cap instead and are 7.5–12.5 KB; none crossed 500
lines before or after this pass.

---

## Fixed

| # | file | change |
|---|---|---|
| F30 | `testing-ci/SKILL.md` + its `deferred.md` | 7 headings renamed/marked `[body]`; body pointer names all 7 verbatim. **7/7 resolve.** |
| F31 | `system-design/SKILL.md` + its `deferred.md` | body pointer replaced with 6 verbatim heading names, each marked `[body]`; the other 6 sections declared as reachable from the file's own ToC. **6/6 resolve.** |
| F29 | `system-design/SKILL.md:8` | "approval queues" removed — the content is in the body itself (`Irreversible effects`), not the reference. |
| F32 | `git-workflow/SKILL.md:82-84` | body now names **both** reference files; `claude-md-lines.md` cited with what it holds. |
| F4/F25 | `outbound-drafts/SKILL.md:70`, `pr-review-method/SKILL.md:59` | scoped both sides + anti-triggers added. See the ruling below. |
| F5 | `craft-prompt/SKILL.md:84,99` | `## Verify` now ends with a line naming what the prompt was **not** exercised against, declared as the only sanctioned tail. |
| F6 | `craft-context-file/SKILL.md:36` | ladder restated strongest-first (hook/tool → this file → skill → scoped), and "migrates down, never up" replaced with a bidirectional rule that names the move UP out of a project silo. |
| F7 | `craft-skill/SKILL.md:38,54` + 6 descriptions | 400 governs; 1024 named as the spec ceiling it sits inside. Six descriptions rewritten in user-sayable text. |
| F8 | `outbound-drafts/SKILL.md:42` | anonymize-to-roles vs strip-process-controls separated as two acts. |
| F26/F27 | `craft-prompt` description | now routes `draft` → `outbound-drafts` and `instructions` → `craft-context-file`. |
| F9 | `CLAUDE.md` preflight | reclaim-order rule placed. **Caveat below.** |
| F10 | `system-design/SKILL.md` (Containment) | R172 trust-anchor rule placed; both deferred files corrected so neither points at the other any more. |
| F11 | `git-workflow/references/deferred.md` | R281 placed with the path verified on this machine. **Placed in the reference, not the body — reason below.** |
| F12 | `agent-dispatch/SKILL.md` (Grading what comes back) | disagreement-resolution rule + hedging-word tell placed. |
| F13 | `CLAUDE.md` Claims and evidence | "name the optimism bias out loud when felt" restored. |
| F17/F18/F19 | `agent-dispatch/SKILL.md` | three always-on paraphrases cut, unique mechanism kept. |
| F20 | `outbound-drafts/SKILL.md:49-53` | "no detector names" and "echoing the user's own framing does not exempt it" cut — both verbatim-in-sense in always-on. |
| F21 | `git-workflow/SKILL.md:30`, `pr-review-method/SKILL.md:29` | lead sentences cut, unique content (red-tree-in-between, enumerate-the-spellings, zero-hit evidence) kept. |
| F22 | `pr-review-method/SKILL.md:46-47` | one copy cut. **The justification is struck, not re-argued — see below.** |
| F15 | `CLAUDE-MD-ASSEMBLY.md:75` | false "now in the `git-workflow` body" struck; `/code-review ultra` re-labelled unverified. |

### Verified already fixed by Chris, not redone

- **F1.** `CLAUDE.md:112-116` splits the ladder into *what it does* (artifact first) and *what
  it must do* (normative text first). `prebid-adcp:25-29` is the second ladder specialized, so
  it no longer contradicts. One clause added to `prebid-adcp` to say so explicitly, because
  the section heading did not scope itself and read as a universal ranking.
- **F2.** `pr-review-method:66-67` carries the gate. `:61`'s unconditional "post as inline
  threads" was still an unconditional imperative about the banned act, so it was reworded to
  set the *shape* only ("an inline thread is its delivery shape"); the act stays gated at the
  next bullet.
- **F3.** Cost section present at `CLAUDE.md:140-145`, 6 lines.
- **F28.** `system-design` and `outbound-drafts` rows present at `CLAUDE.md:14-15`.

---

## Rulings that needed a decision

### F4/F25 — inline threads vs one comment per PR

**They govern different objects, and both were written as if they governed all of them.** A
*finding* is a thread: it has an addressed/declined lifecycle, an anchor, and an author who
must answer it. A *roll-up* is one comment: it is a snapshot of a head SHA, and a second copy
per round is noise. Neither builder was wrong about its own object; both stated it
unconditionally.

- `outbound-drafts:70` → "**One roll-up comment per PR** … **This governs the summary only.**
  An individual review finding is an inline `path:line` thread with its own lifecycle
  (`pr-review-method`)."
- `pr-review-method:59` → "an inline thread is its delivery shape … that comment is the
  roll-up's (`outbound-drafts`)."
- Anti-triggers added **both ways**, which is what F25 asked for: `outbound-drafts` now ends
  "nor finding-by-finding PR review (pr-review-method)"; `pr-review-method` now ends "Not for
  a general outbound message (outbound-drafts)."

Registry **R063** is therefore IN for `outbound-drafts` and OUT for `pr-review-method`, and
that split is now stated in both bodies rather than inferred.

### F22 — the sanctioned scan-set duplicate

The justification (a PR-review turn loads one and not the other) **does not survive its own
test**, exactly as the audit found. Rather than re-justify it, the duplicate was cut: the
mechanism sentence stays in `testing-ci` (with the print-the-roots/exit-on-zero-inputs
detail), and `pr-review-method` keeps only its review-specific delta — include prose surfaces
— plus a pointer. Nothing was re-justified, so the reasoning is not available for the next
duplicate.

### F7 — which cap governs

**400.** It is stated in one place, `ROUTING-RULE.md:99`, unchanged. `craft-skill:38` now
defers to it and names 1024 as the spec ceiling it sits inside rather than as the cap.

Description tax, measured: **5,602 → 4,012 chars, −1,590** across the eleven skills.
`craft-context-file` alone: **964 → 381, −583**, and "Scans the repo for non-derivable facts"
— the exact string `ROUTING-RULE` names as pure tax — is gone.

Six descriptions changed: `craft-context-file`, `craft-prompt`, `craft-skill`,
`review-prompt`, `outbound-drafts`, `pr-review-method`. Five were rewritten to cut mechanism
narration; `pr-review-method` grew 7 chars because it gained an anti-trigger it did not have.

---

## Placements that were not the obvious one

**F9 — the reclaim order is a rule, not an order.** Placed at `CLAUDE.md` preflight as
"**Decide the reclaim order before the fan-out, not at 100%**, and if the data volume cannot
be cleared in time point `TMPDIR` at one with room." **The concrete order — what to delete
first — is recorded in no source in this tree.** `agent-dispatch/references/deferred.md:44-48`
says so directly. Writing a specific order would have been invention, so the rule is placed
and the order is still open. Resolve it empirically and extend that sentence.

**F11 — R281 went to the reference, not the body.** `git-workflow`'s body had 0 B of headroom
and the rule is rank B; the reference is where its two neighbours (the hook-abort rule's
mechanism, the per-push scoping) already live, and the body's pointer now names it, so it is
reachable. The path is **verified on this machine, not assumed**:
`ls ~/.cache/pre-commit/` returns `patch<epoch>-<pid>` files (e.g. `patch1779420209-42688`,
100+ siblings, 2026-08-02). The entry says to confirm it before relying on it elsewhere.

**F12 — went to `agent-dispatch`'s body, not `CLAUDE.md`.** It fires when reading what an
agent returned, and `CLAUDE.md:12` mandates loading `agent-dispatch` "before believing what
they report", so the body arrives in time — ARRIVAL gate A1 does not fire.

---

## Content moved from a body to its reference to pay for the above

Each is a straight swap, recorded at both ends, promotable back without a rewrite.

| rule | from | to | why |
|---|---|---|---|
| A ceiling without a floor is half an authority model | `system-design` body | its `deferred.md` § Authority | paid for R172 (F10) |
| Copy edge-case-dense modules verbatim with their tests | `system-design` body | its `deferred.md` § Migration sequencing | paid for R172 (F10) |
| R287 zsh `:s` brace | `git-workflow` body | its `deferred.md` § zsh `:s` brace | rank B; paid for naming `claude-md-lines.md` (F32) |
| Read a branch-only corpus with `git show` | `git-workflow` body | its `deferred.md` intro | read-only, and the body's own scope line is "operations that CHANGE a repo" |
| R282 stale exported env vs listening port | `agent-dispatch` body | its `deferred.md` § MACHINE | rank B container fact; paid for F12 |
| "Binds hardest once an author adopts your wording" | `pr-review-method` body | cut, not moved | a nuance about when the rule binds, not the rule |

`pr-review-method`'s body was **5,072 B when this pass started — 72 B over cap**, because the
F2 fix landed without a compensating cut. It is 4,991 B now.

---

## NOT fixed — with the reason

- **F23 — `review-prompt:29` restates the snapshot/flattened-layout rule and then cites
  `craft-skill`.** Left as is. R2 governs content duplicated *inside one request*; these two
  descriptions do not co-fire (one authors, one critiques, and each carries the other in its
  anti-trigger half). Cutting the restatement would leave a bare pointer to a skill that is
  not loaded on that turn, which is a delivery loss, not a byte saving.
- **F24 — ~1.5 KB of shared Step-1/Red-flags/Validation scaffolding across the four authoring
  bodies.** The audit already classes it informational. It is template prose, not rules, the
  four rarely co-fire, and factoring it into a shared reference is a restructure of four
  bodies — out of scope for a fix pass, and it would break 71 reference pointers that
  currently resolve only against the installed tree (see below).
- **F33 — `craft-context-file` names 4 of its 5 installed references, and the four authoring
  skills have no `references/` under `drafts/final/` at all.** Both are fixable only by
  writing into `~/.claude/skills/`, which is out of write scope. **This is the largest
  unresolved risk in the tree: if `drafts/final` is deployed as a self-contained set, all 71
  of those pointers break at once.** Decide deploy-in-place vs copy-the-references before
  applying anything.
- **Row 16 of the installed `references/anti-patterns.md` still reads "description >1024".**
  All four copies are under `~/.claude/skills/`, out of write scope. So `craft-skill`'s body
  now says 400 while the catalog row its own Step 7 sweeps says 1024. **The body wins on read
  order, but this is a live inconsistency until those four files are edited.**
- **F14** — no action needed; both orphans were repaired before this pass and the eviction
  rationale that produced them is struck (F15).

## Not tested

- **No description was exercised against a live session.** Six descriptions changed, including
  five that were shortened by 232–583 chars. Trigger firing was not measured before or after;
  every user-sayable phrase was kept and only mechanism narration was cut, but that is an
  argument, not a measurement. `CLAUDE.md`'s imperative routing directive is what carries
  firing (3/28 → 14/14), so the descriptions are no longer the load-bearing channel — also an
  argument, taken from `PLAN.md` §7 and not re-run here.
- **No rule was checked for truth**, only for placement, reachability and non-contradiction.
- **`drafts/split2/` was not opened** except to confirm R281's registry row.
- **The four authoring bodies' own `references/` were not read** — they are not in this tree.
