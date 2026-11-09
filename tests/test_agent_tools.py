import json, threading, time
import apsw
from abhyasa import agent_tools as at, learner
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

    def fails(ask, stopping=lambda: False, progress=lambda s, f: None, goal='learn ranking', guard=None):
        lr = temp_learning()
        r = at.create_walk(lr, ask, goal, stopping, progress, guard=guard)
        assert not lr.journeys(), 'a failed walk leaves no journey'
        return r['status'], r['error']
    assert fails(raiser(at.ModelRefused('no'))) == ('error', 'model_refused')
    assert fails(lambda p, sp='': 'not json') == ('error', 'model_refused')
    assert fails(lambda p, sp='': json.dumps(dict(title='x', subject='ml', steps=[]))) == ('error', 'source_missing')
    for e, want in ((apsw.ReadOnlyError('x'), 'read_only'), (apsw.BusyError('x'), 'vault_locked')):
        lw = temp_learning(); monkeypatch.setattr(lw, 'put_journey', raiser(e))
        assert at.create_walk(lw, plan_ask, 'learn ranking')['error'] == want

    asked = []
    refuse = lambda s: guard(s, mode='refuse')
    assert fails(lambda p, sp='': asked.append(p) or PLAN, goal=MAIL, guard=refuse) == ('error', 'privacy_refused') and not asked, 'a guard that raises Withheld sends nothing'
    redact = lambda s: guard(s, mode='redact')
    lr = temp_learning()
    r = at.create_walk(lr, lambda p, sp='': asked.append(p) or PLAN, MAIL, guard=redact)
    assert r['data']['redacted'] and 'jane.doe@example.com' not in ' '.join(asked) and lr.journey(r['walk']).title == MAIL, 'the redacted text goes out, the title stays the learner\'s goal'
    asked.clear()
    r = at.create_walk(temp_learning(), lambda p, sp='': asked.append(p) or PLAN, MAIL)
    assert not r['data']['redacted'] and 'jane.doe@example.com' in ' '.join(asked), 'guard=None sends the goal unchanged'

BIG = json.dumps(dict(title='Ranking', subject='ml', steps=[
    dict(name=n, statement=f'{n} is one idea of ranking.', ways=['words']) for n in ('Scores', 'Ranks', 'Fusion', 'Recall', 'Precision', 'Lists')]))

def n_steps(settings=None, ask=lambda p, sp='': BIG):
    r = at.create_walk(temp_learning(), ask, 'learn ranking', settings=settings)
    assert r['status'] == 'ok', r
    return r['data']['steps']

def test_create_walk_takes_the_hosts_settings(monkeypatch, tmp_path):
    monkeypatch.setenv('ABHYASA_CONFIG', str(tmp_path))
    learner.update_settings('walks', steps=4)
    assert n_steps() == 4, 'no settings: the settings file counts, as before'
    assert n_steps({}) == 6 and n_steps({'walks.steps': 3}) == 3 and n_steps({'walks.steps': 5}) == 5, 'given settings replace the file, and the others stay default'
    assert n_steps({'walks.steps': 'x', 'nope.key': 1, 'prompts.x': 2}) == 6, 'a bad value gets the default, an unknown name is ignored'
    assert n_steps() == 4 and json.loads((tmp_path/'settings.json').read_text())['walks']['steps'] == 4, 'nothing leaks to the file or to the next call'

    gate, got = threading.Barrier(2, timeout=30), {}
    def run(name, steps):
        def ask(p, sp=''): gate.wait(); return BIG   # both calls are inside their settings when the model answers
        got[name] = n_steps({'walks.steps': steps}, ask)
    ts = [threading.Thread(target=run, args=a) for a in (('a', 3), ('b', 5))]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert got == dict(a=3, b=5)

