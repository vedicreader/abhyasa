"The board renderer in core: the vendored pen libraries, and the rules that keep model text out of the page code."
import hashlib, re, pytest
from pathlib import Path

CORE = Path(__file__).parents[1]/'abhyasa/core'
PINNED = {'rough.js': '6853af8619532f3939b156cd16824d2e14f31e71d3df306ad5558eeafacab194',              # roughjs 4.6.6, bundled/rough.js
          'perfect-freehand.mjs': '0ddf0e44c727ab39d7211af95685bf12234236f0e2eca376091e5791a71626e4'}  # perfect-freehand 1.2.2, dist/esm/index.mjs

def test_vendored_pens_are_pinned():
    for name, h in PINNED.items(): assert hashlib.sha256((CORE/'vendor'/name).read_bytes()).hexdigest() == h, name

def test_licences_are_kept():
    t = (CORE/'vendor/LICENSES.md').read_text()
    for s in ('Rough.js 4.6.6', 'Preet Shihn', 'perfect-freehand 1.2.2', 'Stephen Ruiz', 'MIT License'): assert s in t, s

def test_model_text_goes_in_as_text():
    "board.js never writes HTML: each say, label, quote and title goes in with textContent, and a link is http(s) or a local path."
    js = (CORE/'board.js').read_text()
    assert 'innerHTML' not in js and 'insertAdjacentHTML' not in js and 'outerHTML' not in js and 'eval(' not in js
    assert 'textContent' in js and "noopener" in js and r"/^(https?:\/\/|\/(?!\/))/" in js

def test_every_page_loads_the_board(mk):
    t = mk().get('/').text
    assert re.search(r'/assets/board\.js\?v=', t) and re.search(r'/assets/board\.css\?v=', t)

def _chromium():
    "True when Playwright's bundled Chromium is installed."
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p: return Path(p.chromium.executable_path).exists()
    except Exception: return False

STEP = lambda say, at: dict(say=say, strokes=[dict(op='box', at=at)])

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_a_streaming_board_takes_steps_as_they_come(mk):
    "A board that starts with step 1 waits at it, goes on when add() gives step 2, and shows its end line only after finish()."
    import socket, threading, time, uvicorn
    from playwright.sync_api import sync_playwright
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(mk().app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    s1, s2 = STEP('One word.', 'a'), STEP('Two words.', 'b')
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page(viewport=dict(width=1000, height=700))
                pg.goto(f'http://127.0.0.1:{port}/'); pg.wait_for_function('window.abhyasaBoard')
                pg.evaluate("""() => document.body.insertAdjacentHTML('beforeend', '<p data-guide-id="a">Alpha</p><p data-guide-id="b">Beta</p>')""")
                assert pg.evaluate('s => abhyasaBoard.add(s)', s2) is False   # no board shows
                pg.evaluate("s => abhyasaBoard.play({steps: [s], tier: 'tutor', sources: [], streaming: true}, {quiet: true})", s1)
                pg.wait_for_function('abhyasaBoard.state && abhyasaBoard.state.done')
                pg.wait_for_timeout(1500)   # step 1 is said, and with no step 2 the board waits at it
                assert pg.evaluate('abhyasaBoard.state') | {'first': 0} == dict(i=0, steps=1, tier='tutor', first=0, streaming=True, done=True)
                assert pg.evaluate("document.querySelector('#guide-strip .board-n').textContent") == 'Step 1'
                assert pg.evaluate("!document.querySelector('#guide-strip .board-end')")
                assert pg.evaluate('s => abhyasaBoard.add(s)', s2) is True
                pg.wait_for_function('abhyasaBoard.state.i === 1')   # it goes on at once
                assert pg.evaluate("abhyasaBoard.finish({steps: [{say: 'Not the same.', strokes: []}], tier: 'tutor', sources: []})") is False
                assert pg.evaluate("ss => abhyasaBoard.finish({steps: ss, tier: 'vault', sources: [], end: 'The end line.'})", [s1, s2]) is True
                st = pg.evaluate('abhyasaBoard.state')
                assert (st['steps'], st['streaming'], st['tier']) == (2, False, 'vault')
                assert pg.evaluate("document.querySelector('#guide-strip .board-end').textContent") == 'The end line.'
                assert pg.evaluate("document.querySelector('#guide-strip .board-n').textContent") == 'Step 2 of 2'
                pg.evaluate("() => abhyasaBoard.play({steps: [{say: 'Whole.', strokes: []}], tier: 'tutor', sources: []}, {quiet: true})")
                assert pg.evaluate('s => abhyasaBoard.add(s)', s2) is False   # a whole board takes no steps
            finally: b.close()
    finally:
        srv.should_exit = True; th.join(5)
