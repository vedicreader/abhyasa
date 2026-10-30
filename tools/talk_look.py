"""Browser checks of a talk (Task 8 of the group talk plan), and the screens of the editor, the two windows and the page after the talk.

Run: uv run --all-extras python tools/talk_look.py [--shots] [--out design/screens] [--editor-shots DIR] [--again-shot DIR]
It makes a temporary vault and settings folder, runs the app with the `Fake` model on a free port, and opens it in Playwright's
bundled Chromium (headless, one browser, closed at the end). The presenter window is 1280 by 800 and the audience window 1280 by 720.
Each check prints PASS or FAIL; the run fails when one check fails, or when a page has a script error.
The checks build on each other, in the order of `CHECKS`: one talk, from the editor to the page after the talk.
`--only` runs only the checks that it names, so name a check with the checks before it.
`--shots` also takes the screens `talk-<page>-<theme>-<mode>-<width>.png` at 1280 and 1000 px, light and dark, Paper and Signal,
and the seven screens of the plan (`talk-editor.png`, `talk-presenter.png`, ... in Paper at 1280 px).
`--editor-shots DIR` takes the talk editor with a slide open, after an Undo, and with the rewrite prompt, in Paper dark and Signal light at 1280 px."""
import argparse, os, shutil, socket, struct, sys, tempfile, threading, time, zlib
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).parents[1]
TMP = Path(tempfile.mkdtemp(prefix='abhyasa-talk-look-'))
os.environ['VISHALAKSHI_VAULT'] = os.environ['ABHYASA_VAULT'] = str(TMP/'vault.db')   # never the real vault
os.environ['ABHYASA_CONFIG'] = str(TMP/'config')                                       # nor the real settings
os.environ['RAMABANA_CONFIG'] = str(TMP/'ramabana.toml')                               # nor the real ramabana config
os.environ.setdefault('LITESEARCH_CACHE', str(TMP/'litesearch'))                    # nor the shared litesearch lock of another run
os.environ['ABHYASA_LEELA_FILE'] = str(TMP/'leela'/'serving.json')
os.environ['XDG_CONFIG_HOME'] = str(TMP/'xdg')
for k in ('ABHYASA_STT', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'ABHYASA_MODEL'): os.environ.pop(k, None)
sys.path[:0] = [str(ROOT/'tests')]

import abhyasa.voice
abhyasa.voice.RAMABANA_KEYS = TMP/'keys.env'
import rupaka.check
rupaka.check.can_check = lambda: False   # no browser inside the app for a demo check
from abhyasa.store import temp_learning
from abhyasa.llm import Fake
from abhyasa.app import mk_app
from abhyasa.core.cfg import cfg
from walk_data import EXTRACT_REPLY, EXERCISE, add_paper
from talk_data import TALK_RULES, prep_walk
import abhyasa.research   # no web search and no page fetch in a look: research finds nothing
abhyasa.research.web_search = lambda q, n: []

cfg['leela'] = ''
PRESENTER, AUDIENCE = dict(width=1280, height=800), dict(width=1280, height=720)
LIT = 'softmax function'   # words of the passage of slide 2
REWRITE = dict(body=['A recurrent model works one step at a time.', 'So it cannot use many cores at once.'], notes='Say it slowly.')

def seed():
    "A vault with two concepts, and an app on it with the Fake model and the replies for a walk and a talk."
    ask = Fake({'Return JSON: {"concepts"': EXTRACT_REPLY, 'You write a short note': 'Softmax makes weights from scores. Look at what a large score does.',
                'You write one small Python exercise': EXERCISE, **TALK_RULES, 'Rewrite these fields': REWRITE},
               dflt=dict(question='What does a rank tell you?', answer='Its position.', rubric=['position']))
    lr = temp_learning()
    lr.put('Ranking', 'Order items by a score.', 'ml', order=0)
    lr.put('Reciprocal rank fusion', 'Sum 1/(k + rank) over lists.', 'ml', prereqs=['ranking'], order=1)
    return lr, mk_app(lr, ask, transcribe=lambda a, hint='': 'spoken text', hosts=('127.0.0.1', 'localhost'))

def figure_png(w=640, h=360):
    "A plain picture for the figure of slide 2: four bars, as the shares of a softmax. The test data has only the PNG header."
    bars = [(.62, (122, 74, 50)), (.2, (160, 120, 96)), (.12, (190, 160, 140)), (.06, (215, 195, 180))]
    def px(x, y):
        k, left = divmod(x - 60, 140)
        if 0 <= k < 4 and left < 100 and y > h - 40 - bars[k][0] * (h - 80) and y < h - 40: return bars[k][1]
        return (60, 50, 40) if y == h - 40 and 40 <= x < w - 40 else (246, 241, 230)
    raw = b''.join(b'\0' + bytes(c for x in range(w) for c in px(x, y)) for y in range(h))
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')

def serve(app):
    "Run `app` on a free port in a thread. Return the server and its base URL; the caller stops it with `server.should_exit`."
    import uvicorn
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    threading.Thread(target=srv.run, daemon=True).start()
    end = time.monotonic() + 30
    while not srv.started and time.monotonic() < end: time.sleep(.05)
    return srv, f'http://127.0.0.1:{port}'

def settle(pg, ms=400):
    try: pg.wait_for_load_state('networkidle', timeout=8000)
    except Exception: pass
    pg.wait_for_timeout(ms)

def look(rq, B, theme, mode): rq.post(f'{B}/settings/look', form=dict(theme=theme, mode=mode))

def guard(pg, errs):
    "Collect the errors of `pg` and its frames in `errs`: uncaught errors and console errors, a resource that fails to load (a broken image) too."
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('console', lambda m: m.type == 'error' and errs.append(f"{m.text[:160]} {m.location.get('url', '')[:80]}"))

# --- the state that the checks and the screens share --------------------------------------------------------------

