"""Browser checks of the look of abhyasa (Task 19, design polish), and the screens for the design review.

Run: uv run --all-extras python tools/walk_look.py [--shots] [--out design/screens]
It makes a temporary vault and settings folder, runs the app with the `Fake` model on a free port, and opens it in Playwright's
bundled Chromium (headless, one browser, closed at the end). Each check prints PASS or FAIL; the run fails when one check fails.
`--shots` also takes the screens `polish-<page>-<theme>-<mode>-<width>.png` at 1280 and 1000 px, light and dark, Paper and Signal.
`--only` runs only the checks that it names.
Task 16 adds its own checks to `CHECKS`."""
import argparse, os, re, socket, sys, tempfile, threading, time
from pathlib import Path

ROOT = Path(__file__).parents[1]
TMP = Path(tempfile.mkdtemp(prefix='abhyasa-look-'))
os.environ['VISHALAKSHI_VAULT'] = os.environ['ABHYASA_VAULT'] = str(TMP/'vault.db')   # never the real vault
os.environ['ABHYASA_CONFIG'] = str(TMP/'config')                                       # nor the real settings
os.environ['RAMABANA_CONFIG'] = str(TMP/'ramabana.toml')                               # nor the real ramabana config
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

FAKE = None   # the Fake model of the app, so a check can read the prompts

