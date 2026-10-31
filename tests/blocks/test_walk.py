from walk_data import *
from fastcore.utils import first
from pathlib import Path
import abhyasa.blocks.walk
import pytest

def made(cl, key): return cl.app.state.svc['tutor'].jobs[key].result(timeout=30)   # wait on the demo job, not on the clock
from abhyasa.method import TEXT_WAYS, LABELS

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

def test_outline_names_draw_their_maths(mk, walk_fake, lr):
    "A step name with TeX shows as a maths carrier in the outline (no raw `$`), in plain inline markup with no block tags in the li."
    import re
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    slug = lr.journey(jid).steps[1]['slug']
    lr.update(slug, name=r'Why scale by $1/\sqrt{d_k}$')
    page = cl.get(f'/w/{jid}/0').text
    li = re.search(r'<li[^>]*id="rail-1".*?</li>', page, re.S).group(0)
    assert 'class="math inline"' in li and '$' not in li and '<p>' not in li and 'Why scale by' in li
    assert 'href="/w/' in li

def test_step_page_and_short_check(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why='plain words fit'))
    page = cl.get(f'/w/{jid}/1').text
    assert 'apply a softmax function' in page and f'src="/w/{jid}/1/img"' in page and f'hx-get="/w/{jid}/1/note"' in page
    assert 'Skip this idea' in page and '⌥F' not in page                             # a quiet skip while the check is open; ⌥F stays the shortcuts panel
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
    import socket, threading, uvicorn
    from playwright.sync_api import sync_playwright
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why=''))
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    assert wait_for(lambda: srv.started or None, secs=30), 'the server did not start'
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page(); url = f'http://127.0.0.1:{port}/w/{jid}/1'
                pg.goto(url, wait_until='load'); pg.wait_for_selector('#source')
                pg.wait_for_function('() => window.htmx && window.abhyasaKeys')            # core.js has bound the keys
                pg.fill('#source', GOOD); pg.press('#source', 'Control+Enter')           # runs the tests
                pg.wait_for_selector('#code-out .go')                                     # the close shows Next idea
                pg.wait_for_function("() => abhyasaFind(abhyasaKeys.KeyS)?.closest('#code-out')")   # htmx settled: ⌥S now finds Next idea, not Run
                if how == 'click': pg.click('#code-out .go')
                else: pg.keyboard.press('Alt+s')
                pg.wait_for_function('u => location.href != u', arg=url, timeout=30000)
                assert pg.url != url and 'code-editor' not in pg.content().split('walk-main')[0]
            finally: b.close()
    finally: srv.should_exit = True; th.join(5)

HX = {'hx-request': 'true'}   # htmx asks for a part; without it FastHTML wraps the reply in a page

def test_ways_in(mk, walk_fake, lr):
    cl = mk()
    add = cl.get('/add').text
    assert 'What do you want to learn?' in add and 'hx-post="/walk/new"' in add
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
    assert f'href="/w/{jid}"' in cl.get('/').text and '0 of 3 ideas' in cl.get('/').text   # the journey row: one way to continue
    assert cl.get(f'/j/{jid}', follow_redirects=False).headers['location'] == f'/w/{jid}'   # an old link goes to the walk page
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
    monkeypatch.setattr('socket.getaddrinfo', lambda host, port, *a, **k: [(2, 1, 6, '', ('93.184.216.34', port or 0))])   # no DNS: a host on the internet
    cl = mk(); u = 'https://docs.example.dev/attention/'
    assert 'Pages to read' in cl.get('/learn/read', params=dict(q=u)).text
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
    monkeypatch.setattr('socket.getaddrinfo', lambda host, port, *a, **k: [(2, 1, 6, '', ('93.184.216.34', port or 0))])
    cl = mk(); u = 'https://docs.example.dev/broken/'
    cl.post('/walk/new', data=dict(url=u))
    t = wait_for(lambda: t if 'pending' not in (t := cl.get('/walk/job', params=dict(url=u)).text) else None, secs=10)
    assert 'allow_private' not in t and 'FOSSICK' not in t and 'abhyasa could not make a walk from this link' in t   # a library message never shows


def test_tool_walk_opens_in_leela(mk, walk_fake, lr, monkeypatch, tmp_path):
    from abhyasa.core.leela import LEELA_INSTALL
    from abhyasa.contract import vault_key
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    cl = mk(); assert 'Code steps open in Leela' in cl.get('/learn/read', params=dict(q='github.com/a/b')).text
    jid = cl.post('/walk/new', data=dict(ref=add_paper(lr), tool='on')).headers['hx-redirect'].split('/')[-1]
    assert lr.journey(jid).tool is True
    plan = cl.get(f'/w/{jid}').text
    assert 'Open this in Leela for code and tools' in plan and LEELA_INSTALL in plan and '/learn?' not in plan   # no Leela: never a broken link
    assert cl.post(f'/w/{jid}/plan', data=dict(i=1, act='check', way='code')).status_code == 400                # no library code check in abhyasa
    leela_file(tmp_path); v = vault_key(lr.vault.path)                                                            # the link names the vault
    assert f'href="http://127.0.0.1:5011/learn?walk={jid}&amp;v={v}"' in cl.get(f'/w/{jid}').text
    cl.post(f'/w/{jid}/start')
    step = cl.get(f'/w/{jid}/1').text + cl.get(f'/w/{jid}/1/check').text                                         # a notebook card posts to /leela, then goes to the link
    assert (f'http://127.0.0.1:5011/learn?walk={jid}&amp;step=1&amp;v={v}' in step or f'action="/w/{jid}/1/leela"' in step) and 'target="_blank"' in step
    assert 'code-editor' not in step                                                                              # the check here is short, order or notebook
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

