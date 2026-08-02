# GitHub Activity DB - Memory

- [No real names in DB](no-real-names-in-db.md) — only GitHub logins stored; enrich via `GET /users/{login}`

## Project Overview
- SQLite + SQLAlchemy 2.0 async + Pydantic 2.0 for GitHub PR data from 8 Prebid repos
- CLI: `uv run ghactivity`, Tests: `uv run pytest` (583+ tests), Types: `uv run mypy src/ tests/`
- DB file: `github_activity.db` at project root

## Key Patterns
- **Nested JSON fields**: Follow `commits_breakdown`/`participants`/`file_changes` pattern:
  - Pydantic model in `schemas/nested.py` + `from_list()`/`to_list()` helpers
  - `field_validator` in `PRSync` to parse from dicts
  - `get_*_typed()` method in `PRRead` for typed access
  - Serialize via helper in `_sync_data_to_dict()` in repository layer
- **Test factories**: `tests/factories.py` has `make_repository`, `make_pull_request`, `make_merged_pr`
- **Fixtures**: `tests/conftest.py` has date constants (JAN_10 through JAN_20) and sample data dicts
- **Contract tests**: `tests/fixtures/` has real GitHub API responses for integration testing
- **Alembic**: Uses `render_as_batch=True` for SQLite compatibility

## Recent Changes
- Added `file_changes` column (was `filenames`): stores per-file stats (filename, status, additions, deletions, changes)
- Migration `b3c4d5e6f7g8` converts legacy `["file.go"]` → `[{"filename": "file.go", "status": "unknown", ...}]`
- Fixed `last_synced_at` bug: `update_last_synced()` was never called in `BulkPRIngestionService`
- `CommitManager.commit()` has early return when `_uncommitted_count == 0` - must call `record_success()` before `finalize()`

## Gotchas
- Ruff has 5 pre-existing UP046/UP047 warnings about Generic style - these are expected
- `dict[str, str | int]` type for JSON columns: `dict.get()` returns union type, use `str()` wrapper for mypy
- PRRead.filenames property kept for backward compat but delegates to file_changes
