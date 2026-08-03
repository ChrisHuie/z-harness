---
name: Zero code changes during planning stage — planning and implementation are strictly separated
description: When the work is labeled planning, producing docs, audits, or specs, do NOT edit any code, config, scripts, or cron files. Planning deliverables are pure markdown/analysis. Code comes in a later explicit implementation stage.
type: feedback
originSessionId: 1a81e02d-b77f-4875-831c-116906aee29d
---
**Rule:** during a planning stage, zero edits to `src/`, `tests/`, `scripts/`, `crontab`, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/`, `Makefile`, shell scripts, or any other executable/config file. Planning produces markdown under `.claude/notes/`, memory under `~/.claude/projects/.../memory/`, and audit reports only.

**Why:** On 2026-04-14 during the v2.0 Flask→FastAPI migration planning stage, the user repeatedly requested "use ultrathink and opus subagents to investigate/verify/audit" — explicitly planning work. I misread a subsequent "let's implement" instruction as license to edit code, and started applying what I had framed as "TODAY defects" (crontab path, fly-set-secrets.sh, ruff target-version bump) to working files. That cascaded into `ruff --unsafe-fixes` rewriting 3 production schema files. The user interrupted and clarified: "we do not want any code in our planning stage — revert any code written because it shouldn't have been and is a violation of planning."

**How to apply:**
- **Default to revert when stage is ambiguous.** If I'm not 100% certain the user has transitioned from planning to implementation, I do not edit code. Ambiguous language like "let's use subagents to implement" in the context of an active planning thread means "implement the planning deliverables" (docs, specs), not "start writing production code."
- **"TODAY defects" are still code changes and still require planning-stage exit.** Even a trivial crontab path fix is a code change. During planning, it becomes a documented action item in a future implementation PR plan — not an edit to `crontab`.
- **Subagent scope contract.** When spawning implementation subagents, explicitly state "planning stage — produce spec only, no file edits" OR "implementation stage approved — file edits in scope." If the stage isn't explicitly marked implementation, it's planning.
- **Config bumps are code changes.** Ruff `target-version`, mypy strictness, pyproject pins — all code changes, not planning artifacts.
- **Recovery protocol when caught:** immediately `git checkout -- <all modified paths>` to fully revert. Confirm `git status` shows clean working tree. Then save the rule to memory. Do not re-attempt the edits under a different framing.
- **Planning-stage deliverables look like:** new files under `.claude/notes/flask-to-fastapi/*.md`, audit reports in subagent transcripts, memory files under `~/.claude/projects/*/memory/`, summaries in conversation text. Nothing else.
