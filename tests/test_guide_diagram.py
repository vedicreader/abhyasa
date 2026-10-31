"The diagram card of the board, and the sketch on a figure only, in a headless browser."
import socket, threading, time, pytest
from test_board_js import _chromium

pytestmark = pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")

def diagram(texts, edges, layout, at='passage'):
    "A diagram line with a node for each of `texts` (ids n0, n1, ...) and an edge for each (from, to, words) of `edges`."
    es = [{'from': f'n{f}', 'to': f'n{t}', **({'text': x[0]} if x else {})} for f, t, *x in edges]
    return dict(op='diagram', nodes=[dict(id=f'n{k}', text=s) for k, s in enumerate(texts)], edges=es, layout=layout, at=at)

# The two diagrams that the owner saw broken: a cycle of 3 with words on each arrow, and a row of 4 with long arrows.
CYCLE = diagram(['Draw curve using a, b, c', 'Measure error against data points', 'Adjust a, b, c to reduce error'],
                [(0, 1, 'compare with data'), (1, 2, 'find a downhill direction'), (2, 0, 'try the updated curve')], 'cycle')
ROW = diagram(['Read the question', 'Find the formula', 'Put in the numbers', 'Check the units'],
              [(0, 1, 'pick one'), (1, 2, 'fill in'), (2, 3, 'then check')], 'row')
QUAD = diagram(['y = a·x² + b·x + c', 'a·x²: the bend', 'b·x: the slope', 'c: the start height'],
               [(0, 1, 'has'), (0, 2, 'has'), (0, 3, 'has'), (1, 2, 'adds to')], 'row')
# A ring of 4 with both cross lines: the two cross lines cross in the middle, so no clean ring exists.
TANGLE = diagram(['one', 'two', 'three', 'four'], [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)], 'cycle')
PASSAGE = ('Each input vector is projected into a query, a key and a value. A query is compared with keys to decide how much of '
           'each value to read. The scores go through a softmax, so the weights add to one.')

@pytest.fixture
def browser(mk):
    "A function that opens one headless page of the app at a viewport size, with a passage in the main column; one browser for the test."
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
                def page(w=1600, h=900, reduced=False):
                    pg = b.new_page(viewport=dict(width=w, height=h), reduced_motion='reduce' if reduced else 'no-preference')
                    pg.goto(f'http://127.0.0.1:{port}/'); pg.wait_for_function('window.abhyasaBoard')
                    pg.evaluate("""t => { const p = document.createElement('p'); p.id = 'passage'; p.dataset.guideId = 'passage'; p.textContent = t;
                                          document.querySelector('main').prepend(p); }""", PASSAGE)
                    return pg
                yield page
            finally: b.close()
    finally:
        srv.should_exit = True; th.join(5)

PLAY = "ss => abhyasaBoard.play({steps: ss, tier: 'tutor', sources: []}, {fast: true})"

def show(pg, *strokes):
    "Play one step with `strokes` at once, and wait until each mark shows in full."
    pg.evaluate(PLAY, [dict(say='The parts and how they connect.', strokes=list(strokes))])
    pg.wait_for_function('abhyasaBoard.state && abhyasaBoard.state.done')

