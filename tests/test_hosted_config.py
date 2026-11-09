"A hosted app keeps its files in the folder of its host and never reads the settings or key files of a standalone abhyasa."
import builtins, contextvars, io, os, threading
import pytest
from starlette.testclient import TestClient
from abhyasa.app import mk_app, stop_app
from abhyasa.learner import CtxPool, cfg_dir, settings, use_config
import abhyasa.models as models
from test_hosted import HostAsk, HOSTED
from walk_data import walk

SECRET = 'sk-sentinel-SECRET-7731'

@pytest.fixture
def sentinel(tmp_path, monkeypatch):
    "A folder like the one of a standalone abhyasa, in `$ABHYASA_CONFIG`, with files that a hosted app must never read."
    d = tmp_path/'standalone'; d.mkdir()
    (d/'settings.json').write_text('{"walks": {"steps": 77}, "stt": {"engine": "openai", "model": "sentinel-model"}}')
    (d/'keys.env').write_text(f'export OPENAI_API_KEY="{SECRET}"\n'); (d/'keys.env').chmod(0o600)
    (d/'.sesskey').write_text('sentinel-session-key')
    monkeypatch.setenv('ABHYASA_CONFIG', str(d)); monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setenv('RAMABANA_CONFIG', str(tmp_path/'ramabana.toml'))
    return d

def snap(d): return {p.name: (p.read_text(), p.stat().st_mtime_ns) for p in d.iterdir()}

@pytest.fixture
def spy(sentinel, monkeypatch):
    "Every open or stat of a path in the sentinel folder is listed."
    seen = []
    def watch(f):
        def w(p, *a, **kw):
            if str(p).startswith(str(sentinel)): seen.append(str(p))
            return f(p, *a, **kw)
        return w
    monkeypatch.setattr(os, 'stat', watch(os.stat)); monkeypatch.setattr(io, 'open', watch(io.open)); monkeypatch.setattr(builtins, 'open', watch(builtins.open))
    return seen

@pytest.fixture
def hosted(lr, walk_fake, sentinel, tmp_path, monkeypatch):
    own = tmp_path/'host'
    h = HostAsk(walk_fake)
    sent = {}
    def post(url, headers, data, files, timeout): sent.update(headers); return type('R', (), dict(raise_for_status=lambda s: None, json=lambda s: dict(text='said')))()
    monkeypatch.setattr(models, 'http_post', post)
    tr = lambda a, hint='': models.transcribe(a, 'openai', hint, 'm')
    app = mk_app(lr, h, transcribe=tr, names=HOSTED, hosts=('testserver',), warm_speech=False, config=own)
    yield app, own, sent
    stop_app(app, 1)

def test_requests_never_touch_the_sentinel_and_the_state_goes_to_the_host(hosted, lr, sentinel, spy):
    app, own, sent = hosted; before = snap(sentinel); spy.clear(); cl = TestClient(app)
    jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    assert 'id="check"' in cl.get(f'/w/{jid}/0?pane=1').text
    cl.get(f'/w/{jid}/0/check'); assert cl.post(f'/w/{jid}/0/answer', data=dict(answer='the rank', confidence=70)).status_code == 200
    page = cl.get('/settings').text
    r = cl.post('/voice/stt', content=b'RIFFxxxx')
    assert r.status_code == 500 and 'no OpenAI key' in r.json()['error']
    assert not sent and SECRET not in page and 'sentinel-model' not in page
    assert not spy, spy
    assert snap(sentinel) == before
    assert (own/'.sesskey').exists() and not (own/'keys.env').exists() and not (own/'settings.json').exists()

def test_the_key_of_a_hosted_speech_call_is_the_environment_key(hosted, monkeypatch, spy):
    app, own, sent = hosted
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-from-environment')
    r = TestClient(app).post('/voice/stt', content=b'RIFFxxxx')
    assert r.json() == dict(text='said') and sent['Authorization'] == 'Bearer sk-from-environment' and not spy

def test_gather_and_jobs_read_no_file_of_the_sentinel(hosted, lr, spy):
    app, own, _ = hosted; cl = TestClient(app); jid = walk(cl, lr)
    from abhyasa import path
    with use_config(own): path.gather(lr, jid, threading.Event(), app.state.svc['ask'])
    assert not spy, spy

def test_every_pool_runs_jobs_in_the_folder_of_the_caller(hosted, tmp_path):
    app, own, _ = hosted
    from abhyasa import show
    pools = app.state.pools
    assert pools and all(isinstance(p, CtxPool) for p in [*pools, show._POOL]), pools   # the demo pool is shared by the process: a type check only
    with use_config(own): got = [p.submit(cfg_dir).result() for p in pools]
    assert got == [own] * len(pools)

def test_a_thread_of_the_app_keeps_the_folder(sentinel, tmp_path):
    out = []
    with use_config(tmp_path): threading.Thread(target=contextvars.copy_context().run, args=(lambda: out.append(cfg_dir()),)).start()
    for t in threading.enumerate():
        if t is not threading.current_thread(): t.join(2)
    assert out == [tmp_path]

def test_a_standalone_app_behaves_as_before(lr, fake, sentinel, monkeypatch):
    app = mk_app(lr, fake, names=['walk'], hosts=('testserver',), warm_speech=False)
    try:
        assert (sentinel/'.sesskey').read_text() == 'sentinel-session-key'   # the same folder, as before
        assert cfg_dir() == sentinel and settings()['walks']['steps'] == 77
        assert models.openai_key() == (SECRET, str(sentinel/'keys.env'))
    finally: stop_app(app, 1)

def test_no_pool_of_the_app_forgets_the_context():
    "The filer pool is local to the walk block: its source must use `CtxPool`, and no app code builds a plain pool."
    import re
    from pathlib import Path
    root = Path(__file__).parent.parent/'abhyasa'
    assert 'CtxPool(FILERS' in (root/'blocks/walk/app.py').read_text()
    bare = [str(p.relative_to(root)) for p in root.rglob('*.py') if re.search(r'\bThreadPoolExecutor\(', p.read_text())]
    assert bare == ['models.py'], bare   # `models.py`: the 8 workers of a model-size lookup, which read no file of abhyasa
