#!/usr/bin/env python3
"""Regenerate contracts/goldens/mutation-receipt.json by breaking the guards on purpose.

`guard-decisions.json` pins what the guards DECIDE. Nothing pinned what their suites
CATCH, so the mutation battery behind this branch's review was run by hand and its counts
were retyped from the failure list. Three rows re-measured later were the subset under
attention rather than the suite total the table claimed -- `is_rev_path_git` forced true
was published as 3 and measures 50, and one dropped `MODS` letter was published as 12 and
ranges from 1 to 78 depending on the letter. A count nobody can regenerate is a sentence,
not evidence.

Two mutation classes, both recorded per run:

  set sweep   removes one element at a time from every guarded set the guards declare.
              The scan set is READ FROM THE SOURCE and never listed here, so a name added
              to a set is swept without anyone remembering to extend a list.
  site edit   applies a declared single-site substitution, anchored by content digest, so
              an anchor that no longer matches is an error rather than a silent skip.

The minimum of a set's sweep is the number that matters: it is how many checks stand
between one deleted element and a silent fail-open.

Run this deliberately, then review the diff. `tools/ci-gate.py` verifies that every element
the source declares has a recorded margin and that none falls below the floor.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECEIPT = ROOT / "contracts/goldens/mutation-receipt.json"
SUMMARY = ROOT / "contracts/goldens/mutation-summary.md"

GREP = "hooks/guards/git_grep_engine_guard.py"
ZSH = "hooks/guards/zsh_rev_modifier_guard.py"
BASH = "hooks/bash_command_guard.py"
GUARDS = (GREP, ZSH)

# Every element of every guarded set is swept except these, and the reason is recorded in
# the receipt so the scan set travels with the verdict rather than living only here.
SWEEP_EXCLUSIONS = {
    "FIXTURES": "the fixture table itself; removing a fixture measures the fixture",
    "_GIT_AUTHORITY_CACHE": "runtime cache, empty at import",
    "_EQUALS_LOOKUP_CACHE": "runtime cache, empty at import",
    "GREP_LONG_PATTERN_ARG": "empty at this head, nothing to remove",
}

# Single-site edits. Each anchor must appear exactly once; `digest` pins the bytes so a
# refactor that moves the code fails loudly here instead of quietly measuring nothing.
SITE_MUTATIONS = (
    ("budget wrap deleted", GREP,
     "    except CommandParseError as exc:\n"
     "        decisions.append((\"ask\", BUDGET_EXHAUSTED_REASON % exc))",
     "    except CommandParseError:\n"
     "        pass"),
    ("decision-budget checkpoint neutered", GREP,
     "def _check_decision_budget(deadline):\n"
     "    if deadline is not None and time.monotonic() >= deadline:\n"
     "        raise CommandParseError(\n"
     "            \"the guard's internal decision budget was exhausted while parsing\")",
     "def _check_decision_budget(deadline):\n"
     "    return None"),
    ("guarded-tail predicate rescans per word", GREP,
     "    later = [False] * (len(words) + 1)\n"
     "    for index in range(len(words) - 1, -1, -1):\n"
     "        later[index] = (later[index + 1]\n"
     "                        or os.path.basename(words[index]) in "
     "GIT_HAZARD_SUBCOMMANDS)\n"
     "    return later",
     "    return [any(os.path.basename(w) in GIT_HAZARD_SUBCOMMANDS\n"
     "                for w in words[index + 1:])\n"
     "            for index in range(-1, len(words))]"),
    ("equals PATH-lookup cache dropped", GREP,
     "        if key not in _EQUALS_LOOKUP_CACHE:\n"
     "            resolved = shutil.which(name, path=search_path)\n"
     "            _EQUALS_LOOKUP_CACHE[key] = (\n"
     "                os.path.realpath(resolved) if resolved else None)\n"
     "        resolved = _EQUALS_LOOKUP_CACHE[key]",
     "        resolved = shutil.which(name, path=search_path)\n"
     "        resolved = os.path.realpath(resolved) if resolved else None"),
    ("candidate_trusted forced true", GREP,
     "    if not authority.candidate_trusted or lookup_authority_uncertain:",
     "    if False:"),
    ("is_rev_path_git forced true", ZSH,
     "def is_rev_path_git(tokens, resolution=None):",
     "def is_rev_path_git(tokens, resolution=None):\n    return True"),
)


def declared_sets(relative, rejected=None):
    """name -> (kind, elements). Read from the module's own source, never declared.

    `rejected`, when a dict is passed, collects the constants this rule declined and why,
    so the scan set travels with the verdict instead of living only in this file.
    """
    source = (ROOT / relative).read_text(encoding="utf-8")
    found = {}
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not target.id.isupper():
            continue
        value = node.value
        if isinstance(value, ast.Call) and getattr(value.func, "id", "") in (
                "frozenset", "set"):
            value = value.args[0] if value.args else None
        if value is None:
            continue
        if isinstance(value, ast.Dict):
            elements = [k.value for k in value.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)]
            kind = "dict"
        elif isinstance(value, (ast.Set, ast.List, ast.Tuple)):
            elements = [e.value for e in value.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            kind = "set"
        elif (isinstance(value, ast.Constant) and isinstance(value.value, str)
              and len(value.value) > 2 and value.value.isalpha()):
            # A membership charset has DISTINCT characters by definition. An enum value
            # spelled as a word repeats one -- "guarded", "harmless", "unknown", "off".
            # Sweeping a word reports a margin of zero for every letter, because every
            # comparison uses the same constant, so the hole is false, silent, and pays for
            # a merged-suite probe each time. This rule separates the five word constants
            # in these guards from the two real charsets with no hand-maintained list.
            if len(set(value.value)) != len(value.value):
                if rejected is not None:
                    rejected[target.id] = ("a repeated character, so an enum value spelled "
                                           "as a word rather than a membership charset")
                continue
            elements = list(value.value)
            kind = "charset"
        else:
            continue
        if elements:
            found[target.id] = (kind, elements)
    return found


def without_element(source, name, kind, element):
    """The module's source with one element removed from `name`."""
    tree = ast.parse(source)
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == name):
            break
    else:
        raise LookupError(name)
    value, wrapper = node.value, None
    if isinstance(value, ast.Call):
        wrapper = value.func.id
        value = value.args[0]
    if kind == "charset":
        literal = repr(value.value.replace(element, "", 1))
    elif kind == "dict":
        kept = [(k, v) for k, v in zip(value.keys, value.values)
                if not (isinstance(k, ast.Constant) and k.value == element)]
        literal = "{" + ", ".join(f"{ast.unparse(k)}: {ast.unparse(v)}"
                                 for k, v in kept) + "}" if kept else "{}"
    else:
        kept = [e for e in value.elts
                if not (isinstance(e, ast.Constant) and e.value == element)]
        literal = "{" + ", ".join(ast.unparse(e) for e in kept) + "}" if kept else "set()"
    if wrapper:
        literal = f"{wrapper}({literal})"
    lines = source.splitlines(keepends=True)
    start = sum(len(line) for line in lines[:node.lineno - 1])
    end = sum(len(line) for line in lines[:node.end_lineno])
    return source[:start] + f"{name} = {literal}\n" + source[end:]


