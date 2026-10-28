import json, subprocess, sys
from fastcore.basics import AttrDict
from abhyasa.core.cfg import cfg
from abhyasa.core.leela import leela_link
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