def test_given_settings_refuse_a_write(monkeypatch, tmp_path):
    monkeypatch.setenv('ABHYASA_CONFIG', str(tmp_path))
    learner.update_settings('walks', steps=4)
    before = (tmp_path/'settings.json').read_text()
    with learner.use_settings({'walks.steps': 3}):
        try: learner.update_settings('talks', slides=9); wrote = True
        except RuntimeError: wrote = False
    assert not wrote and (tmp_path/'settings.json').read_text() == before, 'a write inside given settings would drop the rows the host did not pass'

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
    assert (c['status'], c['error']) == ('error', 'attempt_conflict') and n() == 1 and len(walk_fake.calls) == calls
    assert at.record_attempt(lr, jid, 0, 'it ranks', 'a2', walk_fake)['error'] == 'attempt_conflict', 'a step that is answered takes no new attempt'

    w = at.record_attempt(lr, jid, 1, 'no idea at all', 'b1', walk_fake)
    assert (w['status'], w['data']['done'], w['data']['correct']) == ('ok', False, False) and lr.journey(jid).steps[1].get('done') is None
    assert at.record_attempt(lr, jid, 1, 'no idea at all', 'b1', walk_fake) == w
    assert at.record_attempt(lr, jid, 1, 'a rank is a position', 'b2', walk_fake)['data']['done'] is True and lr.journey(jid).steps[1]['done']['outcome']
    assert len(lr.attempts('reciprocal-rank-fusion', limit=None)) == 2

def test_record_attempt_refuses_a_stale_revision(lr, walk_fake):
    jid = mk_walk(lr)
    rev = lr.journey(jid).get('updated')
    calls = len(walk_fake.calls)
    s = at.record_attempt(lr, jid, 0, 'it ranks by position', 'a1', walk_fake, revision='old')
    assert (s['status'], s['error']) == ('error', 'stale_state') and s['data']['revision'] == rev and s['revision'] == rev, 'the refusal carries the current revision'
    assert not lr.attempts('ranking', limit=None) and len(walk_fake.calls) == calls, 'a stale call saves and asks nothing'
    ok = at.record_attempt(lr, jid, 0, 'it ranks by position', 'a1', walk_fake, revision=rev)
    assert ok['status'] == 'ok' and ok['revision'] != rev, 'the current revision is accepted, and the answer moves the revision'
    calls = len(walk_fake.calls)
    assert at.record_attempt(lr, jid, 0, 'it ranks by position', 'a1', walk_fake, revision=rev) == ok and len(walk_fake.calls) == calls, 'a retry after a lost reply gets the stored grade, though its revision is now old'
    assert at.record_attempt(lr, jid, 1, 'no idea', 'b1', walk_fake, revision=rev)['error'] == 'stale_state', 'the old revision is now stale'
    assert at.record_attempt(lr, jid, 1, 'no idea', 'b1', walk_fake)['status'] == 'ok', 'no revision, no check'

def test_a_host_extends_the_error_names():
    assert 'thread_busy' not in at.ERRORS
    assert at.failed('thread_busy', 'x', extra=('thread_busy',))['error'] == 'thread_busy' and at.result('error', error='mode_off', extra=('mode_off',))['error'] == 'mode_off'
    for bad in ('thread_busy', 'conflict', 'withheld', 'no_source'):
        try: at.failed(bad); raise AssertionError(bad)
        except ValueError: pass
    assert {'stale_state', 'attempt_conflict', 'privacy_refused', 'source_missing'} <= set(at.ERRORS)

def test_record_attempt_failures(lr, walk_fake):
    jid = mk_walk(lr, 'w1')
    nb = mk_walk(lr, 'w2', check=dict(way='code', kind='notebook', depth=6))
    assert [at.record_attempt(lr, j, i, 'x', 'k', walk_fake)['error'] for j, i in (('nope', 0), (jid, 9), (nb, 0))] == ['not_found'] * 3
    for e, want in ((Withheld('x'), 'privacy_refused'), (at.ModelRefused('x'), 'model_refused')):
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

def say(*changes): return lambda p, sp='': json.dumps(dict(changes=list(changes)))
def steps(lr, jid): return [(s['slug'], s.get('status'), bool(s.get('locked'))) for s in lr.journey(jid).steps]
def withheld(p, sp=''): raise Withheld('no')

