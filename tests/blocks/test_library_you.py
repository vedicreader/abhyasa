"Library and You: the Sources list of your documents, Your strengths on Your learning, and the empty lines of the four pages."
import time
from starlette.testclient import TestClient
from bs4 import BeautifulSoup
from talk_data import *
from test_tabs import current_tab
from abhyasa.app import mk_app
from abhyasa.store import temp_learning

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
    assert h.index('This week') < h.index('Your strengths') < h.index('What you learned')
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
    assert 'Vault shelves' not in h and '>your source<' in h and f'href="/w/{jid}"' in h and '<summary>More</summary>' in h
    assert f'href="/t/{tid}"' in h   # the talk made from the walk
    did = lr.journey(jid).source['doc_id']
    assert f'href="/v/store/{did}"' in h and len(rows(h)) == 1 and 'Attention Is All You Need' in rows(h)[0]
    assert time.strftime('%b %Y') in rows(h)[0]   # the date it was added
    more = BeautifulSoup(h, 'html.parser').select_one('details.more')
    assert 'Import vedicreader' in more.text and 'Index ramabana sessions' in more.text and not more.has_attr('open')

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

def test_a_paper_with_two_copies_is_one_row(mk, lr):
    "The PDF copy and the HTML copy of one arXiv paper show as one row, with both copies inside it."
    a = lr.vault.add('Attention is a weighted sum.', 'Attention Is All You Need', source='https://arxiv.org/pdf/1706.03762', kind='pdf')['doc_id']
    b = lr.vault.add('Attention is a weighted sum of values.', 'Attention Is All You Need (HTML)', source='https://arxiv.org/html/1706.03762v7', kind='web')['doc_id']
    lr.put_journey(dict(id='w-att', title='Attention', mode='walk', source=dict(shelf='store', doc_id=a, title='Attention Is All You Need'),
                        steps=[dict(slug='ranking', read=dict(shelf='store', doc_id=b, text='Attention is a weighted sum of values.'))]))
    h = mk().get('/sources').text
    assert len(rows(h)) == 1 and '2 copies' in rows(h)[0]
    assert f'href="/v/store/{a}"' in h and f'href="/v/store/{b}"' in h

def test_pasted_text_and_web_kinds(mk, lr):
    "A walk from pasted text shows as `text`; a page that research found shows as `from the web`."
    lr.put_journey(dict(id='my-notes-1', title='My notes', mode='walk', steps=[dict(slug='ranking', read=dict(shelf='store', doc_id='my-notes-1', text='A rank.'))]))
    w = lr.vault.add('A rank is a position.', 'Rank on the web', source='https://example.org/rank', kind='web')['doc_id']
    lr.put_journey(dict(id='w-topic', title='Ranks', mode='walk', steps=[dict(slug='ranking', read=dict(src='web', shelf='store', doc_id=w, text='A rank is a position.'))]))
    rs = rows(mk().get('/sources').text)
    assert any('My notes' in r and 'text' in r.split() for r in rs) and any('Rank on the web' in r and 'from the web' in r for r in rs)

# Each page of Library and You has one line when your learning is empty.

def test_empty_lines(fake):
    cl = TestClient(mk_app(temp_learning(), fake, hosts=('testserver',)))
    for u, line in (('/concepts', 'Concepts appear here when you start a walk.'),
                    ('/sources', 'Sources appear here when you start a walk from a paper, a link or a text.'),
                    ('/graph', 'Each idea that you learn shows here. Start with a walk.'), ('/learning', 'Nothing yet. Do a walk or a review.')):
        h = cl.get(u).text
        assert line in h and 'class="mute empty' in h, u
