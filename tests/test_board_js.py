"The board renderer in core: the vendored pen libraries, and the rules that keep model text out of the page code."
import hashlib, re, pytest
from pathlib import Path
from abhyasa.core.keys import KEYS

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

def test_keys_skip_text_boxes():
    js = (CORE/'board.js').read_text()
    assert "matches('textarea, input, select, [contenteditable]')" in js
    rows = {(g, k): a for g, k, a in KEYS}
    assert rows[('Guide', 'A')] == 'Say and draw the step again' and rows[('Guide', 'S')] == 'Go back one step'
    assert rows[('Guide', 'D')] == 'Go to the next step' and rows[('Guide', 'esc')] == 'Stop the board'

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

# --- the three looks of a point mark (play option `point`, the setting guide.point) ------------------------------------------
TARGET = """() => document.body.insertAdjacentHTML('beforeend', '<div data-guide-id="t" style="position:absolute;left:420px;top:260px;width:90px;height:28px"></div>' +
            '<style>#board-pointer, #guide-strip { display: none !important; } body > :not(#board-host, .board-hl) { visibility: hidden; } body { background: #fff; }</style>')"""
CLIP = dict(x=250, y=110, width=430, height=330)   # the target and all the place around it where a mark can be

def _ink(png, base) -> int:
    "How much ink a mark puts on the page: the sum of the change of each pixel from the same place with no mark."
    import io
    from PIL import Image, ImageChops
    a, b = (Image.open(io.BytesIO(x)).convert('L') for x in (png, base))
    return sum(i * n for i, n in enumerate(ImageChops.difference(a, b).histogram()))

def _draw(pg, op, look=None):
    "Play one mark on the target at once, with the look `look` (None: no option). Return the ink of the mark and the boxes of its parts."
    opts = {'fast': True, **({'point': look} if look else {})}
    pg.evaluate("([op, o]) => abhyasaBoard.play({steps: [{say: 'Look.', strokes: [{op, at: 't'}]}], tier: 'tutor', sources: []}, o)", [op, opts])
    pg.wait_for_function('abhyasaBoard.state && abhyasaBoard.state.done'); pg.wait_for_timeout(300)
    got = pg.evaluate("""() => { const g = document.querySelector('#board-layer g'), box = e => { const r = e.getBoundingClientRect(); return [r.width, r.height, r.left, r.top]; };
                                 return {look: g.dataset.look || '', ring: [...g.querySelectorAll('.board-ring')].map(box), dot: [...g.querySelectorAll('circle.board-dot')].map(box),
                                         pulse: g.querySelectorAll('.board-pulse').length, all: box(g)}; }""")
    shot = pg.screenshot(clip=CLIP)   # in memory only: no file is kept
    pg.evaluate('abhyasaBoard.stop()'); pg.wait_for_timeout(100)
    got['ink'] = _ink(shot, pg.screenshot(clip=CLIP))
    return got

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_point_looks_are_weaker_than_a_circle(mk):
    "Each point look draws its own parts at its own size, and puts less ink on the page than a circle on the same target."
    import socket, threading, time, uvicorn
    from playwright.sync_api import sync_playwright
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(mk().app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page(viewport=dict(width=1000, height=700))
                pg.goto(f'http://127.0.0.1:{port}/'); pg.wait_for_function('window.abhyasaBoard')
                pg.evaluate(TARGET)
                circle = _draw(pg, 'circle')
                assert len(circle['ring']) == 1 and circle['ink'] > 0
                cw, ch = circle['ring'][0][:2]
                tick, dot, ring = (_draw(pg, 'point', k) for k in ('tick', 'dot', 'ring'))
                # tick: a short arrow outside the target, with no ring and no dot
                assert (tick['look'], tick['ring'], tick['dot']) == ('tick', [], [])
                w, h, x, y = tick['all']
                assert w < 50 and h < 50 and not (420 < x < 510 and 260 < y < 288 and 420 < x + w < 510 and 260 < y + h < 288)
                # dot: one small dot under the target, and no ring
                assert (dot['look'], dot['ring'], len(dot['dot'])) == ('dot', [], 1)
                dw, dh, dx, dy = dot['dot'][0]
                assert dw <= 8 and dh <= 8 and dy >= 288
                # ring: a ring that is smaller than the ring of a circle
                assert ring['look'] == 'ring' and len(ring['ring']) == 1 and ring['ring'][0][0] < cw and ring['ring'][0][1] < ch
                for k, m in dict(tick=tick, dot=dot, ring=ring).items(): assert 0 < m['ink'] < circle['ink'] * .6, (k, m['ink'], circle['ink'])
                assert ring['ink'] > tick['ink'] > dot['ink']
                # no option and an unknown look give the default, tick
                assert _draw(pg, 'point')['look'] == 'tick' and _draw(pg, 'point', 'arrow')['look'] == 'tick'
            finally: b.close()
    finally:
        srv.should_exit = True; th.join(5)

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_a_dot_pulses_once_and_not_with_reduced_motion(mk):
    "A live dot sends out one pulse that goes. With reduced motion, the dot shows and there is no pulse."
    import socket, threading, time, uvicorn
    from playwright.sync_api import sync_playwright
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(mk().app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    play = "() => abhyasaBoard.play({steps: [{say: 'Look here now.', strokes: [{op: 'point', at: 't'}]}], tier: 'tutor', sources: []}, {quiet: true, auto: false, point: 'dot'})"
    seen = "() => { const p = document.querySelector('.board-pulse'); return p && +getComputedStyle(p).opacity > 0.1; }"
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page(viewport=dict(width=1000, height=700))
                pg.goto(f'http://127.0.0.1:{port}/'); pg.wait_for_function('window.abhyasaBoard')
                pg.evaluate(TARGET); pg.evaluate(play)
                pg.wait_for_function(seen, timeout=5000)   # the pulse shows
                pg.wait_for_function('abhyasaBoard.state.done', timeout=5000); pg.wait_for_timeout(200)
                assert pg.evaluate("+getComputedStyle(document.querySelector('.board-pulse')).opacity") == 0   # and goes after one time
                pg.evaluate('abhyasaBoard.stop()'); pg.emulate_media(reduced_motion='reduce'); pg.evaluate(play)
                pg.wait_for_function("document.querySelector('circle.board-dot')"); pg.wait_for_timeout(400)
                assert pg.evaluate("[document.querySelectorAll('.board-pulse').length, +document.querySelector('circle.board-dot').getAttribute('r')]") == [0, 3.2]
            finally: b.close()
    finally:
        srv.should_exit = True; th.join(5)
