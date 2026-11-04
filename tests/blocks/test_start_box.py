"After Start on Home: the pending card shows under the Start button, a second press starts no second walk, and the walk opens when it is ready."
import re, socket, threading, time, pytest
from pathlib import Path
from fastcore.basics import AttrDict
import abhyasa.blocks.walk.app as walk_app

GOAL = 'fine-tune my own diffusion model to make a comic'
PLAN = dict(title='Diffusion comic', subject='ml', steps=[dict(name='Noise schedule', statement='', doc='15_DDPM', why='The base.')])

@pytest.fixture(autouse=True)
def no_research():
    "Research is off, so no job of the new walk looks on the web after the test. The settings folder is shared by the tests, so the old value comes back."
    from abhyasa.learner import val, set_val
    old = val('research.on'); set_val('research.on', False)
    yield
    set_val('research.on', old)

@pytest.fixture
def held(monkeypatch):
    "The planner of a goal walk waits for `gate`. `calls` counts the plans; `done` is set when a plan ends."
    gate, done, calls, real = threading.Event(), threading.Event(), [], walk_app.walk_from_topic
    def plan(*a, **kw):
        calls.append(a[2])
        try:
            assert gate.wait(20), 'the test did not release the plan'
            return real(*a, **kw)
        finally: done.set()
    monkeypatch.setattr(walk_app, 'walk_from_topic', plan)
    yield AttrDict(gate=gate, done=done, calls=calls)
    gate.set()   # a test that fails early never leaves the plan waiting

def notebooks(lr):
    "One notebook on the notebooks shelf, so the goal has a vault source."
    lr.vault.shelf('notebooks').add('# Denoising diffusion\n\nWe add noise to each image.', title='nbs/15_DDPM', source='/tmp/course22p2/nbs/15_DDPM.ipynb',
                                    kind='notebook', meta=dict(root='course22p2'))

START = dict(q=GOAL, sources=['vault:course22p2'], chips='1')

def test_the_slot_of_the_result_is_under_start(mk):
    "The Start form sends its result to `#walk-out`, which comes after the Start button and before the sources."
    h = mk().get('/').text
    form = re.search(r'<form[^>]*id="start-form"[^>]*>', h)[0]
    assert 'hx-target="#walk-out"' in form and 'hx-disinherit="*"' in form   # the pending card inside keeps its own target
    assert h.index('id="start-go"') < h.index('id="walk-out"') < h.index('id="start-chips"') < h.index('</form>', h.index('id="start-go"'))

def test_a_read_keeps_the_slot_and_moves_the_sources(mk, lr):
    "A read swaps the Start part and sends the sources out of band, so a pending card in the slot stays."
    lr.vault.shelf('notebooks').add('x', title='a', source='/tmp/course22p2/a.ipynb', kind='notebook', meta=dict(root='course22p2'))
    h = mk().get('/learn/read', params=dict(q='how noise works in course22p2')).text
    assert 'id="walk-out"' not in h and re.search(r'<div[^>]*id="start-chips"[^>]*hx-swap-oob="true"|<div[^>]*hx-swap-oob="true"[^>]*id="start-chips"', h)
    assert 'value="vault:course22p2"' in h

def test_start_shows_the_pending_card_and_starts_one_walk(mk, lr, walk_fake, held):
    "Start gives the pending card for the slot, with the job link. A second Start while the walk is made gives the same card and no second plan."
    notebooks(lr); walk_fake.rules['You plan a learning path'] = PLAN
    cl = mk()
    r = cl.post('/walk/new', data=START)
    assert 'class="walk-link pending"' in r.text and 'You can leave this page.' in r.text and 'href="#activity"' in r.text
    poll = re.search(r'hx-get="([^"]+)"', r.text)[1].replace('&amp;', '&')
    again = cl.post('/walk/new', data=START)
    assert re.search(r'hx-get="([^"]+)"', again.text)[1].replace('&amp;', '&') == poll
    assert 'class="walk-link pending"' in cl.get(poll).text   # it still runs
    held.gate.set(); assert held.done.wait(20)
    for _ in range(200):   # the job row ends just after the plan
        if 'HX-Redirect' in (r := cl.get(poll)).headers: break
        time.sleep(.05)
    jid = r.headers['HX-Redirect'].split('/')[-1]
    assert r.headers['HX-Redirect'] == f'/w/{jid}' and lr.journey(jid).goal == GOAL   # the slot sends you to the new walk
    assert held.calls == [GOAL]   # one plan for two presses

def _chromium():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p: return Path(p.chromium.executable_path).exists()
    except Exception: return False

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_the_pending_line_is_in_view_after_start(mk, lr, walk_fake, held, tmp_path, monkeypatch):
    "In a window of 1280×800 with 10 sources, Start opens the builder (the owner's choice): the page with the builder in the side pane, your words as its first message, and the 10 sources as main sources."
    import uvicorn
    from playwright.sync_api import sync_playwright
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    ps = []
    for k in range(10):
        (d := tmp_path/f'notes{k:02d}').mkdir(); (d/'a.md').write_text('# Noise\n\nNoise is added at each step.\n'); ps.append(str(d))
    walk_fake.rules['You plan a learning path'] = PLAN
    cl = mk()
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True, args=['--mute-audio'])   # a temp profile, with no window and no focus
            try:
                pg = b.new_page(viewport=dict(width=1280, height=800))
                pg.goto(f'http://127.0.0.1:{port}/#start'); pg.wait_for_selector('#start-form')
                pg.evaluate("ps => { const k = document.getElementById('start-keep'); for (const v of ps) { const i = document.createElement('input'); i.type = 'hidden'; i.name = 'extra'; i.value = v; k.append(i); } }", ps)
                pg.fill('#start-q', 'how noise works'); pg.dispatch_event('#start-q', 'input')
                pg.wait_for_function("() => document.querySelectorAll('#start-form input[name=sources]').length === 10")
                pg.wait_for_selector('#start-go:not([disabled])')
                pg.click('#start-go')
                pg.wait_for_url('**/build/**', timeout=10000)
                bid = pg.url.split('/build/')[1].split('?')[0]
                assert 'rh=' in pg.url and pg.locator('#rh-pane iframe').count() == 1
                b_ = lr.build(bid)
                assert len(b_.brief['sources']) == 10 and {x['role'] for x in b_.brief['sources']} == {'main'} and b_.events[1]['delta'] == 'how noise works'
            finally: b.close()
    finally:
        held.gate.set(); held.done.wait(20)
        srv.should_exit = True; th.join(5)

def test_a_folder_inside_a_source_is_not_a_second_source(mk, tmp_path, monkeypatch):
    "A goal names `abhyasa`: the repo `abhyasa` and the folder `abhyasa/abhyasa` in it both have the name. Only the repo is a source, as it files the folder too."
    from abhyasa.learner import set_val
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)   # a root of the sources is in the home folder
    code = tmp_path/'code'
    (repo := code/'abhyasa').mkdir(parents=True); (repo/'.git').mkdir(); (repo/'README.md').write_text('# abhyasa\n')
    (inner := repo/'abhyasa').mkdir(); (inner/'app.py').write_text('x = 1\n')
    (other := code/'notes'/'abhyasa').mkdir(parents=True); (other/'a.md').write_text('# Notes\n')   # the same name, not inside the repo
    set_val('sources.roots', str(code))
    h = mk().get('/learn/read', params=dict(q='I want to market abhyasa')).text
    assert f'value="repo:{repo}"' in h and f'value="folder:{other}"' in h and f'folder:{inner}"' not in h
