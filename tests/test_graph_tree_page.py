"""The Tree in a browser, on a temporary vault of fifteen concepts in two subjects: it is tidy, a branch closes and opens, the keys move along
it, the list says the same, and the layout stays after a reload. One scenario runs on Playwright's bundled Chromium, or on `$FASTCDP_CHROME`
with fastcdp (CLAUDE.md): headless, a new temporary profile, a free port. Set ABHYASA_TREE_SHOTS to a folder to keep the screenshots."""
import asyncio, base64, os, shutil, socket, tempfile, threading, time, pytest
from pathlib import Path

def _chromium():
    "True when Playwright's bundled Chromium is installed."
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p: return Path(p.chromium.executable_path).exists()
    except Exception: return False

def _cft():
    "True when fastcdp and the test browser in `$FASTCDP_CHROME` are there."
    try: import fastcdp.core   # noqa: F401
    except Exception: return False
    p = os.environ.get('FASTCDP_CHROME'); return bool(p) and Path(p).exists()

H = 1 / 24   # an hour, in days
# name, subject, prereqs (names), depth, times seen, next review in days (None: not seen)
DEMO = [('Temperature', 'thermodynamics', [], 5, 6, 10), ('Heat', 'thermodynamics', ['Temperature'], 4, 4, -H),
        ('Work', 'thermodynamics', ['Temperature'], 3, 2, 3), ('First law', 'thermodynamics', ['Heat', 'Work'], 2, 2, 2),
        ('Internal energy', 'thermodynamics', ['First law'], 1, 1, 1), ('Entropy', 'thermodynamics', ['First law'], 1, 1, -2 * H),
        ('Second law', 'thermodynamics', ['Entropy', 'First law', 'Temperature'], 0, 0, None), ('Heat engine', 'thermodynamics', ['Second law'], 0, 0, None),
        ('Rasi', 'jyotisha', [], 5, 5, 20), ('Graha', 'jyotisha', [], 4, 3, -1), ('Bhava', 'jyotisha', ['Rasi', 'Graha'], 3, 2, 4),
        ('Nakshatra', 'jyotisha', ['Rasi'], 2, 1, 5), ('Varga', 'jyotisha', ['Bhava'], 1, 1, 1), ('Navamsa', 'jyotisha', ['Varga', 'Nakshatra'], 0, 0, None),
        ('Dasha', 'jyotisha', ['Nakshatra', 'Graha'], 0, 0, None)]
W, HT = 1440, 860

@pytest.fixture
def lr():
    "The demo vault, in a temporary folder."
    from abhyasa.learner import temp_learning, set_val
    set_val('look.keys_float', False)   # the floating Keys panel stays shut, so it does not cover the roots (the tests have their own settings folder)
    l, slug, now = temp_learning(), {}, time.time()
    for name, subject, pre, floor, seen, due in DEMO:
        slug[name] = l.put(name, f'The idea of {name.lower()}.', subject, prereqs=[slug[p] for p in pre]).slug
        if seen: l.update(slug[name], floor=floor, seen=seen, last=now - 86400, stability=3., due=now + due * 86400)
    return l

class _Served:
    "The app on a free port of this computer, in a thread, for one test."
    def __init__(self, app):
        import uvicorn
        with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
        self.srv = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error'))
        self.th = threading.Thread(target=self.srv.run, daemon=True); self.th.start()
        while not self.srv.started: time.sleep(.05)
        self.base = f'http://127.0.0.1:{port}'
    def stop(self): self.srv.should_exit = True; self.th.join(5)

# The two drivers have the same small surface. Real mouse and key events for the canvas and the keys; a lever is set as a person
# would with a click (`el.click()` sends the same input event), and the find box with an input event.
class _PW:
    def __init__(self, pg): self.pg = pg
    def goto(self, u): self.pg.goto(u)
    def ev(self, js): return self.pg.evaluate(js)
    def move(self, x, y): self.pg.mouse.move(x, y)
    def click_at(self, x, y): self.pg.mouse.click(x, y)
    def press(self, k): self.pg.keyboard.press(k)
    def shot(self, path): self.pg.locator('#graph').screenshot(path=str(path))

