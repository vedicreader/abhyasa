# tests/test_trial.py: the trial script works on the shared data, with no model, no network and no browser
import os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parents[1]

def test_trial_dry_run(tmp_path):
    home = tmp_path/'home'; home.mkdir()   # a new home: any use of the real vault or settings would write here
    r = subprocess.run([sys.executable, 'tools/walk_trial.py', '--dry', '--no-shots', '--out', str(tmp_path/'out')],
                       capture_output=True, text=True, timeout=180, cwd=ROOT, env={**os.environ, 'HOME': str(home)})
    assert r.returncode == 0, r.stderr
    rep = (tmp_path/'out'/'report.md').read_text()
    for name in ('attention', 'gradient-descent', 'pydantic-ai', 'claude-code'): assert name in rep
    assert 'one ask' in rep and 's/step' in rep and 'naive' in rep and 'Leela' in rep
    rows = [l for l in rep.splitlines() if l.startswith('| ') and l.split(' | ')[0][2:] in ('attention', 'gradient-descent', 'pydantic-ai', 'claude-code')]
    assert len(rows) == 4 and not any('error' in l for l in rows), rows
    for name in ('pydantic-ai', 'claude-code'): assert '1 links right, 1 pages right, 0 code checks' in rep.split(f'## {name}')[1]   # no code check, and the right link on the step with Leela
    assert not [p for p in home.rglob('*') if '.vishalakshi' in p.parts or 'abhyasa' in p.parts]   # no real vault, no real settings
