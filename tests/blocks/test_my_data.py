"Your data: a folder that the exercises run on. It is not filed as a source, it shows on the course and walk pages, the Start box can keep one, and it goes to Leela in the notebook spec."
import re, time
import abhyasa.walk as walk_engine
from abhyasa.contract import _GOOD
from abhyasa.course import join_course
from abhyasa.llm import Fake
from test_goal_walk import wait_for_walk

def course_walk(lr):
    "A goal walk of two ideas, as the stage of its course. The second idea has a notebook check."
    for n in ('Captions', 'LoRA'): lr.put(n, f'{n} for a comic.', 'ml')
    lr.put_journey(dict(id='gw', title='Comic', goal='Make a Ramayana comic with a LoRA', mode='walk', source=None, started=None, created=1.,
                        steps=[dict(slug='captions', status='todo', check=dict(way='words', kind='short', depth=2)),
                               dict(slug='lora', status='todo', check=dict(way='code', kind='notebook', depth=3))], chips=[], chip_counts={}))
    return join_course(lr, 'gw')

def episodes(tmp_path, monkeypatch):
    "A home folder with one data folder in it: the Ramayana episodes."
    monkeypatch.setenv('HOME', str(tmp_path.resolve()))
    d = tmp_path.resolve()/'ramayana'; d.mkdir(); (d/'episodes.json').write_text('{}'); (d/'characters.json').write_text('[]')
    return d

MINE = [dict(path='~/ramayana', note='The episodes that my scenarios run on.')]

def test_add_a_source_as_data_is_not_filed(mk, lr, tmp_path, monkeypatch):
    "Add a source with My data for the exercises: the folder goes on the course and its walk, and abhyasa files nothing. Learn from it is the default."
    d, c = episodes(tmp_path, monkeypatch), course_walk(lr)
    cl = mk()
    t = cl.get('/w/gw').text
    assert 'value="learn" checked' in t and 'My data for the exercises' in t
    r = cl.post('/learn/walk-source', data=dict(jid='gw', q=str(d), use='data', note=MINE[0]['note']))
    assert r.status_code == 200 and 'Kept ramayana as your data for the exercises' in r.text
    j = lr.journey('gw')
    assert j.data == MINE and lr.course(c.id).data == MINE
    assert j.chips == [] and not j.get('filing') and lr.course(c.id).sources == []   # not a source: nothing is filed
    assert not lr.vault.shelf('notebooks').sources()

def test_only_a_folder_can_be_data(mk, lr, tmp_path, monkeypatch):
    "A GitHub repo or a path outside the home folder is not your data: the line says why, and nothing is kept."
    episodes(tmp_path, monkeypatch); course_walk(lr)
    cl = mk()
    assert 'Only a folder on this Mac can be your data.' in cl.post('/learn/walk-source', data=dict(jid='gw', q='fastai/diffusion-nbs', use='data')).text
    assert 'not in your home folder' in cl.post('/learn/walk-source', data=dict(jid='gw', q='/etc', use='data')).text
    assert not lr.journey('gw').get('data')

def test_course_page_shows_your_data_and_removes_one(mk, lr, tmp_path, monkeypatch):
    "The course page adds a folder under Your data, shows its note, and × removes it from the course and its walk."
    d, c = episodes(tmp_path, monkeypatch), course_walk(lr)
    cl = mk()
    assert 'Your data' in cl.get(f'/course/{c.id}').text
    r = cl.post(f'/course/{c.id}/data', data=dict(path=str(d), note=MINE[0]['note']))
    assert '~/ramayana' in r.text and MINE[0]['note'] in r.text and lr.journey('gw').data == MINE
    assert '~/ramayana' in cl.get(f'/course/{c.id}').text
    assert 'no folder' in cl.post(f'/course/{c.id}/data', data=dict(path='~/nothing')).text
    r = cl.post(f'/course/{c.id}/data/drop', data=dict(path='~/ramayana'))
    assert '~/ramayana' not in r.text and lr.course(c.id).data == [] and lr.journey('gw').data == []

