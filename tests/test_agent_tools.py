import json, time
import apsw
from abhyasa import agent_tools as at
from abhyasa.learner import NO_CHECK, temp_learning
from abhyasa.models import Withheld, guard

PLAN = json.dumps(dict(title='Ranking', subject='ml', steps=[
    dict(name='Ranking', statement='Ranking orders items by a score.', ways=['words']),
    dict(name='Rank fusion', statement='Fusion adds one over rank plus k for each list.', ways=['words'])]))
QUOTE = 'Ranking orders items by score.'
MAIL = 'learn ranking for jane.doe@example.com'

def plan_ask(p, sp=''): return PLAN

def raiser(e):
    def f(*a, **kw): raise e
    return f

def mk_walk(lr, jid='w1', check=None):
    "A walk on the concepts of the `lr` fixture: step 0 has a linked quote, step 1 has no source, step 2 has text but no link."
    lr.put('Scores', 'A score is a number for one item.', 'ml')
    read = dict(src='vault:notes', ref='n1', title='My ranking notes', url='https://example.org/notes', text=QUOTE)
    ck = check or dict(NO_CHECK)
    steps = [dict(slug='ranking', status='todo', read=read, check=ck), dict(slug='reciprocal-rank-fusion', status='todo', read=None, check=dict(NO_CHECK)),
             dict(slug='scores', status='todo', read={**read, 'url': ''}, check=dict(NO_CHECK))]
    return lr.put_journey(dict(id=jid, title='Ranking', goal='learn ranking', subject='ml', mode='walk', steps=steps, created=time.time())).id

def test_create_walk_ok_and_every_failure(monkeypatch):
    lr, seen = temp_learning(), []
    r = at.create_walk(lr, plan_ask, 'learn ranking', progress=lambda s, f: seen.append(s))
    assert (r['status'], r['error'], r['data']['steps'], r['data']['redacted']) == ('ok', None, 2, False) and r['walk'] == lr.journeys()[0].id
    assert list(dict.fromkeys(seen)) == ['planning', 'sources', 'steps'] and json.loads(json.dumps(r)) == r

    def fails(ask, stopping=lambda: False, progress=lambda s, f: None, goal='learn ranking'):
        lr = temp_learning()
        r = at.create_walk(lr, ask, goal, stopping, progress)
        assert not lr.journeys(), 'a failed walk leaves no journey'
        return r['status'], r['error']
    assert fails(raiser(at.ModelRefused('no'))) == ('error', 'model_refused')
    assert fails(lambda p, sp='': 'not json') == ('error', 'model_refused')
    assert fails(lambda p, sp='': json.dumps(dict(title='x', subject='ml', steps=[]))) == ('error', 'no_source')
    for e, want in ((apsw.ReadOnlyError('x'), 'read_only'), (apsw.BusyError('x'), 'vault_locked')):
        lw = temp_learning(); monkeypatch.setattr(lw, 'put_journey', raiser(e))
        assert at.create_walk(lw, plan_ask, 'learn ranking')['error'] == want

    asked = []
    monkeypatch.setattr(at, 'guard', lambda s: guard(s, mode='refuse'))
    assert fails(lambda p, sp='': asked.append(p) or PLAN, goal=MAIL) == ('error', 'withheld') and not asked
    monkeypatch.setattr(at, 'guard', lambda s: guard(s, mode='redact'))
    lr = temp_learning()
    r = at.create_walk(lr, lambda p, sp='': asked.append(p) or PLAN, MAIL)
    assert r['data']['redacted'] and 'jane.doe@example.com' not in ' '.join(asked) and lr.journey(r['walk']).title == MAIL

def test_stop_leaves_no_partial_walk():
    asked, flag = [], []
    assert fails_stop(lambda p, sp='': asked.append(p) or PLAN, lambda: True) == ('stopped', 'stopped') and not asked, 'a stop before the call sends nothing'
    def stops_inside(p, sp=''): asked.append(p); flag.append(1); return PLAN
    assert fails_stop(stops_inside, lambda: bool(flag)) == ('stopped', 'stopped') and len(asked) == 1, 'a stop inside the call is seen before the walk is saved'
    asked.clear(); flag.clear()
    late = lambda stage, frac: flag.append(1) if stage == 'sources' else None
    assert fails_stop(plan_ask, lambda: bool(flag), late) == ('stopped', 'stopped'), 'a stop after the planner saved the walk drops it'

def fails_stop(ask, stopping, progress=lambda s, f: None):
    lr = temp_learning()
    r = at.create_walk(lr, ask, 'learn ranking', stopping, progress)
    assert not lr.journeys()
    return r['status'], r['error']

