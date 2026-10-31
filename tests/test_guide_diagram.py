"The diagram card of the board, and the sketch on a figure only, in a headless browser."
import socket, threading, time, pytest
from test_board_js import _chromium

pytestmark = pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")

TEXTS = ['query: what I look for', 'key: what each word offers', 'value: what each word gives', 'score', 'softmax: weights that add to one', 'the mix']
EDGES = dict(row=[('n0', 'n1', 'compare'), ('n1', 'n3', 'gives'), ('n3', 'n4'), ('n4', 'n5', 'mix the values'), ('n0', 'n5', 'reads')],
             tree=[('n0', 'n1', 'compare'), ('n0', 'n2'), ('n1', 'n3', 'gives'), ('n1', 'n4'), ('n2', 'n5', 'mix')],
             cycle=[('n0', 'n1', 'next'), ('n1', 'n2'), ('n2', 'n3'), ('n3', 'n4'), ('n4', 'n5'), ('n5', 'n0', 'back')])
PASSAGE = ('Each input vector is projected into a query, a key and a value. A query is compared with keys to decide how much of '
           'each value to read. The scores go through a softmax, so the weights add to one.')

def diagram(layout, at='passage'):
    edges = [{'from': f, 'to': t, **({'text': x[0]} if x else {})} for f, t, *x in EDGES[layout]]
    return dict(op='diagram', nodes=[dict(id=f'n{k}', text=t) for k, t in enumerate(TEXTS)], edges=edges, layout=layout, at=at)

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

# The card, its nodes, and each element of the page with text or a control under the card, in page pixels.
LOOK = """() => {
  const card = document.querySelector('.board-diagram'), box = e => { const r = e.getBoundingClientRect(); return {x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height}; };
  const hit = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
  const c = box(card), covered = [];
  for (const e of document.body.querySelectorAll('*')) {
    if (e.closest('#board-host, #guide-strip, .board-hl, #guide-form')) continue;
    const own = /^(img|svg|canvas|input|textarea|select|button)$/i.test(e.tagName) || [...e.childNodes].some(n => n.nodeType === 3 && n.data.trim());
    const r = box(e);
    if (own && r.w >= 1 && r.h >= 1 && hit(c, r)) covered.push(e.tagName + ' ' + e.textContent.slice(0, 40));
  }
  return {card: c, nodes: [...card.querySelectorAll('.board-node')].map(box), texts: [...card.querySelectorAll('.board-node')].map(e => e.textContent),
          heads: card.querySelectorAll('path').length, where: card.parentElement.id || card.parentElement.className, covered,
          afterSay: !!card.previousElementSibling && card.previousElementSibling.classList.contains('board-say')};
}"""

def overlap(a, b): return a['x'] < b['x'] + b['w'] and b['x'] < a['x'] + a['w'] and a['y'] < b['y'] + b['h'] and b['y'] < a['y'] + a['h']

def test_a_diagram_card_draws_each_node_beside_the_text(browser):
    """On a wide page, each layout draws all 6 nodes in a card in the board layer: no two nodes overlap, each node is inside the card,
    each edge has its stroke and its head, and the card covers no element of the page with text or a control."""
    pg = browser()
    for layout in ('row', 'tree', 'cycle'):
        pg.evaluate(PLAY, [dict(say='The parts and how they connect.', strokes=[dict(op='box', at='passage'), diagram(layout)])])
        pg.wait_for_function('abhyasaBoard.state && abhyasaBoard.state.done')
        got = pg.evaluate(LOOK)
        ns = got['nodes']
        assert got['texts'] == TEXTS and got['where'] == 'board-host', (layout, got['where'])
        assert not [(i, j) for i in range(6) for j in range(i + 1, 6) if overlap(ns[i], ns[j])], (layout, ns)
        c = got['card']
        assert all(c['x'] <= n['x'] and n['x'] + n['w'] <= c['x'] + c['w'] + .5 and c['y'] <= n['y'] and n['y'] + n['h'] <= c['y'] + c['h'] + .5 for n in ns), layout
        assert got['heads'] == 2 * len(EDGES[layout]) and got['covered'] == [], (layout, got['covered'])
        pg.evaluate('abhyasaBoard.stop()')

def test_on_a_narrow_page_the_card_goes_under_the_step_line(browser):
    "With no room beside the text, the card is in the strip, just under the spoken line, and its nodes still do not overlap."
    pg = browser(700, 800)
    pg.evaluate(PLAY, [dict(say='The parts.', strokes=[diagram('row')])])
    pg.wait_for_function('abhyasaBoard.state && abhyasaBoard.state.done')
    got = pg.evaluate(LOOK)
    assert got['where'] == 'guide-strip' and got['afterSay'] and len(got['nodes']) == 6
    ns = got['nodes']
    assert not [(i, j) for i in range(6) for j in range(i + 1, 6) if overlap(ns[i], ns[j])]

def test_reduced_motion_shows_the_diagram_at_once(browser):
    "With reduced motion, a board that is not fast shows each node of its diagram in full soon after it starts: no pop and no pen."
    pg = browser(reduced=True)
    pg.evaluate("ss => abhyasaBoard.play({steps: ss, tier: 'tutor', sources: []}, {quiet: true})", [dict(say='The parts.', strokes=[diagram('tree')])])
    pg.wait_for_selector('.board-diagram .board-node')
    pg.wait_for_timeout(400)
    assert pg.evaluate("[...document.querySelectorAll('.board-diagram .board-node')].map(e => getComputedStyle(e).opacity)") == ['1'] * 6

def test_a_sketch_on_a_part_that_is_not_a_figure_is_dropped(browser):
    "A sketch on the passage draws nothing. The same sketch on a figure draws its stroke."
    pg = browser()
    pg.evaluate("""() => { const i = new Image(200, 120); i.dataset.guideId = 'figure';
                           i.src = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="120"><rect width="200" height="120" fill="%23eee"/></svg>');
                           const f = document.createElement('figure'); f.append(i); document.querySelector('main').append(f); }""")
    pts = [[0, 100], [500, 500], [1000, 900]]
    pg.evaluate(PLAY, [dict(say='A curve.', strokes=[dict(op='sketch', at='passage', pts=pts)])])
    pg.wait_for_function('abhyasaBoard.state && abhyasaBoard.state.done')
    assert pg.evaluate("document.querySelectorAll('#board-layer g[data-op=sketch]').length") == 0
    pg.evaluate(PLAY, [dict(say='A curve.', strokes=[dict(op='sketch', at='figure', pts=pts)])])
    pg.wait_for_function('abhyasaBoard.state && abhyasaBoard.state.done')
    assert pg.evaluate("[...document.querySelectorAll('#board-layer g[data-op=sketch] path')].some(p => (p.getAttribute('d') || '').length > 20)")