class World:
    "The prepared walk, its talk, an old run, and the two windows."
    def __init__(self, lr, ctx, B, errs):
        self.lr, self.ctx, self.B, self.errs, self.rq = lr, ctx, B, errs, ctx.request
        doc = add_paper(lr); (lr.vault.assets('attention')/'images'/'fig2.png').write_bytes(figure_png())
        r = self.rq.post(f'{B}/walk/new', form=dict(ref=doc), headers={'HX-Request': 'true'}, max_redirects=0)
        self.jid = prep_walk(lr, r.headers['hx-redirect'].split('/')[-1])
        self.rq.post(f'{B}/talk/new', form=dict(jid=self.jid))
        end, loc = time.monotonic() + 20, None
        while not loc and time.monotonic() < end:
            loc = self.rq.get(f'{B}/talk/job?jid={self.jid}', max_redirects=0).headers.get('hx-redirect'); time.sleep(.1)
        assert loc, 'the talk was not made in 20 s'
        self.tid = loc.split('/')[-1]
        # a run that ended: its key is an old run key
        self.rq.post(f'{B}/t/{self.tid}/start', max_redirects=0); old = lr.talk(self.tid).live
        self.old_key = lr.run(old)['key']
        self.rq.post(f'{B}/t/{self.tid}/end', max_redirects=0)
        assert lr.talk(self.tid).live is None
        self.n0 = len(lr.attempts(limit=10000))
        self.au = None

    @property
    def run(self): return self.lr.run(self.lr.talk(self.tid).live)
    @property
    def channel(self): return f"{self.tid}:{self.run['key']}"

def place(pg): return pg.evaluate("(s => [s.dataset.slide, +s.dataset.beat])(document.getElementById('stage'))")
def wait_place(pg, slide, beat=None):
    pg.wait_for_function("([s, b]) => { const st = document.getElementById('stage'); return st.dataset.slide === s && (b === null || +st.dataset.beat === b); }",
                         arg=[slide, beat], timeout=8000)
def no_hscroll(pg): return pg.evaluate('document.documentElement.scrollWidth <= innerWidth')
def px(pg, sel): return pg.eval_on_selector(sel, 'e => parseFloat(getComputedStyle(e).fontSize)')
def post_on(pg, name, msg):
    "Post `msg` on the stage channel `name` from page `pg`, as a stranger to the talk would."
    pg.evaluate("([n, m]) => { const b = new BroadcastChannel('abhyasa-stage:' + n); b.postMessage(m); b.close(); }", [name, msg])
def press(pg, *keys):
    for k in keys: pg.keyboard.press(k)

# --- the checks: each takes (pg, w), where pg is the presenter page, and raises AssertionError ---------------------

ROWS = '#deck > li.edit-row'
CALM = "!document.querySelector('.htmx-request, .htmx-swapping, .htmx-settling')"   # htmx has settled the last answer

def editor_keys(pg, w):
    "The editor: rows in walk order, W and S move the focus, ⇧S moves the slide, ⌥F still opens the keyboard shortcuts; a lit: beat saves from its box."
    pg.goto(f'{w.B}/t/{w.tid}'); settle(pg)
    sids = pg.eval_on_selector_all(ROWS, 'els => els.map(e => e.dataset.id)')
    slides = w.lr.talk(w.tid).slides
    assert sids == [s['id'] for s in slides], sids
    steps = [s['step'] for s in slides if s['kind'] == 'idea']
    assert steps == sorted(steps) and len(steps) == 3, steps
    focused = lambda: pg.evaluate("document.activeElement.dataset.id || ''")
    press(pg, 's', 's'); assert focused() == 's2', focused()
    press(pg, 'w'); assert focused() == 's1', focused()
    press(pg, 'Shift+S')
    pg.wait_for_function(f"document.querySelectorAll('{ROWS}')[1].dataset.id === 's1' && document.activeElement.dataset.id === 's1' && {CALM}")
    press(pg, 'Shift+W')
    pg.wait_for_function(f"document.querySelectorAll('{ROWS}')[0].dataset.id === 's1' && document.activeElement.dataset.id === 's1'")
    assert [s['id'] for s in w.lr.talk(w.tid).slides][:3] == ['s1', 's2', 's3']
    press(pg, 'Alt+f'); pg.wait_for_url('**/keys', timeout=8000)
    assert 'Talk plan' in pg.text_content('main'), pg.url
    pg.goto(f'{w.B}/t/{w.tid}'); settle(pg)
    press(pg, 's', 's', 'e')   # the open row of slide 2
    assert pg.evaluate("document.activeElement.closest('li.edit-row')?.dataset.id") == 's2' and pg.evaluate('document.activeElement.name') == 'title'
    pg.locator('li.edit-row[data-id="s2"] details.add-beat > summary').click()
    pg.locator('li.edit-row[data-id="s2"] input[data-light]').fill(LIT); pg.locator('li.edit-row[data-id="s2"] form.light button').click()
    pg.wait_for_function(f"document.getElementById('beats-s2').textContent.includes('Light: {LIT}') && {CALM}")
    assert w.lr.talk(w.tid).slides[1]['beats'] == ['passage', 'figure', f'lit:{LIT}'], w.lr.talk(w.tid).slides[1]['beats']

def editor_beats(pg, w):
    "A beat chip drags by its grip to a place in the line of chips, and back; the stored beats follow."
    pg.goto(f'{w.B}/t/{w.tid}'); settle(pg)
    press(pg, 's', 's', 'e')
    beats = lambda: w.lr.talk(w.tid).slides[1]['beats']
    def drag(i, j):
        pg.locator('#beats-s2').scroll_into_view_if_needed()
        g = pg.locator('#beats-s2 > li.edit-row').nth(i).locator('.grip').bounding_box(); t = pg.locator('#beats-s2 > li.edit-row').nth(j).bounding_box()
        pg.mouse.move(g['x'] + 3, g['y'] + 5); pg.mouse.down(); pg.mouse.move(t['x'] + 6, t['y'] + t['height'] / 2, steps=8); pg.mouse.up()
        pg.wait_for_function(f"!!document.querySelector('#beats-s2') && {CALM}"); pg.wait_for_timeout(50)
    drag(1, 0); pg.wait_for_function("document.querySelector('#beats-s2 > li').dataset.id === 's2:figure'")
    assert beats() == ['figure', 'passage', f'lit:{LIT}'], beats()
    assert pg.evaluate('document.activeElement.dataset.id') == 's2:figure'
    drag(0, 2); pg.wait_for_function("document.querySelector('#beats-s2 > li').dataset.id === 's2:passage'")
    assert beats() == ['passage', 'figure', f'lit:{LIT}'], beats()

