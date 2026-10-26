import abhyasa.demo   # patches Learning with put_demo and record_prediction
"The demo block: rupaka served offline, the concept-page action, the demo page, the prediction log, and a demo after two misses."
import json
from rupaka.spec import gallery

def svc(cl): return cl.app.state.svc

def wait_job(cl, concept): svc(cl)['tutor'].jobs[concept].result(timeout=120)

def test_rupaka_served_offline(mk):
    cl = mk()
    js, css = cl.get('/rupaka/rupaka.js'), cl.get('/rupaka/rupaka.css')
    assert js.status_code == 200 and "Rupaka.block('gate'" in js.text and 'immutable' in js.headers['cache-control']
    assert css.status_code == 200 and '--rk-fg' in css.text

def test_concept_page_has_the_action(mk):
    page = mk().get('/c/reciprocal-rank-fusion').text
    assert 'Show me a demo' in page and 'id="demo-slot"' in page and 'Learn this' in page

def test_make_then_wait_gives_the_demo(mk, lr):
    cl = mk()
    first = cl.post('/demo/make', data=dict(concept='reciprocal-rank-fusion')).text
    assert 'demo-card' in first
    wait_job(cl, 'reciprocal-rank-fusion')
    d = lr.demo_for('reciprocal-rank-fusion')
    assert d.by.startswith('model:') and d.spec['concept'] == 'reciprocal-rank-fusion'
    card = cl.get('/demo/wait/reciprocal-rank-fusion').text
    assert 'data-rupaka' in card and 'type="application/json"' in card and '/rupaka/rupaka.js?v=' in card
    assert 'Reciprocal rank fusion' in cl.post('/demo/make', data=dict(concept='reciprocal-rank-fusion')).text   # no second job

def test_failed_job_says_so(mk, fake):
    fake.rules['You design one interactive demo'] = 'no demo'
    cl = mk()
    cl.post('/demo/make', data=dict(concept='ranking'))
    wait_job(cl, 'ranking')
    assert 'did not make a demo that passes' in cl.get('/demo/wait/ranking').text

def test_demo_page_and_json(mk, lr):
    lr.put_demo(gallery()['reciprocal-rank-fusion'], 'reciprocal-rank-fusion')
    cl = mk()
    page = cl.get('/demo/reciprocal-rank-fusion').text
    assert 'data-rupaka' in page and 'href="/c/reciprocal-rank-fusion"' in page
    assert cl.get('/demo/reciprocal-rank-fusion.json').json()['id'] == 'reciprocal-rank-fusion'
    assert cl.get('/demo/nope.json').status_code == 404

def test_predict_writes_an_attempt(mk, lr):
    lr.put_demo(gallery()['reciprocal-rank-fusion'], 'reciprocal-rank-fusion')
    c0 = lr.concept('reciprocal-rank-fusion')
    r = mk().post('/demo/reciprocal-rank-fusion/predict', data=dict(gate='win', picked='A', ans='B', ok='false', why='A is first in BM25',
                                                                    context='With k = 60 and these lists:', session='s9'))
    assert r.json() == dict(ok=True)
    a = lr.attempts('reciprocal-rank-fusion')[0]
    assert (a.kind, a.correct, a.answer, a.expected, a.thinking, a.session, a.demo) == ('demo', False, 'A', 'B', 'A is first in BM25', 's9', 'reciprocal-rank-fusion')
    assert lr.demo('reciprocal-rank-fusion').stats == dict(shown=1, right=0)
    c1 = lr.concept('reciprocal-rank-fusion')
    assert (c1.misses, c1.seen, c1.ceiling) == (c0.misses + 1, c0.seen + 1, 3)   # a wrong pick with a reason counts at depth 3

def start(cl, **data): return cl.post('/start', data=data, follow_redirects=False).headers['location'].split('/')[-1]

def miss(cl, sid):
    "Three sure wrong answers close the question as a miss with a misconception."
    for _ in range(3): r = cl.post(f'/s/{sid}/answer', data=dict(answer='add the scores', confidence=90)).text
    return r

def test_two_misses_make_a_demo_under_the_lesson(mk, lr):
    cl = mk()
    sid = start(cl, focus='ranking')
    cl.get(f'/s/{sid}')
    first = miss(cl, sid)
    assert 'Lesson' in first and 'demo-card' not in first
    cl.post(f'/s/{sid}/next')
    second = miss(cl, sid)
    assert 'The tutor is making a demo' in second and '/demo/wait/ranking' in second and 'm tutor extra' in second   # a tutor message in the thread
    wait_job(cl, 'ranking')
    card = cl.get('/demo/wait/ranking').text
    assert 'data-rupaka' in card
    cl.post(f'/s/{sid}/next')
    third = miss(cl, sid)
    assert 'data-rupaka' in third and f'data-session="{sid}"' in third   # a miss on a concept with a demo shows it at once
