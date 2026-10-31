"The side panel of the board (Explain) and the rule that a mark needs a thing under it, in headless Chromium."
import socket, threading, time, pytest
from test_board_js import _chromium

pytestmark = pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")

PAGE = """() => document.body.insertAdjacentHTML('beforeend', `
  <pre data-guide-id="out" style="position:absolute;left:40px;top:300px;width:420px;margin:0">when input is tensor([18]) the target: 47
when input is tensor([18, 47]) the target: 56</pre>
  <div data-guide-id="card" style="position:absolute;left:40px;top:420px;width:420px;height:160px"><p style="margin:0">Open in Leela</p></div>`)"""

@pytest.fixture
def page(mk):
    "One headless page of the app with the output of a cell (`out`) and a card with one line of text at its top (`card`)."
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
                pg = b.new_page(viewport=dict(width=1200, height=800), reduced_motion='reduce')
                pg.goto(f'http://127.0.0.1:{port}/'); pg.wait_for_function('window.abhyasaBoard')
                pg.evaluate(PAGE)
                yield pg
            finally: b.close()
    finally:
        srv.should_exit = True; th.join(5)

def play(pg, steps, streaming=False):
    pg.evaluate("([ss, streaming]) => abhyasaBoard.play({steps: ss, tier: 'tutor', sources: [], streaming}, {quiet: true, auto: false})", [steps, streaming])
    pg.wait_for_function('abhyasaBoard.state && abhyasaBoard.state.done', timeout=5000)

def test_a_mark_with_no_thing_under_it_is_not_drawn(page):
    "A box on a bare point, or on the empty lower part of the card, draws nothing. A box on the words of the card draws its glow."
    glows = "[...document.querySelectorAll('.board-glow')].filter(g => g.style.display !== 'none').length"
    play(page, [dict(say='Look here.', strokes=[dict(op='box', at=dict(a='card', pt=[-200, 900]))])])
    assert page.evaluate(glows) == 0
    play(page, [dict(say='Look here.', strokes=[dict(op='box', at=dict(a='card', box=[0, 500, 1000, 1000])), dict(op='circle', at=dict(a='card', box=[0, 500, 1000, 1000]))])])
    assert page.evaluate(glows) == 0 and page.evaluate("[...document.querySelectorAll('#board-layer g[data-op=circle]')].every(g => g.style.display === 'none')")
    play(page, [dict(say='Look here.', strokes=[dict(op='box', at=dict(a='card', box=[0, 0, 1000, 200]))])])
    assert page.evaluate(glows) == 1

def row(cells, to, text=None, **kw): return dict(op='row', cells=cells, to=to, **({'at': dict(a='out', text=text)} if text else {}), **kw)

def panel(pg):
    "The side panel as text: its title, heading, column names, and the cells of each row that shows."
    return pg.evaluate("""() => { const p = document.getElementById('board-panel'); if (!p) return null;
        const t = s => (p.querySelector(s) || {}).textContent || '';
        return {title: t('.board-panel-title'), head: t('.board-panel-head'), cols: [...p.querySelectorAll('.board-panel-cols span')].map(s => s.textContent),
                rows: [...p.querySelectorAll('.board-row, .board-panel-note')].filter(r => r.style.display !== 'none').map(r => r.textContent)}; }""")

def test_the_side_panel_builds_one_row_in_each_step(page):
    """The panel is at the top right. Each step that comes adds its row, and the rows before stay. A row with `at` has a curve from the
    words on the page to its first cell. A new panel line starts a new beat with its own rows; back to an older step shows its beat again."""
    s1 = dict(say='Each line makes one question.', strokes=[dict(op='panel', title='tensors and targets', head='Make a question and its answer', cols=['Input', 'Target']),
                                                           dict(op='circle', at=dict(a='out', text='tensor([18])')), row(['[18]'], '47', 'tensor([18])')])
    s2 = dict(say='The next one adds a token.', strokes=[row(['[18, 47]'], '56', 'tensor([18, 47])')])
    s3 = dict(say='The model guesses, compares and adjusts.', strokes=[row(['Guess', 'Compare', 'Adjust'], None, chain=True), dict(op='note', text='This code prepares the examples.')])
    s4 = dict(say='Then think big.', strokes=[dict(op='panel', title='from this to chatgpt', head='One small task, enormous practice', numbered=True), row(['The', 'sky', 'is'], 'blue')])
    s3['strokes'][0].pop('to')
    play(page, [s1], streaming=True)
    p = panel(page)
    assert (p['title'], p['head'], p['cols'], p['rows']) == ('tensors and targets', 'Make a question and its answer', ['Input', 'Target'], ['[18]⟶47'])
    r = page.evaluate("(() => { const b = document.getElementById('board-panel').getBoundingClientRect(); return [b.right, b.top]; })()")
    assert r[0] > 1150 and r[1] < 100   # the top right of the window
    link = "document.querySelectorAll('#board-layer g[data-op=link] path').length"
    assert page.evaluate(link) >= 2   # the curve and its head
    for s, want in ((s2, ['[18]⟶47', '[18, 47]⟶56']), (s3, ['[18]⟶47', '[18, 47]⟶56', 'Guess→Compare→Adjust', 'This code prepares the examples.'])):
        page.evaluate('s => abhyasaBoard.add(s)', s); page.evaluate('abhyasaBoard.next()')
        page.wait_for_function('abhyasaBoard.state.done')
        assert panel(page)['rows'] == want
    page.evaluate('s => abhyasaBoard.add(s)', s4); page.evaluate('abhyasaBoard.next()'); page.wait_for_function('abhyasaBoard.state.done')
    p = panel(page)
    assert (p['title'], p['rows']) == ('from this to chatgpt', ['1Theskyis⟶blue'])
    page.evaluate('abhyasaBoard.back()'); page.wait_for_function('abhyasaBoard.state.done')
    assert panel(page)['title'] == 'tensors and targets' and len(panel(page)['rows']) == 4
    page.evaluate('abhyasaBoard.stop()')
    assert panel(page) is None