# The demo ladder in a walk: a wrong prediction gets a lesson in another way under the card, and a second one a simpler demo

def two_gates(d):
    "The spec of demo `d` with a second gate, so one demo check can take two predictions."
    g = {**first(b for b in d.spec['blocks'] if b.get('type') == 'gate'), 'id': 'second', 'prompt': 'Which document comes second after fusion?', 'answer': 'fused.1.id'}
    return {**d.spec, 'id': 'two-gates', 'blocks': [*d.spec['blocks'], g]}

def held(fake, key, words):
    "Hold the reply of the rule `key` of `fake` for a prompt with `words` until the event is set, so a test can see the pending state."
    import threading
    ev, real = threading.Event(), fake.rules[key]
    def rule(p, sp):
        if words in p: ev.wait(30)
        return real(p, sp) if callable(real) else real
    fake.rules[key] = rule
    return ev

def test_wrong_predictions_climb_the_demo_ladder(mk, walk_fake, lr):
    "The first wrong prediction shows a lesson in another way under the card. The second shows a simpler demo. The walk never waits on the model."
    from abhyasa.demo import SIMPLER_AIM
    slug = 'scaling-by-the-root-of-dk'
    teach, small_job = held(walk_fake, 'Teach the smallest step', 'They predicted'), held(walk_fake, 'You design one interactive demo', SIMPLER_AIM)
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 2, check=dict(way='demo', kind='demo', depth=2, why=''))
    cl.get(f'/w/{jid}/1')
    d = lr.put_demo(two_gates(made(cl, slug)), slug)
    card = cl.get(f'/w/{jid}/2/check').text
    assert 'id="ladder"' in card and f'hx-get="/w/{jid}/2/ladder"' not in card      # an empty slot until a wrong prediction (the feedback row only POSTs to it)
    r = cl.post(f'/w/{jid}/2/predict', data=dict(slug=d.slug, gate='win', picked='0', ans='1', ok='false')).json()
    assert r['ladder'] == f'/w/{jid}/2/ladder'
    ld = lr.journey(jid).steps[2]['ladder']
    assert ld['rung'] == 1 and ld['way'] in TEXT_WAYS
    part = cl.get(r['ladder']).text
    assert 'The tutor is writing a lesson in another way' in part and 'load delay:2s' in part   # pending: the page asks again
    teach.set(); made(cl, f'{slug}:lesson')
    part = cl.get(r['ladder']).text
    assert 'Positions are shared.' in part and f'Lesson · {LABELS[ld["way"]].lower()}' in part and 'class="go' not in part   # one quiet block, no new main button
    assert f'hx-get="/w/{jid}/2/ladder"' in cl.get(f'/w/{jid}/2/check').text        # a reload loads the help again
    r = cl.post(f'/w/{jid}/2/predict', data=dict(slug=d.slug, gate='second', picked='0', ans='1', ok='false')).json()
    part = cl.get(r['ladder']).text
    assert 'The tutor is making a simpler demo' in part and 'load delay:2s' in part and 'Positions are shared.' in part
    small_job.set(); small = made(cl, f'{slug}:simpler')
    assert small.aim == 'simpler' and lr.demo_for(slug, aim='').slug == d.slug        # the simpler demo is never the plain demo
    part = cl.get(r['ladder']).text
    assert 'Show a simpler demo' in part and 'data-rupaka' not in part and 'class="go' not in part
    shown = cl.get(r['ladder'] + '?show=1').text
    assert 'data-rupaka' in shown and f'data-demo="{small.slug}"' in shown
    a = cl.post(f'/w/{jid}/2/predict', data=dict(slug=small.slug, gate='win', picked='2', ans='1', ok='false')).json()
    assert a['ok'] and not a.get('again') and not a.get('ladder')                      # the third miss after the demo adds nothing (a new pick: the vault keeps one document for each text)
    assert (lr.attempts(slug, limit=1)[0].demo, lr.attempts(slug, limit=1)[0].method) == (small.slug, 'demo')   # it counts against demo

def test_one_gate_demo_can_ask_for_a_simpler_demo(mk, walk_fake, lr):
    "With one gate, the lesson after a wrong prediction has a quiet link. The link makes the simpler demo on demand: first a pending state, then the demo."
    from abhyasa.demo import SIMPLER_AIM
    slug = 'scaling-by-the-root-of-dk'
    hold = held(walk_fake, 'You design one interactive demo', SIMPLER_AIM)
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 2, check=dict(way='demo', kind='demo', depth=2, why=''))
    cl.get(f'/w/{jid}/1')
    d = made(cl, slug); g = first(b['id'] for b in d.spec['blocks'] if b.get('type') == 'gate')
    r = cl.post(f'/w/{jid}/2/predict', data=dict(slug=d.slug, gate=g, picked='0', ans='1', ok='false')).json()
    made(cl, f'{slug}:lesson')
    part = cl.get(r['ladder']).text
    assert 'Positions are shared.' in part and 'Show a simpler demo' in part and 'hx-post="/w/' in part and '?simpler=1' in part and 'class="go' not in part
    jobs = cl.app.state.svc['tutor'].jobs
    cl.get(r['ladder'] + '?simpler=1')                                                   # a GET reads: it asks for nothing and writes nothing
    assert not lr.journey(jid).steps[2]['ladder'].get('asked') and f'{slug}:simpler' not in jobs
    assert f'{slug}:simpler' not in cl.app.state.svc['tutor'].jobs                     # nothing is made until you ask
    part = cl.post(r['ladder'] + '?simpler=1').text
    assert 'The tutor is making a simpler demo' in part and 'load delay:2s' in part and 'Positions are shared.' in part
    assert lr.journey(jid).steps[2]['ladder']['asked']
    hold.set(); small = made(cl, f'{slug}:simpler')
    part = cl.get(r['ladder']).text                                                     # the poll after the job: the demo shows
    assert 'data-rupaka' in part and f'data-demo="{small.slug}"' in part and 'Positions are shared.' in part and 'class="go' not in part

