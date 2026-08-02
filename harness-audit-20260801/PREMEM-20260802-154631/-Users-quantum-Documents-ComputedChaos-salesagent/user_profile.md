---
name: user-profile
description: "Chris, @chrishuie on GitHub. Solo maintainer driving an agent team. No beads. Docker novice — explain concepts. Owns all remote-mutating git/gh ops; no fork/clone without permission."
metadata: 
  node_type: memory
  type: user
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

(Merges user_github_handle + user_docker_experience + feedback_no_beads_workflow + feedback_no_fork_clone, 2026-06-11.)

- **GitHub handle: @chrishuie** (matches issue #1233 author "Chris Huie" in prebid/salesagent). The git commit author name shown in env blocks has varied ("agentmoose", "chrishuie") — it is the local commit identity, not proof of the GitHub account. Use @chrishuie for CODEOWNERS, reviewer lists, and @-mentions.
- **Execution model: solo + agent team.** Implements entirely with agents (implementation, review, refactor, evaluation) — see [[feedback_agent_team_execution_model]] for how that reshapes process docs.
- **No beads.** The beads/`bd`/formula infrastructure belongs to another contributor (the repo's `.claude/rules` beads workflow files are theirs). This user works with standalone Claude Code skills + standard git. New skills: no `bd` steps or formula deps — direct tools + `make quality` / `./run_all_tests.sh` for validation.
- **Docker: novice.** Explain what each step does and why, not just commands. Don't assume Docker knowledge.
- **Permission boundaries:** user owns `git push`, `gh pr create`, and every remote-mutating op ([[feedback_user_owns_git_push]]). Never fork or clone repos without explicit permission.
