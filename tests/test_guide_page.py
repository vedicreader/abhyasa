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
ASKS = dict(wait='Sends your question and the page text to Claude Sonnet.', state='asking', model='Claude Sonnet', where='hosted', who='Anthropic')
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
    page.evaluate("abhyasaBoard.status({wait: 'Sends your question and the page text to Gemma 4 E4B. Nothing leaves this Mac.', state: 'asking', model: 'Gemma 4 E4B', where: 'on this Mac', who: ''})")
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

def test_the_local_flag_of_the_host_sets_the_chip(page):
    "A host flag `local` sets the chip: true is on this Mac, false is hosted, whatever `where` says. With no flag, only on this Mac is local. The voice line keeps the same rule."
    chip = lambda ev: page.evaluate("ev => { abhyasaBoard.status(ev); return document.querySelector('#guide-strip .board-where').textContent }", ev)
    ask = dict(wait='Thinks.', state='asking', model='M', who='')
    assert chip({**ask, 'where': 'in this browser', 'local': True}) == 'on this Mac'
    assert chip({**ask, 'where': 'on this Mac', 'local': False, 'who': 'X'}) == 'hosted · X'
    assert chip({**ask, 'where': 'on this Mac'}) == 'on this Mac' and chip({**ask, 'where': 'in this browser'}) == 'hosted'
    page.evaluate("s => abhyasaBoard.play({steps: [s], tier: 'tutor', sources: []}, {quiet: false, auto: false})", STEP)
    keys = lambda v: page.evaluate("v => { abhyasaBoard.voiceAt(v); return document.querySelector('#guide-strip .board-keys').textContent }", v)
    assert 'Browser voice on this Mac' in keys(dict(model='Browser voice', where='in the browser', local=True)).replace('\xa0', ' ').replace('  ', ' ')
    assert 'hosted' not in keys(dict(model='Browser voice', where='in the browser', local=True))
    assert 'hosted' in keys(dict(model='Browser voice', where='in the browser'))

def test_saved_shows_with_undo(page):
    "A page that the guide saved shows at the end, with Undo. Undo posts to the route and shows its answer."
    page.route('**/guide/undo/k1', lambda r: r.fulfill(status=200, body='Removed Ranks from your vault.'))
    page.reply = sse(dict(saved=dict(title='Ranks', url='https://example.org/r', undo='/guide/undo/k1')),
                     dict(board=dict(tier='web', steps=[STEP], sources=[], end='x')))
    page.evaluate("abhyasaGuideQuiet = true; abhyasaGuide.ask('what is this')")
    page.wait_for_function("document.querySelector('#guide-strip .board-saved')")
    assert page.evaluate("document.querySelector('#guide-strip .board-saved').textContent") == 'Saved to your vault: Ranks. Undo'
    page.click('#guide-strip .board-undo')
    page.wait_for_function("document.querySelector('#guide-strip .board-saved').textContent.startsWith('Removed Ranks')")

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
    from abhyasa.learner import set_val
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

def test_a_concept_page_gives_its_slug_statement_and_passage(page):
    """On a concept page the guide reads the slug from the title, the statement, and the passage of a walk, with the title of its
    source and no source line or link in the passage text."""
    from fasthtml.common import to_xml, Div, Blockquote
    from abhyasa.core import Md, SourceLine, source_of
    page.goto(page.url.rstrip('/') + '/c/ranking'); page.wait_for_function('window.abhyasaGuide')
    walk = Div(Blockquote(Md('Items are ordered by a score.'), SourceLine(source_of(dict(shelf='papers', doc_id='d1', title='Learning to rank', section='2 Ranking', text='x'))),
                          cls='quote'), cls='walk-passages')
    page.evaluate("h => document.querySelector('main').insertAdjacentHTML('beforeend', h)", to_xml(walk))
    ctx = page.evaluate('abhyasaGuide.capture()')
    by = {a['id']: a for a in ctx['anchors']}
    assert ctx['slug'] == 'ranking'
    assert by['statement']['text'] == 'Order items by a score.' and by['statement']['kind'] == 'text'
    assert by['passage']['text'] == 'Items are ordered by a score.'
    assert ctx['source'].startswith('Learning to rank') and 'Open' not in ctx['source'] and 'your source' not in ctx['source']

