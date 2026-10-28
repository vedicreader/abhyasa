from walk_data import *
from fastcore.utils import first
from pathlib import Path
import abhyasa.blocks.walk
import pytest

def made(cl, key): return cl.app.state.svc['tutor'].jobs[key].result(timeout=30)   # wait on the demo job, not on the clock
from abhyasa.method import TEXT_WAYS

def test_plan_then_start(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr)
    page = cl.get(f'/w/{jid}').text
    assert 'Attention Is All You Need' in page and page.index('1 Introduction') < page.index('3.2.1 Scaled Dot-Product Attention')
    assert 'Start the walk' in page and 'min' in page
    cl.post(f'/w/{jid}/plan', data=dict(i=1, act='check', way='code'))
    assert lr.journey(jid).steps[1]['check'] == dict(way='code', kind='code', depth=4, why='you chose it')
    assert cl.post(f'/w/{jid}/plan', data=dict(i=1, act='check', way='board')).status_code == 400   # no board view yet
    cl.post(f'/w/{jid}/plan', data=dict(i=0, act='drop'))
    assert [s['slug'] for s in lr.journey(jid).steps][0] == 'softmax'
    r = cl.post(f'/w/{jid}/start', follow_redirects=False)
    assert r.headers['location'] == f'/w/{jid}/0' and lr.journey(jid).started and lr.journey(jid).sitting

def test_plan_says_how_many_more_ideas(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr)
    assert 'more idea' not in cl.get(f'/w/{jid}').text                                  # all the ideas are steps
    lr.put_journey({**lr.journey(jid), 'more': ['a', 'b']})
    assert 'The source has 2 more ideas.' in cl.get(f'/w/{jid}').text

def test_step_page_and_short_check(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why='plain words fit'))
    page = cl.get(f'/w/{jid}/1').text
    assert 'apply a softmax function' in page and f'src="/w/{jid}/1/img"' in page and f'hx-get="/w/{jid}/1/note"' in page
    assert 'Skip this idea' in page and '⌥F' not in page                             # a quiet skip while the check is open; ⌥F stays the shortcuts panel
    assert 'KeyF' not in (Path(abhyasa.blocks.walk.__file__).parent/'walk.js').read_text()
    assert 'Softmax makes weights' not in page and 'Softmax makes weights' in cl.get(f'/w/{jid}/1/note').text   # the note loads after the page
    assert lr.journey(jid).steps[1]['read_at']
    card = cl.get(f'/w/{jid}/1/check').text
    assert 'What does a rank tell you?' in card and 'Its position.' not in card and 'rubric' not in card   # no answer in the HTML
    r = cl.post(f'/w/{jid}/1/answer', data=dict(answer='the rank is a position', confidence=70)).text
    assert 'Next idea' in r and '⌥S' in r and '⌥F' not in r and lr.attempts('softmax', limit=1)[0].walk == jid
    assert cl.get(f'/w/{jid}/1/img').headers['content-type'] == 'image/png'

