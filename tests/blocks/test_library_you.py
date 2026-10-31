"Library and You: the Sources list of your documents, Your strengths on Your learning, and the empty lines of the four pages."
import time
from bs4 import BeautifulSoup
from talk_data import *
from test_tabs import current_tab

def seen_concepts(lr):
    "Two misses on ranking: a weak spot."
    lr.update('ranking', misses=2, seen=2, misconceptions=['scores add'])

def paper_walk(cl, lr): return prep_walk(lr, walk(cl, lr))

def rows(h):
    "The rows of the Sources list, as their text."
    return [li.get_text(' ', strip=True) for li in BeautifulSoup(h, 'html.parser').select('ul.sources > li')]

def folder(lr, root, n=3):
    "File `n` documents of the folder `root` on the notebooks shelf, as Start does; return them as Start keeps them."
    sh, out = lr.vault.shelf('notebooks'), []
    for i in range(n):
        d = sh.add(f'Part {i} of {root}. A rank is a position in a list.', f'{root}/part{i}', source=f'/tmp/{root}/part{i}.md')
        sh.set_meta(d['doc_id'], root=root, path=f'/tmp/{root}/part{i}.md', mtime=1.0)
        out.append(dict(shelf='notebooks', doc_id=d['doc_id'], title=f'{root}/part{i}', url=f'/tmp/{root}/part{i}.md', mtime=1.0))
    return out

# Your strengths is a part of Your learning, after This week, with the one way to practice the weak spots.

def test_strengths_is_a_section_of_your_learning(mk, lr):
    seen_concepts(lr)
    h = mk().get('/learning').text
    assert 'Your strengths' in h and 'Practice my weak spots' in h and 'href="/you/strengths"' in h
    assert 'href="/start?drill=1"' in h and 'Ranking' in h

def test_no_strengths_before_a_concept_is_seen(mk):
    assert 'Your strengths' not in mk().get('/learning').text

def test_strengths_route_still_answers(mk):
    r = mk().get('/you/strengths')
    assert r.status_code == 200 and current_tab(r.text) == 'You'
    assert 'Ways you learn' in r.text and 'How often to try a new way' in r.text

# Sources lists your documents, with the walks and talks that use them. The shelf names and the indexers leave the page, or go under More.

def test_sources_lists_documents_not_shelves(mk, lr, talk_fake):
    cl = mk(); jid = paper_walk(cl, lr); tid = make_talk(cl, jid)
    h = cl.get('/sources').text
    assert 'Vault shelves' not in h and '>your source<' in h and f'href="/w/{jid}"' in h and '<summary>Add more sources</summary>' in h
    assert f'href="/t/{tid}"' in h   # the talk made from the walk
    did = lr.journey(jid).source['doc_id']
    assert f'href="/v/store/{did}"' in h and len(rows(h)) == 1 and 'Attention Is All You Need' in rows(h)[0]
    assert time.strftime('%b %Y') in rows(h)[0]   # the date it was added
    more = BeautifulSoup(h, 'html.parser').select_one('details.more')
    assert 'Import vedicreader' in more.text and 'Index ' not in more.text and not more.has_attr('open')

def test_a_filed_folder_is_one_row_with_undo(mk, lr):
    "A folder that Start filed now is one row, with its count of documents and Undo, which goes to the walk's Undo."
    ds = folder(lr, 'course')
    lr.put_journey(dict(id='w-course', title='Walk through course', mode='walk', steps=[], source=dict(docs=ds),
                        filed=[dict(root='course', docs=ds, at=time.time(), notebooks=0)]))
    h = mk().get('/sources').text
    rs = rows(h)
    assert len(rs) == 1 and 'course' in rs[0] and '3 documents' in rs[0] and 'Undo' in rs[0] and 'filed' in rs[0]
    assert 'hx-post="/walk/unfile"' in h and 'href="/w/w-course"' in h

def test_an_old_folder_has_remove(mk, lr):
    "After the hour of Undo, the row has Remove: it forgets each document of the folder."
    ds = folder(lr, 'notes', 2)
    lr.put_journey(dict(id='w-notes', title='Notes', mode='walk', steps=[], source=dict(docs=ds), filed=[dict(root='notes', docs=ds, at=time.time() - 7200)]))
    cl = mk()
    h = cl.get('/sources').text
    assert 'Remove' in h and 'Undo' not in h and 'hx-post="/sources/remove"' in h
    r = cl.post('/sources/remove', data=dict(shelf='notebooks', root='notes')).text
    assert 'Removed notes from your vault: 2 documents.' in r
    assert rows(cl.get('/sources').text) == [] and not lr.vault.shelf('notebooks').t.docs(where="json_extract(meta, '$.root') = 'notes'")
    assert 'nothing to remove' in cl.post('/sources/remove', data=dict(shelf='notebooks', root='notes')).text

