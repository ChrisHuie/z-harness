"""Review reproduction for PR 36 thread 4294811773: [P2] Close or explicitly constrain the final settings-write race

Posted by the reviewer against head 2aea1fb at tools/install-claude.py:474, kept verbatim;
the assertion is unchanged: this interleaving is the documented residual.
Run from the repository root: python3 instruments/reproductions/pr-36/4294811773.py
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
    m.stage(str(source.parent.parent), home, version_id='v1')
    m.activate(home, 'v1')
    settings_path = Path(home) / '.claude/settings.json'
    real_replace = os.replace
    writes = []
    def replace_after_writer(src, dst):
        if Path(dst) == settings_path:
            # A separate process writes after the final stat, before the actual rename.
            writer = "import json,sys; from pathlib import Path; p=Path(sys.argv[1]); d=json.loads(p.read_text()); d['appUpdate']='keep-me'; p.write_text(json.dumps(d))"
            subprocess.run([sys.executable, '-c', writer, str(settings_path)], check=True)
            writes.append(True)
        return real_replace(src, dst)
    with patch.object(m.os, 'replace', replace_after_writer):
        active = m.activate(home, 'v1')
    retained = m.load_json(settings_path).get('appUpdate')
    print('activation=', active['version'], 'writer_completed=', bool(writes),
          'app_update=', retained)
    assert writes == [True] and retained is None