def test_block_parts_of_an_anchor_do_not_run_together(page):
    "A label and a paragraph of the check read as two words, and the buttons are not text."
    page.evaluate("""() => document.querySelector('main').insertAdjacentHTML('beforeend',
                     '<div id="check"><span class="lbl">recall</span><p>plain words</p><button>Hint</button></div>')""")
    by = {a['id']: a for a in page.evaluate('abhyasaGuide.capture()')['anchors']}
    assert by['check']['text'] == 'recall plain words'

def test_the_name_of_the_idea_is_not_a_figure_word(page):
    """A walk figure with no caption has the alt "A figure for <idea>": a question that names the idea is not about the figure.
    A word of a real caption is."""
    page.evaluate("""() => { document.querySelector('main').insertAdjacentHTML('afterbegin', '<h1>Softmax</h1>');
                             const f = document.createElement('figure'), i = new Image(); i.alt = 'A figure for Softmax';
                             i.src = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"/>');
                             f.append(i); document.querySelector('main').append(f); return new Promise(ok => i.complete ? ok() : i.onload = ok); }""")
    about = lambda q: page.evaluate("async q => { const c = await abhyasaGuide.capture(); return abhyasaGuide.aboutFigure(q, c, document.querySelector('figure img')); }", q)
    assert not about('why does softmax use exp')
    page.evaluate("""() => document.querySelector('figure').insertAdjacentHTML('beforeend', '<figcaption>Scaled dot-product attention</figcaption>')""")
    assert about('what is scaled here') and not about('why does softmax use exp')

def test_the_page_shows_the_drawing_state_when_the_first_step_comes(page):
    "The server never sends the drawing state: the page shows it when the first step comes, before the board plays."
    page.evaluate("() => { window.states = []; const s = abhyasaBoard.status; abhyasaBoard.status = e => { states.push(e.state); return s(e); }; }")
    page.reply = sse(ASKS, dict(step=STEP, k=1, tier='tutor'))
    page.evaluate("abhyasaGuideQuiet = true; abhyasaGuide.ask('what is this')")
    page.wait_for_function('abhyasaBoard.state && !abhyasaBoard.state.streaming', timeout=5000)
    assert page.evaluate('states') == ['reading', 'asking', 'drawing']

def test_the_voice_notice_stays_until_the_step_changes(page):
    "The first board with a voice says how to turn it off. A next step that streams in does not take the line away; a new step does."
    page.evaluate("""() => { document.body.insertAdjacentHTML('beforeend', '<p data-guide-id="b">Beta</p>');
                             abhyasaBoard.play({steps: [{say: 'One.', strokes: [{op: 'box', at: 'passage'}]}], tier: 'tutor', sources: [], streaming: true},
                                               {onVoice: () => {}, host: {speak: () => {}}}); }""")   # a voice that never ends: the board stays at step 1
    page.wait_for_function("document.querySelector('#guide-strip .board-tell')")
    page.evaluate("abhyasaBoard.add({say: 'Two.', strokes: [{op: 'box', at: 'b'}]})")
    assert page.evaluate("!!document.querySelector('#guide-strip .board-tell')") and page.evaluate('abhyasaBoard.state.i') == 0
    page.evaluate('abhyasaBoard.next()')
    assert page.evaluate("!document.querySelector('#guide-strip .board-tell')")

