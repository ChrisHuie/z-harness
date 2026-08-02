---
name: feedback-uow-detached-after-exit
description: "SQLAlchemy ORM objects returned from UoW.repo lookups are detached when the `with` block exits — accessing column attrs outside the block can raise DetachedInstanceError or return stale data. Either keep usage inside the block or copy attrs to locals"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

ORM model instances returned from `uow.<repo>.find_*()` are bound to the UoW's session. When the `with PushNotificationConfigUoW(...) as uow:` block exits, `BaseUoW.__exit__` commits the session then closes it (per `src/core/database/repositories/uow.py:95-112`). After exit:

- `expire_on_commit=True` (SQLAlchemy 2.0 default) means commit expires the instance's column attributes.
- `session.close()` then makes those expired attributes unrefreshable.
- Reading any column attr outside the block (e.g., `config.authentication_type`) → likely `DetachedInstanceError`, or stale data depending on whether attrs were already populated.

**Why:** Surfaced in PR #1311 audit at `src/services/order_approval_service.py:565-585` where `_send_approval_webhook` does:
```python
with PushNotificationConfigUoW(tenant_id) as uow:
    config = uow.push_notification_configs.find_active_by_url(principal_id, webhook_url)

# Block exited — config attrs now detached/expired
if config:
    if config.authentication_type == "bearer" and config.authentication_token:  # ← hazard
        ...
```
The unit test (`tests/unit/test_order_approval_service.py:241`) mocks `find_active_by_url.return_value = mock_config` (in-memory, not session-attached), so the test passes green while production hits the detached path. P23 + UoW lifecycle interact: mock-only tests don't catch lifecycle bugs.

**How to apply:** When using a UoW lookup whose return value is needed *after* the `with` block:

1. **Preferred — keep usage inside the block.** All reads against the returned ORM model happen before `__exit__` runs.
2. **Acceptable — copy needed scalar attrs to local variables** before exit:
   ```python
   with PushNotificationConfigUoW(tenant_id) as uow:
       config = uow.push_notification_configs.find_active_by_url(principal_id, webhook_url)
       auth_type = config.authentication_type if config else None
       auth_token = config.authentication_token if config else None
   # Block exited — use the local scalars, not `config` itself
   if auth_type == "bearer" and auth_token:
       ...
   ```
3. **Avoid** `session.expunge(config)` as a workaround — it detaches the instance but doesn't refresh expired attrs.

**Detection rule:** When reviewing UoW usage, scan for any attribute access on a UoW-returned model *after* the `with` block's dedent. If found, that's a hazard. Add an integration test (real PostgreSQL via `IntegrationEnv`) that exercises the path — the hazard reproduces under real session lifecycle but is masked by mock-based unit tests.

Related: [[feedback_mock_only_tests_dont_prove_wiring]] (P23), CLAUDE.md § "Database: Repository Pattern + ORM-First".
