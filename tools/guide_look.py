"""Browser checks of the screen guide (phase 1): the board lands on the right parts of the page and stays there.

Run: uv run --all-extras python tools/guide_look.py [--out design/screens] [--browsers chromium,webkit]
It makes a temporary vault and settings folder, and a walk with two steps: the DDPM formula, and a right triangle with the
labels a and b. The app runs with the `Fake` model on a free port. Playwright opens its bundled Chromium and WebKit (headless,
one browser at a time, closed at the end). Each check prints PASS or FAIL; the run fails when one check fails.

1. "I don't get alpha bar" on the DDPM step: the circle lies on the alpha bar of the formula, and stays on it after a scroll and
   after the window changes size. A, S and D move the steps. The time from Send to the first mark is measured.
2. "Explain a and b" on the triangle step: the vision call (faked) finds the labels once, and the pointer marks land on them.
3. The triangle idea has an explainer video (fossick's `read_yt` is faked, and a fake player stands in for youtube-nocookie, so
   no call leaves the Mac). "What does the video say about a and b": the board seeks the embed to the start of the cue that
   holds the quote, and the strip quotes that cue word for word with its `yt_link`. The concept page shows the same video.
4. The look: the pointer lands on its target, the glow on the formula stays around the text (not on it), a chip never covers
   its target, and with reduced motion the pointer jumps and the marks show at once.
5. A page with no data-guide-id plays a board through custom host hooks (resolve, speak, demo, assets).
6. In Chromium, `guide-polish-*.png`: the DDPM, triangle and video boards in Paper light and Signal dark, at several moments.
Screens: `guide-ddpm-<browser>.png`, `guide-triangle-<browser>.png`, `guide-video-<browser>.png` and `guide-video-concept-<browser>.png`. The board voice is off (`abhyasaGuideQuiet`)."""
import argparse, json, os, re, socket, sys, tempfile, threading, time
from pathlib import Path

ROOT = Path(__file__).parents[1]
TMP = Path(tempfile.mkdtemp(prefix='abhyasa-guide-'))
os.environ['VISHALAKSHI_VAULT'] = os.environ['ABHYASA_VAULT'] = str(TMP/'vault.db')   # never the real vault
os.environ['ABHYASA_CONFIG'] = str(TMP/'config')                                       # nor the real settings
os.environ['RAMABANA_CONFIG'] = str(TMP/'ramabana.toml')                               # nor the real ramabana config
os.environ.setdefault('LITESEARCH_CACHE', str(TMP/'litesearch'))
os.environ['ABHYASA_LEELA_FILE'] = str(TMP/'leela'/'serving.json')
for k in ('ABHYASA_STT', 'OPENAI_API_KEY', 'ABHYASA_MODEL'): os.environ.pop(k, None)

import abhyasa.voice
abhyasa.voice.RAMABANA_KEYS = TMP/'keys.env'
import rupaka.check
rupaka.check.can_check = lambda: False
from abhyasa.store import temp_learning
from abhyasa.llm import Fake
from abhyasa.app import mk_app
from abhyasa.core.cfg import cfg
cfg['leela'] = ''

EQ = r'q(\mathbf{x}_t \mid \mathbf{x}_0) = \mathcal{N}(\mathbf{x}_t; \sqrt{\bar\alpha_t}\,\mathbf{x}_0, (1-\bar\alpha_t)\mathbf{I})'
QUOTE = 'A notable property of the forward process is that it admits sampling x_t at an arbitrary timestep t in closed form.'
PASSAGE = (QUOTE + ' Using the notation $\\alpha_t := 1 - \\beta_t$ and $\\bar\\alpha_t := \\prod_{s=1}^{t} \\alpha_s$, we have\n\n$$' + EQ + '$$\n\n'
           'This lets training pick any step t at once. Late steps are almost all noise, so the model learns to remove a little noise at each one.\n\n' * 1)
TRI = 'In a right triangle with legs a and b, the hypotenuse c obeys a squared plus b squared equals c squared.'
PAGES = [(0, f'2 Background\n\n{QUOTE}'), (1, f'3 Geometry\n\n{TRI}\n\n![Figure 1](images/tri.png)')]
EXTRACT = dict(concepts=[
    dict(name='Noise in one jump', statement='The forward process can jump to any step t in closed form.', aliases=[], prereqs=[], section='2 Background',
         quote=QUOTE, figure='', ways=['maths'], moves=[], when=None, who=[]),
    dict(name='Right triangle sides', statement='The legs a and b of a right triangle set its hypotenuse.', aliases=[], prereqs=[], section='3 Geometry',
         quote=TRI, figure='images/tri.png', ways=['picture'], moves=[], when=None, who=[])])

