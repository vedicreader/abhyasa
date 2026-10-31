"Old paths become walks on Home, with their progress; old links go to the walk page; a concept page lists its walks; a session of a walk says when an idea is done."
import re
from abhyasa.journey import plan as plan_path

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

def test_an_old_path_becomes_a_walk_on_home(mk, fake, lr):
    "Home makes the old path a walk with the same id: each step has a check, the known step stays known, and the row counts it."
    cl = mk(); jid = old_path(lr, fake)
    home = cl.get('/').text
    j = lr.journey(jid)
    assert j.mode == 'walk' and [s['slug'] for s in j.steps] == ['tokenizers', 'ranking', 'attention'] and all(s['check'] for s in j.steps)
    assert j.steps[1]['status'] == 'known' and j.steps[1]['read']['title'] == 'My ranking notes'   # a passage from your sources
    assert 'How LLMs work' in home and '1 of 3 ideas' in home and 'Now: Tokenizers' in home and f'href="/w/{jid}"' in home

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
    cl = mk(); jid = old_path(lr, fake); cl.get('/')
    c = cl.get('/c/ranking').text
    assert 'In your walks' in c and 'idea 2 of 3' in c and f'href="/w/{jid}/1"' in c
    lr.put_journey(dict(id='w2', title='Second walk', mode='walk', steps=[dict(slug='tokenizers', status='todo', check=dict(way='words', kind='short', depth=2))]))
    r = cl.post('/walk/attach', data=dict(jid='w2', slug='ranking')).text
    assert 'Added to' in r and 'href="/w/w2/1"' in r and lr.journey('w2').steps[1]['check']['kind']

def test_step_done_in_the_thread(mk, fake, lr):
    "In a session of a walk, the close that makes an idea learned says so, and names the next idea."
    cl = mk(); jid = old_path(lr, fake); cl.get('/')
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