def suite_result(source, relative):
    """(checks, failures) from running one guard's own selftest on mutated source."""
    namespace: dict = {"__name__": "mutant", "__file__": str(ROOT / relative)}
    captured = io.StringIO()
    broke = None
    with contextlib.redirect_stdout(captured):
        try:
            exec(compile(source, str(ROOT / relative), "exec"), namespace)
            namespace["selftest"]()
        except SystemExit:
            pass
        except BaseException as exc:
            # Removing an element can make the module refuse to import at all -- a key some
            # other table indexes, a name a comprehension requires. That is a reddening
            # outcome, not a missing measurement, but it must not take the run down with it.
            broke = type(exc).__name__
    if broke is not None:
        return (-1, f"module failed to load: {broke}")
    match = re.search(r"checks=(\d+) failures=(\d+)", captured.getvalue())
    return (int(match.group(1)), int(match.group(2))) if match else (-1, -1)


def merged_failures(tree, relative, mutated):
    """The merged Bash suite's failures, which needs the mutation on disk.

    Only reached for an element the owning suite does not notice at all, so the cost is
    paid per hole rather than per element. The tree is built once and restored after each
    probe; copying it per element made a full run unusable.
    """
    pristine = (ROOT / relative).read_text(encoding="utf-8")
    (tree / relative).write_text(mutated, encoding="utf-8")
    try:
        done = subprocess.run([sys.executable, BASH, "--selftest"], cwd=str(tree),
                              capture_output=True, text=True)
        match = re.search(r"failures=(\d+)", done.stdout)
        return int(match.group(1)) if match else -1
    finally:
        (tree / relative).write_text(pristine, encoding="utf-8")