def test_next_skips_and_moves_on(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    r = cl.post(f'/w/{jid}/0/next', follow_redirects=False)
    assert lr.journey(jid).steps[0]['done']['outcome'] == 'skipped' and not lr.attempts('sequential-computation')
    assert r.headers['location'] == f'/w/{jid}/0/done'                             # step 1 is in a new section
    assert 'Section done' in cl.get(f'/w/{jid}/0/done').text and f'href="/w/{jid}/1"' in cl.get(f'/w/{jid}/0/done').text
    assert cl.post(f'/w/{jid}/1/next', follow_redirects=False).headers['location'] == f'/w/{jid}/2'   # same section: the next step

def test_reload_keeps_one_question_and_next_is_idempotent(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    a, b = cl.get(f'/w/{jid}/1/check').text, cl.get(f'/w/{jid}/1/check').text
    assert lr.journey(jid).steps[1]['qid'] and a.count('What does a rank') == b.count('What does a rank') == 1
    n = len([c for c in walk_fake.calls if 'Write ONE question' in c[0]])
    assert n == 1                                                                  # the reload made no second question
    cl.post(f'/w/{jid}/1/next'); cl.post(f'/w/{jid}/1/next')
    assert lr.journey(jid).steps[2]['done'] is None                                # a double press moves one step only

def test_step_without_passage_or_figure(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 2, read={**lr.journey(jid).steps[2]['read'], 'text': '', 'figure': None})
    page = cl.get(f'/w/{jid}/2').text
    assert "In the tutor's words" in page and '<img' not in page
    assert cl.get(f'/w/{jid}/2/img').status_code == 404

def test_image_route_stays_in_assets(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr)
    lr.walk_step(jid, 1, read={**lr.journey(jid).steps[1]['read'], 'figure': '../../vault.db'})
    assert cl.get(f'/w/{jid}/1/img').status_code == 404

def test_miss_hint_and_dont_know(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    cl.get(f'/w/{jid}/1/check')
    r = cl.post(f'/w/{jid}/1/answer', data=dict(answer='a sum of scores')).text
    assert 'Not yet' in r and 'You add raw scores.' in r and '2 tries left' in r                   # a miss keeps the check open
    assert 'Think about positions.' in cl.post(f'/w/{jid}/1/hint').text
    r = cl.post(f'/w/{jid}/1/giveup').text
    assert 'Next idea' in r and 'Positions are shared.' in r                                       # Teach me closes with a lesson
    assert lr.journey(jid).steps[1]['done']['outcome'] in ('gap', 'misconception') and lr.journey(jid).steps[1]['done']['aid']
    assert 'Next idea' in cl.post(f'/w/{jid}/1/answer', data=dict(answer='late')).text               # a closed check takes no more answers

def test_code_check_falls_back_to_a_text_way(mk, walk_fake, lr):
    walk_fake.rules['You write one small Python exercise'] = 'no exercise today'                 # the tutor could not make a code task
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why=''))
    assert 'What does a rank tell you?' in cl.get(f'/w/{jid}/1/check').text                      # a short card when the code task fails
    cl.post(f'/w/{jid}/1/answer', data=dict(answer='the rank'))
    assert lr.attempts('softmax', limit=1)[0].method in TEXT_WAYS                                  # the record and the credit name a text way
    assert lr.journey(jid).steps[1]['check']['kind'] == 'code'                                     # the plan keeps its check

def test_demo_check_is_made_ahead_and_logged(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 2, check=dict(way='demo', kind='demo', depth=2, why='a demo fits'))
    cl.get(f'/w/{jid}/1')                                                          # opening step 1 makes the demo of step 2
    d = made(cl, 'scaling-by-the-root-of-dk')
    assert d is not None and d.checked is None                                     # no browser check in the tests
    card = cl.get(f'/w/{jid}/2/check').text
    assert 'walk-demo' in card and 'demo-card' not in card and f'/w/{jid}/2/predict' in card
    g = first(b['id'] for b in d.spec['blocks'] if b.get('type') == 'gate')
    r = cl.post(f'/w/{jid}/2/predict', data=dict(slug=d.slug, gate=g, picked='1', ans='1', ok='true', why='bigger dot products')).json()
    assert r['ok'] and r['dot'] in ('done', 'shaky') and (r['done'], r['total']) == (1, 3)   # walk.js fills the dot and moves the progress line
    a = lr.attempts('scaling-by-the-root-of-dk', limit=1)[0]
    assert (a.kind, a.method, a.walk, a.step, a.depth) == ('demo', 'demo', jid, 2, 3)
    assert lr.journey(jid).steps[2]['done']['outcome'] in ('solid', 'fragile')
    cl.post(f'/w/{jid}/2/keep', data=dict(state='{"dk": 256, "scale": false}'))
    assert lr.attempts('scaling-by-the-root-of-dk', limit=1)[0].keep == {'dk': 256, 'scale': False}

def test_order_check_logs_order(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='order', kind='order', depth=2, why=''))
    cl.get(f'/w/{jid}/0')
    d = made(cl, 'softmax:order'); g = first(b['id'] for b in d.spec['blocks'] if b.get('type') == 'gate')
    cl.post(f'/w/{jid}/1/predict', data=dict(slug=d.slug, gate=g, picked='0', ans='1', ok='false'))
    assert lr.attempts('softmax', limit=1)[0].kind == 'order'

