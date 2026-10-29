"One word, walk: no page says journey, the old `/j/` routes still work, and each walk has a kind."
import re
from html import unescape

PAGES = ('/', '/journeys', '/learning', '/keys', '/settings', '/add', '/concepts')
PLAN = dict(title='How LLMs work', subject='ml', steps=[
    dict(name='Tokenizers', statement='A tokenizer cuts text into tokens.', slug='', why='The model reads tokens.', needs=[]),
    dict(name='Attention', statement='Weights from query-key dot products.', slug='', why='The core of a transformer.', needs=['Tokenizers'])])

def make_plain(cl, fake):
    "Plan a plain walk from a goal with the fake planner, and return its id."
    fake.rules['You plan a learning path'] = PLAN
    return cl.post('/journeys/new', data=dict(goal='I want to learn how LLMs work')).headers['hx-redirect'].split('/')[-1]

def visible_text(html):
    "The words a person sees: no scripts, styles, textarea content (prompt bodies), tags or attributes."
    html = re.sub(r'(?is)<(script|style|textarea)\b.*?</\1>', ' ', html)
    return unescape(re.sub(r'(?s)<[^>]*>', ' ', html))

def test_no_page_says_journey(mk, fake):
    "Every page uses one word, walk. The code names stay; the words on the page change."
    cl = mk(); jid = make_plain(cl, fake)
    for u in (*PAGES, f'/path/{jid}', f'/c/tokenizers'):
        text = visible_text(cl.get(u).text)
        assert 'journey' not in text.lower(), u

def test_old_journey_routes_still_work(mk, fake, lr):
    cl = mk(); jid = make_plain(cl, fake)
    r = cl.get(f'/j/{jid}', follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == f'/path/{jid}'
    r = cl.get(f'/j/{jid}?from=leela', follow_redirects=False)
    assert r.headers['location'] == f'/path/{jid}?from=leela'                      # the query string stays
    assert cl.post(f'/j/{jid}/step', data=dict(slug=lr.journey(jid).steps[0]['slug'], act='skip')).status_code == 200
    assert cl.post(f'/path/{jid}/step', data=dict(slug=lr.journey(jid).steps[1]['slug'], act='skip')).status_code == 200
    assert cl.get(f'/path/{jid}').status_code == 200
    assert f'href="/path/{jid}"' in cl.get('/journeys').text                      # links in the app go to the new route

def test_kind_pill(lr):
    from abhyasa.blocks.journeys.ui import kind_of
    assert kind_of(dict(mode='plan', steps=[])) == 'path'
    assert kind_of(dict(mode='walk', tool=True, source=dict(url='https://github.com/a/b'), steps=[])) == 'repo'
    assert kind_of(dict(mode='walk', source=dict(url='https://github.com/a/b'), steps=[])) == 'repo'
    assert kind_of(dict(mode='walk', source=dict(url='https://arxiv.org/abs/1706.03762', docs=[{}]), steps=[])) == 'paper'
    assert kind_of(dict(mode='walk', source=dict(shelf='store', doc_id='d1', title='Notes'), steps=[])) == 'paper'
    assert kind_of(dict(mode='walk', source=dict(url='https://docs.x.org/a/', docs=[{}]), steps=[])) == 'site'
    assert kind_of(dict(id='w1', mode='walk', source=None, steps=[dict(read=dict(doc_id='w1'))])) == 'text'
    assert kind_of(dict(mode='walk', source=None, steps=[])) == 'topic'

def test_old_walk_title_shows_as_walk(mk, fake, lr):
    "A new walk document has the title `Walk: …`. An old one keeps `Journey: …` in the vault, and the page shows `Walk: …`."
    from abhyasa.store import _src
    cl = mk(); jid = make_plain(cl, fake)
    assert lr.v.t.docs(where='source=?', where_args=[_src('journey', jid)])[0]['title'] == 'Walk: How LLMs work'
    r = lr.v.add('Journey: Old walk (old-1)\n\nGoal: g', title='Journey: Old walk', source=_src('journey', 'old-1'), kind='journey', meta=dict(id='old-1', title='Old walk', steps=[]))
    assert lr.v.t.docs(where='source=?', where_args=[_src('journey', 'old-1')])[0]['title'] == 'Journey: Old walk'   # the stored title stays
    page = cl.get(f'/v/learning/{r["doc_id"]}')
    assert page.status_code == 200 and 'Walk: Old walk' in page.text, page.text[:300]
    assert 'journey' not in visible_text(page.text).lower()
