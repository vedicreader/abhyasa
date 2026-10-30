"The guide on a real page, in a headless browser: the stream of the ask route, the capture of formulas, and the demo ids."
import json, socket, threading, time, pytest
from test_board_js import _chromium

pytestmark = pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")

def sse(*evs) -> str: return ''.join(f'data: {json.dumps(e)}\n\n' for e in evs)

@pytest.fixture
def page(mk):
    "One headless page of the app. The ask route answers here with `page.reply` (server-sent events), and keeps each body in `page.asked`."
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
                pg.asked, pg.reply = [], sse(dict(error='A test.'))
                def answer(route):
                    pg.asked.append(json.loads(route.request.post_data))
                    route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=pg.reply)
                pg.route('**/guide/ask', answer)
                pg.goto(f'http://127.0.0.1:{port}/'); pg.wait_for_function('window.abhyasaGuide && window.abhyasaBoard && window.katex')
                pg.evaluate("""() => { const p = document.createElement('section'); p.id = 'passage'; p.dataset.guideId = 'passage';
                                       p.textContent = 'The forward process adds noise in small steps.'; document.querySelector('main').prepend(p); }""")
                yield pg
            finally: b.close()
    finally:
        srv.should_exit = True; th.join(5)

STEP = dict(say='This is the passage.', strokes=[dict(op='box', at='passage')])

def test_a_stream_with_steps_and_no_board_ends_the_board(page):
    "The stream ends after one step and with no board event: the board stops its wait for steps, in the tutor tier, with no end line."
    page.reply = sse(dict(step=STEP, k=1, tier='tutor'))
    page.evaluate("abhyasaGuideQuiet = true; abhyasaGuide.ask('what is this')")
    page.wait_for_function('abhyasaBoard.state && !abhyasaBoard.state.streaming', timeout=5000)
    st = page.evaluate('abhyasaBoard.state')
    assert (st['steps'], st['tier'], st['streaming']) == (1, 'tutor', False)
    assert page.evaluate("document.querySelector('#guide-strip .board-n').textContent") == 'Step 1 of 1'
    assert page.evaluate("!document.querySelector('#guide-strip .board-end')")

QKV = ('Each input vector $x$ is linearly projected into a query $q = xW_Q$, a key $k = xW_K$ and a value $v = xW_V$. '
       'A query is compared with keys to decide how much of each value to read.')

def test_inline_formulas_of_a_passage_are_anchors(page):
    """A walk-step passage with inline maths, made by abhyasa's own markdown (`Md`) and drawn by KaTeX as the page does. Each formula
    is an anchor with its tokens, and W_Q is one token. The passage keeps the TeX as the page wrote it, also on a second ask, when
    the formulas already carry the ids of their parts."""
    from fasthtml.common import to_xml
    from abhyasa.core.ui import Md
    page.evaluate("""h => { const q = document.getElementById('passage'); q.innerHTML = h; render(q); }""", to_xml(Md(QKV)))
    for _ in range(2):
        ctx = page.evaluate('abhyasaGuide.capture()')
        by = {a['id']: a for a in ctx['anchors']}
        assert by['passage']['text'] == QKV[:300] and '\\htmlId' not in json.dumps(ctx)
        fs = [(a['text'], a['tokens']) for a in ctx['anchors'] if a['kind'] == 'formula']
        assert fs == [('x', ['x']), ('q = xW_Q', ['q', 'x', 'W_Q']), ('k = xW_K', ['k', 'x', 'W_K']), ('v = xW_V', ['v', 'x', 'W_V'])], fs
    box, part = page.evaluate("""async () => { await document.fonts.ready;   // in one call: the KaTeX fonts move the glyphs when they load
                                     const r = document.querySelector('[data-guide-id="m2"] #g-2-2').getBoundingClientRect();
                                     return [abhyasaBoard.boxOf({a: 'm2', tex: 'W_Q'}), {x: r.left + scrollX, w: r.width}]; }""")
    assert abs(box['x'] - part['x']) < 1 and abs(box['w'] - part['w']) < 1   # a mark on the token lands on W_Q, not on q or x

def test_demo_anchors_have_the_agreed_ids(page):
    """`abhyasaBoard.demoAnchors` names a rupaka demo as every host does: `demo`, `in:<bind>` for each key of spec.state, and `out:<n>`
    for each readout that shows, from 1 in depth-first spec order. Blocks pair with [data-rk-type] nodes by index. An id over 40
    characters is dropped, not cut."""
    long = 'b' * 38   # 'in:' + 38 characters is 41
    got = page.evaluate("""long => {
      const h = document.createElement('div'); h.dataset.rupaka = '1';
      const spec = {id: 'rrf', title: 'Fusion', ask: 'Move k.', state: {k: 3, [long]: 1}, blocks: [
        {type: 'slider', bind: 'k', label: 'k', min: 0, max: 10}, {type: 'row', blocks: [{type: 'readout'}, {type: 'slider', bind: long}]},
        {type: 'plot'}, {type: 'gate', id: 'g1'}]};
      for (const [t, x] of [['slider', ''], ['row', ''], ['readout', 'score 0.25'], ['slider', ''], ['plot', 'a plot'], ['gate', '']])
        { const n = Object.assign(document.createElement('div'), {textContent: x}); n.dataset.rkType = t; h.append(n); }
      h.rupaka = {spec, st: {k: 3, [long]: 1, gate: {}}};
      document.querySelector('main').append(h);
      const d = abhyasaBoard.demoAnchors(h);
      return [d.anchors.map(a => a.id), Object.keys(d.demo.inputs), d.demo.readouts, d.demo.open, d.demo.slug,
              [...h.querySelectorAll('[data-guide-id]')].map(e => e.dataset.guideId), h.dataset.guideId];
    }""", long)
    assert got == [['demo', 'in:k', 'out:1', 'out:2'], ['k', long], ['score 0.25', 'a plot'], False, 'rrf', ['in:k', 'out:1', 'out:2'], 'demo']