def test_demo_failure_falls_back_to_short_answer(mk, walk_fake, lr):
    walk_fake.rules['You design one interactive demo'] = '{}'                     # every author try fails the checks
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 2, check=dict(way='demo', kind='demo', depth=2, why=''))
    cl.get(f'/w/{jid}/1')
    assert made(cl, 'scaling-by-the-root-of-dk') is None
    card = cl.get(f'/w/{jid}/2/check').text
    assert 'What does a rank tell you?' in card and lr.journey(jid).steps[2]['check']['kind'] == 'short'
    assert cl.post(f'/w/{jid}/2/next').status_code in (200, 303)

def test_demo_routes_refuse_bad_input(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 2, check=dict(way='demo', kind='demo', depth=2, why=''))
    cl.get(f'/w/{jid}/1')
    d = made(cl, 'scaling-by-the-root-of-dk')
    other = lr.put_demo({**d.spec, 'id': 'another'}, 'softmax')
    assert cl.post(f'/w/{jid}/2/predict', data=dict(slug=other.slug, gate='g', picked='1', ans='1')).status_code == 404   # a demo of another idea
    assert cl.post(f'/w/{jid}/2/keep', data=dict(state='{}')).status_code == 409                                   # no prediction yet
    g = first(b['id'] for b in d.spec['blocks'] if b.get('type') == 'gate')
    cl.post(f'/w/{jid}/2/predict', data=dict(slug=d.slug, gate=g, picked='1', ans='1', ok='true'))
    assert cl.post(f'/w/{jid}/2/keep', data=dict(state='not json')).status_code == 400
    assert cl.post(f'/w/{jid}/2/keep', data=dict(state='[' + '0,' * 10000 + '0]')).status_code == 400            # more than 20 000 chars

