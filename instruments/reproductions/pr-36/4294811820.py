"""Review reproduction for PR 36 thread 4294811820: [P2] Use the complete claim as the worklist identity

Posted by the reviewer against head 2aea1fb at hooks/harness_check.py:1329, kept verbatim;
the final assertion is inverted to the expected outcome.
Run from the repository root: python3 instruments/reproductions/pr-36/4294811820.py
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
source = Path('hooks/harness_check.py').resolve()
spec = importlib.util.spec_from_file_location('subject', source)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

import contextlib
import shutil
repo = source.parent.parent
with tempfile.TemporaryDirectory() as raw:
    root = Path(raw)
    for name in ('skills', 'contracts'):
        shutil.copytree(repo / name, root / name)
    shutil.copyfile(repo / 'AGENTS.md', root / 'AGENTS.md')
    target = root / 'skills/git-workflow/references/deferred.md'
    original = target.read_text()
    assert original.count('require explicit authorization.') == 1
    modified = original.replace('require explicit authorization.', 'need no authorization at all.')
    for name, text in [('baseline', original), ('changed', modified), ('restored', original)]:
        target.write_text(text)
        run = m.Run(str(root), ci=True)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            run.c12_claim_binding()
        print(name, 'failures=', len(run.failures),
              'worklist_occurrences=', len(run.worklists.get('C12', [])))
        if name == 'changed':  # expected: one new item and one stale baseline entry, both red
            assert run.failures and len(run.worklists['C12']) == 14
            assert any('(not in baseline' in d for _c, d in run.failures)
            assert any('stale baseline' in d for _c, d in run.failures)
        else:
            assert not run.failures and len(run.worklists['C12']) == 15
