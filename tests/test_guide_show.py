"Show while you talk: the pointer gestures of guide.js, and the focus that a question sends with them."
import json, socket, threading, time, pytest
from pathlib import Path
from test_board_js import _chromium

PATHS = json.loads((Path(__file__).parent/'data/gesture_paths.json').read_text())
BOX = dict(left=200, top=150, width=300, height=150)   # the #passage element, in page pixels

def near(a, b, tol): return all(abs(x - y) <= tol for x, y in zip(a, b))

@pytest.fixture
def page(mk):
    "One headless page of the app, with a #passage at BOX, and the ask route answered here: each body that it gets goes in `page.asked`."
    import uvicorn
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
                pg.asked = []
                def answer(route):
                    pg.asked.append(json.loads(route.request.post_data))
                    route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body='data: {"error": "A test."}\n\n')
                pg.route('**/guide/ask', answer)
                pg.goto(f'http://127.0.0.1:{port}/'); pg.wait_for_function('window.abhyasaGuide && window.abhyasaBoard')
                pg.evaluate("""b => { const m = document.querySelector('main') || document.body, p = document.createElement('section');
                                      p.id = 'passage'; p.textContent = 'The forward process adds noise in small steps.';
                                      Object.assign(p.style, {position: 'fixed', left: b.left + 'px', top: b.top + 'px', width: b.width + 'px', height: b.height + 'px', zIndex: 5, background: '#fff'});
                                      m.append(p); }""", BOX)
                yield pg
            finally: b.close()
    finally:
        srv.should_exit = True; th.join(5)

pytestmark = pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")

def test_gestures_match_the_shared_paths(page):
    "Each sample path gives the gestures in the shared file, the latest first: a loop is a circle, a still pointer after a move is a point, jitter and swipes give nothing."
    for name, p in PATHS['paths'].items():
        got = page.evaluate('([pts, end]) => abhyasaGuide.gestures(pts, end)', [p['pts'], p['end']])
        assert [g['kind'] for g in got] == [w['kind'] for w in p['want']], (name, got)
        for g, w in zip(got, p['want']): assert near(g['box'], w['box'], PATHS['tolerance']), (name, g, w)

def ask_after(page, moves, still=0):
    "Open the box, move the mouse along `moves` (page pixels, 35 ms apart), wait `still` ms, type a question and send it. The body that the ask route got."
    n = len(page.asked)
    page.mouse.move(10, 690)
    page.evaluate('abhyasaGuide.open()')
    for x, y in moves: page.mouse.move(x, y); page.wait_for_timeout(35)
    page.wait_for_timeout(still)
    page.fill('#guide-box', 'what is this')
    page.press('#guide-box', 'Enter')
    page.wait_for_function(f'document.querySelector("#guide-form").hidden')
    for _ in range(100):
        if len(page.asked) > n: break
        page.wait_for_timeout(50)
    return page.asked[-1]

def test_what_the_learner_shows_goes_with_the_question(page):
    """A loop drawn round the passage sends a circle with the passage anchor and a box from 0 to 1000 of it. A move onto the passage
    and a rest of 600 ms sends a point on it. A hand that rests on the mouse, with a small shake, sends no focus."""
    import math
    cx, cy = BOX['left'] + 150, BOX['top'] + 75
    loop = [(cx + 90 * math.cos(math.radians(a)), cy + 50 * math.sin(math.radians(a))) for a in range(0, 380, 12)]
    body = ask_after(page, loop)
    f = body['ctx']['focus']
    assert f[0]['kind'] == 'circle' and f[0]['anchors'][0] == 'passage', f
    assert near(f[0]['box'], [200, 167, 800, 833], 40), f
    assert body['said'] == 'what is this' and not page.evaluate("document.getElementById('board-trail')")   # nothing of the path stays
    x, y = BOX['left'] + 60, BOX['top'] + 40
    body = ask_after(page, [(x - 120 + 12 * k, y) for k in range(11)], still=600)
    f = body['ctx']['focus']
    assert [(g['kind'], g['anchors'][0]) for g in f] == [('point', 'passage')], f
    x, y = BOX['left'] + 100, BOX['top'] + 60
    body = ask_after(page, [(x + (k % 3) - 1, y + (k % 2)) for k in range(30)], still=500)
    assert 'focus' not in body['ctx'], body['ctx'].get('focus')