def test_every_tool_is_an_operation_and_reads_are_listed():
    names = [n for n, _ in at.TOOLS]
    assert len(names) == len(set(names)) and all(callable(getattr(at, n)) for n in names)
    assert set(at.READS) <= set(names) and {'change_walk', 'keep_idea', 'drop_idea', 'move_idea', 'add_source', 'list_versions', 'restore_version', 'explain_here'} <= set(names)

def test_change_walk_changes_the_plan_as_one_change_with_an_undo(lr):
    jid = mk_walk(lr)
    r = at.change_walk(lr, say(dict(op='skip', idea='scores', why='you asked')), jid, 'skip the scores idea')
    assert (r['status'], r['data']['changed'], r['data']['changes'][0]['op']) == ('ok', True, 'skip') and json.loads(json.dumps(r)) == r
    assert steps(lr, jid)[2][1] == 'skip' and len(lr.edits('walk', jid)) == 1 and r['revision'] == lr.journey(jid).get('updated')
    from abhyasa.path import undo_walk
    undo_walk(lr, jid)
    assert steps(lr, jid)[2][1] == 'todo', 'one Undo takes the whole change back'
    n = at.change_walk(lr, say(), jid, 'something odd')
    assert (n['status'], n['data']['changed'], n['data']['changes']) == ('ok', False, [])
    w = at.change_walk(lr, say(dict(op='source', idea='ranking', why='no source')), jid, 'add sources for idea 1')
    assert w['data']['sources_wanted'] == ['ranking'] and not w['data']['changed']

def test_change_walk_never_changes_a_kept_idea(lr):
    jid = mk_walk(lr)
    assert at.keep_idea(lr, jid, '2')['data']['changed']
    at.change_walk(lr, say(dict(op='skip', idea='reciprocal-rank-fusion', why='x'), dict(op='skip', idea='scores', why='x')), jid, 'skip both')
    assert steps(lr, jid) == [('ranking', 'todo', False), ('reciprocal-rank-fusion', 'todo', True), ('scores', 'skip', False)]

def test_change_walk_failures_leave_the_walk_as_it_was(lr):
    jid = mk_walk(lr)
    before, asked = lr.journey(jid), []
    skip = say(dict(op='skip', idea='scores', why='x'))
    assert [at.change_walk(lr, skip, j, 'x')['error'] for j in ('nope',)] == ['not_found']
    r = at.change_walk(lr, skip, jid, 'x', revision='old')
    assert (r['status'], r['error'], r['data']['revision']) == ('error', 'stale_state', before.get('updated'))
    assert at.change_walk(lr, withheld, jid, 'mail jane.doe@example.com')['error'] == 'privacy_refused'
    assert at.change_walk(lr, raiser(at.ModelRefused('no')), jid, 'x')['error'] == 'model_refused' and at.change_walk(lr, skip, jid, '  ')['error'] == 'model_refused'
    s = at.change_walk(lr, lambda p, sp='': asked.append(p) or '{}', jid, 'x', stopping=lambda: True)
    assert (s['status'], s['error']) == ('stopped', 'stopped') and not asked, 'a stop before the call sends nothing'
    flag = []
    s = at.change_walk(lr, lambda p, sp='': flag.append(1) or skip(p), jid, 'x', stopping=lambda: bool(flag))
    assert s['status'] == 'stopped' and len(flag) == 1, 'a stop inside the call is seen before the walk is saved'
    def moves(p, sp=''): at.keep_idea(lr, jid, '1'); return skip(p)
    before = lr.journey(jid)
    r = at.change_walk(lr, moves, jid, 'skip scores')
    assert r['error'] == 'stale_state' and steps(lr, jid)[2][1] == 'todo', 'a walk that changed during the model call is not overwritten'
    assert len(lr.edits('walk', jid)) == 1

def test_change_walk_new_idea_that_the_stop_cuts_leaves_no_change(lr):
    jid = mk_walk(lr)
    calls = []
    add = say(dict(op='add', name='Rank metrics', to=1, why='x'))
    def ask(p, sp=''): calls.append(p); return add(p) if len(calls) == 1 else json.dumps(dict(name='Rank metrics', statement='Rank metrics score how good a list of ranks is.', core='', wrong=[]))
    r = at.change_walk(lr, ask, jid, 'add rank metrics', stopping=lambda: len(calls) > 1)
    assert r['status'] == 'stopped' and [s[0] for s in steps(lr, jid)] == ['ranking', 'reciprocal-rank-fusion', 'scores'] and not lr.edits('walk', jid)

