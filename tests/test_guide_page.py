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

# --- never caught unaware ---------------------------------------------------------------------------------------------------
ASKS = dict(wait='Asks Claude Sonnet. It gets your question and the page text.', state='asking', model='Claude Sonnet', where='hosted', who='Anthropic')
strip = lambda page: page.evaluate("document.getElementById('guide-strip').textContent")

def test_the_state_line_names_the_model_and_where_it_runs(page):
    "Before the board, the state line shows the wait text, the chip of where the text goes, and Stop. The caption names the model."
    page.reply = sse(ASKS, dict(wait='Searches the web for: "alpha bar"', state='searching', where='hosted', query='alpha bar'))
    page.evaluate("abhyasaGuide.ask('what is this')")
    page.wait_for_function("document.querySelector('#guide-strip .board-state[data-state=\"searching\"]')")
    t = strip(page)
    assert 'Searches the web for: "alpha bar"' in t and 'hosted' in t and 'Stop' in t
    page.evaluate("abhyasaBoard.status(%s)" % json.dumps(ASKS))
    assert page.evaluate("document.querySelector('#guide-strip .board-where').textContent") == 'hosted · Anthropic'
    page.evaluate("abhyasaBoard.status({wait: 'Asks Gemma 4 E4B. Nothing leaves this Mac.', state: 'asking', model: 'Gemma 4 E4B', where: 'on this Mac', who: ''})")
    assert page.evaluate("document.querySelector('#guide-strip .board-where').textContent") == 'on this Mac'
    page.reply = sse(ASKS, dict(step=STEP, k=1, tier='tutor'), dict(board=dict(tier='tutor', steps=[STEP], sources=[], end="In the tutor's own words. No source found.",
                                                                               saved=None, hint='Hint 2 of 6 used (from the board).')))
    page.evaluate("abhyasaGuideQuiet = true; abhyasaGuide.ask('what is this')")
    page.wait_for_function("abhyasaBoard.state && !abhyasaBoard.state.streaming")
    assert page.evaluate("document.querySelector('#guide-strip .board-who').textContent") == 'Claude Sonnet · hosted · Anthropic'   # the words of the chip
    assert 'Hint 2 of 6 used (from the board).' in strip(page)
    assert page.evaluate("[...document.querySelectorAll('#guide-strip .board-btn')].map(b => b.textContent)") == ['Voice on', 'Stop']
    page.click('#guide-strip .board-stop')
    assert page.evaluate('abhyasaBoard.state') is None

def test_saved_shows_with_undo(page):
    "A page that the guide saved shows at the end, with Undo. Undo posts to the route and shows its answer."
    page.route('**/guide/undo/k1', lambda r: r.fulfill(status=200, body='The guide took Ranks out of your vault.'))
    page.reply = sse(dict(saved=dict(title='Ranks', url='https://example.org/r', undo='/guide/undo/k1')),
                     dict(board=dict(tier='web', steps=[STEP], sources=[], end='x')))
    page.evaluate("abhyasaGuideQuiet = true; abhyasaGuide.ask('what is this')")
    page.wait_for_function("document.querySelector('#guide-strip .board-saved')")
    assert page.evaluate("document.querySelector('#guide-strip .board-saved').textContent") == 'Saved to your vault: Ranks. Undo'
    page.click('#guide-strip .board-undo')
    page.wait_for_function("document.querySelector('#guide-strip .board-saved').textContent.startsWith('The guide took')")

def test_stop_before_the_board_ends_the_request(page, fake):
    "Stop in the state line while the model writes, before a board draws: the request ends, and the line says that the guide shows no answer."
    fake.rules = {'Tier: tutor': lambda p, sp: time.sleep(2) or '{"op":"v","n":1,"sure":0.9}', **fake.rules}   # a slow model, on the real route
    page.unroute('**/guide/ask')
    page.evaluate("() => { abhyasaGuide.ask('what is this'); }")   # no wait for the ask to end
    page.wait_for_function("document.querySelector('#guide-strip .board-state[data-state=\"asking\"] .board-stop')")
    page.click('#guide-strip .board-stop')
    page.wait_for_function("document.getElementById('guide-strip').textContent.startsWith('Stopped.')")

