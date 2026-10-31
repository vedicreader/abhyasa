"Each walk has a kind, and an old walk shows as a walk."
import re
from html import unescape

PLAN = dict(title='How LLMs work', subject='ml', steps=[
    dict(name='Tokenizers', statement='A tokenizer cuts text into tokens.', slug='', why='The model reads tokens.', needs=[]),
    dict(name='Attention', statement='Weights from query-key dot products.', slug='', why='The core of a transformer.', needs=['Tokenizers'])])

def make_plain(cl, fake, lr):
    "Plan a walk from a goal with the fake planner, and return its id."
    from abhyasa.journey import walk_from_topic
    fake.rules['You plan a learning path'] = PLAN
    return walk_from_topic(lr, fake, 'I want to learn how LLMs work').id

def visible_text(html):
    "The words a person sees: no scripts, styles, textarea content (prompt bodies), tags or attributes."
    html = re.sub(r'(?is)<(script|style|textarea)\b.*?</\1>', ' ', html)
    return unescape(re.sub(r'(?s)<[^>]*>', ' ', html))

def test_kind_pill(lr):
    from abhyasa.blocks.today.ui import kind_of
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
    cl = mk(); jid = make_plain(cl, fake, lr)
    assert lr.v.t.docs(where='source=?', where_args=[_src('journey', jid)])[0]['title'] == 'Walk: How LLMs work'
    r = lr.v.add('Journey: Old walk (old-1)\n\nGoal: g', title='Journey: Old walk', source=_src('journey', 'old-1'), kind='journey', meta=dict(id='old-1', title='Old walk', steps=[]))
    assert lr.v.t.docs(where='source=?', where_args=[_src('journey', 'old-1')])[0]['title'] == 'Journey: Old walk'   # the stored title stays
    page = cl.get(f'/v/learning/{r["doc_id"]}')
    assert page.status_code == 200 and 'Walk: Old walk' in page.text, page.text[:300]
    assert 'journey' not in visible_text(page.text).lower()