def test_data_goes_to_leela_in_the_notebook_spec(lr, tmp_path, monkeypatch):
    "The tutor that writes the notebook step sees the folder, its note and its files. The spec that Leela reads has the folder, also when the model leaves it out."
    d, c = episodes(tmp_path, monkeypatch), course_walk(lr)
    from abhyasa.course import add_data
    add_data(lr, c.id, str(d), MINE[0]['note'])
    spec = {**_GOOD, 'data': []}
    f = Fake({'Return JSON: {"task"': spec})
    got = walk_engine.nb_spec(lr, f, lr.journey('gw'), 1)
    p = f.calls[-1][0]
    assert 'RAMAYANA' in p and '~/ramayana' in p and MINE[0]['note'] in p and 'characters.json, episodes.json' in p
    want = dict(name='RAMAYANA', path='~/ramayana', what=f"{MINE[0]['note']} It holds: characters.json, episodes.json.", need=False)
    assert got.data == [want] and lr.journey('gw').steps[1]['nb']['data'] == [want]

def test_walk_page_shows_your_data_and_removes_one(mk, lr, tmp_path, monkeypatch):
    "The walk page shows each data folder with its note under Sources; × removes it from the course and its walk. A walk with no course keeps it on the walk."
    from abhyasa.course import add_data
    d, c = episodes(tmp_path, monkeypatch), course_walk(lr)
    add_data(lr, c.id, str(d), MINE[0]['note'])
    cl = mk()
    t = cl.get('/w/gw').text
    assert 'data-part="data"' in t and '~/ramayana' in t and MINE[0]['note'] in t
    r = cl.post('/w/gw/data/drop', data=dict(path='~/ramayana'))
    assert '~/ramayana' not in r.text and lr.course(c.id).data == [] and lr.journey('gw').data == []
    lr.put_journey(dict(id='solo', title='Solo', mode='walk', steps=[dict(slug='lora', status='todo', check=dict(way='words', kind='short', depth=2))], data=MINE))
    cl.post('/w/solo/data/drop', data=dict(path='~/ramayana'))
    assert lr.journey('solo').data == [] and 'data-part="data"' not in cl.get('/w/solo').text

def test_a_spec_written_before_a_folder_gets_it(mk, lr, tmp_path, monkeypatch):
    "A notebook spec that the tutor wrote before you added a folder gets the folder when the check shows, so Leela reads it."
    from abhyasa.course import add_data
    d, c = episodes(tmp_path, monkeypatch), course_walk(lr)
    lr.walk_step('gw', 1, nb={**_GOOD, 'data': []})
    add_data(lr, c.id, str(d), MINE[0]['note'])
    assert mk().get('/w/gw/1/check').status_code == 200
    assert [e['path'] for e in lr.journey('gw').steps[1]['nb']['data']] == ['~/ramayana']

def test_start_box_keeps_a_folder_as_your_data(mk, lr, walk_fake, tmp_path, monkeypatch):
    "In the Start box a folder chip has My data. A ticked folder is not filed: the walk and its course keep it as your data."
    d = episodes(tmp_path, monkeypatch); cl = mk()
    q = 'Make my own comic from the episodes'
    h = cl.get('/learn/read', params=dict(q=q, extra=[str(d)])).text
    fid = re.search(r'name="mine" value="([^"]+)"', h)[1]
    assert 'My data' in h and 'checked' not in re.search(r'<input[^>]*name="mine"[^>]*>', h)[0]
    assert re.search(r'<input[^>]*name="mine"[^>]*checked', cl.get('/learn/read', params=dict(q=q, extra=[str(d)], mine=[fid])).text)
    walk_fake.rules['You plan a learning path'] = dict(title='Comic', subject='ml', steps=[dict(name='Captions', statement='Captions name a panel.', slug='', why='The goal.', needs=[])])
    r = cl.post('/walk/new', data=dict(q=q, chips='1', sources=[fid], mine=[fid]))
    jid = wait_for_walk(cl, r).split('/')[-1]
    j = lr.journey(jid)
    assert j.data == [dict(path='~/ramayana', note='')] and fid not in (j.get('chips') or ()) and not lr.vault.shelf('notebooks').sources()
    assert lr.course(j.course).data == j.data
