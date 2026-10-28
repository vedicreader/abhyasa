"""Browser checks of the look of abhyasa (Task 19, design polish), and the screens for the design review.

Run: uv run --all-extras python tools/walk_look.py [--shots] [--out design/screens]
It makes a temporary vault and settings folder, runs the app with the `Fake` model on a free port, and opens it in Playwright's
bundled Chromium (headless, one browser, closed at the end). Each check prints PASS or FAIL; the run fails when one check fails.
`--shots` also takes the screens `polish-<page>-<theme>-<mode>-<width>.png` at 1280 and 1000 px, light and dark, Paper and Signal.
Task 16 adds its own checks to `CHECKS`."""
import argparse, os, socket, sys, tempfile, threading, time
from pathlib import Path

ROOT = Path(__file__).parents[1]
TMP = Path(tempfile.mkdtemp(prefix='abhyasa-look-'))
os.environ['VISHALAKSHI_VAULT'] = os.environ['ABHYASA_VAULT'] = str(TMP/'vault.db')   # never the real vault
os.environ['ABHYASA_CONFIG'] = str(TMP/'config')                                       # nor the real settings
os.environ['ABHYASA_LEELA_FILE'] = str(TMP/'leela'/'serving.json')
for k in ('ABHYASA_STT', 'OPENAI_API_KEY', 'ABHYASA_MODEL'): os.environ.pop(k, None)
sys.path[:0] = [str(ROOT/'tests')]

import abhyasa.voice
abhyasa.voice.RAMABANA_KEYS = TMP/'keys.env'
import rupaka.check
rupaka.check.can_check = lambda: False   # no browser inside the app for a demo check
from rupaka.spec import gallery
from abhyasa.store import temp_learning
from abhyasa.llm import Fake
from abhyasa.app import mk_app
from abhyasa.core.cfg import cfg
from walk_data import EXTRACT_REPLY, EXERCISE, GOOD, add_paper

cfg['leela'] = ''

def grader(p, sp):
    "A grade from the words of the answer: `faster` is a miss with a gap, `rank` or `weight` a pass, anything else a miss."
    ans = p.split("Learner's answer:")[1].split("Learner's think-aloud:")[0].lower()
    if 'faster' in ans: return dict(correct=False, grade=2, first_error='Speed is not the point here.', misconception='', feedback='Think of the slope.', gaps=['gradients'])
    ok = 'rank' in ans or 'weight' in ans
    return dict(correct=ok, grade=8 if ok else 3, first_error='' if ok else 'You add raw scores.', misconception='' if ok else 'scores are comparable',
                feedback='Yes. The position is what counts.' if ok else 'Look at positions.')

def seed():
    "A vault with some concepts and the attention paper, and an app on it with the Fake model."
    ask = Fake({'You grade one answer': grader, 'Give hint level': 'Think about positions.',
                'Teach the smallest step': 'Positions are shared. Check: what if k = 0?',
                'Return JSON: {"concepts"': EXTRACT_REPLY, 'You write a short note': 'Softmax makes weights from scores. Look at what a large score does.',
                'You write one small Python exercise': EXERCISE, 'You design one interactive demo': gallery()['reciprocal-rank-fusion']},
               dflt=dict(question='What does a rank tell you?', answer='Its position.', rubric=['position']))
    lr = temp_learning()
    lr.put('Ranking', 'Order items by a score.', 'ml', order=0)
    lr.put('Reciprocal rank fusion', 'Sum 1/(k + rank) over lists.', 'ml', prereqs=['ranking'], order=1)
    lr.put('Derivatives and gradients', 'The slope of a function at a point, one for each input.', 'ml', slug='gradients')
    return lr, mk_app(lr, ask, transcribe=lambda a, hint='': 'spoken text', hosts=('127.0.0.1', 'localhost'))

def serve(app):
    "Run `app` on a free port in a thread. Return the server and its base URL; the caller stops it with `server.should_exit`."
    import uvicorn
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    threading.Thread(target=srv.run, daemon=True).start()
    end = time.monotonic() + 30
    while not srv.started and time.monotonic() < end: time.sleep(.05)
    return srv, f'http://127.0.0.1:{port}'

def settle(pg, ms=500):
    try: pg.wait_for_load_state('networkidle', timeout=8000)
    except Exception: pass
    pg.wait_for_timeout(ms)

def look(rq, B, theme, mode): rq.post(f'{B}/settings/look', form=dict(theme=theme, mode=mode))

# --- the state that the checks and the screens share --------------------------------------------------------------

