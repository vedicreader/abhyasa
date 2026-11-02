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

def test_a_notebook_walk_uses_the_notebook_as_it_is(mk, walk_fake, lr):
    "One idea for each section, in the words and the code of the notebook, with its source; the walk page offers Learn the notebook in Leela and says where the copy is."
    cl = mk(); jid, p = nb_walk(cl, lr)
    j = lr.journey(jid)
    assert [s['read']['section'] for s in j.steps] == ['Introduction', 'Noise schedule'] and 'show_images(noised)' in j.steps[1]['read']['text']
    t = cl.get(f'/w/{jid}').text
    assert 'Learn the notebook in Leela' in t and f'action="/w/{jid}/notebook"' in t and 'Your notebook 15_DDPM.ipynb does not change.' in t
    assert f'walks/{jid}/15_DDPM.ipynb' in t

def test_learn_in_leela_writes_a_learning_copy_with_the_demos(mk, walk_fake, lr, monkeypatch):
    "The press writes the copy in the folder of the walk, with the demo of the step after its section, notes it on the walk, and goes to Leela. The notebook does not change."
    import abhyasa.blocks.walk.app as W
    import abhyasa.show
    monkeypatch.setattr(W, 'leela_link', lambda j, i=None, topic='', vault=None: f'http://127.0.0.1:5121/learn?walk={j.id}')
    cl = mk(); jid, p = nb_walk(cl, lr)
    was = p.read_bytes()
    slug = lr.journey(jid).steps[1]['slug']
    from rupaka.spec import gallery
    lr.put_demo({**gallery()['reciprocal-rank-fusion'], 'id': 'noise-demo'}, slug, by='test')
    r = cl.post(f'/w/{jid}/notebook', follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == f'http://127.0.0.1:5121/learn?walk={jid}'
    j = lr.journey(jid)
    c = notebook_copy(j)
    assert c and c.parent.name == jid and c.parent.parent.name == 'walks' and p.read_bytes() == was
    src = [x.source for x in read_nb(c).cells]
    assert len(src) == 7 and src[6].startswith('**A demo: Noise schedule.**') and '```rupaka' in src[6] and '"noise-demo"' in src[6]   # after the last cell of its section
