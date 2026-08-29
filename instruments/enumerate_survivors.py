"""Single-operand survivor enumeration.

Method: over the module's production region (every top-level function except selftest),
(1) every `if`/`elif` test replaced by False; (2) every operand of a boolean `and`/`or`
replaced by its identity (True for and, False for or); (3) every `return` whose value is not
a constant replaced by `return True` and by `return False`. One mutant per site for (1) and
(2); two mutants per site for (3). A site is KILLED when the module's own --selftest exits
non-zero or reports failures>0 for the mutant (for a return site: under BOTH mutants, and
separately reported under EITHER). Source is the file given; the mutant runs from a
directory copy so relative fixtures resolve.
"""
import ast, os, re, shutil, subprocess, sys, tempfile, json

src_path = os.path.abspath(sys.argv[1])
extra_copy = sys.argv[2:]  # extra sibling files/dirs to copy beside the mutant
source = open(src_path, encoding="utf-8").read()
tree = ast.parse(source)

def prod_functions(tree):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name != "selftest":
            yield node

sites = []  # (kind, node-to-replace-locator, replacement-source)
for fn in prod_functions(tree):
    for node in ast.walk(fn):
        if isinstance(node, ast.If):
            sites.append(("if", node.test, ["False"]))
        elif isinstance(node, ast.BoolOp):
            ident = "True" if isinstance(node.op, ast.And) else "False"
            for value in node.values:
                sites.append(("boolop", value, [ident]))
        elif isinstance(node, ast.Return) and node.value is not None and not isinstance(node.value, ast.Constant):
            sites.append(("return", node.value, ["True", "False"]))

lines = source.splitlines(keepends=True)
def offset(lineno, col):
    return sum(len(l) for l in lines[:lineno - 1]) + col

def mutate(node, replacement):
    a = offset(node.lineno, node.col_offset)
    b = offset(node.end_lineno, node.end_col_offset)
    # parenthesise to keep precedence when replacing an operand
    return source[:a] + "(" + replacement + ")" + source[b:]

def run(mutant_source):
    work = tempfile.mkdtemp(prefix="mut-")
    try:
        target = os.path.join(work, os.path.basename(src_path))
        open(target, "w", encoding="utf-8").write(mutant_source)
        for item in extra_copy:
            dst = os.path.join(work, os.path.basename(item))
            (shutil.copytree if os.path.isdir(item) else shutil.copy)(item, dst)
        env = dict(os.environ); env.pop("ANNOUNCED_WORK_GUARD", None)
        try:
            done = subprocess.run([sys.executable, target, "--selftest"], capture_output=True, stdin=subprocess.DEVNULL,
                                  text=True, timeout=180, cwd=work, env=env)
        except subprocess.TimeoutExpired:
            return "killed(timeout)"
        m = re.search(r"SELFTEST-SUMMARY suite=\S+ checks=(\d+) failures=(\d+)", done.stdout)
        if done.returncode != 0 or m is None or int(m.group(2)) > 0:
            return "killed"
        return "survived"
    finally:
        shutil.rmtree(work, ignore_errors=True)

results = []
for idx, (kind, node, replacements) in enumerate(sites):
    outcomes = [run(mutate(node, r)) for r in replacements]
    results.append({"index": idx, "kind": kind, "line": node.lineno, "col": node.col_offset,
                    "source": ast.get_source_segment(source, node)[:80],
                    "outcomes": outcomes})
    print(f"{idx:3} {kind:6} L{node.lineno:<4} {outcomes} {ast.get_source_segment(source, node)[:70]!r}", flush=True)

both_killed = sum(1 for r in results if all(o.startswith("killed") for o in r["outcomes"]))
either_killed = sum(1 for r in results if any(o.startswith("killed") for o in r["outcomes"]))
by_kind = {}
for r in results:
    by_kind.setdefault(r["kind"], [0, 0])
    by_kind[r["kind"]][0] += 1
    by_kind[r["kind"]][1] += 1 if all(o.startswith("killed") for o in r["outcomes"]) else 0
print(f"ENUM-SUMMARY file={os.path.basename(src_path)} sites={len(sites)} killed_all_mutants={both_killed} "
      f"surviving={len(sites)-both_killed} killed_any_mutant={either_killed} by_kind={by_kind}")
json.dump(results, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
          os.path.basename(src_path) + ".results.json"), "w"), indent=1)
