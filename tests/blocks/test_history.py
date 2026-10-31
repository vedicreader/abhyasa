"Your learning, resume after a restart, Continue, and the end of a session."
import time
from starlette.testclient import TestClient
from abhyasa.app import mk_app
from conftest import Notes

def start(cl, **data):
    return cl.post('/start', data=data, follow_redirects=False).headers['location'].split('/')[-1]

def test_resume_after_a_restart(mk, lr, fake):
    cl = mk()
    sid = start(cl)
    cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/answer', data=dict(answer='add the scores', thinking='numbers', confidence=70))   # a wrong try: still open
    cl2 = TestClient(mk_app(lr, fake, transcribe=lambda a, hint='': '', sources=[Notes()], hosts=('testserver',)))             # a restart: nothing in memory
    page = cl2.get(f'/s/{sid}').text
    assert 'What does a rank tell you?' in page and 'add the scores' in page and 'Not yet' in page      # the same question, its thread
    assert 'id="continue"' not in page   # a review has no Continue in the top bar
    r = cl2.post(f'/s/{sid}/answer', data=dict(answer='its rank position', confidence=80)).text
    assert 'Right, but shaky' in r

def test_end_shows_what_moved(mk, lr):
    cl = mk()
    sid = start(cl)
    cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/answer', data=dict(answer='its rank position', confidence=90))
    end = cl.get(f'/s/{sid}/end').text
    assert 'Done for now' in end and '1 of 1 passed' in end and 'What moved' in end and 'Related topics' in end
    assert cl.get(f'/s/{sid}', follow_redirects=False).headers['location'] == f'/s/{sid}/end'          # an ended session opens its summary

def test_your_learning(mk, lr):
    cl = mk()
    sid = start(cl, focus='ranking')
    cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/giveup', data=dict(dont_know=1))
    page = cl.get('/learning').text
    assert 'Your learning' in page and 'This week' in page and 'Ranking' in page and '0 of 1 passed' in page
    assert 'Continue' in page and 'Review the misses' in page and f'/learning/{sid}' in page
    one = cl.get(f'/learning/{sid}').text
    assert 'What does a rank tell you?' in one and 'A gap' in one and 'href="/learning"' in one

def test_session_page_shows_the_feedback_on_a_question(mk, lr):
    "The page of one past session shows what you said about the lesson of a question (pick and note), as the concept page does; a question with none shows nothing."
    cl = mk()
    sid = start(cl, focus='ranking')
    cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/giveup', data=dict(dont_know=1))
    assert 'Your feedback' not in cl.get(f'/learning/{sid}').text
    a = lr.attempts(session=sid)[0]
    lr.mark_attempt(a.id, feedback_on='lesson', verdict='unclear', note='The second step lost me.')
    one = cl.get(f'/learning/{sid}').text
    assert 'Your feedback on the lesson: Not clear' in one and 'The second step lost me.' in one

def test_session_page_matches_feedback_to_its_own_question(mk, lr):
    "A question asked twice in one session shows the feedback of each own attempt, not the newest on both rows."
    cl = mk(); sid = 'twice1'; q = 'What does a rank tell you?'
    a1 = lr.record('ranking', q, 'x', session=sid); a2 = lr.record('ranking', q, 'y', session=sid)
    row = lambda: dict(qid='q', concept='ranking', name='Ranking', depth=1, question=q, correct=False, outcome='gap', floor=0, turns=[dict(who='tutor', text=q)])
    lr.log_session(sid, 'two', start=1e9, end=1e9 + 9, concepts=['ranking'], passed=0, asked=2, log=[row(), row()], ended=True)
    first, second = sorted(lr.attempts(session=sid), key=lambda a: a.at)
    lr.mark_attempt(first.id, feedback_on='lesson', verdict='simple', note='First note.')
    lr.mark_attempt(second.id, feedback_on='lesson', verdict='unclear', note='Second note.')
    one = cl.get(f'/learning/{sid}').text
    assert one.count('Your feedback') == 2 and one.index('First note.') < one.index('Second note.')
    assert one.count('First note.') == one.count('Second note.') == 1

def test_continue_on_today_and_top_bar(mk):
    cl = mk()
    assert 'id="continue"' not in cl.get('/').text
    sid = start(cl)
    cl.get(f'/s/{sid}')
    today = cl.get('/').text
    assert 'Continue where you stopped' in today and f'href="/s/{sid}"' in today and 'id="continue"' not in today   # Home has the card, so the top bar has none
    assert f'href="/s/{sid}"' in top(cl.get('/concepts').text)

