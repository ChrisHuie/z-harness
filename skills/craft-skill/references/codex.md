verified: 2026-07-14 · sources: landscape §3 (OpenAI Codex, CLI 0.144.x) + §12, example-corpus §5, concepts M4

# Harness profile: OpenAI Codex

**Default model family:** GPT-5.x. **Capability tier: T2** confirmed (sandbox/approval tool restriction); hooks + subagents give a T3 surface at harness level; skill argument passing (T1) **verified working** — `$skill-name` + trailing `key=value` grammar (spike Q1, 2026-07-14).

## Skill directories + precedence
- `.agents/skills/` (cwd → repo root), `~/.agents/skills/`, `/etc/codex/skills`. Honors `name` + `description`.
- Optional `agents/openai.yaml` sidecar for UI config + tool deps.
- Custom prompts (`~/.codex/prompts`) **deprecated in favor of skills**.

## Frontmatter dialect
Spec core (`name`, `description`) + the `agents/openai.yaml` sidecar: `interface` (display_name, short_description, icons, brand_color, default_prompt), `policy.allow_implicit_invocation`, `dependencies.tools` (MCP servers). Config rides the sidecar, not inline fields.

## Budgets
- Skill index capped at ~2% of context or **8k chars** — front-load triggers so a shortened description still matches.
- `AGENTS.md` concatenated git-root→cwd (closer overrides); precedence `AGENTS.override.md` → `AGENTS.md` → fallbacks; **32 KiB combined cap** (`project_doc_max_bytes`).

## Invocation mechanics
Implicit (description match) or explicit (`$skill-name`). `$skill-name` plus trailing `key=value` arguments is verified working (spike Q1); the target profile must still preserve ordinary trailing prompt text for portable fallback.

## Enforcement surfaces
`approval_policy.skill_approval` (gates skill use), `sandbox_mode` (read-only / workspace-write), approval policy, hooks (`hooks.json`: PreToolUse/PostToolUse/SessionStart/Stop), subagents (TOML in `.codex/agents/`).

## Capability tier justification
**T2** firmly via sandbox + approval tool restriction. Hooks/subagents give a T3 surface at harness level; skill argument passing (T1) is verified, while skill-frontmatter-native restrictions remain narrower than the harness surface.

## Headless (evals)
`codex exec` with `--json`, `--output-schema`, `--output-last-message`. Controlled raw runs use a fresh auth-only `CODEX_HOME` plus `--ignore-user-config`, `--ignore-rules`, `--ephemeral`, an explicit sandbox, and closed stdin. The measurement sentinel requires an evidence-linked exact-version adapter profile and proves `/etc/codex/skills` absent before execution; an unverified CLI version fails preflight rather than inheriting 0.144.4 assumptions. The 0.144.4 JSONL sentinel did not expose actual model identity, so its report records `unknown` and forbids causal/provider claims that require a verified actual model.

## Models + KNOWN-UNVERIFIED (spike questions)
- Models mid-2026: `gpt-5.6-sol/terra/luna`, `gpt-5.5`; OpenAI advises not pinning models in ChatGPT-auth sessions.
- Spike ledger (resolutions 2026-07-14): Q1 RESOLVED — `$skill-name` + trailing `key=value` works. Q2 RESOLVED — re-copied skills picked up on next `codex exec` (each exec is fresh; interactive hot-reload untested). Q3 partial — ~600-char descriptions fine; 8k-cap boundary UNVERIFIED. Q6 RESOLVED — 6/6 MVP triggers + 3/3 anti-probes (audit-fix pass). Q8 RESOLVED — copy-based install. Codex skills origin version — still UNVERIFIED (§12 risks).
- Headless quirks (observed 2026-07-14): `codex exec` refuses untrusted non-git dirs without `--skip-git-repo-check`; close stdin when detached (it reads additional input from stdin).