def test_no_open_check_is_refused(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    for r in ('answer', 'hint', 'giveup'):
        assert cl.post(f'/w/{jid}/1/{r}', data=dict(answer='x')).status_code == 409                # the check was never loaded
    assert cl.post(f'/w/{jid}/9/answer').status_code == 404

def test_a_gate_logs_once_and_a_skipped_demo_is_closed(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    for i in (1, 2): lr.walk_step(jid, i, check=dict(way='demo', kind='demo', depth=2, why=''))
    cl.get(f'/w/{jid}/0'); cl.get(f'/w/{jid}/1')
    d = made(cl, 'scaling-by-the-root-of-dk'); g = first(b['id'] for b in d.spec['blocks'] if b.get('type') == 'gate')
    cl.post(f'/w/{jid}/2/predict', data=dict(slug=d.slug, gate=g, picked='0', ans='1', ok='false'))
    cl.get(f'/w/{jid}/2/check')                                                    # a reload shows the demo again
    r = cl.post(f'/w/{jid}/2/predict', data=dict(slug=d.slug, gate=g, picked='1', ans='1', ok='true')).json()
    assert r['ok'] and r['again'] and len(lr.attempts('scaling-by-the-root-of-dk')) == 1   # the second try on a gate is not logged
    assert lr.journey(jid).steps[2]['done']['outcome'] not in ('solid', 'fragile')
    cl.post(f'/w/{jid}/1/next')                                                    # skip step 1, then come back to it
    s = made(cl, 'softmax')
    assert 'walk-demo' not in cl.get(f'/w/{jid}/1/check').text                     # a skipped demo shows as closed
    assert cl.post(f'/w/{jid}/1/predict', data=dict(slug=s.slug, gate=g, picked='1', ans='1', ok='true')).status_code == 409
    assert not lr.attempts('softmax')

def test_code_check_in_the_browser(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why='your best way here: code'))
    card = cl.get(f'/w/{jid}/1/check').text
    assert 'code-editor' in card and 'def softmax(x, t=1.0):' in card and 'm = max(x)' not in card
    assert 'max(softmax([1000.0, 1001.0]))' not in card                            # a hidden test stays hidden
    assert 'Run the tests' in card and 'Hint' in card and "I don&#x27;t know" in card.replace("'", '&#x27;')
    assert cl.get(f'/w/{jid}/1/check').text.count('code-editor') == card.count('code-editor')   # a reload keeps one task
    assert lr.journey(jid).steps[1]['code']['fname'] == 'softmax'
    r = cl.post(f'/w/{jid}/1/run', data=dict(source='def softmax(x\n')).text
    assert 'line 1' in r and 'Try 1 of 3. A syntax error does not count as a try.' in r                                          # a syntax error does not count as a try
    r = cl.post(f'/w/{jid}/1/run', data=dict(source=NAIVE)).text
    assert '2 of 3 tests pass' in r and 'It does not fail on large scores' in r and 'm = max(x)' not in r
    assert 'code-editor' not in r and 'max(softmax([1000.0, 1001.0]))' not in r   # only the results part comes back
    r = cl.post(f'/w/{jid}/1/run', data=dict(source=GOOD)).text
    assert 'Next idea' in r and lr.attempts('softmax', limit=1)[0].kind == 'code'
    assert lr.journey(jid).steps[1]['done']['outcome'] == 'fragile'                # a pass after a failing try is not clean

def test_code_check_hides_a_failing_hidden_test(mk, walk_fake, lr):
    secret = 'assert softmax([0.0, 1.0]) == [0.123456, 0.876544]'
    walk_fake.rules['You write one small Python exercise'] = dict(EXERCISE, tests=EXERCISE['tests'][:2] + [dict(test=secret, say='A secret weight check', hidden=True)])
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why=''))
    cl.get(f'/w/{jid}/1/check')
    r = cl.post(f'/w/{jid}/1/run', data=dict(source=GOOD)).text
    assert 'A secret weight check' in r and 'fail' in r and '2 of 3 tests pass' in r
    for leak in ('0.123456', '0.876544', 'softmax([0.0, 1.0])', '0.2689', '0.7310'): assert leak not in r

def test_code_run_refuses_a_closed_or_missing_check(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why=''))
    assert cl.post(f'/w/{jid}/1/run', data=dict(source=GOOD)).status_code == 409   # the check was never loaded
    assert cl.post('/w/nope/1/run', data=dict(source=GOOD)).status_code == 404
    cl.get(f'/w/{jid}/1/check')
    assert 'Next idea' in cl.post(f'/w/{jid}/1/giveup').text
    assert 'Next idea' in cl.post(f'/w/{jid}/1/run', data=dict(source=GOOD)).text and lr.attempts('softmax', limit=5)[0].kind == 'code'
    assert len(lr.attempts('softmax', limit=9)) == 1                                # a closed check takes no more runs

def _chromium():
    "True when Playwright's bundled Chromium is installed."
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p: return Path(p.chromium.executable_path).exists()
    except Exception: return False

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
@pytest.mark.parametrize('how', ['click', 'key'])
def test_next_idea_moves_on_after_a_code_pass_in_a_browser(mk, walk_fake, lr, how):
    import socket, threading, time, uvicorn
    from playwright.sync_api import sync_playwright
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why=''))
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page(); url = f'http://127.0.0.1:{port}/w/{jid}/1'
                pg.goto(url); pg.wait_for_selector('#source')
                pg.fill('#source', GOOD); pg.press('#source', 'Control+Enter')           # runs the tests
                pg.wait_for_selector('#code-out .go')                                     # the close shows Next idea
                if how == 'click': pg.click('#code-out .go')
                else: pg.keyboard.press('Alt+s')
                pg.wait_for_function('u => location.href != u', arg=url, timeout=10000)
                assert pg.url != url and 'code-editor' not in pg.content().split('walk-main')[0]
            finally: b.close()
    finally: srv.should_exit = True; th.join(5)

