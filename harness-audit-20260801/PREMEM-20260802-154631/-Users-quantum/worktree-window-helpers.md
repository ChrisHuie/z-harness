---
name: worktree-window-helpers
description: User has prw/iss/wt-ls zsh helpers to open a GitHub PR or issue in its own isolated VS Code window
metadata: 
  node_type: memory
  type: reference
  originSessionId: cb63c40b-54ff-4db7-8b11-d183d2e7a5e4
---

User works with coding agents a lot and wanted to open a GitHub PR or issue in a **separate** VS Code window without hijacking another window from the same repo (GitHub Desktop / `code .` reuse the existing window). Solution: a git worktree per PR/issue.

Installed at `~/.oh-my-zsh/custom/worktree-windows.zsh` (auto-sourced by oh-my-zsh). Commands, run from inside the repo:
- `prw <pr#|url>` — checks out the PR branch into `~/worktrees/<repo>/pr-<n>`, opens `code -n` there
- `iss <issue#|url>` — new branch `issue-<n>` off the default branch in `~/worktrees/<repo>/issue-<n>`, opens it
- `wtnew [name]` — fresh worktree off `origin/<default-branch>` in `~/worktrees/<repo>/new-<name>` (branch `scratch/<name>`), opens `code -n`; no PR/issue needed. Bare `wtnew` auto-names `main-<timestamp>`. Use this to open a repo in a separate isolated VS Code window without disturbing the one already open.
- `prw-clean <n>` / `iss-clean <n>` / `wtnew-clean <name>` — remove that worktree + local branch
- `wt-ls` — list this repo's worktree windows
- `export WT_EDITOR=cursor` switches the editor from `code` to Cursor

If asked to open a PR/issue in a window, prefer these. To revert the whole thing, just delete that one file.