def editor_undo(pg, w):
    "X removes a slide at once and the Undo bar says so; ⌘Z gives it back in its place, with the focus on it. The Undo button is 44 px high or more."
    pg.goto(f'{w.B}/t/{w.tid}'); settle(pg)
    before = [s['id'] for s in w.lr.talk(w.tid).slides]
    press(pg, 's', 's', 'x')
    pg.wait_for_function(f"document.querySelectorAll('{ROWS}').length === {len(before) - 1}")
    assert 'Removed' in pg.inner_text('#undo-bar') and pg.eval_on_selector('#undo-bar button', 'b => b.getBoundingClientRect().height') >= 44
    pg.wait_for_function(CALM); press(pg, 'Meta+z')
    pg.wait_for_function(f"document.querySelectorAll('{ROWS}').length === {len(before)}")
    assert [s['id'] for s in w.lr.talk(w.tid).slides] == before and 'Undone' in pg.inner_text('#undo-bar')
    pg.wait_for_function("document.activeElement.dataset.id === 's2'")

def editor_rewrite(pg, w):
    "R opens the row and puts the focus in Rewrite this slide; a chip asks the tutor; the points change and the passage stays."
    pg.goto(f'{w.B}/t/{w.tid}'); settle(pg)
    old = w.lr.talk(w.tid).slides[0]['show']['passage']
    press(pg, 's', 'r')
    assert pg.evaluate("document.activeElement.name") == 'text' and pg.evaluate("document.activeElement.closest('li.edit-row').dataset.id") == 's1'
    pg.locator('li.edit-row[data-id="s1"] form.rewrite button[value="Simpler"]').click()
    pg.wait_for_function("document.getElementById('undo-bar').textContent.includes('Rewrote the points of slide 1')")
    s = w.lr.talk(w.tid).slides[0]
    assert s['show']['body'] == REWRITE['body'] and s['show']['passage'] == old
    pg.wait_for_function(CALM); press(pg, 'Meta+z'); pg.wait_for_function("document.getElementById('undo-bar').textContent.includes('Undone')")

def change_walk(w):
    "Give slide 2 your title, then change the walk: drop idea 1, change the note of idea 2 and add Layer norm. Return the old steps."
    w.rq.post(f'{w.B}/t/{w.tid}/slide?sid=s2', form=dict(act='set', title='Softmax, in my words'))
    j = w.lr.journey(w.jid); old = [dict(s) for s in j.steps]
    c = w.lr.put('Layer norm', 'Layer norm scales the values of one layer to a mean of 0 and a variance of 1.', 'ml')
    steps = [dict(s, note='Softmax gives weights that add to 1.') if s['slug'] == 'softmax' else s for s in j.steps[1:]]
    w.lr.put_journey({**j, 'steps': [*steps, dict(slug=c.slug, status='todo', why='')]})
    return old

def make_again(pg, w):
    "Press Make it again on the editor and wait for the talk to open again with its Undo bar."
    pg.goto(f'{w.B}/t/{w.tid}'); settle(pg)
    assert 'The walk changed after this talk was made: 1 idea added, 1 idea removed.' in pg.inner_text('.talk-again')
    pg.locator('.talk-again button').click()
    pg.wait_for_url(f'**/t/{w.tid}?done=again', timeout=20000); settle(pg)
    assert 'Made the talk again from the walk.' in pg.inner_text('#undo-bar')

def put_back(pg, w, old):
    "Undo Make it again and your title, and give the walk its old steps, so the next checks see the talk as before."
    pg.wait_for_function(CALM); press(pg, 'Meta+z'); pg.wait_for_function("document.getElementById('undo-bar').textContent.includes('Undone')")
    w.rq.post(f'{w.B}/t/{w.tid}/undo')
    j = w.lr.journey(w.jid); w.lr.put_journey({**j, 'steps': old})

def editor_again(pg, w):
    "Make it again keeps your title on its idea, takes the new note of the walk, puts the idea that left under Not in the walk any more, and ⌘Z takes it back."
    before = w.lr.talk(w.tid); old = change_walk(w)
    make_again(pg, w)
    t = w.lr.talk(w.tid); by = {s.get('concept'): s for s in t.slides}
    assert t.id == before.id and by['softmax']['title'] == 'Softmax, in my words' and by['softmax']['notes'] == 'Softmax gives weights that add to 1.'
    assert by['sequential-computation']['section'] == 'Not in the walk any more' and 'layer-norm' in by
    assert pg.locator('#deck li.sec', has_text='Not in the walk any more').count() == 1 and 'Softmax, in my words' in pg.inner_text('#deck')
    assert 'Put back in the talk' in pg.inner_text('#deck > li.parked .line') and 'not in the talk' in pg.inner_text('#deck > li.parked')
    put_back(pg, w, old)
    t = w.lr.talk(w.tid)
    assert t.slides == before.slides and t.made_from == before.made_from and t.marks == before.marks

def present_opens_audience(pg, w):
    "⌥S on the editor opens the presenter view; the first D opens the audience window, whose URL has the run key, and goes to s2 beat 1."
    pg.goto(f'{w.B}/t/{w.tid}'); settle(pg)
    press(pg, 'Alt+s'); pg.wait_for_url(f'**/t/{w.tid}/present', timeout=10000); settle(pg)
    with w.ctx.expect_page(timeout=10000) as got: press(pg, 'd')
    au = w.au = got.value; guard(au, w.errs)
    au.set_viewport_size(AUDIENCE); settle(au)
    assert f'/t/{w.tid}/audience?k=' in au.url and au.url.endswith('k=' + w.run['key']), au.url
    pg.bring_to_front()
    wait_place(au, 's2', 1); wait_place(pg, 's2', 1)
    pg.wait_for_selector('#aud-live:not([hidden])', timeout=8000)