def triangle(path):
    "A right triangle with the labels a and b; return the label boxes, from 0 to 1000 of the image."
    from PIL import Image, ImageDraw, ImageFont
    W, H = 600, 420
    im = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(im)
    d.line([(120, 360), (520, 360), (120, 60), (120, 360)], fill='black', width=4)
    d.rectangle([120, 330, 150, 360], outline='black', width=2)
    try: font = ImageFont.load_default(size=40)
    except TypeError: font = ImageFont.load_default()
    boxes = {}
    for t, (x, y) in dict(a=(70, 190), b=(305, 368)).items():
        d.text((x, y), t, fill='black', font=font)
        x0, y0, x1, y1 = d.textbbox((x, y), t, font=font)
        boxes[t] = [round(1000 * x0 / W), round(1000 * y0 / H), round(1000 * x1 / W), round(1000 * y1 / H)]
    path.parent.mkdir(parents=True, exist_ok=True); im.save(path)
    return boxes

VID = 'abc123def45'
CUES = [dict(start=0.0, end=12.5, text='Here is a right triangle.'), dict(start=12.5, end=19.0, text='The two short sides are the legs, a and b.'),
        dict(start=19.0, end=26.0, text='The long side is the hypotenuse.')]
VIDEO_Q = 'the legs, a and b'   # in the cue at 12.5 s; the Fake gives a later time, 15 s, and the board must seek to 12.5 s

def read_yt(url, force=False, cues=False, **kw):
    "fossick's `read_yt`, faked: no network."
    v = dict(title='Right triangles', channel='Maths Room', description='', duration=26, upload_date='20260101', source=' '.join(c['text'] for c in CUES))
    return {**v, 'cues': CUES} if cues else v

# The fake player: it takes the commands of the YouTube API and tells the page which time it was asked to seek to.
PLAYER = '''<!doctype html><body style="margin:0;background:#222;color:#eee;font:16px sans-serif;display:grid;place-items:center;height:100vh">
<div id="t">Fake player</div><script>addEventListener('message', e => { let m; try { m = JSON.parse(e.data); } catch (x) { return; }
if (m.func === 'seekTo') { document.getElementById('t').textContent = 'Seek to ' + m.args[0] + ' s'; parent.postMessage({fakePlayer: 'seek', t: m.args[0]}, '*'); } });</script>'''

def board(p, sp):
    "The Fake tutor: a board for the page in the prompt, from its anchors."
    L = lambda *os: '\n'.join(json.dumps(o) for o in os)
    if 'What does the video say' in p:
        return L(dict(op='v', n=1, sure=0.9, need='none'), dict(op='step', say='The video names the two short sides.'),
                 dict(op='video_at', t=15, quote=VIDEO_Q, w=0), dict(op='box', at='video', w=2))
    if 'figure (figure)' in p:
        return L(dict(op='v', n=1, sure=0.9, need='none'),
                 dict(op='step', say='Side a is the upright leg of the triangle.'), dict(op='point', at=dict(a='figure', label='a'), w=1),
                 dict(op='step', say='Side b is the flat leg at the bottom.'), dict(op='point', at=dict(a='figure', label='b'), w=1),
                 dict(op='label', at=dict(a='figure', label='b'), text='leg b', side='below', w=4))
    f = re.search(r'- (m\d+) \(formula\): [^\n]*mathcal', p).group(1)   # the display formula, from the anchor list
    return L(dict(op='v', n=1, sure=0.9, need='none'),
             dict(op='step', say='This formula adds noise to the clean picture in one jump.'), dict(op='box', at=f, w=3),
             dict(op='step', say='Alpha bar t is how much of the clean picture is left at step t.'),
             dict(op='circle', at=dict(a=f, tex=r'\bar\alpha_t'), w=0), dict(op='label', at=dict(a=f, tex=r'\bar\alpha_t'), text='how much is left', side='above', w=5),
             dict(op='step', say='Its root scales the picture, and one minus alpha bar sets the noise.'),
             dict(op='underline', at=dict(a=f, tex=r'\sqrt{\bar\alpha_t}'), w=1),
             dict(op='arrow', **{'from': dict(a=f, pt=[900, 1900]), 'to': dict(a=f, tex=r'(1-\bar\alpha_t)')}, w=7))

LABELS = {}
FAKE = Fake({'You find the text labels': lambda p, sp: dict(labels=[dict(text=k, box=v) for k, v in LABELS.items()]),
             'Tier: tutor': board, 'Return JSON: {"concepts"': EXTRACT, 'You write a short note': 'Alpha bar falls as t grows.'},
            dflt=dict(question='What does alpha bar tell you?', answer='How much signal is left.', rubric=['signal']))