def seed():
    "A vault with some concepts and the attention paper, and an app on it with the Fake model."
    global FAKE
    ask = FAKE = Fake({'You grade one answer': grader, 'Give hint level': 'Think about positions.',
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
    assert pg.eval_on_selector('.walk-demo .rk-b.mv-hot', 'n => getComputedStyle(n).outlineStyle + getComputedStyle(n).outlineOffset') == 'solid4px'
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

def l1_demo_ladder(pg, w):
    """A wrong prediction shows a lesson in another way under the demo, with a quiet link to a simpler demo. A second wrong prediction
    shows the simpler demo behind a quiet button. With one gate, the link makes the simpler demo on demand. Next idea stays the one main button."""
    jid = new_walk(w)
    spec = gallery()['reciprocal-rank-fusion']
    g2 = {**next(b for b in spec['blocks'] if b.get('type') == 'gate'), 'id': 'second', 'prompt': 'Which document comes second after fusion?', 'answer': 'fused.1.id'}
    two, one = (w.lr.journey(jid).steps[k]['slug'] for k in (2, 1))
    w.lr.put_demo({**spec, 'id': f'{two}-two-gates', 'blocks': [*spec['blocks'], g2]}, two)
    w.lr.put_demo({**spec, 'id': f'{one}-one-gate'}, one)
    for k, slug in ((2, two), (1, one)):
        w.lr.record(slug, 'A pass before this check', correct=True, final=True)   # a pass ends the count of the checks before
        w.lr.walk_step(jid, k, check=dict(way='demo', kind='demo', depth=2, why='a demo shows it best'))
    gate = lambda k: f'#check .walk-demo [data-rupaka] .rk-b[data-rk-type="gate"] >> nth={k}'
    def wrong(k, opt):
        pg.click(f'{gate(k)} >> .opts button >> nth={opt}')
        pg.click(f'{gate(k)} >> button.go')
        pg.wait_for_selector(f'{gate(k)} >> .verdict', state='visible', timeout=10000)
    own = lambda: pg.eval_on_selector_all('#ladder .go', 'els => els.filter(e => e.checkVisibility() && !e.closest("[data-rupaka]")).length')
    def calm(): assert 'Next idea ⌥S' in visible_gos(pg) and not own() and pg.is_visible('#passage'), visible_gos(pg)   # the help adds no main button
    # two gates: the lesson, then the simpler demo on the second wrong prediction
    pg.goto(f'{w.B}/w/{jid}/2'); pg.wait_for_selector('#check .walk-demo [data-rk-ready="1"]', timeout=30000); settle(pg)
    wrong(0, 0)
    pg.wait_for_selector('#ladder .lesson', timeout=15000)
    assert 'Positions are shared.' in pg.inner_text('#ladder') and pg.text_content('#ladder .lbl').startswith('Lesson · ')
    assert pg.is_visible('#ladder button[hx-post$="simpler=1"]'); calm()
    wrong(1, 2)
    pg.wait_for_selector('#ladder button[hx-get$="show=1"]', timeout=20000)
    assert 'Positions are shared.' in pg.inner_text('#ladder'); calm()
    pg.click('#ladder button[hx-get$="show=1"]')
    pg.wait_for_selector('#ladder[data-demo] [data-rk-ready="1"]', timeout=30000)
    small = pg.get_attribute('#ladder', 'data-demo')
    assert w.lr.demo(small).aim == 'simpler'; calm()
    g = '#ladder [data-rupaka] .rk-b[data-rk-type="gate"]'
    pg.eval_on_selector('#check .said', 'e => { e.textContent = ""; }')
    pg.click(f'{g} >> .opts button >> nth=3'); pg.click(f'{g} >> button.go')
    pg.wait_for_selector(f'{g} >> .verdict', state='visible', timeout=10000)
    pg.wait_for_function("() => document.querySelector('#check .said')?.textContent.includes('saved')", timeout=10000)
    assert w.lr.attempts(two, limit=1)[0].demo == small                        # a prediction in the simpler demo goes in with its own slug
    # one gate: the quiet link under the lesson makes the simpler demo on demand
    pg.goto(f'{w.B}/w/{jid}/1'); pg.wait_for_selector('#check .walk-demo [data-rk-ready="1"]', timeout=30000); settle(pg)
    wrong(0, 0)
    pg.wait_for_selector('#ladder button[hx-post$="simpler=1"]', timeout=15000); calm()
    pg.click('#ladder button[hx-post$="simpler=1"]')
    pg.wait_for_selector('#ladder[data-demo] [data-rk-ready="1"]', timeout=30000)
    assert w.lr.demo(pg.get_attribute('#ladder', 'data-demo')).aim == 'simpler' and 'Positions are shared.' in pg.inner_text('#ladder'); calm()

def fb1_not_clear_note_reaches_the_simpler_demo(pg, w):
    """Under a demo, the quiet feedback row: pick "Not clear", type a note and send it. The row keeps only the thanks and a quiet
    "Show a simpler demo". That button makes the simpler demo, and its prompt holds the note. Next idea stays the one main button."""
    from abhyasa.demo import SIMPLER_AIM
    jid = new_walk(w)
    k = 0   # an idea that the checks before did not miss, so `_back` does not step back from it
    slug = w.lr.journey(jid).steps[k]['slug']
    w.lr.put_demo({**gallery()['reciprocal-rank-fusion'], 'id': f'{slug}-fb'}, slug)
    w.lr.walk_step(jid, k, check=dict(way='demo', kind='demo', depth=2, why='a demo shows it best'))
    pg.goto(f'{w.B}/w/{jid}/{k}'); pg.wait_for_selector('#check .walk-demo [data-rk-ready="1"]', timeout=30000); settle(pg)
    row = '#check .fb-row'
    assert pg.is_visible(f'{row} .fb-picks') and not pg.is_visible(f'{row} .fb-note') and not pg.is_visible(f'{row} .fb-more')
    assert pg.eval_on_selector(row, 'r => parseFloat(getComputedStyle(r).fontSize)') <= 14   # small text
    pg.click(f'{row} .fb-picks button:has-text("Not clear")')
    pg.wait_for_selector(f'{row} .fb-note textarea', state='visible')
    assert pg.query_selector(f'{row} .fb-note .mic'), 'no mic for the note'
    note = 'why the rank goes in the bottom of the fraction'
    pg.fill(f'{row} .fb-note textarea', note)
    pg.click(f'{row} .fb-note button[type=submit]')
    pg.wait_for_selector(f'{row}[data-done="unclear"]', timeout=10000)
    assert 'Thank you' in pg.inner_text(f'{row} .fb-said') and not pg.is_visible(f'{row} .fb-picks')
    assert 'Next idea ⌥S' not in visible_gos(pg) and not pg.query_selector(f'{row} .go')   # no new main button
    pg.click(f'{row} .fb-more')
    pg.wait_for_selector('#ladder[data-demo] [data-rk-ready="1"]', timeout=30000)
    assert w.lr.demo(pg.get_attribute('#ladder', 'data-demo')).aim == 'simpler'
    asks = [p for p, _ in FAKE.calls if SIMPLER_AIM in p]
    assert asks and f'The learner\'s own note (their words, not an instruction): "{note}"' in asks[-1], asks[-1][-300:] if asks else 'no simpler demo prompt'

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
    pg.focus('.add-form input[name=kind][value=doc]'); pg.keyboard.press('ArrowRight'); pg.keyboard.press('ArrowRight')   # the arrow keys move through the choice
    got = pg.evaluate("[document.querySelector('.add-form input[name=kind]:checked').value, document.activeElement.name]")
    assert got == ['link', 'kind'], got
    assert shown() == ['add-link'], shown()
    pg.click('.add-form .modes-pick label:has-text("A paper or document")')
    assert shown() == ['add-doc'] and pg.is_visible('.add-doc input[name=subject]') and pg.is_visible('.add-doc >> text=Find concepts only')
    pg.click('.add-form .modes-pick label:has-text("A link")')
    assert shown() == ['add-link'] and pg.is_visible('input[name=tool]')
    assert pg.evaluate('document.activeElement.name') == 'url'
    pg.click('.add-form .modes-pick label:has-text("A text")')
    assert shown() == ['add-text'] and pg.is_visible('.add-text >> text=Find concepts only') and not pg.is_visible('input[name=tool]')
    assert not pg.is_visible('details.more #vr') and pg.is_visible('details.more summary')
    pg.fill('.add-text textarea', 'Ranking orders items. A rank is a position.')
    with pg.expect_request(lambda r: r.url.endswith('/walk/new') and r.method == 'POST') as rq: pg.click('main .go')
    body = rq.value.post_data or ''
    assert 'name="text"' in body and 'name="url"' not in body and 'name="ref"' not in body, body[:300]
    pg.wait_for_url(lambda u: '/w/' in u, timeout=30000); settle(pg, 200)   # the walk opens; wait, so the next check's page load is not cut off

def f10_graph_has_more_graph(pg, w):
    "Graph: Find, the layout and the legend show; the other levers are in a closed Adjust the view; an unseen node has the raised fill in the legend."
    pg.goto(w.B + '/graph'); pg.wait_for_function('() => window.abhyasaGraph', timeout=15000); settle(pg, 300)
    assert pg.is_visible('#levers input[name=q]') and pg.is_visible('#levers .modes') and pg.is_visible('#levers .legend')
    assert not pg.is_visible('#levers input[name=spacing]') and not pg.is_visible('#levers select[name=colorBy]')
    assert pg.eval_on_selector('#levers details.adjust', 'd => d.open') is False
    assert pg.is_visible('#focus-name')   # the E hint changes on E, so it shows outside the fold
    fill = pg.evaluate("(() => { const i = document.createElement('i'); i.style.color = 'var(--raised)'; document.body.append(i); const c = getComputedStyle(i).color; i.remove(); return c; })()")
    assert pg.eval_on_selector('#levers .legend i', 'i => getComputedStyle(i).backgroundColor') == fill
    pg.click('#levers details.adjust > summary')
    assert pg.is_visible('#levers input[name=spacing]')
    pg.click('#levers details.adjust > summary')

def m5_graph_grows(pg, w):
    "The graph: each idea whose floor went up since the last visit pulses once, a new idea fades in, and a line says how many; a reload shows nothing; with no motion, only the line."
    w.lr.put('Pulse one', 'A concept for the pulse check.', 'ml', slug='pulse-one', prereqs=['ranking'])
    graph = lambda: (pg.goto(w.B + '/graph'), pg.wait_for_function('() => window.abhyasaGraph', timeout=15000))
    line = lambda: pg.text_content('#graph .moved') if pg.query_selector('#graph .moved') else ''
    graph(); graph()
    assert line() == '' and pg.evaluate('abhyasaGraph.rose') == []
    w.lr.update('pulse-one', floor=2, seen=1)
    w.lr.put('Pulse two', 'A new concept for the pulse check.', 'ml', slug='pulse-two', prereqs=['pulse-one'])
    graph()
    assert line() == '1 idea went up since your last visit. You have 1 new idea since your last visit.', line()
    assert pg.evaluate('abhyasaGraph.rose') == ['pulse-one'] and pg.evaluate('abhyasaGraph.fresh') == ['pulse-two']
    pg.wait_for_function('() => abhyasaGraph.pulsing', timeout=3000)
    pg.wait_for_function('() => !abhyasaGraph.pulsing', timeout=3000)    # one time, about 600 ms
    graph(); pg.wait_for_timeout(400)
    assert line() == '' and not pg.evaluate('abhyasaGraph.pulsing')       # a reload shows nothing
    pg.emulate_media(reduced_motion='reduce')
    try:
        w.lr.update('pulse-one', floor=3)
        pg.goto(w.B + '/graph'); pg.evaluate("window.seenPulse = false; setInterval(() => { if (window.abhyasaGraph?.pulsing) window.seenPulse = true; }, 10)")
        pg.wait_for_function('() => window.abhyasaGraph', timeout=15000); pg.wait_for_timeout(1000)
        assert line() == '1 idea went up since your last visit.' and not pg.evaluate('window.seenPulse')
        assert pg.eval_on_selector('#graph .moved', 'e => getComputedStyle(e).animationName') in ('none', '') or \
               pg.eval_on_selector('#graph .moved', 'e => parseFloat(getComputedStyle(e).animationDuration)') < .01
    finally: pg.emulate_media(reduced_motion='no-preference')
    w.lr.update('pulse-one', floor=1)   # a floor that went down: its colour only, no line and no pulse
    graph(); pg.wait_for_timeout(400)
    assert line() == '' and pg.evaluate('abhyasaGraph.rose') == [] and not pg.evaluate('abhyasaGraph.pulsing')

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
    w.lr.clear_profile()   # start from an empty profile, so the check cannot pass without checking
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
    w.lr.set_profile(by='you', why='the look check', background=['nurse'])   # a known profile: the fields open, Save is the main button, no card
    try:
        pg.goto(w.B + '/you'); settle(pg, 300)
        assert not pg.query_selector('.raised.invite') and not pg.query_selector('details.by-hand') and pg.is_visible('#pf-background')
        assert visible_gos(pg) == ['Save ⌥S'], visible_gos(pg)
        assert pg.is_visible('text=Clear what abhyasa knows about you')
    finally: w.lr.clear_profile()

# --- Task 16: the walk page, the side pane keys, a bad pane address and Open in Leela -------------------------------------

NO_SCROLL = 'document.documentElement.scrollWidth <= innerWidth'

def rh_now(pg): return pg.evaluate("new URLSearchParams(location.search).get('rh')")

def t16_step_page_parts(pg, w):
    "A code step at 1280 px has the outline, the passage and the code editor, no sideways scroll; ⌥F opens the shortcuts."
    pg.goto(w.step(1)); pg.wait_for_selector('#check .code-editor'); settle(pg)
    for sel in ('#rail', '#passage', '#check .code-editor'): assert pg.is_visible(sel), sel
    assert pg.evaluate('document.documentElement.scrollWidth') <= 1280 and pg.evaluate(NO_SCROLL)
    pg.locator('h1.idea').click(); pg.keyboard.press('Alt+f'); pg.wait_for_url('**/keys', timeout=10000)

def t16_side_walk_by_key(pg, w):
    "On step 3, ⌥B opens the offer and 2 opens the side walk in the pane; rh is a local path; ⌥Z closes it, drops rh and puts the focus on the check."
    side_walk(w)
    pg.goto(w.step(2)); pg.wait_for_selector('.rh-line'); settle(pg)
    pg.locator('h1.idea').click(); pg.keyboard.press('Alt+b'); pg.wait_for_selector('#rh-offer .rh-way')
    pg.keyboard.press('2'); pg.wait_for_selector('#rh-pane iframe', timeout=15000); settle(pg, 700)
    rh = rh_now(pg)
    assert rh and rh.startswith('/') and not rh.startswith('//') and '://' not in rh, rh
    assert pg.evaluate(NO_SCROLL), 'sideways scroll with the pane open'
    pg.locator('h1.idea').click(); pg.keyboard.press('Alt+z')
    pg.wait_for_function("() => !document.documentElement.classList.contains('rh-open')", timeout=10000); settle(pg, 700)
    assert rh_now(pg) is None, rh_now(pg)
    assert pg.evaluate("!!document.activeElement.closest('#check')"), pg.evaluate('document.activeElement.outerHTML.slice(0, 80)')

def t16_pane_refuses_other_places(pg, w):
    "?rh=https://evil.example/ draws no pane; a message from the main page that names another site leaves rh as it was."
    pg.goto(f'{w.step(2)}?rh=https://evil.example/'); settle(pg, 500)
    assert not pg.query_selector('#rh-pane'), 'a pane for another site'
    pg.goto(f'{w.step(2)}?rh={side_walk(w)}'); pg.wait_for_selector('#rh-pane iframe'); settle(pg, 700)
    before = rh_now(pg)
    assert before and before.startswith('/'), before
    pg.evaluate("window.postMessage({type: 'rh:at', url: 'https://evil.example/'}, '*')"); pg.wait_for_timeout(500)
    assert rh_now(pg) == before, (before, rh_now(pg))

def t16_narrow_side_walk_same_tab(pg, w):
    "At 1000 px, ⌥B and 2 open the side walk in this tab, with Back to the paper at the top."
    side_walk(w)
    try:
        pg.set_viewport_size(dict(width=1000, height=900))
        pg.goto(w.step(2)); pg.wait_for_selector('.rh-line'); settle(pg)
        pages = len(pg.context.pages)
        pg.locator('h1.idea').click(); pg.keyboard.press('Alt+b'); pg.wait_for_selector('#rh-offer .rh-way')
        pg.keyboard.press('2'); pg.wait_for_url(lambda u: f'/w/{w.jid}/2' not in u, timeout=15000); settle(pg, 500)
        assert len(pg.context.pages) == pages and not pg.query_selector('#rh-pane'), 'the side walk did not open in this tab'
        ys = pg.evaluate("() => { const a = [...document.querySelectorAll('a')].find(a => a.textContent.includes('Back to the paper')); return a && [a.getBoundingClientRect().top, document.querySelector('h1').getBoundingClientRect().top]; }")
        assert ys and ys[0] < ys[1], ys   # the line is above the title
    finally: pg.set_viewport_size(dict(width=1280, height=900))

def t16_open_in_leela(pg, w):
    "With an address file, a code step of a tool walk has Open in Leela with target=_blank; with none, a muted line and Get Leela, and no link to /learn."
    from abhyasa.core.leela import leela_address
    from walk_data import leela_file
    jid = new_walk(w); w.lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why='you learn well with code'), leela=True)
    u, f = f'{w.B}/w/{jid}/1', leela_address()
    try:
        leela_file(f.parents[1]); pg.goto(u); pg.wait_for_selector('#check .code-editor'); settle(pg)
        a = pg.query_selector('.leela-line a:has-text("Open in Leela")')
        assert a, 'no Open in Leela link'
        assert 'Open in Leela' in a.inner_text() and a.get_attribute('target') == '_blank' and '/learn' in a.get_attribute('href'), (a.inner_text(), a.get_attribute('href'))
        f.unlink(); pg.goto(u); pg.wait_for_selector('#check .code-editor'); settle(pg)
        assert pg.query_selector('.leela-line.muted') and pg.is_visible('.leela-line >> text=Get Leela')
        bad = pg.eval_on_selector_all('a[href*="/learn?"]', 'as => as.map(a => a.outerHTML)')
        assert not bad, bad
    finally: f.unlink(missing_ok=True)