def audience_type(pg, w):
    "The look is the feature: the room reads the screen from far away, so the audience h1 is 46 px and the passage 28 px; neither window scrolls sideways."
    au = w.au
    h1, ps = px(au, '#stage > section.stage:not([hidden]) h1'), px(au, '#stage > section.stage:not([hidden]) .passage')
    assert abs(h1 - 46) < .5 and abs(ps - 28) < .5, (h1, ps, au.evaluate("[innerWidth, innerHeight, document.getElementById('stage').getBoundingClientRect().toJSON()]"))
    assert no_hscroll(au) and no_hscroll(pg), 'a window scrolls sideways'

def beats_and_lit(pg, w):
    "D gives beat 2 with the figure, then the lit: beat lights the words in both windows."
    au = w.au
    press(pg, 'd'); wait_place(au, 's2', 2)
    assert au.is_visible('section[data-sid=s2] figure.fig'), 'no figure at beat 2'
    assert au.locator('#stage mark.lit').count() == 0
    press(pg, 'd'); wait_place(au, 's2', 3)
    au.wait_for_selector('#stage mark.lit')
    assert au.inner_text('#stage mark.lit') == LIT and pg.inner_text('#stage mark.lit') == LIT

def laser(pg, w):
    "X, then a move of the pointer over the slide, shows the dot in the audience window; 2 s with no move hides it."
    au = w.au
    press(pg, 'x')
    r = pg.locator('#stage').bounding_box()
    for i in range(4): pg.mouse.move(r['x'] + r['width'] * (.4 + i * .02), r['y'] + r['height'] * .5)
    au.wait_for_selector('#stage .stage-dot.on', timeout=3000)
    au.wait_for_timeout(2100)
    assert au.locator('#stage .stage-dot.on').count() == 0, 'the dot stays after 2 s'
    press(pg, 'x')

def blank(pg, w):
    "B blanks the room screen; B again shows the slide."
    au = w.au
    press(pg, 'b'); au.wait_for_function("document.getElementById('stage').classList.contains('blank')")
    assert au.is_visible('#stage .stage-blank')
    press(pg, 'b'); au.wait_for_function("!document.getElementById('stage').classList.contains('blank')")
    assert not au.is_visible('#stage .stage-blank')

DEMO = "document.querySelector('section[data-sid=s3] [data-rupaka]')"
def demo(pg, w):
    "G 3 goes to s3; E puts the focus in the demo; a change of t in the presenter's demo gives the same t in the audience copy."
    au = w.au
    press(pg, 'g', '3'); wait_place(au, 's3')
    press(pg, 'd'); wait_place(au, 's3', 2)
    au.wait_for_function(f"!!{DEMO}?.rupaka"); pg.wait_for_function(f"!!{DEMO}?.rupaka")
    press(pg, 'e'); assert pg.evaluate("!!document.activeElement.closest('[data-rupaka]')"), 'E did not go into the demo'
    pg.evaluate(f"""() => {{ const h = {DEMO};
      h.querySelector('.rk-gate .opts button').click(); h.querySelector('.rk-gate button.go').click();
      const i = h.querySelector('.rk-slider input'); i.value = 2; i.dispatchEvent(new Event('input', {{bubbles: true}})); }}""")
    au.wait_for_function(f"{DEMO}.rupaka.st.t === 2", timeout=5000)
    assert pg.evaluate(f"{DEMO}.rupaka.st.t") == au.evaluate(f"{DEMO}.rupaka.st.t") == 2
    press(pg, 'Escape'); assert pg.evaluate("!document.activeElement.closest('[data-rupaka]')")

ZOOM = f"""(() => {{ const h = {DEMO}, st = document.getElementById('stage'), d = h.parentElement.getBoundingClientRect(), r = h.getBoundingClientRect();
  return {{z: +h.style.zoom * 1280 / st.clientWidth, alone: h.closest('section').classList.contains('demo-alone'),
          inside: r.bottom <= d.bottom + 1 && r.right <= d.right + 1, tall: h.parentElement.classList.contains('tall'), text: +h.style.zoom * parseFloat(getComputedStyle(h).fontSize)}}; }})()"""
def demo_floor(pg, w):
    "The look is the feature: the room must read the demo, so its zoom keeps its floor (0.55 of a slide 1280 px wide) at 1280 and 1000 px; a demo too tall for the floor shows alone, with text of 14 px or more."
    au = w.au
    for width in (1280, 1000):
        au.set_viewport_size(dict(width=width, height=round(width * 9 / 16))); pg.set_viewport_size(dict(width=width, height=800)); au.wait_for_timeout(300)
        for x in (au, pg):
            got = x.evaluate(ZOOM)
            assert got['z'] >= .55 - .01 and got['inside'] and not got['alone'], (width, got)
    au.set_viewport_size(AUDIENCE); pg.set_viewport_size(PRESENTER); au.wait_for_timeout(300)
    tall = f"{DEMO}.firstElementChild.style.paddingBottom"
    # a demo too tall for the floor shows alone; its text is then 14 px or more, in a taller box that scrolls, and the presenter's scroll shows in the room
    for width in (1280, 1000):
        au.set_viewport_size(dict(width=width, height=round(width * 9 / 16))); pg.set_viewport_size(dict(width=width, height=800))
        for x in (au, pg): x.evaluate(f"{tall} = '700px'")
        for x in (au, pg): x.wait_for_function(f"{DEMO}.closest('section').classList.contains('demo-alone')", timeout=3000)
        for x in (au, pg):
            got = x.evaluate(ZOOM)
            assert got['alone'] and got['tall'] and got['text'] >= 14 - .1, (width, got)
            assert x.is_hidden('section[data-sid=s3] .passage') and x.is_hidden('section[data-sid=s3] h1'), got
        room = lambda x: x.evaluate(f"(d => d.scrollTop / Math.max(1, d.scrollHeight - d.clientHeight))({DEMO}.parentElement)")
        assert pg.evaluate(f"({DEMO}.parentElement.scrollHeight > {DEMO}.parentElement.clientHeight)"), width
        pg.evaluate(f"(d => {{ d.scrollTop = (d.scrollHeight - d.clientHeight) / 2; }})({DEMO}.parentElement)")
        au.wait_for_function(f"(d => Math.abs(d.scrollTop / Math.max(1, d.scrollHeight - d.clientHeight) - .5) < .02)({DEMO}.parentElement)", timeout=3000)
        for x in (au, pg): x.evaluate(f"{tall} = ''")
        for x in (au, pg): x.wait_for_function(f"!{DEMO}.closest('section').classList.contains('demo-alone')", timeout=3000)
        assert au.is_visible('section[data-sid=s3] .passage') and not au.evaluate(ZOOM)['tall']
    au.set_viewport_size(AUDIENCE); pg.set_viewport_size(PRESENTER); au.wait_for_timeout(300)