def seed():
    "A vault with the DDPM walk, and an app on it with the Fake model. Return the app and the walk id."
    from starlette.testclient import TestClient
    lr = temp_learning()
    d = lr.vault.add(PAGES, 'Denoising Diffusion Probabilistic Models', source='/tmp/ddpm.pdf', kind='pdf')
    LABELS.update(triangle(lr.vault.assets('ddpm')/'images'/'tri.png'))
    app = mk_app(lr, FAKE, transcribe=lambda a, hint='': 'spoken text', hosts=('127.0.0.1', 'localhost', 'testserver'))
    jid = TestClient(app).post('/walk/new', data=dict(ref=d['doc_id'])).headers['hx-redirect'].split('/')[-1]
    s = lr.journey(jid).steps[0]
    lr.walk_step(jid, 0, read={**s['read'], 'text': PASSAGE})   # the passage with the formula, as an arXiv HTML source gives it
    import fossick.core, abhyasa.sources
    from abhyasa.guide import file_video
    fossick.core.read_yt, abhyasa.sources.public_url = read_yt, lambda u: u   # no network
    file_video(lr, VID, lr.journey(jid).steps[1]['slug'])
    return app, jid

def serve(app):
    import uvicorn
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    assert port not in (5077, 5078)
    srv = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(100):
        if srv.started: break
        time.sleep(.05)
    return srv, f'http://127.0.0.1:{port}'

RESULTS = []
def check(name, ok, info=''):
    RESULTS.append(ok)
    print(('PASS' if ok else 'FAIL'), name, info)

# Where a mark is, in the window: its centre, and the centre of what it should be on.
NEAR = """([sel, at]) => {
  const g = document.querySelector(sel); if (!g) return null;
  const r = g.getBoundingClientRect(), b = abhyasaBoard.boxOf(at);
  if (!b) return null;
  return {mark: [r.left + r.width / 2, r.top + r.height / 2, r.width, r.height], want: [b.x - scrollX + b.w / 2, b.y - scrollY + b.h / 2, b.w, b.h]};
}"""
TOKEN = """([fid, tex]) => { const h = document.querySelector(`[data-guide-id="${fid}"]`); const p = JSON.parse(h.dataset.parts).find(x => abhyasaBoard.normTex(x[0]) === abhyasaBoard.normTex(tex));
  const r = document.getElementById(p[1]).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2, r.width, r.height]; }"""

def close_to(a, b, tol=6): return a and b and abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol

def settle(page):
    "Wait until each mark of the step shows in full."
    page.wait_for_function('abhyasaBoard.state && abhyasaBoard.state.done', timeout=10000); page.wait_for_timeout(100)

def ask(page, said):
    page.evaluate('window.abhyasaGuideQuiet = true')
    page.click('#guide-go')
    page.fill('#guide-box', said)
    page.press('#guide-box', 'Enter')
    page.wait_for_function('window.abhyasaGuideLast && window.abhyasaGuideLast.first_ms != null', timeout=15000)
    return page.evaluate('window.abhyasaGuideLast')

