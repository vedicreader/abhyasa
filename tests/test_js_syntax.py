"Each app script parses (`node --check`), so a slip such as a name declared twice fails here. Skips when node is not installed."
import shutil, subprocess, pytest
from pathlib import Path

JS = sorted(p for p in (Path(__file__).parents[1]/'abhyasa').rglob('*.js') if 'vendor' not in p.parts)

def test_there_are_scripts(): assert len(JS) >= 10

@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
@pytest.mark.parametrize('p', JS, ids=lambda p: p.name)
def test_js_parses(p):
    r = subprocess.run(['node', '--check', str(p)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
