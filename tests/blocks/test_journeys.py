"Old paths become walks at the start, with their progress; old links go to the walk page; a concept page lists its walks; a session of a walk says when an idea is done."
import re, time
from abhyasa.journey import plan as plan_path, walk_state
from walk_data import wait_for

PLAN = dict(title='How LLMs work', subject='ml', steps=[
    dict(name='Tokenizers', statement='A tokenizer cuts text into tokens.', slug='', why='The model reads tokens.', needs=[]),
    dict(name='Ranking', statement='', slug='ranking', why='You rank the next token.', needs=['Tokenizers']),
    dict(name='Attention', statement='Weights from query-key dot products.', slug='', why='The core of a transformer.', needs=['Ranking'])])

def old_path(lr, fake):
    "A path as abhyasa made it before 0.0.16: a goal and its steps, with no `mode`. Its second step is marked known."
    fake.rules['You plan a learning path'] = PLAN
    j = plan_path(lr, fake, 'I want to learn how LLMs work')
    lr.merge_journey(j.id, steps=[{**s, 'status': 'known'} if s['slug'] == 'ranking' else s for s in j.steps])
    return j.id

def migrated(lr):
    "The job row of the migration of the old paths, once it ended; else None."
    r = lr.job('walk:paths')
    return r if r and r.state != 'running' else None

def test_an_old_path_becomes_a_walk_at_the_start(mk, fake, lr):
    """At the start the app makes the old path a walk with the same id, on the pool, with a job row: each step has a check, the known step
    stays known, and the row on Home counts it. No step was searched: the passage of a step comes when its idea opens."""
    jid = old_path(lr, fake); cl = mk()
    assert wait_for(lambda: migrated(lr)).state == 'done'
    j = lr.journey(jid)
    assert j.mode == 'walk' and [s['slug'] for s in j.steps] == ['tokenizers', 'ranking', 'attention'] and all(s['check'] for s in j.steps)
    assert j.steps[1]['status'] == 'known' and not j.steps[1].get('read') and j.steps[1]['read_later']
    home = cl.get('/').text
    assert 'How LLMs work' in home and '1 of 3 ideas' in home and 'Now: Tokenizers' in home and f'href="/w/{jid}"' in home
    note = cl.get(f'/w/{jid}/1/note').text   # the idea opens: its passage comes from your sources, and swaps in
    assert lr.journey(jid).steps[1]['read']['title'] == 'My ranking notes' and not lr.journey(jid).steps[1]['read_later']
    assert 'id="passage"' in note and 'hx-swap-oob="true"' in note and 'Ranking orders items by score.' in note

def test_home_does_not_run_the_migration(mk, fake, lr):
    "Home answers with no migration in the request: a path that came after the start stays a path. Its old link makes it a walk at once."
    cl = mk(); jid = old_path(lr, fake)
    assert cl.get('/').status_code == 200 and lr.journey(jid).get('mode') is None and lr.job('walk:paths') is None
    assert cl.get(f'/path/{jid}', follow_redirects=False).status_code == 301 and lr.journey(jid).mode == 'walk'

def test_an_old_path_keeps_its_progress(mk, fake, lr):
    """An old path with two sessions keeps its progress: a step with a pass is done, a step with a fragile answer is shaky, the newest open
    session is the sitting with its open question, and `started` and `here` come from the sessions. So a newer walk stays Continue."""
    from abhyasa.tutor import Tutor, public
    from abhyasa.journey import last_place
    for n in ('Softmax', 'Tokens'): lr.put(n, f'{n} is one idea.', 'ml')
    steps = [dict(slug=s, status='todo') for s in ('ranking', 'reciprocal-rank-fusion', 'softmax', 'tokens')]
    lr.put_journey(dict(id='old-p', title='Old path', goal='Learn ranking', subject='ml', created=500., steps=steps))
    row = lambda slug, o, at: dict(concept=slug, outcome=o, correct=o == 'solid', question=f'Q on {slug}', at=at)
    lr.log_session('s1', 'The first session.', journey='old-p', start=1000., updated=1100., ended=1100.,
                   log=[row('ranking', 'gap', 1010.), row('ranking', 'solid', 1050.)])
    q = Tutor(lr, fake).ask_on(lr.concept('softmax'), 2, 'the next idea', session='s2')
    lr.log_session('s2', 'The second session.', journey='old-p', start=2000., updated=2100.,
                   log=[row('reciprocal-rank-fusion', 'fragile', 2050.)], open=dict(public(q)))
    lr.put_journey(dict(id='newer', title='Newer walk', mode='walk', started=time.time() - 60, created=time.time() - 60,
                        steps=[dict(slug='tokens', status='todo', check=dict(way='words', kind='short', depth=2))]))
    cl = mk(); wait_for(lambda: migrated(lr))
    j = lr.journey('old-p')
    st = walk_state(j)
    assert [s.dot for s in st.steps] == ['done', 'shaky', 'now', 'todo'] and (st.done, st.total) == (1, 4)
    assert (j.sitting, j.started, j.here, j.steps[2]['qid']) == ('s2', 1000., dict(step=2, at=2100.), q.id)
    assert last_place(lr).walk == 'newer'   # the old path does not jump to Continue
    page = cl.get('/w/old-p').text
    assert 'Continue: idea 3 of 4' in page and 'aria-valuenow="1" aria-valuemax="4"' in cl.get('/w/old-p/2').text
    assert 'What does a rank tell you?' in cl.get('/w/old-p/2/check').text   # the open question, not a new one