def ddpm(page, base, jid, name, out):
    page.set_viewport_size(dict(width=1280, height=720))
    page.goto(f'{base}/w/{jid}/0')
    page.wait_for_function("document.querySelectorAll('#passage .katex').length >= 3")
    last = ask(page, "I don't get alpha bar")
    fid = page.evaluate("[...document.querySelectorAll('[data-guide-id^=m]')].find(h => (h.dataset.tex || '').includes('mathcal')).dataset.guideId")
    check(f'{name}: tier 1 answers with the tutor pill', page.text_content('#guide-strip .pill') == 'tutor' and last['tier'] == 'tutor')
    toks = page.evaluate("(f) => JSON.parse(document.querySelector(`[data-guide-id='${f}']`).dataset.parts).map(p => p[0])", fid)
    check(f'{name}: the formula has the parts the model names', all(t in toks for t in (r'\bar\alpha_t', r'\sqrt{\bar\alpha_t}', r'(1-\bar\alpha_t)')), str(toks[:8]))
    page.mouse.click(5, 300)   # the focus leaves the box: the board keys work
    page.keyboard.press('d')
    page.wait_for_function("abhyasaBoard.state && abhyasaBoard.state.i === 1")
    settle(page)
    at = dict(a=fid, tex=r'\bar\alpha_t')
    n = page.evaluate(NEAR, ['#board-layer g[data-op="circle"]', at]); tok = page.evaluate(TOKEN, [fid, r'\bar\alpha_t'])
    check(f'{name}: the circle is on alpha bar', n and close_to(n['mark'], tok) and n['mark'][2] > tok[2], f"mark {n and [round(x) for x in n['mark']]} token {[round(x) for x in tok]}")
    page.evaluate('window.scrollBy(0, 160)'); page.wait_for_timeout(300)
    n2 = page.evaluate(NEAR, ['#board-layer g[data-op="circle"]', at]); tok2 = page.evaluate(TOKEN, [fid, r'\bar\alpha_t'])
    check(f'{name}: it stays on alpha bar after a scroll', n2 and close_to(n2['mark'], tok2) and abs(tok2[1] - tok[1]) > 100, f"token moved {round(tok[1] - tok2[1])} px")
    page.set_viewport_size(dict(width=900, height=720)); page.wait_for_timeout(500)
    n3 = page.evaluate(NEAR, ['#board-layer g[data-op="circle"]', at]); tok3 = page.evaluate(TOKEN, [fid, r'\bar\alpha_t'])
    check(f'{name}: it stays on alpha bar after a resize', n3 and close_to(n3['mark'], tok3), f"token x {round(tok[0])} -> {round(tok3[0])}")
    lab = page.evaluate("(() => { const l = document.querySelector('.board-label.on'); const r = l.getBoundingClientRect(); return [r.top + r.height, l.textContent]; })()")
    check(f'{name}: the label is above alpha bar', lab[1] == 'how much is left' and lab[0] <= tok3[1] - tok3[3] / 2)
    page.set_viewport_size(dict(width=1280, height=720)); page.evaluate('window.scrollTo(0, 0)')
    page.keyboard.press('d'); page.wait_for_function("abhyasaBoard.state.i === 2"); settle(page)
    u = page.evaluate(NEAR, ['#board-layer g[data-op="underline"]', dict(a=fid, tex=r'\sqrt{\bar\alpha_t}')])
    check(f'{name}: the underline is under the root of alpha bar', u and abs(u['mark'][0] - u['want'][0]) <= 8 and u['mark'][1] >= u['want'][1])
    page.evaluate("(f) => document.querySelector(`[data-guide-id='${f}']`).scrollIntoView({block: 'center'})", fid); page.wait_for_timeout(300)
    page.screenshot(path=str(out/f'guide-ddpm-{name}.png'))
    i0 = page.evaluate('abhyasaBoard.state.i')
    page.fill('#ans', ''); page.focus('#ans'); page.keyboard.press('s')   # in the answer box, S types, and the board stays
    check(f'{name}: a key in the answer box types and does not move the board', page.evaluate('abhyasaBoard.state.i') == i0 and page.input_value('#ans') == 's')
    page.fill('#ans', ''); page.mouse.click(5, 300)
    page.keyboard.press('s'); page.wait_for_function(f"abhyasaBoard.state.i === {i0 - 1}")
    page.keyboard.press('Escape'); page.wait_for_function("!abhyasaBoard.state && !document.getElementById('board-host')")
    check(f'{name}: S goes back and Esc stops the board', True)
    return last

# The look: where the pointer tip is, the glow and its text, and each chip with its target.
GLOW = """(fid) => { const g = document.querySelector('.board-glow[data-op="box"]'), k = document.querySelector(`[data-guide-id="${fid}"] .katex-html`);
  if (!g || !k) return null; const a = g.getBoundingClientRect(), b = k.getBoundingClientRect(), bg = getComputedStyle(g).backgroundColor;
  return {margin: Math.min(b.left - a.left, b.top - a.top, a.right - b.right, a.bottom - b.bottom), bg, op: +getComputedStyle(g).opacity}; }"""
CHIP = """(at) => { const c = document.querySelector('.board-label.on'), b = abhyasaBoard.boxOf(at); if (!c || !b) return null; const r = c.getBoundingClientRect();
  const x = b.x - scrollX, y = b.y - scrollY; return {free: r.right <= x || r.left >= x + b.w || r.bottom <= y || r.top >= y + b.h, chip: [r.left, r.top, r.width, r.height], part: [x, y, b.w, b.h]}; }"""
TIP = """(at) => { const p = abhyasaBoard.pointer, b = abhyasaBoard.boxOf(at); if (!p || !b) return null;
  const x = b.x - scrollX, y = b.y - scrollY, [tx, ty] = p.tip, d = Math.max(x - tx, 0, tx - x - b.w) + Math.max(y - ty, 0, ty - y - b.h); return {d, flying: p.flying, tip: p.tip.map(Math.round)}; }"""