def test_maths_in_the_board_caption(page):
    """The words of a step with $…$ or a bare W_Q show maths: KaTeX draws it where the page has it, else a <sub> holds the subscript.
    The text never goes in as HTML, and each formula is one word that lights up."""
    step = dict(say='Multiply $x$ by W_Q, then <b>d_k</b>.', strokes=[dict(op='box', at='passage')])
    def say():
        page.evaluate("s => abhyasaBoard.play({steps: [s], tier: 'tutor', sources: []}, {quiet: true, fast: true})", step)
        page.wait_for_function("document.querySelector('#guide-strip .board-say')")
        return page.evaluate("""() => { const s = document.querySelector('#guide-strip .board-say');
                                         return [s.children.length, s.querySelectorAll('.katex').length, [...s.querySelectorAll('sub')].map(x => x.textContent), !!s.querySelector('b')]; }""")
    assert say() == [6, 2, [], False]   # Multiply, x, by, W_Q, then, <b>d_k</b>. (one word with its tags as text)
    page.evaluate('window.katexSaved = window.katex; delete window.katex')
    try: assert say() == [6, 0, ['Q'], False]
    finally: page.evaluate('window.katex = window.katexSaved')

def test_demo_set_keeps_each_value_in_its_input(page):
    """Rupaka.set copies a value as it is given, so the board fits each value of `demo_set` to its input first: a number over the
    max lands at the max and on the step, an option that the choice does not have and a toggle that is not true or false are dropped."""
    got = page.evaluate("""async () => {
      const calls = []; window.Rupaka = {set: (h, s) => calls.push(s)};
      const h = Object.assign(document.createElement('div'), {textContent: 'A demo'}); h.dataset.guideId = 'demo';
      h.rupaka = {spec: {id: 'd', state: {k: 3, shape: 'square', on: false}, blocks: [
        {type: 'slider', bind: 'k', min: 0, max: 10, step: 0.5}, {type: 'choice', bind: 'shape', options: ['triangle', 'square']},
        {type: 'toggle', bind: 'on'}]}, st: {k: 3, shape: 'square', on: false, gate: {}}};
      document.querySelector('main').append(h);
      await abhyasaBoard.play({steps: [{say: 'Move k.', strokes: [{op: 'demo_set', set: {k: 99, shape: 'circle', on: 'yes'}}, {op: 'box', at: 'demo'}]},
                                       {say: 'Again.', strokes: [{op: 'demo_set', set: {k: 2.7, shape: 'triangle', on: true, nope: 1}}, {op: 'box', at: 'demo'}]}],
                               tier: 'tutor', sources: []}, {quiet: true, fast: true});
      return calls; }""")
    assert got == [{'k': 10}, {'k': 2.5, 'shape': 'triangle', 'on': True}]

