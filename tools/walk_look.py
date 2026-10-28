"""Browser checks of the look of abhyasa (Task 19, design polish), and the screens for the design review.

Run: uv run --all-extras python tools/walk_look.py [--shots] [--out design/screens]
It makes a temporary vault and settings folder, runs the app with the `Fake` model on a free port, and opens it in Playwright's
bundled Chromium (headless, one browser, closed at the end). Each check prints PASS or FAIL; the run fails when one check fails.
`--shots` also takes the screens `polish-<page>-<theme>-<mode>-<width>.png` at 1280 and 1000 px, light and dark, Paper and Signal.
`--only` runs only the checks that it names.
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
        r = rq.post(f'{B}/walk/new', form=dict(text='Ranking orders items by a score. A rank is a position in the list.', title='Ranking notes'),
                    headers={'HX-Request': 'true'}, max_redirects=0)
        self.plan = r.headers['hx-redirect']   # a walk that is not started, so its plan page shows (with the way selects)

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
    pg.goto(w.B + w.plan); settle(pg)
    assert pg.query_selector('.plan select'), 'no plan page'
    assert pg.eval_on_selector('.plan select', "e => getComputedStyle(e).appearance") == 'none'

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

MOVING = """() => [...document.querySelectorAll('body, body *')].flatMap(e => [e, '::before', '::after'].map(p => p === e ? getComputedStyle(e) : getComputedStyle(e, p)))
                 .filter(s => s.animationName != 'none' || parseFloat(s.transitionDuration) > 0).length"""

def reduced_motion(pg, w):
    "With reduced motion, nothing moves: not the step, the end of a walk, nor the side pane, and htmx makes no view transition."
    ctx = pg.context.browser.new_context(viewport=dict(width=1280, height=900), reduced_motion='reduce')
    try:
        p2 = ctx.new_page()
        for u in (w.step(0), walk_to_end(w), f'{w.step(2)}?rh={side_walk(w)}'):
            p2.goto(u); settle(p2)
            assert p2.evaluate(MOVING) == 0, (u, p2.evaluate(MOVING))
        assert p2.evaluate('htmx.config.globalViewTransitions') is False
    finally: ctx.close()

# --- Task 19b: the walk, the side pane and the end of a walk ----------------------------------------------------

def f7_step_lines_up(pg, w):
    "The crumbs start where the outline starts at 1280 px, and at 1000 px nothing goes past the right edge."
    try:
        pg.goto(w.step(2)); pg.wait_for_selector('#check .check'); settle(pg)
        xs = pg.evaluate("() => [document.querySelector('main .crumbs').getBoundingClientRect().left, document.querySelector('.outline').getBoundingClientRect().left]")
        assert abs(xs[0] - xs[1]) < 1, xs
        pg.set_viewport_size(dict(width=1000, height=900)); pg.goto(w.step(2)); pg.wait_for_selector('#check .check'); settle(pg)
        r = pg.evaluate("() => [document.documentElement.scrollWidth, innerWidth, document.querySelector('#check .check').getBoundingClientRect().right]")
        assert r[0] <= r[1] and r[2] <= r[1] - 16, r
    finally: pg.set_viewport_size(dict(width=1280, height=900))

def side_walk(w):
    "A side walk on Derivatives and gradients from step 3, made once; the URL of its first step."
    if not getattr(w, 'side', None):
        w.lr.update('scaling-by-the-root-of-dk', prereqs=['softmax', 'gradients'])
        w.side = w.rq.post(f'{w.B}/rh/open', form=dict(slug='gradients', at=f'{w.jid}/2', how='primer')).json()['url']
    return w.side

def rows(pg, sel='body > nav'):
    "The rows of the top bar: a child that starts under the bottom of the first child is on a new row."
    return pg.eval_on_selector(sel, """n => { const r = [...n.children].filter(e => e.checkVisibility() && e.getBoundingClientRect().width).map(e => e.getBoundingClientRect());
                                          return 1 + r.filter(b => b.top >= r[0].bottom).length; }""")

def f6_pane_layout(pg, w):
    "With the pane open at 1280 px the top bar has one row, the pane shows no outline, and in Signal the bar lines meet; at 1000 px a line names the side walk."
    u = f'{w.step(2)}?rh={side_walk(w)}'
    try:
        for theme in ('paper', 'signal'):
            look(w.rq, w.B, theme, 'light')
            pg.goto(u); pg.wait_for_selector('#rh-pane iframe'); settle(pg, 900)
            assert rows(pg) == 1, (theme, rows(pg))
            assert pg.is_visible('body > nav a.nav-search') and not pg.is_visible('body > nav form'), 'no short Search link beside the pane'
            assert pg.evaluate("() => document.querySelector('body > nav a.nav-search').getBoundingClientRect().right <= document.querySelector('#rh-pane').getBoundingClientRect().left"), 'the Search link goes under the pane'
            fr = pg.frame_locator('#rh-pane iframe'); fr.locator('#check .check').wait_for()
            assert not fr.locator('.outline').is_visible() and '1 of 1' not in fr.locator('main').inner_text()
            assert not pg.is_visible('main > a.rh-narrow'), 'the line for a narrow window shows beside the pane'
            ys = pg.evaluate("() => [document.querySelector('body > nav').getBoundingClientRect().bottom, document.querySelector('#rh-pane .rh-bar').getBoundingClientRect().bottom]")
            assert abs(ys[0] - ys[1]) < 1, (theme, ys)
        look(w.rq, w.B, 'paper', 'light')
        pg.set_viewport_size(dict(width=1000, height=900)); pg.goto(u); settle(pg)
        assert pg.is_visible('main > a.rh-narrow') and 'Derivatives and gradients' in pg.inner_text('main > a.rh-narrow')
        pg.wait_for_selector('#check #ans'); settle(pg)
        assert 'Held while' not in pg.inner_text('#check'), 'the check waits for a pane that does not show'
        assert rows(pg) == 1, rows(pg)
    finally: look(w.rq, w.B, 'paper', 'light'); pg.set_viewport_size(dict(width=1280, height=900))

def f5_way_beside(pg, w):
    "Each unmet need has Learn beside, with no dot at the start of a line; the tip shows under the first passage once; ⌥B opens the offer."
    side_walk(w)
    pg.goto(w.B + '/'); pg.evaluate("localStorage.removeItem('rh-tip')")
    pg.goto(w.step(2)); pg.wait_for_selector('.rh-line'); settle(pg)
    st = pg.eval_on_selector_all('.rh-line .need', """ns => ns.map(n => [n.querySelector('.st').textContent.trim(), !!n.querySelector('.rh-ask'), getComputedStyle(n, '::before').content])""")
    assert st and all(a == (s == '· not learned yet') for s, a, _ in st) and all(b in ('none', 'normal') for *_, b in st), st
    assert pg.is_visible('.rh-tip') and 'press ⌥B' in pg.inner_text('.rh-tip')
    pg.locator('h1.idea').click(); pg.keyboard.press('Alt+b'); pg.wait_for_selector('#rh-offer .rh-way')
    assert not pg.is_visible('.rh-tip'), 'the tip stays after one use'
    pg.goto(w.step(2)); pg.wait_for_selector('.rh-line'); settle(pg)
    assert not pg.query_selector('.rh-tip'), 'the tip shows twice'

def new_walk(w):
    "A new walk on the paper, started, with a short check on each idea. Its id."
    r = w.rq.post(f'{w.B}/walk/new', form=dict(ref=add_paper(w.lr)), headers={'HX-Request': 'true'}, max_redirects=0)
    jid = r.headers['hx-redirect'].split('/')[-1]
    for i in range(3): w.lr.walk_step(jid, i, check=dict(way='words', kind='short', depth=2, why='plain words fit this idea'))
    w.rq.post(f'{w.B}/w/{jid}/start', max_redirects=0)
    return jid

def walk_to_end(w):
    "A second walk on the paper, walked to the end: idea 1 skipped, idea 2 passed, idea 3 skipped. The URL of its last page."
    if not getattr(w, 'end', None):
        jid = new_walk(w)
        w.rq.post(f'{w.B}/w/{jid}/0/next', max_redirects=0)
        w.rq.get(f'{w.B}/w/{jid}/1/check'); w.rq.post(f'{w.B}/w/{jid}/1/answer', form=dict(answer='the rank is a position', confidence='70'))
        w.rq.post(f'{w.B}/w/{jid}/2/next', max_redirects=0)
        w.end = f'{w.B}/w/{jid}/2/done'
    return w.end

def f2_calm_end(pg, w):
    "The end of a walk says You finished the walk, has one dot for each idea, and Back to Today is the one main button."
    pg.goto(walk_to_end(w)); settle(pg)
    assert pg.inner_text('main h1') == 'You finished the walk'
    assert pg.eval_on_selector_all('.walk-dots .d', 'ds => ds.map(d => d.className)') == ['d skipped', 'd done', 'd skipped']
    assert visible_gos(pg) == ['Back to Today ⌥S'], visible_gos(pg)
    assert 'stays at unseen' not in pg.inner_text('main') and 'Well walked' not in pg.inner_text('main')

def m4_calm_finish(pg, w):
    "At the end of a walk, the dots of the ideas you did fill one by one, 60 ms apart, then the sum fades in."
    pg.goto(walk_to_end(w)); settle(pg, 100)
    d = pg.eval_on_selector_all('.walk-dots .d', "ds => ds.map(d => [getComputedStyle(d).animationName, getComputedStyle(d).animationDelay])")
    assert d[1] == ['dot-fill', '0.06s'] and d[0][0] == 'none', d
    assert pg.eval_on_selector('.walk-sum', "e => [getComputedStyle(e).animationName, getComputedStyle(e).animationDelay]") == ['fade', '0.48s']

def m1_next_idea_comes_in_gently(pg, w):
    "Next idea swaps the page in a view transition and the outline does not move; a check answer swaps with no transition."
    jid = new_walk(w)
    pg.goto(f'{w.B}/w/{jid}/1'); pg.wait_for_selector('#check #ans'); settle(pg)
    pg.evaluate("""() => { window.vt = 0; const o = document.startViewTransition.bind(document);
                           document.startViewTransition = f => { window.vt++; return o(f); }; }""")
    x0 = pg.eval_on_selector('#rail', 'e => e.getBoundingClientRect().left')
    pg.fill('#ans', 'it is the rank'); pg.click('#send'); pg.wait_for_selector('#check .check.shut'); settle(pg)
    assert pg.evaluate('window.vt') == 0, 'a check answer made a view transition'
    pg.click('#check .go'); pg.wait_for_url(lambda u: u.endswith(f'/w/{jid}/2'), timeout=10000); settle(pg)
    assert pg.evaluate('window.vt') >= 1, 'Next idea made no view transition'
    assert pg.evaluate("getComputedStyle(document.querySelector('.walk-main')).viewTransitionName") == 'idea'
    assert abs(pg.eval_on_selector('#rail', 'e => e.getBoundingClientRect().left') - x0) < 1
    root = "() => getComputedStyle(document.documentElement, '::view-transition-old(root)').animationName"
    pg.goto(w.B + '/'); settle(pg); pg.click('nav a[href="/graph"]'); pg.wait_for_url('**/graph'); settle(pg)
    assert pg.evaluate(root) == 'none', 'another page crossfades'

ACC = "c => { const d = document.createElement('i'); d.style.color = `var(${c})`; document.querySelector('#check .check').append(d); const v = getComputedStyle(d).color; d.remove(); return v; }"

def m2_check_answers_in_place(pg, w):
    "When a check closes, the tag fades in and a line in the outcome colour grows under the question."
    jid = new_walk(w)
    pg.goto(f'{w.B}/w/{jid}/1'); pg.wait_for_selector('#check #ans'); settle(pg)
    assert pg.eval_on_selector('#check .check > .q', "q => getComputedStyle(q, '::after').content") in ('none', 'normal')   # no line while it is open
    pg.fill('#ans', 'it is the rank'); pg.click('#send'); pg.wait_for_selector('#check .check.shut'); settle(pg, 100)
    line = pg.eval_on_selector('#check .check > .q', "q => { const s = getComputedStyle(q, '::after'); return [s.animationName, s.height, s.backgroundColor]; }")
    assert line[:2] == ['grow', '2px'] and line[2] == pg.evaluate(f"({ACC})('--ok')"), line
    assert pg.eval_on_selector('#check .close > .tag', 'e => getComputedStyle(e).animationName') == 'fade'

def m3_outline_dot_fills(pg, w):
    "When a check closes, the dot of its idea in the outline fills from the centre, and the progress line moves."
    jid = new_walk(w)
    pg.goto(f'{w.B}/w/{jid}/0'); pg.wait_for_selector('#check #ans'); settle(pg)
    w0 = pg.eval_on_selector('#rail-bar', 'e => e.getBoundingClientRect().width')
    pg.fill('#ans', 'it is the rank'); pg.click('#send'); pg.wait_for_selector('#rail-0.just'); settle(pg, 100)
    st = pg.eval_on_selector('#rail-0', "e => [e.className, getComputedStyle(e, '::before').animationName]")
    assert st == ['c done on just', 'dot-grow'], st
    pg.wait_for_timeout(400)
    assert pg.eval_on_selector('#rail-bar', 'e => e.getBoundingClientRect().width') > w0
    assert pg.evaluate("getComputedStyle(document.querySelector('#rail-bar')).transitionProperty") == 'width'

def demo_step(w, fresh=False):
    "A step with a demo check whose passage names two parts of the demo, made once (or a new one when `fresh`). Its URL."
    if fresh or not getattr(w, 'demo', None):
        jid = new_walk(w)
        w.lr.walk_step(jid, 2, check=dict(way='demo', kind='demo', depth=2, why='a demo shows it best'),
                       read={**(w.lr.journey(jid).steps[2].get('read') or {}), 'text': 'Fusion adds up the rank in the keyword search list and in the vector search list.'})
        if fresh: return f'{w.B}/w/{jid}/2'
        w.demo = f'{w.B}/w/{jid}/2'
    return w.demo

def m6_words_point_at_the_demo(pg, w):
    "On a demo step, the words of the passage that name a part of the demo get a dotted line; pointing at one rings that part, and back."
    pg.goto(demo_step(w)); pg.wait_for_selector('#check .walk-demo [data-rk-ready="1"]', timeout=30000); settle(pg)
    pg.wait_for_selector('#passage .mv')
    assert 'Next idea ⌥S' not in visible_gos(pg) and pg.is_visible('.next-bar .skip'), visible_gos(pg)   # Next idea waits for the first prediction
    assert pg.eval_on_selector_all('#passage .mv', 'ms => ms.map(m => m.textContent)') == ['keyword search', 'vector search']
    assert pg.eval_on_selector('#passage .mv', "m => getComputedStyle(m).textDecorationStyle") == 'dotted'
    pg.hover('#passage .mv >> nth=0')
    hot = pg.eval_on_selector_all('.walk-demo .rk-b.mv-hot', 'ns => ns.map(n => n.dataset.rkType)')
    assert hot == ['ranklist'], hot
    assert pg.eval_on_selector('.walk-demo .rk-b.mv-hot', 'n => getComputedStyle(n).boxShadow') != 'none'
    pg.mouse.move(5, 5)
    assert not pg.query_selector('.walk-demo .rk-b.mv-hot')
    pg.hover('.walk-demo .rk-ranklist >> nth=1')
    assert pg.eval_on_selector_all('#passage .mv.hot', 'ms => ms.map(m => m.textContent)') == ['vector search']

def rupaka_settle(pg, w):
    "A demo prediction that the walk does not save leaves the gate open, with the pick, the why and a message; a saved one shows the answer."
    pg.goto(demo_step(w, fresh=True)); pg.wait_for_selector('#check .walk-demo [data-rk-ready="1"]', timeout=30000); settle(pg)
    gate = '#check .walk-demo [data-rupaka]'
    pg.eval_on_selector('#check .walk-demo', "c => { c.dataset.good = c.dataset.demo; c.dataset.demo = 'no-such-demo'; }")   # the server refuses this slug
    pg.click(f'{gate} .opts button >> nth=0')
    why = pg.query_selector(f'{gate} textarea')
    if why: why.fill('my reason')
    pg.click(f'{gate} button.go')
    pg.wait_for_function(f"() => document.querySelector('{gate} .note')?.textContent.includes('did not save')", timeout=10000)
    assert pg.is_visible(f'{gate} button.go') and pg.is_enabled(f'{gate} button.go'), 'the gate did not open again'
    assert not pg.is_visible(f'{gate} .verdict'), 'the answer showed after a failed save'
    assert pg.get_attribute(f'{gate} .opts button >> nth=0', 'aria-checked') == 'true'   # the pick stays
    if why: assert why.input_value() == 'my reason'
    assert 'Next idea ⌥S' not in visible_gos(pg)
    pg.eval_on_selector('#check .walk-demo', 'c => { c.dataset.demo = c.dataset.good; }')
    pg.click(f'{gate} button.go')
    pg.wait_for_selector(f'{gate} .verdict', state='visible', timeout=10000)
    assert not pg.is_visible(f'{gate} .note')
    pg.wait_for_function("() => [...document.querySelectorAll('main .go')].some(e => e.checkVisibility() && e.textContent.includes('Next idea'))", timeout=10000)

def m7_side_walk_returns_you(pg, w):
    "At the end of a side walk the pane slides out to the right, the needs line says learned on the way today, and the draft is still in the answer box."
    jid = new_walk(w)
    w.lr.update('scaling-by-the-root-of-dk', prereqs=['softmax', 'gradients'])
    side = w.rq.post(f'{w.B}/rh/open', form=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url']
    pg.goto(f'{w.B}/w/{jid}/2?rh={side}'); pg.wait_for_selector('#check #ans'); settle(pg)
    pg.fill('#check #ans', 'my draft')
    pane = pg.locator('#rh-pane iframe').element_handle().content_frame()
    pane.wait_for_selector('#check #ans'); pane.fill('#check #ans', 'the slope, a rank of change'); pane.click('#send')
    pane.wait_for_selector('#check .check.shut .go')
    pg.evaluate("""() => { window.left = false; new MutationObserver(() => { if (document.documentElement.classList.contains('rh-leave')) window.left = true; })
                           .observe(document.documentElement, {attributes: true, attributeFilter: ['class']}); }""")
    pane.click('#check .check.shut .go')
    pg.wait_for_function("() => !document.documentElement.classList.contains('rh-open')", timeout=15000)
    assert pg.evaluate('window.left'), 'the pane did not slide out'
    pg.wait_for_function("() => document.querySelector('.rh-needs')?.textContent.includes('learned on the way today')", timeout=10000)
    assert pg.is_visible('.rh-needs.fresh .rh-strip') and pg.eval_on_selector('.rh-needs.fresh .rh-strip', 'e => getComputedStyle(e).animationName') == 'rise'
    assert pg.evaluate("document.activeElement.id") == 'ans' and pg.input_value('#check #ans') == 'my draft'

# --- 19c: the other pages ------------------------------------------------------------------------------------------

def f9_add_asks_for_one_thing(pg, w):
    "Add: a choice of four; only the chosen fields show; the tool box only for a link; one main button; a text walk sends only the text."
    pg.goto(w.B + '/add'); settle(pg, 300)
    shown = lambda: pg.eval_on_selector_all('.add-form fieldset', 'fs => fs.filter(f => f.checkVisibility()).map(f => f.className)')
    assert shown() == ['add-doc'], shown()
    assert not pg.is_visible('input[name=tool]') and visible_gos(pg) == ['Make a walk ⌥S']
    pg.click('.add-form .modes-pick label:has-text("A link")')
    assert shown() == ['add-link'] and pg.is_visible('input[name=tool]')
    assert pg.evaluate('document.activeElement.name') == 'url'
    pg.click('.add-form .modes-pick label:has-text("A text")')
    assert shown() == ['add-text'] and pg.is_visible('text=Find concepts only') and not pg.is_visible('input[name=tool]')
    pg.fill('.add-text textarea', 'Ranking orders items. A rank is a position.')
    with pg.expect_request(lambda r: r.url.endswith('/walk/new') and r.method == 'POST') as rq: pg.click('main .go')
    body = rq.value.post_data or ''
    assert 'name="text"' in body and 'name="url"' not in body and 'name="ref"' not in body, body[:300]
    assert not pg.is_visible('details.more #vr') and pg.is_visible('details.more summary')

def f10_graph_has_more_graph(pg, w):
    "Graph: Find, the layout and the legend show; the other levers are in a closed Adjust the view; an unseen node has the sunken fill in the legend."
    pg.goto(w.B + '/graph'); pg.wait_for_function('() => window.abhyasaGraph', timeout=15000); settle(pg, 300)
    assert pg.is_visible('#levers input[name=q]') and pg.is_visible('#levers .modes') and pg.is_visible('#levers .legend')
    assert not pg.is_visible('#levers input[name=spacing]') and not pg.is_visible('#levers select[name=colorBy]')
    assert pg.eval_on_selector('#levers details.adjust', 'd => d.open') is False
    sunk = pg.evaluate("(() => { const i = document.createElement('i'); i.style.color = 'var(--sunken)'; document.body.append(i); const c = getComputedStyle(i).color; i.remove(); return c; })()")
    assert pg.eval_on_selector('#levers .legend i', 'i => getComputedStyle(i).backgroundColor') == sunk
    pg.click('#levers details.adjust > summary')
    assert pg.is_visible('#levers input[name=spacing]')
    pg.click('#levers details.adjust > summary')

def m5_graph_grows(pg, w):
    "The graph: each idea whose floor moved since the last visit pulses once, a new idea fades in, and a line says how many; a reload shows nothing; with no motion, only the line."
    w.lr.put('Pulse one', 'A concept for the pulse check.', 'ml', slug='pulse-one', prereqs=['ranking'])
    graph = lambda: (pg.goto(w.B + '/graph'), pg.wait_for_function('() => window.abhyasaGraph', timeout=15000))
    line = lambda: pg.text_content('#graph .moved') if pg.query_selector('#graph .moved') else ''
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    graph(); graph()
    assert not errs, errs
    assert line() == '' and pg.evaluate('abhyasaGraph.moved') == []
    w.lr.update('pulse-one', floor=2, seen=1)
    w.lr.put('Pulse two', 'A new concept for the pulse check.', 'ml', slug='pulse-two', prereqs=['pulse-one'])
    graph()
    assert line() == '1 idea moved since your last visit. You have 1 new idea since your last visit.', line()
    assert pg.evaluate('abhyasaGraph.moved') == ['pulse-one'] and pg.evaluate('abhyasaGraph.fresh') == ['pulse-two']
    pg.wait_for_function('() => abhyasaGraph.pulsing', timeout=3000)
    pg.wait_for_function('() => !abhyasaGraph.pulsing', timeout=3000)    # one time, about 600 ms
    graph(); pg.wait_for_timeout(400)
    assert line() == '' and not pg.evaluate('abhyasaGraph.pulsing')       # a reload shows nothing
    pg.emulate_media(reduced_motion='reduce')
    try:
        w.lr.update('pulse-one', floor=3)
        pg.goto(w.B + '/graph'); pg.evaluate("window.seenPulse = false; setInterval(() => { if (window.abhyasaGraph?.pulsing) window.seenPulse = true; }, 10)")
        pg.wait_for_function('() => window.abhyasaGraph', timeout=15000); pg.wait_for_timeout(1000)
        assert line() == '1 idea moved since your last visit.' and not pg.evaluate('window.seenPulse')
        assert pg.eval_on_selector('#graph .moved', 'e => getComputedStyle(e).animationName') in ('none', '') or \
               pg.eval_on_selector('#graph .moved', 'e => parseFloat(getComputedStyle(e).animationDuration)') < .01
    finally: pg.emulate_media(reduced_motion='no-preference')

def f12_today_has_an_order(pg, w):
    "Today: the Continue card, the review line, the journeys, the goal on one line, then the links on one line; no week and no subjects."
    pg.goto(f'{w.B}/s/{w.sid}'); settle(pg, 300)   # the session is open, so the Continue card shows
    pg.goto(w.B + '/'); settle(pg, 300)
    top = lambda sel: pg.eval_on_selector(sel, 'e => e.getBoundingClientRect().top')
    ys = [top(x) for x in ('.continue-card', '.review', 'main h2:has-text("Your journeys")', 'details.goal-fold', 'p.foot')]
    assert ys == sorted(ys), ys
    assert pg.eval_on_selector('details.goal-fold', 'd => d.open') is False and not pg.is_visible('#goal')
    assert pg.eval_on_selector('p.foot', 'e => e.getBoundingClientRect().height') < 40
    assert not pg.query_selector('main h2:has-text("This week")') and not pg.query_selector('main h2:has-text("Subjects")')
    assert visible_gos(pg) == ['Continue ⌥S'], visible_gos(pg)

def f13_profile_invites(pg, w):
    "Profile, empty: one raised card with Start ⌥S; the fields are under a closed Edit by hand; each Speak sits in its label row, and only the first names ⌥D."
    if w.lr.profile().known: return   # the check needs an empty profile
    pg.goto(w.B + '/you'); settle(pg, 300)
    assert pg.is_visible('.raised.invite') and visible_gos(pg) == ['Start ⌥S'], visible_gos(pg)
    assert pg.eval_on_selector('details.by-hand', 'd => d.open') is False and not pg.is_visible('#pf-background')
    pg.click('details.by-hand > summary')
    assert pg.is_visible('label[for=pf-background] .mic.in-label')
    lb, box = (pg.eval_on_selector(x, 'e => { const r = e.getBoundingClientRect(); return [r.top, r.bottom]; }') for x in ('label[for=pf-background]', '#pf-background'))
    mic = pg.eval_on_selector('label[for=pf-background] .mic', 'e => e.getBoundingClientRect().top')
    assert lb[0] - 2 <= mic < box[0], (lb, mic, box)
    assert pg.eval_on_selector_all('.mic.in-label kbd', 'ks => ks.map(k => k.textContent)') == ['⌥D']
    assert pg.eval_on_selector('label[for=pf-background]', 'l => l.textContent.replace(/\\s+/g, " ").trim()').startswith('Background · Speak ⌥D')

CHECKS = [f1_one_main_button_and_alt_s, f3_same_check_card, f4_one_filled_button, f11_native_controls, f14_sheet_lines_up,
          f15_no_ring_until_a_key, f16_signal_why_in_text_font, f17_no_broken_figure, reduced_motion,
          f7_step_lines_up, f6_pane_layout, f5_way_beside, f2_calm_end, m4_calm_finish, m1_next_idea_comes_in_gently, m2_check_answers_in_place, m3_outline_dot_fills,
          m6_words_point_at_the_demo, m7_side_walk_returns_you, rupaka_settle,
          f9_add_asks_for_one_thing, f10_graph_has_more_graph, m5_graph_grows, f12_today_has_an_order, f13_profile_invites]

# --- the screens --------------------------------------------------------------------------------------------------

def screens(pg, w, out, only=None, widths=(1280, 1000), looks=None):
    "Each changed page at 1280 and 1000 px, light and dark, Paper and Signal."
    out.mkdir(parents=True, exist_ok=True)
    w.lr.walk_step(w.jid, 2, check=dict(way='words', kind='short', depth=2, why='plain words fit this idea'))
    pages = dict(today='/', step=w.step(2), code=w.step(1), session=f'/s/{w.sid}', settings='/settings', strengths='/you/strengths',
                 profile='/you', keys='/keys', add='/add', concept='/c/ranking', plan=w.plan, end=f'/w/{w.jid}/0/done',
                 walkend=walk_to_end(w), pane=f'{w.step(2)}?rh={side_walk(w)}', demo=demo_step(w),   # 19b: the end of a walk, the pane (1000 px: the narrow view), a demo
                 graph='/graph', learning='/learning', journeys='/journeys', concepts='/concepts', sources='/sources', search='/search?q=rank')   # 19c
    if only: pages = {k: v for k, v in pages.items() if k in only}
    shots = []
    for theme in ('paper', 'signal'):
        for mode in ('light', 'dark'):
            if looks and f'{theme}-{mode}' not in looks: continue
            look(w.rq, w.B, theme, mode)
            for width in widths:
                pg.set_viewport_size(dict(width=width, height=900))
                for n, u in pages.items():
                    pg.goto(u if u.startswith('http') else w.B + u); settle(pg, 900 if n in ('step', 'code', 'session', 'pane', 'demo', 'walkend', 'graph') else 400)
                    if n == 'demo': pg.wait_for_selector('#passage .mv', timeout=30000); pg.hover('#passage .mv >> nth=0')
                    p = out/f'polish-{n}-{theme}-{mode}-{width}.png'; pg.screenshot(path=str(p), full_page=True); shots.append(p.name)
    look(w.rq, w.B, 'paper', 'auto')
    return shots

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--shots', action='store_true', help='also take the screens')
    ap.add_argument('--out', default=str(ROOT/'design/screens'))
    ap.add_argument('--only', nargs='*', default=None, help='run only the checks with these names')
    ap.add_argument('--pages', nargs='*', default=None, help='take only the screens of these pages')
    ap.add_argument('--looks', nargs='*', default=None, help='take only these looks, for example paper-light')
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
                for c in [c for c in CHECKS if a.only is None or c.__name__ in a.only]:
                    try: c(pg, w); print('PASS', c.__name__, flush=True)
                    except Exception as e: bad += 1; print('FAIL', c.__name__, '-', str(e)[:300], flush=True)
                if a.shots: print(len(screens(pg, w, Path(a.out), a.pages, looks=a.looks)), 'screens in', a.out)
            finally: b.close()
    finally: srv.should_exit = True
    sys.exit(1 if bad else 0)

if __name__ == '__main__': main()
