#!/usr/bin/env python3
"""Run deterministic guard mutations and build the tracked coverage receipt.

Each mutation runs the real suite from a private on-disk tree. Shards write raw
fragments; aggregation reconstructs the exact plan, rejects missing or overlapping IDs,
and reduces platform-specific counts to the stable fact the receipt claims: whether the
shipped gate catches that mutation. Receipt changes require an explicit acceptance flag.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
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
GUARDS = (GREP, ZSH, BASH)
SCHEMA_VERSION = 2
GENERATOR = "tools/write-mutation-receipt.py"
NOTE = "which guard mutations the shipped suites catch"
OUTCOMES = {"caught", "survived"}
RECEIPT_KEYS = (
    "schema_version", "generated_by", "note", "generator_sha256",
    "source_digests", "plan_sha256", "baseline", "sweep_exclusions",
    "results", "survivors", "caught", "total",
)
FRAGMENT_KEYS = (
    "schema_version", "kind", "head_sha", "generator_sha256", "source_digests",
    "plan_sha256", "shard", "baseline", "results",
)


def qname(module: str, name: str) -> str:
    return f"{module}::{name}"


SWEEP_EXCLUSIONS = {
    qname(GREP, "FIXTURES"): "fixture corpus; removing a fixture measures the grader",
    qname(GREP, "GREP_LONG_PATTERN_ARG"):
        "empty grammar collection has no element mutation; absence is fixture-pinned",
    qname(GREP, "_GIT_AUTHORITY_CACHE"):
        "runtime memoization map, not a guarded membership collection",
    qname(GREP, "_EQUALS_LOOKUP_CACHE"):
        "runtime memoization map, not a guarded membership collection",
    qname(ZSH, "FIXTURES"): "fixture corpus; removing a fixture measures the grader",
}

CHARSET_COLLECTIONS = {
    qname(GREP, "PCRE_ESCAPE_LETTERS"),
    qname(GREP, "GREP_SHORT_VALUE"),
    qname(GREP, "GREP_SHORT_NOARG"),
    qname(ZSH, "MODS"),
    qname(ZSH, "MOD_PREFIXES"),
    qname(ZSH, "MOD_UNMODELLED"),
}


# ``timeout`` is an allowed kill only for the edit that restores an unbounded traversal.
SITE_MUTATIONS = (
    {
        "label": "budget wrap deleted", "module": GREP,
        "anchor": (
            "    except CommandParseError as exc:\n"
            "        decisions.append((\"ask\", BUDGET_EXHAUSTED_REASON % exc))"),
        "replacement": "    except CommandParseError:\n        pass",
        "allowed_statuses": (),
    },
    {
        "label": "decision-budget checkpoint neutered", "module": GREP,
        "anchor": (
            "def _check_decision_budget(deadline):\n"
            "    if deadline is not None and time.monotonic() >= deadline:\n"
            "        raise CommandParseError(\n"
            "            \"the guard's internal decision budget was exhausted while parsing\")"),
        "replacement": "def _check_decision_budget(deadline):\n    return None",
        "allowed_statuses": (),
    },
    {
        "label": "guarded-tail predicate rescans per word", "module": GREP,
        "anchor": (
            "    later = [False] * (len(words) + 1)\n"
            "    for index in range(len(words) - 1, -1, -1):\n"
            "        later[index] = (later[index + 1]\n"
            "                        or os.path.basename(words[index]) in GIT_HAZARD_SUBCOMMANDS)\n"
            "    return later"),
        "replacement": (
            "    return [any(os.path.basename(w) in GIT_HAZARD_SUBCOMMANDS\n"
            "                for w in words[index + 1:])\n"
            "            for index in range(-1, len(words))]"),
        "allowed_statuses": ("timeout",),
    },
    {
        "label": "candidate authority forced trusted", "module": GREP,
        "anchor": "    if not authority.candidate_trusted or lookup_authority_uncertain:",
        "replacement": "    if False:", "allowed_statuses": (),
    },
    {
        "label": "dynamic source adoption removed", "module": GREP,
        "anchor": (
            "    for finding in dynamic_source_findings(\n"
            "            scan_command, commands, _deadline, _shell, equals_states):"),
        "replacement": "    for finding in ():", "allowed_statuses": (),
    },
    {
        "label": "process substitution loses typed operand", "module": GREP,
        "anchor": "            append_tok(marker + \"__PROCESS__)\")",
        "replacement": "            append_tok(\"<\")", "allowed_statuses": (),
    },
    {
        "label": "source exec wrapper omitted", "module": GREP,
        "anchor": "    while executable in {\"builtin\", \"command\", \"exec\"}:",
        "replacement": "    while executable in {\"builtin\", \"command\"}:",
        "allowed_statuses": (),
    },
    {
        "label": "source command wrapper omitted", "module": GREP,
        "anchor": "    while executable in {\"builtin\", \"command\", \"exec\"}:",
        "replacement": "    while executable in {\"builtin\", \"exec\"}:",
        "allowed_statuses": (),
    },
    {
        "label": "nested source shell identity dropped", "module": GREP,
        "anchor": "        source_operand = _source_builtin_operand(tokens, current_shell)",
        "replacement": "        source_operand = _source_builtin_operand(tokens)",
        "allowed_statuses": (),
    },
    {
        "label": "attached exec argv-zero grammar dropped", "module": GREP,
        "anchor": "                if index + 1 < len(flags):\n                    index = len(flags)",
        "replacement": "                if False:\n                    index = len(flags)",
        "allowed_statuses": (),
    },
    {
        "label": "exec single-dash terminator dropped", "module": GREP,
        "anchor": "        if option in {\"--\", \"-\"}:\n            return None",
        "replacement": (
            "        if option == \"--\":\n"
            "            return None\n"
            "        if option == \"-\":\n"
            "            return \"unmodelled exec option '-'\""),
        "allowed_statuses": (),
    },
    {
        "label": "dynamic source command identity dropped", "module": GREP,
        "anchor": "    if source_has_dynamic_command_word(command, deadline):\n        findings.append(DynamicSourceFinding(",
        "replacement": "    if False:\n        findings.append(DynamicSourceFinding(",
        "allowed_statuses": (),
    },
    {
        "label": "source alias invocation dropped", "module": GREP,
        "anchor": (
            "    findings.extend(_literal_source_alias_findings(\n"
            "        command, parsed, current_shell, deadline))"),
        "replacement": "    findings.extend(())",
        "allowed_statuses": (),
    },
    {
        "label": "source alias wrapper resolution dropped", "module": GREP,
        "anchor": (
            "            resolved = _source_command_invocation(\n"
            "                tokens, current_shell)\n"
            "            if resolved is None:\n"
            "                continue\n"
            "            executable, items, _noglob = resolved\n"
            "            if _apply_literal_alias_mutation(executable, items, aliases):"),
        "replacement": (
            "            resolved = (\n"
            "                (tokens[0][0], list(tokens[1:]), False)\n"
            "                if tokens else None)\n"
            "            if resolved is None:\n"
            "                continue\n"
            "            executable, items, _noglob = resolved\n"
            "            if _apply_literal_alias_mutation(executable, items, aliases):"),
        "allowed_statuses": (),
    },
    {
        "label": "source alias body traversal dropped", "module": GREP,
        "anchor": (
            "    def inspect(commands, depth, alias_stack=()):\n"
            "        if depth > MAX_SOURCE_DEPTH:\n"
            "            findings.append(DynamicSourceFinding(\n"
            "                \"<alias eval>\", \"literal alias evaluation exceeds the source depth bound\"))\n"
            "            return\n"
            "        for tokens in commands:"),
        "replacement": (
            "    def inspect(commands, depth, alias_stack=()):\n"
            "        if depth > MAX_SOURCE_DEPTH:\n"
            "            findings.append(DynamicSourceFinding(\n"
            "                \"<alias eval>\", \"literal alias evaluation exceeds the source depth bound\"))\n"
            "            return\n"
            "        for tokens in commands[-1:]:"),
        "allowed_statuses": (),
    },
    {
        "label": "ordinary shell alias Git classification dropped", "module": GREP,
        "anchor": (
            "            if alias_stack:\n"
            "                alias_resolution = unwrap_command_prefix("),
        "replacement": (
            "            if False:\n"
            "                alias_resolution = unwrap_command_prefix("),
        "allowed_statuses": (),
    },
    {
        "label": "executed alias Git traversal dropped", "module": GREP,
        "anchor": "            if body_alias_maps:\n",
        "replacement": "            if False:\n",
        "allowed_statuses": (),
    },
    {
        "label": "nonordinary alias mode tracking dropped", "module": GREP,
        "anchor": (
            "        if \"g\" in option[1:]:\n"
            "            modes.add(\"global\")\n"
            "        if \"s\" in option[1:]:\n"
            "            modes.add(\"suffix\")"),
        "replacement": (
            "        if False:\n"
            "            modes.add(\"global\")\n"
            "        if False:\n"
            "            modes.add(\"suffix\")"),
        "allowed_statuses": (),
    },
    {
        "label": "nonordinary alias use detection dropped", "module": GREP,
        "anchor": (
            "            special_alias = _used_nonordinary_alias(\n"
            "                tokens, (aliases, *executed_alias_maps))\n"
            "            if special_alias is not None:"),
        "replacement": (
            "            special_alias = None\n"
            "            if special_alias is not None:"),
        "allowed_statuses": (),
    },
    {
        "label": "declared helper function alias traversal dropped", "module": GREP,
        "anchor": (
            "            if declarations is not None and executable in declarations:\n"
            "                if executable in active_stack or len(active_stack) >= MAX_SOURCE_DEPTH:"),
        "replacement": (
            "            if False:\n"
            "                if executable in active_stack or len(active_stack) >= MAX_SOURCE_DEPTH:"),
        "allowed_statuses": (),
    },
    {
        "label": "invoked alias body state transition dropped", "module": GREP,
        "anchor": (
            "            inspect(nested, depth + 1, "
            "alias_stack + (executable,))"),
        "replacement": "            pass",
        "allowed_statuses": (),
    },
    {
        "label": "source alias embedded operand classification dropped", "module": GREP,
        "anchor": (
            "                    reason = _dynamic_source_operand_reason(\n"
            "                        source_items[0], _noglob, current_shell)\n"
            "                    if reason is not None:"),
        "replacement": (
            "                    reason = None\n"
            "                    if reason is not None:"),
        "allowed_statuses": (),
    },
    {
        "label": "source alias dynamic command detection dropped", "module": GREP,
        "anchor": (
            "    if source_has_dynamic_command_word(body, deadline):\n"
            "        return \"unresolved\""),
        "replacement": (
            "    if False:\n"
            "        return \"unresolved\""),
        "allowed_statuses": (),
    },
    {
        "label": "source alias state lookup bypass dropped", "module": GREP,
        "anchor": (
            "            if (executable not in aliases\n"
            "                    or _literal_alias_invocation_bypassed(command_tokens)):\n"
            "                continue"),
        "replacement": (
            "            if executable not in aliases:\n"
            "                continue"),
        "allowed_statuses": (),
    },
    {
        "label": "source alias invocation lookup bypass dropped", "module": GREP,
        "anchor": (
            "            if executable not in aliases or bypassed:\n"
            "                continue"),
        "replacement": (
            "            if executable not in aliases:\n"
            "                continue"),
        "allowed_statuses": (),
    },
    {
        "label": "same-shell alias mutation wrapper resolution dropped", "module": GREP,
        "anchor": (
            "            resolved = _source_command_invocation(\n"
            "                tokens, current_shell)\n"
            "            if resolved is None:\n"
            "                continue\n"
            "            executable, items, _noglob = resolved\n"
            "            _apply_literal_alias_mutation(executable, items, aliases)"),
        "replacement": (
            "            resolved = (\n"
            "                (tokens[0][0], list(tokens[1:]), False)\n"
            "                if tokens else None)\n"
            "            if resolved is None:\n"
            "                continue\n"
            "            executable, items, _noglob = resolved\n"
            "            _apply_literal_alias_mutation(executable, items, aliases)"),
        "allowed_statuses": (),
    },
    {
        "label": "called function alias state dropped", "module": GREP,
        "anchor": "    for context in call_contexts:\n",
        "replacement": "    for context in ():\n",
        "allowed_statuses": (),
    },
    {
        "label": "TRAPDEBUG function alias state dropped", "module": GREP,
        "anchor": (
            "    extra_sources = [record.body for record in records\n"
            "                     if record.name == \"TRAPDEBUG\"]"),
        "replacement": "    extra_sources = []",
        "allowed_statuses": (),
    },
    {
        "label": "DEBUG trap alias state dropped", "module": GREP,
        "anchor": "    extra_sources.extend(_debug_trap_action_sources(parsed, current_shell))",
        "replacement": "    extra_sources.extend(())",
        "allowed_statuses": (),
    },
    {
        "label": "repeat zero execution boundary dropped", "module": GREP,
        "anchor": "            if count == \"0\":\n                return None",
        "replacement": "            if False:\n                return None",
        "allowed_statuses": (),
    },
    {
        "label": "trap action traversal dropped", "module": GREP,
        "anchor": "    if shell == \"trap\":\n        args = resolution.items[1:]",
        "replacement": "    if False:\n        args = resolution.items[1:]",
        "allowed_statuses": (),
    },
    {
        "label": "builtin trap wrapper adoption dropped", "module": GREP,
        "anchor": (
            "            if items[0][0] in "
            "{\"builtin\", \"command\", \"exec\", \"trap\"}:\n"
            "                continue"),
        "replacement": (
            "            if items[0][0] in "
            "{\"builtin\", \"command\", \"exec\"}:\n"
            "                continue"),
        "allowed_statuses": (),
    },
    {
        "label": "zsh trap function source traversal dropped", "module": GREP,
        "anchor": "    if _shell == \"zsh\":\n        for body in zsh_trap_function_sources(command, _deadline):",
        "replacement": "    if False:\n        for body in zsh_trap_function_sources(command, _deadline):",
        "allowed_statuses": (),
    },
    {
        "label": "git config count cap dropped", "module": GREP,
        "anchor": "        if count > MAX_TOKENS:\n            raise CommandParseError(",
        "replacement": "        if False:\n            raise CommandParseError(",
        "allowed_statuses": (),
    },
    {
        "label": "git config loop budget dropped", "module": GREP,
        "anchor": "        for index in range(count):\n            _check_decision_budget(deadline)",
        "replacement": "        for index in range(count):\n            pass",
        "allowed_statuses": (),
    },
    {
        "label": "git hazard union adoption dropped", "module": GREP,
        "anchor": "} | REV_PATH_SUBCOMMANDS\n\n\ndef _consume_exec_options",
        "replacement": "}\n\n\ndef _consume_exec_options",
        "allowed_statuses": (),
    },
    {
        "label": "native command checked after alias", "module": GREP,
        "anchor": "        if authority_error is None:\n            return current, argv, None, derived_configs",
        "replacement": "        if False:\n            return current, argv, None, derived_configs",
        "allowed_statuses": (),
    },
    {
        "label": "shell alias forwarding dropped", "module": GREP,
        "anchor": "    if invocation.subcommand is None and forwarded_argv:",
        "replacement": "    if False:", "allowed_statuses": (),
    },
    {
        "label": "shell alias cycle context reset", "module": GREP,
        "anchor": "            resolution.items, resolution, deadline, aliases, seen, depth)",
        "replacement": "            resolution.items, resolution, deadline, aliases, (), 0)",
        "allowed_statuses": ("invalid-receipt",),
    },
    {
        "label": "zsh shared resolver bypassed", "module": ZSH,
        "anchor": (
            "        invocation = resolve_effective_git_invocation(\n"
            "            tokens, resolution, deadline)"),
        "replacement": "        invocation = None", "allowed_statuses": (),
    },
    {
        "label": "zsh unmodelled modifier uncertainty dropped", "module": ZSH,
        "anchor": "            if unmodelled_hits:\n                decisions.append((",
        "replacement": "            if False:\n                decisions.append((",
        "allowed_statuses": (),
    },
    {
        "label": "zsh unmodelled modifier prefix grammar dropped", "module": ZSH,
        "anchor": (
            "    r\"|(?:[A-Za-z_][A-Za-z0-9_]*(?:\\[[^\\]]*\\])?|[0-9]+|[#?*@!$-]))\"\n"
            "    r\":[\" + MOD_PREFIXES + r\"]*W\")"),
        "replacement": (
            "    r\"|(?:[A-Za-z_][A-Za-z0-9_]*(?:\\[[^\\]]*\\])?|[0-9]+|[#?*@!$-])):W\")"),
        "allowed_statuses": (),
    },
    {
        "label": "zsh trap function traversal dropped", "module": ZSH,
        "anchor": "    if _shell == \"zsh\":\n        for body in zsh_trap_function_sources(command, _deadline):",
        "replacement": "    if False:\n        for body in zsh_trap_function_sources(command, _deadline):",
        "allowed_statuses": (),
    },
)


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_digests(root: Path = ROOT) -> dict[str, str]:
    return {relative: file_sha256(root / relative) for relative in GUARDS}


def _string_collection(value, assignments, seen=()):
    """Statically resolve a closed string collection without importing production."""
    if isinstance(value, ast.Name):
        if value.id in seen or value.id not in assignments:
            return None
        return _string_collection(
            assignments[value.id], assignments, seen + (value.id,))
    if (isinstance(value, ast.BinOp) and isinstance(value.op, ast.BitOr)):
        left = _string_collection(value.left, assignments, seen)
        right = _string_collection(value.right, assignments, seen)
        if left is None or right is None:
            return None
        return tuple(dict.fromkeys(left + right))
    if isinstance(value, ast.Call) and getattr(value.func, "id", "") in {
            "frozenset", "set"}:
        value = value.args[0] if len(value.args) == 1 else None
    if isinstance(value, ast.Dict):
        if all(isinstance(key, ast.Constant) and isinstance(key.value, str)
               for key in value.keys):
            return tuple(key.value for key in value.keys)
        return None
    if isinstance(value, (ast.Set, ast.List, ast.Tuple)):
        if all(isinstance(item, ast.Constant) and isinstance(item.value, str)
               for item in value.elts):
            return tuple(item.value for item in value.elts)
        return None
    return None


def declared_sets(relative: str) -> tuple[dict, dict]:
    """Return literal guarded collections plus structurally rejected constants."""
    source = (ROOT / relative).read_text(encoding="utf-8")
    found, rejected = {}, {}
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: node.value for node in tree.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not target.id.isupper():
            continue
        if target.id == "FIXTURES":
            found[target.id] = ("fixture", ())
            continue
        value = node.value
        identity = qname(relative, target.id)
        if target.id == "GUARDS" and isinstance(value, (ast.List, ast.Tuple)):
            elements = tuple(
                item.elts[0].value for item in value.elts
                if isinstance(item, ast.Tuple) and len(item.elts) == 2
                and isinstance(item.elts[0], ast.Constant)
                and isinstance(item.elts[0].value, str))
            if len(elements) != len(value.elts):
                rejected[identity] = "dispatch list is not entirely (label, predicate) tuples"
                continue
            found[target.id] = ("dispatch", elements)
            continue
        if identity in CHARSET_COLLECTIONS:
            if isinstance(value, ast.Call) and getattr(value.func, "id", "") in {
                    "frozenset", "set"}:
                value = value.args[0] if len(value.args) == 1 else None
            if (not isinstance(value, ast.Constant)
                    or not isinstance(value.value, str)):
                rejected[identity] = "declared charset is not one literal string"
                continue
            if len(set(value.value)) != len(value.value):
                rejected[qname(relative, target.id)] = (
                    "repeated characters identify an enum word, not a membership charset")
                continue
            found[target.id] = ("charset", tuple(value.value))
            continue
        elements = _string_collection(value, assignments)
        if elements is None:
            if (isinstance(value, ast.Constant) and isinstance(value.value, str)
                    and len(value.value) > 2 and value.value.isalpha()
                    and len(set(value.value)) != len(value.value)):
                rejected[identity] = (
                    "repeated characters identify an enum word, not a membership charset")
            continue
        if isinstance(value, ast.Dict):
            kind = "dict"
        elif isinstance(value, ast.BinOp):
            kind = "computed-set"
        else:
            kind = "set"
        found[target.id] = (kind, tuple(elements))
    return found, rejected


def without_element(source: str, name: str, kind: str, element: str) -> str:
    tree = ast.parse(source)
    target_node = None
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == name):
            target_node = node
            break
    if target_node is None:
        raise LookupError(name)
    value, wrapper = target_node.value, None
    if isinstance(value, ast.Call):
        wrapper = value.func.id
        value = value.args[0]
    if kind == "charset":
        literal = repr(value.value.replace(element, "", 1))
    elif kind == "dispatch":
        kept = [item for item in value.elts
                if not (isinstance(item, ast.Tuple) and item.elts
                        and isinstance(item.elts[0], ast.Constant)
                        and item.elts[0].value == element)]
        literal = "[" + ", ".join(ast.unparse(item) for item in kept) + "]"
    elif kind == "computed-set":
        assignments = {
            node.targets[0].id: node.value for node in tree.body
            if isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        }
        elements = _string_collection(value, assignments)
        if elements is None:
            raise ValueError(f"cannot resolve computed collection {name}")
        kept = [item for item in elements if item != element]
        literal = ("{" + ", ".join(repr(item) for item in kept) + "}"
                   if kept else "set()")
    elif kind == "dict":
        kept = [(key, item) for key, item in zip(value.keys, value.values)
                if not (isinstance(key, ast.Constant) and key.value == element)]
        literal = ("{" + ", ".join(
            f"{ast.unparse(key)}: {ast.unparse(item)}" for key, item in kept) + "}"
            if kept else "{}")
    else:
        kept = [item for item in value.elts
                if not (isinstance(item, ast.Constant) and item.value == element)]
        literal = ("{" + ", ".join(ast.unparse(item) for item in kept) + "}"
                   if kept else "set()")
    if wrapper:
        literal = f"{wrapper}({literal})"
    lines = source.splitlines(keepends=True)
    start = sum(len(line) for line in lines[:target_node.lineno - 1])
    end = sum(len(line) for line in lines[:target_node.end_lineno])
    return source[:start] + f"{name} = {literal}\n" + source[end:]


def mutation_plan() -> tuple[list[dict], dict[str, str]]:
    mutations, rejected = [], {}
    discovered_names = set()
    for module in GUARDS:
        declared, module_rejected = declared_sets(module)
        rejected.update(module_rejected)
        for name, (kind, elements) in sorted(declared.items()):
            identity = qname(module, name)
            discovered_names.add(identity)
            if identity in SWEEP_EXCLUSIONS:
                continue
            for element in elements:
                descriptor = {
                    "version": 1, "kind": "set-element", "module": module,
                    "name": name, "collection_kind": kind, "element": element,
                    "allowed_statuses": ["invalid-receipt"],
                }
                descriptor["id"] = digest(descriptor)
                mutations.append(descriptor)
    stale_exclusions = sorted(set(SWEEP_EXCLUSIONS) - discovered_names)
    if stale_exclusions:
        raise ValueError(f"stale sweep exclusions: {stale_exclusions}")
    for site in SITE_MUTATIONS:
        source = (ROOT / site["module"]).read_text(encoding="utf-8")
        count = source.count(site["anchor"])
        if count != 1:
            raise ValueError(
                f"site anchor {site['label']!r} matched {count} times in {site['module']}")
        descriptor = {
            "version": 1, "kind": "site", "module": site["module"],
            "label": site["label"],
            "anchor_sha256": hashlib.sha256(site["anchor"].encode()).hexdigest(),
            "replacement_sha256": hashlib.sha256(
                site["replacement"].encode()).hexdigest(),
            "allowed_statuses": list(site["allowed_statuses"]),
        }
        descriptor["id"] = digest(descriptor)
        mutations.append(descriptor)
    mutations.sort(key=lambda item: item["id"])
    ids = [item["id"] for item in mutations]
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError("mutation plan has duplicate IDs or is empty")
    exclusions = dict(SWEEP_EXCLUSIONS)
    exclusions.update(rejected)
    return mutations, dict(sorted(exclusions.items()))


RECEIPT_RE = re.compile(
    r"^SELFTEST-SUMMARY suite=(?P<suite>[a-z0-9_-]+) "
    r"checks=(?P<checks>\d+) failures=(?P<failures>\d+)$")


def suite_name(relative: str) -> str:
    return Path(relative).stem


def run_suite(tree: Path, relative: str, timeout: int = 240) -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        done = subprocess.run(
            [sys.executable, "-B", relative, "--selftest"], cwd=tree,
            capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "timeout_seconds": timeout}
    matches = [match for line in done.stdout.splitlines()
               if (match := RECEIPT_RE.fullmatch(line)) is not None]
    final = done.stdout.rstrip().splitlines()[-1] if done.stdout.rstrip() else ""
    expected_suite = suite_name(relative)
    if (len(matches) != 1 or matches[0].group("suite") != expected_suite
            or final != matches[0].group(0)):
        return {
            "status": "invalid-receipt", "returncode": done.returncode,
            "receipt_count": len(matches), "stderr_tail": done.stderr[-1000:],
        }
    return {
        "status": "completed", "returncode": done.returncode,
        "checks": int(matches[0].group("checks")),
        "failures": int(matches[0].group("failures")),
    }


def baseline_results(tree: Path) -> dict[str, dict]:
    if shutil.which("zsh") is None:
        raise ValueError(
            "zsh is required for mutation baselines; skipped runtime probes are not proof")
    baseline = {relative: run_suite(tree, relative) for relative in GUARDS}
    bad = {relative: result for relative, result in baseline.items()
           if result.get("status") != "completed"
           or result.get("returncode") != 0 or result.get("failures") != 0}
    if bad:
        raise ValueError(f"baseline suites are not green: {bad}")
    return baseline


def result_kill(result: dict, baseline: dict, allowed_statuses=()) -> tuple[bool, str]:
    status = result.get("status")
    if status != "completed":
        if status in allowed_statuses:
            return True, status
        raise ValueError(f"mutation produced an invalid measurement: {result}")
    if result.get("returncode") != 0 or result.get("failures", 0) > 0:
        return True, "suite-failure"
    if result.get("checks") != baseline.get("checks"):
        return True, "exact-check-count"
    return False, "survived"


def apply_mutation(tree: Path, descriptor: dict) -> tuple[Path, str]:
    target = tree / descriptor["module"]
    source = target.read_text(encoding="utf-8")
    if descriptor["kind"] == "set-element":
        mutated = without_element(
            source, descriptor["name"], descriptor["collection_kind"],
            descriptor["element"])
    else:
        site = next(item for item in SITE_MUTATIONS
                    if item["label"] == descriptor["label"]
                    and item["module"] == descriptor["module"])
        if source.count(site["anchor"]) != 1:
            raise ValueError(f"site anchor moved for {descriptor['label']!r}")
        mutated = source.replace(site["anchor"], site["replacement"])
    target.write_text(mutated, encoding="utf-8")
    return target, source


def execute_mutation(tree: Path, descriptor: dict, baseline: dict) -> dict:
    target, pristine = apply_mutation(tree, descriptor)
    try:
        owner = run_suite(tree, descriptor["module"])
        killed, reason = result_kill(
            owner, baseline[descriptor["module"]], descriptor.get("allowed_statuses", ()))
        merged = None
        if not killed and descriptor["module"] != BASH:
            merged = run_suite(tree, BASH)
            killed, reason = result_kill(
                merged, baseline[BASH], descriptor.get("allowed_statuses", ()))
        return {
            "owner": owner, "merged": merged,
            "outcome": "caught" if killed else "survived", "reason": reason,
        }
    finally:
        target.write_text(pristine, encoding="utf-8")


def git_head() -> str:
    done = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
        text=True, check=True)
    return done.stdout.strip()


def fragment_payload(index: int, count: int, expected_head: str | None) -> dict:
    if count < 1 or index < 0 or index >= count:
        raise ValueError(f"invalid shard {index}/{count}")
    head = git_head()
    if expected_head is not None and head != expected_head:
        raise ValueError(f"checkout HEAD {head} != expected exact head {expected_head}")
    plan, _exclusions = mutation_plan()
    plan_hash = digest(plan)
    generator_hash = file_sha256(ROOT / GENERATOR)
    guard_hashes = source_digests()
    with tempfile.TemporaryDirectory(prefix="z-harness-mutations-") as raw:
        tree = Path(raw) / "tree"
        shutil.copytree(ROOT, tree, ignore=shutil.ignore_patterns(
            ".git", ".worktrees", "__pycache__", "node_modules"))
        if (file_sha256(tree / GENERATOR) != generator_hash
                or source_digests(tree) != guard_hashes):
            raise ValueError("private mutation tree differs from the captured sources")
        baseline = baseline_results(tree)
        assigned = [item for position, item in enumerate(plan)
                    if position % count == index]
        results = {}
        for position, descriptor in enumerate(assigned, 1):
            result = execute_mutation(tree, descriptor, baseline)
            results[descriptor["id"]] = result
            print(
                f"[{position}/{len(assigned)}] {descriptor['id'][:12]} "
                f"{descriptor['kind']} {result['outcome']} ({result['reason']})",
                flush=True)
    if (file_sha256(ROOT / GENERATOR) != generator_hash
            or source_digests() != guard_hashes):
        raise ValueError("mutation sources changed while the shard was running")
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "mutation-fragment",
        "head_sha": head,
        "generator_sha256": generator_hash,
        "source_digests": guard_hashes,
        "plan_sha256": plan_hash,
        "shard": {"index": index, "count": count},
        "baseline": baseline,
        "results": results,
    }


def validate_fragment(fragment: dict) -> str:
    if not isinstance(fragment, dict) or set(fragment) != set(FRAGMENT_KEYS):
        return "fragment fields are not exact"
    if fragment.get("schema_version") != SCHEMA_VERSION:
        return "fragment schema version differs"
    if fragment.get("kind") != "mutation-fragment":
        return "fragment kind differs"
    if not isinstance(fragment.get("results"), dict):
        return "fragment results are not an object"
    shard = fragment.get("shard")
    if not isinstance(shard, dict) or set(shard) != {"index", "count"}:
        return "fragment shard is malformed"
    index, count = shard.get("index"), shard.get("count")
    if (not isinstance(index, int) or isinstance(index, bool)
            or not isinstance(count, int) or isinstance(count, bool)
            or count < 1 or index < 0 or index >= count):
        return "fragment shard coordinates are outside their domain"
    baseline = fragment.get("baseline")
    if not isinstance(baseline, dict) or set(baseline) != set(GUARDS):
        return "fragment baseline inventory differs"
    for relative, result in baseline.items():
        problem = suite_result_error(result, baseline=True)
        if problem:
            return f"fragment baseline {relative}: {problem}"
    return ""


def suite_result_error(result: object, *, baseline: bool = False) -> str:
    if not isinstance(result, dict) or not isinstance(result.get("status"), str):
        return "suite result is not a typed object"
    status = result["status"]
    expected = {
        "completed": {"status", "returncode", "checks", "failures"},
        "timeout": {"status", "timeout_seconds"},
        "invalid-receipt": {
            "status", "returncode", "receipt_count", "stderr_tail"},
    }.get(status)
    if expected is None or set(result) != expected:
        return f"suite result fields differ for status {status!r}"
    if status == "completed":
        integers = (result["returncode"], result["checks"], result["failures"])
        if any(not isinstance(value, int) or isinstance(value, bool)
               for value in integers):
            return "completed suite result counters are not integers"
        if result["checks"] < 1 or result["failures"] < 0:
            return "completed suite result counters are outside their domain"
        if baseline and (result["returncode"] != 0 or result["failures"] != 0):
            return "baseline suite result is not green"
    elif status == "timeout":
        if (not isinstance(result["timeout_seconds"], int)
                or isinstance(result["timeout_seconds"], bool)
                or result["timeout_seconds"] < 1):
            return "timeout duration is invalid"
    else:
        if (not isinstance(result["returncode"], int)
                or isinstance(result["returncode"], bool)
                or not isinstance(result["receipt_count"], int)
                or isinstance(result["receipt_count"], bool)
                or result["receipt_count"] < 0
                or not isinstance(result["stderr_tail"], str)):
            return "invalid-receipt evidence is malformed"
    return ""


def recompute_raw_result(raw: object, descriptor: dict, baseline: dict) -> tuple[str, str]:
    expected = {"owner", "merged", "outcome", "reason"}
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ValueError(f"raw result fields differ for {descriptor['id']}")
    problem = suite_result_error(raw["owner"])
    if problem:
        raise ValueError(f"raw owner result {descriptor['id']}: {problem}")
    killed, reason = result_kill(
        raw["owner"], baseline[descriptor["module"]],
        descriptor.get("allowed_statuses", ()))
    if killed or descriptor["module"] == BASH:
        if raw["merged"] is not None:
            raise ValueError(
                f"raw merged result is unexpected for {descriptor['id']}")
    else:
        problem = suite_result_error(raw["merged"])
        if problem:
            raise ValueError(f"raw merged result {descriptor['id']}: {problem}")
        killed, reason = result_kill(
            raw["merged"], baseline[BASH], descriptor.get("allowed_statuses", ()))
    outcome = "caught" if killed else "survived"
    if raw["outcome"] != outcome or raw["reason"] != reason:
        raise ValueError(
            f"raw classification disagrees with recomputation for {descriptor['id']}")
    return outcome, reason


def aggregate_context_error(
        fragment: dict, expected_head: str, expected_baseline: dict) -> str:
    if fragment["head_sha"] != expected_head:
        return "fragment head is not the aggregate checkout head"
    if fragment["baseline"] != expected_baseline:
        return "fragment baseline differs from the aggregate checkout baseline"
    return ""


def shard_assignment_error(fragment: dict, plan: list[dict], shard_count: int) -> str:
    index = fragment["shard"]["index"]
    expected = {
        descriptor["id"] for position, descriptor in enumerate(plan)
        if position % shard_count == index
    }
    actual = set(fragment["results"])
    if actual == expected:
        return ""
    return (
        f"fragment shard {index} assignment differs: "
        f"foreign={sorted(actual - expected)[:4]} "
        f"missing={sorted(expected - actual)[:4]}")


def normalized_receipt(fragments: list[dict]) -> dict:
    plan, exclusions = mutation_plan()
    plan_by_id = {item["id"]: item for item in plan}
    expected_ids = set(plan_by_id)
    if not fragments:
        raise ValueError("no mutation fragments supplied")
    for fragment in fragments:
        problem = validate_fragment(fragment)
        if problem:
            raise ValueError(problem)
    for field in (
            "head_sha", "generator_sha256", "source_digests", "plan_sha256",
            "baseline"):
        values = {json.dumps(fragment[field], sort_keys=True) for fragment in fragments}
        if len(values) != 1:
            raise ValueError(f"fragments disagree on {field}")
    if fragments[0]["generator_sha256"] != file_sha256(ROOT / GENERATOR):
        raise ValueError("fragment generator digest is stale")
    if fragments[0]["source_digests"] != source_digests():
        raise ValueError("fragment guard digests are stale")
    if fragments[0]["plan_sha256"] != digest(plan):
        raise ValueError("fragment plan digest is stale")
    aggregate_baseline = baseline_results(ROOT)
    context_problem = aggregate_context_error(
        fragments[0], git_head(), aggregate_baseline)
    if context_problem:
        raise ValueError(context_problem)
    counts = {fragment["shard"]["count"] for fragment in fragments}
    if len(counts) != 1:
        raise ValueError("fragments disagree on shard count")
    shard_count = counts.pop()
    indices = [fragment["shard"]["index"] for fragment in fragments]
    if sorted(indices) != list(range(shard_count)) or len(indices) != len(set(indices)):
        raise ValueError(
            f"fragment shard inventory is incomplete or duplicated: {sorted(indices)}")
    for fragment in fragments:
        assignment_problem = shard_assignment_error(fragment, plan, shard_count)
        if assignment_problem:
            raise ValueError(assignment_problem)
    combined = {}
    for fragment in fragments:
        for mutation_id, raw in fragment["results"].items():
            if mutation_id in combined:
                raise ValueError(f"overlapping mutation result {mutation_id}")
            combined[mutation_id] = (raw, fragment["baseline"])
    foreign = sorted(set(combined) - expected_ids)
    missing = sorted(expected_ids - set(combined))
    if foreign or missing:
        raise ValueError(
            f"mutation result inventory foreign={foreign[:4]} missing={missing[:4]}")
    reduced, survivors = {}, []
    for mutation_id in sorted(expected_ids):
        raw, baseline = combined[mutation_id]
        outcome, _reason = recompute_raw_result(
            raw, plan_by_id[mutation_id], baseline)
        descriptor = dict(plan_by_id[mutation_id])
        descriptor.pop("allowed_statuses", None)
        descriptor["outcome"] = outcome
        reduced[mutation_id] = descriptor
        if outcome == "survived":
            survivors.append(mutation_id)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": f"{GENERATOR} --aggregate ... --accept-receipt-changes",
        "note": NOTE,
        "generator_sha256": fragments[0]["generator_sha256"],
        "source_digests": fragments[0]["source_digests"],
        "plan_sha256": fragments[0]["plan_sha256"],
        "baseline": {relative: "passed" for relative in GUARDS},
        "sweep_exclusions": exclusions,
        "results": reduced,
        "survivors": survivors,
        "caught": len(reduced) - len(survivors),
        "total": len(reduced),
    }


def summary_text(payload: dict) -> str:
    lines = [
        "<!-- generated by tools/write-mutation-receipt.py -- do not edit -->", "",
        "| module | guarded set | elements | caught | survived |",
        "|---|---|---:|---:|---:|",
    ]
    grouped, sites = {}, []
    for entry in payload["results"].values():
        if entry["kind"] == "site":
            sites.append(entry)
            continue
        key = (entry["module"], entry["name"])
        counts = grouped.setdefault(key, {"caught": 0, "survived": 0})
        counts[entry["outcome"]] += 1
    for (module, name), counts in sorted(grouped.items()):
        total = counts["caught"] + counts["survived"]
        lines.append(
            f"| `{Path(module).name}` | `{name}` | {total} | "
            f"{counts['caught']} | {counts['survived']} |")
    lines += ["", "| module | site mutation | outcome |", "|---|---|---|"]
    for entry in sorted(sites, key=lambda item: (item["module"], item["label"])):
        lines.append(
            f"| `{Path(entry['module']).name}` | {entry['label']} | "
            f"{entry['outcome']} |")
    lines += [
        "",
        f"{payload['caught']} of {payload['total']} planned mutations are caught; "
        f"{len(payload['survivors'])} exact mutation IDs remain recorded coverage debt.",
        "",
    ]
    if payload["sweep_exclusions"]:
        lines.append(
            "Not swept: " + "; ".join(
                f"`{name}` ({reason})" for name, reason
                in sorted(payload["sweep_exclusions"].items())) + ".")
    return "\n".join(lines) + "\n"


def load_json(path: Path) -> dict:
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON object key {key!r} in {path}")
            value[key] = item
        return value

    return json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def aggregate(paths: list[Path], accept: bool) -> int:
    payload = normalized_receipt([load_json(path) for path in paths])
    summary = summary_text(payload)
    existing = load_json(RECEIPT) if RECEIPT.is_file() else None
    existing_summary = SUMMARY.read_text(encoding="utf-8") if SUMMARY.is_file() else None
    if not accept and (existing != payload or existing_summary != summary):
        before = len(existing.get("results", {})) if isinstance(existing, dict) else 0
        print(
            f"refusing mutation receipt change ({before} -> {payload['total']} results; "
            f"{len(payload['survivors'])} survivors); review fragments and rerun with "
            "--accept-receipt-changes",
            file=sys.stderr)
        return 2
    if accept:
        RECEIPT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
        SUMMARY.write_text(summary, encoding="utf-8")
        print(
            f"wrote {RECEIPT.relative_to(ROOT)} and {SUMMARY.relative_to(ROOT)}: "
            f"{payload['caught']}/{payload['total']} caught, "
            f"{len(payload['survivors'])} survivors")
    else:
        print(
            f"verified {payload['caught']}/{payload['total']} caught mutation outcomes "
            "against the tracked receipt")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-plan", action="store_true")
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--shard-count", type=int)
    parser.add_argument("--fragment", type=Path)
    parser.add_argument("--expected-head")
    parser.add_argument("--aggregate", nargs="+", type=Path)
    parser.add_argument("--accept-receipt-changes", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.list_plan:
            plan, exclusions = mutation_plan()
            kinds = {kind: sum(item["kind"] == kind for item in plan)
                     for kind in ("set-element", "site")}
            print(json.dumps({
                "total": len(plan), "kinds": kinds,
                "plan_sha256": digest(plan), "exclusions": exclusions,
            }, indent=1))
            return 0
        if args.aggregate:
            return aggregate(args.aggregate, args.accept_receipt_changes)
        if (args.shard_index is None or args.shard_count is None
                or args.fragment is None):
            print(
                "choose --list-plan, --aggregate <fragments>, or all of "
                "--shard-index/--shard-count/--fragment",
                file=sys.stderr)
            return 2
        payload = fragment_payload(args.shard_index, args.shard_count, args.expected_head)
        args.fragment.parent.mkdir(parents=True, exist_ok=True)
        args.fragment.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
        print(
            f"wrote {args.fragment}: shard {args.shard_index}/{args.shard_count}, "
            f"{len(payload['results'])} mutation(s)")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"mutation proof failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
