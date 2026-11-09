"An app that a host runs in its own process: its own cookie, no speech warm-up, no agent of its own, every model call through the host ask, and a bounded stop."
import threading, time
import pytest
from starlette.testclient import TestClient
from abhyasa.app import mk_app, stop_app, SESSION_COOKIE
from abhyasa.blocks import NAMES
import abhyasa.models as models, abhyasa.path as path
from walk_data import walk

HOSTED = [n for n in NAMES if n not in ('build', 'guide')]

class HostAsk:
    "A host's default `ask`: each routed call is recorded with its task, then answered by `fake`."
    hosted, model = True, 'host/model'
    def __init__(self, fake): self.fake, self.tasks = fake, []
    def via(self, task, name='', max_tokens=None):
        def ask(prompt, sp=''): self.tasks.append(task); return self.fake(prompt, sp)
        ask.stream, ask.model = (lambda prompt, sp='': iter([ask(prompt, sp)])), name or self.model
        return ask
    def __call__(self, prompt, sp=''): return self.via('ask')(prompt, sp)

@pytest.fixture
def host(lr, walk_fake, monkeypatch):
    def own(*a, **kw): raise AssertionError('a hosted app made a model call of its own')
    for n in ('ramabana_agent', 'ramabana_oneshot', 'ramabana_stream', 'model_ask'): monkeypatch.setattr(models, n, own)
    monkeypatch.setattr(path, 'ramabana_lead', own)
    h = HostAsk(walk_fake)
    app = mk_app(lr, h, transcribe=lambda a, hint='': 'spoken', names=HOSTED, hosts=('testserver',), warm_speech=False)
    yield h, app
    stop_app(app, 1)

def test_a_hosted_app_asks_only_the_host(host, lr):
    h, app = host; cl = TestClient(app)
    jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    page = cl.get(f'/w/{jid}/0?pane=1').text
    assert 'id="check"' in page
    cl.get(f'/w/{jid}/0/check'); cl.post(f'/w/{jid}/0/answer', data=dict(answer='the rank', confidence=70))
    assert lr.attempts(), 'the answer was not kept'
    assert h.tasks and 'grade' in h.tasks and all(t for t in h.tasks), h.tasks

def test_a_hosted_app_keeps_its_own_cookie_and_loads_no_speech(host):
    h, app = host
    assert [m.kwargs['session_cookie'] for m in app.user_middleware if m.cls.__name__ == 'SessionMiddleware'] == [SESSION_COOKIE]
    assert app.state.svc['speech'].status == 'not loaded'

def test_hosted_gather_makes_no_agent(host, lr):
    h, app = host; cl = TestClient(app)
    jid = walk(cl, lr)
    out = path.gather(lr, jid, threading.Event(), app.state.svc['ask'])
    assert 'second agent' in (lr.journey(jid).get('gather') or [{}])[0].get('outcome', '') and out.read == 0

def test_stop_app_keeps_its_deadline(host):
    h, app = host
    ev = threading.Event(); app.state.svc['pool'].submit(ev.wait, 5)
    t = time.monotonic(); stop_app(app, .3)
    assert time.monotonic() - t < 1.5
    stop_app(app, .3)   # a second stop does nothing
    ev.set()
    for p in app.state.pools: p.shutdown(wait=True)
