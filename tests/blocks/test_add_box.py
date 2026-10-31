"The Start box takes a folder from the folder chooser of macOS (`/learn/pick`) and shows a cue while you drag files over it."
import json, os, subprocess, pytest
from pathlib import Path
import abhyasa.blocks.add.app as add_app
from starlette.testclient import TestClient
from abhyasa.sources import NO_READ
from abhyasa.settings import NO_FOLDER

@pytest.fixture
def home(tmp_path, monkeypatch):
    "A temp home folder with the folder `course22`, and a folder chooser that a test can open. `$HOME` stays, so Playwright finds its Chromium."
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    (tmp_path/'course22').mkdir(); (tmp_path/'course22'/'a.md').write_text('# Noise\n')
    monkeypatch.setattr(add_app, 'can_pick', lambda: True)
    return tmp_path

def chooser(monkeypatch, out='', code=0):
    "osascript is faked: it gives `out` and stops with `code`. The calls are kept, so a test sees the arguments."
    calls = []
    def run(args, **kw):
        calls.append((args, kw))
        return subprocess.CompletedProcess(args, code, stdout=out, stderr='User canceled. (-128)' if code else '')
    monkeypatch.setattr(add_app, '_osa', run)
    return calls

def local(cl): return TestClient(cl.app, client=('127.0.0.1', 50000))

def test_pick_refuses_a_request_that_is_not_local(mk, home, monkeypatch):
    calls = chooser(monkeypatch, '/x/\n')
    r = mk().post('/learn/pick')   # the test client is not 127.0.0.1
    assert r.status_code == 403 and r.text == add_app.NOT_HERE and not calls

def test_pick_needs_a_mac(mk, home, monkeypatch):
    calls = chooser(monkeypatch, '/x/\n')
    monkeypatch.setattr(add_app, 'can_pick', lambda: False)
    cl = local(mk())
    assert cl.post('/learn/pick').status_code == 403 and not calls
    assert 'id="start-pick"' not in cl.get('/').text   # no button where no chooser opens

def test_pick_gives_the_path_and_a_cancel_gives_nothing(mk, home, monkeypatch):
    cl = local(mk())
    calls = chooser(monkeypatch, f'{home/"course22"}/\n')
    assert cl.post('/learn/pick').json() == dict(paths=[str(home/'course22')])
    args, kw = calls[0]
    assert args[:2] == ['osascript', '-e'] and 'choose folder' in args[2] and kw['timeout'] == add_app.PICK_WAIT   # a list, no shell
    assert 'with multiple selections allowed' in args[2] and args.count('-e') == len(add_app.PICK_ASK)
    chooser(monkeypatch, '', code=1)
    assert cl.post('/learn/pick').json() == dict(paths=[])

def test_pick_several_folders_gives_a_chip_for_each(mk, home, monkeypatch):
    "The chooser gives one POSIX path on each line. Each folder is one path, and the box shows one chip for each."
    cl = local(mk())
    (home/'fastbook').mkdir(); (home/'My notes').mkdir()
    chooser(monkeypatch, f'{home/"course22"}/\n{home/"fastbook"}/\n{home/"My notes"}/\n')
    paths = cl.post('/learn/pick').json()['paths']
    assert paths == [str(home/'course22'), str(home/'fastbook'), str(home/'My notes')]
    h = cl.get('/learn/read', params=dict(q='how noise works', extra=paths)).text
    for x in paths: assert f'name="sources" value="folder:{x}"' in h

def test_a_picked_path_has_the_checks_of_a_typed_path(mk, home, monkeypatch):
    "start.js adds the picked path as `extra`, as it adds a typed path. A file or a folder that you cannot read is refused with the same line."
    cl = local(mk())
    (f := home/'notes.txt').write_text('x')
    (shut := home/'shut').mkdir(); shut.chmod(0)
    try:
        for p, why in ((f, NO_FOLDER), (shut, NO_READ)):
            chooser(monkeypatch, f'{p}\n')
            got, = cl.post('/learn/pick').json()['paths']
            assert got == str(p)
            picked = cl.get('/learn/read', params=dict(q='how noise works', extra=[got])).text
            typed = cl.get('/learn/read', params=dict(q='how noise works', extra=[str(p)])).text
            assert why in picked and picked == typed and f'name="sources" value="folder:{p}"' not in picked
        assert NO_READ in cl.get('/learn/read', params=dict(q=str(shut))).text   # in the main field too
    finally: shut.chmod(0o755)
    h = cl.get('/learn/read', params=dict(q='how noise works', extra=[str(home/'course22')])).text
    assert f'name="sources" value="folder:{home/"course22"}"' in h   # a folder that you can read is a source

@pytest.fixture
def research():
    "Research is on and its line is not told yet. The settings folder is shared by the tests, so the old values come back."
    from abhyasa.settings import set_val, val
    old = val('research.on'), val('research.told')
    set_val('research.on', True); set_val('research.told', False)
    yield
    set_val('research.on', old[0]); set_val('research.told', old[1])

