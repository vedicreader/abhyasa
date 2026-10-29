"abhyasa's address file: `{url, pid, vault}`, as Leela's own `serving.json`, so Leela can link back to a walk."
import json, os, stat, subprocess, sys
import pytest
from abhyasa.core.leela import abhyasa_address, write_address, drop_address
from abhyasa.contract import read_handoff

@pytest.fixture
def addr(monkeypatch, tmp_path):
    "The address file in a temp folder, never the real `~/.config/abhyasa/serving.json`."
    f = tmp_path/'cfg'/'serving.json'; monkeypatch.setenv('ABHYASA_ADDRESS_FILE', str(f)); return f

def test_read_handoff_refuses_bad_v():
    for q in ('walk=a&v=xyz', 'walk=a&v=0A1B2C3D', 'walk=a&v=0a1b2c3', 'walk=a&v=0a1b2c3d%0A'):
        with pytest.raises(ValueError, match='v is not a vault key'): read_handoff(q)
    assert read_handoff('walk=a').v == '' and read_handoff('walk=a&step=1&v=0a1b2c3d').v == '0a1b2c3d'

def test_address_file_written_and_removed(addr):
    assert abhyasa_address() == addr
    write_address('http://127.0.0.1:5077', vault='/v.db')
    assert json.loads(addr.read_text()) == dict(url='http://127.0.0.1:5077', pid=os.getpid(), vault='/v.db')
    assert stat.S_IMODE(addr.stat().st_mode) == 0o600 and [p.name for p in addr.parent.iterdir()] == ['serving.json']   # no temp file left
    drop_address(); assert not addr.exists()
    drop_address()                                                                       # no file: nothing to do

def test_address_file_of_another_abhyasa_stays(addr):
    "A file with another pid belongs to an abhyasa that started later. This one does not remove it."
    write_address('http://127.0.0.1:5077', vault='/v.db')
    addr.write_text(json.dumps({**json.loads(addr.read_text()), 'pid': os.getpid() + 1}))
    drop_address(); assert addr.exists()

def test_address_file_is_loopback_only(addr):
    for url in ('http://evil.example:5077', 'https://127.0.0.1:5077', 'http://127.0.0.1'):
        with pytest.raises(ValueError): write_address(url, vault='/v.db')
    assert not addr.exists()

def test_address_file_default_path(monkeypatch, tmp_path):
    monkeypatch.delenv('ABHYASA_ADDRESS_FILE', raising=False); monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    assert abhyasa_address() == tmp_path/'abhyasa'/'serving.json'

def test_address_file_goes_at_exit(addr):
    "The app registers `drop_address` with `atexit`, so the file goes when the process ends."
    code = ("import atexit; from abhyasa.core.leela import write_address, drop_address; "
            "write_address('http://127.0.0.1:5077', '/v.db'); atexit.register(drop_address); print(open(__import__('os').environ['ABHYASA_ADDRESS_FILE']).read())")
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, check=True, env={**os.environ, 'ABHYASA_ADDRESS_FILE': str(addr)}).stdout
    assert json.loads(out)['url'] == 'http://127.0.0.1:5077' and not addr.exists()