def test_hand_changes_use_the_slug_or_the_number_and_keep_an_undo(lr):
    jid = mk_walk(lr)
    k = at.keep_idea(lr, jid, 'ranking')
    assert (k['status'], k['data']['changed']) == ('ok', True) and steps(lr, jid)[0][2]
    assert not at.keep_idea(lr, jid, '1')['data']['changed'], 'a second keep changes nothing'
    m = at.move_idea(lr, jid, '3', 1)
    assert m['data']['ideas'] == ['scores', 'ranking', 'reciprocal-rank-fusion'] and len(lr.edits('walk', jid)) == 2
    d = at.drop_idea(lr, jid, 'ranking', revision=m['revision'])
    assert d['data']['ideas'] == ['scores', 'reciprocal-rank-fusion']
    assert [at.drop_idea(lr, jid, 'zzz')['error'], at.drop_idea(lr, jid, '9')['error'], at.keep_idea(lr, 'nope', '1')['error'], at.move_idea(lr, 'nope', '1', 1)['error']] == ['not_found'] * 4
    assert at.keep_idea(lr, jid, '1', revision='old')['error'] == 'stale_state' and at.drop_idea(lr, jid, '1', revision=m['revision'])['error'] == 'stale_state'
    assert at.move_idea(lr, jid, '1', 7)['error'] == 'model_refused' and at.move_idea(lr, jid, '1', 'x')['error'] == 'model_refused'

def test_versions_list_and_restore(lr):
    jid = mk_walk(lr)
    at.drop_idea(lr, jid, '3'); at.move_idea(lr, jid, '2', 1)
    v = at.list_versions(lr, jid)
    assert v['status'] == 'ok' and [x['version'] for x in v['data']['versions']] == [1, 2] and all(x['restorable'] for x in v['data']['versions']) and json.loads(json.dumps(v)) == v
    r = at.restore_version(lr, jid, 2)
    assert r['status'] == 'ok' and r['data']['ideas'] == ['ranking', 'reciprocal-rank-fusion', 'scores'] and len(at.list_versions(lr, jid)['data']['versions']) == 3
    assert at.restore_version(lr, jid, 9)['error'] == at.restore_version(lr, jid, 0)['error'] == at.list_versions(lr, 'nope')['error'] == 'not_found'
    assert at.restore_version(lr, jid, 1, revision='old')['error'] == 'stale_state' and at.restore_version(lr, 'nope', 1)['error'] == 'not_found'

def test_add_source_files_a_document_and_grounds_the_ideas_that_have_none(lr):
    jid = mk_walk(lr)
    d = lr.vault.add([(0, 'Ranking\n\nA reciprocal rank fusion adds one over rank plus k for each list that ranks the item. It joins ranked lists into one.' * 2)], 'Fusion notes', source='https://example.org/fusion', kind='web')['doc_id']
    r = at.add_source(lr, jid, f'doc:{d}')
    j = lr.journey(jid)
    assert (r['status'], r['data']['changed'], r['data']['documents']) == ('ok', True, 1) and j['chips'] == [f'doc:{d}'] and j['chip_counts'] == {f'doc:{d}': 1}
    assert j.steps[1]['read']['text'].strip() and j.steps[1]['read']['url'] == 'https://example.org/fusion', 'the idea with no passage gets a verbatim one'
    assert j.steps[0]['read']['text'] == QUOTE, 'a passage that a step has stays'
    assert not at.add_source(lr, jid, f'doc:{d}')['data']['changed'] and len(lr.edits('walk', jid)) == 1
    from abhyasa.path import undo_walk
    undo_walk(lr, jid)
    assert not lr.journey(jid).get('chips') and not lr.journey(jid).steps[1].get('read'), 'one Undo takes the source and its passages back'
    assert [at.add_source(lr, jid, 'doc:nope')['error'], at.add_source(lr, jid, ' ')['error'], at.add_source(lr, jid, '/nowhere/x.md')['error']] == ['source_missing'] * 3
    assert at.add_source(lr, 'nope', f'doc:{d}')['error'] == 'not_found' and at.add_source(lr, jid, f'doc:{d}', revision='old')['error'] == 'stale_state'
    assert at._chip('https://a.b/c.') == 'link:https://a.b/c.' and at._chip('gh:a/b') == 'gh:a/b' and at._chip('Notes') == 'vault:Notes'