def test_a_failed_lesson_job_does_not_start_again_on_the_poll(mk, walk_fake, lr):
    "A lesson job that fails stays failed: the next polls start no job and show one plain line with a button that POSTs. The button starts the job again."
    slug, calls, real = 'scaling-by-the-root-of-dk', [], walk_fake.rules['Teach the smallest step']
    def boom(p, sp): calls.append(p); return ''   # the model gives an empty lesson
    walk_fake.rules['Teach the smallest step'] = boom
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 2, check=dict(way='demo', kind='demo', depth=2, why=''))
    cl.get(f'/w/{jid}/1')
    d = made(cl, slug); g = first(b['id'] for b in d.spec['blocks'] if b.get('type') == 'gate')
    r = cl.post(f'/w/{jid}/2/predict', data=dict(slug=d.slug, gate=g, picked='0', ans='1', ok='false')).json()
    jb = cl.app.state.svc['tutor'].jobs[f'{slug}:lesson']; jb.result(timeout=30)
    n = len(calls)
    for _ in range(3):
        part = cl.get(r['ladder']).text
        assert 'could not write a lesson' in part and 'load delay' not in part and f'hx-post="/w/{jid}/2/ladder"' in part and 'Try again' in part
    assert len(calls) == n and cl.app.state.svc['tutor'].jobs[f'{slug}:lesson'] is jb      # the polls start no new job
    walk_fake.rules['Teach the smallest step'] = real
    cl.post(r['ladder']); made(cl, f'{slug}:lesson')                                          # Try again starts the job
    assert 'Positions are shared.' in cl.get(r['ladder']).text

def test_a_model_that_raises_gives_a_failed_ladder_not_a_lesson(mk, walk_fake, lr):
    "The tutor writes a fallback note when the model raises. The ladder does not show it as a lesson: it shows the failed state with Try again, and the poll starts no new job."
    slug, calls = 'scaling-by-the-root-of-dk', []
    def boom(p, sp): calls.append(p); raise RuntimeError('the model is down')
    walk_fake.rules['Teach the smallest step'] = boom
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 2, check=dict(way='demo', kind='demo', depth=2, why=''))
    cl.get(f'/w/{jid}/1')
    d = made(cl, slug); g = first(b['id'] for b in d.spec['blocks'] if b.get('type') == 'gate')
    r = cl.post(f'/w/{jid}/2/predict', data=dict(slug=d.slug, gate=g, picked='0', ans='1', ok='false')).json()
    cl.app.state.svc['tutor'].jobs[f'{slug}:lesson'].result(timeout=30); n = len(calls)
    for _ in range(2):
        part = cl.get(r['ladder']).text
        assert 'could not write a lesson' in part and 'Try again' in part and 'load delay' not in part and 'model answer' not in part
    assert not lr.journey(jid).steps[2]['ladder'].get('lesson') and len(calls) == n

def test_a_lesson_with_no_attempt_stops_the_poll(mk, walk_fake, lr):
    "When the attempt of the ladder is gone, the block shows a plain line with no poll and no button."
    slug = 'scaling-by-the-root-of-dk'
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 2, check=dict(way='demo', kind='demo', depth=2, why=''))
    lr.walk_step(jid, 2, ladder=dict(rung=1, aid='missing', way=TEXT_WAYS[0]))
    part = cl.get(f'/w/{jid}/2/ladder').text
    assert 'could not write a lesson' in part and 'load delay' not in part and 'Try again' not in part
    assert f'{slug}:lesson' not in cl.app.state.svc['tutor'].jobs

def test_a_prereq_does_not_stop_the_ladder_in_a_walk(mk, walk_fake, lr):
    "An idea with a prereq that is not learned still gets the simpler demo on the second wrong prediction: `_back` waits for the third miss since the demo."
    slug = 'scaling-by-the-root-of-dk'
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 2, check=dict(way='demo', kind='demo', depth=2, why=''))
    cl.get(f'/w/{jid}/1')
    d = lr.put_demo(two_gates(made(cl, slug)), slug)
    assert lr.concept(slug).prereqs                                                    # the idea has a prereq, and it is not learned
    for g in ('win', 'second'): r = cl.post(f'/w/{jid}/2/predict', data=dict(slug=d.slug, gate=g, picked='0', ans='1', ok='false')).json()
    made(cl, f'{slug}:lesson'); made(cl, f'{slug}:simpler')
    assert lr.concept(slug).after_demo == 2 and 'Show a simpler demo' in cl.get(r['ladder']).text

