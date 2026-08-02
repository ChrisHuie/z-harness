---
name: uv-venv-corruption-reinstall
description: "Repeated branch-switches + uv syncs can leave .venv packages corrupted (files gone but uv still lists them installed) → ModuleNotFoundError / griffe 'unknown location' despite `uv sync` saying 'Audited N packages'. Fix: uv sync --reinstall."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8377e960-8e7a-4aba-8c4d-4aedb89a6629
---

After many branch checkouts + `uv sync` / `uv lock --upgrade-package` cycles in one session, individual packages in `.venv` can become CORRUPTED — `uv pip list` shows them installed at the right version, but `import <pkg>` raises `ModuleNotFoundError` (or `ImportError: cannot import name X from <pkg> (unknown location)`). A plain `uv sync` does NOT repair it — it reports "Resolved … / Audited N packages" and considers the env in sync (it trusts its own metadata, not the on-disk files).

**Symptom that masquerades as a real failure:** `make quality` mypy reports spurious `Unused "type: ignore"` errors. Mechanism: a type-only dependency (e.g. fastmcp) is corrupted/unimportable, so mypy can't resolve the parent types the ignore covers → the override/misc error doesn't fire → the ignore looks "unused." This is NOT a code issue and NOT caused by whatever you just changed; it's the broken env. (Burned ~30 min on PR #1307 chasing a pyjwt bump that wasn't the cause — the real cause was a corrupted fastmcp + griffe install.)

**How to apply:**
- If `import X` fails but `uv pip list` shows X installed, the venv is corrupted, not the lock.
- Repair one package: `uv sync --reinstall-package <name>`. Repair all: `uv sync --reinstall` (rebuilds the whole venv from the lock; slower but reliable).
- After ANY surprising mypy/import failure following branch-switches, FIRST verify the env (`uv run python -c "import <suspect>"`) before concluding it's a code/dep problem. Ties [[feedback_verify_before_asserting]] and [[feedback_truth_over_optimism]] (don't attribute to your change without checking the env).
