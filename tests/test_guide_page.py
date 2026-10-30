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
