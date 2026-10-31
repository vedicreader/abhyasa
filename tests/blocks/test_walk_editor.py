"The walk path editor: each change saves at once with an Undo; moves keep progress, side walks and research; the hands-on share only warns; passages are real."
from walk_data import *
import threading
from fastcore.utils import first
from abhyasa.edit import hands_count

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
    from abhyasa.research import put_step
    assert put_step(lr, jid, ss[2], 2, read=dict(text='x', src='web')) in (None, 2)   # finds the step by slug

def test_undo_gives_back_the_exact_old_steps(mk, lr, walk_fake):
    "Undo of a move gives back the exact old steps and the side walk place; the history is empty again."
    cl = mk(); jid = paper_walk(cl, lr); cl.post(f'/w/{jid}/start'); side = open_side_walk(cl, lr, jid, 2)
    old = lr.journey(jid).steps
    post(cl, jid, slug=old[2]['slug'], act='move', to=0)
    r = cl.post(f'/w/{jid}/undo')
    assert lr.journey(jid).steps == old and not lr.edits('walk', jid) and 'Undone: Moved' in r.text
    assert lr.journey(side).parent['step'] == 2

def test_a_note_edit_can_be_undone(mk, lr, walk_fake):
    "A live note answers with the bar only; two saves join; Undo gives back the old note (the note is not a run field)."
    cl = mk(); jid = paper_walk(cl, lr); s = slugs(lr, jid)[1]
    assert wait_for(lambda: True if {'nb', 'nb_why'} & set(lr.journey(jid).steps[1]) else None)   # the notebook spec job of the walk ends first
    lr.walk_step(jid, 1, note='The old note.'); old = lr.journey(jid).steps
    r = cl.post(f'/w/{jid}/edit?slug={s}', data=dict(act='set', note='My note.'))
    assert r.status_code == 200 and 'id="steps"' not in r.text and 'Changed the note of idea 2.' in r.text
    cl.post(f'/w/{jid}/edit?slug={s}', data=dict(act='set', note='My better note.'))
    assert lr.journey(jid).steps[1]['note'] == 'My better note.' and len(lr.edits('walk', jid)) == 1
    assert cl.post(f'/w/{jid}/edit?slug={s}', data=dict(act='set', note='My better note.')).status_code == 204
    cl.post(f'/w/{jid}/undo')
    assert lr.journey(jid).steps == old

def test_hands_share_only_warns(mk, lr, walk_fake):
    cl = mk(); jid = paper_walk(cl, lr)
    for s in lr.journey(jid).steps: r = post(cl, jid, slug=s['slug'], act='check', way='predict')
    assert all(s['check']['kind'] != 'short' for s in lr.journey(jid).steps)
    assert '3 of 3 ideas have a hands-on check. You set about 33%.' in r.text and 'Change the setting' in r.text

def test_notebook_kind_queues_the_spec(mk, lr, walk_fake, monkeypatch):
    queued = []; monkeypatch.setattr('abhyasa.walk.nb_spec', lambda lr, ask, j, i: queued.append(i))
    cl = mk(); jid = paper_walk(cl, lr); s = slugs(lr, jid)[0]
    r = post(cl, jid, slug=s, act='check', way='notebook')
    assert lr.journey(jid).steps[0]['check']['kind'] == 'notebook' and '2 of 3 ideas have a hands-on check' in r.text   # a notebook that you pick is hands-on
    assert wait_for(lambda: True if 0 in queued else None)

def test_hands_count_three_numbers():
    "Hands-on checks, the ideas that count, and the notebooks that build the goal. A notebook that you pick is hands-on."
    assert hands_count([dict(check=dict(kind='demo')), dict(check=dict(kind='notebook'), hands='notebook'), dict(check=dict(kind='short'), status='skip')]) == (1, 2, 1)
    assert hands_count([dict(check=dict(kind='notebook', why='you chose it'))]) == (1, 1, 0)