def sweep(tree, baseline, only=None):
    """Per-element margins, plus any mutation that moved the SELECTOR rather than a verdict.

    A mutation that changes the check COUNT did not break a behaviour, it broke the suite's
    ability to enumerate its own cases -- a different and worse failure, and one the earlier
    hand-run battery asserted was absent without recording it.
    """
    results, skipped, drift = {}, {}, []
    for relative in GUARDS:
        source = (ROOT / relative).read_text(encoding="utf-8")
        expected_checks = baseline[relative][0]
        rejected: dict = {}
        discovered = declared_sets(relative, rejected)
        skipped.update(rejected)
        for name, (kind, elements) in sorted(discovered.items()):
            if name in SWEEP_EXCLUSIONS:
                skipped[name] = SWEEP_EXCLUSIONS[name]
                continue
            if only and name not in only:
                continue
            margins = {}
            for element in elements:
                mutated = without_element(source, name, kind, element)
                checks, failures = suite_result(mutated, relative)
                entry = {"failures": failures}
                if checks != expected_checks:
                    entry["checks"] = checks
                    drift.append(f"{name}.{element}: {expected_checks} -> {checks}")
                if failures == 0:
                    entry["merged_failures"] = merged_failures(tree, relative, mutated)
                margins[element] = entry
                print(f"  {name}.{element!r} -> {failures}", flush=True)
            # An element whose removal stops the module importing is caught as hard as an
            # element can be caught, but it carries no failure count, so it is named rather
            # than folded into the range it would distort.
            broke = sorted(e for e, m in margins.items()
                           if not isinstance(m["failures"], int))
            counted = [m["failures"] for m in margins.values()
                       if isinstance(m["failures"], int)]
            entry = {
                "module": relative, "kind": kind, "elements": len(elements),
                "min": min(counted) if counted else None,
                "max": max(counted) if counted else None,
                "at_minimum": (sorted(e for e, m in margins.items()
                                      if m["failures"] == min(counted)) if counted else []),
                "margins": margins,
            }
            if broke:
                entry["removal_breaks_import"] = broke
            results[name] = entry
    return results, skipped, drift


# A site mutation may restore a cost the guard was changed to remove -- the quadratic tail
# predicate is one -- and a mutation that never returns would hang this tool. It is bounded
# the way the hook is bounded, and a mutation that exceeds the bound is RECORDED as such
# rather than waited on: exceeding the registered hook timeout is the fail-open this branch
# measured, so `timed out` is a reddening outcome, not a missing measurement.
SITE_TIMEOUT_SECONDS = 180


def sites(tree, baseline):
    """Site mutations run on disk under a wall-clock bound, as the hook itself does."""
    results, drift = {}, []
    for label, relative, anchor, replacement in SITE_MUTATIONS:
        source = (ROOT / relative).read_text(encoding="utf-8")
        if source.count(anchor) != 1:
            raise SystemExit(
                f"anchor for {label!r} matched {source.count(anchor)} times in "
                f"{relative}; a moved anchor measures nothing, so this is an error")
        entry: dict = {
            "module": relative,
            "anchor_sha256": hashlib.sha256(anchor.encode()).hexdigest()[:16],
        }
        (tree / relative).write_text(source.replace(anchor, replacement), encoding="utf-8")
        try:
            done = subprocess.run([sys.executable, relative, "--selftest"], cwd=str(tree),
                                  capture_output=True, text=True,
                                  timeout=SITE_TIMEOUT_SECONDS)
            match = re.search(r"checks=(\d+) failures=(\d+)", done.stdout)
            checks, failures = ((int(match.group(1)), int(match.group(2))) if match
                                else (-1, -1))
            entry["failures"] = failures
            if match and checks != baseline[relative][0]:
                entry["checks"] = checks
                drift.append(f"{label}: {baseline[relative][0]} -> {checks}")
        except subprocess.TimeoutExpired:
            failures = "timed out"
            entry["failures"] = failures
            entry["timeout_seconds"] = SITE_TIMEOUT_SECONDS
        finally:
            (tree / relative).write_text(source, encoding="utf-8")
        results[label] = entry
        print(f"  site {label!r} -> {failures}", flush=True)
    return results, drift


