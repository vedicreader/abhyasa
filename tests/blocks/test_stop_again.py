"Stop and Do it again on every job: in the jobs list (the activity chip) and on the part that waits for it. Then Make this walk again, from the ⋯ menu of a walk."
import json, re, threading, time
from abhyasa.learner import job_start, job_end, STOPPED
from walk_data import walk, wait_for

EXTRACT = 'Return JSON: {"concepts"'
PROPOSE = 'You propose changes to one learning walk'

def chip(h): return re.search(r'<details[^>]*id="activity".*?</details>', h, re.S)[0]

def held(fake, key):
    "Hold the replies of the rule `key` of `fake` until the event is set, so the job still runs when the test presses Stop."
    go, real = threading.Event(), fake.rules[key]
    fake.rules[key] = lambda p, sp: (go.wait(10), real(p, sp) if callable(real) else real)[1]
    return go

def stop(cl, key): return cl.post('/activity/stop', data=dict(key=key))
def again(cl, key): return cl.post('/activity/again', data=dict(key=key))
def ended(lr, key): return wait_for(lambda: (r := lr.job(key)) and r.state != 'running' and r or None, secs=10)

# The jobs list

def test_a_running_job_has_stop_and_stop_asks_it_to_end(mk, lr):
    "A running job shows Stop in the chip. Stop marks the row; the chip then says Stopping…, and the reply tells the part to load again."
    cl = mk()
    job_start(lr, 'build:s', 'build', title='A walk from a link', said='Reading the paper')
    c = chip(cl.get('/').text)
    assert 'data-act="stop-job"' in c and '{"key": "build:s"}' in c
    r = stop(cl, 'build:s')
    assert r.headers['hx-trigger'] == 'job' and lr.job('build:s').halt
    assert 'Stopping…' in cl.get('/activity').text and 'data-act="stop-job"' not in cl.get('/activity').text

def test_a_job_with_no_way_to_run_again_shows_no_button(mk, lr):
    "An ended job that kept no inputs has no Do it again; one that kept them has it, also after a restart closed it."
    cl = mk()
    job_start(lr, 'build:n', 'build', title='No inputs'); job_end(lr, 'build:n', 'failed', why='It did not work.')
    assert 'data-act="again-job"' not in cl.get('/activity').text
    job_start(lr, 'build:y', 'build', title='With inputs', again=dict(url='https://example.org/a'))
    cl = mk()   # a restart closes it
    a = cl.get('/activity').text
    assert lr.job('build:y').state == 'closed' and a.count('data-act="again-job"') == 1 and 'build:y' in a
    assert again(cl, 'build:n').headers['hx-trigger'] == 'job' and lr.job('build:n').state == 'failed'   # nothing starts

def test_the_mac_app_sees_stop_and_again(mk, lr):
    "The rows for the Mac app say whether Stop was asked and whether the job can run again."
    cl = mk()
    job_start(lr, 'k1', 'build', title='One', again=dict(url='u')); stop(cl, 'k1')
    run = cl.get('/jobs.json').json()['running']
    assert [(r['key'], r['halt'], r['again']) for r in run] == [('k1', True, False)]

# A fake slow job: the box of a walk

def test_stop_ends_a_slow_job_at_its_next_step_and_do_it_again_starts_it(mk, walk_fake, lr):
    "The box waits for the model. Stop: the model call ends, its result is not used, the walk does not change, and the job says You stopped it. Do it again starts the same job."
    walk_fake.rules[PROPOSE] = dict(changes=[dict(op='easier', idea='softmax', why='The check asks less.')])
    go = held(walk_fake, PROPOSE)
    cl = mk(); jid = walk(cl, lr)
    r = cl.post(f'/w/{jid}/improve', data=dict(words='Make the walk simpler.')).text
    key = re.search(r'data-job="(improve:[^"]+)"', r)[1]
    assert 'data-act="stop-job"' in r   # the part that waits has Stop
    stop(cl, key); go.set()
    row = ended(lr, key)
    assert (row.state, row.said) == ('stopped', STOPPED) and not lr.edits('walk', jid)   # no change was kept
    p = cl.get(f'/w/{jid}/improve', params=dict(key=key)).text
    assert f'{STOPPED} Nothing changed.' in p and 'data-act="again-job"' in p and 'Stopped: Change the walk' in chip(cl.get('/').text)
    again(cl, key)
    assert lr.job(key).state == 'running' and lr.job(key).again == dict(jid=jid, words='Make the walk simpler.')
    assert ended(lr, key).state == 'done' and len(lr.edits('walk', jid)) == 1

