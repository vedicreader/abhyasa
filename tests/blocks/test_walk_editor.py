"The plan of a walk: each change by hand saves at once with an Undo; moves keep progress, side walks and research; the box makes the other changes."
from walk_data import *
import threading
from fastcore.utils import first
from abhyasa.path import hands_count

def paper_walk(cl, lr): return walk(cl, lr)
def slugs(lr, jid): return [s['slug'] for s in lr.journey(jid).steps]
def post(cl, jid, **kw): return cl.post(f'/w/{jid}/edit', data=kw)

def answer_step(cl, jid, i):
    "Open the check of step `i` and answer it, so the step is done."
    cl.get(f'/w/{jid}/{i}/check'); cl.post(f'/w/{jid}/{i}/answer', data=dict(answer='the rank', confidence=70))

def open_side_walk(cl, lr, jid, i):
    "Open a quick side walk from step `i`; return its id."
    lr.put('Derivatives and gradients', 'The slope of a function at a point, one for each input.', 'ml', slug='gradients')
    return cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/{i}', how='primer')).json()['url'].split('/')[2]

def test_reorder_keeps_progress_side_walks_and_research(mk, lr, walk_fake):
    cl = mk(); jid = paper_walk(cl, lr); cl.post(f'/w/{jid}/start'); answer_step(cl, jid, 0)
    side = open_side_walk(cl, lr, jid, 1); ss = slugs(lr, jid)
    r = post(cl, jid, slug=ss[1], act='move', to=0)
    j = lr.journey(jid)
    assert [s['slug'] for s in j.steps][:2] == [ss[1], ss[0]] and j.steps[1].get('done')
    assert lr.journey(side).parent['step'] == 0 and 'Moved “' in r.text and 'to idea 1.' in r.text
    from abhyasa.path import put_step
    assert put_step(lr, jid, ss[2], 2, read=dict(text='x', src='web')) in (None, 2)   # finds the step by slug

def test_undo_gives_back_the_exact_old_steps(mk, lr, walk_fake):
    "Undo of a move gives back the exact old steps and the side walk place; the history is empty again."
    cl = mk(); jid = paper_walk(cl, lr); cl.post(f'/w/{jid}/start'); side = open_side_walk(cl, lr, jid, 2)
    old = lr.journey(jid).steps
    post(cl, jid, slug=old[2]['slug'], act='move', to=0)
    r = cl.post(f'/w/{jid}/undo')
    assert lr.journey(jid).steps == old and not lr.edits('walk', jid) and 'Undone: Moved' in r.text
    assert lr.journey(side).parent['step'] == 2

def test_notebook_kind_queues_the_spec(mk, lr, walk_fake, monkeypatch):
    "A check that the box makes a notebook gets its notebook spec job, and the plan counts it as hands-on."
    from flows import change
    queued = []; monkeypatch.setattr('abhyasa.path.nb_spec', lambda lr, ask, j, i, stop=None: queued.append(i))
    cl = mk(); jid = paper_walk(cl, lr); s = slugs(lr, jid)[0]
    walk_fake.rules['You propose changes to one learning walk'] = dict(changes=[dict(op='kind', idea=s, kind='notebook', why='x')])
    r = change(cl, jid, 'make idea 1 a notebook')
    assert lr.journey(jid).steps[0]['check']['kind'] == 'notebook' and '2 of 3 ideas have a hands-on check' in r.text   # a notebook that you pick is hands-on
    assert wait_for(lambda: True if 0 in queued else None)

def test_hands_count_three_numbers():
    "Hands-on checks, the ideas that count, and the notebooks that build the goal. A notebook that you pick is hands-on."
    assert hands_count([dict(check=dict(kind='demo')), dict(check=dict(kind='notebook'), hands='notebook'), dict(check=dict(kind='short'), status='skip')]) == (1, 2, 1)
    assert hands_count([dict(check=dict(kind='notebook', why='you chose it'))]) == (1, 1, 0)