def write_summary(payload):
    """Emit the receipt as a markdown table for outbound text to INCLUDE, not restate.

    Every wrong number this mechanism exists to prevent was retyped into a comment by hand.
    A table generated from the same run that produced the receipt cannot disagree with it,
    so review text quotes this file instead of a memory of the failure list.
    """
    lines = ["<!-- generated by tools/write-mutation-receipt.py -- do not edit -->", ""]
    lines += ["| guarded set | module | elements | weakest | strongest | at the weakest |",
              "|---|---|---|---|---|---|"]
    for name, entry in sorted(payload["sets"].items()):
        at = ", ".join(f"`{e}`" for e in entry["at_minimum"][:6])
        if len(entry["at_minimum"]) > 6:
            at += f", and {len(entry['at_minimum']) - 6} more"
        lines.append(f"| `{name}` | {Path(entry['module']).name} | {entry['elements']} "
                     f"| {entry['min']} | {entry['max']} | {at} |")
    lines += ["", "| site mutation | module | checks that redden |", "|---|---|---|"]
    for label, entry in sorted(payload["sites"].items()):
        lines.append(f"| {label} | {Path(entry['module']).name} | {entry['failures']} |")
    measured = [s["min"] for s in payload["sets"].values() if s["min"] is not None]
    weakest = min(measured) if measured else 0
    total = sum(s["elements"] for s in payload["sets"].values())
    lines += ["", f"{len(payload['sets'])} guarded sets, {total} elements swept one at a "
                  f"time. The weakest element in any set is held by {weakest} "
                  f"check{'s' if weakest != 1 else ''}, which is the margin between "
                  "deleting it and a silent fail-open.", ""]
    if payload["sweep_exclusions"]:
        lines.append("Not swept, and why: "
                     + "; ".join(f"`{n}` ({r})"
                                 for n, r in sorted(payload["sweep_exclusions"].items()))
                     + ".")
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    sys.path.insert(0, str(ROOT / "hooks"))
    sys.path.insert(0, str(ROOT / "hooks" / "guards"))
    baseline = {relative: suite_result((ROOT / relative).read_text(encoding="utf-8"),
                                       relative)
                for relative in GUARDS}
    for relative, (checks, failures) in baseline.items():
        if failures:
            print(f"{relative} is not green at baseline ({failures} failures); "
                  "refusing to write a receipt", file=sys.stderr)
            return 2
    only = set(sys.argv[1:]) or None
    with tempfile.TemporaryDirectory(prefix="mutation-") as scratch:
        tree = Path(scratch) / "tree"
        shutil.copytree(ROOT, tree, ignore=shutil.ignore_patterns(
            "__pycache__", ".git", "node_modules"))
        swept, skipped, sweep_drift = sweep(tree, baseline, only)
        site_results, site_drift = sites(tree, baseline)
    if not swept:
        print("no guarded sets discovered; refusing to write an empty receipt",
              file=sys.stderr)
        return 2
    if only:
        print("partial run; receipt not written", file=sys.stderr)
        return 0
    survivors = sorted(label for label, r in site_results.items() if r["failures"] == 0)
    payload = {
        "note": "what the guards' suites CATCH, measured by breaking them",
        # Every margin here describes the source it was measured against. Set membership
        # alone cannot detect a change that only moves margins -- adding a fixture leaves
        # the declared sets identical while every number below shifts -- so the gate needs
        # the bytes to tell a current receipt from one describing an older guard.
        "measured_against": {
            relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            for relative in (GREP, ZSH, BASH)
        },
        "baseline": {relative: {"checks": c, "failures": f}
                     for relative, (c, f) in baseline.items()},
        "sweep_exclusions": skipped,
        "selector_drift": sweep_drift + site_drift,
        "site_survivors": survivors,
        "sets": swept,
        "sites": site_results,
    }
    RECEIPT.write_text(json.dumps(payload, indent=1, sort_keys=False) + "\n",
                       encoding="utf-8")
    write_summary(payload)
    total = sum(s["elements"] for s in swept.values())
    measured = [s["min"] for s in swept.values() if s["min"] is not None]
    floor = min(measured) if measured else 0
    print(f"wrote {RECEIPT.relative_to(ROOT)} and {SUMMARY.relative_to(ROOT)}: "
          f"{len(swept)} sets / {total} elements swept, {len(site_results)} site edits, "
          f"weakest element margin {floor}, {len(survivors)} site survivors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