def question(pg, w):
    "Q shows the question and 3 options in the audience window, with no right answer; 1 then R marks It falls as the right answer."
    au = w.au
    press(pg, 'q'); au.wait_for_selector('#stage .stage-ask:not([hidden])')
    assert au.locator('#stage .stage-ask .ask-opts li').count() == 3
    assert au.locator('#stage .stage-ask li.right').count() == 0 and 'Right answer' not in au.inner_text('#stage .stage-ask')
    press(pg, '1', 'r'); au.wait_for_selector('#stage .stage-ask li.right')
    right = au.inner_text('#stage .stage-ask li.right')
    assert 'It falls' in right and 'right answer' in right.lower(), right
    press(pg, 'Escape'); au.wait_for_selector('#stage .stage-ask', state='hidden')

PANE_FRAME = "#stage > iframe.stage-pane"
def beside(pg, w):
    "⌥B, then 1, opens the Softmax primer beside the slide in both windows, in the talk type with no check; ⌥Z closes both."
    au = w.au
    press(pg, 'Alt+b'); pg.wait_for_selector('#beside-offer .bs-offer')
    press(pg, '1')
    au.wait_for_selector('#stage.beside > iframe.stage-pane', timeout=8000)
    pg.wait_for_selector('#rh-pane iframe', timeout=8000)
    for src, fr in ((au.get_attribute(PANE_FRAME, 'src'), au.frame_locator(PANE_FRAME)), (pg.get_attribute('#rh-pane iframe', 'src'), pg.frame_locator('#rh-pane iframe'))):
        assert 'talk=1' in src, src
        fr.locator('h1').first.wait_for()
        assert 'Softmax' in fr.locator('h1').first.inner_text() and fr.locator('#check').count() == 0, src
    # the primer is a short note that fits its window, in type of 22 px or more, with no broken picture
    frames = [x.frame_locator(sel) for x, sel in ((au, PANE_FRAME), (pg, '#rh-pane iframe'))]
    for fr in frames:
        fr.locator('#passage').wait_for(); pg.wait_for_timeout(300)
        got = fr.locator('html').evaluate("""() => ({fits: document.scrollingElement.scrollHeight <= innerHeight + 1, px: parseFloat(getComputedStyle(document.querySelector('#passage')).fontSize),
            text: document.querySelector('#passage').textContent, broken: [...document.images].filter(i => !i.closest('.gone') && !(i.complete && i.naturalWidth)).length,
            pages: abhyasaTalkPage.pages})""")
        assert got['fits'] and got['px'] >= 22 and not got['broken'] and got['pages'] == 1, got
        assert len(got['text']) < 400 and '![' not in got['text'] and '3.2.1' not in got['text'], got['text']
    # a long passage: the type gets smaller down to 22 px, then pages; D and A turn the page in both windows
    long = 'Softmax turns a list of scores into weights that are above 0 and add to 1. ' * 14
    for fr in frames: fr.locator('html').evaluate("(_, t) => { document.querySelector('#passage .md').textContent = t; abhyasaTalkPage.fit(); }", long)
    state = lambda fr: fr.locator('html').evaluate("""() => ({page: abhyasaTalkPage.page, pages: abhyasaTalkPage.pages, top: document.querySelector('#passage').scrollTop,
        px: parseFloat(getComputedStyle(document.querySelector('#passage')).fontSize), fits: document.scrollingElement.scrollHeight <= innerHeight + 1,
        more: document.querySelector('#passage').classList.contains('more'), label: document.querySelector('.talk-page').textContent})""")
    for fr in frames:
        got = state(fr); assert got['pages'] > 1 and abs(got['px'] - 22) < .6 and got['fits'] and got['more'] and got['top'] == 0, got
    press(pg, 'd')
    au.wait_for_function(f"document.querySelector('{PANE_FRAME}').contentWindow.abhyasaTalkPage.page === 1", timeout=5000)
    for fr in frames:
        got = state(fr); assert got['page'] == 1 and got['top'] > 0 and 'page 2 of' in got['label'], got
    assert w.run['side']['page'] == 1 and place(au)[0] == 's3'
    press(pg, 'a'); au.wait_for_function(f"document.querySelector('{PANE_FRAME}').contentWindow.abhyasaTalkPage.page === 0", timeout=5000)
    assert w.run['side']['page'] == 0 and place(au) == place(pg)
    press(pg, 'Alt+z')
    au.wait_for_function("!document.getElementById('stage').classList.contains('beside')")
    pg.wait_for_function("!document.documentElement.classList.contains('rh-open')")
    assert au.locator(PANE_FRAME).count() == 0

def reload_audience(pg, w):
    "A reload of the audience window shows the same slide and beat."
    before = place(pg)
    w.au.reload(); settle(w.au)
    wait_place(w.au, *before)
    pg.bring_to_front()

TEX = r'$1/\sqrt{d_k}$'
SHOWN = "(s => [...document.querySelectorAll(s)].map(e => [e.innerText, e.querySelectorAll('.katex').length]))"
CASES = [r'costs \$5 now', r'sum $$x^2$$ here', '$$x$$', r'a $b$ and \$c$', 'x $a$$b$ y', 'plain 5$ and $ 6$', 'pay $5 and $10', f'Why scale by {TEX}?']
TOKENS = """(s => { const e = abhyasaMath(document.createElement('p'), s);
  return [...e.childNodes].map(n => n.nodeType === 3 ? n.data : `[${n.classList.contains('display') ? 'd' : 'i'}:${n.querySelector('annotation')?.textContent ?? n.textContent}]`).join(''); })"""