def test_a_row_with_at_draws_its_own_circle_in_a_fixed_order(page):
    """A row with `at` and no circle line: the board draws one circle and one curve for it. The circle starts at once, the curve 120 ms
    later, the row when the curve lands, then each cell 80 ms after the one before."""
    play(page, [dict(say='The first question.', strokes=[dict(op='panel', head='Make a question'), row(['[18]'], '47', 'tensor([18])')])])
    assert page.evaluate("[...document.querySelectorAll('#board-layer g[data-op=circle][data-step=\"0\"]')].length") == 1
    assert page.evaluate("[...document.querySelectorAll('#board-layer g[data-op=link][data-step=\"0\"]')].length") == 1
    t = [x for x in page.evaluate('abhyasaBoard.timeline()') if x[0] == 'row']
    pen, dash, cells = t[0], [x for x in t if x[1] == 'dash'][0], [x[2] for x in t if x[1] == 'node']
    assert (pen[1], pen[2], dash[2]) == ('pen', 0, 120)
    land = max(x[2] for x in t if x[1] in ('dash', 'head'))
    assert cells[0] >= land - 60 and all(b - a == 80 for a, b in zip(cells, cells[1:])) and len(cells) == 3   # the cell, the arrow, the answer

def test_d_next_keeps_the_panel(page):
    "D next keeps the same panel node and its rows, and adds the row of the new step. S back builds the panel again."
    s1 = dict(say='One.', strokes=[dict(op='panel', head='Make a question'), row(['[18]'], '47', 'tensor([18])')])
    s2 = dict(say='Two.', strokes=[row(['[18, 47]'], '56', 'tensor([18, 47])')])
    play(page, [s1, s2])
    page.evaluate("document.getElementById('board-panel').dataset.tag = 'kept'; document.querySelector('.board-row').dataset.tag = 'kept'")
    page.evaluate('abhyasaBoard.next()'); page.wait_for_function('abhyasaBoard.state.i === 1 && abhyasaBoard.state.done')
    assert page.evaluate("document.getElementById('board-panel').dataset.tag") == 'kept' and page.evaluate("document.querySelector('.board-row').dataset.tag") == 'kept'
    assert len(panel(page)['rows']) == 2

def test_the_board_scrolls_its_first_mark_into_view(page):
    "A step whose mark is far down the page scrolls it into view first: the mark is under the top bar and above the strip."
    page.evaluate("""() => document.body.insertAdjacentHTML('beforeend', '<p data-guide-id="far" style="position:absolute;left:40px;top:2400px;margin:0">Far down the page</p><div style="height:3200px"></div>')""")
    play(page, [dict(say='Look here.', strokes=[dict(op='box', at='far')])])
    page.wait_for_timeout(200)
    r = page.evaluate("(() => { const g = document.querySelector('.board-glow').getBoundingClientRect(), s = document.getElementById('guide-strip'); return [g.top, g.bottom, innerHeight - (s && !s.hidden ? s.offsetHeight : 0)]; })()")
    assert 64 <= r[0] and r[1] <= r[2], r

def test_a_box_on_words_stays_inside_its_line(page):
    "A box on words has at most a quarter line of pad above them, so it does not cover the line above."
    play(page, [dict(say='Look here.', strokes=[dict(op='box', at=dict(a='out', text='tensor([18, 47])'))])])
    g, b = page.evaluate("[parseFloat(document.querySelector('.board-glow').style.top), abhyasaBoard.boxOf({a: 'out', text: 'tensor([18, 47])'})]")
    assert g >= b['y'] - .25 * b['h'] - .5, (g, b)

