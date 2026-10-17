"""Review reproduction for PR 36 thread 4294811785: [P2] Reject a required scenario that is absent from the execution inventory

Posted by the reviewer against head 2aea1fb at tools/run-skill-evals.py:408, kept verbatim;
the final assertion is inverted to the expected outcome.
Run from the repository root: python3 instruments/reproductions/pr-36/4294811785.py
"""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
source = Path('tools/run-skill-evals.py').resolve()
spec = importlib.util.spec_from_file_location('subject', source)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

with tempfile.TemporaryDirectory() as raw:
    root = Path(raw)
    (root / 'skills/alpha/evals').mkdir(parents=True)
    (root / 'skills/alpha/SKILL.md').write_text('---\nname: alpha\ndescription: fixture\n---\n')
    (root / 'release').mkdir()
    (root / 'contracts').mkdir()
    (root / 'contracts/worklists.json').write_text(json.dumps({
        'schema_version': 1, 'note': 'fixture', 'C12': [], 'C13': []}))
    manifest = {'schema_version': 1, 'note': 'fixture', 'skills': {
        'alpha': {'status': 'tested', 'required': ['001-happy.json']}}}
    (root / 'release/evals.json').write_text(json.dumps(manifest))
    scenario = {'skills': ['alpha'], 'query': 'fixture', 'files': [],
                'expected_behavior': ['emits ## Files']}
    for name in ('001-happy.json', '002-failure.json', '003-near-miss.json'):
        (root / 'skills/alpha/evals' / name).write_text(json.dumps(scenario))
    assert m.validate(str(root), out=io.StringIO()) == 0

    runner = lambda query, cwd: (0, '## Files\n')
    assert m.run(str(root), runner=runner, out=io.StringIO()) == 0
    (root / 'skills/alpha/evals/001-happy.json').unlink()
    validation = m.validate(str(root), out=io.StringIO())
    output = io.StringIO()
    result = m.run(str(root), runner=runner, out=output)
    print('validate_exit=', validation, 'run_exit=', result)
    print(output.getvalue().splitlines()[-1])
    assert validation == 1 and result == 1  # expected: --run is red when its required scenario is absent