def test_tool_walk_has_no_code_check(mk, lr, walk_fake):
    cl = mk(); jid = paper_walk(cl, lr); lr.merge_journey(jid, tool=True)
    t = cl.get(f'/w/{jid}').text
    assert 'Write code' not in t and 'Notebook' in t and 'Predict a demo' in t
    assert post(cl, jid, slug=slugs(lr, jid)[0], act='check', way='code').status_code == 400

def test_rewrite_changes_note_and_question_not_passage(mk, lr, walk_fake):
    walk_fake.rules['Rewrite these fields'] = dict(note='A short note.', q='What does softmax give?', passage='NOT THIS')
    cl = mk(); jid = paper_walk(cl, lr); s = slugs(lr, jid)[1]
    post(cl, jid, slug=s, act='check', way='short'); post(cl, jid, slug=s, act='q', text='Why softmax?'); lr.walk_step(jid, 1, note='A long old note.')
    before = lr.journey(jid).steps[1]['read']
    r = post(cl, jid, slug=s, act='rewrite', chip='Simpler')
    st = lr.journey(jid).steps[1]
    assert st['note'] == 'A short note.' and st['check']['q'] == 'What does softmax give?' and st['read'] == before
    assert lr.edits('walk', jid)[0].who == 'tutor' and 'Rewrote the note and the check question of idea 2: Simpler.' in r.text
    assert 'NOT THIS' not in str(lr.journey(jid).steps)

def test_a_rewrite_keeps_your_edit(mk, lr, walk_fake):
    "A field that you change during the model call keeps your edit; the model call runs outside the lock."
    cl = mk(); jid = paper_walk(cl, lr); s = slugs(lr, jid)[1]
    post(cl, jid, slug=s, act='check', way='short'); post(cl, jid, slug=s, act='q', text='Why softmax?'); lr.walk_step(jid, 1, note='Old note.')
    from abhyasa.edit import edit_lock
    def model(p, sp):
        got = []
        t = threading.Thread(target=lambda: got.append(edit_lock('walk', jid).acquire(timeout=2) and edit_lock('walk', jid).release() is None)); t.start(); t.join()
        assert got == [True]   # another thread takes the lock during the model call
        lr.walk_step(jid, 1, note='My edit.')
        return dict(note='Tutor note.', q='Tutor question?')
    walk_fake.rules['Rewrite these fields'] = model
    r = post(cl, jid, slug=s, act='rewrite', text='shorter')
    st = lr.journey(jid).steps[1]
    assert st['note'] == 'My edit.' and st['check']['q'] == 'Tutor question?' and 'Your edit of the note was kept.' in r.text

def test_a_failed_rewrite_changes_nothing(mk, lr, walk_fake):
    def boom(p, sp): raise RuntimeError('model down')
    walk_fake.rules['Rewrite these fields'] = boom
    cl = mk(); jid = paper_walk(cl, lr); s = slugs(lr, jid)[1]; lr.walk_step(jid, 1, note='Old note.'); old = lr.journey(jid).steps
    r = post(cl, jid, slug=s, act='rewrite', text='simpler')
    assert r.status_code == 400 and r.text == 'The tutor could not rewrite this. Nothing changed.' and lr.journey(jid).steps == old

def test_pick_refuses_text_that_is_not_in_the_source(mk, lr, walk_fake):
    cl = mk(); jid = paper_walk(cl, lr); s = slugs(lr, jid)[0]; before = lr.journey(jid).steps[0]['read']['text']
    r = post(cl, jid, slug=s, act='pick', text='Words the tutor made up.')
    assert r.status_code == 400 and lr.journey(jid).steps[0]['read']['text'] == before

def test_pick_a_real_passage(mk, lr, walk_fake):
    "The picker lists real paragraphs of the paper; a picked one is saved word for word, with its page."
    cl = mk(); jid = paper_walk(cl, lr); s = slugs(lr, jid)[2]
    t = cl.get(f'/w/{jid}/passages?i=2&q=gradients').text
    assert 'extremely small gradients' in t and 'Use this passage' in t and 'Recurrent models' not in t
    q = 'We suspect that for large values of dk, the dot products grow large in magnitude'
    r = post(cl, jid, slug=s, act='pick', text=q)
    rd = lr.journey(jid).steps[2]['read']
    assert r.status_code == 200 and rd['text'] == q and rd['page'] and 'Changed the passage of idea 3.' in r.text

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

