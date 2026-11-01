"Lock what is good, and fix the rest: a locked idea or stage never changes by Improve, by Fix the rest or by a replan. A hand edit unlocks it, with Undo."
import json, re, threading, time
from walk_data import walk
from flows import key_of
from abhyasa.course import join_course

FIX = 'You redo the ideas of one learning walk'
PLAN = 'You plan a course to one learner'

def snap(lr, jid, slugs): return {s['slug']: json.dumps(s, sort_keys=True) for s in lr.journey(jid).steps if s['slug'] in slugs}

def held(go, reply):
    "A rule of the Fake that waits until the test lets it go, so the job is still running when the page asks."
    def f(p, sp): go.wait(10); return reply
    return f

def proposal(cl, r):
    "Ask the pending part again until the proposal comes. Gives its HTML."
    for _ in range(200):
        if 'improve-wait' not in r.text: return r.text
        time.sleep(.05); r = cl.get(re.search(r'hx-get="([^"]+)"', r.text)[1].replace('&amp;', '&'))
    raise AssertionError('no proposal came')

def lock(cl, jid, slug, act='lock'): return cl.post(f'/w/{jid}/edit', data=dict(slug=slug, act=act))

def test_fix_the_rest_never_touches_the_locked_ideas(mk, walk_fake, lr):
    "Lock two ideas, then Fix the rest with your words: the proposal has no change to a locked idea, the apply keeps them byte for byte, and one Undo takes it back."
    cl = mk(); jid = walk(cl, lr)
    a, mid, b = [s['slug'] for s in lr.journey(jid).steps]
    r = lock(cl, jid, a); lock(cl, jid, b)
    assert 'Locked “' in r.text and 'aria-pressed="true"' in r.text and 'lock-mark' in r.text
    was, steps = snap(lr, jid, {a, b}), lr.journey(jid).steps
    go = threading.Event()
    walk_fake.rules[FIX] = held(go, dict(changes=[dict(op='remove', idea=a, why='x'), dict(op='harder', idea=b, why='x'), dict(op='easier', idea=mid, why='Less to do.')]))
    page = cl.get(f'/w/{jid}').text
    assert 'data-act="fix"' in page and '>Fix the rest</button>' in page
    r = cl.post(f'/w/{jid}/improve', data=dict(words='make the rest simpler, add pricing', fix='1'))
    go.set()
    p = proposal(cl, r)
    assert p.count('class="change"') == 1 and 'Less to do.' in p   # only the idea that is not locked
    asked = walk_fake.calls[-1][0]
    assert 'make the rest simpler, add pricing' in asked and asked.count(' · locked') == 2
    r = cl.post(f'/w/{jid}/improve/apply', data=dict(key=key_of(p)))
    assert 'Fixed the rest of the walk: 1 change.' in r.text
    assert snap(lr, jid, {a, b}) == was and [s['slug'] for s in lr.journey(jid).steps] == [a, mid, b]
    assert lr.journey(jid).steps[1]['check'] != steps[1]['check']
    cl.post(f'/w/{jid}/undo')
    assert lr.journey(jid).steps == steps

def test_fix_the_rest_needs_no_words(mk, walk_fake, lr):
    "Fix the rest with an empty box asks the tutor too. Ask the tutor with an empty box asks for words."
    cl = mk(); jid = walk(cl, lr)
    walk_fake.rules[FIX] = dict(changes=[])
    assert 'Write what should change' in cl.post(f'/w/{jid}/improve', data=dict(words='')).text
    assert 'The tutor found nothing to change.' in proposal(cl, cl.post(f'/w/{jid}/improve', data=dict(words='', fix='1')))

def test_a_hand_edit_unlocks_the_idea_and_undo_locks_it_again(mk, walk_fake, lr):
    "A locked idea can still change by hand: the edit unlocks it. Undo gives back the edit and the lock. A live note edit takes the lock off in place."
    cl = mk(); jid = walk(cl, lr)
    slug = lr.journey(jid).steps[1]['slug']
    lock(cl, jid, slug)
    r = cl.post(f'/w/{jid}/edit', data=dict(slug=slug, act='skip'))
    s = lr.journey(jid).steps[1]
    assert s['status'] == 'skip' and 'locked' not in s and f'id="lock-{slug}"' in r.text
    cl.post(f'/w/{jid}/undo')
    s = lr.journey(jid).steps[1]
    assert s['status'] == 'todo' and s['locked'] is True
    r = cl.post(f'/w/{jid}/edit', data=dict(slug=slug, act='set', note='My own note.'))
    assert 'locked' not in lr.journey(jid).steps[1] and f'id="lock-{slug}"' in r.text and 'hx-swap-oob' in r.text
    lock(cl, jid, slug, 'unlock')
    assert 'locked' not in lr.journey(jid).steps[1]

def test_a_locked_stage_stays_after_fix_the_rest(mk, lr, fake):
    "On the course page, lock the stage of the goal walk, then Fix the rest: the locked stage and its walk stay as they were; the stage that is not locked is planned again."
    for n in ('Noise', 'Denoise'): lr.put(n, f'{n} a picture.', 'ml')
    lr.put_journey(dict(id='gw', title='Diffusion for comics', goal='Fine-tune diffusion for comics', mode='walk', source=None, started=time.time(), created=1.,
                        steps=[dict(slug=s, status='todo', check=dict(way='words', kind='short', depth=2)) for s in ('noise', 'denoise')], chips=[], chip_counts={}))
    cid = join_course(lr, 'gw').id
    lr.change_course(cid, lambda c: c.stages.append(dict(key='s2', name='An old plan', makes='', ideas=['Old'], foundation=False, skip_if='', short=False, walk=None, status='planned')))
    cl = mk()
    t = cl.post(f'/course/{cid}/lock', data=dict(key='s1', on='1')).text
    assert 'id="course-stages"' in t and 'aria-pressed="true"' in t and 'lock-mark' in t
    was = json.dumps(lr.course(cid).stages[0], sort_keys=True)
    go = threading.Event()
    fake.rules[PLAN] = held(go, dict(title='x', makes='x', stages=[dict(name='Your comic data', makes='captions.jsonl', ideas=['Captions'])]))
    page = cl.get(f'/course/{cid}').text
    assert 'data-act="fix"' in page and 'Fix the rest' in page
    r = cl.post(f'/course/{cid}/fix')
    go.set()
    for _ in range(200):
        if 'HX-Redirect' in r.headers: break
        time.sleep(.05); r = cl.get(f'/course/{cid}/job?k=plan')
    c = lr.course(cid)
    assert [s['name'] for s in c.stages] == ['Diffusion for comics', 'Your comic data']
    assert json.dumps(c.stages[0], sort_keys=True) == was and c.stages[0]['walk'] == 'gw'