class World:
    "The walk, the session and the URLs that the checks use."
    def __init__(self, lr, rq, B):
        self.lr, self.rq, self.B = lr, rq, B
        r = rq.post(f'{B}/walk/new', form=dict(ref=add_paper(lr)), headers={'HX-Request': 'true'}, max_redirects=0)
        self.jid = jid = r.headers['hx-redirect'].split('/')[-1]
        lr.walk_step(jid, 0, check=dict(way='words', kind='short', depth=2, why='plain words fit this idea'))
        lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why='you learn well with code'))
        lr.walk_step(jid, 2, check=dict(way='words', kind='short', depth=2, why='plain words fit this idea'))
        rq.post(f'{B}/w/{jid}/start', max_redirects=0)
        self.sid = rq.get(f'{B}/start?focus=ranking', max_redirects=0).headers['location'].rstrip('/').split('/')[-1]

    def step(self, i): return f'{self.B}/w/{self.jid}/{i}'

def visible_gos(pg): return pg.eval_on_selector_all('main .go', 'els => els.filter(e => e.checkVisibility()).map(e => e.textContent.trim())')

# --- the checks: each takes (pg, w) and raises AssertionError ------------------------------------------------------

def f1_one_main_button_and_alt_s(pg, w):
    "A walk step: while the check is open, Send is the one main button and ⌥S sends; then Next idea is, the skip goes, and ⌥S moves on."
    pg.goto(w.step(0)); pg.wait_for_selector('#check #ans'); settle(pg)
    assert visible_gos(pg) == ['Send ⌥S'], visible_gos(pg)
    assert pg.is_visible('.next-bar .skip') and not pg.query_selector('.next-bar kbd')
    pg.fill('#ans', 'it is the rank'); pg.keyboard.press('Alt+s')
    pg.wait_for_selector('#check .check.shut'); settle(pg)
    assert visible_gos(pg) == ['Next idea ⌥S'], visible_gos(pg)
    assert not pg.is_visible('.next-bar .skip'), 'the skip still shows'
    assert 'Do the check' not in pg.inner_text('main')
    pg.keyboard.press('Alt+s'); pg.wait_for_url(lambda u: not u.endswith('/w/' + w.jid + '/0'), timeout=10000)

def f3_same_check_card(pg, w):
    "The walk and the session draw the check card, the question, your message and First error alike."
    css = """() => { const c = document.querySelector('.check'), q = c.querySelector('.q'), y = c.querySelector('.m.you'), k = c.querySelector('.err .k');
                     const s = e => e && getComputedStyle(e);
                     return [s(c).backgroundColor, s(c).borderRadius, s(c).boxShadow != 'none', s(q).fontSize, y && s(y).alignSelf, y && s(y).textAlign,
                             k && s(k).color, k && s(k).textTransform]; }"""
    pg.goto(w.step(2)); pg.wait_for_selector('#check #ans'); pg.fill('#ans', 'a sum'); pg.click('#send'); pg.wait_for_selector('#check .err'); settle(pg)
    a = pg.evaluate(css)
    pg.goto(f'{w.B}/s/{w.sid}'); pg.wait_for_selector('#ans'); pg.fill('#ans', 'a sum'); pg.click('#send'); pg.wait_for_selector('.check .err'); settle(pg)
    b = pg.evaluate(css)
    assert a == b, (a, b)
    assert a[3] == '21px' and a[4] != 'flex-end' and a[7] == 'none', a

def f4_one_filled_button(pg, w):
    "No page shows two filled buttons."
    for u in ['/', '/journeys', f'/w/{w.jid}', '/settings', '/c/ranking', '/add', '/you/strengths', '/you', '/learning', '/keys']:
        pg.goto(w.B + u); settle(pg, 300)
        n = pg.eval_on_selector_all('main .go', 'els => els.filter(e => e.checkVisibility()).length')
        assert n <= 1, (u, n)

def f11_native_controls(pg, w):
    "Radios, checkboxes and ranges take the accent colour, and a select draws its own arrow."
    pg.goto(w.B + '/you'); settle(pg)
    acc = pg.evaluate("() => { const d = document.createElement('i'); d.style.color = 'var(--acc)'; document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return c; }")
    got = pg.eval_on_selector_all('input[type=checkbox], input[type=radio], input[type=range]', 'els => els.map(e => getComputedStyle(e).accentColor)')
    assert got and set(got) == {acc}, (acc, set(got))
    pg.goto(w.B + f'/w/{w.jid}?plan=1'); settle(pg)
    if pg.query_selector('select'): assert pg.eval_on_selector('select', "e => getComputedStyle(e).appearance") == 'none'

def f14_sheet_lines_up(pg, w):
    "The key column of every group on the sheet starts and ends at the same place."
    pg.goto(w.B + '/keys'); settle(pg)
    xs = pg.eval_on_selector_all('dl.keys', 'els => els.map(e => e.querySelector("dd").getBoundingClientRect().left)')
    assert len(xs) > 3 and max(xs) - min(xs) < 1, xs