def server_tokens(s):
    "The text of `Inline(s)` with each maths span as [i:tex] or [d:tex], as TOKENS gives it in the browser."
    import html, re
    from fastcore.xml import to_xml
    from abhyasa.core import Inline
    h = re.sub(r'<span class="math (inline|display)">(.*?)</span>', lambda m: f'[{m[1][0]}:{m[2]}]', to_xml(Inline(s)))
    return html.unescape(re.sub(r'^<span class="">|</span>\s*$', '', h.strip()))

def relink(pg, au):
    "Reload the presenter, then the audience, so the audience's hello reaches the new presenter; wait until the presenter sees the audience live."
    for x in (pg, au): x.reload(); settle(x)
    pg.wait_for_selector('#aud-live:not([hidden])', timeout=15000)

def maths(pg, w):
    "Maths in the title, the section, the points, the question and the options of slide 1 draws with KaTeX, the same in both windows."
    au, before, t0 = w.au, place(pg), w.lr.talk(w.tid)
    t = deepcopy(dict(t0)); s = t['slides'][0]
    s.update(title=f'Why scale by {TEX}', section=f'Scale by {TEX}', beats=['body', *[b for b in s.get('beats') or [] if b != 'body']])
    s['show'] = dict(s['show'], body=[f'We divide the scores by {TEX}.', 'Large scores make softmax flat.'])
    s['ask'] = dict(s['ask'], q=f'Why divide by {TEX}?', options=[f'To keep {TEX} small', 'To add noise', 'To sort them'])
    for c in CASES: assert pg.evaluate(TOKENS, c) == server_tokens(c), (c, pg.evaluate(TOKENS, c), server_tokens(c))   # the same maths as md_html
    w.lr.put_talk(t)
    try:
        relink(pg, au)
        pg.bring_to_front(); press(pg, 'g', '1'); wait_place(au, 's1', 1)
        parts = 'section[data-sid=s1] h1, section[data-sid=s1] .crumb, section[data-sid=s1] .points li'
        got = [x.evaluate(f"{SHOWN}('{parts}')") for x in (au, pg)]
        assert got[0] == got[1] and all(n == 1 and '$' not in txt for txt, n in got[0][:3]), got
        assert pg.evaluate("document.querySelectorAll('#now .katex, #ask-card .ask-q:not([hidden]) .katex').length") == 3   # the crumb, the question and an option
        press(pg, 'q'); au.wait_for_selector('#stage .stage-ask:not([hidden])')
        got = [x.evaluate(f"{SHOWN}('#stage .stage-ask h2, #stage .stage-ask li .t')") for x in (au, pg)]
        assert got[0] == got[1] and got[0][0][1] == 1 and got[0][1][1] == 1 and '$' not in got[0][0][0] + got[0][1][0], got
        press(pg, 'Escape'); au.wait_for_selector('#stage .stage-ask', state='hidden')
    finally:
        w.lr.put_talk(t0)
        relink(pg, au)
        pg.bring_to_front(); press(pg, 'g', before[0][1:]); wait_place(au, before[0])

def strangers(pg, w):
    "A pane to another site, a message of version 2, and a message on the channel of the old run change nothing in the audience window."
    au = w.au; before = place(au)
    post_on(pg, w.channel, {'v': 1, 't': 'pane', 'url': 'https://evil.example/'})
    post_on(pg, w.channel, {'v': 2, 't': 'go', 'slide': 's1', 'beat': 1})
    post_on(pg, f"{w.tid}:{w.old_key}", {'v': 1, 't': 'go', 'slide': 's1', 'beat': 1})
    post_on(pg, f"{w.tid}:{w.old_key}", {'v': 1, 't': 'blank', 'on': True})
    au.wait_for_timeout(400)
    assert place(au) == before and au.locator(PANE_FRAME).count() == 0, place(au)
    assert not au.evaluate("document.getElementById('stage').classList.contains('blank')")

def audience_closed(pg, w):
    "Closing the audience window shows in the presenter window within 6 s."
    w.au.close(); w.au = None
    pg.wait_for_selector('#aud-gone:not([hidden])', timeout=6000)
    assert 'The audience window is closed. Open it again.' in pg.inner_text('#aud-gone')

def stray_keys(pg, w):
    "Esc with nothing open, ⌥T and / leave the presenter on its URL."
    url = pg.url
    press(pg, 'Escape', 'Alt+t', '/'); pg.wait_for_timeout(300)
    assert pg.url == url, pg.url

def end_and_after(pg, w):
    "⌥S on the last slide ends the talk and shows After the talk; the learning has the same number of attempts as before the talk."
    n = len(w.lr.talk(w.tid).slides)
    press(pg, 'g', str(n)); pg.wait_for_function("document.querySelector('#ask-go .act').textContent === 'End the talk'", timeout=5000)
    press(pg, 'Alt+s'); pg.wait_for_url(f'**/t/{w.tid}/after?run=*', timeout=10000); settle(pg)
    assert 'After the talk' in pg.inner_text('h1')
    assert w.lr.talk(w.tid).live is None and len(w.lr.attempts(limit=10000)) == w.n0

def present_journey(pg, w):
    "An old /j/ link opens the path; Present this walk there makes the talk and opens the editor; ⌥S there opens the presenter view; the path then offers Open the talk."
    jid = w.lr.put_journey(dict(id='attention-basics-ab12', title='Attention basics', goal='Learn how attention works', subject='ml',
                                steps=[dict(slug=s, status='todo', why='') for s in ('softmax', 'sequential-computation')])).id
    pg.goto(f'{w.B}/j/{jid}'); settle(pg)
    assert pg.url.endswith(f'/path/{jid}'), pg.url
    pg.get_by_role('button', name='Present this walk').click()
    pg.wait_for_url('**/t/*', timeout=20000); settle(pg)
    tid = pg.url.rstrip('/').split('/')[-1]
    assert 'Made from your walk' in pg.inner_text('main') and w.lr.talk(tid).src['walk'] != w.jid, pg.url
    press(pg, 'Alt+s'); pg.wait_for_url(f'**/t/{tid}/present', timeout=10000); settle(pg)
    assert pg.is_visible('#stage'), 'no stage in the presenter view'
    w.rq.post(f'{w.B}/t/{tid}/end', max_redirects=0)
    pg.goto(f'{w.B}/path/{jid}'); settle(pg)
    assert pg.get_by_role('link', name='Open the talk').first.get_attribute('href') == f'/t/{tid}', 'no Open the talk'   # a row of the list beside has its own

