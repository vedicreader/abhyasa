"More sources for a goal walk: each source files on its own job, a slow one joins the walk later, and Add a source on the plan page."
import threading, time, pytest
from pathlib import Path
from fastcore.nbio import new_nb, mk_cell, write_nb
import abhyasa.blocks.walk.app as walk_app
from abhyasa.sources import vault_roots
from test_sources_folder import public, two_notebooks, PLAN
from test_goal_walk import wait_for_walk

GOAL = 'Help me learn diffusion with course22 from the start'

@pytest.fixture
def home(tmp_path, monkeypatch):
    "A temp home folder with the folders `course22` (two notebooks) and `more` (one note)."
    monkeypatch.setattr(Path, 'home', lambda: tmp_path); monkeypatch.setenv('HOME', str(tmp_path))
    (d := tmp_path/'course22').mkdir(); two_notebooks(d)
    (m := tmp_path/'more').mkdir(); (m/'unet.md').write_text('# The U-net\n\nThe U-net predicts the noise in the image.')
    return tmp_path

def until(f, tries=200):
    "Ask `f` again until it gives a true value; give that value."
    for _ in range(tries):
        if x := f(): return x
        time.sleep(.05)
    raise AssertionError('it did not happen')

def walk(cl, home):
    return wait_for_walk(cl, cl.post('/walk/new', data=dict(q=GOAL, sources=[f'folder:{home/"course22"}'], chips='1')))

def test_a_slow_source_does_not_stop_the_plan(mk, lr, walk_fake, home, monkeypatch):
    "A clone that takes long: the walk opens after `FILE_WAIT`, with a line. When the clone is filed, it joins the chips of the walk, with its count."
    go = threading.Event()
    src = home/'src'; src.mkdir(); (src/'README.md').write_text('# B\n\nA repo on noise.')
    def clone(url, timeout=None): go.wait(10); return src
    public(monkeypatch, clone)
    monkeypatch.setattr(walk_app, 'FILE_WAIT', .3)
    walk_fake.rules['You plan a learning path'] = PLAN
    cl = mk()
    url = wait_for_walk(cl, cl.post('/walk/new', data=dict(q=GOAL, sources=[f'folder:{home/"course22"}', 'gh:a/b'], chips='1')))
    jid = url.split('/')[-1]
    j = lr.journey(jid)
    assert j['filing'] == ['gh:a/b'] and 'abhyasa is still filing b. The walk uses it when it is filed.' in cl.get(url).text
    assert j['chip_counts'] == {f'folder:{home/"course22"}': 2}   # the folder was filed before the plan
    go.set()
    j = until(lambda: (x := lr.journey(jid)) and not x.get('filing') and x)
    assert j['chips'] == [f'folder:{home/"course22"}', 'gh:a/b'] and j['chip_counts']['gh:a/b'] == 1
    assert not any('still filing' in n for n in j['notes']) and [f['root'] for f in j['filed']] == ['course22', 'a/b']

def test_add_a_source_to_a_walk_files_it(mk, lr, walk_fake, home):
    "The plan page of a goal walk has Add a source. A folder that you add is filed on its own job and joins the chips, with Undo."
    walk_fake.rules['You plan a learning path'] = PLAN
    cl = mk()
    url = walk(cl, home)
    jid = url.split('/')[-1]
    h = cl.get(url).text
    assert 'Add a source' in h and 'id="walk-src-form"' in h
    r = cl.post('/learn/walk-source', data=dict(jid=jid, q=f'{home/"more"}, {home/"course22"}'))   # the walk has course22: only `more` is new
    assert r.status_code == 200 and 'req-err' not in r.text
    j = until(lambda: (x := lr.journey(jid)) and not x.get('filing') and f'folder:{home/"more"}' in x['chips'] and x)
    assert j['chips'] == [f'folder:{home/"course22"}', f'folder:{home/"more"}'] and j['chip_counts'][f'folder:{home/"more"}'] == 1
    assert vault_roots(lr) == {'course22': 2, 'more': 1} and 'Added more: 1 file.' in cl.get(url).text
    assert 'Filing' not in cl.get('/learn/walk-source', params=dict(jid=jid)).text   # the line stops asking when nothing files

def test_add_a_source_says_why_it_refuses(mk, lr, walk_fake, home):
    walk_fake.rules['You plan a learning path'] = PLAN
    cl = mk()
    jid = walk(cl, home).split('/')[-1]
    h = cl.post('/learn/walk-source', data=dict(jid=jid, q='/etc')).text
    assert 'abhyasa reads only folders in your home folder.' in h and lr.journey(jid)['chips'] == [f'folder:{home/"course22"}']
    assert 'abhyasa cannot use nothing here as a source.' in cl.post('/learn/walk-source', data=dict(jid=jid, q='nothing here')).text
    assert cl.post('/learn/walk-source', data=dict(jid='no-such-walk', q='/etc')).status_code == 404

def test_add_a_source_picks_several_folders(mk, lr, walk_fake, home, monkeypatch):
    "Pick folders on the plan page: the chooser (faked) gives two folders, and each one is filed for the walk."
    import subprocess, abhyasa.blocks.add.app as add_app
    from starlette.testclient import TestClient
    monkeypatch.setattr(add_app, 'can_pick', lambda: True)
    (o := home/'other').mkdir(); (o/'a.md').write_text('# A\n\nAttention mixes tokens.')
    monkeypatch.setattr(add_app, '_osa', lambda args, **kw: subprocess.CompletedProcess(args, 0, stdout=f'{home/"more"}/\n{o}/\n', stderr=''))
    walk_fake.rules['You plan a learning path'] = PLAN
    cl = TestClient(mk().app, client=('127.0.0.1', 50000))
    jid = walk(cl, home).split('/')[-1]
    cl.post('/learn/walk-source', data=dict(jid=jid, pick='1'))
    j = until(lambda: (x := lr.journey(jid)) and len(x['chips']) == 3 and not x.get('filing') and x)
    assert j['chips'][1:] == [f'folder:{home/"more"}', f'folder:{o}']
