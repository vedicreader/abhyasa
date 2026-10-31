"The line of research on the walk: what it does now, the sources, the time left and the last step; how it ended; the notice on any page; the state for the Mac app."
import time
import pytest
import abhyasa.research as R
from abhyasa.journey import walk_from_topic
from abhyasa.llm import Fake

HX = {'HX-Request': 'true'}
PLAN = dict(title='Softmax and attention', subject='ml', steps=[dict(name='Softmax', statement='Softmax turns scores into weights.', slug='', why='Weights.', needs=[], ways=['words']),
                                                                dict(name='Attention', statement='Attention mixes values by weights.', slug='', why='The goal.', needs=['Softmax'], ways=['words']),
                                                                dict(name='Keys', statement='A key is matched with a query.', slug='', why='The goal.', needs=[], ways=['words'])])

@pytest.fixture(autouse=True)
def no_resume(monkeypatch):
    "The app does not look again for the pending idea of these fake walks at its start: each test sets the state itself."
    monkeypatch.setattr(R.Researcher, 'resume', lambda self: None)

def walk(lr, **kv):
    "A walk of three ideas that research looks at: the first has a source, the second has none, the third waits."
    j = walk_from_topic(lr, Fake({'You plan a learning path': PLAN}), 'learn softmax and attention')
    now = time.time()
    lr.walk_step(j.id, 0, research='found', research_at=now - 40, read=dict(text='Softmax turns scores into weights.', researched=True, src='web', url='https://example.org/s'))
    lr.walk_step(j.id, 1, research='none', research_at=now - 20)
    lr.walk_step(j.id, 2, research='pending', research_at=now - 60)
    return lr.merge_journey(j.id, research_start=now - 60, research_beat=now - 12, gather_now=dict(title='attention.md', idea='keys'), **kv)

def running(cl, monkeypatch, on=True):
    "Make the research of each walk look as if it runs now."
    rs = cl.app.state.svc['research']
    monkeypatch.setattr(rs, 'running', lambda jid, but=0: on)
    return rs

def test_the_line_while_research_runs(mk, lr, monkeypatch):
    "While research runs, the walk page and each step show what it reads, the sources, the time left and the last step, with Stop; the outline links the sources of the walk page."
    j = walk(lr); cl = mk(); running(cl, monkeypatch)
    b = cl.get(f'/w/{j.id}/gather', headers=HX).text
    assert 'Reads attention.md for idea 3. 1 of 3 ideas have a source. Less than a minute left. Last step 12 s ago.' in b
    assert 'Search words go to the web.' in b   # where the words go
    assert '>Stop<' in b and 'every 3s' in b and 'See the build' not in b
    cl.post(f'/w/{j.id}/start')
    step = cl.get(f'/w/{j.id}/1').text
    assert '1 of 3 ideas have a source.' in step and f'href="/w/{j.id}#sources" class="see-build">Sources<' in step   # the line, and the link in the outline
    assert 'has a source' in step   # the idea with a source is marked in the outline
    assert cl.get(f'/w/{j.id}?plan=1', follow_redirects=False).headers['location'] == f'/w/{j.id}#sources'   # the old build view: the sources of the walk page
    page = cl.get(f'/w/{j.id}').text   # the walk page after the start: no jump to the step
    assert 'You can start now.' in page and '1 of 3 ideas have a source.' in page and 'Continue: idea 1 of 3' in page and f'href="/w/{j.id}/0"' in page

def test_the_heartbeat_moves(mk, lr, monkeypatch):
    "The time since the last step grows while nothing happens, and goes back down after a step."
    j = walk(lr); cl = mk(); running(cl, monkeypatch)
    assert 'Last step 12 s ago.' in cl.get(f'/w/{j.id}/gather', headers=HX).text
    old = time.time() - 300
    for k in range(3): lr.walk_step(j.id, k, research_at=old)
    lr.merge_journey(j.id, research_beat=old)
    assert 'Last step 5 min ago.' in cl.get(f'/w/{j.id}/gather', headers=HX).text
    lr.merge_journey(j.id, research_beat=time.time() - 2)
    assert 'Last step 2 s ago.' in cl.get(f'/w/{j.id}/gather', headers=HX).text

