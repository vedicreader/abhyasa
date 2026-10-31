"The course page, Where you start, the stages, and the course line on Today, with a temp vault and the Fake model."
import re, time
from abhyasa.course import join_course

LEVEL = dict(questions=[dict(q='Do you know how a neural network learns?', idea='How a neural network learns'), dict(q='Have you used diffusers?', idea='The diffusers library')])
STAGES = dict(title='Diffusion for comics', makes='a LoRA in your comic style', stages=[
    dict(name='How a neural network learns', makes='a small net that learns', ideas=['Gradient descent', 'Loss'], foundation=True, skip_if='q1'),
    dict(name='Your comic data', makes='captions.jsonl', ideas=['Captions'])])
STEP = dict(way='words', kind='short', depth=2)

def goal_walk(lr, done=0):
    "A goal walk of three ideas from the Start box, with a failed clone; the first `done` ideas are done."
    for n, pre in (('Noise', []), ('Denoise', ['noise']), ('Sample', ['denoise'])): lr.put(n, f'{n} a picture.', 'ml', prereqs=pre)
    j = lr.put_journey(dict(id='gw', title='Diffusion for comics', goal='Fine-tune diffusion for comics', mode='walk', source=None, started=time.time(), created=1.,
                            steps=[dict(slug=s, status='todo', check=dict(STEP)) for s in ('noise', 'denoise', 'sample')],
                            chips=['gh:huggingface/diffusers'], chip_counts={}, notes=['abhyasa could not clone huggingface/diffusers.']))
    for i, s in enumerate(j.steps[:done]):
        lr.walk_step('gw', i, done=dict(outcome='solid', at=time.time())); lr.update(s['slug'], floor=4, seen=1, last=time.time(), stability=5., due=time.time() + 5 * 86400)
    return lr.journey('gw')

def follow(cl, r, tries=200):
    "Ask the pending part again until it gives an answer that is not pending; give that answer."
    for _ in range(tries):
        if 'HX-Redirect' in r.headers or 'hx-trigger="load delay:2s"' not in r.text: return r
        m = re.search(r'hx-get="([^"]+)"', r.text); assert m, r.text
        time.sleep(.05); r = cl.get(m[1].replace('&amp;', '&'))
    raise AssertionError('the job did not end')

def test_course_page_says_where_you_are_and_what_is_next(mk, lr):
    "Two ideas done: you are at idea 3, the reason says why, Continue opens it, and the failed clone and Leela show as blocking rows."
    goal_walk(lr, done=2)
    cl = mk()
    r = cl.get('/course/of/gw', follow_redirects=False)
    cid = lr.journey('gw').course
    assert r.headers['location'] == f'/course/{cid}'
    t = cl.get(f'/course/{cid}').text
    assert 'Stage 1 of 1, idea 3 of 3: <b>Sample</b>' in t and '2 of 3 ideas done.' in t
    assert '>You know the ideas that it needs.<' in t and 'Next: Sample' not in t and 'href="/w/gw/2"' in t   # the idea of You are here shows once
    assert 'abhyasa could not clone huggingface/diffusers.' in t and '1 idea: Sample.' in t
    assert 'Ask me where I start' in t and 'huggingface/diffusers' in t
    assert t.count('class="btn go"') == 1   # one main button

def test_today_shows_the_course_line(mk, lr):
    "Today's top line names the course, what comes next and why, and Continue goes to that idea. An older goal walk gets its course here."
    goal_walk(lr, done=1)
    t = mk().get('/').text
    assert 'Your course' in t and 'Next: Denoise. You know the ideas that it needs.' in t and 'href="/w/gw/1"' in t
    assert lr.journey('gw').course

def test_step_keeps_your_place(mk, lr):
    "Opening an idea of a course walk keeps it as the place where you are: the course page then says You chose it."
    goal_walk(lr, done=1); c = join_course(lr, 'gw')
    lr.update('denoise', floor=3)
    cl = mk()
    assert cl.get('/w/gw/2').status_code == 200
    assert lr.course(c.id).here['slug'] == 'sample'
    assert 'You chose it.' in cl.get(f'/course/{c.id}').text

def test_known_elsewhere_shows_on_the_step(mk, lr):
    "An idea that a session closed at the learned depth shows as known (learned elsewhere) in the walk, and the walk goes past it."
    goal_walk(lr, done=1); lr.update('denoise', floor=4, seen=1)
    t = mk().get('/w/gw/2').text
    assert 'known (learned elsewhere)' in t

