"""Browser checks of the shared editor list (`core/edit.py`, `edit.js`, `edit.css`) in Chromium and in WebKit, the engine of the Mac app.

Run: uv run --all-extras python tools/edit_look.py [--browser chromium|webkit|both] [--shots DIR]
It serves a small page with one `EditList`, live fields and the `UndoBar` on a free port, and opens it in Playwright's bundled
browsers (headless, one browser at a time, closed at the end). WebKit needs `uv run playwright install webkit` one time.
Each check prints PASS or FAIL; the run fails when one check fails."""
import argparse, os, socket, sys, tempfile, threading, time
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='abhyasa-edit-look-'))
os.environ['ABHYASA_CONFIG'] = str(TMP/'config')   # never the real settings
os.environ.setdefault('LITESEARCH_CACHE', str(TMP/'litesearch'))

from fasthtml.common import *
from abhyasa.core import HDRS, serve_assets
from abhyasa.core.ui import Quiet
from abhyasa.core.edit import EditList, Live, UndoBar, edit_assets

POSTS = []   # (row id, form) of each post that the page sent
ROWS = [dict(id=f's{i}', title=f'Slide {i}', line='passage · 5 min', post=f'/row/s{i}') for i in range(4)]
ORDER = [r['id'] for r in ROWS]

def the_list():
    rs = [{**next(r for r in ROWS if r['id'] == i), 'body': [Label('Title', Live('title', Input(value=i))), Label('Notes', Live('notes', Textarea('n', rows=2)))],
           'acts': [Quiet('Remove', Kbd('X'), type='button', data_key='X', hx_post=f'/row/{i}', hx_vals='{"act": "x"}', hx_swap='none')]} for i in ORDER]
    return EditList(rs, 'talk', add=[Button('Add a slide', Kbd('A'), type='button', data_key='A', hx_post='/row/new', hx_vals='{"act": "add"}', hx_swap='none')], id='slides')

def mk_page():
    app = FastHTML(hdrs=HDRS())
    serve_assets(app)
    @app.get('/')
    def index(): return Title('edit look'), *edit_assets(), Main(H1('Editor'), the_list(), Input(id='outside', aria_label='Outside'), UndoBar(oob=False))
    @app.post('/row/{rid}')
    async def row(rid:str, req):
        f = dict(await req.form()); POSTS.append((rid, f))
        if f.get('act') == 'move':
            ORDER.remove(rid); ORDER.insert(int(f['to']), rid)
            return the_list(), UndoBar(f'Moved “{rid}” to slide {int(f["to"]) + 1}.', '/undo', '/hist', step='e1')
        return UndoBar(f'Did {f.get("act")} on {rid}.', '/undo', '/hist', step='e1')
    @app.post('/undo')
    async def undo(req): POSTS.append(('undo', dict(await req.form()))); return UndoBar('Undone.', '/undo', '/hist')
    return app

def serve(app):
    "Run `app` on a free port in a thread. Return the server and its base URL."
    import uvicorn
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(100):
        if srv.started: break
        time.sleep(.05)
    return srv, f'http://127.0.0.1:{port}'

