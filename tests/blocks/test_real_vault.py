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

# The tutor finds passages on each shelf of documents. A store of names does not stop it.

def test_vault_source_skips_a_store_of_names(lr):
    names_store(lr); notes(lr)
    hs = VaultSource(lr).search('softmax weights')
    assert [h['title'] for h in hs] == ['notes/rank']
