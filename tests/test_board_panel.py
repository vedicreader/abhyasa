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