class _CFT:
    def __init__(self, loop, p): self.loop, self.p = loop, p
    def _r(self, c): return self.loop.run_until_complete(c)
    def goto(self, u): self._r(self.p.goto(u))
    def ev(self, js):
        import json
        r = self._r(self.p.eval(f'JSON.stringify(({js})())'))   # once: a value that JSON keeps, as Playwright gives
        return None if r is None else json.loads(r)
    def move(self, x, y): self._r(self.p.input.dispatchMouseEvent(type='mouseMoved', x=x, y=y))
    def click_at(self, x, y):
        self.move(x, y)
        for t in ('mousePressed', 'mouseReleased'): self._r(self.p.input.dispatchMouseEvent(type=t, x=x, y=y, button='left', clickCount=1))
    def press(self, k): self._r(self.p.press(' ' if k == 'Space' else k))
    def shot(self, path):   # the clip of captureScreenshot is in page units, so the scroll is added
        r = self.ev("() => { const b = document.querySelector('#graph').getBoundingClientRect(); return {x: b.x + scrollX, y: b.y + scrollY, width: b.width, height: b.height} }")
        Path(path).write_bytes(base64.b64decode(self._r(self.p.page.captureScreenshot(format='png', clip={**r, 'scale': 1}))))

def _wait(d, js, timeout=10):
    "Wait until the function `js` gives a true value in the page; give that value."
    end = time.time() + timeout
    while True:
        v = d.ev(js)
        if v: return v
        if time.time() > end: raise AssertionError(f'timed out: {js}; the page: {d.ev(STATE)}')
        time.sleep(.05)

def _shot(d, tmp_path, name):
    "A screenshot of the graph in the test folder, and in ABHYASA_TREE_SHOTS when it is set."
    p = tmp_path/name; d.shot(p)
    if (o := os.environ.get('ABHYASA_TREE_SHOTS')): Path(o).mkdir(parents=True, exist_ok=True); shutil.copy(p, Path(o)/name)
    return p

STATE = ("() => ({errors: window.__errs || [], clicks: window.__clicks || [], toggles: window.abhyasaGraph?.tree?.toggles, graph: !!window.abhyasaGraph, mode: window.abhyasaGraph?.mode, moving: window.abhyasaGraph?.moving, "
         "tree: !!window.abhyasaGraph?.tree, treeScript: !!window.abhyasaTree})")
SETTLED = "() => window.abhyasaGraph && abhyasaGraph.mode === 'tree' && !abhyasaGraph.moving && !!abhyasaGraph.tree"
TREE = '() => abhyasaGraph.tree'
FOCUS = "() => { document.getElementById('graph').focus({preventScroll: true}); return true }"   # as the page does: the keys work, and the page does not scroll
CANVAS = "() => { const b = document.querySelector('#graph canvas').getBoundingClientRect(); return [b.x, b.y] }"
click = lambda sel: f"() => {{ document.querySelector({sel!r}).click(); return true }}"
fill = lambda sel, t: f"() => {{ const e = document.querySelector({sel!r}); e.value = {t!r}; e.dispatchEvent(new Event('input', {{bubbles: true}})); return true }}"
text = lambda sel: f"() => document.querySelector({sel!r}).innerText"

def _mark(d, key):
    "Click the open or closed mark after the name of `key`, with the mouse."
    time.sleep(.15)   # a key that moved the view draws the marks again on the next frame
    cx, cy = d.ev(CANVAS); x0, y0, x1, y1 = dict(d.ev(TREE)['toggles'])[key]
    d.click_at(cx + (x0 + x1) / 2, cy + (y0 + y1) / 2)

ERRS = ("() => { window.__errs = []; window.__clicks = []; addEventListener('error', e => __errs.push(String(e.message))); addEventListener('unhandledrejection', e => __errs.push(String(e.reason))); "
        "addEventListener('click', e => __clicks.push([e.target.tagName + '.' + e.target.className, Math.round(e.clientX), Math.round(e.clientY)]), true); return true }")