# --- Task 19d: the last design faults -----------------------------------------------------------------------------

CONT = """() => { const c = document.querySelector('body > nav #continue'); if (!c || !c.checkVisibility()) return 'hidden';
                 return c.scrollWidth <= c.clientWidth || c.clientWidth >= 8 * parseFloat(getComputedStyle(c).fontSize) ? 'room' : 'cut'; }"""

def d1_narrow_band(pg, w):
    "At 1000 px the outline is one line over the title that opens on a click, the title stays near the top, and Continue never shows as 'C…'."
    try:
        pg.goto(w.step(2)); pg.wait_for_selector('#check .check'); settle(pg)
        assert pg.is_visible('#rail ol li.c'), 'the outline does not show at 1280 px'
        pg.eval_on_selector('#rail summary', 's => s.click()'); assert pg.is_visible('#rail ol li.c'), 'a click closes the outline at 1280 px'
        pg.set_viewport_size(dict(width=1000, height=900))
        for u in (w.step(2), f'/s/{w.sid}', '/graph'):
            pg.goto(u if u.startswith('http') else w.B + u); settle(pg)
            assert pg.evaluate(CONT) != 'cut', (u, 'Continue is cut')
        pg.goto(w.step(2)); pg.wait_for_selector('#check .check'); settle(pg)
        assert pg.evaluate(CONT) != 'cut' and pg.eval_on_selector('#continue', 'c => !!c') is True
        assert not pg.is_visible('#rail ol li.c') and pg.text_content('#rail summary').startswith('The paper · 3 of 3'), pg.text_content('#rail summary')
        assert pg.is_visible('#rail-prog'), 'no progress line in the folded outline'
        top = pg.eval_on_selector('h1.idea', 'h => h.getBoundingClientRect().top')
        assert top < 260, f'the title starts at y = {top}'
        pg.click('#rail summary'); assert pg.is_visible('#rail ol li.c'), 'a click does not open the outline'
        with pg.expect_navigation(): pg.keyboard.press('Alt+c')   # ⌥C still works when Continue does not show
        settle(pg, 200)
    finally: pg.set_viewport_size(dict(width=1280, height=900))

