"Folders, local repos and GitHub repos as sources: filing, Undo, the chips of the Start box, and Start."
import json, time, pytest
from pathlib import Path
from fastcore.nbio import new_nb, mk_cell, write_nb
from abhyasa.sources import file_folder, file_repo, unfile, doc_pages, vault_roots, LinkError
from abhyasa.detect import named_sources

def two_notebooks(d):
    "Write 01_a.ipynb and 02_b.ipynb in the folder `d`."
    write_nb(new_nb([mk_cell('# Noise\n\nA diffusion model adds noise, then learns to remove it.', 'markdown')]), Path(d)/'01_a.ipynb')
    write_nb(new_nb([mk_cell('# Steps\n\nThe sampler removes the noise in small steps.', 'markdown')]), Path(d)/'02_b.ipynb')

def doc_meta(lr, x): return lr.vault.shelf(x.shelf).doc(x.doc_id)['meta']

@pytest.fixture
def home(tmp_path, monkeypatch):
    "A temp home folder with the folder `course22` of two notebooks."
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    d = tmp_path/'course22'; d.mkdir(); two_notebooks(d)
    return tmp_path

def public(monkeypatch, clone):
    "GitHub says that each repo is public, and `gh_clone` gives the folder `clone`. Nothing goes to the network."
    monkeypatch.setattr('abhyasa.sources.gh_public', lambda o, n: dict(private=False, size=10))
    monkeypatch.setattr('fossick.gh_clone', clone if callable(clone) else (lambda u: clone))

def test_folder_becomes_docs_with_root(lr, home):
    docs = file_folder(lr, home/'course22')
    assert len(docs) == 2 and {doc_meta(lr, x)['root'] for x in docs} == {'course22'}
    assert file_folder(lr, home/'course22') == docs   # a second run skips the same mtime

def test_path_outside_home_is_refused(lr, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path/'home')
    with pytest.raises(LinkError): file_folder(lr, tmp_path/'elsewhere')

def test_a_link_and_a_hidden_folder_are_refused(lr, home):
    (home/'.secret').mkdir(); (home/'link').symlink_to(home/'course22')
    for p in (home/'.secret', home/'link', home):
        with pytest.raises(LinkError): file_folder(lr, p)

