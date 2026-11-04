"Delete a talk, and Make it again from scratch: the talk goes with its runs and its history, or its slides come again from the walk with no edits."
import re
from talk_data import *
from abhyasa.show import talk_from_walk, FRESH
from abhyasa.learner import job_start

DROP_SAYS = 'Delete this talk? Its slides and runs go. Your walk, answers and what you learned stay.'

def new_talk(mk, lr):
    cl = mk(); jid = prep_walk(lr, walk(cl, lr)); return cl, jid, make_talk(cl, jid)

def test_delete_from_the_editor(mk, talk_fake, lr):
    "The editor has Delete this talk with one confirm line. The delete takes the talk, its runs and its history, then the walk page opens. The walk stays."
    cl, jid, tid = new_talk(mk, lr)
    cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', notes='Mine.'))
    cl.post(f'/t/{tid}/start'); cl.post(f'/t/{tid}/end')
    assert lr.runs(tid) and lr.edits('talk', tid)
    page = cl.get(f'/t/{tid}').text
    assert 'Delete this talk' in page and DROP_SAYS in page and f'action="/t/{tid}/drop"' in page
    r = cl.post(f'/t/{tid}/drop', follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == f'/w/{jid}'
    assert lr.talk(tid) is None and not lr.runs(tid) and not lr.edits('talk', tid) and lr.journey(jid)
    assert f'/t/{tid}' not in cl.get('/').text and f'/t/{tid}' not in cl.get(f'/w/{jid}').text
    assert cl.get(f'/t/{tid}').status_code == 404 and cl.post(f'/t/{tid}/drop').status_code == 404

def test_delete_in_each_list(mk, talk_fake, lr):
    "Home (Teach) and the walk page show Delete this talk on each talk, with the confirm line."
    cl, jid, tid = new_talk(mk, lr)
    for u in ('/', f'/w/{jid}'):
        page = cl.get(u).text
        assert f'action="/t/{tid}/drop"' in page and DROP_SAYS in page, u

def test_delete_goes_home_when_the_walk_is_gone(mk, talk_fake, lr):
    "A talk whose walk is gone goes to Home after the delete."
    cl, jid, tid = new_talk(mk, lr)
    lr.put_talk({**lr.talk(tid), 'src': {'walk': 'no-such-walk'}})
    r = cl.post(f'/t/{tid}/drop', follow_redirects=False)
    assert r.headers['location'] == '/' and lr.talk(tid) is None

def test_no_delete_while_presented(mk, talk_fake, lr):
    "A talk that runs now is not deleted: the line says to end the talk first. After End the talk, the delete works."
    cl, jid, tid = new_talk(mk, lr)
    cl.post(f'/t/{tid}/start')
    page = cl.get(f'/t/{tid}').text
    assert 'This talk is being presented now. End the talk first, then delete it.' in page and f'action="/t/{tid}/drop"' not in page
    r = cl.post(f'/t/{tid}/drop', follow_redirects=False)
    assert r.status_code == 409 and 'End the talk first' in r.text and lr.talk(tid)
    cl.post(f'/t/{tid}/end')
    assert cl.post(f'/t/{tid}/drop', follow_redirects=False).status_code == 303 and lr.talk(tid) is None

def test_no_delete_while_a_job_changes_it(mk, talk_fake, lr):
    "A talk that a job changes now is not deleted, so the job cannot save it again."
    cl, jid, tid = new_talk(mk, lr)
    job_start(lr, f'talk:{tid}', 'talk', title='Talk')
    assert 'abhyasa is changing this talk now. Stop the job first, then delete it.' in cl.get(f'/t/{tid}').text
    assert cl.post(f'/t/{tid}/drop', follow_redirects=False).status_code == 409 and lr.talk(tid)

# --- Make it again from scratch ----------------------------------------------------------------------------------------

def test_from_scratch_is_offered(mk, talk_fake, lr):
    "The walk page and the editor offer Make it again from scratch next to Make it again; it posts fresh=1 with the talk id."
    cl, jid, tid = new_talk(mk, lr)
    for u in (f'/w/{jid}', f'/t/{tid}'):
        page = cl.get(u).text
        assert 'Make it again from scratch' in page and ('&quot;fresh&quot;: &quot;1&quot;' in page or '"fresh": "1"' in page or 'name="fresh" value="1"' in page), u
    assert 'Make the talk again (keeps your edits)' in cl.get(f'/w/{jid}').text

def test_from_scratch_drops_edits_with_undo(mk, talk_fake, lr):
    "From scratch runs as a job on the talk id. The slides are new from the walk with no edits, as one change: one Undo gives the edits back."
    cl, jid, tid = new_talk(mk, lr); made = lr.talk(tid).slides
    cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', notes='Mine.'))
    cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='drop'))
    mine = lr.talk(tid).slides
    r = cl.post('/talk/new', data=dict(jid=jid, again='1', tid=tid, fresh='1'))
    assert f'/talk/job?jid={tid}' in r.text and 'Making the talk again from scratch' in r.text
    loc = wait_for(lambda: cl.get(f'/talk/job?jid={tid}').headers.get('hx-redirect'))
    assert loc == f'/t/{tid}?done=fresh' and len(lr.talks()) == 1
    t = lr.talk(tid)
    assert t.slides == made and lr.edits('talk', tid)[0].what == FRESH and FRESH in cl.get(loc).text
    assert lr.job(f'talk:{tid}').again == dict(jid=jid, tid=tid, fresh=True)   # Do it again makes it from scratch again
    cl.post(f'/t/{tid}/undo')
    assert lr.talk(tid).slides == mine

def test_from_scratch_stops(mk, talk_fake, lr):
    "Stop during From scratch ends the job, and the talk keeps your edits."
    from abhyasa.learner import stop_job
    cl, jid, tid = new_talk(mk, lr)
    cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', notes='Mine.')); mine = lr.talk(tid).slides
    talk_fake.rules['You write one slide of a talk'] = lambda p, sp: (stop_job(lr, f'talk:{tid}'), SLIDE)[1]
    cl.post('/talk/new', data=dict(jid=jid, again='1', tid=tid, fresh='1'))
    wait_for(lambda: True if lr.job(f'talk:{tid}').state != 'running' else None)
    assert lr.job(f'talk:{tid}').state == 'stopped' and lr.talk(tid).slides == mine
    assert 'You stopped it.' in cl.get(f'/talk/job?jid={tid}').text and 'Do it again' in cl.get(f'/talk/job?jid={tid}').text