def test_the_figure_goes_out_only_when_the_question_is_about_it(page):
    "A figure on the page is not posted for a question on the passage. A question on the figure posts it, and the line says so first."
    posts = []
    page.route('**/guide/figure*', lambda r: (posts.append(1), r.fulfill(status=200, content_type='application/json', body='{"labels": {}}')))
    page.evaluate("""() => new Promise(ok => { const f = document.createElement('figure'); f.id = 'figure'; const i = new Image(); i.onload = ok;
                      i.alt = 'A right triangle'; i.src = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><rect width="40" height="40"/></svg>');
                      f.append(i); document.querySelector('main').append(f); })""")
    page.evaluate("abhyasaGuideQuiet = true; abhyasaGuide.ask('what is the noise')")
    page.wait_for_function("document.getElementById('guide-strip').textContent.includes('A test.')")
    assert not posts and 'labels' not in json.dumps(page.asked[-1]['ctx'])
    page.evaluate("abhyasaGuide.ask('what is this triangle')")
    page.wait_for_function("document.getElementById('guide-strip').textContent.includes('A test.')")
    assert posts == [1]

def test_reading_line_and_the_pointer_notice(page):
    page.evaluate("document.querySelector('main').insertAdjacentHTML('beforeend', '<div id=\"note\">A note.</div><div id=\"check\">A check.</div>')")
    ctx = page.evaluate('abhyasaGuide.capture()')
    assert page.evaluate('c => abhyasaGuide.readLine(c)', ctx) == 'Reads this page: the passage, the note and the check.'
    page.evaluate('abhyasaGuide.open()')
    assert page.evaluate("document.querySelector('#guide-form .guide-follow').textContent") == 'The guide follows your pointer while you ask.'

def test_the_saved_point_look_reaches_the_board(page):
    "A look that you save on the Settings page goes from the page to play(), and the point mark draws in that look."
    from abhyasa.settings import set_val
    try:
        assert page.evaluate("async () => (await fetch('/settings/value', {method: 'POST', body: new URLSearchParams({name: 'guide.point', value: 'ring'})})).ok")
        page.reload(); page.wait_for_function('window.abhyasaGuide && window.abhyasaBoard')
        page.evaluate("""() => { const p = document.createElement('section'); p.id = 'passage'; p.dataset.guideId = 'passage'; p.textContent = 'Some words.';
                                 document.querySelector('main').prepend(p);
                                 const play = abhyasaBoard.play; abhyasaBoard.play = (b, o) => { window.gotPoint = o && o.point; return play(b, o); }; }""")
        page.reply = sse(dict(step=dict(say='This is the passage.', strokes=[dict(op='point', at='passage')]), k=1, tier='tutor'))
        page.evaluate("abhyasaGuideQuiet = true; abhyasaGuide.ask('what is this')")
        page.wait_for_function("document.querySelector('#board-layer g[data-op=point]')", timeout=5000)
        assert page.evaluate("[window.gotPoint, document.querySelector('#board-layer g[data-op=point]').dataset.look]") == ['ring', 'ring']
    finally: set_val('guide.point', 'tick')

def test_esc_while_the_guide_asks_stays_on_the_page(page, fake):
    """Esc while the state line shows stops the guide, and the learner stays on the page: the Esc of core.js, which goes up to the
    parent in the crumbs, does not run. Esc in the open box closes the box, and the page stays too."""
    fake.rules = {'Tier: tutor': lambda p, sp: time.sleep(2) or '{"op":"v","n":1,"sure":0.9}', **fake.rules}   # a slow model, on the real route
    page.unroute('**/guide/ask')
    page.goto(page.url.rstrip('/') + '/c/ranking'); page.wait_for_function('window.abhyasaGuide && window.abhyasaBoard')
    here = page.url
    assert page.evaluate("!!document.querySelector('main .crumbs a.up')")   # without the fix, Esc clicks this link
    page.evaluate("() => { abhyasaGuide.ask('what is this'); }")
    page.wait_for_function("document.querySelector('#guide-strip .board-state[data-state=\"asking\"]')")
    page.keyboard.press('Escape')
    page.wait_for_function("document.getElementById('guide-strip').textContent.startsWith('Stopped.')")
    page.wait_for_timeout(300)
    assert page.url == here
    page.evaluate('abhyasaGuide.open()')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    assert page.url == here and page.evaluate("document.getElementById('guide-form').hidden")

def test_the_first_use_line_keeps_the_box_wide(page):
    "The first Explain in a new browser profile shows one line under the box. The line has its own row, so the box stays wide."
    page.evaluate('abhyasaGuide.open()')
    assert page.evaluate("document.querySelector('#guide-form .guide-heard').textContent").startswith('The tutor reads this page')
    assert page.evaluate("document.getElementById('guide-box').getBoundingClientRect().width") > 300