def test_explain_here_gives_the_data_to_teach_and_calls_no_model(lr):
    jid = mk_walk(lr)
    r = at.explain_here(lr, jid, 0, 'why does\nrank start at 1')
    d = r['data']
    assert (r['status'], r['step'], d['recorded'], d['ungrounded'], d['quote']['url'], d['quote']['text']) == ('ok', 0, True, False, 'https://example.org/notes', QUOTE) and json.loads(json.dumps(r)) == r
    assert d['confusion'] == 'why does rank start at 1' and d['confuses'] == ['Ranking: why does rank start at 1'] and d['level'] and d['simpler'] and d['statement']
    assert 'numbered steps' in d['rules'] and 'answered anything wrong' in d['rules'] and 'explanation' not in d
    u = at.explain_here(lr, jid, 1, 'what is k')
    assert u['data']['ungrounded'] and u['data']['quote'] is None
    import inspect
    assert 'ask' not in inspect.signature(at.explain_here).parameters
    assert 'explain_here' in dict(at.TOOLS) and list(dict(at.TOOLS)['explain_here']) == ['note'] and 'explain_here' not in at.READS

def test_explain_here_failures_keep_nothing(lr):
    jid = mk_walk(lr)
    assert [at.explain_here(lr, 'nope', 0, 'q')['error'], at.explain_here(lr, jid, 9, 'q')['error']] == ['not_found'] * 2
    assert at.explain_here(lr, jid, 0, 'q', revision='old')['error'] == 'stale_state'
    assert at.explain_here(lr, jid, 0, ' ')['error'] == 'model_refused' and not lr.profile().confuses

def test_the_page_gives_the_walk_and_step_on_screen(lr):
    jid = mk_walk(lr)
    kinds = [at.page_of(p)['kind'] for p in ('/w/a/2?pane=1', '/w/a', '/w/a/gather', '/c/x', '/you', '/you/strengths', '/graph', '/library/graph', '/library', '/concepts', '/t/9', '/talk/new', '/talks', '/', '', '/zzz')]
    assert kinds == ['step', 'walk', 'walk', 'concept', 'you', 'you', 'graph', 'graph', 'library', 'library', 'talk', 'talk', 'talk', 'today', '', 'other']
    assert at.page_of('/learn/abh/w/a%20b/2') == dict(kind='step', jid='a b', i=2, slug=None)
    c1 = at.learner_context(lr, None, page=f'/w/{jid}/1?x=1')
    assert 'Step 2 of 3' in c1 and 'This step is ungrounded' in c1 and 'explain_here' in c1 and at.RULE in c1 and len(c1) <= 1200
    c0 = at.learner_context(lr, jid, 2, page=f'/w/{jid}/0')
    assert QUOTE in c0 and 'Step 1 of 3' in c0, 'the page wins over the step that the host passes'
    assert 'this walk' in at.learner_context(lr, page=f'/w/{jid}') and 'Step 1 of 3' in at.learner_context(lr, page=f'/w/{jid}')
    assert 'the graph page' in at.learner_context(lr, page='/graph') and at.RULE in at.learner_context(lr, page='/graph')
    assert 'the concept Ranking' in at.learner_context(lr, page='/c/ranking') or 'the concept page' in at.learner_context(lr, page='/c/ranking')
    assert at.learner_context(lr, page='/w/zz/0').endswith(at.RULE) and at.learner_context(lr) == at.learner_context(lr, page='')
    assert len(at.learner_context(lr, jid, page=f'/w/{jid}/0', n=300)) <= 301
