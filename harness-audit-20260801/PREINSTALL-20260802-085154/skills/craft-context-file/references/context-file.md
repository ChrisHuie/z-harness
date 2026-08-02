verified: 2026-07-14 · sources: prompt-craft §5; example-corpus §4/§10; anti-patterns row 11

# Checklist: authoring a context file (AGENTS.md / CLAUDE.md / GEMINI.md)

- [ ] Short: CLAUDE.md <200 lines; AGENTS.md well under Codex's 32KiB combined cap. Every line competes for the attention budget.
- [ ] Non-derivable only: commands the agent can't guess, non-default conventions, repo etiquette, environment gotchas. Delete anything inferable from code, README, or standard practice ("would removing this cause mistakes?").
- [ ] Commands-first, exact and named: `pnpm test`, not "run the tests"; `<placeholder>` syntax for substitution points.
- [ ] Sections that earn their keep: setup commands, testing instructions, code style (non-default only), PR/commit rules, environment tips.
- [ ] Positive instructions; decision rules over absolutes; caps only on true invariants (destructive-command bans, mode gates).
- [ ] Stable-prefix ordering: durable rules first; volatile content last or nowhere; no timestamps.
- [ ] Monorepos: directory-scoped files (nested AGENTS.md / path-scoped rules), nearest-wins; machine-generated blocks fenced with markers.
- [ ] Routing check: always-on rule → this file; on-demand knowledge/workflow → a skill; must-happen-every-time → a hook (prose is a request; a hook is enforcement); path-specific → scoped rules. Migrate content down that ladder, not up.
- [ ] Bridge pattern where needed: AGENTS.md as source + `@AGENTS.md` import in CLAUDE.md with a harness-specific addendum section.
- [ ] Never auto-generate-and-forget: generated drafts duplicating the README measurably hurt task success — curate by hand.