def test_repo_uses_gh_clone(lr, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    clone = tmp_path/'.cache/fossick/git_clones/fastai-diffusion-nbs'; clone.mkdir(parents=True); two_notebooks(clone)
    public(monkeypatch, clone)
    docs = file_repo(lr, 'fastai/diffusion-nbs')
    m = doc_meta(lr, docs[0]); assert m['root'] == 'fastai/diffusion-nbs' and m['url'].startswith('https://github.com/fastai/diffusion-nbs/blob/')

def test_a_private_repo_is_not_cloned(lr, monkeypatch):
    got = []
    monkeypatch.setattr('abhyasa.sources.gh_public', lambda o, n: dict(private=True))
    monkeypatch.setattr('fossick.gh_clone', lambda u: got.append(u))
    with pytest.raises(LinkError, match='not a public repo'): file_repo(lr, 'a/b')
    assert not got

def test_named_sources_same_name_two_roots():
    p1, p2 = Path('/r1/x'), Path('/r2/x')
    cs = named_sources('Use x for this', names={'x': [p1, p2]})
    assert [(c.id, c.path) for c in cs] == [(f'folder:{p1}', str(p1)), (f'folder:{p2}', str(p2))]

def test_unfile_removes_only_what_start_added(lr, home):
    "Undo forgets what one filing added. A folder that was there before stays, and so does a file that changed since."
    first = file_folder(lr, home/'course22')
    (d := home/'more').mkdir()
    for k in 'abc': write_nb(new_nb([mk_cell(f'# {k}\n\nA note on noise, part {k}.', 'markdown')]), d/f'0_{k}.ipynb')
    docs = file_folder(lr, d)
    assert len(docs.added) == 3 and len(file_folder(lr, home/'course22').added) == 0
    import os; os.utime(d/'0_c.ipynb', (1e9, 1e9)); file_folder(lr, d)   # 0_c changed after Start
    assert unfile(lr, docs.added) == 2
    assert vault_roots(lr) == {'course22': 2, 'more': 1} and len(first.added) == 2

def test_doc_pages_finds_a_notebook_shelf_doc(lr, home):
    file_folder(lr, home/'course22')
    assert doc_pages(lr, 'course22/02_b').title == 'course22/02_b'

def wait_for_walk(cl, r, tries=200):
    "Ask the pending card again until the walk opens; give the redirect."
    import re
    for _ in range(tries):
        if 'HX-Redirect' in r.headers: return r.headers['HX-Redirect']
        m = re.search(r'hx-get="([^"]+)"', r.text); assert m, r.text
        time.sleep(.05); r = cl.get(m[1].replace('&amp;', '&'))
    raise AssertionError('the walk did not open')

PLAN = dict(title='Diffusion', subject='ml', steps=[dict(name='Ranking', statement='', slug='', why='Scores to places.', needs=[], ways=['code'])])

def test_failed_clone_keeps_the_walk(mk, lr, walk_fake, monkeypatch):
    def boom(u): raise IOError('no network')
    public(monkeypatch, boom)
    walk_fake.rules['You plan a learning path'] = PLAN
    lr.vault.shelf('notebooks').add('Notes on noise.', title='fb/01', source='/x/01.ipynb', kind='notebook', meta=dict(root='fastbook', path='/x/01.ipynb'))
    cl = mk()
    r = cl.post('/walk/new', data=dict(q='I want to fine-tune a diffusion model for my own comic book pages', sources=['gh:a/b', 'vault:fastbook'], chips='1'))
    url = wait_for_walk(cl, r)
    h = cl.get(url).text
    assert 'abhyasa could not clone a/b.' in h
    assert lr.journey(url.split('/')[-1])['chips'] == ['gh:a/b', 'vault:fastbook']

def test_start_files_a_folder_and_undo_forgets_it(mk, lr, walk_fake, home):
    walk_fake.rules['You plan a learning path'] = PLAN
    cl = mk()
    r = cl.post('/walk/new', data=dict(q='Help me learn diffusion with course22 from the start', sources=[f'folder:{home/"course22"}'], chips='1'))
    url = wait_for_walk(cl, r)
    h = cl.get(url).text
    assert 'Added course22: 2 notebooks.' in h and 'Undo' in h
    jid = url.split('/')[-1]
    assert 'Removed course22 from your vault: 2 documents.' in cl.post('/walk/unfile', data=dict(jid=jid, root='course22')).text
    assert vault_roots(lr) == {} and 'Added course22' not in cl.get(url).text

def test_removed_chip_is_not_filed(mk, lr, walk_fake, home):
    "The form sends only the chips that it shows: a removed chip is not filed."
    walk_fake.rules['You plan a learning path'] = PLAN
    cl = mk()
    url = wait_for_walk(cl, cl.post('/walk/new', data=dict(q='Help me learn diffusion with course22 from the start', chips='1')))
    assert vault_roots(lr) == {} and lr.journey(url.split('/')[-1])['chips'] == []

def test_read_route_shows_the_chips(mk, lr, home):
    from abhyasa.settings import set_val
    set_val('sources.roots', str(home))
    lr.vault.shelf('notebooks').add('Notes.', title='fb/01', source='/x/01.ipynb', kind='notebook', meta=dict(root='fastbook', path='/x/01.ipynb'))
    h = mk().get('/learn/read', params=dict(q='I want to make my own comic. Use course22 and fastbook. Also fastai/diffusion-nbs.')).text
    assert 'Sources for this goal' in h and 'aria-label="Remove course22"' in h
    assert 'a folder on this Mac · added when you press Start' in h and 'a GitHub repo · cloned when you press Start' in h
    assert '1 document' in h and 'in your vault' in h and 'abhyasa found these by their names' in h
    assert f'value="folder:{home/"course22"}"' in h and 'value="gh:fastai/diffusion-nbs"' in h and 'value="vault:fastbook"' in h
    assert 'class="go"' in h   # Start is on

def test_read_route_keeps_added_and_removed_chips(mk, home):
    cl = mk()
    p = str(home/'course22')
    h = cl.get('/learn/read', params=dict(q='', extra=[p])).text
    assert 'Write your goal in the box.' in h and f'value="folder:{p}"' in h and 'disabled' in h
    h = cl.get('/learn/read', params=dict(q='how attention works', extra=[p, 'not a source here'])).text
    assert 'A goal.' in h and f'value="folder:{p}"' in h and 'abhyasa cannot use not a source here as a source.' in h
    h = cl.get('/learn/read', params=dict(q='how attention works', extra=[p], drop=[f'folder:{p}'])).text
    assert f'value="folder:{p}"' not in h

def test_folder_line_counts_and_asks(mk, home):
    cl = mk()
    h = cl.get('/learn/read', params=dict(q=str(home/'course22'))).text
    assert 'A folder with 2 notebooks.' in h and 'Walk through it' in h and 'Use it for a goal' in h
    h = cl.get('/learn/read', params=dict(q='/etc')).text
    assert 'abhyasa reads only folders in your home folder.' in h