def test_walk_state_labels_ungrounded_steps_and_context(lr):
    jid = mk_walk(lr)
    r = at.walk_state(lr, jid)
    d = r['data']
    assert r['status'] == 'ok' and json.loads(json.dumps(r)) == r and d['current'] == 0
    assert [s['ungrounded'] for s in d['steps']] == [False, True, True], 'no passage, or a passage with no link, is ungrounded'
    assert d['steps'][0]['quote'] == dict(text=QUOTE, url='https://example.org/notes', title='My ranking notes') and d['steps'][1]['quote'] is None
    assert d['steps'][0]['check']['kind'] == 'short' and set(d['gauge']) == {'ranking', 'reciprocal-rank-fusion', 'scores'}
    assert at.walk_state(lr, 'nope')['error'] == 'not_found'
    monkey_error = lr.journey; lr.journey = raiser(apsw.BusyError('x'))
    try: assert at.walk_state(lr, jid)['error'] == 'vault_locked'
    finally: lr.journey = monkey_error

    c0, c1 = at.learner_context(lr, jid), at.learner_context(lr, jid, 1)
    assert at.RULE in c0 and QUOTE in c0 and 'https://example.org/notes' in c0 and 'ungrounded' not in c0.split(at.RULE)[1]
    assert 'This step is ungrounded' in c1 and QUOTE not in c1 and len(at.learner_context(lr, jid, n=300)) <= 301
    assert 'No walk is open' in at.learner_context(lr) and at.RULE in at.learner_context(lr, 'nope')

def test_record_attempt_is_graded_once_per_attempt_id(lr, walk_fake):
    jid = mk_walk(lr)
    n = lambda: len(lr.attempts('ranking', limit=None))
    a = at.record_attempt(lr, jid, 0, 'it ranks by position', 'a1', walk_fake)
    assert (a['status'], a['data']['done'], a['data']['correct'], a['data']['outcome']) == ('ok', True, True, 'solid') and json.loads(json.dumps(a)) == a
    assert lr.journey(jid).steps[0]['done']['outcome'] == 'solid' and n() == 1
    assert a['data']['gauge'] == {'ranking': at.walk_state(lr, jid)['data']['gauge']['ranking']} and a['data']['gauge']['ranking']['floor'] > 0

    calls = len(walk_fake.calls)
    assert at.record_attempt(lr, jid, 0, 'it ranks by position', 'a1', walk_fake) == a and len(walk_fake.calls) == calls and n() == 1, 'a repeat gives the stored result'
    c = at.record_attempt(lr, jid, 0, 'something else', 'a1', walk_fake)
    assert (c['status'], c['error']) == ('error', 'conflict') and n() == 1 and len(walk_fake.calls) == calls
    assert at.record_attempt(lr, jid, 0, 'it ranks', 'a2', walk_fake)['error'] == 'conflict', 'a step that is answered takes no new attempt'

    w = at.record_attempt(lr, jid, 1, 'no idea at all', 'b1', walk_fake)
    assert (w['status'], w['data']['done'], w['data']['correct']) == ('ok', False, False) and lr.journey(jid).steps[1].get('done') is None
    assert at.record_attempt(lr, jid, 1, 'no idea at all', 'b1', walk_fake) == w
    assert at.record_attempt(lr, jid, 1, 'a rank is a position', 'b2', walk_fake)['data']['done'] is True and lr.journey(jid).steps[1]['done']['outcome']
    assert len(lr.attempts('reciprocal-rank-fusion', limit=None)) == 2

def test_record_attempt_failures(lr, walk_fake):
    jid = mk_walk(lr, 'w1')
    nb = mk_walk(lr, 'w2', check=dict(way='code', kind='notebook', depth=6))
    assert [at.record_attempt(lr, j, i, 'x', 'k', walk_fake)['error'] for j, i in (('nope', 0), (jid, 9), (nb, 0))] == ['not_found'] * 3
    for e, want in ((Withheld('x'), 'withheld'), (at.ModelRefused('x'), 'model_refused')):
        r = at.record_attempt(lr, jid, 2, 'rank', 'k', raiser(e))
        assert (r['status'], r['error']) == ('error', want)
    assert not lr.attempts('scores', limit=None)
    for e, want in ((apsw.ReadOnlyError('x'), 'read_only'), (apsw.BusyError('x'), 'vault_locked')):
        keep, lr.update = lr.update, raiser(e)
        try: assert at.record_attempt(lr, jid, 2, 'rank', 'k2', walk_fake)['error'] == want
        finally: lr.update = keep

def test_note_confusion_is_no_answer(lr):
    jid = mk_walk(lr)
    state = lambda: (len(lr.attempts(limit=None)), lr.concept('ranking'))
    before = state()
    r = at.note_confusion(lr, jid, 0, 'why  does\nrank start at 1')
    assert r['status'] == 'ok' and r['data']['recorded'] and r['data']['confuses'] == ['Ranking: why does rank start at 1'] and json.loads(json.dumps(r)) == r
    assert state() == before, 'a confusion makes no attempt and changes no concept'
    assert not at.note_confusion(lr, jid, 0, 'why  does rank start at 1')['data']['recorded'] and not at.note_confusion(lr, jid, 0, '  ')['data']['recorded']
    assert at.note_confusion(lr, jid, 9, 'x')['error'] == 'not_found' and at.note_confusion(lr, 'nope', 0, 'x')['error'] == 'not_found'
    keep, lr.set_profile = lr.set_profile, raiser(apsw.ReadOnlyError('x'))
    try: assert at.note_confusion(lr, jid, 1, 'what is k')['error'] == 'read_only'
    finally: lr.set_profile = keep