def test_remove_keeps_attempts(mk, lr, walk_fake):
    cl = mk(); jid = paper_walk(cl, lr); cl.post(f'/w/{jid}/start'); answer_step(cl, jid, 0)
    s = slugs(lr, jid)[0]; n = len(lr.attempts(s))
    r = post(cl, jid, slug=s, act='remove')
    assert s not in slugs(lr, jid) and len(lr.attempts(s)) == n and n and 'hx-confirm' not in r.text and 'Removed “' in r.text

def test_skip_and_bring_back(mk, lr, walk_fake):
    cl = mk(); jid = paper_walk(cl, lr); s = slugs(lr, jid)[1]
    r = post(cl, jid, slug=s, act='skip')
    assert lr.journey(jid).steps[1]['status'] == 'skip' and 'skipped · you can bring it back' in r.text and 'Bring back' in r.text
    post(cl, jid, slug=s, act='back')
    assert lr.journey(jid).steps[1]['status'] == 'todo'

def test_safe_digits_and_only_the_changes_by_hand(mk, lr, walk_fake):
    "A move needs a place in the list, an unknown idea is 404, and the edit route takes only move, skip, back, remove, lock and unlock: the box makes the others."
    cl = mk(); jid = paper_walk(cl, lr); s = slugs(lr, jid)[0]
    for act in ('note', 'rewrite', 'split', 'merge', 'add', 'pick', 'check', 'set'): assert post(cl, jid, slug=s, act=act).status_code == 400
    assert post(cl, jid, slug=s, act='move', to='²').status_code == 400 and post(cl, jid, slug=s, act='move', to='9').status_code == 400
    assert post(cl, jid, slug='nope', act='skip').status_code == 404 and post(cl, jid, slug=s, act='zap').status_code == 400

def test_history_and_restore(mk, lr, walk_fake):
    cl = mk(); jid = paper_walk(cl, lr); ss = slugs(lr, jid)
    post(cl, jid, slug=ss[0], act='remove')
    assert 'Removed “' in cl.get(f'/w/{jid}/history', headers={'HX-Request': 'true'}).text   # the fold Earlier versions loads it
    assert cl.get(f'/w/{jid}/history', follow_redirects=False).headers['location'] == f'/w/{jid}#history'
    assert cl.get(f'/w/{jid}/edit', follow_redirects=False).headers['location'] == f'/w/{jid}#plan'   # the old page: the plan is on the walk page
    r = cl.post(f'/w/{jid}/restore', data=dict(k='0'))
    assert r.headers['hx-redirect'] == f'/w/{jid}#plan' and slugs(lr, jid) == ss and len(lr.edits('walk', jid)) == 2
    assert cl.post(f'/w/{jid}/restore', data=dict(k='²')).status_code == 404

def test_talk_line_links_the_talk(mk, lr, walk_fake):
    from abhyasa.show import talk_from_walk
    from talk_data import TALK_RULES
    from abhyasa.models import Fake
    cl = mk(); jid = paper_walk(cl, lr); t = talk_from_walk(lr, Fake(TALK_RULES), jid)
    page = cl.get(f'/w/{jid}').text
    assert '1 talk was made from this walk' in page and f'href="/t/{t.id}"' in page

def test_old_path_page_of_a_walk_opens_the_walk_page(mk, lr, walk_fake):
    cl = mk(); jid = paper_walk(cl, lr)
    r = cl.get(f'/path/{jid}', follow_redirects=False)
    assert r.status_code == 301 and r.headers['location'] == f'/w/{jid}'

def test_research_none_line_offers_look_again(mk, lr, walk_fake):
    "With no source found, the step offers Look again; the passage picker of the old editor is gone."
    cl = mk(); jid = paper_walk(cl, lr)
    lr.walk_step(jid, 0, read=dict(text=''), research='none')
    t = cl.get(f'/w/{jid}/0/source').text
    assert 'Look again' in t and 'Pick a passage yourself' not in t

