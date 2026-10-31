import re
import abhyasa.demo   # patches Learning with put_demo and record_prediction
"The demo block: rupaka served offline, the Show slot of the concept page, no demo page of its own, the prediction log, and a demo after two misses."
import json
from rupaka.spec import gallery

def svc(cl): return cl.app.state.svc

def wait_job(cl, concept): svc(cl)['tutor'].jobs[concept].result(timeout=120)

def test_rupaka_served_offline(mk):
    cl = mk()
    js, css = cl.get('/rupaka/rupaka.js'), cl.get('/rupaka/rupaka.css')
    assert js.status_code == 200 and "Rupaka.block('gate'" in js.text and 'immutable' in js.headers['cache-control']
    assert css.status_code == 200 and '--rk-fg' in css.text

def aid_of(html): return re.search(r'data-ask="([0-9a-f]{12})"', html)[1]

def test_the_concept_page_show_slot_makes_then_shows_the_demo(mk, lr):
    "The concept page has one Show me and its Show slot. Show files an ask and starts the job; the ask is the one wait; a second Show starts no job."
    cl = mk()
    page = cl.get('/c/reciprocal-rank-fusion').text
    assert page.count('id="show-demo"') == 1 and 'id="show-slot"' in page and '/demo/make' not in page
    first = cl.post('/demo/ask', data=dict(where='concept', concept='reciprocal-rank-fusion')).text
    assert 'ask-card' in first
    wait_job(cl, 'reciprocal-rank-fusion')
    d = lr.demo_for('reciprocal-rank-fusion')
    assert d.by.startswith('model:') and d.spec['concept'] == 'reciprocal-rank-fusion'
    card = cl.get(f'/demo/asked/{aid_of(first)}').text
    assert 'data-rupaka' in card and 'type="application/json"' in card and '/rupaka/rupaka.js?v=' in card
    n = len(svc(cl)['tutor'].jobs)
    assert 'Reciprocal rank fusion' in cl.post('/demo/ask', data=dict(where='concept', concept='reciprocal-rank-fusion')).text and len(svc(cl)['tutor'].jobs) == n   # no second job
    assert cl.post('/demo/make', data=dict(concept='ranking')).status_code in (404, 405) and cl.get('/demo/wait/ranking').status_code == 404   # one engine

def test_failed_job_says_so(mk, fake):
    fake.rules['You design one interactive demo'] = 'no demo'
    cl = mk()
    a = aid_of(cl.post('/demo/ask', data=dict(where='concept', concept='ranking')).text)
    wait_job(cl, 'ranking')
    assert 'did not make a demo that passes' in cl.get(f'/demo/asked/{a}').text

def test_a_demo_has_no_page_of_its_own(mk, lr):
    "The old page of a demo goes to the Show slot of its idea, on the concept page. The spec JSON stays."
    lr.put_demo(gallery()['reciprocal-rank-fusion'], 'reciprocal-rank-fusion')
    cl = mk()
    r = cl.get('/demo/reciprocal-rank-fusion', follow_redirects=False)
    assert (r.status_code, r.headers['location']) == (301, '/c/reciprocal-rank-fusion')
    assert cl.get('/demo/nope', follow_redirects=False).headers['location'] == '/library'
    assert cl.get('/demo/reciprocal-rank-fusion.json').json()['id'] == 'reciprocal-rank-fusion'
    assert cl.get('/demo/nope.json').status_code == 404