def test_no_ladder_in_a_walk_when_the_setting_is_off(mk, walk_fake, lr):
    "With checks.demo_ladder off, a wrong prediction only shows the answer, as before."
    from abhyasa.settings import set_val
    set_val('checks.demo_ladder', False)
    try:
        cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
        lr.walk_step(jid, 2, check=dict(way='demo', kind='demo', depth=2, why=''))
        cl.get(f'/w/{jid}/1')
        d = made(cl, 'scaling-by-the-root-of-dk'); g = first(b['id'] for b in d.spec['blocks'] if b.get('type') == 'gate')
        r = cl.post(f'/w/{jid}/2/predict', data=dict(slug=d.slug, gate=g, picked='0', ans='1', ok='false')).json()
        assert r['ok'] and 'ladder' not in r and not lr.journey(jid).steps[2].get('ladder')
        assert f'/w/{jid}/2/ladder' not in cl.get(f'/w/{jid}/2/check').text
    finally: set_val('checks.demo_ladder', True)

def test_a_failed_walk_shows_a_plain_line_and_logs_the_error(mk, walk_fake, lr, monkeypatch, caplog):
    "The page never shows the words of a library. The log keeps them."
    def boom(*a, **k): raise RuntimeError('litellm.APIError: 500 from upstream')
    monkeypatch.setattr('abhyasa.blocks.walk.app.walk_from_topic', boom)
    cl = mk()
    with caplog.at_level('WARNING'): r = cl.post('/walk/new', data=dict(topic='attention'), headers=HX)
    assert 'req-err' in r.text and 'litellm' not in r.text and 'upstream' not in r.text and 'Try again' in r.text
    assert 'litellm.APIError' in caplog.text

def test_code_run_refuses_a_source_that_is_too_long(mk, walk_fake, lr):
    "More than 100 000 characters of code is refused with 413, and it uses no try."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why=''))
    cl.get(f'/w/{jid}/1/check')
    big = GOOD + '\n#' + 'x' * (100_000 - len(GOOD))
    assert len(big) > 100_000 and cl.post(f'/w/{jid}/1/run', data=dict(source=big)).status_code == 413
    assert not lr.attempts('softmax') and 'Next idea' not in cl.get(f'/w/{jid}/1/check').text

def test_only_the_post_of_next_idea_ends_the_sitting(mk, walk_fake, lr):
    "A GET of the section summary (also a `?rh=` frame load) does not end the sitting. Next idea at the end of a section does."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    live, sid = cl.app.state.svc['sessions'], lr.journey(jid).sitting
    s = live[sid]
    for u in (f'/w/{jid}/0/done', f'/w/{jid}/0/done?pane=1', f'/?rh=/w/{jid}/0/done'): assert cl.get(u).status_code == 200
    assert not s.ended and live.get(sid) is s
    assert cl.post(f'/w/{jid}/0/next', follow_redirects=False).headers['location'] == f'/w/{jid}/0/done'
    assert s.ended and sid not in live
    assert 'Section done' in cl.get(f'/w/{jid}/0/done').text
    cl.get(f'/w/{jid}/1/check')
    assert lr.journey(jid).sitting != sid                                              # the next step opens a new sitting

def test_two_writers_on_one_walk_lose_no_field(mk, walk_fake, lr):
    "`walk_step` on two steps and `merge_journey` of `sitting` at the same time: each change stays."
    import threading
    cl = mk(); jid = walk(cl, lr); n = 15
    def a():
        for k in range(n): lr.walk_step(jid, 0, a=k)
    def b():
        for k in range(n): lr.walk_step(jid, 1, b=k)
    def c():
        for k in range(n): lr.merge_journey(jid, sitting=f's{k}')
    ts = [threading.Thread(target=f) for f in (a, b, c)]
    for t in ts: t.start()
    for t in ts: t.join()
    j = lr.journey(jid)
    assert (j.steps[0].get('a'), j.steps[1].get('b'), j.sitting) == (n - 1, n - 1, f's{n - 1}')
    assert lr.merge_journey(jid, sitting='x').steps == j.steps                      # a merge changes only the fields that it names


def fake_web(monkeypatch, pdf_title='Attention Is All You Need'):
    "The PDF and crawl readers file the test pages and fetch nothing; no DNS, no fetch of the start page or of an arXiv HTML page or title."
    from fastcore.utils import L
    from vishalakshi.core import Vault
    monkeypatch.setattr(Vault, 'pdf', lambda self, url, **kw: self.add(PAGES, pdf_title, source=url, kind='pdf'))
    monkeypatch.setattr(Vault, 'crawl', lambda self, start_url, max_pages=10, **kw: L([self.add([(k, 'From the docs. ' + t) for k, t in PAGES], 'Attention docs', source=start_url, kind='web')]))
    monkeypatch.setattr('abhyasa.sources._final', lambda u: u)
    monkeypatch.setattr('abhyasa.sources.read_arxiv_html', lambda aid: None)   # no arXiv HTML page, so the PDF reader runs
    monkeypatch.setattr('abhyasa.sources.arxiv_title', lambda aid, strict=False: None)   # no arXiv metadata fetch
    monkeypatch.setattr('socket.getaddrinfo', lambda host, port, *a, **k: [(2, 1, 6, '', ('93.184.216.34', port or 0))])

def test_link_in_the_document_field_makes_a_link_walk(mk, walk_fake, lr, monkeypatch):
    "A web link or an arXiv id in the vault document field makes the link walk, with one quiet note."
    fake_web(monkeypatch)
    cl = mk(); u = 'https://arxiv.org/pdf/1706.03762'
    r = cl.post('/walk/new', data=dict(ref=u, shelf='store'), headers=HX).text
    assert 'This is a link, so the tutor reads it from the web.' in r and 'pending' in r and '/walk/job' in r and 'req-err' not in r
    jid = wait_for(lambda: (cl.get('/walk/job', params=dict(url=u)).headers.get('hx-redirect') or '').split('/')[-1] or None, secs=10)
    assert lr.journey(jid).source['url'] == u and lr.journey(jid).steps
    r = cl.post('/walk/new', data=dict(ref='arXiv:1706.03762'), headers=HX).text
    assert 'This is a link' in r and 'pending' in r
    r = cl.post('/walk/new', data=dict(ref='http://127.0.0.1:5001/'), headers=HX).text
    assert 'req-err' in r and 'pending' not in r                                   # the link checks still refuse a local link

