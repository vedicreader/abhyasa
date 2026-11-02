"Delete a walk from its ⋯ menu or from its row on Home, and learn a walk made from one of your notebooks in Leela, with a learning copy."
import json, tempfile, time
from pathlib import Path
from fastcore.nbio import new_nb, mk_cell, write_nb, read_nb
from fastcore.utils import first
from walk_data import walk
from abhyasa.sources import index_notebooks
from abhyasa.contract import notebook_copy

def test_the_menu_of_the_walk_has_delete_with_one_confirm(mk, walk_fake, lr):
    "The walk page and the row on Home have the ⋯ menu with Delete this walk. The confirm says what goes and what stays."
    cl = mk(); jid = walk(cl, lr)
    for url in (f'/w/{jid}', '/'):
        t = cl.get(url).text
        assert 'class="more-menu walk-menu"' in t and 'Delete this walk' in t and f'action="/w/{jid}/drop"' in t
        assert 'Your answers, your attempts and what you learned stay. Its side walks go with it.' in t

def test_delete_removes_the_plan_and_its_side_walks_and_keeps_the_answers(mk, walk_fake, lr):
    "Delete: the walk, its history and its side walks go; the attempts and the concepts stay; the list of walks opens."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    cl.get(f'/w/{jid}/0/check'); cl.post(f'/w/{jid}/0/answer', data=dict(answer='the rank', confidence=70))
    slug = lr.journey(jid).steps[0]['slug']; n = len(lr.attempts(slug))
    cl.post(f'/w/{jid}/edit', data=dict(slug=lr.journey(jid).steps[1]['slug'], act='skip'))
    lr.put_journey(dict(id='side1', title='Side', mode='walk', parent=dict(walk=jid, step=1), depth=1, steps=[dict(slug=slug, status='todo', check=dict(way='words', kind='short', depth=2))]))
    r = cl.post(f'/w/{jid}/drop', follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == '/'
    assert lr.journey(jid) is None and lr.journey('side1') is None and not lr.edits('walk', jid)
    assert n and len(lr.attempts(slug)) == n and lr.concept(slug)
    assert cl.post('/w/nope/drop').status_code == 404

def nb_walk(cl, lr):
    "A walk from one of your notebooks: a title and two sections, the second with code that draws."
    d = Path(tempfile.mkdtemp())/'nbs'; d.mkdir()
    cells = [mk_cell('# DDPM', 'markdown'), mk_cell('## Introduction', 'markdown'), mk_cell('The 2020 paper made some crucial assumptions that simplify the training of the model.', 'markdown'),
             mk_cell('## Noise schedule', 'markdown'), mk_cell('The noise grows at each step of the forward process, as the picture shows.', 'markdown'), mk_cell('show_images(noised)')]
    p = d/'15_DDPM.ipynb'; write_nb(new_nb(cells), p)
    index_notebooks(lr.vault, [d])
    doc = first(lr.doc_shelf('notebooks').t.docs())
    r = cl.post('/walk/new', data=dict(ref=doc['id'], shelf='notebooks'))
    return r.headers['hx-redirect'].split('/')[2], p

def test_a_notebook_walk_uses_the_notebook_as_it_is(mk, walk_fake, lr, monkeypatch):
    "One idea for each section, in the words and the code of the notebook, with its source; the walk page offers Learn the notebook in Leela and says where the copy is."
    import abhyasa.blocks.walk.ui as U
    monkeypatch.setattr(U, 'leela_base', lambda: 'http://127.0.0.1:5121')
    cl = mk(); jid, p = nb_walk(cl, lr)
    j = lr.journey(jid)
    assert [s['read']['section'] for s in j.steps] == ['Introduction', 'Noise schedule'] and 'show_images(noised)' in j.steps[1]['read']['text']
    t = cl.get(f'/w/{jid}').text
    assert 'Learn the notebook in Leela' in t and f'action="/w/{jid}/notebook' in t and 'Your notebook 15_DDPM.ipynb' not in t and '15_DDPM.ipynb, which does not change.' in t
    assert f'walks/{jid}/15_DDPM.ipynb' in t

def test_with_no_leela_the_walk_says_how_to_start_it(mk, walk_fake, lr, monkeypatch):
    "When Leela does not run, the walk page and the step say so in one plain line, with no button that goes to a broken page."
    import abhyasa.blocks.walk.ui as U
    from abhyasa.core.leela import LEELA_OFF
    monkeypatch.setattr(U, 'leela_base', lambda: None)
    cl = mk(); jid, p = nb_walk(cl, lr); cl.post(f'/w/{jid}/start')
    for url in (f'/w/{jid}', f'/w/{jid}/0'):
        t = cl.get(url).text
        assert LEELA_OFF in t and f'action="/w/{jid}/notebook' not in t

def press(cl, lr, monkeypatch, i=None):
    "Press Open in Leela on notebook walk `jid` (at idea `i`) with Leela at port 5121; the walk, the notebook and the response."
    import abhyasa.blocks.walk.app as W
    from abhyasa.contract import handoff
    monkeypatch.setattr(W, 'leela_open', lambda j, i=None, cell=None, vault=None: 'http://127.0.0.1:5121' + handoff(j.id, i, cell=cell, go=True))
    jid, p = nb_walk(cl, lr)
    return jid, p, cl.post(f'/w/{jid}/notebook' + ('' if i is None else f'?i={i}'), follow_redirects=False)

def test_learn_in_leela_writes_a_learning_copy_with_the_demos(mk, walk_fake, lr, monkeypatch):
    "The press writes the copy in the folder of the walk, with a line back to the walk first and the demo of the step after its section, notes it on the walk, and goes to Leela at once. The notebook does not change."
    import abhyasa.show
    cl = mk()
    orig = lr.put_demo
    jid, p, r = press(cl, lr, monkeypatch)   # the first press: no demo yet
    slug = lr.journey(jid).steps[1]['slug']
    from rupaka.spec import gallery
    lr.put_demo({**gallery()['reciprocal-rank-fusion'], 'id': 'noise-demo'}, slug, by='test')
    was = p.read_bytes()
    r = cl.post(f'/w/{jid}/notebook?i=1', follow_redirects=False)
    j = lr.journey(jid)
    c = notebook_copy(j)
    assert r.status_code == 303 and r.headers['location'] == f'http://127.0.0.1:5121/learn?walk={jid}&step=1&cell=4&go=1'   # the heading of Noise schedule, after the line back
    assert c and c.parent.name == jid and c.parent.parent.name == 'walks' and p.read_bytes() == was
    src = [x.source for x in read_nb(c).cells]
    assert src[0].startswith('**A learning copy of 15_DDPM.ipynb**') and f'/w/{jid})' in src[0].replace('>', '') and src[4] == '## Noise schedule'
    assert len(src) == 8 and src[7].startswith('**A demo: Noise schedule.**') and '```rupaka' in src[7] and '"noise-demo"' in src[7]   # after the last cell of its section
    assert type(j.notebook['opened']) is float and j.notebook['wrote']

def test_a_copy_that_you_changed_stays(mk, walk_fake, lr, monkeypatch):
    "A copy that you changed in Leela is not written again: the next press opens it as it is."
    cl = mk(); jid, p, r = press(cl, lr, monkeypatch, 0)
    c = notebook_copy(lr.journey(jid))
    nb = read_nb(c); nb.cells.append(mk_cell('x = 1  # my own cell')); write_nb(nb, c)
    mine = c.read_bytes()
    r = cl.post(f'/w/{jid}/notebook?i=0', follow_redirects=False)
    assert r.status_code == 303 and 'cell=2' in r.headers['location'] and c.read_bytes() == mine

def test_the_copy_runs_in_the_folder_of_the_notebook(mk, walk_fake, lr, monkeypatch):
    "`copy_home` of the copy is the folder of your notebook, so Leela runs it there; a file that is not a copy has none."
    from abhyasa.contract import copy_home
    cl = mk(); jid, p, r = press(cl, lr, monkeypatch)
    assert copy_home(notebook_copy(lr.journey(jid))) == p.parent and copy_home(p) is None