def test_where_you_start_plans_the_stages(mk, lr, fake):
    "Ask me where I start: the questions come from the model; a tap and a spoken answer keep the answers; the last one plans the stages. A learner who says no gets the foundation stage first."
    fake.rules.update({'You find out what one learner knows': LEVEL, 'You plan a course to one learner': STAGES,
                       'You plan a learning path': dict(title='Basics', subject='ml', steps=[dict(name='Gradient descent', statement='Step down the slope.', why='w'), dict(name='Loss', statement='How wrong it is.', why='w')])})
    goal_walk(lr); c = join_course(lr, 'gw')
    cl = mk()
    r = follow(cl, cl.post(f'/course/{c.id}/level'))
    assert 'Do you know how a neural network learns?' in r.text and 'data-mic' in r.text
    r = cl.post(f'/course/{c.id}/answer', data=dict(key='q1', answer='no'))
    assert 'Have you used diffusers?' in r.text
    r = cl.post(f'/course/{c.id}/answer', data=dict(key='q2', answer='banana'))
    assert 'Answer yes, a little, or no.' in r.text
    r = follow(cl, cl.post(f'/course/{c.id}/answer', data=dict(key='q2', answer="No, I don't")))
    assert r.headers['HX-Redirect'] == f'/course/{c.id}'
    st = lr.course(c.id).stages
    assert [s['name'] for s in st] == ['How a neural network learns', 'Diffusion for comics', 'Your comic data']
    assert st[0]['walk'] and lr.journey(st[0]['walk']).course == c.id   # the current stage was built at once
    t = cl.get(f'/course/{c.id}').text
    assert 'Stage 1 of 3' in t and 'Gradient descent' in t and 'Your comic data' in t

def test_a_learner_who_knows_it_skips_the_foundation(mk, lr, fake):
    "Yes to the question of the foundation stage: the stage shows as skipped, and the goal walk stays current."
    fake.rules.update({'You find out what one learner knows': LEVEL, 'You plan a course to one learner': STAGES})
    goal_walk(lr); c = join_course(lr, 'gw')
    cl = mk()
    follow(cl, cl.post(f'/course/{c.id}/level'))
    cl.post(f'/course/{c.id}/answer', data=dict(key='q1', answer='yes'))
    follow(cl, cl.post(f'/course/{c.id}/answer', data=dict(key='q2', answer='a little')))
    st = lr.course(c.id).stages
    assert (st[0]['status'], st[0]['walk']) == ('skipped', None)
    t = cl.get(f'/course/{c.id}').text
    assert 'skipped' in t and 'idea 1 of 3: <b>Noise</b>' in t and '>You know the ideas that it needs.<' in t

def test_open_a_planned_stage_builds_it(mk, lr, fake):
    "Plan it now on a planned stage: the walk is built on the pool, then it opens."
    fake.rules['You plan a learning path'] = dict(title='Data', subject='ml', steps=[dict(name='Captions', statement='Words for each picture.', why='w')])
    goal_walk(lr, done=3); c = join_course(lr, 'gw')
    lr.change_course(c.id, lambda c: c.stages.append(dict(key='s2', name='Your comic data', makes='captions.jsonl', ideas=['Captions'], walk=None, status='planned')))
    cl = mk()
    t = cl.get(f'/course/{c.id}').text
    assert 'Stage 2 is next: Your comic data. It makes captions.jsonl.' in t
    r = cl.get(f'/course/{c.id}/stage/s2')
    assert 'abhyasa plans the ideas of this stage' in r.text
    r = follow(cl, r)
    jid = lr.course(c.id).stages[1]['walk']
    assert r.headers['HX-Redirect'] == f'/w/{jid}' and lr.journey(jid).stage == 's2'

def test_goal_on_start_makes_a_course(mk, lr, walk_fake):
    "A goal walk from the Start box joins a new course, and its plan page links to the course."
    walk_fake.rules['You plan a learning path'] = dict(title='Ranks', subject='ml', steps=[dict(name='Ranking', slug='ranking', statement='', why='')])
    cl = mk()
    r = follow(cl, cl.post('/walk/new', data=dict(q='I want to rank search results well', sources=['vault:notes'], chips='1')))
    j = lr.journey(r.headers['HX-Redirect'].split('/')[-1])
    c = lr.course(j.course)
    assert c.goal == 'I want to rank search results well' and c.stages[0]['walk'] == j.id
    assert f'href="/course/{c.id}"' in cl.get(f'/w/{j.id}').text