def test_vault_name_with_no_document(mk, walk_fake, lr, caplog):
    "A vault name that matches no document gives a plain message, and the log keeps a line."
    cl = mk()
    with caplog.at_level('WARNING'): r = cl.post('/walk/new', data=dict(ref='No such paper'), headers=HX).text
    assert 'No document in your vault has this name. To add a web page or a paper, paste its link.' in r and 'Try again' not in r
    assert 'No such paper' in caplog.text
    t = cl.post('/add', data=dict(ref='No such paper')).text
    assert 'No document in your vault has this name' in t and 'matching' not in t

def test_paper_link_says_paper(mk, walk_fake, lr, monkeypatch):
    "A paper link ignores the page count and its wait line says Reading the paper, with its page count; a docs link keeps its count of pages."
    import threading
    fake_web(monkeypatch)
    said, go = {}, threading.Event()
    def hold(lr_, ask, docs, progress=None, **kw):
        progress(0, len(docs)); said[docs[0].url] = True; go.wait(10)
        raise ValueError('stop')
    monkeypatch.setattr('abhyasa.blocks.walk.app.journey_from_sources', hold)
    from abhyasa.sources import file_link
    seen = {}
    def spy(lr_, url, pages=None, **kw): seen[url] = pages; return file_link(lr_, url, pages, **kw)
    monkeypatch.setattr('abhyasa.blocks.walk.app.file_link', spy)
    cl = mk(); p, d = 'https://arxiv.org/pdf/1706.03762', 'https://docs.example.dev/attention/'
    try:
        assert 'Reading the paper' in cl.post('/walk/new', data=dict(url=p, pages=15), headers=HX).text
        t = wait_for(lambda: t if 'Reading the paper: 5 pages' in (t := cl.get('/walk/job', params=dict(url=p)).text) else None, secs=10)
        assert t and '1 of 1' not in t and seen[p] is None
        cl.post('/walk/new', data=dict(url=d, pages=15), headers=HX)
        t = wait_for(lambda: t if 'Reading 1 of 1 page' in (t := cl.get('/walk/job', params=dict(url=d)).text) else None, secs=10)
        assert t and seen[d] == 15
    finally: go.set()

def test_start_box_shows_no_pages_for_a_paper(mk):
    "A paper is read in full, so the Start box shows no Pages to read for it. A docs site shows it."
    cl = mk()
    assert 'Pages to read' not in cl.get('/learn/read', params=dict(q='https://arxiv.org/pdf/1706.03762')).text
    assert 'Pages to read' in cl.get('/learn/read', params=dict(q='https://docs.example.dev/a/')).text

def boxes(html):
    "The answer box and the think-aloud box of a page, as their tags and their text."
    import re
    return {m[1]: (m[0], m[2]) for m in re.findall(r'(<textarea[^>]*id="(ans|think)"[^>]*>)(.*?)</textarea>', html, re.S)}

def test_wrong_try_gives_empty_boxes_and_keeps_the_try_in_the_record(mk, walk_fake, lr):
    "After a miss the card shows the try in its record, and the answer box and the think-aloud box are empty."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    cl.get(f'/w/{jid}/1/check'); qid = lr.journey(jid).steps[1]['qid']
    r = cl.post(f'/w/{jid}/1/answer', data=dict(answer='a sum of scores', thinking='I added them')).text
    assert 'Not yet' in r and 'a sum of scores' in r                                  # the try shows in the record
    b = boxes(r)
    assert b['ans'][1] == '' and b['think'][1] == '' and 'a sum of scores' not in b['ans'][0]   # the boxes are empty
    assert f'data-qid="{qid}"' in r and all('data-draft' in b[k][0] for k in b)        # core.js keeps a draft for each box, by question

def test_a_refused_move_gives_the_server_a_plain_reason(mk, walk_fake, lr):
    "A move on a check that is not open answers 409 with a short plain line, which the page shows (walk_look er1 checks it in a browser)."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    r = cl.post(f'/w/{jid}/1/answer', data=dict(answer='x'))
    assert r.status_code == 409 and r.text == 'No check is open on this idea. Load the page again.' and 'html' not in r.headers.get('content-type', '')

def link_walk_subjects(cl, u, **data):
    "Make a link walk with the form fields `data`, wait for it, and return the subjects of its concepts."
    cl.post('/walk/new', data=dict(url=u, **data), headers=HX)
    jid = wait_for(lambda: (cl.get('/walk/job', params=dict(url=u)).headers.get('hx-redirect') or '').split('/')[-1] or None, secs=10)
    return jid

def test_link_walk_sets_a_subject_for_each_new_concept(mk, walk_fake, lr, monkeypatch):
    "A link walk uses the Subject field when it is given. Else the finder gives the subject. A concept with a subject keeps it. A name that is a slug becomes words."
    fake_web(monkeypatch)
    lr.put('Softmax', 'Old words.', 'math')
    reply = dict(concepts=[{**c, 'subject': 'Transformers'} for c in EXTRACT_REPLY['concepts']])
    reply['concepts'][0]['name'] = 'sequential-computation'
    walk_fake.rules['Return JSON: {"concepts"'] = reply
    cl = mk()
    assert 'name="subject"' in cl.get('/learn/read', params=dict(q='a\nb')).text
    jid = link_walk_subjects(cl, 'https://docs.example.dev/a/')
    assert lr.journey(jid).subject == 'transformers'                                 # the walk has the subject that the tutor picked
    got = {c.slug: c.subject for c in lr.concepts()}
    assert got['sequential-computation'] == 'transformers' and got['scaling-by-the-root-of-dk'] == 'transformers' and got['softmax'] == 'math'
    assert lr.concept('sequential-computation').name == 'Sequential computation'