def test_the_box_says_what_you_can_do_once(mk, home, research):
    cl = mk()
    h = cl.get('/').text
    assert add_app.CAN in h and add_app.CUE in h and 'id="start-pick"' in h and 'You can also drop a file here.' not in h
    h = cl.get('/learn/read', params=dict(q='how noise works', extra=[str(home/'course22')])).text
    assert h.count('Turn this off in Settings') == 1 and 'id="start-pick"' in h   # the chooser is beside the field
    assert 'Turn this off in Settings' in cl.get('/learn/read', params=dict(q='how noise works')).text   # a topic has no web chip

def _chromium():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p: return Path(p.chromium.executable_path).exists()
    except Exception: return False

DRAG = """([type, entry]) => {
  const f = document.getElementById('start-form'), dt = new DataTransfer();
  if (entry !== 'dir') dt.items.add(new File(['Softmax turns scores into weights.'], 'notes.txt', {type: 'text/plain'}));
  const e = new DragEvent(type, {bubbles: true, cancelable: true, dataTransfer: dt});
  if (entry === 'dir') Object.defineProperty(e, 'dataTransfer', {value: {types: ['Files'], files: [], getData: () => '',
    items: [{webkitGetAsEntry: () => ({isDirectory: true, name: 'course22'})}]}});
  (type === 'dragleave' ? f : f.querySelector('textarea')).dispatchEvent(e);
}"""

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_drag_cue_drops_and_pick_in_a_browser(mk, home):
    import socket, threading, time, uvicorn
    from playwright.sync_api import sync_playwright
    cl = mk()
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page()
                picked = []
                pg.route('**/learn/pick', lambda r: (picked.append(1), r.fulfill(status=200, content_type='application/json', body=json.dumps(dict(paths=[str(home/'course22')])))))
                pg.goto(f'http://127.0.0.1:{port}/'); pg.wait_for_selector('#start-form')
                cue = pg.locator('#start-form .drop-cue')
                assert not cue.is_visible()
                pg.evaluate(DRAG, ['dragenter', 'file'])
                assert cue.is_visible() and cue.inner_text() == add_app.CUE   # a dashed outline and one line
                assert pg.evaluate("getComputedStyle(document.getElementById('start-form')).outlineStyle") == 'dashed'
                pg.evaluate(DRAG, ['dragleave', 'file'])
                assert not cue.is_visible()
                pg.evaluate(DRAG, ['drop', 'file'])                                      # a text file goes into the box, as before
                pg.wait_for_function("() => document.getElementById('start-q').value.startsWith('Softmax')")
                assert pg.input_value('#start-file') == 'notes.txt' and not cue.is_visible()
                pg.evaluate(DRAG, ['drop', 'dir'])                                       # a folder has no path in a browser
                pg.wait_for_function("() => document.getElementById('start-say').textContent === 'To add a folder, use Pick folders.'")
                pg.fill('#start-q', ''); pg.dispatch_event('#start-q', 'input')
                pg.wait_for_function("() => document.getElementById('start-will')?.textContent && !document.getElementById('start-will').classList.contains('req-err')")
                pg.click('#start-pick')                                                  # the route is faked: no chooser opens
                pg.wait_for_selector(f'#start-form input[name=sources][value="folder:{home/"course22"}"]', state='attached')
                assert picked and pg.locator('#start-keep input[name=extra]').evaluate('i => i.value') == str(home/'course22')
            finally: b.close()
    finally: srv.should_exit = True; th.join(5)

TWO = """() => {
  const f = document.getElementById('start-form'), dt = new DataTransfer();
  dt.items.add(new File(['# Noise\\n\\nA diffusion model adds noise, then learns to remove it.'], 'noise.md', {type: 'text/markdown'}));
  dt.items.add(new File(['The sampler removes the noise in small steps.'], 'steps.txt', {type: 'text/plain'}));
  f.querySelector('textarea').dispatchEvent(new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: dt}));
}"""

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_dropping_two_files_adds_two_chips(mk, home):
    "Two files in one drop: abhyasa files each one in the vault, and the box shows a chip for each. The box keeps no text."
    import socket, threading, time, uvicorn
    from playwright.sync_api import sync_playwright
    cl = mk()
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page()
                pg.goto(f'http://127.0.0.1:{port}/'); pg.wait_for_selector('#start-form')
                pg.evaluate(TWO)
                pg.wait_for_function("() => document.querySelectorAll('#start-form .schip input[name=sources]').length === 2")
                ids = pg.eval_on_selector_all('#start-form .schip input[name=sources]', 'xs => xs.map(x => x.value)')
                names = pg.eval_on_selector_all('#start-form .schip:not(.web) b', 'xs => xs.map(x => x.textContent)')
                assert all(i.startswith('doc:') for i in ids) and sorted(names) == ['noise', 'steps']
                assert pg.input_value('#start-q') == ''
            finally: b.close()
    finally: srv.should_exit = True; th.join(5)

def test_drops_route_files_each_and_refuses_other_types(mk, home):
    cl = mk()
    fs = [('fs', ('a.md', b'# A\n\nAttention mixes the tokens.', 'text/markdown')), ('fs', ('b.png', b'x', 'image/png'))]
    got = cl.post('/learn/files', files=fs).json()
    assert len(got['ids']) == 1 and got['said'] == ['b.png: Drop a PDF, a .md or a .txt file.']
