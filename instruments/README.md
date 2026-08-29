# Review instruments

Measurement scripts the PR review handoffs describe, kept so the published figures can be
regenerated instead of re-derived.

## Single-operand survivor enumeration

    python3 enumerate_survivors.py <module.py> [extra sibling files/dirs to copy]

Over every top-level function except `selftest`: each `if`/`elif` test replaced by `False`;
each `and`/`or` operand replaced by its identity; each non-constant `return` replaced by
`True` and by `False` (two mutants, a site killed only when both are killed). A mutant is
killed when the module's own `--selftest` exits non-zero or reports a failure — nothing
else runs against it, so an operand only other suites reach counts as surviving. Run from
a directory containing the module so relative fixtures resolve; results are written beside
the script as `<module>.results.json`.

## Differential judge fuzz

    python3 fuzz_judge_diff.py <oracle_guard.py> <candidate_guard.py> <seed> <count>

Compares Stop-guard verdicts between two guard sources over grammar-generated endings and
prints every divergence. The allow direction is the finding direction. The vocabulary
bounds what a null result proves; extend it with the tokens a change touches.

Both figures move with the enumeration and the grammar. Publish the invocation with the
number.