def test_link_walk_uses_the_subject_field(mk, walk_fake, lr, monkeypatch):
    "With the Subject field, each new concept gets that subject, and the request does not ask the finder for one."
    fake_web(monkeypatch)
    walk_fake.rules['Return JSON: {"concepts"'] = dict(concepts=[{**c, 'subject': 'Transformers'} for c in EXTRACT_REPLY['concepts']])
    jid = link_walk_subjects(mk(), 'https://docs.example.dev/b/', subject=' NLP!\n- x ')
    assert lr.journey(jid).subject == 'nlp - x'
    assert {c.subject for c in lr.concepts() if c.slug in ('softmax', 'sequential-computation')} == {'nlp - x'}
    assert 'Subject: "nlp - x"' in walk_fake.calls[-1][0] and '"subject": str' not in walk_fake.calls[-1][0]

def open_check(cl, lr, jid):
    "Start walk `jid`, open the short check of step 1, give one wrong try and get one hint."
    cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    cl.get(f'/w/{jid}/1/check')
    assert '2 tries left' in cl.post(f'/w/{jid}/1/answer', data=dict(answer='a sum of scores', confidence=40)).text
    assert 'Think about positions.' in cl.post(f'/w/{jid}/1/hint').text
    return lr.journey(jid).steps[1]['qid']

def test_open_check_survives_a_restart(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); qid = open_check(cl, lr, jid)
    cl2 = mk()                                                                      # a restart: a new app with a new tutor on the same vault
    assert qid not in dict(cl2.app.state.svc['tutor'].open)
    for page in (cl2.get(f'/w/{jid}/1').text, cl2.get(f'/w/{jid}/1/check').text):
        assert 'Its position.' not in page and 'rubric' not in page                 # the answer key never reaches the HTML
    card = cl2.get(f'/w/{jid}/1/check').text
    assert 'What does a rank tell you?' in card and 'Think about positions.' in card and lr.journey(jid).steps[1]['qid'] == qid   # the same check, with its hint
    r = cl2.post(f'/w/{jid}/1/answer', data=dict(answer='more scores', confidence=50))
    assert r.status_code == 200 and '1 try left' in r.text                          # the try before the restart counts
    assert 'a sum of scores' in walk_fake.calls[-1][0]                              # and the grader sees it
    r = cl2.post(f'/w/{jid}/1/answer', data=dict(answer='its rank position', confidence=70)).text
    assert 'Next idea' in r and lr.journey(jid).steps[1]['done']['outcome'] == 'fragile'
    assert len(lr.attempts('softmax', limit=None)) == 3 and lr.open_q(qid).status == 'closed'

def test_closed_check_after_a_restart_is_refused(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); qid = open_check(cl, lr, jid)
    lr.put_open_q(lr.open_q(qid).q, 'closed', 'closed')
    r = mk().post(f'/w/{jid}/1/answer', data=dict(answer='its rank position'))
    assert r.status_code == 409 and r.text == 'No check is open on this idea. Load the page again.'

def test_old_check_closes_with_no_grade(mk, walk_fake, lr):
    import time
    cl = mk(); jid = walk(cl, lr); qid = open_check(cl, lr, jid)
    before, n = dict(lr.concept('softmax')), len(lr.attempts('softmax', limit=None))
    lr.v.set_meta(lr.open_q(qid).doc_id, updated=time.time() - 8 * 86400)          # no change in 8 days; the setting is 7
    assert mk().post(f'/w/{jid}/1/answer', data=dict(answer='its rank position')).status_code == 409
    assert (lr.open_q(qid).status, lr.open_q(qid).end) == ('closed', 'abandoned')
    assert dict(lr.concept('softmax')) == before and len(lr.attempts('softmax', limit=None)) == n and not lr.journey(jid).steps[1]['done']

def test_two_answers_at_once_close_one_time(mk, walk_fake, lr):
    import threading, time
    from conftest import grader
    def slow(p, sp): time.sleep(.2); return grader(p, sp)
    cl = mk(); jid = walk(cl, lr); qid = open_check(cl, lr, jid)
    walk_fake.rules['You grade one answer'] = slow
    cl2 = mk()                                                                      # after a restart, so both requests load the question
    out = []
    def send(): out.append(cl2.post(f'/w/{jid}/1/answer', data=dict(answer='its rank position', confidence=70)))
    ts = [threading.Thread(target=send) for _ in range(2)]
    for t in ts: t.start()
    for t in ts: t.join()
    assert sorted(r.status_code for r in out) in ([200, 200], [200, 409]), [r.status_code for r in out]   # never a 500
    assert len([a for a in lr.attempts('softmax', limit=None) if a.get('final')]) == 1
    assert lr.journey(jid).steps[1]['done']['outcome'] == 'fragile'

def test_vault_viewer_refuses_an_open_question(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); qid = open_check(cl, lr, jid)
    d = lr.open_q(qid).doc_id
    r = cl.get(f'/v/learning/{d}')
    assert 'No such document' in r.text and 'Its position.' not in r.text and 'What does a rank' not in r.text   # the same page as a document that is not there
    assert cl.get(f'/v/learning/{d}/img?f=x.png').status_code == 404

