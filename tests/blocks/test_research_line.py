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
    "While research runs, the plan and each step show what it reads, the sources, the time left and the last step, with Stop and the way back to the build."
    j = walk(lr); cl = mk(); running(cl, monkeypatch)
    b = cl.get(f'/w/{j.id}/gather', headers=HX).text
    assert 'Reads attention.md for idea 3. Sources for 1 of 3 ideas. Less than a minute left. Last step 12 s ago.' in b
    assert '>Stop<' in b and 'every 3s' in b and f'href="/w/{j.id}?plan=1#gather"' in b
    cl.post(f'/w/{j.id}/start')
    step = cl.get(f'/w/{j.id}/1').text
    assert 'Sources for 1 of 3 ideas.' in step and 'See the build' in step and f'href="/w/{j.id}?plan=1#gather" class="see-build">Sources<' in step   # the line, and the link in the outline
    assert 'has a source' in step   # the idea with a source is marked in the outline
    plan = cl.get(f'/w/{j.id}?plan=1').text   # the build stays in reach after the start
    assert 'You can start now.' in plan and 'Sources for 1 of 3 ideas.' in plan and 'looking for a source' in plan
    assert cl.get(f'/w/{j.id}', follow_redirects=False).status_code in (302, 303)   # Continue still goes to the step

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
        assert f'Sources for 1 of 3 ideas. {said}' in b and 'Find sources again' in b and 'every 3s' not in b, (said, b)

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
    assert 'Sources for your walk' in page and 'Softmax and attention' in page and f'href="/w/{j.id}?plan=1#gather"' in page
    st = cl.get('/walk/research.json').json()
    assert st['running'] == [] and st['ended'][0]['id'] == j.id and st['ended'][0]['title'] == 'Softmax and attention' and (st['ended'][0]['have'], st['ended'][0]['total']) == (1, 3)
    cl.get(f'/w/{j.id}?plan=1')   # the learner opens the walk
    assert 'Sources for your walk' not in cl.get('/learn').text
    monkeypatch.setattr(rs, 'running', lambda jid, but=0: True)
    assert cl.get('/walk/research.json').json()['running'][0]['id'] == j.id