def test_two_demos_with_one_id_at_the_same_time_get_two_slugs(lr, monkeypatch):
    "Two demo jobs that run at once with the same spec id file under two slugs, one for each concept."
    import threading, time
    from abhyasa.store import Learning
    real = Learning.demo
    def slow(self, slug): r = real(self, slug); time.sleep(.05); return r   # widen the gap between the check and the add
    monkeypatch.setattr(Learning, 'demo', slow)
    spec, out = gallery()['reciprocal-rank-fusion'], {}
    ts = [threading.Thread(target=lambda c=c: out.__setitem__(c, lr.put_demo(spec, c))) for c in ('ranking', 'reciprocal-rank-fusion')]
    for t in ts: t.start()
    for t in ts: t.join()
    assert out['ranking'].slug != out['reciprocal-rank-fusion'].slug
    assert {c: lr.demo(d.slug).concept for c, d in out.items()} == {c: c for c in out}

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
    assert 'The tutor makes a demo' in second and '/demo/asked/' in second and 'm tutor extra' in second   # a tutor message in the thread, and its wait is an ask
    wait_job(cl, 'ranking')
    card = cl.get(f'/demo/asked/{aid_of(second)}').text
    assert 'data-rupaka' in card
    cl.post(f'/s/{sid}/next')
    third = miss(cl, sid)
    assert 'data-rupaka' in third and f'data-session="{sid}"' in third   # a miss on a concept with a demo shows it at once

def test_an_order_demo_is_not_the_plain_demo(mk, lr):
    lr.put_demo(gallery()['reciprocal-rank-fusion'], 'reciprocal-rank-fusion', aim='order')
    cl = mk()
    assert 'Show me' in cl.get('/c/reciprocal-rank-fusion').text
    cl.post('/demo/ask', data=dict(where='concept', concept='reciprocal-rank-fusion'))   # the order demo does not count: a plain demo job starts
    d = svc(cl)['tutor'].jobs['reciprocal-rank-fusion'].result(timeout=120)
    assert d.aim == '' and lr.demo_for('reciprocal-rank-fusion', aim='') is not None

def test_the_ladder_after_a_demo_in_a_session(mk, lr, fake):
    "After you saw the demo: a lesson in another way with the demo kept, then a simpler demo, then nothing new."
    import itertools
    n = itertools.count()
    fake.rules['Teach the smallest step'] = lambda p, sp: f'Positions are shared. Check: what if k = {next(n)}?'   # each attempt gets its own text
    lr.put_demo(gallery()['reciprocal-rank-fusion'], 'ranking')
    cl = mk(); sid = start(cl, focus='ranking'); cl.get(f'/s/{sid}')
    def miss(cl, sid):
        "Three sure wrong answers, each with its own words, so the vault keeps each attempt as its own document."
        for k in range(3): r = cl.post(f'/s/{sid}/answer', data=dict(answer=f'add the scores, try {k}', confidence=90)).text
        return r
    first = miss(cl, sid)
    assert 'data-rupaka' in first and 'Lesson · ' not in first                         # the plain demo, as before
    cl.post(f'/s/{sid}/next'); second = miss(cl, sid)
    assert 'Lesson · ' in second and 'data-rupaka' in second and 'A simpler demo' not in second   # another way, and the demo stays
    cl.post(f'/s/{sid}/next'); third = miss(cl, sid)
    assert 'The tutor makes a simpler demo' in third and '/demo/asked/' in third
    svc(cl)['tutor'].jobs['ranking:simpler'].result(timeout=120)
    card = cl.get(f'/demo/asked/{aid_of(third)}').text
    assert 'data-rupaka' in card and lr.asked(aid_of(third)).aim == 'simpler'
    assert lr.demo_for('ranking', aim='').slug == 'reciprocal-rank-fusion'               # the simpler demo is never the plain demo
    cl.post(f'/s/{sid}/next'); fourth = miss(cl, sid)
    assert 'demo-card' not in fourth and 'Lesson · ' not in fourth                     # the third miss after the demo adds nothing

def test_identical_misses_each_count(mk, lr):
    "Misses with the same words are separate attempts: the history keeps each try, and the ladder counts each miss."
    from abhyasa.demo import rung
    lr.put_demo(gallery()['reciprocal-rank-fusion'], 'ranking')
    cl = mk(); sid = start(cl, focus='ranking'); cl.get(f'/s/{sid}')
    miss(cl, sid); cl.post(f'/s/{sid}/next'); miss(cl, sid)
    a = lr.attempts('ranking')
    assert len(a) == 6 and len([x for x in a if x.get('final')]) == 2 and rung(lr, 'ranking') == 1