def test_old_path_links_go_to_the_walk_page(mk, fake, lr):
    "An old link to a path makes it a walk and opens the walk page, with the same query. The path routes that changed a path are gone."
    cl = mk(); jid = old_path(lr, fake)
    r = cl.get(f'/j/{jid}?from=leela', follow_redirects=False)
    assert r.status_code == 301 and r.headers['location'] == f'/w/{jid}?from=leela' and lr.journey(jid).mode == 'walk'
    assert cl.get(f'/path/{jid}', follow_redirects=False).headers['location'] == f'/w/{jid}'
    for u in (f'/path/{jid}/step', f'/j/{jid}/drop', f'/path/{jid}/sources', '/journeys/new', '/talk/journey'):
        assert cl.post(u).status_code in (404, 405), u

def test_concept_page_lists_its_walks(mk, fake, lr):
    "A concept page names each walk that has the idea, with a link to the idea, and adds the idea to another walk."
    cl = mk(); jid = old_path(lr, fake); cl.get(f'/path/{jid}')
    c = cl.get('/c/ranking').text
    assert 'In your walks' in c and 'idea 2 of 3' in c and f'href="/w/{jid}/1"' in c
    lr.put_journey(dict(id='w2', title='Second walk', mode='walk', steps=[dict(slug='tokenizers', status='todo', check=dict(way='words', kind='short', depth=2))]))
    r = cl.post('/walk/attach', data=dict(jid='w2', slug='ranking')).text
    assert 'Added to' in r and 'href="/w/w2/1"' in r and lr.journey('w2').steps[1]['check']['kind']

def test_step_done_in_the_thread(mk, fake, lr):
    "In a session of a walk, the close that makes an idea learned says so, and names the next idea."
    cl = mk(); jid = old_path(lr, fake); cl.get(f'/path/{jid}')
    lr.update('tokenizers', floor=3, ceiling=6, seen=1)
    sid = cl.get(f'/start?journey={jid}', follow_redirects=False).headers['location'].split('/')[-1]
    page = cl.get(f'/s/{sid}').text
    assert 'Tokenizers' in page and f'href="/w/{jid}"' in page   # the session names its walk
    fake.rules['You grade one answer'] = dict(correct=True, grade=9, first_error='', misconception='', feedback='Yes.')
    r = cl.post(f'/s/{sid}/answer', data=dict(answer='tokens', confidence=90)).text
    assert 'Idea done' in r and 'Next in the walk: Attention' in r

def test_home_counts_a_walk_as_its_outline_does(mk, lr):
    "An idea that a check closed as fragile counts the same in the outline and on Home: both use `walk_state`."
    ck = dict(way='words', kind='short', depth=2)
    lr.put_journey(dict(id='wf', title='Fragile walk', mode='walk', goal='learn ranking', started=1.,
                        steps=[dict(slug='ranking', status='todo', check=ck, done=dict(outcome='fragile', at=1.)), dict(slug='reciprocal-rank-fusion', status='todo', check=ck)]))
    cl = mk()
    row, rail = cl.get('/').text, cl.get('/w/wf/1').text
    assert 'Now: Reciprocal rank fusion' in row   # a fragile idea is not the current one: the walk goes on
    n = re.search(r'aria-valuenow="(\d)"', rail)[1]
    assert f'aria-valuenow="{n}" aria-valuemax="2"' in row and f'{n} of 2 ideas' in row   # one count: the row says what the outline says
