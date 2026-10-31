"Pages over a vault with the shapes of a real vault: a store of names (`entities`) with no `doc_id`, shelves from other tools, and odd links."
from bs4 import BeautifulSoup
from abhyasa.ground import VaultSource

def names_store(lr):
    "The store of names that vishalakshi keeps beside the main shelf: columns kind, canon and freq, and no doc_id."
    lr.vault.db.get_graph('store', ann=False)
    lr.vault.db.get_graph('dialog0', ann=False)   # a store of names of another shelf: `dialog0_entities`
    assert {'entities', 'dialog0_entities'} <= {s['store'] for s in lr.vault.shelves()}

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