HX = {'hx-request': 'true'}   # htmx asks for a part; without it FastHTML wraps the reply in a page

def test_ways_in(mk, walk_fake, lr):
    cl = mk()
    add = cl.get('/add').text
    assert 'A paper or document' in add and '/walk/new' in add
    did = add_paper(lr)
    assert 'Learn as a walk' in cl.get(f'/v/store/{did}').text
    jid = cl.post('/walk/new', data=dict(text=PAGES[1][1], title='My notes')).headers['hx-redirect'].split('/')[-1]
    assert lr.journey(jid).mode == 'walk' and lr.journey(jid).source is None
    walk_fake.rules['You plan a learning path'] = dict(title='Attention', subject='ml', steps=[dict(name='Ranking', statement='', slug='', why='Scores to places.', needs=[], ways=['code'])])
    tj = cl.post('/walk/new', data=dict(topic='how attention works')).headers['hx-redirect'].split('/')[-1]
    assert lr.journey(tj).mode == 'walk' and lr.journey(tj).steps[0]['read']['text'].startswith('Ranking orders')   # from the Notes source
    assert cl.post('/walk/new', data=dict(), headers=HX).text.startswith('<p')                 # nothing given: a plain message, no error page

def test_new_walk_errors_are_plain_messages(mk, walk_fake, lr):
    cl = mk()
    r = cl.post('/walk/new', data=dict(ref='no-such-document'), headers=HX)
    assert r.status_code == 200 and r.text.startswith('<p') and 'req-err' in r.text and 'hx-redirect' not in r.headers
    walk_fake.rules['Return JSON: {"concepts"'] = dict(concepts=[])
    r = cl.post('/walk/new', data=dict(ref=add_paper(lr)), headers=HX)
    assert 'The tutor found no ideas in this document.' in r.text and not [j for j in lr.journeys() if j.get('mode') == 'walk']

