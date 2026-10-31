"Make it again: a talk made from a walk takes the later changes of the walk and keeps your edits to its slides."
from talk_data import *
from abhyasa.talk import talk_from_walk, talk_again, walk_changes, GONE, AGAIN
from fastcore.basics import AttrDict


def paper_walk_lr(lr): return talk_walk(lr)

def edit_slide(lr, tid, concept, **kw):
    "Change the fields `kw` of the slide of `concept`, as the editor does."
    t = lr.talk(tid)
    for s in t.slides:
        if s.get('concept') == concept: s.update(kw)
    return lr.put_talk(t)

def new_step(lr, name):
    "A new idea `name` on the shelf, as a walk step with no passage."
    c = lr.put(name, f'{name} is a new idea for the test.', 'ml')
    return dict(slug=c.slug, status='todo', why='')

def drop_and_add(lr, jid, slug, name='Layer norm'):
    j = lr.journey(jid); j.steps = [s for s in j.steps if s['slug'] != slug] + [new_step(lr, name)]; lr.put_journey(j)

def test_again_keeps_edits_moves_gone_and_adds_new(lr, talk_fake):
    "Your note stays, the new idea gets a slide, the idea that left goes to the section at the end, and the change is one row by the tutor."
    jid = paper_walk_lr(lr); t = talk_from_walk(lr, talk_fake, jid)
    a, b = t.slides[0]['concept'], t.slides[1]['concept']
    edit_slide(lr, t.id, a, notes='My words.')
    drop_and_add(lr, jid, b)
    assert walk_changes(lr, lr.talk(t.id)) == AttrDict(added=1, removed=1, moved=0, changed=0)
    n = talk_again(lr, talk_fake, t.id)
    by = {s['concept']: s for s in n.slides if s['kind'] == 'idea'}
    assert by[a]['notes'] == 'My words.' and 'layer-norm' in by and n.id == t.id
    gone = [s for s in n.slides if s.get('section') == GONE]
    assert [s['concept'] for s in gone] == [b] and lr.edits('talk', t.id)[0].who == 'tutor' and lr.edits('talk', t.id)[0].what == AGAIN
    assert n.slides[-1]['concept'] == b and [s['kind'] for s in n.slides[-3:-1]] == ['questions', 'recap']

def test_old_talk_shows_no_change_line(mk, lr, talk_fake):
    "A talk with no made_from (made before 0.0.14) shows no change line, even when the walk changed."
    cl = mk(); jid = prep_walk(lr, walk(cl, lr)); tid = make_talk(cl, jid)
    t = lr.talk(tid); lr.put_talk({**t, 'made_from': None, 'walk_at': None, 'marks': None})   # the store merges meta keys, so an old talk reads as None
    drop_and_add(lr, jid, t.slides[1]['concept'])
    assert 'The walk changed' not in cl.get(f'/t/{tid}').text

def test_change_line_and_button(mk, lr, talk_fake):
    "After the walk gets a new idea, the editor says so and offers Make it again; the walk editor marks the talk as older."
    cl = mk(); jid = prep_walk(lr, walk(cl, lr)); tid = make_talk(cl, jid)
    assert 'The walk changed' not in cl.get(f'/t/{tid}').text
    j = lr.journey(jid); j.steps = [*j.steps, new_step(lr, 'Layer norm')]; lr.put_journey(j)
    h = cl.get(f'/t/{tid}').text
    assert 'The walk changed after this talk was made: 1 idea added.' in h and 'Make it again' in h
    assert 'Your edits to slides stay in the new talk where the idea is the same.' in h and 'A change here does not change the walk.' in h
    j = lr.journey(jid); j.steps = j.steps[1:]; lr.put_journey(j)
    assert 'The walk changed after this talk was made: 1 idea added, 1 idea removed.' in cl.get(f'/t/{tid}').text
    assert '(older than this walk)' in cl.get(f'/w/{jid}').text