def test_the_capture_has_the_last_graded_try(page):
    """A walk check with a try, the nudge on it and the gaps it points at, made by the real parts of the walk: the capture has the
    anchor `try` with the answer, the outcome, the feedback, the Error line, the gaps and the tries left. A session question gives
    the same, and after the close the check is closed."""
    from fasthtml.common import to_xml, Div, Span
    from abhyasa.core.ui import Check
    from abhyasa.blocks.walk.ui import Turn
    from abhyasa.blocks.detour.ui import GapLine
    from abhyasa.blocks.session import ui as S
    you = dict(who='you', text='Alpha bar grows with t.', confidence=50)
    nudge = dict(who='tutor', kind='nudge', text='Look at what each alpha is.', first_error='Alpha bar does not grow.')
    walk = Div(Check(Div('Check', cls='lbl'), 'Why does alpha bar fall?', Turn(you, 0), Turn(nudge, 0),
                     foot=(GapLine([('cumulative-product', 'cumulative product', 'missing', None), ('noise', 'noise schedule', 'missing', None)]), Div(Span('2 tries left', cls='mute'), cls='row conf'))), id='check')
    page.evaluate("h => document.querySelector('main').insertAdjacentHTML('beforeend', h)", to_xml(walk))
    t = {a['id']: a for a in page.evaluate('abhyasaGuide.capture()')['anchors']}['try']
    assert {k: t.get(k) for k in ('kind', 'answer', 'outcome', 'feedback', 'error', 'gaps', 'state', 'left')} == dict(
        kind='try', answer='Alpha bar grows with t.', outcome='Not yet', feedback='Look at what each alpha is.', error='Alpha bar does not grow.',
        gaps=['cumulative product', 'noise schedule'], state='open', left=2)
    assert page.evaluate("document.querySelector('[data-guide-id=try]').classList.contains('you')")
    page.evaluate("document.getElementById('check').remove()")
    turns = [dict(who='you', text='It grows.'), dict(who='tutor', kind='nudge', text='Look again.'), dict(who='you', text='It falls, as a product.'),
             dict(who='tutor', kind='close', outcome='gap', text='Alpha bar is a product.')]
    chat = Div(Check(Div('Alpha bar', cls='head'), 'Why does alpha bar fall?', *S.Turns(turns), cls='qa'), id='chat')
    page.evaluate("h => { document.querySelector('main').insertAdjacentHTML('beforeend', h); }", to_xml(chat))
    t = {a['id']: a for a in page.evaluate('abhyasaGuide.capture()')['anchors']}['try']
    assert (t['answer'], t['outcome'], t['state'], 'left' in t) == ('It falls, as a product.', 'A gap', 'closed', False)

def test_a_show_event_opens_the_demo_card_and_no_board(page):
    """A show event on a page with no Show slot puts the demo in the side panel at the top right: the card of the demo block as it is, or a
    link to the demo of the idea. No board draws, and × closes the panel. On a page with a Show slot, the card fills the slot and no panel opens."""
    page.set_viewport_size(dict(width=1400, height=900))
    page.reply = sse(dict(show=dict(html='<div class="ask-card" id="ask-x"><p>A 2D demo</p></div>')))
    page.evaluate("abhyasaGuideQuiet = true; abhyasaGuide.ask('show me how the noise grows')")
    page.wait_for_selector('#guide-show .ask-card')
    assert page.evaluate("document.querySelector('#guide-show .guide-show-head').textContent").startswith('Show ')
    r = page.evaluate("(() => { const b = document.getElementById('guide-show').getBoundingClientRect(); return [innerWidth - b.right, b.top]; })()")
    assert r[0] < 40 and r[1] < 120   # the top right of the window
    m, c = [page.evaluate(f"(() => {{ const b = document.querySelector('{q}').getBoundingClientRect(); return [b.left, b.right]; }})()") for q in ('main', '#guide-show')]
    assert m[1] <= c[0] and page.evaluate("document.body.classList.contains('has-panel')")   # the page column moves left: the card covers no text
    assert page.evaluate('abhyasaBoard.state') is None and page.evaluate("document.getElementById('guide-strip').hidden")
    page.reply = sse(dict(show=dict(href='/c/ranking?show=', title='Ranking')))
    page.evaluate("abhyasaGuide.ask('show me the ranks')")
    page.wait_for_selector('#guide-show a[href="/c/ranking?show="]')
    assert page.evaluate("document.querySelectorAll('#guide-show').length") == 1 and page.evaluate("document.querySelector('#guide-show a').textContent") == 'Open the demo of Ranking'
    page.click('#guide-show .guide-show-close')
    assert page.evaluate("!document.getElementById('guide-show')") and not page.evaluate("document.body.classList.contains('has-panel')")
    page.set_viewport_size(dict(width=900, height=900))   # below 1100 px the card stands in the page
    page.reply = sse(dict(show=dict(href='/c/ranking?show=', title='Ranking')))
    page.evaluate("abhyasaGuide.ask('show me')")
    page.wait_for_selector('main #guide-show.inline')
    page.click('#guide-show .guide-show-close')
    page.evaluate("""() => { const d = document.createElement('div'); d.id = 'show-slot'; (document.querySelector('main') || document.body).append(d); }""")
    page.reply = sse(dict(show=dict(html='<div class="ask-card" id="ask-y"><p>A 2D demo</p></div>', href='/c/ranking?show=')))
    page.evaluate("abhyasaGuide.ask('yes, show me')")
    page.wait_for_selector('#show-slot .ask-card')
    assert page.evaluate("!document.getElementById('guide-show')")