def test_a_demo_stops_and_makes_it_again(mk, walk_fake, lr):
    "Show me on a concept page: the wait has Stop; after Stop the card says so, with Make it again, which starts the same demo job."
    walk_fake.rules['You design one interactive demo'] = 'no JSON here'   # each try fails the checks: a safe point
    go = held(walk_fake, 'You design one interactive demo')
    cl = mk()
    r = cl.post('/demo/ask', data=dict(concept='ranking', where='concept')).text
    assert 'data-job="demo:ranking"' in r and 'data-act="stop-job"' in r
    stop(cl, 'demo:ranking'); go.set()
    assert ended(lr, 'demo:ranking').state == 'stopped'
    aid = re.search(r'/demo/asked/([0-9a-f]+)', r)[1]
    t = cl.get(f'/demo/asked/{aid}').text
    assert STOPPED in t and 'Make it again' in t
    again(cl, 'demo:ranking')
    assert lr.job('demo:ranking').state == 'running' and lr.job('demo:ranking').again['slug'] == 'ranking'

# Make this walk again

REPLAN = 'Make the plan of this walk again from its source? Locked ideas stay. Your answers stay.'

def test_the_menu_has_make_this_walk_again_with_one_confirm(mk, walk_fake, lr):
    "The ⋯ menu of the walk, on its page and on its row on Home, has Make this walk again next to Delete this walk, with one confirm line."
    cl = mk(); jid = walk(cl, lr)
    for url in (f'/w/{jid}', '/'):
        t = cl.get(url).text
        assert 'Make this walk again' in t and REPLAN in t and f'action="/w/{jid}/replan"' in t and t.index('Make this walk again') < t.index('Delete this walk')