def run(pg, base, check, shots=None, name=''):
    "The checks on one page."
    meta = 'Meta' if sys.platform == 'darwin' else 'Control'
    ORDER[:] = [r['id'] for r in ROWS]; POSTS.clear()
    pg.goto(base + '/')
    li = lambda i: pg.locator('#slides > li.edit-row').nth(i)
    box = lambda sel: pg.locator(sel).first.bounding_box()
    focused = lambda: pg.evaluate('document.activeElement.dataset.id || document.activeElement.name || ""')
    head, summ = box('#slides > li:nth-child(1) .head'), box('#slides > li:nth-child(1) summary')
    check('layout: the title and Edit are on one line, Edit at the right', abs(head['y'] - summ['y']) < 12 and summ['x'] > head['x'] + 300)
    check('layout: a closed row hides its fields', not pg.locator('#slides > li:nth-child(1) .fields').is_visible())
    check('layout: the grip is in the row, not at the edge of the page', box('#slides > li:nth-child(1) .grip')['x'] > 100)
    li(0).focus(); pg.keyboard.press('s')
    check('S moves the focus down', focused() == 's1')
    pg.keyboard.press('Shift+S'); pg.wait_for_timeout(500)
    check('⇧S posts a move', ('s1', {'act': 'move', 'to': '2'}) in POSTS)
    check('the moved row has the focus', focused() == 's1')
    check('the Undo bar says the move', 'Moved “s1” to slide 3.' in pg.inner_text('#undo-bar') and 'fresh' in pg.get_attribute('#undo-bar', 'class'))
    pg.keyboard.press('e'); pg.wait_for_timeout(100)
    check('E opens the row and puts the focus in its first field', focused() == 'title' and pg.locator('#slides > li.open').count() == 1)
    t, f = box('#slides > li.open .head'), box('#slides > li.open .fields')
    check('layout: the open fields are under the title, as wide as the row', f['y'] > t['y'] + 10 and abs(f['x'] - t['x']) < 12 and f['width'] > 400)
    if shots: pg.screenshot(path=str(Path(shots)/f'edit-open-{name}.png'), full_page=True)
    pg.evaluate('(el => el.setSelectionRange(el.value.length, el.value.length))(document.activeElement)')   # the caret at the end: End does not move it in WebKit on a Mac
    pg.keyboard.press('s')
    v = pg.input_value('#slides > li.open input[name=title]')
    check(f'S types in a field ({v!r})', v == 's1s')
    n = len(POSTS); pg.wait_for_timeout(900)
    check('a live field posts to its row after 600 ms', POSTS[n:] and POSTS[-1][0] == 's1' and POSTS[-1][1].get('act') == 'set' and POSTS[-1][1].get('title') == 's1s')
    n = len(POSTS); pg.keyboard.press(f'{meta}+z'); pg.wait_for_timeout(300)
    check('⌘Z in a field does not press Undo', not any(p[0] == 'undo' for p in POSTS[n:]))
    pg.keyboard.press('Escape'); pg.keyboard.press('Escape'); pg.wait_for_timeout(100)
    check('Esc leaves the field, then closes the row', pg.locator('#slides > li.open').count() == 0 and focused() == 's1')
    pg.keyboard.press(f'{meta}+z'); pg.wait_for_timeout(300)
    check('⌘Z outside a field presses Undo with its step', ('undo', {'step': 'e1'}) in POSTS)
    li(0).locator('summary').click(); li(3).locator('summary').click(); pg.wait_for_timeout(100)
    check('one open row at a time', pg.locator('#slides > li.open').count() == 1 and 'open' in li(3).get_attribute('class'))
    n = len(POSTS); li(3).locator('[data-move="2"]').click(); pg.wait_for_timeout(400)
    check('Move up posts a move', POSTS[n:] and POSTS[n][1] == {'act': 'move', 'to': '2'})
    li(0).focus(); n = len(POSTS); pg.keyboard.press('x'); pg.keyboard.press('a'); pg.wait_for_timeout(300)
    check('X and A press their buttons', [q[1].get('act') for q in POSTS[n:]] == ['x', 'add'])
    ids = lambda: [x.get_attribute('data-id') for x in pg.locator('#slides > li.edit-row').all()]
    before, g, t = ids(), li(0).locator('.grip').bounding_box(), li(2).bounding_box()
    pg.mouse.move(g['x'] + 5, g['y'] + 5); pg.mouse.down(); pg.mouse.move(g['x'] + 5, t['y'] + t['height'] - 4, steps=8); pg.mouse.up(); pg.wait_for_timeout(400)
    check('a drag by the grip moves the row', ids() == [before[1], before[2], before[0], before[3]])
    before, n, g = ids(), len(POSTS), li(0).locator('.grip').bounding_box()
    pg.mouse.move(g['x'] + 5, g['y'] + 5); pg.mouse.down(); pg.mouse.move(g['x'] + 900, g['y'] + 300, steps=8); pg.mouse.up(); pg.wait_for_timeout(300)
    check('a drop outside the list does nothing', ids() == before and len(POSTS) == n)
    n, t = len(POSTS), li(1).locator('.ttl').bounding_box()
    pg.mouse.move(t['x'] + 2, t['y'] + 5); pg.mouse.down(); pg.mouse.move(t['x'] + 2, t['y'] + 200, steps=5); pg.mouse.up(); pg.wait_for_timeout(300)
    check('the row text does not drag', len(POSTS) == n)
    h = pg.evaluate("Math.min(...[...document.querySelectorAll('#slides > li.edit-row')].map(l => l.getBoundingClientRect().height))")
    check('rows are 44 px high at least', h >= 44)

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--browser', choices=('chromium', 'webkit', 'both'), default='both')
    ap.add_argument('--shots', default=None, help='a folder for the screens of the open row')
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    srv, base = serve(mk_page())
    bad = 0
    try:
        with sync_playwright() as p:
            for name in (('chromium', 'webkit') if a.browser == 'both' else (a.browser,)):
                b = getattr(p, name).launch(headless=True)
                try:
                    pg = b.new_page(viewport=dict(width=1280, height=900)); errs = []
                    pg.on('pageerror', lambda e: errs.append(str(e)))
                    def check(what, ok):
                        nonlocal bad
                        print('PASS' if ok else 'FAIL', name, '-', what, flush=True); bad += not ok
                    try: run(pg, base, check, a.shots, name)
                    except Exception as e: check(f'the checks ran to the end ({str(e)[:200]})', False)
                    check('no script errors on the page', not errs)
                finally: b.close()
    finally: srv.should_exit = True
    sys.exit(1 if bad else 0)

if __name__ == '__main__': main()