def test_the_panel_covers_no_text_and_no_mark_at_1400(page):
    "At 1400 by 900 the page column moves left while the panel shows: the panel covers no text of main and no mark. The panel is on paper, in the hand font."
    page.set_viewport_size(dict(width=1400, height=900))
    page.evaluate("""() => { const m = document.querySelector('main'); const p = document.createElement('pre'); p.dataset.guideId = 'm'; p.textContent = 'x = tensor([18, 47, 56]) and more text to the right edge of the column ' + 'y'.repeat(60); p.style.whiteSpace = 'pre-wrap'; m.prepend(p); }""")
    play(page, [dict(say='The values.', strokes=[dict(op='panel', head='Make a question'), dict(op='row', cells=['[18]'], to='47', at=dict(a='m', text='tensor([18, 47, 56])'))])])
    page.wait_for_timeout(400)   # the column moves
    p, m = [page.evaluate(f"(() => {{ const b = document.querySelector('{q}').getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; }})()") for q in ('#board-panel', 'main')]
    assert m[2] <= p[0], (m, p)
    marks = page.evaluate("[...document.querySelectorAll('#board-layer g[data-op=circle]')].map(g => { const b = g.getBoundingClientRect(); return [b.left, b.right]; })")
    assert marks and all(r <= p[0] for _, r in marks)
    assert 'Caveat' in page.evaluate("getComputedStyle(document.querySelector('.board-panel-head')).fontFamily")
    assert page.evaluate("document.fonts.check('25px Caveat')")

def test_code_is_an_anchor(page):
    "The guide reads each `pre` of the page as an anchor `code1` to `code4`, so the board can mark a value in code."
    page.evaluate("""() => { const m = document.querySelector('main') || document.body; const p = document.createElement('pre'); p.textContent = 'assert add_noise_loss([1.0, 1.0], [1.0, -1.0], 0.5, [1.0, 1.0]) == ([1.414, 0.0], 2.0)'; m.prepend(p); }""")
    ctx = page.evaluate('abhyasaGuide.capture()')
    code = [a for a in ctx['anchors'] if a['kind'] == 'code']
    assert code and code[0]['id'] == 'code1' and '[1.0, -1.0]' in code[0]['text']
    b, pre = page.evaluate("[abhyasaBoard.boxOf({a: 'code1', text: '[1.0, -1.0]'}), (r => ({x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height}))(document.querySelector('main pre, body > pre').getBoundingClientRect())]")
    assert b and pre['x'] <= b['x'] and b['x'] + b['w'] <= pre['x'] + pre['w'] + 1 and pre['y'] <= b['y'] <= pre['y'] + pre['h']

LONG = """() => { const m = document.querySelector('main'); const p = document.createElement('pre'); p.dataset.guideId = 'm'; p.style.whiteSpace = 'pre-wrap';
  p.textContent = 'x = tensor([18, 47, 56]) and more text to the right edge of the column ' + 'y'.repeat(60); m.prepend(p); }"""
PANEL_STEP = dict(say='The values.', strokes=[dict(op='panel', title='tensors and targets', head='Make a question'), dict(op='row', cells=['[18]'], to='47', at=dict(a='m', text='tensor([18, 47, 56])'))])

def test_a_panel_is_whole_after_its_pop_in(page):
    "With motion on, a panel that a panel line opens ends at full opacity, with no transform: it never stays faint."
    page.emulate_media(reduced_motion='no-preference')
    page.evaluate(LONG)
    play(page, [PANEL_STEP])
    page.wait_for_timeout(1200)
    assert page.evaluate("getComputedStyle(document.getElementById('board-panel')).opacity") == '1'
    assert page.evaluate("document.getElementById('board-panel').style.transform") == ''

@pytest.mark.parametrize('w', [1280, 1400, 1728])
def test_the_column_moves_and_keeps_its_width(page, w):
    "While the panel shows, the page column moves left into the free gutter with its width kept, the panel covers it not, and the page does not jump."
    page.set_viewport_size(dict(width=w, height=900))
    page.evaluate(LONG)
    box = "(() => { const b = document.querySelector('main').getBoundingClientRect(); return [b.left, b.right, b.width]; })()"
    before = page.evaluate(box)
    play(page, [PANEL_STEP])
    page.wait_for_timeout(300)
    after, y0 = page.evaluate(box), page.evaluate('scrollY')
    pl = page.evaluate("document.getElementById('board-panel').getBoundingClientRect().left")
    assert after[2] == before[2] or w < 1400, (w, before, after)   # at 1280 the gutter can be too small: then it narrows only as much as it must
    assert after[1] <= pl - 23 and page.evaluate("document.body.classList.contains('has-panel')")
    page.wait_for_timeout(800)
    assert page.evaluate('scrollY') == y0
    ring = page.evaluate("(() => { const b = document.querySelector('#board-layer g[data-op=circle]').getBoundingClientRect(); return [b.top, b.bottom]; })()")
    assert 0 <= ring[0] and ring[1] <= 900
    page.evaluate('abhyasaBoard.stop()')
    assert page.evaluate(box) == before   # the column takes its place back

