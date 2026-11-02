"The background jobs in one place: a stored row for each job, the activity chip in the top bar, the event stream, and the state for the Mac app."
import json, re, threading, time
from fastcore.utils import L
from abhyasa.learner import job_start, job_end
from walk_data import PAGES, wait_for, walk

def chip(h):
    "The activity chip of a page, as its HTML."
    return re.search(r'<details[^>]*id="activity".*?</details>', h, re.S)[0]

def lines(r):
    "The data lines and the event names of an event stream, in order."
    return [l for l in r.iter_lines() if l.startswith(('data:', 'event:')) and l != 'data: {}']   # the empty data line of `end`

# The chip shows only while a job runs or a result is new.

def test_no_job_no_chip(mk):
    "With no job, the top bar has an empty chip: no part, no words, no stream."
    c = chip(mk().get('/').text)
    assert 'data-part' not in c and '<summary' not in c and 'data-stream' not in c

def test_a_restart_closes_a_running_job(mk, lr):
    "A job that ran when abhyasa closed is closed at the next start, and the chip says so. Clear takes it away."
    job_start(lr, 'build:x', 'build', title='Diffusion for comics', said='Planning the walk')
    cl = mk()   # a new start of the app
    assert lr.job('build:x').state == 'closed'
    c = chip(cl.get('/library').text)
    assert 'Stopped: Diffusion for comics' in c and 'It stopped because abhyasa closed.' in c and 'data-stream' not in c
    assert 'Stopped' not in str(cl.post('/activity/seen').text) and lr.job('build:x').seen

def test_a_failed_job_says_why(mk, lr):
    "A failed job shows its reason in the list of the chip."
    cl = mk()
    job_start(lr, 'build:y', 'build', title='A walk from a link'); job_end(lr, 'build:y', 'failed', why='abhyasa could not read this link.')
    c = chip(cl.get('/').text)
    assert 'Failed: A walk from a link' in c and 'abhyasa could not read this link.' in c

# The stream sends one event when a job changes, and ends when no job runs.

def test_the_stream_tells_the_end_of_a_job(mk, lr):
    "While a job runs the stream stays open; its end comes as one event with its key and object, then `end`."
    cl = mk()
    job_start(lr, 'walk:w1:research', 'research', title='W', obj='walk:w1')
    threading.Timer(.3, lambda: job_end(lr, 'walk:w1:research')).start()
    with cl.stream('GET', '/events') as r:
        assert r.headers['content-type'].startswith('text/event-stream')
        got = lines(r)
    assert json.loads(got[0][5:]) == dict(key='walk:w1:research', obj='walk:w1', state='done') and got[-1] == 'event: end'

def test_with_no_job_the_stream_ends_at_once(mk, lr):
    "With no job, the stream says `end` at once, so a page keeps no connection. A change after the page was drawn sends one event for every part."
    cl = mk()
    with cl.stream('GET', '/events') as r: assert lines(r) == ['event: end']
    job_start(lr, 'k', 'build'); job_end(lr, 'k')   # a change after the page was drawn
    with cl.stream('GET', '/events', params=dict(v=0)) as r: got = lines(r)
    assert json.loads(got[0][5:])['obj'] == '*' and got[-1] == 'event: end'

# Each kind of job writes its row: a walk from a link, a source that files, a course job.

def test_a_walk_from_a_link_has_a_row(mk, walk_fake, lr, monkeypatch):
    "The card of a walk from a link waits on the stream; its row runs, then links to the walk when it is ready."
    from vishalakshi.core import Vault
    monkeypatch.setattr(Vault, 'crawl', lambda self, start_url, max_pages=10, sel=None, **kw: L([self.add(PAGES, 'Attention docs', source=start_url, kind='web', meta=dict(url=start_url))]))
    monkeypatch.setattr('abhyasa.sources._final', lambda u: u)
    monkeypatch.setattr('socket.getaddrinfo', lambda host, port, *a, **k: [(2, 1, 6, '', ('93.184.216.34', port or 0))])
    cl = mk(); u = 'https://docs.example.dev/attention/'
    r = cl.post('/walk/new', data=dict(url=u, pages=3)).text
    assert 'hx-trigger="job, every 30s"' in r and 'data-job="build:' in r and 'load delay' not in r
    key = re.search(r'data-job="(build:[^"]+)"', r)[1]
    jid = wait_for(lambda: (cl.get('/walk/job', params=dict(url=u)).headers.get('hx-redirect') or '').split('/')[-1] or None, secs=10)
    row = wait_for(lambda: (x := lr.job(key)) and x.state == 'done' and x or None)
    assert (row.url, row.obj, row.title) == (f'/w/{jid}', f'walk:{jid}', lr.journey(jid).title)
    assert f'Ready: {row.title}' in chip(cl.get('/').text)
    cl.get(f'/w/{jid}')   # opening the walk is seeing it
    assert 'Ready' not in chip(cl.get('/').text)