def test_merge_keeps_both_passages(mk, lr, walk_fake):
    cl = mk(); jid = paper_walk(cl, lr); ss = lr.journey(jid).steps
    r = post(cl, jid, slug=ss[1]['slug'], act='merge')
    j = lr.journey(jid)
    assert [s['slug'] for s in j.steps] == [ss[0]['slug'], ss[1]['slug']] and j.steps[1]['read']['also'][0]['text'] == ss[2]['read']['text']
    assert 'Merged “' in r.text and post(cl, jid, slug=ss[1]['slug'], act='merge').status_code == 400   # the last idea

def test_add_by_name_tree_and_source(mk, lr, walk_fake):
    "Add an idea by name (after the idea that had the focus), from the concept tree, and with a real passage."
    walk_fake.rules['The idea: '] = dict(name='Layer normalization', statement='It scales the values of a layer.')
    cl = mk(); jid = paper_walk(cl, lr); ss = slugs(lr, jid)
    r = post(cl, jid, act='add', name='Layer normalization', after=ss[0])
    assert slugs(lr, jid)[1] == 'layer-normalization' and 'Added “Layer normalization”.' in r.text and 'data-fresh="1"' in r.text
    assert lr.journey(jid).steps[1]['check']['kind']
    post(cl, jid, act='add', concept='ranking')
    assert slugs(lr, jid)[-1] == 'ranking'
    t = cl.get(f'/w/{jid}/passages', params=dict(name='Parallel training', q='parallelization')).text
    assert 'Add with this passage' in t
    q = 'This inherently sequential nature precludes parallelization within training examples.'
    walk_fake.rules['The idea: '] = dict(name='Parallel training', statement='Train the positions at the same time.')
    post(cl, jid, act='add', name='Parallel training', text=q)
    assert lr.journey(jid).steps[-1]['read']['text'] == q
    assert post(cl, jid, act='add', concept='ranking').status_code == 400   # in the walk already

def test_split_adds_parts_before(mk, lr, walk_fake):
    cl = mk(); jid = paper_walk(cl, lr); ss = slugs(lr, jid)
    walk_fake.rules['Return JSON: {"concepts"'] = dict(concepts=[dict(name='Dot product', statement='Multiply and add.', aliases=[], prereqs=[])])
    r = post(cl, jid, slug=ss[2], act='split')
    assert slugs(lr, jid) == [ss[0], ss[1], 'dot-product', ss[2]] and 'Split “' in r.text
    cl.post(f'/w/{jid}/undo')
    assert slugs(lr, jid) == ss

def test_edited_check_question_is_asked(mk, lr, walk_fake):
    cl = mk(); jid = paper_walk(cl, lr); s = slugs(lr, jid)[0]
    post(cl, jid, slug=s, act='check', way='short')
    post(cl, jid, slug=s, act='q', text='Set dk where the softmax goes flat.')
    cl.post(f'/w/{jid}/start')
    assert 'Set dk where the softmax goes flat.' in cl.get(f'/w/{jid}/0/check').text

def test_no_control_marks_and_safe_digits(mk, lr, walk_fake):
    cl = mk(); jid = paper_walk(cl, lr); s = slugs(lr, jid)[0]
    post(cl, jid, slug=s, act='note', text='A‮ note\x07.')
    assert lr.journey(jid).steps[0]['note'] == 'A note.'
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
    from abhyasa.talk import talk_from_walk
    from talk_data import TALK_RULES
    from abhyasa.llm import Fake
    cl = mk(); jid = paper_walk(cl, lr); t = talk_from_walk(lr, Fake(TALK_RULES), jid)
    page = cl.get(f'/w/{jid}').text
    assert '1 talk was made from this walk' in page and f'href="/t/{t.id}"' in page