OFF_CHIP = """() => { const p = document.querySelector('#board-pointer svg').getBoundingClientRect(), cs = [...document.querySelectorAll('.board-label.on')].filter(c => +c.style.opacity > .9);
  return cs.length ? cs.every(c => { const r = c.getBoundingClientRect(); return p.right <= r.left || p.left >= r.right || p.bottom <= r.top || p.top >= r.bottom; }) : null; }"""
JUMP = """() => new Promise(ok => { abhyasaBoard.again(); const out = []; const f = () => { out.push(abhyasaBoard.pointer); if (out.length < 6) requestAnimationFrame(f); else ok(out); }; requestAnimationFrame(f); })"""

def alpha(css):
    "The alpha of a computed colour such as `rgba(181, 85, 28, 0.06)` or `color(srgb 0.7 0.3 0.1 / 0.06)`."
    m = re.search(r'/\s*([\d.]+)\)$', css) or re.search(r'rgba\([^)]*,\s*([\d.]+)\)$', css)
    return float(m.group(1)) if m else 1.0

def look(page, base, jid, name):
    "The look checks on the DDPM board: the pointer, the glow, the chip, and reduced motion."
    page.set_viewport_size(dict(width=1280, height=760))
    page.goto(f'{base}/w/{jid}/0')
    page.wait_for_function("document.querySelectorAll('#passage .katex').length >= 3")
    ask(page, "I don't get alpha bar"); settle(page)
    fid = page.evaluate("[...document.querySelectorAll('[data-guide-id^=m]')].find(h => (h.dataset.tex || '').includes('mathcal')).dataset.guideId")
    g = page.evaluate(GLOW, fid)
    check(f'{name}: the glow is around the formula, not on its text', g and g['margin'] >= 6 and alpha(g['bg']) <= .1 and g['op'] > .5, str(g))
    t = page.evaluate(TIP, fid)
    check(f'{name}: the pointer lands on the formula', t and t['d'] <= 14 and not t['flying'], str(t))
    page.mouse.click(5, 300); page.keyboard.press('d'); page.wait_for_function('abhyasaBoard.state.i === 1')
    page.wait_for_function('abhyasaBoard.pointer && abhyasaBoard.pointer.flying', timeout=3000)
    flew = True
    settle(page)
    at = dict(a=fid, tex=r'\bar\alpha_t')
    t = page.evaluate(TIP, at)
    check(f'{name}: the pointer flies, then lands on alpha bar', flew and t and t['d'] <= 14 and not t['flying'], str(t))
    c = page.evaluate(CHIP, at)
    check(f'{name}: the chip does not cover alpha bar', c and c['free'], str(c))
    check(f'{name}: the pointer rests off the chip', page.evaluate(OFF_CHIP) is True)
    page.emulate_media(reduced_motion='reduce')
    frames = page.evaluate(JUMP)
    tips = [f and f['tip'] for f in frames]
    t = page.evaluate(TIP, at)
    check(f'{name}: with reduced motion the pointer jumps and does not fly', all(f and not f['flying'] for f in frames) and len({tuple(map(round, x)) for x in tips}) == 1 and t['d'] <= 14, str(tips[:3]))
    ring = """document.querySelector('#board-layer g[data-op="circle"] path').getBBox().width"""
    page.wait_for_timeout(200); w0 = page.evaluate(ring); page.wait_for_timeout(900); w1 = page.evaluate(ring)
    check(f'{name}: with reduced motion the marks show at once', w0 > 20 and abs(w0 - w1) < .5, f'ring width {round(w0, 1)} then {round(w1, 1)}')
    page.emulate_media(reduced_motion='no-preference')
    page.keyboard.press('Escape')

# A page with no data-guide-id: the host resolves its own anchors, speaks, and moves its own demo.
HOST_PAGE = r"""<!doctype html><html data-theme="paper" data-mode="light"><head><meta charset="utf-8"><title>Host hooks</title>
<link rel="stylesheet" href="/assets/themes.css"><link rel="stylesheet" href="/assets/base.css"><link rel="stylesheet" href="/assets/board.css">
<script src="/assets/board.js"></script></head><body><main style="padding:40px 80px;max-width:760px">
<p data-leela="para" style="font-size:20px">The share that is left is <b data-leela="eq" data-parts='[["\\bar\\alpha", "leela-abar"], ["(1-\\bar\\alpha)", "leela-var"]]'>
<span id="leela-abar">ᾱ</span> and <span id="leela-var">(1 − ᾱ)</span></b>.</p>
<div data-leela="pic" style="width:300px;height:180px;background:#fff;border:1px solid #ccc;margin-top:60px"></div></main></body></html>"""
HOST_BOARD = dict(tier='tutor', sources=[], end='', steps=[
    dict(say='Alpha bar is the share that is left.', strokes=[dict(op='circle', at=dict(a='eq', tex=r'\bar\alpha'), w=0),
         dict(op='label', at=dict(a='eq', tex=r'\bar\alpha'), text='share left', side='above', w=2), dict(op='circle', at='nothing', w=3),
         dict(op='underline', at=dict(a='eq', tex=r'\gamma'), w=4)]),
    dict(say='The picture shows it.', strokes=[dict(op='box', at='pic', w=0), dict(op='demo_set', set=dict(t=3), w=1)])])