def paper_walk(monkeypatch, cl, u='https://arxiv.org/pdf/1706.03762'):
    "Make a walk from an arXiv link whose PDF is filed under its id, as the PDF reader does; the arXiv metadata has the real title."
    fake_web(monkeypatch, pdf_title='1706.03762')
    monkeypatch.setattr('abhyasa.sources.arxiv_title', lambda i: 'Attention Is All You Need')
    cl.post('/walk/new', data=dict(url=u), headers=HX)
    return wait_for(lambda: (cl.get('/walk/job', params=dict(url=u)).headers.get('hx-redirect') or '').split('/')[-1] or None, secs=10)

def test_paper_walk_is_named_for_the_paper(mk, walk_fake, lr, monkeypatch):
    "A walk from an arXiv link takes the title of the paper, not its id; the id stays as a quiet tag on a row."
    cl = mk(); jid = paper_walk(monkeypatch, cl)
    assert lr.journey(jid).title == 'Attention Is All You Need'
    page = cl.get(f'/w/{jid}').text
    assert '<h1>Attention Is All You Need</h1>' in page and '1706.03762' not in page.split('<h1>')[0].split('<title>')[-1]
    cl.post(f'/w/{jid}/start')
    crumbs = cl.get(f'/w/{jid}/0').text
    assert 'Today' in crumbs and '>Attention Is All You Need<' in crumbs and '>1706.03762<' not in crumbs
    for url in ('/', '/journeys'):
        t = cl.get(url).text
        assert 'Attention Is All You Need' in t and 'class="paper-id mute"' in t and '>1706.03762<' in t

def test_old_paper_walk_title_is_repaired_once(lr):
    "A walk whose title is a bare arXiv id takes the title of its vault document, one time; a walk with a real title stays."
    from abhyasa.store import Learning
    d = lr.vault.add(PAGES, 'Attention Is All You Need', source='https://arxiv.org/pdf/1706.03762', kind='pdf')
    mk_j = lambda i, t, doc: lr.put_journey(dict(id=i, title=t, mode='walk', steps=[], url='https://arxiv.org/pdf/1706.03762', source=dict(url='https://arxiv.org/pdf/1706.03762'),
                                                 docs=[dict(shelf='store', doc_id=doc, title=t, url='https://arxiv.org/pdf/1706.03762')]))
    mk_j('old', '1706.03762', d['doc_id']); mk_j('mine', 'My own title', d['doc_id'])
    mark = first(lr.v.t.docs(where='source=?', where_args=['learning://marker/titles']))
    assert mark                       # the shelf has the mark of the repair
    lr.v.forget(mark['id'])           # a vault from before the repair: no mark, so the next load repairs
    assert not first(lr.v.t.docs(where='source=?', where_args=['learning://marker/titles']))
    assert Learning(lr.vault).journey('old').title == 'Attention Is All You Need' and lr.journey('mine').title == 'My own title'
    lr.put_journey({**lr.journey('old'), 'title': '1706.03762'})
    assert Learning(lr.vault).journey('old').title == '1706.03762'   # the mark is set: it does not look again

def test_continue_card_of_a_walk_says_what_was_done(mk, walk_fake, lr):
    "The Continue card on Today says the ideas done in a walk, not the questions of a session."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    cl.post(f'/w/{jid}/plan', data=dict(i=1, act='check', way='words'))
    cl.get(f'/w/{jid}/1/check'); cl.post(f'/w/{jid}/1/answer', data=dict(answer='the rank is a position'))
    card = cl.get('/').text.split('class="continue-card"')[1].split('</div>')[0]
    assert ' of 3 ideas' in card and 'question' not in card

def old_paper_walk(lr):
    "An old walk from an arXiv link: its title and its vault document have only the id."
    u = 'https://arxiv.org/pdf/1706.03762'
    d = lr.vault.add(PAGES, '1706.03762', source=u, kind='pdf')
    lr.put_journey(dict(id='old', title='1706.03762', mode='walk', steps=[], source=dict(url=u), url=u, docs=[dict(shelf='store', doc_id=d['doc_id'], title='1706.03762', url=u)]))
    return d['doc_id']

def test_old_paper_walk_gets_its_title_in_the_background(mk, lr):
    "After the start, the pool asks arXiv (faked) for the title of an old walk; the walk and its document take it."
    from abhyasa.app import repair_in_background
    did = old_paper_walk(lr); cl = mk()
    assert repair_in_background(cl.app, lambda aid: 'Attention Is All You Need').result(timeout=10) == ['old']
    assert lr.journey('old').title == 'Attention Is All You Need'
    assert first(lr.vault.t.docs(where='id=?', where_args=[did]))['title'] == 'Attention Is All You Need'

def test_failed_title_repair_keeps_the_id_and_tries_again(mk, lr):
    "A network failure keeps the id title and leaves the mark off, so the next start asks again."
    from abhyasa.app import repair_in_background
    old_paper_walk(lr); cl = mk()
    def down(aid): raise OSError('no network')
    assert repair_in_background(cl.app, down).result(timeout=10) == [] and lr.journey('old').title == '1706.03762'
    assert repair_in_background(cl.app, lambda aid: 'Attention Is All You Need').result(timeout=10) == ['old']