def present_started_walk(pg, w):
    "A started walk goes to its step: on step 2 the quiet Present this walk is in the outline column and opens the talk editor."
    r = w.rq.post(f'{w.B}/walk/new', form=dict(ref=add_paper(w.lr)), headers={'HX-Request': 'true'}, max_redirects=0)
    jid = prep_walk(w.lr, r.headers['hx-redirect'].split('/')[-1])
    w.rq.post(f'{w.B}/w/{jid}/start', max_redirects=0)
    pg.goto(f'{w.B}/w/{jid}/1'); settle(pg)
    link = pg.locator('#rail').get_by_role('button', name='Present this walk')
    assert link.is_visible(), 'no Present this walk on step 2'
    link.click(); pg.wait_for_url('**/t/*', timeout=20000); settle(pg)
    assert 'Made from your walk' in pg.inner_text('main'), pg.url

def journey_points(pg, w):
    "Present a walk planned from a goal, on ideas that no source names: each idea slide in the audience window has points, the first slide shows them, and no note shows."
    jid = w.lr.put_journey(dict(id='ranking-talk-ab12', title='Ranking talk', goal='Learn how to rank results', subject='ml',
                                steps=[dict(slug=s, status='todo', why='') for s in ('ranking', 'reciprocal-rank-fusion')])).id
    pg.goto(f'{w.B}/path/{jid}'); settle(pg)
    pg.get_by_role('button', name='Present this walk').click()
    pg.wait_for_url('**/t/*', timeout=20000); settle(pg)
    tid = pg.url.rstrip('/').split('/')[-1]
    w.rq.post(f'{w.B}/t/{tid}/start', max_redirects=0)
    key, ideas = w.lr.run(w.lr.talk(tid).live)['key'], [s['id'] for s in w.lr.talk(tid).slides if s['kind'] == 'idea']
    au = w.ctx.new_page(); guard(au, w.errs); au.set_viewport_size(AUDIENCE)
    try:
        au.goto(f'{w.B}/t/{tid}/audience?k={key}'); settle(au)
        n = {sid: au.eval_on_selector(f'section.stage[data-sid="{sid}"]', "s => [...s.querySelectorAll('.points li')].filter(l => l.textContent.trim()).length") for sid in ideas}
        assert ideas and all(k >= 2 for k in n.values()), n
        first = f'section.stage[data-sid="{ideas[0]}"] .points'
        assert au.is_visible(first) and px(au, first) >= 21.9, 'the points of the first slide do not show at a size that the room can read'
        assert 'Watch for' not in au.inner_text('body') and no_hscroll(au), 'a note shows to the room, or the window scrolls sideways'
        # long points: the type gets smaller, down to 22 px, so that they fit the slide
        got = au.eval_on_selector(first, """p => { p.querySelectorAll('li').forEach(l => { l.textContent = 'A long point with many words in it. '.repeat(9); });
            dispatchEvent(new Event('resize')); return parseFloat(getComputedStyle(p).fontSize); }""")
        assert 21.9 <= got < 27.9, f'long points did not get smaller: {got} px'
    finally:
        au.close(); w.rq.post(f'{w.B}/t/{tid}/end', max_redirects=0)

CHECKS = [editor_keys, editor_beats, editor_undo, editor_rewrite, editor_again, present_opens_audience, audience_type, beats_and_lit, laser, blank, demo, demo_floor, question, beside,
          reload_audience, maths, strangers, audience_closed, stray_keys, end_and_after, present_journey, present_started_walk, journey_points]

# --- the screens --------------------------------------------------------------------------------------------------

LOOKS = [(t, m) for t in ('paper', 'signal') for m in ('light', 'dark')]
PLAN = {'editor': 'paper-light', 'presenter': 'paper-light', 'presenter-dark': 'paper-dark', 'audience': 'paper-light',
        'hands': 'paper-light', 'beside': 'paper-light', 'after': 'paper-light'}

def screens(w, out, widths=(1280, 1000)):
    "Each page of a talk in each look and width; then the seven screens of the plan."
    out.mkdir(parents=True, exist_ok=True)
    B, tid, shots = w.B, w.tid, []
    w.rq.post(f'{B}/t/{tid}/start', max_redirects=0)
    pr = w.ctx.new_page(); guard(pr, w.errs); pr.set_viewport_size(PRESENTER)
    au = w.ctx.new_page(); guard(au, w.errs); au.set_viewport_size(AUDIENCE)
    au.goto(f"{B}/t/{tid}/audience?k={w.run['key']}"); pr.goto(f'{B}/t/{tid}/present')
    settle(au); settle(pr); pr.wait_for_selector('#aud-live:not([hidden])', timeout=8000); pr.bring_to_front()

    def take(name, pg, height):
        for theme, mode in LOOKS:
            look(w.rq, B, theme, mode)
            for width in widths:
                pg.set_viewport_size(dict(width=width, height=height if pg is not au else round(width * 9 / 16)))
                pg.reload(); settle(pg, 900)
                if pg is pr: pr.wait_for_selector('#aud-live:not([hidden])', timeout=8000)
                p = out/f'talk-{name}-{theme}-{mode}-{width}.png'; pg.screenshot(path=str(p)); shots.append(p.name)
        look(w.rq, B, 'paper', 'light')
        if pg in (pr, au): pg.set_viewport_size(PRESENTER if pg is pr else AUDIENCE); pg.reload(); settle(pg)
        pr.bring_to_front()

    ed = w.ctx.new_page(); guard(ed, w.errs); ed.goto(f'{B}/t/{tid}'); take('editor', ed, 900); ed.close()
    press(pr, 'g', '2'); wait_place(au, 's2'); press(pr, 'd', 'd'); wait_place(au, 's2', 3)
    take('presenter', pr, 800); take('audience', au, 720)
    press(pr, 'g', '3'); wait_place(au, 's3'); press(pr, 'd'); wait_place(au, 's3', 2)
    press(pr, 'q'); au.wait_for_selector('#stage .stage-ask:not([hidden])'); press(pr, '1', 'r'); au.wait_for_selector('#stage .stage-ask li.right')
    take('hands', pr, 800)
    press(pr, 'Escape'); au.wait_for_selector('#stage .stage-ask', state='hidden')
    press(pr, 'Alt+b'); pr.wait_for_selector('#beside-offer .bs-offer'); press(pr, '1'); au.wait_for_selector(PANE_FRAME, timeout=8000)
    take('beside', au, 720)
    press(pr, 'Alt+z'); au.wait_for_function("!document.getElementById('stage').classList.contains('beside')")
    press(pr, 'g', str(len(w.lr.talk(tid).slides))); pr.wait_for_function("document.querySelector('#ask-go .act').textContent === 'End the talk'")
    press(pr, 'Alt+s'); pr.wait_for_url(f'**/t/{tid}/after?run=*', timeout=10000)
    after = w.ctx.new_page(); guard(after, w.errs); after.goto(pr.url); take('after', after, 900); after.close()
    pr.close(); au.close()
    for name, lk in PLAN.items():
        shutil.copyfile(out/f"talk-{name.removesuffix('-dark')}-{lk}-1280.png", out/f'talk-{name}.png'); shots.append(f'talk-{name}.png')
    return shots