HOST_PLAY = r"""(board) => new Promise(ok => {
  window.__said = []; window.__sets = []; window.__resolved = [];
  const host = {resolve: id => { __resolved.push(id); return document.querySelector(`[data-leela="${CSS.escape(id)}"]`); },
                speak: (text, onWord, done) => { __said.push(text); const n = text.split(/\s+/).length; let k = 0;
                  const t = setInterval(() => { if (k < n) onWord(k++); else { clearInterval(t); done(); } }, 40); return () => clearInterval(t); },
                demo: set => __sets.push(set), assets: '/vendor'};
  document.addEventListener('board:first', () => ok(true), {once: true});
  abhyasaBoard.play(board, {host, auto: true});
})"""

def hooks(page, base, name):
    "The custom host hooks: a page with no data-guide-id plays a board with its own resolve, speak, demo and assets."
    page.set_viewport_size(dict(width=1100, height=700))
    page.route(f'{base}/host-test', lambda r: r.fulfill(status=200, content_type='text/html', body=HOST_PAGE))
    page.goto(f'{base}/host-test')
    page.evaluate(HOST_PLAY, HOST_BOARD)
    check(f'{name}: the host page has no data-guide-id', page.evaluate("document.querySelectorAll('[data-guide-id]').length") == 0)
    settle(page)
    r = page.evaluate("""() => { const g = document.querySelector('#board-layer g[data-op="circle"]').getBoundingClientRect(), t = document.getElementById('leela-abar').getBoundingClientRect();
                          return [g.left + g.width / 2 - t.left - t.width / 2, g.top + g.height / 2 - t.top - t.height / 2]; }""")
    check(f'{name}: host resolve: a token with a part element marks that part', abs(r[0]) <= 6 and abs(r[1]) <= 6, str([round(x) for x in r]))
    u = page.evaluate("""() => { const g = document.querySelector('#board-layer g[data-op="underline"]'), e = document.querySelector('[data-leela="eq"]').getBoundingClientRect();
                          if (!g || g.style.display === 'none') return null; const r = g.getBoundingClientRect(); return [r.left - e.left, r.right - e.right, r.top - e.bottom]; }""")
    check(f'{name}: a token with no part element marks the whole formula, and the stroke stays', u and abs(u[0]) <= 8 and abs(u[1]) <= 8 and -4 <= u[2] <= 14, str(u and [round(x) for x in u]))
    c = page.evaluate(CHIP, dict(a='eq', tex=r'\bar\alpha'))
    check(f'{name}: host resolve: the chip is near its part and does not cover it', c and c['free'], str(c))
    page.wait_for_function('abhyasaBoard.state && abhyasaBoard.state.i === 1', timeout=8000); settle(page)
    page.wait_for_function('window.__said.length === 2 && document.querySelectorAll("#guide-strip .board-say span.on").length === 4', timeout=5000)
    check(f'{name}: host speak says each line, and its words light up', page.evaluate('window.__said') == [s['say'] for s in HOST_BOARD['steps']])
    check(f'{name}: host demo gets the set', page.evaluate('window.__sets') == [dict(t=3)])
    check(f'{name}: host resolve finds each anchor, and a missing one draws nothing', {'eq', 'pic', 'nothing'} <= set(page.evaluate('window.__resolved'))
          and page.evaluate("""document.querySelectorAll('#board-layer g[data-op="circle"]').length""") == 1)
    page.keyboard.press('Escape')

THEMES = (('paper', 'light'), ('signal', 'dark'))

