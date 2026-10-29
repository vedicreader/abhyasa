"Your learning, resume after a restart, Continue, and the end of a session."
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
    assert 'Continue: Ranking' not in page and 'id="continue"' in page
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

def test_continue_on_today_and_top_bar(mk):
    cl = mk()
    assert 'id="continue"' not in cl.get('/').text
    sid = start(cl)
    cl.get(f'/s/{sid}')
    today = cl.get('/').text
    assert 'Continue where you stopped' in today and f'href="/s/{sid}"' in today and 'id="continue"' in today

def test_old_summary_still_shows(mk, lr):
    lr.log_session('old1', '2 of 3 passed. Concepts: ranking.', start=1e9, end=1e9 + 60, concepts=['ranking'], passed=2, asked=3)
    page = mk().get('/learning').text
    assert '2 of 3 passed' in page

def test_crumbs_and_keys(mk):
    cl = mk()
    page = cl.get('/c/ranking').text
    assert 'class="crumbs"' in page and 'class="up"' in page and 'href="/concepts"' in page
    js = cl.get('/assets/core.js').text
    assert "'Escape'" in js and 'KeyT' in js and 'KeyC' in js