def editor_screens(w, out):
    "The talk editor at 1280 px in Paper dark and Signal light: a slide open, the list after an Undo, and the rewrite prompt."
    out.mkdir(parents=True, exist_ok=True)
    B, tid, shots = w.B, w.tid, []
    ed = w.ctx.new_page(); guard(ed, w.errs); ed.set_viewport_size(dict(width=1280, height=900))
    try:
        for theme, mode in (('paper', 'dark'), ('signal', 'light')):
            look(w.rq, B, theme, mode)
            def shot(name):
                p = out/f'talk-editor-{name}-{theme}-{mode}-1280.png'; ed.screenshot(path=str(p)); shots.append(p.name)
            ed.goto(f'{B}/t/{tid}'); settle(ed)
            press(ed, 's', 's', 'e'); ed.wait_for_timeout(300)
            ed.set_viewport_size(dict(width=1280, height=1700))   # the whole open row: the fields, the figure, the beats and the question
            ed.evaluate("document.querySelector('li.edit-row[data-id=\"s2\"]').scrollIntoView({block: 'start'}); scrollBy(0, -80)"); shot('open')
            ed.set_viewport_size(dict(width=1280, height=900))
            press(ed, 'Escape', 'Escape', 'x'); ed.wait_for_function("document.getElementById('undo-bar').textContent.includes('Removed')")
            ed.wait_for_function(CALM); press(ed, 'Meta+z'); ed.wait_for_function("document.getElementById('undo-bar').textContent.includes('Undone')")
            ed.wait_for_timeout(300); ed.evaluate('scrollTo(0, 0)'); shot('undo')
            ed.goto(f'{B}/t/{tid}'); settle(ed)
            press(ed, 's', 'r'); ed.keyboard.type('Add an example from daily life'); ed.wait_for_timeout(200)
            ed.evaluate("document.querySelector('li.edit-row[data-id=\"s1\"] form.rewrite').scrollIntoView({block: 'center'})"); shot('rewrite')
    finally:
        ed.close(); look(w.rq, B, 'paper', 'light')
    return shots

def again_screen(w, out):
    "The talk editor after Make it again, at 1280 px in Paper dark: your title kept on its idea, the new idea, and Not in the walk any more."
    out.mkdir(parents=True, exist_ok=True)
    ed = w.ctx.new_page(); guard(ed, w.errs); ed.set_viewport_size(dict(width=1280, height=900))
    try:
        look(w.rq, w.B, 'paper', 'dark')
        old = change_walk(w); make_again(ed, w)
        p = out/'talk-editor-again-paper-dark-1280.png'; ed.screenshot(path=str(p), full_page=True)
        put_back(ed, w, old)
    finally:
        ed.close(); look(w.rq, w.B, 'paper', 'light')
    return [p.name]

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--shots', action='store_true', help='also take the screens')
    ap.add_argument('--out', default=str(ROOT/'design/screens'))
    ap.add_argument('--only', nargs='*', default=None, help='run only the checks with these names')
    ap.add_argument('--editor-shots', default=None, help='also take the screens of the talk editor in this folder')
    ap.add_argument('--again-shot', default=None, help='also take the talk editor after Make it again in this folder')
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    lr, app = seed()
    srv, B = serve(app)
    bad = 0
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                ctx = b.new_context(viewport=PRESENTER, reduced_motion='reduce')
                errs = []
                pg = ctx.new_page(); guard(pg, errs)
                w = World(lr, ctx, B, errs)
                look(w.rq, B, 'paper', 'light')
                for c in [c for c in CHECKS if a.only is None or c.__name__ in a.only]:
                    errs.clear()
                    try:
                        c(pg, w)
                        assert not errs, f'script errors on a page: {errs[:3]}'
                        print('PASS', c.__name__, flush=True)
                    except Exception as e:
                        bad += 1; tb = e.__traceback__
                        while tb.tb_next and tb.tb_next.tb_frame.f_code.co_filename == __file__: tb = tb.tb_next
                        print('FAIL', c.__name__, f'(line {tb.tb_lineno})', '-', str(e)[:300], flush=True)
                if a.editor_shots:
                    errs.clear(); n = len(editor_screens(w, Path(a.editor_shots)))
                    if errs: bad += 1; print('FAIL editor screens - script errors on a page:', errs[:3], flush=True)
                    print(n, 'editor screens in', a.editor_shots)
                if a.again_shot:
                    errs.clear(); again_screen(w, Path(a.again_shot))
                    if errs: bad += 1; print('FAIL again screen - script errors on a page:', errs[:3], flush=True)
                    print('the again screen in', a.again_shot)
                if a.shots:
                    errs.clear(); n = len(screens(w, Path(a.out)))
                    if errs: bad += 1; print('FAIL screens - script errors on a page:', errs[:3], flush=True)
                    print(n, 'screens in', a.out)
            finally: b.close()
    finally: srv.should_exit = True; shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1 if bad else 0)

if __name__ == '__main__': main()