def test_a_paper_with_its_copies_is_one_row(mk, lr):
    "The PDF copy, the HTML copy (`abs/<id>`) and a changed HTML copy (`abs/<id>?html=<sha>`) of one arXiv paper show as one row, with the copies inside it."
    add = lambda src, t: lr.vault.add(f'Attention is a weighted sum. {t}', t, source=src, kind='pdf')['doc_id']
    a = add('https://arxiv.org/pdf/1706.03762', 'Attention Is All You Need')
    b = add('https://arxiv.org/abs/1706.03762', 'Attention Is All You Need (HTML)')
    c = add('https://arxiv.org/abs/1706.03762?html=0123456789', 'Attention Is All You Need (HTML, new)')
    lr.put_journey(dict(id='w-att', title='Attention', mode='walk', source=dict(shelf='store', doc_id=a, title='Attention Is All You Need'),
                        steps=[dict(slug='ranking', read=dict(shelf='store', doc_id=d, text='Attention is a weighted sum.')) for d in (b, c)]))
    h = mk().get('/sources').text
    assert len(rows(h)) == 1 and '3 copies' in rows(h)[0]
    assert all(f'href="/v/store/{d}"' in h for d in (a, b, c))

def test_paper_id_from_any_arxiv_link():
    "One id for each form of an arXiv link: abs, pdf and html, a version, a query, and the old form of an id. Another link has none."
    from abhyasa.blocks.sources.app import _paper
    for u in ('https://arxiv.org/pdf/1706.03762', 'https://arxiv.org/pdf/1706.03762v7.pdf', 'https://arxiv.org/abs/1706.03762?html=0123456789',
              'arxiv.org/abs/1706.03762v2', 'https://arxiv.org/html/1706.03762v7', 'https://www.arxiv.org/abs/1706.03762#s1'):
        assert _paper(u) == '1706.03762', u
    assert _paper('https://arxiv.org/abs/hep-th/9901001v2?html=ab') == 'hep-th/9901001'
    assert _paper('https://example.org/1706.03762') == '' and _paper('/tmp/attention.pdf') == ''

def test_one_undo_limit_for_the_walk_and_sources(mk, lr):
    "The walk page and Sources read the one Undo limit in core: just inside it both show Undo, just outside it neither does."
    from abhyasa.core import UNDO_FOR
    ds = folder(lr, 'course')
    for at, shows in ((time.time() - UNDO_FOR + 60, True), (time.time() - UNDO_FOR - 60, False)):
        lr.put_journey(dict(id='w-course', title='Walk through course', mode='walk', steps=[], source=dict(url='/tmp/course', docs=ds), filed=[dict(root='course', docs=ds, at=at)]))
        cl = mk()
        assert ('Added course' in cl.get('/w/w-course').text) == shows
        assert ('hx-post="/walk/unfile"' in cl.get('/sources').text) == shows

def test_undo_on_sources_gives_a_row(mk, lr):
    "Undo on Sources swaps its row for a list item that says what it removed; the walk page keeps its plain line."
    ds = folder(lr, 'course')
    lr.put_journey(dict(id='w-course', title='Walk', mode='walk', steps=[], source=dict(docs=ds), filed=[dict(root='course', docs=ds, at=time.time())]))
    cl = mk()
    hx = {'HX-Request': 'true'}
    li = BeautifulSoup(cl.post('/walk/unfile', data=dict(jid='w-course', root='course', row='1'), headers=hx).text, 'html.parser').find()
    assert li.name == 'li' and li.p.get_text() == 'Removed course from your vault: 3 documents.'
    assert BeautifulSoup(cl.post('/walk/unfile', data=dict(jid='w-course', root='course'), headers=hx).text, 'html.parser').find().name == 'p'

def test_subjects_show_their_labels(mk, lr):
    "Your learning names each subject by its label: ML, and General for no subject."
    lr.put('Loose idea', 'An idea with no subject.', '')
    h = mk().get('/learning').text
    assert '>ML</a>' in h and '>General</a>' in h and '>general</a>' not in h

def test_pasted_text_and_web_kinds(mk, lr):
    "A walk from pasted text shows as `text`; a page that research found shows as `from the web`."
    lr.put_journey(dict(id='my-notes-1', title='My notes', mode='walk', steps=[dict(slug='ranking', read=dict(shelf='store', doc_id='my-notes-1', text='A rank.'))]))
    w = lr.vault.add('A rank is a position.', 'Rank on the web', source='https://example.org/rank', kind='web')['doc_id']
    lr.put_journey(dict(id='w-topic', title='Ranks', mode='walk', steps=[dict(slug='ranking', read=dict(src='web', shelf='store', doc_id=w, text='A rank is a position.'))]))
    rs = rows(mk().get('/sources').text)
    assert any('My notes' in r and 'text' in r.split() for r in rs) and any('Rank on the web' in r and 'from the web' in r for r in rs)

# Each page of Library and You has one line when your learning is empty.

