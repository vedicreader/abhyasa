"An arXiv paper is read from its HTML page first, so its passages keep their maths; the PDF is the fallback. No test uses the network."
import pytest
from pathlib import Path
from fastcore.basics import AttrDict
from abhyasa.sources import math_md, file_link, doc_pages
from abhyasa.journey import journey_from_sources
from talk_data import *

SAMPLE = (Path(__file__).parent/'data/arxiv_html_sample.html').read_text()
PDF_TEXT = '# Attention\n\nWe scale the dot products by 1 dk before the softmax. ' * 10

def html_of(aid): return AttrDict(title='Attention Is All You Need', text=math_md(SAMPLE), figures=[])
def fail_if_called(how, target, **kw): raise AssertionError('the PDF was read')
def doc_text(lr, d): return '\n\n'.join(t for _, t in doc_pages(lr, d.doc_id, d.shelf).pages)

def pdf_reader(lr):
    "A fake PDF reader that files the PDF text of the paper and records its call."
    def read(how, target, **kw): read.called = (how, target); return [lr.vault.add(PDF_TEXT, 'Attention', source=target, kind='pdf')]
    read.called = None
    return read

def test_math_md_keeps_tex():
    md = math_md(SAMPLE)
    assert r'$\frac{1}{\sqrt{d_k}}$' in md and '$$' in md and '1 dk' not in md
    assert 'alert' not in md                                                         # the script is gone

def test_paper_link_reads_html_first(lr):
    docs = file_link(lr, '1706.03762', html=html_of, read=fail_if_called)
    assert docs[0].url == 'https://arxiv.org/abs/1706.03762' and r'\sqrt{d_k}' in doc_text(lr, docs[0])

def test_paper_link_falls_back_to_the_pdf(lr):
    read = pdf_reader(lr)
    docs = file_link(lr, 'https://arxiv.org/abs/1706.03762', html=lambda aid: None, read=read)
    assert read.called == ('pdf', 'https://arxiv.org/pdf/1706.03762') and docs[0].url == 'https://arxiv.org/pdf/1706.03762'

def test_an_old_pdf_copy_stays(lr):
    "A paper filed from its PDF before keeps that document; the HTML copy is a new document beside it."
    pdf = file_link(lr, '1706.03762', html=lambda aid: None, read=pdf_reader(lr))[0]
    before = doc_text(lr, pdf)
    html = file_link(lr, '1706.03762', html=html_of, read=fail_if_called)[0]
    assert html.doc_id != pdf.doc_id and doc_text(lr, pdf) == before and r'\sqrt{d_k}' in doc_text(lr, html)

def test_passage_with_maths_is_word_for_word(lr, walk_fake):
    "A walk step on the HTML copy quotes it word for word, maths and all."
    quote = r'we scale the dot products by $\frac{1}{\sqrt{d_k}}$ before the softmax'
    walk_fake.rules['Return JSON: {"concepts"'] = dict(concepts=[dict(name='Scaled dot products', statement='Attention scales the dot products by one over the root of dk.',
        aliases=[], prereqs=[], section='3 Scaled Dot-Product Attention', quote=quote, figure='', ways=['maths'], moves=[], when=None, who=[])])
    docs = file_link(lr, '1706.03762', html=html_of, read=fail_if_called)
    j = journey_from_sources(lr, walk_fake, docs)
    text = next(s['read']['text'] for s in j.steps if s['slug'] == 'scaled-dot-products')
    assert quote in text and text in doc_text(lr, docs[0])

def test_slide_passage_draws_maths(mk, lr, talk_fake):
    "A slide passage with maths shows it as `span.math` to the presenter and to the room."
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr)))
    t = lr.talk(tid); s = next(s for s in t.slides if (s.get('show') or {}).get('passage'))
    s['show']['passage'] = 'We divide each by $\\sqrt{d_k}$.\n\nThen a softmax gives the weights.<script>alert(1)</script>'
    lr.put_talk(t); cl.post(f'/t/{tid}/start'); run = lr.run(lr.talk(tid).live)
    for page in (cl.get(f'/t/{tid}/present').text, cl.get(f'/t/{tid}/audience?k={run["key"]}').text):
        assert '<span class="math inline">\\sqrt{d_k}</span>' in page and '<script>alert(1)' not in page   # maths drawn, no script

