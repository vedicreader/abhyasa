"The background jobs in one place: a stored row for each job, the activity chip in the top bar, the event stream, and the state for the Mac app."
import json, re, threading, time
from fastcore.utils import L
from abhyasa.jobs import job_start, job_end
from walk_data import PAGES, wait_for

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
    from abhyasa.course import join_course
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