def test_old_summary_still_shows(mk, lr):
    lr.log_session('old1', '2 of 3 passed. Concepts: ranking.', start=1e9, end=1e9 + 60, concepts=['ranking'], passed=2, asked=3)
    page = mk().get('/learning').text
    assert '2 of 3 passed' in page


def test_review_the_misses_lines_up_on_each_row(mk, lr):
    "Your learning in a browser: on an open row (with Continue), an older open row and an ended row, the text of Review the misses starts at the title column."
    import socket, threading, time, uvicorn, pytest
    from test_board_js import _chromium
    if not _chromium(): pytest.skip("Playwright's Chromium is not installed")
    from playwright.sync_api import sync_playwright
    q = 'What does a rank tell you?'
    row = lambda: dict(qid='q', concept='ranking', name='Ranking', depth=1, question=q, correct=False, outcome='gap', floor=0, turns=[dict(who='tutor', text=q)])
    now = time.time()
    for k, ended in enumerate((False, False, True)):
        lr.log_session(f'miss{k}', f'run {k}', start=now - 60 * k, updated=now - 60 * k, concepts=['ranking'], passed=0, asked=1, log=[row()], ended=ended)
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(mk().app, host='127.0.0.1', port=port, log_level='error'))
    threading.Thread(target=srv.run, daemon=True).start()
    while not srv.started: time.sleep(.05)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page(viewport=dict(width=1100, height=900))
                pg.goto(f'http://127.0.0.1:{port}/learning', wait_until='load')
                xs = pg.evaluate("""() => [...document.querySelectorAll('.runs .run')].map(li => {
                    const left = el => { const r = document.createRange(); r.selectNodeContents(el); return Math.round(r.getBoundingClientRect().left); };
                    const a = [...li.querySelectorAll('.acts a')].find(a => a.textContent === 'Review the misses');
                    return [left(li.querySelector('.tt')), a && left(a), li.querySelector('.acts a').textContent]; })""")
            finally: b.close()
    finally: srv.should_exit = True
    assert [c for *_, c in xs] == ['Review the misses'] * 3, xs   # first on each row, also before Continue
    assert len({t for t, _, _ in xs} | {r for _, r, _ in xs}) == 1, xs   # one column: each title and each Review the misses

def open_session(lr, at):
    "An open session on Ranking that you used last at `at`."
    lr.log_session('old-open', 'open', start=at - 60, updated=at, focus='ranking', concepts=['ranking'], log=[], open=True)
    return 'old-open'

def a_walk(lr):
    "A walk of two ideas that you did not open yet."
    return lr.put_journey(dict(id='wk1', title='Softmax walk', mode='walk', goal='learn softmax', steps=[dict(slug='ranking', status='todo'), dict(slug='reciprocal-rank-fusion', status='todo')]))

def top(page): return page.split('id="continue"')[0].rsplit('<a ', 1)[1] + page.split('id="continue"')[1].split('</a>')[0]

def test_continue_names_the_walk_that_you_used_last(mk, walk_fake, lr):
    "A walk that you made, a session that you used after it, then the walk that you open now: the top bar and Today continue the walk, on the walk and on other pages."
    a_walk(lr); open_session(lr, time.time()); cl = mk()
    assert 'Continue: Ranking' in top(cl.get('/concepts').text)   # before you open the walk, the session is the newest place
    step = cl.get('/w/wk1/0').text
    assert 'id="continue"' not in step   # on the place itself, the top bar has no Continue
    assert 'Continue: Softmax walk' in top(cl.get('/concepts').text) and 'href="/w/wk1/0"' in top(cl.get('/concepts').text)
    card = cl.get('/').text.split('class="continue-card"')[1].split('</div>')[0]
    assert 'Softmax walk' in card and '0 of 2 ideas' in card and 'Ranking' not in card

def test_continue_names_a_newer_session(mk, walk_fake, lr):
    "A walk that you read an hour ago and a session that you used after it: the top bar and Today continue the session, also on the plan of the walk."
    a_walk(lr); cl = mk(); cl.get('/w/wk1/0')
    hour = time.time() - 3600
    lr.merge_journey('wk1', here=dict(step=0, at=hour), steps=[{**s, 'read_at': hour if k == 0 else None} for k, s in enumerate(lr.journey('wk1').steps)])
    sid = open_session(lr, time.time())
    bar = top(cl.get('/concepts').text)
    assert 'Continue: Ranking' in bar and f'href="/s/{sid}"' in bar
    assert 'Continue: Ranking' in top(cl.get('/w/wk1').text)   # on the walk page, the newer session wins
    card = cl.get('/').text.split('class="continue-card"')[1].split('</div>')[0]
    assert 'Ranking' in card and 'Softmax walk' not in card