def test_today_journeys_concept_and_review_links(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    assert f'href="/w/{jid}"' in cl.get('/').text and '0 of 3 steps' in cl.get('/').text   # the journey row: one way to continue
    assert f'href="/w/{jid}"' in cl.get(f'/j/{jid}').text
    assert 'apply a softmax function' in cl.get('/c/softmax').text and f'/w/{jid}/1' in cl.get('/c/softmax').text
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    cl.get(f'/w/{jid}/1/check'); cl.post(f'/w/{jid}/1/answer', data=dict(answer='the rank is a position'))
    sid = cl.get('/start?focus=softmax', follow_redirects=False).headers['location'].split('/')[-1]
    cl.get(f'/s/{sid}'); r = cl.post(f'/s/{sid}/answer', data=dict(answer='rank'))
    assert 'Read the passage again: p. 4' in r.text and f'/w/{jid}/1' in r.text
    assert f'/w/{jid}' in cl.get('/learning').text                                 # Continue goes to the walk, not a plain session

def test_walk_from_a_link(mk, walk_fake, lr, monkeypatch):
    from fastcore.utils import L
    from vishalakshi.core import Vault
    def crawl(self, start_url, max_pages=10, sel=None, **kw):
        return L([self.add(PAGES, 'Attention docs', source=start_url, kind='web', meta=dict(url=start_url))])
    monkeypatch.setattr(Vault, 'crawl', crawl)
    monkeypatch.setattr('abhyasa.sources._final', lambda u: u)   # no fetch of the start page
    monkeypatch.setattr('abhyasa.sources._addrs', lambda host: {'93.184.216.34'})   # no DNS: a host on the internet
    cl = mk(); u = 'https://docs.example.dev/attention/'
    assert 'A link' in cl.get('/add').text and 'Pages to read' in cl.get('/add').text
    r = cl.post('/walk/new', data=dict(url=u, pages=3)).text
    assert 'pending' in r and '/walk/job' in r                                     # a link walk is made as a job
    jid = wait_for(lambda: (cl.get('/walk/job', params=dict(url=u)).headers.get('hx-redirect') or '').split('/')[-1] or None, secs=10)
    assert lr.journey(jid).source['url'] == u and len(lr.journey(jid).steps) == 3
    assert 'From the link' in cl.get(f'/w/{jid}').text
    monkeypatch.setattr(Vault, 'crawl', lambda self, *a, **kw: L())
    e = 'https://docs.example.dev/empty/'
    cl.post('/walk/new', data=dict(url=e))
    t = wait_for(lambda: t if 'pending' not in (t := cl.get('/walk/job', params=dict(url=e)).text) else None, secs=10)
    assert 'could not read this link' in t and 'req-err' in t

def test_link_walk_refuses_local_links(mk, walk_fake, lr):
    cl = mk()
    for bad in ('http://127.0.0.1:5001/', 'file:///etc/passwd', 'http://192.168.1.1/admin'):
        r = cl.post('/walk/new', data=dict(url=bad), headers=HX).text
        assert 'req-err' in r and 'pending' not in r                               # refused in the request: no job, no fetch
    assert 'No walk' in cl.get('/walk/job', params=dict(url='https://nothing.example/')).text

def test_link_walk_shows_only_its_own_messages(mk, walk_fake, lr, monkeypatch):
    from vishalakshi.core import Vault
    def crawl(self, *a, **kw): raise ValueError('10.0.0.1 is a private address — pass allow_private=True or set FOSSICK_ALLOW_PRIVATE=1')
    monkeypatch.setattr(Vault, 'crawl', crawl)
    monkeypatch.setattr('abhyasa.sources._final', lambda u: u)   # no fetch of the start page
    monkeypatch.setattr('abhyasa.sources._addrs', lambda host: {'93.184.216.34'})
    cl = mk(); u = 'https://docs.example.dev/broken/'
    cl.post('/walk/new', data=dict(url=u))
    t = wait_for(lambda: t if 'pending' not in (t := cl.get('/walk/job', params=dict(url=u)).text) else None, secs=10)
    assert 'allow_private' not in t and 'FOSSICK' not in t and 'abhyasa could not make a walk from this link' in t   # a library message never shows


def test_tool_walk_opens_in_leela(mk, walk_fake, lr, monkeypatch, tmp_path):
    from abhyasa.core.leela import LEELA_INSTALL
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    cl = mk(); assert 'Code opens in Leela' in cl.get('/add').text
    jid = cl.post('/walk/new', data=dict(ref=add_paper(lr), tool='on')).headers['hx-redirect'].split('/')[-1]
    assert lr.journey(jid).tool is True
    plan = cl.get(f'/w/{jid}').text
    assert 'Open this in Leela for code and tools' in plan and LEELA_INSTALL in plan and '/learn?' not in plan   # no Leela: never a broken link
    assert cl.post(f'/w/{jid}/plan', data=dict(i=1, act='check', way='code')).status_code == 400                # no library code check in abhyasa
    leela_file(tmp_path)
    assert f'href="http://127.0.0.1:5011/learn?walk={jid}"' in cl.get(f'/w/{jid}').text
    cl.post(f'/w/{jid}/start')
    step = cl.get(f'/w/{jid}/1').text
    assert f'http://127.0.0.1:5011/learn?walk={jid}&amp;step=1' in step and 'target="_blank"' in step
    assert 'code-editor' not in cl.get(f'/w/{jid}/1/check').text                                                 # the check here is short or order
    assert '/learn?' not in cl.get(f'/w/{jid}/0').text                                                           # an idea with no code way has no link

def test_code_card_and_concept_page_offer_leela_only_when_it_runs(mk, walk_fake, lr, monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why=''))
    card = cl.get(f'/w/{jid}/1/check').text
    assert 'code-editor' in card and 'Leela' not in card and 'Leela' not in cl.get('/c/softmax').text   # quiet when Leela is not running
    leela_file(tmp_path)
    card = cl.get(f'/w/{jid}/1/check').text
    assert 'code-editor' in card and f'/learn?walk={jid}&amp;step=1' in card                           # the small stdlib check stays in abhyasa
    assert '/learn?topic=Softmax' in cl.get('/c/softmax').text