# What a test reads from the card: each node and each pill that shows (card pixels before the scale), whether a node cuts its
# text, the ends of each edge, the card in window pixels, the top bar, and each element of the page with text that the card
# covers now or that can move under it (the side card is fixed, so a page that scrolls can bring text under it).
LOOK = """() => {
  const card = document.querySelector('.board-diagram');
  if (!card || getComputedStyle(card).display === 'none') return null;
  const own = e => ({x: e.offsetLeft, y: e.offsetTop, w: e.offsetWidth, h: e.offsetHeight});
  const c = card.getBoundingClientRect(), nav = document.querySelector('body > nav').getBoundingClientRect(), covered = [];
  for (const e of document.body.querySelectorAll('*')) {
    if (e.closest('#board-host, #guide-strip, .board-hl, #guide-form, body > nav')) continue;
    const text = /^(img|svg|canvas|input|textarea|select|button)$/i.test(e.tagName) || [...e.childNodes].some(n => n.nodeType === 3 && n.data.trim());
    const r = e.getBoundingClientRect();
    if (text && r.width >= 1 && r.height >= 1 && r.left < c.right && c.left < r.right) covered.push(e.tagName + ' ' + e.textContent.slice(0, 40));
  }
  const nodes = [...card.querySelectorAll('.board-node')];
  return {dock: card.dataset.dock, kind: card.dataset.kind, card: {x: c.left, y: c.top, w: c.width, h: c.height, right: innerWidth - c.right},
          navBottom: nav.bottom, ids: nodes.map(e => e.dataset.id), nodes: nodes.map(own),
          cut: nodes.filter(e => e.scrollWidth > e.clientWidth || e.scrollHeight > e.clientHeight).map(e => e.textContent),
          tags: [...card.querySelectorAll('.board-edge-text:not([hidden])')].map(own),
          edges: [...card.querySelectorAll('path[data-ends]')].map(p => ({from: p.dataset.from, to: p.dataset.to, ends: p.dataset.ends.split(' ').map(Number)})),
          covered};
}"""

def overlap(a, b, p=0): return a['x'] < b['x'] + b['w'] + p and b['x'] < a['x'] + a['w'] + p and a['y'] < b['y'] + b['h'] + p and b['y'] < a['y'] + a['h'] + p

def to_border(b, x, y):
    "How far the point (x, y) is from the border of box `b`, in px."
    dx, dy = max(b['x'] - x, 0, x - b['x'] - b['w']), max(b['y'] - y, 0, y - b['y'] - b['h'])
    if dx or dy: return (dx * dx + dy * dy) ** .5
    return min(x - b['x'], b['x'] + b['w'] - x, y - b['y'], b['y'] + b['h'] - y)

def check_clean(got, n_tags=None):
    "No node cuts its text, no pill covers a node or another pill, and each edge starts and ends on the border of its nodes."
    assert got['cut'] == [], got['cut']
    ns, ts = got['nodes'], got['tags']
    assert not [(i, j) for i in range(len(ns)) for j in range(i + 1, len(ns)) if overlap(ns[i], ns[j], 8)], ns
    assert not [(t, n) for t in ts for n in ns if overlap(t, n)], (ts, ns)
    assert not [(i, j) for i in range(len(ts)) for j in range(i + 1, len(ts)) if overlap(ts[i], ts[j])], ts
    box = dict(zip(got['ids'], ns))
    for e in got['edges']:
        x0, y0, x1, y1 = e['ends']
        assert to_border(box[e['from']], x0, y0) <= 4 and to_border(box[e['to']], x1, y1) <= 4, e
    if n_tags is not None: assert len(ts) == n_tags, ts

def test_a_cycle_of_three_is_a_clean_ring_at_the_top_right(browser):
    """The owner's cycle: a ring with each node in full, the words of each arrow on no node and no other words, each arrow from
    border to border. The card is at the top right under the top bar, and no page text is under it or can move under it."""
    pg = browser()
    show(pg, dict(op='box', at='passage'), CYCLE)
    got = pg.evaluate(LOOK)
    assert got and got['kind'] == 'ring' and got['dock'] == 'side', got
    check_clean(got)
    assert len(got['edges']) == 3 and len(got['tags']) >= 2, got['tags']
    c = got['card']
    assert c['right'] <= 40 and got['navBottom'] <= c['y'] <= got['navBottom'] + 40, c
    assert got['covered'] == [], got['covered']

def test_a_row_of_four_is_clean_with_its_words(browser):
    "A process of 4 steps: 4 nodes in full, 3 arrows from border to border, all 3 pills shown, and the card at the top right."
    pg = browser()
    show(pg, ROW)
    got = pg.evaluate(LOOK)
    assert got and got['dock'] == 'side' and got['kind'] in ('right', 'down'), got
    check_clean(got, n_tags=3)
    assert len(got['edges']) == 3 and got['covered'] == [] and got['card']['right'] <= 40