def test_again_through_the_app(mk, lr, talk_fake):
    "Make it again posts again=1: the job keeps the talk id, opens it with the Undo bar, and keeps your edit."
    cl = mk(); jid = prep_walk(lr, walk(cl, lr)); tid = make_talk(cl, jid); n = len(lr.talks())
    a = lr.talk(tid).slides[0]['concept']
    cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', notes='Mine.'))
    drop_and_add(lr, jid, lr.talk(tid).slides[1]['concept'])
    r = cl.post('/talk/new', data=dict(jid=jid, again='1'))
    assert f'/talk/job?jid={tid}' in r.text   # the newest talk of the walk, with no tid; its job has the talk id
    loc = wait_for(lambda: cl.get(f'/talk/job?jid={tid}').headers.get('hx-redirect'))
    assert loc == f'/t/{tid}?done=again' and len(lr.talks()) == n
    h = cl.get(loc).text
    assert AGAIN in h and GONE in h and "The walk changed" not in h and "3 ideas · 2 sections" in h
    assert next(s for s in lr.talk(tid).slides if s.get('concept') == a)['notes'] == 'Mine.'

def test_again_can_be_undone(mk, lr, talk_fake):
    "One Undo gives back the slides, and what the talk keeps of its walk, as they were before Make it again."
    cl = mk(); jid = prep_walk(lr, walk(cl, lr)); tid = make_talk(cl, jid)
    cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', notes='Mine.'))
    drop_and_add(lr, jid, lr.talk(tid).slides[1]['concept'])
    before = lr.talk(tid)
    talk_again(lr, talk_fake, tid)
    assert lr.talk(tid).slides != before.slides
    cl.post(f'/t/{tid}/undo')
    after = lr.talk(tid)
    assert after.slides == before.slides and after.made_from == before.made_from and after.marks == before.marks and after.walk_at == before.walk_at
    assert 'The walk changed after this talk was made: 1 idea added, 1 idea removed.' in cl.get(f'/t/{tid}').text

def test_restore_before_again(mk, lr, talk_fake):
    "Restore this version on the row of Make it again gives back the whole talk, and is a change that Undo takes back."
    cl = mk(); jid = prep_walk(lr, walk(cl, lr)); tid = make_talk(cl, jid)
    drop_and_add(lr, jid, lr.talk(tid).slides[1]['concept'])
    before = lr.talk(tid); talk_again(lr, talk_fake, tid); made = lr.talk(tid)
    r = cl.post(f'/t/{tid}/restore', data=dict(id=lr.edits('talk', tid)[0].id))
    assert r.headers.get('hx-redirect') == f'/t/{tid}' and lr.talk(tid).slides == before.slides and lr.talk(tid).made_from == before.made_from
    cl.post(f'/t/{tid}/undo')
    assert lr.talk(tid).slides == made.slides and lr.talk(tid).made_from == made.made_from

def test_model_call_outside_the_lock(lr, talk_fake):
    "The model writes the new slide while another thread can take the lock of the talk."
    import threading
    from abhyasa.edit import edit_lock
    jid = paper_walk_lr(lr); t = talk_from_walk(lr, talk_fake, jid)
    drop_and_add(lr, jid, t.slides[1]['concept'])
    free = []
    def slide(p, sp):
        th = threading.Thread(target=lambda: free.append(edit_lock('talk', t.id).acquire(timeout=1) and edit_lock('talk', t.id).release() is None))
        th.start(); th.join()
        return SLIDE
    talk_again(lr, Fake({**TALK_RULES, 'You write one slide of a talk': slide}), t.id)
    assert free and all(free)