def f15_no_ring_until_a_key(pg, w):
    "A main button that takes the cursor when the page loads shows no focus ring; the ring in dark stands 3 px off."
    look(w.rq, w.B, 'paper', 'dark')
    try:
        pg.goto(w.B + '/'); settle(pg)
        st = pg.evaluate("() => { const a = document.activeElement; return [a && a.matches('.go'), a && a.matches(':focus-visible')]; }")
        assert st[1] is not True, st
        off = pg.evaluate("() => { const b = document.querySelector('main .go'); if (!b) return null; b.focus({focusVisible: true}); return getComputedStyle(b).outlineOffset; }")
        assert off in (None, '3px'), off
    finally: look(w.rq, w.B, 'paper', 'light')

def f16_signal_why_in_text_font(pg, w):
    "In Signal, the why line of a check is in the text font, not the mono font of the labels."
    look(w.rq, w.B, 'signal', 'light')
    try:
        pg.goto(w.step(0)); pg.wait_for_selector('#check .lbl .why'); settle(pg)
        f = pg.eval_on_selector('#check .lbl .why', 'e => [getComputedStyle(e).fontFamily, getComputedStyle(e.parentElement).fontFamily]')
        assert 'mono' not in f[0].lower() and f[0] != f[1], f
    finally: look(w.rq, w.B, 'paper', 'light')

def f17_no_broken_figure(pg, w):
    "A figure that does not load is out of sight, with its alt text still in the page."
    pg.goto(w.step(1)); settle(pg, 1500)
    assert pg.query_selector('#figure img'), 'no figure on the step'
    box = pg.eval_on_selector('#figure', 'e => [e.classList.contains("gone"), e.getBoundingClientRect().width, e.querySelector("img").alt]')
    assert box[0] and box[1] <= 1 and box[2], box

def reduced_motion(pg, w):
    "With reduced motion, nothing moves."
    ctx = pg.context.browser.new_context(viewport=dict(width=1280, height=900), reduced_motion='reduce')
    try:
        p2 = ctx.new_page(); p2.goto(w.step(0)); settle(p2)
        names = p2.evaluate("() => [...document.querySelectorAll('main, main *')].map(e => getComputedStyle(e)).filter(s => s.animationName != 'none' || parseFloat(s.transitionDuration) > 0).length")
        assert names == 0, names
    finally: ctx.close()

CHECKS = [f1_one_main_button_and_alt_s, f3_same_check_card, f4_one_filled_button, f11_native_controls, f14_sheet_lines_up,
          f15_no_ring_until_a_key, f16_signal_why_in_text_font, f17_no_broken_figure, reduced_motion]

# --- the screens --------------------------------------------------------------------------------------------------

def screens(pg, w, out):
    "Each changed page at 1280 and 1000 px, light and dark, Paper and Signal."
    out.mkdir(parents=True, exist_ok=True)
    w.lr.walk_step(w.jid, 2, check=dict(way='words', kind='short', depth=2, why='plain words fit this idea'))
    pages = dict(today='/', step=w.step(2), code=w.step(1), session=f'/s/{w.sid}', settings='/settings', strengths='/you/strengths',
                 profile='/you', keys='/keys', add='/add', concept='/c/ranking', plan=f'/w/{w.jid}?plan=1')
    shots = []
    for theme in ('paper', 'signal'):
        for mode in ('light', 'dark'):
            look(w.rq, w.B, theme, mode)
            for width in (1280, 1000):
                pg.set_viewport_size(dict(width=width, height=900))
                for n, u in pages.items():
                    pg.goto(u if u.startswith('http') else w.B + u); settle(pg, 900 if n in ('step', 'code', 'session') else 400)
                    p = out/f'polish-{n}-{theme}-{mode}-{width}.png'; pg.screenshot(path=str(p), full_page=True); shots.append(p.name)
    look(w.rq, w.B, 'paper', 'auto')
    return shots

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--shots', action='store_true', help='also take the screens')
    ap.add_argument('--out', default=str(ROOT/'design/screens'))
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    lr, app = seed()
    srv, B = serve(app)
    bad = 0
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                ctx = b.new_context(viewport=dict(width=1280, height=900), reduced_motion='no-preference')
                pg = ctx.new_page()
                w = World(lr, pg.request, B)
                look(pg.request, B, 'paper', 'light')
                for c in CHECKS:
                    try: c(pg, w); print('PASS', c.__name__, flush=True)
                    except Exception as e: bad += 1; print('FAIL', c.__name__, '-', str(e)[:300], flush=True)
                if a.shots: print(len(screens(pg, w, Path(a.out))), 'screens in', a.out)
            finally: b.close()
    finally: srv.should_exit = True
    sys.exit(1 if bad else 0)

if __name__ == '__main__': main()