def test_the_quadratic_row_is_clean_or_not_drawn(browser):
    "The owner's row of the parts of a formula, with an arrow past the nodes between: it shows clean (layers, no crossing), or not at all."
    pg = browser()
    show(pg, QUAD)
    got = pg.evaluate(LOOK)
    if got: check_clean(got); assert got['covered'] == []

def test_a_diagram_that_cannot_be_clean_is_not_drawn(browser):
    "A ring with two crossing lines is not drawn, the other mark of the step shows, and the strip does not say that the page changed."
    pg = browser()
    show(pg, dict(op='box', at='passage'), TANGLE)
    assert pg.evaluate(LOOK) is None
    assert pg.evaluate("document.querySelector('.board-glow').style.display") != 'none'
    assert not pg.evaluate("!!document.querySelector('#guide-strip .board-note')")

def test_on_a_narrow_window_the_card_stands_over_the_strip(browser):
    "With no room beside the text, the card has the full width of the window just over the strip, and is still clean. The strip keeps only its words and controls."
    pg = browser(700, 800)
    show(pg, ROW)
    got = pg.evaluate(LOOK)
    assert got and got['dock'] == 'wide', got
    check_clean(got)
    strip = pg.evaluate("document.getElementById('guide-strip').getBoundingClientRect().top")
    c = got['card']
    assert c['y'] + c['h'] <= strip and c['x'] <= 20 and c['right'] <= 20, (c, strip)
    assert pg.evaluate("document.querySelectorAll('#guide-strip .board-diagram').length") == 0

def test_reduced_motion_shows_the_diagram_at_once(browser):
    "With reduced motion, a board that is not fast shows each node of its diagram in full soon after it starts: no pop and no pen."
    pg = browser(reduced=True)
    pg.evaluate("ss => abhyasaBoard.play({steps: ss, tier: 'tutor', sources: []}, {quiet: true})", [dict(say='The parts.', strokes=[ROW])])
    pg.wait_for_selector('.board-diagram .board-node')
    pg.wait_for_timeout(400)
    assert pg.evaluate("[...document.querySelectorAll('.board-diagram .board-node')].map(e => getComputedStyle(e).opacity)") == ['1'] * 4

def test_a_sketch_on_a_part_that_is_not_a_figure_is_dropped(browser):
    "A sketch on the passage draws nothing. The same sketch on a figure draws its stroke."
    pg = browser()
    pg.evaluate("""() => { const i = new Image(200, 120); i.dataset.guideId = 'figure';
                           i.src = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="120"><rect width="200" height="120" fill="%23eee"/></svg>');
                           const f = document.createElement('figure'); f.append(i); document.querySelector('main').append(f); }""")
    pts = [[0, 100], [500, 500], [1000, 900]]
    show(pg, dict(op='sketch', at='passage', pts=pts))
    assert pg.evaluate("document.querySelectorAll('#board-layer g[data-op=sketch]').length") == 0
    show(pg, dict(op='sketch', at='figure', pts=pts))
    assert pg.evaluate("[...document.querySelectorAll('#board-layer g[data-op=sketch] path')].some(p => (p.getAttribute('d') || '').length > 20)")

def test_a_card_never_goes_under_the_strip(browser):
    """A page with text across the whole width: there is no side place, so the card stands over the strip (the strip is over the
    page), never under it."""
    pg = browser(1440, 650)
    pg.evaluate("""() => { const b = document.createElement('div'); b.textContent = 'Text across the page. '.repeat(60);
                          document.querySelector('main').style.maxWidth = 'none'; document.querySelector('main').append(b); }""")
    show(pg, diagram(['input', 'model', 'output'], [(0, 1), (1, 2)], 'row'))
    got = pg.evaluate(LOOK)
    strip = pg.evaluate("document.getElementById('guide-strip').getBoundingClientRect().top")
    assert got and got['dock'] == 'wide' and got['card']['y'] + got['card']['h'] <= strip, (got, strip)