def d2_pane_bar(pg, w):
    "The pane bar shows the whole place, `Idea 3 › Derivatives and gradients`, and under it `Side walk · 1 of 1` with the thin line; the bar lines still meet."
    pg.goto(f'{w.step(2)}?rh={side_walk(w)}'); pg.wait_for_selector('#rh-pane iframe')
    pg.frame_locator('#rh-pane iframe').locator('#check .check').wait_for(); settle(pg, 900)
    t = pg.eval_on_selector('#rh-pane .rh-trail', 't => [t.textContent, t.scrollWidth <= t.clientWidth]')
    assert t == ['Idea 3›Derivatives and gradients', True], t
    assert pg.text_content('#rh-pane .rh-pace span') == 'Side walk · 1 of 1' and pg.is_visible('#rh-pane .rh-pace .prog')
    fr = pg.frame_locator('#rh-pane iframe').locator('#rail-prog')
    done, total = fr.get_attribute('aria-valuenow'), fr.get_attribute('aria-valuemax')
    assert pg.get_attribute('#rh-pane .rh-pace .prog', 'aria-valuenow') == done and pg.get_attribute('#rh-pane .rh-pace .prog', 'aria-valuemax') == total
    ys = pg.evaluate("() => [document.querySelector('body > nav').getBoundingClientRect().bottom, document.querySelector('#rh-pane .rh-bar').getBoundingClientRect().bottom]")
    assert abs(ys[0] - ys[1]) < 1, ys