def test_concept_page_passage_draws_maths(mk, lr, walk_fake):
    "The In a walk part of a concept page draws the maths of a passage, and keeps its source line."
    cl = mk(); jid = walk(cl, lr)
    i = next(k for k, s in enumerate(lr.journey(jid).steps) if s['slug'] == 'softmax')
    read = dict(lr.journey(jid).steps[i]['read'], text='We divide each by $\\sqrt{d_k}$.<script>alert(2)</script>')
    lr.walk_step(jid, i, read=read)
    part = (h := cl.get('/c/softmax').text)[h.index('walk-passages'):]
    assert '<span class="math inline">\\sqrt{d_k}</span>' in part and 'Attention Is All You Need' in part and 'src-line' in part
    assert '<script>alert(2)' not in part

def test_a_cut_never_splits_a_formula(lr):
    "The cap on a saved page and on a step passage moves a cut back to before a formula that it would split."
    from abhyasa.sources import _clip, extract, placement
    from abhyasa.settings import set_val, val
    from abhyasa.llm import Fake
    kept, most = val('links.kept'), val('walks.passage')
    try:
        set_val('links.kept', 10_000)
        assert _clip('x' * 9_990 + ' $\\frac{1}{\\sqrt{d_k}}$ end.') == 'x' * 9_990 + ' '
        set_val('walks.passage', 200)
        quote = 'We scale the words ' + 'w' * 170 + ' by $\\frac{1}{\\sqrt{d_k}}$ before the softmax.'
        d = lr.vault.add([(0, 'Intro. ' + quote + ' More.')], 'Maths', source='/tmp/maths.md', kind='file')
        ask = Fake({'Return JSON: {"concepts"': dict(concepts=[dict(name='Scaling', statement='Scale the dot products.', aliases=[], prereqs=[], quote=quote, section='')])})
        extract(lr, ask, pages=[(1, 'Intro. ' + quote + ' More.')], source=dict(src='vault', shelf='store', doc_id=d['doc_id'], title='Maths'))
        p = placement(lr.concept('scaling'), d['doc_id'])
        assert p.passage == quote[:quote.index('$')] and p.span[1] - p.span[0] == len(p.passage)   # the cut moved back to before the formula
    finally: set_val('links.kept', kept); set_val('walks.passage', most)

LIGHT_HTML = '<section id="s"><blockquote class="passage">Scale <span class="math inline"><span class="katex">softmax</span></span> then softmax.</blockquote></section>'

def test_light_skips_drawn_maths():
    "A lit beat lights its words in the text of the passage, never inside drawn maths."
    import re
    pw = pytest.importorskip('playwright.sync_api')
    js = (Path(__file__).parents[1]/'abhyasa/blocks/talk/talk.js').read_text()
    make = re.search(r'^const make = .*$', js, re.M)[0]
    light = re.search(r'^function light\(sec, beat\) \{.*?^\}', js, re.M | re.S)[0]
    with pw.sync_playwright() as p:
        if not Path(p.chromium.executable_path).exists(): pytest.skip("Playwright's Chromium is not installed")
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page(); pg.set_content(LIGHT_HTML)
            pg.add_script_tag(content=f'{make}\n{light}\nconst s = document.getElementById("s"); s.dataset.lits = JSON.stringify([[1, "softmax"]]); light(s, 1);')
            assert pg.evaluate("[...document.querySelectorAll('mark.lit')].map(m => [m.textContent, !!m.closest('.math')])") == [['softmax', False]]
        finally: b.close()