def test_each_step_scrolls_its_marks_into_view(page):
    "Step 3 marks a line above the window: when step 3 starts, the page scrolls it into view."
    page.evaluate("""() => document.body.insertAdjacentHTML('beforeend', '<p data-guide-id="low" style="position:absolute;left:40px;top:2600px;margin:0">Low on the page</p><div style="height:3200px"></div>')""")
    steps = [dict(say='One.', strokes=[dict(op='box', at='low')]), dict(say='Two.', strokes=[dict(op='box', at='low')]), dict(say='Three.', strokes=[dict(op='box', at='card')])]
    play(page, steps)
    page.evaluate('abhyasaBoard.next()'); page.wait_for_function('abhyasaBoard.state.i === 1 && abhyasaBoard.state.done')
    assert page.evaluate('scrollY') > 1500
    page.evaluate('abhyasaBoard.next()'); page.wait_for_function('abhyasaBoard.state.i === 2 && abhyasaBoard.state.done')
    page.wait_for_timeout(200)
    r = page.evaluate("(() => { const g = [...document.querySelectorAll('.board-glow')].find(e => e.dataset.step === '2').getBoundingClientRect(); return [g.top, g.bottom, innerHeight]; })()")
    assert 50 <= r[0] and r[1] <= r[2], r

def test_an_inline_panel_draws_no_curve_back_up(page):
    "Below 1100 px the panel stands in the page under the marked line. A curve goes down from the ring, never back up across the text, and none when the row is right under the ring."
    page.set_viewport_size(dict(width=1024, height=900))
    page.evaluate(LONG)
    play(page, [PANEL_STEP])
    assert page.evaluate("document.getElementById('board-panel').classList.contains('inline')")
    ring = page.evaluate("document.querySelector('#board-layer g[data-op=circle]').getBoundingClientRect().bottom")
    links = page.evaluate("[...document.querySelectorAll('#board-layer g[data-op=link]')].filter(g => g.style.display !== 'none' && g.childElementCount).map(g => g.getBoundingClientRect().top)")
    assert all(t >= ring - 2 for t in links), (ring, links)

def test_at_1280_the_ring_is_above_the_strip(page):
    "At 1280 px, with motion on, the column makes room before the board scrolls: the ring of step 1 ends fully above the strip, and the page does not move after."
    page.set_viewport_size(dict(width=1280, height=900))
    page.emulate_media(reduced_motion='no-preference')
    page.evaluate("""() => document.querySelector('main').insertAdjacentHTML('beforeend', '<div style="height:1400px"></div><pre data-guide-id="m" style="white-space:pre-wrap">x = tensor([18, 47, 56]) and more words that wrap when the column gets narrow ' + 'y'.repeat(120) + '</pre><div style="height:1400px"></div>')""")
    play(page, [PANEL_STEP])
    page.wait_for_timeout(1500)
    y0 = page.evaluate('scrollY')
    r = page.evaluate("(() => { const g = document.querySelector('#board-layer g[data-op=circle]').getBoundingClientRect(), s = document.getElementById('guide-strip'); return [g.top, g.bottom, s.getBoundingClientRect().top]; })()")
    assert 0 <= r[0] and r[1] <= r[2], r
    page.wait_for_timeout(800)
    assert page.evaluate('scrollY') == y0

def test_a_step_that_comes_again_grows_in_place(page):
    "The server sends step 1 with its first mark, then again with its rows. The board keeps step 1 and adds only the new rows; then step 2 comes as a new step."
    s1 = dict(n=1, say='Each test is a question.', strokes=[dict(op='panel', head='Make a question')])
    play(page, [s1], streaming=True)
    assert panel(page)['rows'] == []
    page.evaluate('s => abhyasaBoard.add(s)', {**s1, 'strokes': [*s1['strokes'], row(['[18]'], '47', 'tensor([18])')]})
    page.wait_for_function("document.querySelectorAll('.board-row').length === 1")
    page.evaluate('s => abhyasaBoard.add(s)', {**s1, 'strokes': [*s1['strokes'], row(['[18]'], '47', 'tensor([18])'), row(['[18, 47]'], '56', 'tensor([18, 47])')]})
    page.wait_for_function("document.querySelectorAll('.board-row').length === 2")
    assert page.evaluate('abhyasaBoard.state.steps') == 1
    page.evaluate('s => abhyasaBoard.add(s)', dict(n=2, say='Then it adds up.', strokes=[]))
    assert page.evaluate('abhyasaBoard.state.steps') == 2
