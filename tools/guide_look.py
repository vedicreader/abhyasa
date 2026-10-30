"""Browser checks of the screen guide (phase 1): the board lands on the right parts of the page and stays there.

Run: uv run --all-extras python tools/guide_look.py [--out design/screens] [--browsers chromium,webkit]
It makes a temporary vault and settings folder, and a walk with two steps: the DDPM formula, and a right triangle with the
labels a and b. The app runs with the `Fake` model on a free port. Playwright opens its bundled Chromium and WebKit (headless,
one browser at a time, closed at the end). Each check prints PASS or FAIL; the run fails when one check fails.

1. "I don't get alpha bar" on the DDPM step: the circle lies on the alpha bar of the formula, and stays on it after a scroll and
   after the window changes size. A, S and D move the steps. The time from Send to the first mark is measured.
2. "Explain a and b" on the triangle step: the vision call (faked) finds the labels once, and the pointer marks land on them.
Screens: `guide-ddpm-<browser>.png` and `guide-triangle-<browser>.png`. The board voice is off (`abhyasaGuideQuiet`)."""
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

def board(p, sp):
    "The Fake tutor: a board for the page in the prompt, from its anchors."
    L = lambda *os: '\n'.join(json.dumps(o) for o in os)
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
    page.wait_for_timeout(400)
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
    page.keyboard.press('d'); page.wait_for_function("abhyasaBoard.state.i === 2"); page.wait_for_timeout(3500)
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

def tri(page, base, jid, name, out):
    page.set_viewport_size(dict(width=1280, height=800))
    page.goto(f'{base}/w/{jid}/1')
    page.wait_for_function("(() => { const i = document.querySelector('#figure img'); return i && i.complete && i.naturalWidth > 0; })()")
    page.evaluate("document.querySelector('#figure').scrollIntoView({block: 'center'})")
    last = ask(page, 'Explain a and b')
    page.evaluate("window.scrollTo(0, document.querySelector('#figure').getBoundingClientRect().top + scrollY - 120)"); page.wait_for_timeout(300)
    ok = True
    for k, step in (('a', 0), ('b', 1)):
        if step: page.mouse.click(5, 300); page.keyboard.press('d'); page.wait_for_function('abhyasaBoard.state.i === 1'); page.wait_for_timeout(900)
        want = page.evaluate("""(b) => { const r = document.querySelector('#figure img').getBoundingClientRect();
                                return [r.left + r.width * (b[0] + b[2]) / 2000, r.top + r.height * (b[1] + b[3]) / 2000]; }""", LABELS[k])
        mark = page.evaluate(f"""(() => {{ const g = document.querySelectorAll('#board-layer g[data-op="point"]')[{step}]; const c = g && g.lastElementChild.getBoundingClientRect();
                                 return c && [c.left + c.width / 2, c.top + c.height / 2]; }})()""")
        good = close_to(mark, want, 6)
        ok &= bool(good)
        check(f'{name}: the pointer lands on label {k}', good, f'mark {mark and [round(x) for x in mark]} label {[round(x) for x in want]}')
    page.screenshot(path=str(out/f'guide-triangle-{name}.png'))
    page.keyboard.press('Escape')
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
                finally: b.close()
    finally: srv.should_exit = True
    n = sum('You find the text labels' in sp for _, sp in FAKE.calls)
    check('the figure labels are found once, then kept', n == 1, f'{n} vision calls')
    for k, t in times.items(): print(f'TIME {k}: Send to first mark {t["first_ms"]} ms (page read {t["capture_ms"]} ms, board in {t["board_ms"]} ms, server {t["server_ms"]} ms with the Fake model)')
    print(f'{sum(RESULTS)} of {len(RESULTS)} checks pass')
    sys.exit(0 if all(RESULTS) else 1)

if __name__ == '__main__': main()