def test_a_move_during_the_notebook_job_keeps_the_spec_on_its_idea(mk, lr, walk_fake):
    "The notebook job finds its step by the concept: a move while the model writes the spec puts the spec on the same idea."
    from abhyasa.contract import NB_SPEC_CASES
    go, asked = threading.Event(), threading.Event()
    def model(p, sp):
        if 'Sequential computation' in p: asked.set(); go.wait(5)   # hold only the job of the idea that moves
        return NB_SPEC_CASES[0][0]
    walk_fake.rules['Write one exercise and one real run'] = model
    cl = mk(); jid = paper_walk(cl, lr); ss = slugs(lr, jid)
    lr.walk_step(jid, 0, check=dict(way='code', kind='notebook', depth=4, why='you chose it'))
    cl.post(f'/w/{jid}/0/check')   # Write the notebook
    assert asked.wait(5)
    post(cl, jid, slug=ss[0], act='move', to=2); go.set()
    assert wait_for(lambda: True if lr.journey(jid).steps[2].get('nb') else None)
    j = lr.journey(jid)
    assert j.steps[2]['slug'] == ss[0] and not first(s for s in j.steps if s['slug'] == ss[2]).get('nb')   # the third idea has no notebook

def test_an_attempt_keeps_the_concept_of_its_step(mk, lr, walk_fake):
    "Each attempt of a step keeps `idea`, the slug of the step, next to its place, so a move does not lose which step it was."
    cl = mk(); jid = paper_walk(cl, lr); cl.post(f'/w/{jid}/start'); answer_step(cl, jid, 0)
    s = slugs(lr, jid)[0]; a = lr.attempts(s, limit=1)[0]
    assert (a['walk'], a['step'], a['idea']) == (jid, 0, s)

def test_a_side_walk_comes_back_to_its_step_after_remove_or_merge_and_undo(mk, lr, walk_fake):
    "The side walk is tied to the concept of its step: remove, then Undo, puts it back on the same idea; a merge by the box maps it to the idea it joined."
    from flows import change
    cl = mk(); jid = paper_walk(cl, lr); cl.post(f'/w/{jid}/start'); side = open_side_walk(cl, lr, jid, 1); ss = slugs(lr, jid)
    post(cl, jid, slug=ss[1], act='remove')
    assert lr.journey(side).parent['step'] is None and lr.journey(side).parent['idea'] == ss[1]
    cl.post(f'/w/{jid}/undo')
    assert lr.journey(side).parent['step'] == 1 and slugs(lr, jid) == ss
    walk_fake.rules['You propose changes to one learning walk'] = dict(changes=[dict(op='merge', idea=ss[0], why='x')])
    change(cl, jid, 'merge idea 1 with idea 2')
    assert lr.journey(side).parent['step'] == 0
    cl.post(f'/w/{jid}/undo')
    assert lr.journey(side).parent['step'] == 1

def test_back_from_a_side_walk_finds_its_step_by_concept(mk, lr, walk_fake):
    "Back from a side walk keeps its result on the step that opened it, also when that step moved."
    cl = mk(); jid = paper_walk(cl, lr); cl.post(f'/w/{jid}/start'); side = open_side_walk(cl, lr, jid, 1); ss = slugs(lr, jid)
    lr.put_journey({**lr.journey(jid), 'steps': [lr.journey(jid).steps[k] for k in (1, 0, 2)]})   # moved by another writer: the side walk still says step 1
    cl.post(f'/rh/back/{side}')
    j = lr.journey(jid)
    assert j.steps[0]['slug'] == ss[1] and j.steps[0].get('detours') and not j.steps[1].get('detours')

def test_the_plan_marks_each_idea_as_the_outline_does(mk, lr):
    "The plan on the walk page has the same dot for each idea as the outline: done, shaky and to do."
    import re
    ck = dict(way='words', kind='short', depth=2)
    lr.put('Softmax', 'Softmax makes weights that add to 1.', 'ml')
    lr.put_journey(dict(id='wd', title='Dots walk', mode='walk', started=1., steps=[dict(slug='ranking', status='todo', check=ck, done=dict(outcome='solid', at=1.)),
                        dict(slug='reciprocal-rank-fusion', status='todo', check=ck, done=dict(outcome='fragile', at=2.)), dict(slug='softmax', status='todo', check=ck)]))
    cl = mk()
    plan = cl.get('/w/wd').text
    rail = cl.get('/w/wd/2').text
    assert re.findall(r'class="plan-dot (\w+)"', plan) == ['done', 'shaky', 'now'] == re.findall(r'<li id="rail-\d" class="c (\w+)', rail)