def d3_one_button_in_a_list(pg, w):
    "Journeys and Your learning: one button in the list; the other rows show a quiet Continue → only on hover or focus; no Open."
    new_walk(w)   # a second journey, and two open sessions with an answer
    row = [dict(concept='ranking', correct=True, depth=1, question='What does a rank tell you?', turns=[])]
    for k in (1, 2): w.lr.log_session(f'look-open-{k}', f'An open session, number {k}.', start=time.time() - 60 * k, updated=time.time() - 60 * k, log=row)
    for u, row in (('/journeys', '.jrow'), ('/learning', '.runs li')):
        pg.goto(w.B + u); settle(pg)
        assert pg.eval_on_selector_all(f'{row} .btn:not(.quiet)', 'bs => bs.length') == 1, u
        assert not pg.query_selector(f'{row} a:text-is("Open")'), u
        ons = pg.query_selector_all(f'{row} .onward')
        assert ons, (u, 'no quiet link')
        assert ons[0].evaluate('a => getComputedStyle(a).opacity') == '0', u
        ons[0].evaluate("a => a.closest('li').querySelector('a').focus()"); pg.wait_for_timeout(300)
        assert ons[0].evaluate('a => getComputedStyle(a).opacity') == '1', (u, 'the quiet link does not show on focus')

ROW = """() => ['#mic', '#conf', '#idk', '#hint', '#send'].map(s => document.querySelector('#composer ' + s)).map(e => e && e.checkVisibility() ? e.getBoundingClientRect() : null)
                  .map(r => r && [Math.round(r.top + r.height / 2), Math.round(r.left), Math.round(r.right)])"""

def d4_session_bar_one_row(pg, w):
    "The session answer bar is one row at 1280 and 1000 px: Speak (no box), Sure?, Teach me, Hint, Send last; ⌥S sends."
    sid = w.rq.get(f'{w.B}/start?focus=reciprocal-rank-fusion', max_redirects=0).headers['location'].rstrip('/').split('/')[-1]
    try:
        for width in (1280, 1000):
            pg.set_viewport_size(dict(width=width, height=900)); pg.goto(f'{w.B}/s/{sid}'); pg.wait_for_selector('#composer #send'); settle(pg)
            r = pg.evaluate(ROW)
            assert all(r), (width, r)
            assert max(y for y, *_ in r) - min(y for y, *_ in r) <= 8, (width, 'not one row', r)
            assert [x for _, x, _ in r] == sorted(x for _, x, _ in r) and r[-1][2] == max(x for *_, x in r), (width, 'Send is not last', r)
            edge = pg.eval_on_selector('#composer #ans', 'a => a.getBoundingClientRect().right')
            assert r[-1][2] <= edge + 1, (width, 'Send goes past the box', r[-1][2], edge)
            assert pg.eval_on_selector('#composer #mic', "m => getComputedStyle(m).borderTopColor === 'rgba(0, 0, 0, 0)' || getComputedStyle(m).borderTopStyle === 'none'"), 'Speak has a box'
        n = pg.eval_on_selector_all('.check .thread > .m', 'ms => ms.length')
        pg.fill('#ans', 'a sum'); pg.keyboard.press('Alt+s')   # a miss: the row also holds the tries that are left
        pg.wait_for_function(f"document.querySelectorAll('.check .thread > .m').length > {n}", timeout=10000)
        pg.wait_for_selector('#composer #left:not(:empty)'); settle(pg, 300)
        r, edge = pg.evaluate(ROW), pg.eval_on_selector('#composer #ans', 'a => a.getBoundingClientRect().right')
        assert max(y for y, *_ in r) - min(y for y, *_ in r) <= 8 and r[-1][2] <= edge + 1, ('the row with the tries left', r, edge)
    finally: pg.set_viewport_size(dict(width=1280, height=900))

