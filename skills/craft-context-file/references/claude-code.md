verified: 2026-07-14 · sources: landscape §3 (Claude Code), example-corpus §4/§5, concepts M4 (capability tier)

# Harness profile: Claude Code

**Default model family:** Claude. **Capability tier: T3** (tool restrictions + dynamic injection + hooks).

## Skill directories + precedence
- `~/.claude/skills/`, `.claude/skills/`, plugins, enterprise config. Nested dirs give scoped names (`apps/web:deploy`). Live-reload on edit (a brand-new skill dir needs a restart — issue #38707).
- Slash commands merged into skills; `.claude/commands/` still works; **skill wins on a name clash**.
- Does NOT read the portable `.agents/skills/` — bridge by mirroring the canonical source into `.claude/skills/`.

## Frontmatter dialect (beyond spec core)
`when_to_use`, `argument-hint`/`arguments` (`$ARGUMENTS`, `$1`…, named), `disable-model-invocation`, `user-invocable`, `allowed-tools`/`disallowed-tools`, `model`, `effort`, `context: fork`, `agent`, `hooks`, `paths` (glob-gated activation), `shell`; dynamic injection via `` !`cmd` ``.

## Budgets
Skill listing ≈ 1% of context. Per-entry description text capped at **1,536 chars** (deviation from spec's 1,024). Post-compaction re-attach budget 25k tokens.
Deviations to design around: `name` optional (dir-derived); description cap 1,536 vs spec 1,024; no `.agents/skills/`; no native `AGENTS.md` ([issue #6235](https://github.com/anthropics/claude-code/issues/6235) open) — bridge via `@AGENTS.md` import in `CLAUDE.md` or a symlink.


## Invocation mechanics
Implicit (description match) + explicit (slash command / `user-invocable`). Arguments via `$ARGUMENTS`, positional `$1`…, or named — verified for Claude Code.

## Enforcement surfaces
Permission modes/rules + PreToolUse/PostToolUse hooks are the real tool restriction; plus `paths` glob-gating, `context: fork` isolation, `` !`cmd` `` runtime injection. **Verified 2026-07-14:** `allowed-tools` in SKILL.md frontmatter is advisory permission-smoothing only — parsed, never enforced (https://github.com/anthropics/claude-code/issues/37683); documented syntax is comma-separated or array. Read-only stances therefore rest on prose + permission rules/hooks, not skill frontmatter.

## Capability tier justification
**T3** — tool restriction via permission rules + hooks (T2; skill-frontmatter `allowed-tools` is advisory only) AND runtime dynamic injection + hooks (T3). The reference implementation of the spec's rich end.

## Headless (evals)
Legacy captures use `claude -p --output-format json` (+ `--json-schema`, `--max-budget-usd`); output shape varies (single result object vs event array), so parse both. Controlled runs use `stream-json`, retain structured init evidence, and reject malformed/empty/provider-error streams before grading.


## Native version and update controls

verified: 2026-07-15 · primary sources: [advanced setup](https://code.claude.com/docs/en/setup), [environment variables](https://code.claude.com/docs/en/env-vars), [settings table](https://code.claude.com/docs/en/settings#available-settings)

- Native installations check for updates at startup and periodically, install them in the background, and activate them on the next process start. On macOS/Linux, the managed launcher points into `~/.local/share/claude/versions/`; from 2.1.207 onward, a custom launcher is preserved and newly installed siblings do not determine which version it launches.
- `DISABLE_AUTOUPDATER=1` disables automatic background updates while leaving manual update/install commands available. `DISABLE_UPDATES=1` blocks background and manual update/install paths. The current environment-variable reference explicitly documents both names and the value `1`.
- For controlled measurement, set both variables in the frozen launch environment. Their presence proves only which environment the runner requested; Anthropic documents no independent runtime attestation that the internal updater honored them. Bind executable identity separately through the direct versioned path, reported version, and binary hash.
- Releases from 2.1.89 onward publish a detached-signed manifest containing platform SHA-256 values. Verify the selected binary against that manifest and the documented release-key fingerprint before qualification, then record the manifest digest, signature result, fingerprint, and binary digest. Hash the selected version binary/package rather than the parent `versions/` directory so installation of an unused sibling is not misclassified as execution drift.
- `minimumVersion` constrains updates but does not block startup. The primary [`requiredMaximumVersion` and `requiredMinimumVersion` settings rows](https://code.claude.com/docs/en/settings#available-settings) explicitly mark both fields managed-only, state that older versions predating each setting ignore it, and state that `claude update`, `claude install`, and `claude doctor` remain available outside the allowed range for recovery. Invalid managed values are stripped and fail open. On macOS, file-based managed policy lives under `/Library/Application Support/ClaudeCode/`; managed sources outrank command, project, and user settings and therefore remain active independently of a fresh user config home.
- Treat exact managed version bounds as optional dedicated-host defense-in-depth, not a portable baseline. Before relying on them, use a zero-provider-call canary in a disposable or exclusively controlled host to prove that the in-range binary passes the startup version gate, an adjacent version refuses before network/model execution, invalid policy is surfaced by the runner's own gate, and the complete highest-precedence managed-policy source and hash are observable. Do not mutate a shared machine's policy merely to run an experiment.