def test_path_talk_keeps_its_behaviour(mk, lr, talk_fake):
    "A talk from a path does not show the new line, and Make it again on a path still makes a new talk."
    from walk_data import EXTRACT_REPLY
    cl = mk(); jid = prep_walk(lr, walk(cl, lr))
    pj = lr.put_journey(dict(id='softmax-path-ab12', title='Softmax path', goal='Learn softmax', subject='ml',
                             steps=[dict(slug=s, status='todo', why='') for s in ('softmax', 'sequential-computation')]))
    cl.post('/talk/journey', data=dict(jid=pj.id))
    tid = wait_for(lambda: cl.get(f'/talk/job?jid={pj.id}').headers.get('hx-redirect')).split('/')[-1]
    assert 'The walk changed after this talk was made:' not in cl.get(f'/t/{tid}').text
    cl.post('/talk/journey', data=dict(jid=pj.id, again='1'))
    tid2 = wait_for(lambda: (h := cl.get(f'/talk/job?jid={pj.id}').headers.get('hx-redirect')) and h.split('/')[-1] != tid and h or None).split('/')[-1]
    assert tid2 != tid

def again_with_a_parked_slide(cl, lr, talk_fake):
    "A talk made again after the walk dropped idea 2: its slide is parked. Return (talk id, walk id, the parked slide)."
    jid = prep_walk(lr, walk(cl, lr)); tid = make_talk(cl, jid)
    drop_and_add(lr, jid, lr.talk(tid).slides[1]['concept'])
    t = talk_again(lr, talk_fake, tid)
    return tid, jid, next(s for s in t.slides if s.get('section') == GONE)

def test_a_parked_slide_is_not_presented(mk, lr, talk_fake):
    "A parked slide takes no minutes and no slide count; the presenter, the room and the run never get it; its row offers Put back and Remove."
    cl = mk(); tid, jid, p = again_with_a_parked_slide(cl, lr, talk_fake)
    t = lr.talk(tid); live = [s for s in t.slides if s.get('section') != GONE]
    h = cl.get(f'/t/{tid}').text
    assert f"About {sum(s['mins'] for s in live)} min" in h and 'Put back in the talk' in h and 'not in the talk' in h
    assert f"{len(live)} slides" in cl.get('/learn').text
    cl.post(f'/t/{tid}/start')
    r = lr.run(lr.talk(tid).live)
    pres = cl.get(f'/t/{tid}/present').text
    assert f'data-sid="{p["id"]}"' not in pres and f'data-sid="{live[0]["id"]}"' in pres and r['at']['slide'] != p['id']
    assert f'data-sid="{p["id"]}"' not in cl.get(f"/t/{tid}/audience?k={r['key']}").text
    assert 'No such slide.' in cl.post(f'/t/{tid}/at', data=dict(slide=p['id'], beat=1)).text
    assert any(s['id'] == p['id'] for s in lr.talk(tid).slides)   # starting and moving never drop the parked slide
    cl.post(f'/t/{tid}/end')
    assert any(s['id'] == p['id'] for s in lr.talk(tid).slides)

def test_put_back_is_one_change(mk, lr, talk_fake):
    "Put back in the talk moves the slide before the closing slides as one history row, and Undo parks it again; Remove works too."
    cl = mk(); tid, jid, p = again_with_a_parked_slide(cl, lr, talk_fake)
    before = lr.talk(tid).slides; n = len(lr.edits('talk', tid))
    r = cl.post(f'/t/{tid}/slide', data=dict(sid=p['id'], act='back'))
    ss = lr.talk(tid).slides
    assert f'Put “{p["title"]}” back in the talk.' in r.text and len(lr.edits('talk', tid)) == n + 1
    assert [s['kind'] for s in ss[-3:]] == ['idea', 'questions', 'recap'] and ss[-3]['id'] == p['id'] and ss[-3]['section'] != GONE
    assert talk_again(lr, talk_fake, tid).slides[-3]['id'] == p['id']   # a later Make it again does not park it again
    while len(lr.edits('talk', tid)) > n: cl.post(f'/t/{tid}/undo')
    assert lr.talk(tid).slides == before
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='back')).text == 'This slide is in the talk already.'
    cl.post(f'/t/{tid}/slide', data=dict(sid=p['id'], act='drop'))
    assert not any(s['id'] == p['id'] for s in lr.talk(tid).slides)

