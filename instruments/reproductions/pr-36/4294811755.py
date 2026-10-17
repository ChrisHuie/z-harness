"""Review reproduction for PR 36 thread 4294811755: [P2] Recover an interrupted switch before trusting the active receipt

Posted by the reviewer against head 2aea1fb at tools/install-claude.py:507, kept verbatim;
the final assertion is inverted to the expected outcome.
Run from the repository root: python3 instruments/reproductions/pr-36/4294811755.py
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
source = Path('tools/install-claude.py').resolve()
spec = importlib.util.spec_from_file_location('subject', source)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

with tempfile.TemporaryDirectory() as home:
    for version in ('v1', 'v2'):
        m.stage(str(source.parent.parent), home, version_id=version)
    m.activate(home, 'v1')
    child = """import importlib.util, os, sys
s = importlib.util.spec_from_file_location('i', sys.argv[1])
i = importlib.util.module_from_spec(s); s.loader.exec_module(i)
i.activate(sys.argv[2], 'v2', after_replace=lambda: os._exit(86))
"""
    dead = subprocess.run([sys.executable, '-c', child, str(source), home])
    rollback = subprocess.run([sys.executable, str(source), '--activate', 'v1',
                               '--home', home], capture_output=True, text=True)
    check = subprocess.run([sys.executable, str(source), '--check', '--home', home],
                           capture_output=True, text=True)
    settings = m.load_json(Path(home) / '.claude/settings.json')
    commands = [h['command'] for _, _, h in m.registered_handlers(settings)]
    counts = {v: sum('/' + v + '/' in c for c in commands) for v in ('v1', 'v2')}
    print('process_exit=', dead.returncode, 'rollback_exit=', rollback.returncode,
          'check_exit=', check.returncode, 'hooks=', counts)
    print(check.stdout.splitlines()[-1])
    assert dead.returncode == 86 and rollback.returncode == check.returncode == 0
    assert counts == {'v1': 4, 'v2': 0}  # expected: one version's entries, never both