def test_a_source_that_files_has_a_row(mk, lr, monkeypatch):
    "Add a source on a walk: one row runs while it files, and its line on the walk page waits on the stream of the walk."
    lr.put_journey(dict(id='w2', title='Ranks', mode='walk', steps=[dict(slug='ranking', status='todo')]))
    cl = mk(); svc = cl.app.state.svc
    gate = threading.Event()
    monkeypatch.setattr('abhyasa.blocks.walk.app.file_folder', lambda lr_, v: (gate.wait(5), L())[1])
    from abhyasa.core.hooks import run
    assert run('walk_add_sources', 'w2', ['folder:/tmp/notes']) == [['folder:/tmp/notes']]
    assert lr.job('walk:w2:filing').state == 'running' and '1 running' in chip(cl.get('/').text)
    gate.set()
    assert wait_for(lambda: lr.job('walk:w2:filing').state == 'done' or None)

def test_a_course_job_has_a_row(mk, lr, fake):
    "Where you start: the job of its questions has a row on the course, and its part waits on the stream of the course."
    from test_course import goal_walk
    from abhyasa.path import join_course
    goal_walk(lr); c = join_course(lr, 'gw')
    gate = threading.Event()
    fake.rules['You find out what one learner knows'] = lambda p, sp: (gate.wait(5), dict(qs=[]))[1]
    cl = mk()
    r = cl.post(f'/course/{c.id}/level').text
    assert f'data-job="course:{c.id}"' in r and 'load delay' not in r
    assert lr.job(f'course:{c.id}:level').state == 'running' and f'{c.title}: Where you start' in chip(cl.get('/').text)
    gate.set()
    assert wait_for(lambda: lr.job(f'course:{c.id}:level').state in ('done', 'failed') or None)
    cl.get(f'/course/{c.id}')
    assert lr.job(f'course:{c.id}:level').seen

def test_the_research_notice_is_gone(mk, lr):
    "No page has the old research notice: the chip is the one way to be told."
    job_start(lr, 'walk:w3:research', 'research', title='Old', obj='walk:w3'); job_end(lr, 'walk:w3:research')
    h = mk().get('/').text
    assert 'research-notice' not in h and 'Sources for your walk' not in h

# Each job that once polled on its own has a row, and its part loads again on the event of the row.

def events_until(cl, go):
    "The events of the stream while one job ends: `go()` lets it end, 0.3 s after the stream opens. Each event as a dict."
    threading.Timer(.3, go).start()
    with cl.stream('GET', '/events') as r: return [json.loads(l[5:]) for l in lines(r) if l.startswith('data:')]

def hx_get(h): return re.search(r'hx-get="([^"]+)"', h)[1].replace('&amp;', '&')

def test_a_demo_has_a_row_and_its_card_swaps_on_the_event(mk, walk_fake, lr):
    "Show me: the card waits on the row of its demo job; the row says the real stage; the end comes as an event, and the card then has the demo."
    from abhyasa.show import STAGES
    from rupaka.spec import gallery
    gate, n = threading.Event(), []
    def rule(p, sp):   # the first try fails the checks; the second waits for the test
        n.append(1)
        if len(n) == 1: return 'no JSON here'
        gate.wait(5); return {**gallery()['reciprocal-rank-fusion'], 'id': 'ranking'}
    walk_fake.rules['You design one interactive demo'] = rule
    cl = mk()
    r = cl.post('/demo/ask', data=dict(concept='ranking', where='concept')).text
    assert 'data-job="demo:ranking"' in r and 'hx-trigger="job, every 30s"' in r and 'load delay' not in r
    assert wait_for(lambda: lr.job('demo:ranking').said == STAGES['fixing'] or None)   # a try failed the checks: the row says so
    assert STAGES['fixing'] in cl.get(hx_get(r)).text and 'Demo: Ranking' in chip(cl.get('/').text)   # the card and the chip show it
    got = events_until(cl, gate.set)
    assert dict(key='demo:ranking', obj='demo:ranking', state='done') in got
    card = cl.get(hx_get(r)).text
    assert 'data-rupaka' in card and 'pending' not in card and lr.job('demo:ranking').seen   # the demo is on the page: not news in the chip

