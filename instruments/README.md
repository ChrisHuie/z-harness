# Review instruments

Measurement scripts the PR review handoffs describe, kept so the published figures can be
regenerated instead of re-derived.

## Single-operand survivor enumeration

    python3 enumerate_survivors.py <module.py> [extra sibling files/dirs to copy]

Over every top-level function except `selftest` and the CLI `main`: each `if`/`elif` test is
replaced by `False`; each `and`/`or` operand is replaced by its identity; and each
non-constant `return` is replaced by `True` and by `False` (two mutants, with a site killed
only when both are killed). The pristine source must first emit one terminal green receipt.
A mutant is killed only by one terminal red receipt for the same suite and check count
with assertion-failure exit 1; timeout, crash, missing receipt, count drift, every other
exit, and setup failure are instrument errors.
Fixture symlinks and Python bytecode caches are rejected. Each completed private copy is
checked against its recorded digest before and after execution. The report binds those
starting and ending snapshots, not transient changes restored by the code under test or
arbitrary undeclared file reads. JSON is written to stdout, progress to stderr, and the
checkout is not modified.

## Differential judge fuzz

    python3 fuzz_judge_diff.py <oracle_guard.py> <candidate_guard.py> <seed> <count>

Compares Stop-guard verdicts between two guard sources in isolated workers over
grammar-generated endings. Instrument and guard bytes are captured once; each side gets a
separate private snapshot that is verified before and after execution, and the guard is
compiled directly without import bytecode. Runtime reads through the guard's `__file__`
resolve to that private snapshot; the original path remains only the compile filename used
in tracebacks. The deterministic prefix
covers every production and renders every supported delimiter before random cases begin.
JSON on stdout retains every case; stderr summarizes block-to-allow, allow-to-block, and
block-reason changes separately. A block-to-allow divergence exits 1 and an instrument
failure exits 2. The vocabulary bounds what a null result proves; extend it with the tokens
a change touches. Source symlinks are rejected. The report binds the two top-level guard
sources and their runtime `__file__` reads, not modules they import from the interpreter
environment.

Both figures move with the enumeration and the grammar. Publish the invocation with the
number.
