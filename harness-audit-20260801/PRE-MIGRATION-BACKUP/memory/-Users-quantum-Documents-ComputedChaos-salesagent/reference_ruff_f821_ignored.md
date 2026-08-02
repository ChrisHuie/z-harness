---
name: reference_ruff_f821_ignored
description: "This project's ruff config IGNORES F821 (undefined-name), so missing imports only fail at runtime, not in `ruff check`"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8377e960-8e7a-4aba-8c4d-4aedb89a6629
---

`pyproject.toml` `[tool.ruff.lint] ignore` includes `F821` ("4 false positives from conditional imports and TYPE_CHECKING blocks"). It also ignores `F841` (unused local var).

**Consequence:** `ruff check` (and `make quality`) will NOT catch a missing import — an undefined name only surfaces at runtime as `NameError` (often inside a `pytest.raises`/test body, so even import-time checks miss it).

**How to apply:** When resolving merge conflicts on import lines, or editing imports, do NOT trust `ruff check` for import completeness. Verify by grepping actual symbol usages against the import lines (`grep -oE "AdCP[A-Za-z]+Error"` vs the `from ... import` lines), or run the tests. `ruff check --fix --select F401` still prunes *unused* imports correctly — the blind spot is *missing* ones. This cost 3 runtime test failures during the #1307 re-derivation (import unions that dropped a symbol a non-conflict test used). Related: [[feedback_wire_shape_change_systematic_sweep]].