def test_the_demo_of_a_step_has_a_quiet_row(mk, walk_fake, lr):
    "The demo check of a walk step waits on the row of its demo job. The row is quiet: the page shows the wait, so the chip does not."
    from test_walk import held
    slug = 'scaling-by-the-root-of-dk'
    gate = held(walk_fake, 'You design one interactive demo', '')
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 2, check=dict(way='demo', kind='demo', depth=2, why=''))
    r = cl.get(f'/w/{jid}/2/check').text
    assert f'data-job="demo:{slug}"' in r and 'making the demo' in r and 'load delay' not in r
    assert lr.job(f'demo:{slug}').state == 'running' and lr.job(f'demo:{slug}').quiet and 'running' not in chip(cl.get('/').text)
    assert any(e['key'] == f'demo:{slug}' and e['state'] == 'done' for e in events_until(cl, gate.set))
    assert 'walk-demo' in cl.get(f'/w/{jid}/2/check').text

def test_improve_has_a_row_and_its_line_swaps_on_the_event(mk, walk_fake, lr):
    "Improve the walk: the line waits on its row; the chip lists it; the end comes as an event, and the proposal shows."
    from test_walk import held
    walk_fake.rules['You propose changes to one learning walk'] = dict(changes=[dict(op='easier', idea='softmax', why='The check asks less.')])
    gate = held(walk_fake, 'You propose changes to one learning walk', '')
    cl = mk(); jid = walk(cl, lr)
    r = cl.post(f'/w/{jid}/improve', data=dict(words='Make the walk simpler.')).text
    key = re.search(r'data-job="(improve:[^"]+)"', r)[1]
    row = lr.job(key)
    assert (row.kind, row.state, row.url, row.quiet) == ('improve', 'running', f'/w/{jid}#improve', False) and f'Improve: {lr.journey(jid).title}' in chip(cl.get('/').text)
    assert any(e['key'] == key and e['state'] == 'done' for e in events_until(cl, gate.set))
    assert 'Apply the kept changes' in cl.get(hx_get(r)).text

def test_a_talk_has_a_row_and_its_card_swaps_on_the_event(mk, talk_fake, lr, monkeypatch):
    "Present: the card waits on the row of the talk job; the end comes as an event, and the row links to the talk. Opening the talk is seeing it."
    import abhyasa.blocks.talk.app as T
    gate, real = threading.Event(), T.talk_from_walk
    monkeypatch.setattr(T, 'talk_from_walk', lambda *a, **kw: (gate.wait(5), real(*a, **kw))[1])
    cl = mk(); jid = walk(cl, lr)
    r = cl.post('/talk/new', data=dict(jid=jid)).text
    assert f'data-job="talk:{jid}"' in r and 'hx-trigger="job, every 30s"' in r and 'load delay' not in r
    assert lr.job(f'talk:{jid}').state == 'running' and 'Talk: ' in chip(cl.get('/').text)
    assert any(e['key'] == f'talk:{jid}' and e['state'] == 'done' for e in events_until(cl, gate.set))
    loc = cl.get(hx_get(r)).headers['hx-redirect']
    assert wait_for(lambda: lr.job(f'talk:{jid}').url == loc or None)
    cl.get(loc); assert lr.job(f'talk:{jid}').seen

def test_a_sort_has_a_row_and_its_card_swaps_on_the_event(mk, lr, fake):
    "Sort my concepts: the card waits on the row of the sort; the end comes as an event, and the card has the new tree. Cancel stops the row."
    from test_concept_tree import sorter, SORT, sort_id
    gate = threading.Event()
    fake.rules[SORT] = sorter(gate)
    lr.put('Mesha', 'The first rasi.', 'jyotisha')
    cl = mk()
    r = cl.post('/concepts/sort').text
    key = f'sort:{sort_id(r)}'
    assert f'data-job="{key}"' in r and 'load delay' not in r and lr.job(key).state == 'running' and 'Sort: your concepts' in chip(cl.get('/').text)
    assert any(e['key'] == key and e['state'] == 'done' for e in events_until(cl, gate.set))
    t = cl.get('/concepts/sort').text
    assert 'Accept this tree' in t and lr.job(key).said == 'The new tree is ready. Accept it or cancel.'
    cl.post('/concepts/sort/cancel', data=dict(sort=sort_id(r)))
    assert (lr.job(key).state, lr.job(key).seen) == ('stopped', True)