def polish(page, base, jid, out):
    "Screens of the board at several moments, in Paper light and Signal dark: `guide-polish-<board>-<theme>-<n>-<moment>.png`."
    def shot(board, look, n, moment): page.screenshot(path=str(out/f'guide-polish-{board}-{look}-{n}-{moment}.png'))
    def theme(t, m): page.evaluate("([t, m]) => { document.documentElement.dataset.theme = t; document.documentElement.dataset.mode = m; }", [t, m])
    def still(): page.mouse.click(5, 300); page.keyboard.press('s'); page.wait_for_timeout(50)   # S on step 1 draws it again, and stops the auto step
    for t, m in THEMES:
        look = f'{t}-{m}'
        page.set_viewport_size(dict(width=1280, height=760))
        page.goto(f'{base}/w/{jid}/0'); theme(t, m)
        page.wait_for_function("document.querySelectorAll('#passage .katex').length >= 3")
        page.evaluate("document.querySelector('#passage .katex-display').scrollIntoView({block: 'center'})")
        ask(page, "I don't get alpha bar"); still(); page.wait_for_timeout(380); shot('ddpm', look, 1, 'flight')
        settle(page); page.wait_for_timeout(300); shot('ddpm', look, 2, 'glow')
        page.keyboard.press('d'); page.wait_for_function('abhyasaBoard.state.i === 1'); page.wait_for_timeout(900); shot('ddpm', look, 3, 'marker')
        settle(page); page.wait_for_timeout(300); shot('ddpm', look, 4, 'chip')
        page.keyboard.press('d'); page.wait_for_function('abhyasaBoard.state.i === 2'); settle(page); page.wait_for_timeout(300); shot('ddpm', look, 5, 'end')
        page.keyboard.press('Escape')
        page.set_viewport_size(dict(width=1280, height=800))
        page.goto(f'{base}/w/{jid}/1'); theme(t, m)
        page.wait_for_function("(() => { const i = document.querySelector('#figure img'); return i && i.complete && i.naturalWidth > 0; })()")
        page.evaluate("document.querySelector('#figure').scrollIntoView({block: 'center'})")
        ask(page, 'Explain a and b'); still()
        page.evaluate("window.scrollTo(0, document.querySelector('#figure').getBoundingClientRect().top + scrollY - 120)"); page.wait_for_timeout(500); shot('triangle', look, 1, 'drawing')
        settle(page); page.keyboard.press('d'); page.wait_for_function('abhyasaBoard.state.i === 1'); settle(page); page.wait_for_timeout(300); shot('triangle', look, 2, 'chip')
        page.keyboard.press('Escape')
        page.set_viewport_size(dict(width=1280, height=900))
        page.route('https://www.youtube-nocookie.com/**', lambda r: r.fulfill(status=200, content_type='text/html', body=PLAYER))
        page.goto(f'{base}/w/{jid}/1'); theme(t, m)
        page.frame_locator('#guide-video iframe').locator('#t').wait_for()
        ask(page, 'What does the video say about a and b'); page.wait_for_timeout(250); shot('video', look, 1, 'bloom')
        settle(page); page.wait_for_timeout(600); shot('video', look, 2, 'glow')
        page.keyboard.press('Escape')

def tri(page, base, jid, name, out):
    page.set_viewport_size(dict(width=1280, height=800))
    page.goto(f'{base}/w/{jid}/1')
    page.wait_for_function("(() => { const i = document.querySelector('#figure img'); return i && i.complete && i.naturalWidth > 0; })()")
    page.evaluate("document.querySelector('#figure').scrollIntoView({block: 'center'})")
    last = ask(page, 'Explain a and b')
    page.evaluate("window.scrollTo(0, document.querySelector('#figure').getBoundingClientRect().top + scrollY - 120)"); settle(page)
    ok = True
    for k, step in (('a', 0), ('b', 1)):
        if step: page.mouse.click(5, 300); page.keyboard.press('d'); page.wait_for_function('abhyasaBoard.state.i === 1'); settle(page)
        want = page.evaluate("""(b) => { const r = document.querySelector('#figure img').getBoundingClientRect();
                                return [r.left + r.width * (b[0] + b[2]) / 2000, r.top + r.height * (b[1] + b[3]) / 2000]; }""", LABELS[k])
        mark = page.evaluate(f"""(() => {{ const g = document.querySelectorAll('#board-layer g[data-op="point"]')[{step}]; const c = g && g.lastElementChild.getBoundingClientRect();
                                 return c && [c.left + c.width / 2, c.top + c.height / 2]; }})()""")
        good = close_to(mark, want, 6)
        ok &= bool(good)
        check(f'{name}: the pointer lands on label {k}', good, f'mark {mark and [round(x) for x in mark]} label {[round(x) for x in want]}')
    check(f'{name}: the pointer rests off the chip of leg b', page.evaluate(OFF_CHIP) is True)
    page.screenshot(path=str(out/f'guide-triangle-{name}.png'))
    page.keyboard.press('Escape')
    return last

