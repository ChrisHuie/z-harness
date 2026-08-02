---
name: feedback_exception_class_partition_needs_condition_mapping
description: "Never reuse an exception-class tuple across consumers — map CONDITION→class for the new consumer's question; one class carries conditions whose correct handling is opposite"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 911b3dd8-a6f2-4ab8-a7bb-b9d69b117cd7
  modified: 2026-07-28T22:39:12.924Z
---

When code branches on an exception **class** to answer a control-flow question ("must this escape
my per-item isolation?", "should I retry?", "is the connection gone?"), the class is a proxy. Ask
which **conditions** land in that class, and whether they all deserve the same answer to *this*
question. Reusing a tuple that already exists for a *different* consumer's question is a
semantic-boundary violation even when the tuple is correct where it came from.

**Why:** we recommended `except (OperationalError, DisconnectionError): raise` above a broad catch
so a DB outage would still reach the session layer's circuit breaker. We derived that membership by
copying it from the breaker arm itself — a derived authority — instead of asking which conditions
must escape isolation. In psycopg2, `QueryCanceled` (statement timeout), `DeadlockDetected`,
`SerializationFailure`, `LockNotAvailable`, `TooManyConnections`, `AdminShutdown` and `DiskFull`
**all** subclass `OperationalError`. Every one is a per-statement failure on a *live* connection —
precisely what a per-item SAVEPOINT exists to absorb. So the recommendation converted the single
most likely per-row failure into a whole-batch abort plus a process-global fail-fast, and it did so
on a signal that SQLAlchemy itself contradicts: `DBAPIError.connection_invalidated` was `False`.
Simultaneously the tuple **omitted** `InterfaceError` and `sqlalchemy.exc.TimeoutError` — real
connection-gone classes — so those got silently isolated. Wrong in both directions, from one copied
set. Exporting the tuple to a single constant (the fix a reviewer asked for) removed the *copy*
problem and left the *membership* problem completely untouched.

**How to apply:**
- Enumerate conditions, not classes. `python -c "import psycopg2.errors as e; issubclass(e.X, psycopg2.OperationalError)"` for each condition you can name, then decide per condition.
- Prefer the library's own semantic flag over a class check where one exists — here `getattr(exc, "connection_invalidated", False)`, set by the dialect's `is_disconnect`, which tests the raw connection's `closed` flag and message patterns. Read the dialect source; the class was never the signal.
- One constant answering N questions is the tell. Retry, back-off/breaker, and isolation-escape are three different predicates; if they share a tuple, at most one of them is right.
- Take the probe to real infrastructure. A synthesized `raise OperationalError(...)` from Python does not poison a transaction, so it will show the isolation "working" when a genuine timeout does not — that exact false negative appeared in an earlier round of the same review.

Same root shape as [[feedback_recovery_audit_coherence_blind_to_condition]] and
[[reference_adcp_spec_grounding]] (validate against the source, not a derived authority), applied
to control-flow classification rather than wire semantics. Related:
[[feedback_claimed_invariant_needs_failing_oracle]], [[feedback_trace_flows_not_claims]].