LUM = "c => { const x = document.createElement('canvas').getContext('2d'); x.fillStyle = c; x.fillRect(0, 0, 1, 1); const [r, g, b] = x.getImageData(0, 0, 1, 1).data; return .2126 * r + .7152 * g + .0722 * b; }"   # any CSS colour, as sRGB

def d5_small_faults(pg, w):
    "Settings says 1 day; the concept page says not learned yet; a weak spot gives a reason, not its recall; in dark, an unseen graph node is lighter than the page."
    pg.goto(w.B + '/settings'); settle(pg, 200)
    assert 'default 1 days' not in pg.inner_text('main') and 'default 1 day' in pg.inner_text('main')
    pg.goto(w.B + '/c/ranking'); settle(pg, 200)
    head = pg.inner_text('main h1 + p')
    assert 'floor' not in head and ('not learned yet' in head or 'level:' in head), head
    w.lr.update('reciprocal-rank-fusion', misses=1, seen=1, last=time.time(), stability=30.)   # one miss and a high recall
    pg.goto(w.B + '/you/strengths'); settle(pg, 200)
    assert pg.query_selector_all('.weak .concepts > li'), 'no weak spot'
    for li in pg.query_selector_all('.weak .concepts > li'):
        t = li.inner_text()
        assert li.query_selector('.why li') and not re.search(r'^\s*recall \d+%', t, re.M), t
    try:
        look(w.rq, w.B, 'paper', 'dark')
        pg.goto(w.B + '/graph'); pg.wait_for_function('() => window.abhyasaGraph', timeout=15000); settle(pg, 300)
        node = pg.eval_on_selector('#levers .legend i', f"i => ({LUM})(getComputedStyle(i).backgroundColor)")
        page = pg.evaluate(f"({LUM})(getComputedStyle(document.body).backgroundColor)")
        assert node > page, ('an unseen node is darker than the page', node, page)
    finally: look(w.rq, w.B, 'paper', 'light')

def s1_source_link_opens_the_pane(pg, w):
    "In a session, a vault source under the lesson opens the document in the side pane, in its pane form; it stays a real link to a new tab; Esc closes the pane."
    d = w.lr.vault.add([(0, 'Ranking puts the items in order. The rank of an item is its position in the list.')], 'Ranking in my notes',
                       source='/tmp/ranking-notes.pdf', kind='pdf')['doc_id']
    sid = w.rq.get(f'{w.B}/start?focus=ranking', max_redirects=0).headers['location'].rstrip('/').split('/')[-1]
    pg.goto(f'{w.B}/s/{sid}'); pg.wait_for_selector('#composer #send'); settle(pg)
    pg.fill('#ans', 'its rank, a position'); pg.keyboard.press('Alt+s')
    a = pg.wait_for_selector(f'.cites a[href="/v/store/{d}"]', timeout=15000)
    assert a.get_attribute('target') == '_blank' and a.get_attribute('data-pane') == f'/v/store/{d}?pane=1', a.evaluate('a => a.outerHTML')
    a.click(); pg.wait_for_selector('#rh-pane iframe', timeout=10000); settle(pg, 700)
    assert rh_now(pg) == f'/v/store/{d}' and f'/s/{sid}' in pg.url, (pg.url, rh_now(pg))
    fr = pg.frame_locator('#rh-pane iframe')
    fr.locator('main h1').wait_for()
    assert fr.locator('main h1').text_content() == 'Ranking in my notes' and fr.locator('body > nav').count() == 0
    assert pg.text_content('#rh-pane .rh-trail b') == 'Ranking in my notes'
    pg.locator('main').first.click(position=dict(x=5, y=5)); pg.keyboard.press('Escape')
    pg.wait_for_function("() => !document.documentElement.classList.contains('rh-open')", timeout=10000)
    assert rh_now(pg) is None and f'/s/{sid}' in pg.url, pg.url

PNG = bytes.fromhex('89504e470d0a1a0a0000000d4948445200000001000000010806000000'
                    '1f15c4890000000d49444154789c63f8cfc0f01f0005000201a5f6e1d70000000049454e44ae426082')   # one pixel