def video(page, base, jid, name, out):
    page.set_viewport_size(dict(width=1280, height=900))
    page.route('https://www.youtube-nocookie.com/**', lambda r: r.fulfill(status=200, content_type='text/html', body=PLAYER))
    page.goto(f'{base}/w/{jid}/1')
    page.evaluate("window.__seeks = []; addEventListener('message', e => { if (e.data && e.data.fakePlayer === 'seek') __seeks.push(e.data.t); })")
    src = page.get_attribute('#guide-video iframe', 'src') or ''
    check(f'{name}: the step embeds the video from youtube-nocookie, with no autoplay',
          src.startswith(f'https://www.youtube-nocookie.com/embed/{VID}?') and 'enablejsapi=1' in src and 'autoplay' not in src, src)
    page.frame_locator('#guide-video iframe').locator('#t').wait_for()   # the fake player is ready for commands
    last = ask(page, 'What does the video say about a and b')
    page.wait_for_function('window.__seeks.length > 0', timeout=5000)
    seeks = page.evaluate('window.__seeks')
    check(f'{name}: the video seeks to the start of the right cue', seeks[-1] == 12.5, f'seeks {seeks}')
    q = page.evaluate("(() => { const p = [...document.querySelectorAll('#guide-strip .board-quote')].find(x => x.querySelector('a[href*=\"youtube.com/watch\"]')); return p && [p.querySelector('q').textContent, p.querySelector('a').href, p.querySelector('.pill').textContent]; })()")
    want = f'https://www.youtube.com/watch?v={VID}&t=12s'
    check(f'{name}: the board quotes that cue word for word, with its link', q and q[0] == VIDEO_Q and VIDEO_Q in CUES[1]['text'] and q[1] == want and q[2] == 'video', str(q))
    end = page.text_content('#guide-strip .board-end') or ''
    check(f'{name}: the end line names the video as the source', 'Maths Room · Right triangles' in end, end)
    page.screenshot(path=str(out/f'guide-video-{name}.png'))
    page.keyboard.press('Escape')
    slug = page.get_attribute('#guide-video', 'data-concept')
    page.goto(f'{base}/c/{slug}')
    t = page.text_content('#guide-video-slot') or ''
    check(f'{name}: the concept page shows the video and a quiet transcript',
          page.locator('#guide-video iframe').count() == 1 and 'Maths Room · Right triangles' in t and page.locator('#guide-video details:not([open])').count() == 1)
    page.click('#guide-video summary'); page.wait_for_timeout(200)
    page.evaluate("window.__seeks = []; addEventListener('message', e => { if (e.data && e.data.fakePlayer === 'seek') __seeks.push(e.data.t); })")
    page.wait_for_timeout(300)
    page.click('#guide-video a[data-t="19.0"]'); page.wait_for_function('window.__seeks.length > 0', timeout=5000)
    check(f'{name}: a time in the transcript seeks the video', page.evaluate('window.__seeks')[-1] == 19, str(page.evaluate('window.__seeks')))
    page.locator('#guide-video-slot').scroll_into_view_if_needed()
    page.screenshot(path=str(out/f'guide-video-concept-{name}.png'))
    return last

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT/'design'/'screens'))
    ap.add_argument('--browsers', default='chromium,webkit')
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    app, jid = seed()
    srv, base = serve(app)
    from playwright.sync_api import sync_playwright
    times = {}
    try:
        with sync_playwright() as p:
            for name in a.browsers.split(','):
                b = getattr(p, name).launch(headless=True)
                try:
                    page = b.new_page()
                    page.on('pageerror', lambda e: check(f'{name}: no page error', False, str(e)))
                    times[name] = ddpm(page, base, jid, name, out)
                    tri(page, base, jid, name, out)
                    video(page, base, jid, name, out)
                    look(page, base, jid, name)
                    hooks(page, base, name)
                finally: b.close()
            if 'chromium' in a.browsers.split(','):
                b = p.chromium.launch(headless=True)
                try: polish(b.new_page(device_scale_factor=2), base, jid, out)
                finally: b.close()
    finally: srv.should_exit = True
    n = sum('You find the text labels' in sp for _, sp in FAKE.calls)
    check('the figure labels are found once, then kept', n == 1, f'{n} vision calls')
    for k, t in times.items(): print(f'TIME {k}: Send to first mark {t["first_ms"]} ms (page read {t["capture_ms"]} ms, board in {t["board_ms"]} ms, server {t["server_ms"]} ms with the Fake model)')
    print(f'{sum(RESULTS)} of {len(RESULTS)} checks pass')
    sys.exit(0 if all(RESULTS) else 1)

if __name__ == '__main__': main()