def play(pg, steps):
    pg.evaluate("ss => abhyasaBoard.play({steps: ss, tier: 'tutor', sources: [], streaming: false}, {quiet: true, auto: false})", steps)
    pg.wait_for_function('abhyasaBoard.state && abhyasaBoard.state.done', timeout=5000)

def test_code_is_an_anchor(page):
    "The guide reads each `pre` of the page as an anchor `code1` to `code4`, so the board can mark a value in code."
    page.evaluate("""() => { const m = document.querySelector('main') || document.body; const p = document.createElement('pre'); p.textContent = 'assert add_noise_loss([1.0, 1.0], [1.0, -1.0], 0.5, [1.0, 1.0]) == ([1.414, 0.0], 2.0)'; m.prepend(p); }""")
    ctx = page.evaluate('abhyasaGuide.capture()')
    code = [a for a in ctx['anchors'] if a['kind'] == 'code']
    assert code and code[0]['id'] == 'code1' and '[1.0, -1.0]' in code[0]['text']
    b, pre = page.evaluate("[abhyasaBoard.boxOf({a: 'code1', text: '[1.0, -1.0]'}), (r => ({x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height}))(document.querySelector('main pre, body > pre').getBoundingClientRect())]")
    assert b and pre['x'] <= b['x'] and b['x'] + b['w'] <= pre['x'] + pre['w'] + 1 and pre['y'] <= b['y'] <= pre['y'] + pre['h']

def test_the_panel_covers_no_text_and_no_mark_at_1400(page):
    "On the app page at 1400 by 900, the side panel of rupaka's board is at the top right, and the page column moves left while the panel shows: the panel covers no text of main and no mark. The panel is on paper, in the hand font."
    page.set_viewport_size(dict(width=1400, height=900))
    page.evaluate("""() => { const m = document.querySelector('main'); const p = document.createElement('pre'); p.dataset.guideId = 'm'; p.textContent = 'x = tensor([18, 47, 56]) and more text to the right edge of the column ' + 'y'.repeat(60); p.style.whiteSpace = 'pre-wrap'; m.prepend(p); }""")
    play(page, [dict(say='The values.', strokes=[dict(op='panel', head='Make a question'), dict(op='row', cells=['[18]'], to='47', at=dict(a='m', text='tensor([18, 47, 56])'))])])
    page.wait_for_timeout(400)   # the column moves
    p, m = [page.evaluate(f"(() => {{ const b = document.querySelector('{q}').getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; }})()") for q in ('#board-panel', 'main')]
    assert m[2] <= p[0], (m, p)
    marks = page.evaluate("[...document.querySelectorAll('#board-layer g[data-op=circle]')].map(g => { const b = g.getBoundingClientRect(); return [b.left, b.right]; })")
    assert marks and all(r <= p[0] for _, r in marks)
    assert page.evaluate("getComputedStyle(document.querySelector('.board-panel-head')).fontFamily").startswith('"Patrick Hand"')
    assert page.evaluate("document.fonts.ready.then(() => [...document.fonts].some(f => f.family.includes('Patrick Hand') && f.status === 'loaded'))")   # rupaka's file, served here

