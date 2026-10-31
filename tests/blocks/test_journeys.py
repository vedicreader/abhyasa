"Journeys: plan from a goal, change the path, continue it, and see it on Today and on a concept page."
import re
from starlette.testclient import TestClient
from abhyasa.app import mk_app

PLAN = dict(title='How LLMs work', subject='ml', steps=[
    dict(name='Tokenizers', statement='A tokenizer cuts text into tokens.', slug='', why='The model reads tokens.', needs=[]),
    dict(name='Ranking', statement='', slug='ranking', why='You rank the next token.', needs=['Tokenizers']),
    dict(name='Attention', statement='Weights from query-key dot products.', slug='', why='The core of a transformer.', needs=['Ranking'])])

def plan(cl, fake):
    fake.rules['You plan a learning path'] = PLAN
    r = cl.post('/journeys/new', data=dict(goal='I want to learn how LLMs work'))
    return r.headers['hx-redirect'].split('/')[-1]

def test_plan_and_path(mk, fake, lr):
    cl = mk()
    jid = plan(cl, fake)
    assert lr.concept('tokenizers').subject == 'ml' and lr.concept('ranking').floor == 0
    page = cl.get(f'/j/{jid}').text
    assert 'How LLMs work' in page and page.index('Tokenizers') < page.index('Ranking') < page.index('Attention')
    assert 'step tokenizers' not in page and 'class="step new now"' in page            # the first step is the one to do now
    assert f'href="/start?journey={jid}"' in page and 'Continue: Tokenizers' in page
    assert 'class="crumbs"' in page and 'href="/learn"' in page                      # a way up
    assert 'data-mic' in page                                                         # say a topic to add

def test_empty_goal(mk):
    assert 'Say or type' in mk().post('/journeys/new', data=dict(goal=' ')).text

def test_change_the_path(mk, fake, lr):
    cl = mk()
    jid = plan(cl, fake)
    r = cl.post(f'/j/{jid}/step', data=dict(slug='attention', act='up')).text
    assert r.index('Attention') < r.index('Ranking') and 'id="path"' in r
    r = cl.post(f'/j/{jid}/step', data=dict(slug='tokenizers', act='known')).text
    assert 'you know it' in r and 'Continue: Attention' in r                         # the path goes on
    cl.post(f'/j/{jid}/step', data=dict(slug='ranking', act='remove'))
    assert [s['slug'] for s in lr.journey(jid).steps] == ['tokenizers', 'attention']
    fake.rules['The idea: '] = dict(name='Mamba', statement='Mamba is a selective state-space model.')
    assert 'Mamba' in cl.post(f'/j/{jid}/add', data=dict(name='Mamba')).text

def test_continue_a_journey(mk, fake, lr):
    cl = mk()
    jid = plan(cl, fake)
    r = cl.get(f'/start?journey={jid}', follow_redirects=False)
    sid = r.headers['location'].split('/')[-1]
    page = cl.get(f'/s/{sid}').text
    assert 'Tokenizers' in page and f'href="/path/{jid}"' in page                     # the session names its walk, its parent

def test_today_and_concept_page(mk, fake):
    cl = mk()
    today = cl.get('/').text
    assert 'href="/learn#start"' in today and 'No walks yet' in today
    jid = plan(cl, fake)
    today = cl.get('/').text
    assert 'How LLMs work' in today and '0 of 3 ideas' in today and '>path<' in today and 'Now: Tokenizers' in today
    c = cl.get('/c/ranking').text
    assert 'In your walks' in c and 'idea 2 of 3' in c
    assert 'Continue: How LLMs work' in cl.get('/concepts').text                     # the top bar continues the journey

def test_step_done_in_the_thread(mk, fake, lr):
    cl = mk()
    jid = plan(cl, fake)
    lr.update('tokenizers', floor=3, ceiling=6, seen=1)
    sid = cl.get(f'/start?journey={jid}', follow_redirects=False).headers['location'].split('/')[-1]
    cl.get(f'/s/{sid}')
    fake.rules['You grade one answer'] = dict(correct=True, grade=9, first_error='', misconception='', feedback='Yes.')
    r = cl.post(f'/s/{sid}/answer', data=dict(answer='tokens', confidence=90)).text
    assert 'Idea done' in r and 'Next in the walk: Ranking' in r

def test_drop(mk, fake, lr):
    cl = mk()
    jid = plan(cl, fake)
    cl.post(f'/j/{jid}/drop')
    assert lr.journey(jid) is None and 'No such walk' in cl.get(f'/j/{jid}').text