def test_title_repair_never_blocks_the_start(mk, lr):
    "The repair is a future on the pool: the call returns while arXiv is slow, and a load of the vault asks nothing."
    import threading
    from abhyasa.app import repair_in_background
    from abhyasa.store import Learning
    old_paper_walk(lr); cl = mk(); go = threading.Event()
    f = repair_in_background(cl.app, lambda aid: go.wait(10) and 'Attention Is All You Need')
    try:
        assert not f.done() and cl.get('/').status_code == 200 and Learning(lr.vault).journey('old').title == '1706.03762'
    finally: go.set()
    assert f.result(timeout=10) == ['old']

def test_link_walk_places_its_new_concepts_in_the_groups(mk, walk_fake, lr, monkeypatch):
    "A link walk into a subject with groups puts its new concepts in those groups, on the pool, after the walk."
    import re, time
    fake_web(monkeypatch)
    lr.set_group('ranking', ['Lists'], by='sort'); lr.save_groups('ml')
    walk_fake.rules['Return JSON: {"places"'] = lambda p, sp: dict(places=[dict(slug=s, group=['Lists']) for s in re.findall(r'^- ([a-z0-9-]+):', p, re.M)])
    link_walk_subjects(mk(), 'https://docs.example.dev/c/', subject='ml')
    for _ in range(250):
        if (c := lr.concept('softmax')) and c.get('group'): break
        time.sleep(.02)
    assert (c.group, c.group_by) == (['Lists'], 'placed')

def test_walk_from_a_vault_pdf_named_by_an_arxiv_id_gets_the_paper_title(mk, walk_fake, lr, monkeypatch):
    "A walk made from a vault PDF titled with its id takes the title of the paper from arXiv (faked) on the pool; no link is needed."
    monkeypatch.setattr('abhyasa.sources.arxiv_title', lambda aid, strict=False: 'Attention Is All You Need')
    d = lr.vault.add(PAGES, '1706.03762', source='/tmp/attention.pdf', kind='pdf')
    cl = mk(); jid = cl.post('/walk/new', data=dict(ref=d['doc_id'])).headers['hx-redirect'].split('/')[-1]
    assert wait_for(lambda: lr.journey(jid).title if lr.journey(jid).title != '1706.03762' else None, secs=10) == 'Attention Is All You Need'
    assert 'Attention Is All You Need' in cl.get('/').text

def test_old_vault_pdf_walk_is_repaired_after_the_first_mark(mk, lr):
    "A walk from a vault PDF with only an id for a title is repaired by the background repair, also when the first mark is on the shelf."
    from abhyasa.app import repair_in_background
    d = lr.vault.add(PAGES, '1706.03762', source='/tmp/attention.pdf', kind='pdf')
    lr.put_journey(dict(id='v', title='1706.03762', mode='walk', steps=[], source=dict(shelf='store', doc_id=d['doc_id'], title='1706.03762')))
    lr.v.add('old', title='Paper titles repaired', source='learning://marker/paper-titles', kind='marker')   # as the first release left it
    cl = mk()
    assert repair_in_background(cl.app, lambda aid: 'Attention Is All You Need').result(timeout=10) == ['v']
    assert lr.journey('v').title == 'Attention Is All You Need'
    assert first(lr.vault.t.docs(where='id=?', where_args=[d['doc_id']]))['title'] == 'Attention Is All You Need'

def test_a_board_on_an_open_check_counts_as_one_hint(mk, walk_fake, lr):
    "The screen guide explains a part of a step with an open check: the board is the next hint of the check, and the check says so."
    import json
    cl = mk(); jid = walk(cl, lr); open_check(cl, lr, jid)
    walk_fake.rules['Tier: tutor'] = '\n'.join(json.dumps(o) for o in [dict(op='v', n=1, sure=0.9), dict(op='step', say='The check asks about the place of an item.'),
                                                                     dict(op='box', at='check')])
    ctx = dict(page=f'/w/{jid}/1', anchors=[dict(id='check', kind='check', text='What does a rank tell you?')])
    evs = [json.loads(l[6:]) for l in cl.post('/guide/ask', json=dict(said='I do not get the check', ctx=ctx)).text.splitlines() if l.startswith('data: ')]
    assert evs[-1]['board']['hint'] == 'Hint 2 of 6 used (from the board).'
    card = cl.get(f'/w/{jid}/1/check').text
    assert 'Hint 2 of 6 (from the board)' in card and 'The check asks about the place of an item.' in card
    assert evs[0]['hint'] is True and evs[0]['wait'].endswith('This board counts as one hint on the open check.')   # said before the ask
    ctx['anchors'] += [dict(id='passage', kind='passage', text='The Kamba Ramayanam is a Tamil epic.')]   # an off-topic question on the same open check
    walk_fake.rules['Tier: tutor'] = '\n'.join(json.dumps(o) for o in [dict(op='v', n=1, sure=0.9), dict(op='step', say='It is a Tamil epic.'), dict(op='box', at='passage')])
    evs = [json.loads(l[6:]) for l in cl.post('/guide/ask', json=dict(said='Who wrote the Kamba Ramayanam?', ctx=ctx)).text.splitlines() if l.startswith('data: ')]
    assert 'hint' not in evs[0] and 'hint' not in evs[-1]['board'] and evs[-1]['board']['steps']
    assert 'Hint 3' not in cl.get(f'/w/{jid}/1/check').text   # the learner keeps the hint
    ctx['anchors'] = [dict(id='passage', kind='passage', text='Ranks.')]   # a board that does not show the check is not a hint
    evs = [json.loads(l[6:]) for l in cl.post('/guide/ask', json=dict(said='I do not get ranks', ctx=ctx)).text.splitlines() if l.startswith('data: ')]
    assert 'hint' not in evs[-1]['board']