def test_maths_in_a_panel_cell_is_katex(page):
    "On the app page, a panel cell with `$w_1x_1$`, a bare `x_i` and a head with `$z$` draw with KaTeX, as marks on the page do: no raw `_` or `$` shows."
    page.set_viewport_size(dict(width=1440, height=900))
    play(page, [dict(say='Multiply each input by its weight.', strokes=[dict(op='panel', head='Inside $z$', cols=['Step', 'Result']),
                                                                       dict(op='row', cells=['Multiply each x_i by w_i'], to='$w_1x_1$')])])
    got = page.evaluate("""() => [...document.querySelectorAll('#board-panel .board-cell, #board-panel .board-panel-head')].map(e => {
        const seen = [...e.querySelectorAll('.katex-html')].map(k => k.textContent).join(''), c = e.cloneNode(true);
        c.querySelectorAll('.katex-mathml').forEach(m => m.remove());
        return {katex: e.querySelectorAll('.katex').length, text: c.textContent, seen}; })""")
    assert [g['katex'] for g in got] == [1, 2, 1], got   # the head, the cell, the answer
    assert all('_' not in g['text'] and '$' not in g['text'] for g in got), got
    assert 'w1x1' in got[2]['text'].replace('​', ''), got

NEURON = r"A neuron takes numbers $x_1, \dots, x_n$, multiplies each by a weight $w_i$, adds a bias $b$, and outputs $z = w_1x_1 + \cdots + w_nx_n + b$. In Python this is a loop that sums products, then adds one number."
PARAS = """() => { const out = [], r = document.createRange(), tw = document.createTreeWalker(document.querySelector('#passage p'), NodeFilter.SHOW_TEXT,
    {acceptNode: n => n.parentElement.closest('.katex-mathml') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT});
  for (let n; (n = tw.nextNode());) { if (!n.data.trim()) continue; r.selectNodeContents(n); for (const q of r.getClientRects()) out.push([q.left + scrollX, q.top + scrollY, q.right + scrollX, q.bottom + scrollY]); }
  return out; }"""

def test_a_label_and_a_curve_on_a_formula_keep_off_the_passage(page):
    """At 1440 px, on a passage with KaTeX formulas: a label on the `z` of the formula covers no line of the passage, and the curve from
    `w_1` to its row crosses no line of the passage after its start."""
    from fasthtml.common import to_xml
    from abhyasa.core.ui import Md
    page.set_viewport_size(dict(width=1440, height=900))
    page.evaluate("""h => { const q = document.getElementById('passage'); q.innerHTML = h; render(q); }""", to_xml(Md(NEURON)))
    page.evaluate('abhyasaGuide.capture()')   # the formulas get their anchors and parts
    page.evaluate('document.fonts.ready')
    play(page, [dict(say='It multiplies each input by its weight.', strokes=[dict(op='panel', head='Inside one neuron'),
                     dict(op='row', cells=['Multiply each $x_i$ by $w_i$'], to='$w_1x_1$', at=dict(a='m4', tex='w_1'))]),
                dict(say='The output z is one number.', strokes=[dict(op='label', at=dict(a='m4', tex='z'), text="one number out", side='below')])])
    lines = page.evaluate(PARAS)
    pts = page.evaluate("""() => { const p = document.querySelector('#board-layer g[data-op=link] path'), L = p.getTotalLength(), out = [];
        for (let s = 14; s <= L; s += 3) { const q = p.getPointAtLength(s); out.push([q.x, q.y]); } return out; }""")
    assert pts and not [p for p in pts if any(q[0] + 1 < p[0] < q[2] - 1 and q[1] + 1 < p[1] < q[3] - 1 for q in lines)]
    page.evaluate('abhyasaBoard.next()'); page.wait_for_function('abhyasaBoard.state.i === 1 && abhyasaBoard.state.done')
    chip = page.evaluate("(() => { const b = document.querySelector('.board-label').getBoundingClientRect(); return [b.left + scrollX, b.top + scrollY, b.right + scrollX, b.bottom + scrollY]; })()")
    assert not any(chip[0] < q[2] and q[0] < chip[2] and chip[1] < q[3] and q[1] < chip[3] for q in lines), (chip, lines)