def s2_document_shows_its_images(pg, w):
    "A document page shows the images that its text names from its assets folder; an image that is not there leaves no broken box."
    d = w.lr.vault.add([(2, 'Aries is a fire sign.\n\n![Image 1 from page 2](images/page2_1.png)\n\n![Image 2 from page 2](images/page2_2.png)\n\n'
                            '![Other](../attention/images/fig2.png)')], 'Rasi Characteristics', source='/tmp/vr/Rasi-Characteristics.pdf', kind='pdf')['doc_id']
    f = w.lr.vault.assets('Rasi-Characteristics')/'images'/'page2_1.png'
    f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(PNG)
    pg.goto(f'{w.B}/v/store/{d}'); pg.wait_for_selector('.md.doc'); settle(pg, 700)
    imgs = pg.eval_on_selector_all('.md.doc img', 'is => is.map(i => [i.getAttribute("src"), i.alt, i.complete && i.naturalWidth > 0])')
    assert imgs == [[f'/v/store/{d}/img?f=images/page2_1.png', 'Image 1 from page 2', True]], imgs
    assert 'Image 2 from page 2' not in pg.inner_text('main') and 'Other' not in pg.inner_text('.md.doc'), pg.inner_text('.md.doc')

def s3_link_in_the_document_field(pg, w):
    "A link in the vault document field starts the link walk with one quiet note; a paper says Reading the paper. On A link, a paper quiets Pages to read. No network: the readers are fakes."
    import abhyasa.sources
    from vishalakshi.core import Vault
    from walk_data import PAGES
    was = Vault.pdf, abhyasa.sources._final, abhyasa.sources._addrs
    Vault.pdf = lambda self, url, **kw: self.add([(k, 'From the PDF. ' + t) for k, t in PAGES], 'Attention Is All You Need', source=url, kind='pdf')
    abhyasa.sources._final, abhyasa.sources._addrs = (lambda u: u), (lambda host: {'93.184.216.34'})
    try:
        pg.goto(f'{w.B}/add'); pg.wait_for_selector('.add-form input[name=ref]'); settle(pg, 300)
        pg.fill('.add-form input[name=ref]', 'https://arxiv.org/pdf/1706.03762'); pg.click('.add-form button.go')
        pg.wait_for_selector('#walk-out .walk-link', timeout=10000)
        out = pg.inner_text('#walk-out')
        assert 'This is a link, so the tutor reads it from the web.' in out and 'Reading the paper' in out and '1 of 1' not in out, out
        assert not pg.query_selector('#walk-out .req-err'), out
        pg.wait_for_url('**/w/*', timeout=30000)
        pg.goto(f'{w.B}/add'); pg.wait_for_selector('.add-form'); settle(pg, 300)
        pg.click('.add-form label:has(input[name=kind][value=link])'); pg.wait_for_selector('.add-link input[name=url]', state='visible')
        pg.fill('.add-link input[name=url]', '1706.03762')
        assert pg.is_hidden('.add-link .pages') and pg.is_visible('.add-link .paper-note') and pg.inner_text('.add-link .paper-note') == 'A paper is read in full.'
        pg.fill('.add-link input[name=url]', 'https://docs.example.dev/attention/')
        assert pg.is_visible('.add-link .pages') and pg.is_hidden('.add-link .paper-note')
    finally: Vault.pdf, abhyasa.sources._final, abhyasa.sources._addrs = was

def r1_start_forms_show_no_error(pg, w):
    "A form that starts something and redirects (Learn this, Make a walk, Start the walk) shows no error line and lands on the next page."
    pg.add_init_script("document.addEventListener('DOMContentLoaded', () => new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => n.classList && n.classList.contains('req-err') && sessionStorage.setItem('errs', n.textContent)))).observe(document, {childList: true, subtree: true}));")
    for url, fill, btn, land in [('/c/ranking', None, 'main button:has-text("Learn this")', '/s/'),
                                 ('/add', ('.add-form input[name=ref]', add_paper(w.lr)), 'main .go', '/w/'),
                                 (w.plan.replace(w.B, ''), None, 'main button:has-text("Start the walk")', '/w/')]:
        pg.goto(w.B + url); settle(pg, 200)
        if fill: pg.fill(*fill)
        pg.evaluate("sessionStorage.removeItem('errs')")
        pg.click(btn)
        pg.wait_for_url(lambda u: land in u and not u.endswith(url), timeout=30000); settle(pg, 300)
        errs = pg.evaluate("sessionStorage.getItem('errs')")
        assert not errs and not pg.query_selector('.req-err'), (url, errs)