def _scenario(d, base, tmp_path):
    d.goto(base + '/library/graph'); d.ev(ERRS); _wait(d, '() => !!window.abhyasaGraph')
    d.ev(click('label.mode:has(input[value=tree])'))   # the Tree lever
    _wait(d, SETTLED); time.sleep(.3)   # the fit, with no glide for reduced motion
    g = d.ev(TREE)
    assert g['roots'] == ['s:jyotisha', 's:thermodynamics'] and len(g['rows']) == 17 and g['cross'] == 6, g
    assert sorted(g['labels']) == sorted(n[0] for n in DEMO_IDS), g['labels']   # each name shows
    pts = d.ev('() => abhyasaGraph.vis.map(n => [abhyasaGraph.t.applyX(n.x), abhyasaGraph.t.applyY(n.y)])')
    near = min(((a[0] - c[0]) ** 2 + (a[1] - c[1]) ** 2) ** .5 for i, a in enumerate(pts) for c in pts[i + 1:])
    assert near >= 18, near   # no two nodes touch
    cw, ch = d.ev("() => { const c = document.querySelector('#graph canvas'); return [c.clientWidth, c.clientHeight] }")
    assert all(0 <= x <= cw and 0 <= y <= ch for x, y in pts), (pts, cw, ch)   # the fit shows the whole tree
    assert d.ev(text('#levers .legend')).split() == ['not', 'started', 'under', 'way', 'mastered', 'review', 'due']
    assert d.ev("() => !document.querySelector('.tree-only').hidden && document.querySelector('[name=colorBy]').disabled")
    _shot(d, tmp_path, 'tree.png')

    # hover a concept: its status, depth and next review
    cx, cy = d.ev(CANVAS)
    hx, hy = d.ev("() => { const n = abhyasaGraph.nodes.find(n => n.id === 'heat'); return [abhyasaGraph.t.applyX(n.x), abhyasaGraph.t.applyY(n.y)] }")
    d.move(cx + hx, cy + hy)
    assert d.ev(text('#graph .tip')).split('\n')[:2] == ['Heat', 'review due · depth apply · review due now']
    d.move(cx + 3, cy + 3)

    # the keys: the first root, its first child, the next sibling, back to the parent, the next root
    d.ev(FOCUS)
    seen = []
    for k in ('ArrowDown', 'ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowDown'): d.press(k); seen.append(d.ev(TREE)['cursor'])
    assert seen == ['s:jyotisha', 'graha', 'rasi', 's:jyotisha', 's:thermodynamics'], seen
    assert d.ev(text('#focus-name')) == 'thermodynamics: 8 concepts: 2 not started, 2 under way, 2 mastered, 2 review due.'

    # close First law with a click on its mark, and Graha with Space
    _mark(d, 'first-law'); _wait(d, "() => abhyasaGraph.tree.collapsed.includes('first-law')")
    for k in ('ArrowLeft', 'ArrowLeft', 'ArrowLeft', 'ArrowUp', 'ArrowRight'): d.press(k)   # Heat, Temperature, thermodynamics, jyotisha, Graha
    d.press('Space')
    g = d.ev(TREE)
    assert sorted(g['collapsed']) == ['first-law', 'graha'] and g['cursor'] == 'graha', g
    assert not {'entropy', 'second-law', 'internal-energy', 'heat-engine', 'bhava', 'varga', 'navamsa'} & set(g['rows']) and 'dasha' in g['rows'], g['rows']   # Dasha sits under Nakshatra
    assert 'Closed branch of 3' in d.ev(text('#focus-name'))
    _wait(d, SETTLED); time.sleep(.3)
    _shot(d, tmp_path, 'tree-collapsed.png')
    d.press('Space'); _wait(d, "() => !abhyasaGraph.tree.collapsed.includes('graha')")   # Space opens it again
    time.sleep(.2)   # the next frame draws the marks in their new places
    _mark(d, 'first-law'); _wait(d, '() => !abhyasaGraph.tree.collapsed.length')

    # the list: the same tree in words; the find keeps the branch above a match
    d.ev(click('[name=asList]')); _wait(d, "() => !document.querySelector('#graph .outline').hidden")
    assert d.ev("() => getComputedStyle(document.querySelector('#graph canvas')).visibility") == 'hidden'
    txt = d.ev(text('#graph .outline'))
    assert all(s in txt for s in ('Heat review due', 'Temperature mastered', 'Second law not started', 'First law under way')), txt
    assert d.ev("() => [document.querySelectorAll('#graph .outline details').length, document.querySelectorAll('#graph .outline a').length]") == [12, 15]   # 2 subjects and 10 concepts with a concept under them
    _shot(d, tmp_path, 'tree-list.png')
    d.ev("() => { [...document.querySelectorAll('#graph .outline summary')].find(s => s.querySelector('a')?.textContent === 'Graha').click(); return true }")   # closed in the list, closed on the canvas
    _wait(d, "() => abhyasaGraph.tree.collapsed.includes('graha')")
    d.ev(fill('#levers [name=q]', 'navam'))   # the Find of the graph; the top bar has a search box with the same name
    assert d.ev("() => [...document.querySelectorAll('#graph .outline a')].map(a => a.textContent)") == ['Graha', 'Bhava', 'Varga', 'Navamsa']
    assert d.ev(TREE)['collapsed'] == ['graha']   # the find opens the branch but does not save that
    d.ev(fill('#levers [name=q]', '')); time.sleep(.4)   # the levers save 300 ms after the last change

    # a reload keeps the Tree, the list and the closed branch
    d.goto(base + '/library/graph'); _wait(d, SETTLED)
    assert d.ev(TREE)['collapsed'] == ['graha'] and d.ev("() => !document.querySelector('#graph .outline').hidden && document.querySelector('[name=asList]').checked")
    d.ev(click('[name=asList]')); _wait(d, "() => document.querySelector('#graph .outline').hidden")

    # Enter opens the concept of the keys, as a click does
    d.ev(FOCUS)
    for k in ('ArrowDown', 'ArrowDown', 'ArrowRight'): d.press(k)   # jyotisha, thermodynamics, Temperature
    assert d.ev(TREE)['cursor'] == 'temperature'
    d.press('Enter'); _wait(d, "() => location.pathname === '/c/temperature'")

