import json, subprocess, sys
from pathlib import Path
from fastcore.basics import AttrDict
from abhyasa.core.cfg import cfg
from abhyasa.core.leela import leela_link, _alive, use_vault, app_vault
from abhyasa.contract import vault_key
from walk_data import leela_file

def test_leela_link_is_local_and_live(monkeypatch, tmp_path):
    monkeypatch.setattr('abhyasa.core.leela._app', dict(vault=None)); monkeypatch.setitem(cfg, 'vault', None)   # no vault known: no key
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path)); j = AttrDict(id='attention-ab12')
    assert leela_link(j, 2) is None                                                     # no address file: no link
    f = leela_file(tmp_path)
    assert leela_link(j, 2) == 'http://127.0.0.1:5011/learn?walk=attention-ab12&step=2'
    assert leela_link(None, topic='Softmax') == 'http://127.0.0.1:5011/learn?topic=Softmax'
    p = subprocess.Popen([sys.executable, '-c', '']); p.wait()
    leela_file(tmp_path, pid=p.pid); assert leela_link(j) is None                       # a stale file: that Leela stopped
    leela_file(tmp_path, url='http://evil.example:5011/'); assert leela_link(j) is None  # not on this computer
    f.unlink(); monkeypatch.setitem(cfg, 'leela', 'http://127.0.0.1:5020/')
    assert leela_link(j) == 'http://127.0.0.1:5020/learn?walk=attention-ab12'           # the owner's setting
    monkeypatch.setitem(cfg, 'leela', 'https://evil.example/'); assert leela_link(j) is None

def test_leela_file_override(monkeypatch, tmp_path):
    j = AttrDict(id='attention-ab12'); f = leela_file(tmp_path / 'else', port=5019)
    monkeypatch.setenv('ABHYASA_LEELA_FILE', str(f))                                    # no change to XDG_CONFIG_HOME or HOME
    assert leela_link(j, vault=tmp_path/'v.db') == f'http://127.0.0.1:5019/learn?walk=attention-ab12&v={vault_key(tmp_path/"v.db")}'

def test_leela_link_names_the_vault_of_the_app(mk, monkeypatch, tmp_path):
    "The link has the key of the vault that `mk_app` uses, so Leela can tell when it uses another vault."
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path)); leela_file(tmp_path)
    mk(names=['walk'])
    lr_path = app_vault(); assert lr_path and vault_key(lr_path) == vault_key(Path(lr_path).resolve())
    assert leela_link(AttrDict(id='attention-ab12'), 3) == f'http://127.0.0.1:5011/learn?walk=attention-ab12&step=3&v={vault_key(lr_path)}'
    monkeypatch.setattr('abhyasa.core.leela._app', dict(vault=None)); use_vault(tmp_path/'other.db')
    assert leela_link(AttrDict(id='a')).endswith(f'&v={vault_key(tmp_path/"other.db")}')

def test_a_pid_of_zero_or_less_is_not_alive(monkeypatch, tmp_path):
    "`os.kill(0, 0)` signals the process group, so a pid of 0 or less must not count as a running Leela."
    assert not any(map(_alive, (0, -1, True, None, 'x', 1.5)))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path)); monkeypatch.setitem(cfg, 'leela', '')
    f = leela_file(tmp_path); f.write_text(json.dumps({**json.loads(f.read_text()), 'pid': 0}))   # the helper turns a pid of 0 into this pid
    assert leela_link(AttrDict(id='attention-ab12')) is None