def test_make_this_walk_again_keeps_locked_ideas_and_answers_with_one_undo(mk, walk_fake, lr):
    "A locked idea stays as it is and in its place, an idea you removed comes back from the source, your answers stay, and one Undo takes it back."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    a, mid, b = [s['slug'] for s in lr.journey(jid).steps]
    cl.get(f'/w/{jid}/0/check'); cl.post(f'/w/{jid}/0/answer', data=dict(answer='the rank', confidence=70))
    n = len(lr.attempts(a))
    cl.post(f'/w/{jid}/edit', data=dict(slug=b, act='lock'))
    cl.post(f'/w/{jid}/edit', data=dict(slug=mid, act='remove'))
    lr.walk_slug(jid, b, note='My own note.')   # a locked idea that is not as the source has it
    locked = json.dumps(next(s for s in lr.journey(jid).steps if s['slug'] == b), sort_keys=True)
    r = cl.post(f'/w/{jid}/replan', follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == f'/w/{jid}#change'
    key = f'walk:{jid}:replan'
    assert ended(lr, key).state == 'done'
    j = lr.journey(jid)
    assert [s['slug'] for s in j.steps] == [a, b, mid]   # the locked idea keeps its place, 2; the idea you removed comes back after it
    assert json.dumps(j.steps[1], sort_keys=True) == locked and j.steps[0].get('done') and len(lr.attempts(a)) == n
    t = cl.get(f'/w/{jid}').text
    assert 'The tutor made the plan again from its source. Locked ideas stayed.' in t and 'data-act="undo-change"' in t
    assert lr.edits('walk', jid)[0].what == 'Made the plan again from its source. Locked ideas stayed.'
    cl.post(f'/w/{jid}/undo', data=dict(step=lr.edits('walk', jid)[0].id))
    assert [s['slug'] for s in lr.journey(jid).steps] == [a, b]

def test_a_walk_from_its_source_with_no_chips_is_made_again_with_one_press(mk, walk_fake, lr):
    "A walk from a link or a paper has its source documents and no chips. Its form has no list of sources, and the job starts: it does not ask for a source."
    cl = mk(); jid = walk(cl, lr)
    j = lr.journey(jid)
    lr.merge_journey(jid, source={**(j.get('source') or {}), 'docs': [j.steps[0].get('doc') or 'd1']})
    t = cl.get(f'/w/{jid}').text
    assert 'Make this walk again' in t and 'replan-src' not in t
    r = cl.post(f'/w/{jid}/replan', data=dict(form='1'))
    assert 'Keep one source or add one' not in r.text and r.headers.get('hx-redirect') == f'/w/{jid}#change'
    assert lr.job(f'walk:{jid}:replan') is not None

def test_make_this_walk_again_shows_a_skeleton_then_the_new_plan_and_what_changed(mk, walk_fake, lr):
    """While the tutor makes the plan again, the plan is a skeleton and its line asks every 5 seconds. When it is ready, the new plan takes the place
    of the skeleton, and the Undo bar under the plan says what changed. The activity list says it too."""
    cl = mk(); jid = walk(cl, lr)
    cl.post(f'/w/{jid}/edit', data=dict(slug=lr.journey(jid).steps[1]['slug'], act='remove'))
    go, key = held(walk_fake, EXTRACT), f'walk:{jid}:replan'
    cl.post(f'/w/{jid}/replan')
    t = cl.get(f'/w/{jid}').text
    assert 'plan-busy' in t and 'aria-busy="true"' in t and 'hx-trigger="job, every 5s"' in t
    go.set()
    assert ended(lr, key).state == 'done'
    p = cl.get(f'/w/{jid}/replan', params=dict(key=key)).text
    assert 'id="steps"' in p and 'hx-swap-oob="true"' in p and 'plan-busy' not in p
    assert 'id="undo-bar"' in p and 'Added 1 idea: “' in p and 'Removed no ideas.' in p and 'The plan has 3 ideas now.' in p
    assert 'Added 1 idea' in lr.job(key).said and 'plan-busy' not in cl.get(f'/w/{jid}').text

def test_make_this_walk_again_on_its_page_swaps_in_place(mk, walk_fake, lr):
    """From the walk page, the form does not redirect: a redirect to the same page with only `#change` added loads nothing. The answer closes the menu,
    puts the line in the box and the skeleton in the place of the plan. From Home, the walk page opens."""
    cl = mk(); jid = walk(cl, lr)
    go, key = held(walk_fake, EXTRACT), f'walk:{jid}:replan'
    r = cl.post(f'/w/{jid}/replan', data=dict(form='1'), headers={'HX-Request': 'true', 'HX-Current-URL': f'http://localhost:5088/w/{jid}#change'})
    assert 'hx-redirect' not in r.headers
    assert 'class="more-menu walk-menu"' in r.text and 'walk-menu" open' not in r.text
    assert 'id="change-out"' in r.text and 'data-act="stop-job"' in r.text and 'plan-busy' in r.text and r.text.count('hx-swap-oob="true"') == 2
    go.set(); assert ended(lr, key).state == 'done'
    r = cl.post(f'/w/{jid}/replan', data=dict(form='1'), headers={'HX-Request': 'true', 'HX-Current-URL': 'http://localhost:5088/'})
    assert r.headers['hx-redirect'] == f'/w/{jid}#change'

def test_stop_on_make_this_walk_again_keeps_the_plan(mk, walk_fake, lr):
    "Stop while the tutor reads the source: the plan does not change, the line says so, and Plan it again starts the same job."
    cl = mk(); jid = walk(cl, lr)
    cl.post(f'/w/{jid}/edit', data=dict(slug=lr.journey(jid).steps[1]['slug'], act='remove'))
    was = [s['slug'] for s in lr.journey(jid).steps]
    go = held(walk_fake, EXTRACT)
    cl.post(f'/w/{jid}/replan')
    key = f'walk:{jid}:replan'
    t = cl.get(f'/w/{jid}').text
    assert 'data-act="stop-job"' in t and f'data-job="{key}"' in t   # the line of the job, with Stop, under the box
    stop(cl, key); go.set()
    assert ended(lr, key).state == 'stopped' and [s['slug'] for s in lr.journey(jid).steps] == was
    p = cl.get(f'/w/{jid}/replan', params=dict(key=key)).text
    assert f'{STOPPED} The plan did not change.' in p and 'Plan it again' in p
    assert 'id="steps"' in p and 'hx-swap-oob="true"' in p and 'plan-busy' not in p   # the plan comes back in the place of its skeleton
    again(cl, key)
    assert ended(lr, key).state == 'done' and len(lr.journey(jid).steps) == 3