def test_old_path_page_of_a_walk_opens_the_walk_page(mk, lr, walk_fake):
    cl = mk(); jid = paper_walk(cl, lr)
    r = cl.get(f'/path/{jid}', follow_redirects=False)
    assert r.status_code == 301 and r.headers['location'] == f'/w/{jid}'

def test_research_none_line_offers_a_pick(mk, lr, walk_fake):
    cl = mk(); jid = paper_walk(cl, lr); s = slugs(lr, jid)[0]
    lr.walk_step(jid, 0, read=dict(text=''), research='none')
    assert 'Pick a passage yourself' in cl.get(f'/w/{jid}/0/source').text

def test_a_move_during_the_notebook_job_keeps_the_spec_on_its_idea(mk, lr, walk_fake):
    "The notebook job finds its step by the concept: a move while the model writes the spec puts the spec on the same idea."
    from abhyasa.contract import NB_SPEC_CASES
    go, asked = threading.Event(), threading.Event()
    def model(p, sp):
        if 'Sequential computation' in p: asked.set(); go.wait(5)   # hold only the job of the idea that moves
        return NB_SPEC_CASES[0][0]
    walk_fake.rules['Write one exercise and one real run'] = model
    cl = mk(); jid = paper_walk(cl, lr); ss = slugs(lr, jid)
    post(cl, jid, slug=ss[0], act='check', way='notebook')
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

def test_a_note_that_the_rewrite_writes_first_has_its_own_undo(mk, lr, walk_fake):
    "With no note, the rewrite first writes the note, as its own change by the tutor; two Undos give back the step with no note."
    walk_fake.rules['Rewrite these fields'] = dict(note='A short note.')
    cl = mk(); jid = paper_walk(cl, lr); s = slugs(lr, jid)[1]
    assert wait_for(lambda: lr.journey(jid).steps[1].get('nb_why') or None)   # the notebook job of idea 2 ends first
    old = lr.journey(jid).steps
    post(cl, jid, slug=s, act='rewrite', text='simpler')
    es = lr.edits('walk', jid)
    assert [e.what for e in es] == ['Rewrote the note of idea 2: simpler.', 'The tutor wrote the note of idea 2.'] and es[1].who == 'tutor'
    cl.post(f'/w/{jid}/undo'); cl.post(f'/w/{jid}/undo')
    assert lr.journey(jid).steps == old

def test_your_question_only_on_a_short_check(mk, lr, walk_fake):
    cl = mk(); jid = paper_walk(cl, lr); s = slugs(lr, jid)[2]
    post(cl, jid, slug=s, act='check', way='predict')
    r = post(cl, jid, slug=s, act='q', text='Why divide?')
    assert r.status_code == 400 and 'short-answer' in r.text and 'q' not in lr.journey(jid).steps[2]['check']

def test_a_side_walk_comes_back_to_its_step_after_remove_or_merge_and_undo(mk, lr, walk_fake):
    "The side walk is tied to the concept of its step: remove, then Undo, puts it back on the same idea; a merge maps it to the idea it joined."
    cl = mk(); jid = paper_walk(cl, lr); cl.post(f'/w/{jid}/start'); side = open_side_walk(cl, lr, jid, 1); ss = slugs(lr, jid)
    post(cl, jid, slug=ss[1], act='remove')
    assert lr.journey(side).parent['step'] is None and lr.journey(side).parent['idea'] == ss[1]
    cl.post(f'/w/{jid}/undo')
    assert lr.journey(side).parent['step'] == 1 and slugs(lr, jid) == ss
    post(cl, jid, slug=ss[0], act='merge')
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

def test_a_long_name_is_refused_and_marks_go(mk, lr, walk_fake):
    cl = mk(); jid = paper_walk(cl, lr)
    assert post(cl, jid, act='add', name='x' * 121).status_code == 400
    walk_fake.rules['The idea: '] = dict(name='Layer norm', statement='It scales a layer.')
    post(cl, jid, act='add', name='Layer‮ norm')
    p = [c for c in walk_fake.calls if 'The idea: ' in c[0]][-1][0]
    assert '<source title="idea">Layer norm</source>' in p