def ct1_concept_tree(pg, w):
    "Concepts: a quiet tree, open at the subject. A click opens a group. The find box finds a deep concept and opens its branch; an empty box closes it again."
    w.lr.put('Ashvini', 'The first nakshatra.', 'jyotisha', group=['nakshatras'], group_by='model')
    w.lr.put('Magha', 'The tenth nakshatra.', 'jyotisha', aliases=['Maghā'], group=['nakshatras', 'pitri gana'], group_by='model')
    w.lr.put('Mesha', 'The first rasi.', 'jyotisha')
    pg.goto(w.B + '/concepts'); settle(pg, 200)
    subj = 'details.tree.subj:has(> summary .name:text-is("Jyotisha"))'
    grp = subj + ' > details.tree.grp:has(> summary .name:text-is("Nakshatras"))'
    deep = grp + ' > details.tree.grp:has(> summary .name:text-is("Pitri gana"))'
    is_open = lambda sel: pg.eval_on_selector(sel, 'd => d.open')
    assert is_open(subj) and not is_open(grp), 'the subject is open and its groups are closed'
    assert pg.inner_text(grp + ' > summary').replace('\n', ' ').strip() == 'Nakshatras · 2', pg.inner_text(grp + ' > summary')
    assert not pg.is_visible('a:text-is("Ashvini")')
    pg.click(grp + ' > summary'); settle(pg, 150)
    assert is_open(grp) and pg.is_visible('a:text-is("Ashvini")') and not pg.is_visible('a:text-is("Magha")')
    pg.click(grp + ' > summary'); settle(pg, 150)
    pg.fill('#find', 'magh'); settle(pg, 150)
    assert is_open(grp) and is_open(deep) and pg.is_visible('a:text-is("Magha")'), 'the find box opens the branch of Magha'
    assert not pg.is_visible('a:text-is("Ashvini")') and not pg.is_visible('a:text-is("Ranking")') and not pg.is_visible('a:text-is("Mesha")')
    pg.fill('#find', ''); settle(pg, 150)
    assert not is_open(grp) and pg.is_visible(subj + ' > summary') and pg.is_visible('a:text-is("Ranking")'), 'an empty box gives the tree as it was'
    pg.fill('#find', 'zzz'); settle(pg, 150)
    assert pg.is_visible('.find-none') and not pg.is_visible('a:text-is("Magha")')
    pg.fill('#find', 'magh'); pg.press('#find', 'Enter'); pg.wait_for_url(lambda u: 'q=magh' in u); settle(pg, 200)
    assert is_open(deep) and pg.is_visible('a:text-is("Magha")'), 'with no script, the server opens the branch too'

def box_values(pg): return pg.evaluate("['#ans', '#think'].map(s => document.querySelector(s)?.value)")

def dr1_wrong_try_leaves_empty_boxes(pg, w):
    "After a wrong try, the answer box and the think-aloud box are empty in the walk check and in the session, and the try stays in the record."
    jid = new_walk(w)
    pg.goto(f'{w.B}/w/{jid}/1'); pg.wait_for_selector('#check #ans'); settle(pg)
    pg.fill('#ans', 'a sum of scores'); pg.fill('#think', 'I added them'); pg.click('#send')
    pg.wait_for_selector('#check .thread .you'); settle(pg, 300)
    assert 'a sum of scores' in pg.inner_text('#check .thread') and box_values(pg) == ['', ''], box_values(pg)
    sid = w.rq.get(f'{w.B}/start?focus=ranking', max_redirects=0).headers['location'].rstrip('/').split('/')[-1]
    pg.goto(f'{w.B}/s/{sid}'); pg.wait_for_selector('#composer #ans'); settle(pg)
    pg.fill('#ans', 'a sum of scores'); pg.fill('#think', 'I added them'); pg.click('#send')
    pg.wait_for_selector('#chat .m.you'); settle(pg, 300)
    assert box_values(pg) == ['', ''], box_values(pg)

CHECKS = [f1_one_main_button_and_alt_s, f3_same_check_card, f4_one_filled_button, f11_native_controls, f14_sheet_lines_up,
          f15_no_ring_until_a_key, f16_signal_why_in_text_font, f17_no_broken_figure, reduced_motion,
          f7_step_lines_up, f6_pane_layout, f5_way_beside, f2_calm_end, m4_calm_finish, m1_next_idea_comes_in_gently, m2_check_answers_in_place, m3_outline_dot_fills,
          m6_words_point_at_the_demo, m7_side_walk_returns_you, rupaka_settle,
          f9_add_asks_for_one_thing, f10_graph_has_more_graph, m5_graph_grows, f12_today_has_an_order, f13_profile_invites,
          t16_step_page_parts, t16_side_walk_by_key, t16_pane_refuses_other_places, t16_narrow_side_walk_same_tab, t16_open_in_leela,
          d1_narrow_band, d2_pane_bar, d3_one_button_in_a_list, d4_session_bar_one_row, d5_small_faults, l1_demo_ladder, fb1_not_clear_note_reaches_the_simpler_demo,
          s1_source_link_opens_the_pane, s2_document_shows_its_images, s3_link_in_the_document_field, r1_start_forms_show_no_error, ct1_concept_tree,
          dr1_wrong_try_leaves_empty_boxes]

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

def guard(pg):
    "Collect the script errors of the page and its frames: uncaught errors and console errors. A failed request is not a script error."
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('console', lambda m: m.type == 'error' and not m.text.startswith('Failed to load resource') and errs.append(m.text[:200]))
    return errs

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
                errs = guard(pg)
                w = World(lr, pg.request, B)
                look(pg.request, B, 'paper', 'light')
                for c in [c for c in CHECKS if a.only is None or c.__name__ in a.only]:
                    errs.clear()
                    try:
                        c(pg, w)
                        assert not errs, f'script errors on the page: {errs[:3]}'
                        print('PASS', c.__name__, flush=True)
                    except Exception as e: bad += 1; print('FAIL', c.__name__, f'(line {e.__traceback__.tb_next.tb_lineno if e.__traceback__.tb_next else "?"})', '-', str(e)[:300], flush=True)
                if a.shots:
                    errs.clear(); n = len(screens(pg, w, Path(a.out), a.pages, looks=a.looks))
                    if errs: bad += 1; print('FAIL screens - script errors on the page:', errs[:3], flush=True)
                    print(n, 'screens in', a.out)
            finally: b.close()
    finally: srv.should_exit = True
    sys.exit(1 if bad else 0)

if __name__ == '__main__': main()