def test_changed_ideas_line(mk, lr, talk_fake):
    "A note that changes in the walk shows as a changed idea; Make it again takes it and keeps the note that you wrote on another slide."
    cl = mk(); jid = prep_walk(lr, walk(cl, lr)); tid = make_talk(cl, jid)
    a, b = [s['concept'] for s in lr.talk(tid).slides[:2]]
    cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', notes='Mine.'))
    lr.walk_slug(jid, a, note='A new note in the walk.'); lr.walk_slug(jid, b, note='Another new note.')
    h = cl.get(f'/t/{tid}').text
    assert '2 ideas changed in the walk. Make it again to take the changes.' in h and 'The walk changed after this talk was made:' not in h
    t = talk_again(lr, talk_fake, tid); by = {s.get('concept'): s for s in t.slides}
    assert by[a]['notes'] == 'Mine.' and by[b]['notes'] == 'Another new note.' and walk_changes(lr, t).changed == 0
    assert 'changed in the walk' not in cl.get(f'/t/{tid}').text

def test_second_talk_under_more(mk, lr, talk_fake):
    "Make a second talk (under More on the walk page) still makes a new talk with a new id."
    cl = mk(); jid = prep_walk(lr, walk(cl, lr)); tid = make_talk(cl, jid)
    tid2 = make_talk(cl, jid)
    assert tid2 != tid and lr.talk(tid) and lr.talk(tid2)

def test_again_remakes_the_talk_it_is_pressed_in(mk, lr, talk_fake):
    "With two talks of one walk, Make it again in the older talk remakes that talk, not the newest; a talk of another walk is refused."
    cl = mk(); jid = prep_walk(lr, walk(cl, lr)); old = make_talk(cl, jid); new = make_talk(cl, jid)
    drop_and_add(lr, jid, lr.talk(old).slides[1]['concept'])
    h = cl.get(f'/t/{old}').text
    assert f'name="tid" value="{old}"' in h
    cl.post('/talk/new', data=dict(jid=jid, again='1', tid=old))
    loc = wait_for(lambda: cl.get(f'/talk/job?jid={old}').headers.get('hx-redirect'))
    assert loc == f'/t/{old}?done=again' and lr.edits('talk', old)[0].what == AGAIN and not lr.edits('talk', new)
    other = lr.put_talk({**lr.talk(new), 'id': 'other-talk-ab12', 'src': {'walk': 'another-walk'}})
    assert 'No such talk for this walk.' in cl.post('/talk/new', data=dict(jid=jid, again='1', tid=other.id)).text

def test_again_zero_is_not_again(mk, lr, talk_fake):
    "again=0 (or a word) makes a new talk as before; it does not remake the talk."
    cl = mk(); jid = prep_walk(lr, walk(cl, lr)); tid = make_talk(cl, jid)
    for v in ('0', 'no'):
        cl.post('/talk/new', data=dict(jid=jid, again=v, tid=tid))
        loc = wait_for(lambda: (h := cl.get(f'/talk/job?jid={jid}').headers.get('hx-redirect')) and 'done=again' not in h and h.split('/')[-1] != tid and h or None)
        assert loc and not lr.edits('talk', tid)

def test_after_page_with_a_parked_slide(mk, lr, talk_fake):
    "After a run that showed a slide that is parked now, the After page and the recap file still open."
    cl = mk(); jid = prep_walk(lr, walk(cl, lr)); tid = make_talk(cl, jid)
    cl.post(f'/t/{tid}/start'); s2 = lr.talk(tid).slides[1]
    cl.post(f'/t/{tid}/at', data=dict(slide=s2['id'], beat=1)); cl.post(f'/t/{tid}/end')
    drop_and_add(lr, jid, s2['concept']); talk_again(lr, talk_fake, tid)
    rid = lr.runs(tid)[0]['id']
    assert cl.get(f'/t/{tid}/after?run={rid}').status_code == 200
    r = cl.get(f'/t/{tid}/recap.html?run={rid}&look=1')
    assert r.status_code == 200 and lr.talk(tid).slides[0]['title'] in r.text
