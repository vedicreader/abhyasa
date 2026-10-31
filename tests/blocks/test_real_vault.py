"Pages over a vault with the shapes of a real vault: a store of names (`entities`) with no `doc_id`, shelves from other tools, and odd links."
from bs4 import BeautifulSoup
from abhyasa.ground import VaultSource

def names_store(lr):
    "The store of names that vishalakshi keeps beside the main shelf: columns kind, canon and freq, and no doc_id."
    lr.vault.db.get_graph('store', ann=False)
    lr.vault.db.get_graph('dialog0', ann=False)   # a store of names of another shelf: `dialog0_entities`
    assert {'entities', 'dialog0_entities'} <= set(lr.vault.db.table_names())   # the tables are in the vault; vishalakshi 0.1.36 no longer lists them as shelves

def notes(lr):
    "One folder file on the notebooks shelf; return its doc id."
    sh = lr.vault.shelf('notebooks')
    d = sh.add('A rank is a position in a list. Softmax makes weights.', 'notes/rank', source='/tmp/notes/rank.md')
    sh.set_meta(d['doc_id'], root='notes', path='/tmp/notes/rank.md', mtime=1.0)
    return d['doc_id']

def shelves(lr): return {s['store'] for s in lr.vault.shelves()}

# Library > Sources gave error 500: it opened each store of the vault as a shelf of documents, and a store of names has no doc_id.

def test_sources_page_with_a_store_of_names(mk, lr):
    names_store(lr); notes(lr)
    r = mk().get('/sources')
    assert r.status_code == 200
    assert 'notes' in [li.get_text(' ', strip=True).split(' ')[0] for li in BeautifulSoup(r.text, 'html.parser').select('ul.sources > li')]

# The vault viewer opened any shelf name in the link, so a GET added a new empty shelf to the vault, and a store of names gave an error.

def test_vault_viewer_never_makes_a_shelf(mk, lr):
    names_store(lr); did = notes(lr)
    cl, before = mk(), shelves(lr)
    for u in ('/v/entities/x', '/v/dialog0_entities/x', '/v/nope/x', '/v/r/x'):
        r = cl.get(u)
        assert r.status_code == 200 and 'No such document' in r.text, u
    assert shelves(lr) == before
    assert 'Softmax makes weights' in cl.get(f'/v/notebooks/{did}').text

# A walk from a document on a shelf that is not a shelf of documents says that there is no such document. It does not make the shelf.

def test_walk_from_a_store_of_names(mk, lr):
    names_store(lr)
    cl, before = mk(), shelves(lr)
    for sh in ('entities', 'nope'):
        r = cl.post('/walk/new', data=dict(ref='x', shelf=sh))
        assert r.status_code == 200 and 'req-err' in r.text, sh
    assert shelves(lr) == before

# The tutor finds passages on each shelf of documents. A store of names does not stop it.

def test_vault_source_skips_a_store_of_names(lr):
    names_store(lr); notes(lr)
    hs = VaultSource(lr).search('softmax weights')
    assert [h['title'] for h in hs] == ['notes/rank']

# A source that fails gives no passages, as before, but the log now says why. Before, the error was lost, and a broken shelf looked like no passages.

def test_a_failed_source_is_in_the_log(lr, caplog):
    from abhyasa.ground import concept_grounds
    class Broken:
        name = 'broken'
        def search(self, q, k=4): raise RuntimeError('no such column: doc_id')
    with caplog.at_level('WARNING'): assert list(concept_grounds(lr.concept('ranking'), [Broken()])) == []
    assert 'no such column: doc_id' in caplog.text

# An empty clip is a bad request, not an error of the server.

def test_empty_clip_is_a_bad_request(mk):
    r = mk(['voice']).post('/voice/stt', content=b'')
    assert r.status_code == 400 and r.json()['text'] == ''

# A very long query is cut to `Q_MOST` characters, so the page and the search stay small.

def test_long_query_is_cut(mk):
    from abhyasa.blocks.search.app import Q_MOST
    h = BeautifulSoup(mk().get('/search', params=dict(q='x' * 5000)).text, 'html.parser')
    assert h.select_one('h1.query').get_text() == f"“{'x' * Q_MOST}”"

# A model that fails, or that gives JSON with no question, gave error 500 on the session page. Now the page says so and has Try again.

def test_session_page_when_the_model_gives_no_question(mk, fake):
    fake.dflt = '[1, 2]'
    cl = mk()
    sid = cl.get('/start?focus=ranking', follow_redirects=False).headers['location'].split('/')[-1]
    r = cl.get(f'/s/{sid}')
    assert r.status_code == 200 and 'The tutor could not write the next question.' in r.text and f'href="/s/{sid}"' in r.text

def test_a_failed_grade_keeps_the_answer(mk, fake):
    cl = mk()
    sid = cl.get('/start?focus=ranking', follow_redirects=False).headers['location'].split('/')[-1]
    assert cl.get(f'/s/{sid}').status_code == 200
    def down(p, sp): raise RuntimeError('the route timed out')
    fake.rules['You grade one answer'] = down
    r = cl.post(f'/s/{sid}/answer', data=dict(answer='A rank is a position.'))
    assert r.status_code == 503 and r.text == 'The tutor could not grade your answer. Try again.'

# The same in a walk: a check that the model could not write shows a line and Try again, and a failed grade is a 503 with a plain line.

def test_walk_check_when_the_model_fails(mk, walk_fake, lr):
    from walk_data import walk
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why='plain words fit'))
    walk_fake.dflt = '[1, 2]'
    card = cl.get(f'/w/{jid}/1/check')
    assert card.status_code == 200 and 'The tutor could not write the check.' in card.text and f'hx-get="/w/{jid}/1/check"' in card.text
    walk_fake.dflt = dict(question='What does a rank tell you?', answer='Its position.', rubric=['position'])
    assert 'What does a rank tell you?' in cl.get(f'/w/{jid}/1/check').text
    def down(p, sp): raise RuntimeError('the route timed out')
    walk_fake.rules['You grade one answer'] = down
    r = cl.post(f'/w/{jid}/1/answer', data=dict(answer='the rank is a position'))
    assert r.status_code == 503 and r.text == 'The tutor could not grade your answer. Try again.'

# "Add to a walk" on a concept page added a step with no check, and the walk pages then gave error 500 (KeyError: 'check').

def test_a_concept_added_to_a_walk_has_a_check(mk, walk_fake, lr):
    from walk_data import walk
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    n = len(lr.journey(jid).steps)
    assert 'Added to' in cl.post('/journeys/attach', data=dict(jid=jid, slug='ranking', src='concept')).text
    assert lr.journey(jid).steps[n]['check']['kind']
    for u in (f'/w/{jid}/{n - 1}', f'/w/{jid}/{n}', f'/w/{jid}/{n}/check'): assert cl.get(u).status_code == 200, u

def test_an_old_walk_step_with_no_check(mk, walk_fake, lr):
    from walk_data import walk
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    j = lr.journey(jid); j.steps.append(dict(slug='ranking', status='todo', why='you added it')); lr.put_journey(j)   # as abhyasa 0.0.15 left it
    n = len(j.steps) - 1
    assert lr.journey(jid).steps[n]['check']['kind'] == 'short'
    for u in (f'/w/{jid}/{n - 1}', f'/w/{jid}/{n}', f'/w/{jid}/{n}/check'): assert cl.get(u).status_code == 200, u
