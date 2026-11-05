"What the room sees on a slide: maths drawn with KaTeX, code whose lines stay inside the slide, and a demo with no Lock in button."
from talk_data import *
import pytest
from pathlib import Path
from fastcore.xml import to_xml
from abhyasa.core import tex_dollars
from abhyasa.show import CODE_COLS
from test_talk import serve

MATHS = 'Each wave is c_n·e^{i2πnt/T}. The values are \\\\(\\mathbf{v}_i\\\\).'
FITS = 'total = sum(w * x for w, x in zip(weights, input))'   # a line of the longest length that a slide with points takes
LONG = 'result = compute_attention(queries, keys, values, mask=causal_mask, dropout=0.1, scale=True)'

def test_bare_maths_goes_in_dollars():
    "A bare TeX word, and maths in `\\(…\\)`, go in dollars. Code, a link, a name with an underscore and a markdown escape stay as they are."
    assert tex_dollars(MATHS) == 'Each wave is $c_n·e^{i2πnt/T}$. The values are $\\mathbf{v}_i$.'
    assert tex_dollars('(see x^2), `a^b`, d_model, https://x.org/a^b and \\[1\\]') == '(see $x^2$), `a^b`, d_model, https://x.org/a^b and \\[1\\]'

def code_talk(mk, lr):
    "A talk whose slide 1 has maths in its passage and points, and whose slide 2 has a point and a code piece with a line of `CODE_COLS` characters."
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr)))
    t = lr.talk(tid); ss = t.slides
    ss[0]['show'].update(passage=MATHS, body=['The power x^2 grows fast.']); ss[0]['beats'] = ['passage', 'body']
    ss[1]['show'].update(passage=f'```python\n{FITS}\nprint(total)\n```', body=['Each input has a weight.'], figure=None); ss[1]['beats'] = ['body', 'passage']
    lr.put_talk(t)
    return cl, tid

def test_the_slide_draws_maths_and_an_old_slide_loses_long_code(mk, talk_fake, lr):
    "The passage and the points have their maths as `span.math`. A slide that was made with a long line of code shows its points with no code."
    assert len(FITS) == CODE_COLS
    cl, tid = code_talk(mk, lr)
    cl.post(f'/t/{tid}/start'); run = lr.run(lr.talk(tid).live)
    h = cl.get(f'/t/{tid}/audience?k={run["key"]}').text
    assert '<span class="math inline">c_n·e^{i2πnt/T}</span>' in h and '<span class="math inline">x^2</span>' in h and '<span class="math inline">\\mathbf{v}_i</span>' in h
    t = lr.talk(tid); t.slides[1]['show']['passage'] = f'```python\n{LONG}\n```'
    lr.put_talk(t)   # the save keeps the long line, as an old release did; the check is on each load
    s2 = lr.talk(tid).slides[1]
    assert s2['show']['passage'] == '' and s2['beats'] == ['body']

def _chromium():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p: return Path(p.chromium.executable_path).exists()
    except Exception: return False

ROOM = """sid => { const st = document.getElementById('stage').getBoundingClientRect(), sec = document.querySelector(`section[data-sid=${sid}]`);
  const pre = sec.querySelector('.passage pre'), math = sec.querySelectorAll('.katex').length, raw = /\\^\\{|\\\\mathbf/.test(sec.innerText);
  const r = pre?.getBoundingClientRect();
  return {math, raw, code: pre ? {inside: r.right <= st.right + 1 && pre.scrollWidth <= pre.clientWidth + 1, px: parseFloat(getComputedStyle(pre).fontSize) / (st.width / 1280)} : null}; }"""
GATE = """() => { const st = document.getElementById('stage').getBoundingClientRect(), g = document.querySelector('section[data-sid=s3] .rk-gate');
  const seen = el => !!el && el.checkVisibility(), d = document.querySelector('section[data-sid=s3] .demo').getBoundingClientRect();
  return {gate: seen(g), go: seen(g.querySelector('button.go')), why: seen(g.querySelector('textarea')), inside: d.bottom <= st.bottom + 1}; }"""

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_the_room_sees_maths_whole_code_and_no_lock_in(mk, talk_fake, lr, tmp_path):
    """In Chromium, the audience window of a run: KaTeX draws the maths of the passage and the points; the code line of `CODE_COLS` characters
    stays inside the slide at a size that the room can read; the demo shows its gate, with no Lock in button and no box for the reason."""
    pw = pytest.importorskip('playwright.sync_api')
    cl, tid = code_talk(mk, lr)
    cl.post(f'/t/{tid}/start'); run = lr.run(lr.talk(tid).live)
    srv, base = serve(cl)
    try:
        with pw.sync_playwright() as p:
            b = p.chromium.launch(headless=True, args=['--mute-audio'])
            try:
                c = b.new_context(viewport=dict(width=1280, height=800))
                errs = []
                pr = c.new_page(); pr.on('pageerror', lambda e: errs.append(str(e)))
                pr.goto(f'{base}/t/{tid}/present'); pr.wait_for_load_state('networkidle')
                au = c.new_page(); au.on('pageerror', lambda e: errs.append(str(e)))
                au.set_viewport_size(dict(width=1280, height=720))
                au.goto(f'{base}/t/{tid}/audience?k={run["key"]}'); au.wait_for_load_state('networkidle')
                pr.wait_for_selector('#aud-live:not([hidden])')
                pr.keyboard.press('d'); au.wait_for_function("document.getElementById('stage').dataset.beat === '2'")
                s1 = au.evaluate(ROOM, 's1')
                assert s1['math'] >= 3 and not s1['raw'], s1
                au.screenshot(path=str(tmp_path/'room-maths.png'))
                pr.keyboard.press('g'); pr.keyboard.press('2'); au.wait_for_function("document.getElementById('stage').dataset.slide === 's2'")
                pr.keyboard.press('d'); au.wait_for_function("document.getElementById('stage').dataset.beat === '2'")
                au.wait_for_timeout(200)
                s2 = au.evaluate(ROOM, 's2')
                assert s2['code']['inside'] and s2['code']['px'] >= 13.5, s2
                au.screenshot(path=str(tmp_path/'room-code.png'))
                pr.keyboard.press('g'); pr.keyboard.press('3'); au.wait_for_function("document.getElementById('stage').dataset.slide === 's3'")
                pr.keyboard.press('d'); au.wait_for_function("document.querySelector('section[data-sid=s3] .demo:not([hidden]) [data-rk-ready]')")
                au.wait_for_timeout(300)
                g = au.evaluate(GATE)
                assert g == dict(gate=True, go=False, why=False, inside=True), g
                assert pr.evaluate("document.querySelector('section[data-sid=s3] .rk-gate button.go').checkVisibility()")   # the presenter still locks in
                au.screenshot(path=str(tmp_path/'room-demo.png'))
                assert not errs, errs
            finally: b.close()
    finally: srv.should_exit = True
