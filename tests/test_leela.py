import json, subprocess, sys
from fastcore.basics import AttrDict
from abhyasa.core.cfg import cfg
from abhyasa.core.leela import leela_link, _alive
from abhyasa.contract import vault_key
from walk_data import leela_file

def test_leela_link_is_local_and_live(monkeypatch, tmp_path):
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

def test_leela_link_has_the_key_only_with_a_vault(monkeypatch, tmp_path):
    "With a vault, the link has its key `v`. With none, the link is as in 0.0.12."
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path)); leela_file(tmp_path); j = AttrDict(id='attention-ab12')
    assert leela_link(j, 3, vault=tmp_path/'v.db') == f'http://127.0.0.1:5011/learn?walk=attention-ab12&step=3&v={vault_key(tmp_path/"v.db")}'
    assert leela_link(j, 3) == 'http://127.0.0.1:5011/learn?walk=attention-ab12&step=3'

def test_a_pid_of_zero_or_less_is_not_alive(monkeypatch, tmp_path):
    "`os.kill(0, 0)` signals the process group, so a pid of 0 or less must not count as a running Leela."
    assert not any(map(_alive, (0, -1, True, None, 'x', 1.5)))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path)); monkeypatch.setitem(cfg, 'leela', '')
    f = leela_file(tmp_path); f.write_text(json.dumps({**json.loads(f.read_text()), 'pid': 0}))   # the helper turns a pid of 0 into this pid
    assert leela_link(AttrDict(id='attention-ab12')) is None

def test_address_is_rebuilt_from_its_parts(monkeypatch, tmp_path):
    "A browser reads `\\` and `@` in another way than Python does. Such an address gives no link. A good one is rebuilt from its scheme, host and port."
    from abhyasa.core.leela import loopback
    for bad in ('http://evil.com\\@127.0.0.1:5010', 'http://evil.com@127.0.0.1:5010/', 'http://u:p@127.0.0.1:5010/', 'http://127.0.0.1:5010\\@evil.com/',
                'https://127.0.0.1:5010/', 'http://127.0.0.1/', 'http://127.0.0.1:99999/', 'http://127.0.0.1:5010/\n', 'http://127.0.0.1:5010/ x', 5010, None, ['x']):
        assert loopback(bad) is None, bad
    assert loopback('http://127.0.0.1:5010/x?y=1#z') == 'http://127.0.0.1:5010' and loopback('http://[::1]:5010/') == 'http://[::1]:5010'
    assert loopback('http://localhost:5010') == 'http://localhost:5010'
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path)); monkeypatch.setitem(cfg, 'leela', 'http://evil.com\\@127.0.0.1:5020/')
    leela_file(tmp_path, url='http://evil.com\\@127.0.0.1:5011/')
    assert leela_link(AttrDict(id='attention-ab12')) is None                                  # neither the file nor the setting gives a link
