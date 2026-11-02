"Every place that shows one of your notebooks offers Open in Leela, at its section when abhyasa knows it; with no Leela, one plain line says how to start it."
import tempfile
from pathlib import Path
from fastcore.nbio import new_nb, mk_cell, write_nb
from fastcore.utils import first, AttrDict
from abhyasa.sources import index_notebooks
from abhyasa.contract import read_handoff
from abhyasa.core.leela import LEELA_OFF

def notebook(lr):
    "One notebook in the vault, with two sections; its shelf and its doc id."
    d = Path(tempfile.mkdtemp())/'nbs'; d.mkdir()
    write_nb(new_nb([mk_cell('# DDPM', 'markdown'), mk_cell('## Imports', 'markdown'), mk_cell('import torch')]), d/'15_DDPM.ipynb')
    index_notebooks(lr.vault, [d])
    return 'notebooks', first(lr.doc_shelf('notebooks').t.docs())['id']

def up(monkeypatch, url='http://127.0.0.1:5121'):
    "Leela runs at `url` (None: it does not run)."
    monkeypatch.setattr('abhyasa.core.leela.leela_base', lambda: url)

def query(t):
    "The handoff in the first Open in Leela link of the page text `t`."
    href = t.split('class="leela-open"', 1)[0].rsplit('href="', 1)[1].split('"', 1)[0].replace('&amp;', '&')
    return read_handoff(href.split('?', 1)[1])

def test_the_vault_page_of_a_notebook_opens_it_in_leela(mk, lr, monkeypatch):
    "The page of a notebook (it opens in the side pane from a source line) has Open in Leela, with the doc, the shelf and go; another page has none."
    up(monkeypatch); cl = mk(); shelf, doc = notebook(lr)
    q = query(cl.get(f'/v/{shelf}/{doc}').text)
    assert (q.doc, q.shelf, q.go, q.walk) == (doc, shelf, True, '')

def test_a_source_line_and_a_link_line_of_a_notebook_open_it_in_leela(mk, lr, monkeypatch):
    "A source line of a passage from a notebook links to Leela at the cell of its section; a link to a notebook (a lesson notebook that a transcript names) too."
    from abhyasa.core import SourceLine, SourceLinks
    from fasthtml.common import to_xml
    up(monkeypatch); mk(); shelf, doc = notebook(lr)
    q = query(to_xml(SourceLine(AttrDict(label='Your source', title='15_DDPM', href=f'/v/{shelf}/{doc}', place='Imports', url='', date=''), cell=1)))
    assert (q.doc, q.cell, q.go) == (doc, 1, True)
    assert query(to_xml(SourceLinks([AttrDict(text='Lesson notebook · 15_DDPM', href=f'/v/{shelf}/{doc}')]))).doc == doc
    assert 'leela-open' not in to_xml(SourceLine(AttrDict(label='Your source', title='x', href='/v/store/nope', place='', url='', date='')))

def test_an_idea_from_a_notebook_opens_it_at_its_section(mk, lr, monkeypatch):
    "The page of an idea from a notebook names the notebook and opens it in Leela at the first cell of the section of the idea."
    up(monkeypatch); cl = mk(); shelf, doc = notebook(lr)
    c = lr.put('Imports of DDPM', 'The imports.', 'ml', provenance=[dict(src=f'vault:{shelf}', doc_id=doc)])
    lr.put_journey(dict(id='w1', title='W', mode='walk', steps=[dict(slug=c.slug, read=dict(doc_id=doc, cells=[1, 2]), check=dict(kind='short'))]))
    t = cl.get(f'/c/{c.slug}').text
    assert 'From your notebook' in t and (query(t).doc, query(t).cell) == (doc, 1)

def test_with_no_leela_each_place_says_how_to_start_it(mk, lr, monkeypatch):
    "When Leela does not run, the place says so in one plain line, with no link."
    up(monkeypatch, None); cl = mk(); shelf, doc = notebook(lr)
    t = cl.get(f'/v/{shelf}/{doc}').text
    assert LEELA_OFF in t and '/learn?' not in t