def test_the_line_after_research_ends(mk, lr, monkeypatch):
    "After research ends, the line says how and when, with Find sources again for the ideas with no source."
    end = time.time() - 5
    hm = time.strftime('%H:%M', time.localtime(end))
    cl = mk(); running(cl, monkeypatch, False)
    for kv, said in ((dict(research_end=end), f'Research ended at {hm}.'), (dict(research_end=end, research_stopped='you'), f'You stopped research at {hm}.'),
                     (dict(research_end=end, research_stopped='time'), f'The time for research ended at {hm}.'), ({}, 'Research stopped because abhyasa closed.')):
        j = walk(lr, **kv)
        b = cl.get(f'/w/{j.id}/gather', headers=HX).text
        assert f'1 of 3 ideas have a source. {said}' in b and 'Find sources again' in b and 'every 3s' not in b, (said, b)

def test_find_sources_again(mk, lr, monkeypatch):
    "Find sources again looks for each idea with no source."
    j = walk(lr, research_end=time.time()); cl = mk(); rs = running(cl, monkeypatch, False)
    asked = []
    monkeypatch.setattr(rs, 'look_for', lambda jid, ix=None: asked.append(ix))
    cl.post(f'/w/{j.id}/gather/again', headers=HX)
    assert asked == [[1, 2]]

def test_notice_on_any_page_and_the_mac_state(mk, lr, monkeypatch):
    "When research ends, each page has a notice with a link to the walk, until the learner opens it. The Mac app reads the state as JSON."
    j = walk(lr, research_end=time.time() - 5, research_seen=False); cl = mk(); rs = running(cl, monkeypatch, False)
    rs.jobs[j.id] = []   # the walk had research in this run of abhyasa
    page = cl.get('/learn').text
    assert 'Sources for your walk' in page and 'Softmax and attention' in page and f'href="/w/{j.id}#sources"' in page
    st = cl.get('/walk/research.json').json()
    assert st['running'] == [] and st['ended'][0]['id'] == j.id and st['ended'][0]['title'] == 'Softmax and attention' and (st['ended'][0]['have'], st['ended'][0]['total']) == (1, 3)
    cl.get(f'/w/{j.id}')   # the learner opens the walk
    assert 'Sources for your walk' not in cl.get('/learn').text
    monkeypatch.setattr(rs, 'running', lambda jid, but=0: True)
    assert cl.get('/walk/research.json').json()['running'][0]['id'] == j.id


def test_the_editor_shows_the_line_of_research(mk, lr, monkeypatch):
    "The walk page shows the line of research in its sources, with Find sources again, and each idea of its plan with no source says so."
    j = walk(lr, research_end=time.time() - 5); cl = mk(); running(cl, monkeypatch, False)
    page = cl.get(f'/w/{j.id}').text
    assert '1 of 3 ideas have a source. Research ended at' in page and 'Find sources again' in page
    assert page.index('id="steps"') < page.index('id="gather"') < page.index('id="walk-src-form"')   # the plan, then the sources with Add a source
    assert page.count('no source yet') == 2 and page.count('data-main=') == 1   # one main button

def test_sources_in_the_outline_before_research(mk, walk_fake, lr, monkeypatch):
    "A walk with ideas that have no source, and no research yet: the outline of an idea has Sources, and the line offers Find sources."
    j = walk_from_topic(lr, Fake({'You plan a learning path': PLAN}), 'learn softmax and attention'); cl = mk(); rs = running(cl, monkeypatch, False)
    assert not j.get('research_start') and not j.get('gather_at')
    rail = cl.get(f'/w/{j.id}/0').text.split('id="rail"')[1].split('</aside>')[0]
    assert f'href="/w/{j.id}#sources"' in rail and '>Sources<' in rail
    plan = cl.get(f'/w/{j.id}').text
    assert '0 of 3 ideas have a source. Research did not look for sources yet.' in plan and '>Find sources<' in plan.replace('</button>', '<')
    asked = []
    monkeypatch.setattr(rs, 'look_for', lambda jid, ix=None: asked.append(ix))
    monkeypatch.setattr(R, 'want_agent', lambda *a, **k: False)
    cl.post(f'/w/{j.id}/gather/again', headers=HX)
    assert asked == [[0, 1, 2]]   # Find sources starts the search of each idea
