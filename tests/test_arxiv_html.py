"An arXiv paper is read from its HTML page first, so its passages keep their maths; the PDF is the fallback. No test uses the network."
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