DEMO_IDS = [(n.lower().replace(' ', '-'),) for n, *_ in DEMO]

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_the_tree_in_playwright_chromium(mk, tmp_path):
    "The scenario on Playwright's bundled Chromium, with reduced motion."
    from playwright.sync_api import sync_playwright
    s = _Served(mk().app)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_context(viewport=dict(width=W, height=HT), reduced_motion='reduce').new_page()
                errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
                _scenario(_PW(pg), s.base, tmp_path)
                assert errs == [], errs
            finally: b.close()
    finally: s.stop()

@pytest.mark.skipif(not _cft(), reason='fastcdp or the test browser in $FASTCDP_CHROME is not there')
def test_the_tree_in_chrome_for_testing(mk, tmp_path):
    "The scenario on `$FASTCDP_CHROME` with fastcdp, headless, on a new temporary profile, with reduced motion."
    from fastcdp.core import CDP
    s, loop = _Served(mk().app), asyncio.new_event_loop()
    try:
        c = loop.run_until_complete(CDP.launch(user_data_dir=tempfile.mkdtemp(prefix='abhyasa-cft-'), headless=True, reuse=False))
        try:
            p = loop.run_until_complete(c.new_page())
            loop.run_until_complete(p.emulation.setDeviceMetricsOverride(width=W, height=HT, deviceScaleFactor=1, mobile=False))
            loop.run_until_complete(p.emulation.setEmulatedMedia(features=[dict(name='prefers-reduced-motion', value='reduce')]))
            _scenario(_CFT(loop, p), s.base, tmp_path)
        finally: loop.run_until_complete(c.quit())
    finally: loop.close(); s.stop()
