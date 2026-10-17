"""Review reproduction for PR 36 thread 4294811762: [P2] Include event and matcher when removing receipt-owned hooks

Posted by the reviewer against head 2aea1fb at tools/install-claude.py:235, kept verbatim;
the final assertion is inverted to the expected outcome.
Run from the repository root: python3 instruments/reproductions/pr-36/4294811762.py
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
    active = m.activate(home, 'v1')
    owned = next(h for h in active['owned_hooks'] if h['matcher'] == 'Bash')
    handler = {k: owned[k] for k in ('type', 'command', 'timeout')}
    settings_path = Path(home) / '.claude/settings.json'
    settings = m.load_json(settings_path)
    settings['hooks']['PreToolUse'].append({'matcher': 'Bash|Shell', 'hooks': [handler]})
    settings['hooks']['PostToolUse'].append({'matcher': 'Bash', 'hooks': [handler]})
    settings_path.write_text(json.dumps(settings))
    m.activate(home, 'v2')
    final = m.registered_handlers(m.load_json(settings_path))
    kept = [(event, matcher) for event, matcher, h in final if h == handler]
    print('user entries retained:', kept)
    assert sorted(kept) == [('PostToolUse', 'Bash'), ('PreToolUse', 'Bash|Shell')]  # expected: both user entries kept