def test_a_download_has_a_row_and_its_lines_swap_on_the_event(mk, lr, monkeypatch):
    "Download a model in Settings: the progress lines wait on its row, which says the bytes so far; the end comes as an event."
    from abhyasa import models as voice
    m, gate, got = 'mlx-community/whisper-tiny-asr-fp16', threading.Event(), []
    monkeypatch.setattr(voice, 'cached', lambda model: model in got)
    monkeypatch.setattr(voice, 'model_size', lambda model: 2**20)
    monkeypatch.setattr(voice, 'fetch', lambda model: (gate.wait(5), got.append(model)))
    cl = mk(['voice', 'settings', 'jobs'])
    r = cl.post('/settings/get', data=dict(engine='mlx', model=m)).text
    assert f'data-job="download:{m}"' in r and 'every 1s' not in re.search(r'<div[^>]*id="jobs"[^>]*>', r)[0]
    row = wait_for(lambda: (x := lr.job(f'download:{m}')) and x.said.startswith('Downloading') and x or None)
    assert (row.kind, row.state, row.url) == ('download', 'running', '/settings#g-stt') and f'Download: {m}' in chip(cl.get('/settings').text)
    assert any(e['key'] == f'download:{m}' and e['state'] == 'done' for e in events_until(cl, gate.set))
    assert 'ready and in use' in cl.get('/settings/jobs').text and lr.job(f'download:{m}').seen


# A vault from abhyasa 0.0.15 keeps its job rows in one document. The app moves them to the ledger at its first read.

def test_an_old_jobs_document_moves_to_the_ledger(mk, lr):
    "The rows of the old document show in the chip and in `/jobs.json`, with the same shape. A row that ran is closed. A bad row is left out."
    import time
    from abhyasa.learner import OLD
    now = time.time()
    rows = {'walk:w8:research': dict(kind='research', state='running', title='Old walk', said='Looking for sources', start=now - 60, url='/w/w8', obj='walk:w8'),
            'build:b8': dict(kind='build', state='done', title='Old link', said='Ready.', start=now - 90, end=now - 30, url='/w/w9', seen=False),
            'odd': ['not', 'a', 'row']}
    lr.v.add('The background jobs of abhyasa.', title='abhyasa jobs', source=OLD, kind='jobs', meta=dict(rows=rows))
    cl = mk()
    assert lr.v.by_source(OLD) is None and lr.job('odd') is None
    j = cl.get('/jobs.json').json()
    assert j['running'] == [] and [r['key'] for r in j['ended']] == ['walk:w8:research', 'build:b8']
    assert j['ended'][1] == dict(key='build:b8', kind='build', state='done', title='Old link', said='Ready.', why='', start=now - 90, end=now - 30, url='/w/w9', seen=False)
    assert 'Stopped: Old walk and 1 more' in chip(cl.get('/').text)
    with cl.stream('GET', '/events') as r: assert lines(r) == ['event: end']   # no job runs

def test_a_demo_try_that_fails_its_checks_says_why(mk, walk_fake, lr, caplog):
    "A try that fails the checks: the card has a calm line and a Why fold, the log has the errors at INFO, and the row keeps them. A good first try is one call."
    import logging
    from abhyasa.show import STAGES, queue_demo
    from rupaka.spec import gallery
    good = {**gallery()['reciprocal-rank-fusion'], 'id': 'ranking'}
    gate, n = threading.Event(), []
    def rule(p, sp):
        n.append(1)
        if len(n) == 1: return {'blocks': 'not a list'}
        gate.wait(5); return good
    walk_fake.rules['You design one interactive demo'] = rule
    cl = mk()
    with caplog.at_level(logging.INFO, logger='abhyasa.show'):
        r = cl.post('/demo/ask', data=dict(concept='ranking', where='concept')).text
        assert wait_for(lambda: lr.job('demo:ranking').said == STAGES['fixing'] or None)
        card = cl.get(hx_get(r)).text
        assert 'did not pass its checks. The tutor writes it again.' in card and 'class="on fixing"' in card and '<summary>Why</summary>' in card and 'Try 1 did not pass: ' in card
        assert lr.job('demo:ranking').tries[0]['errors'] and any('demo demo:ranking: try 1 did not pass its checks' in m for m in caplog.messages)
        gate.set(); assert wait_for(lambda: lr.job('demo:ranking').state == 'done' or None)
    assert (len(n), lr.job('demo:ranking').said) == (2, 'The demo is ready.')   # one repair: two tries in all
    n.clear(); walk_fake.rules['You design one interactive demo'] = lambda p, sp: (n.append(1), {**good, 'id': 'reciprocal-rank-fusion'})[1]
    cl.post('/demo/ask', data=dict(concept='reciprocal-rank-fusion', where='concept'))
    assert wait_for(lambda: lr.job('demo:reciprocal-rank-fusion').state == 'done' or None)
    assert (len(n), lr.job('demo:reciprocal-rank-fusion').tries) == (1, [])   # a good first try: one call, and no tries kept
