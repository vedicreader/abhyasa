"Task 19d: the pane trail, and small copy faults."
import re, json, html
from walk_data import *

# 1. The pane trail and the pace of the side walk

def test_pane_trail_starts_at_the_idea(mk, walk_fake, lr):
    "A side walk tells the pane a trail that starts at the idea (`Idea 3`), with no walk title, and its pace: `Side walk · 1 of 1`."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.put('Derivatives and gradients', 'The slope of a function at a point, one for each input.', 'ml', slug='gradients')
    lr.update('scaling-by-the-root-of-dk', prereqs=['softmax', 'gradients'])
    url = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url']
    h = cl.get(url + '?pane=1').text
    back = re.search(r'<a [^>]*class="rh-back walk-back"[^>]*>', h)
    assert back, h[h.find('walk-back') - 300:h.find('walk-back') + 50]
    attr = lambda k: html.unescape(re.search(k + r"""=(['"])(.*?)\1""", back.group(0)).group(2))
    trail = json.loads(attr('data-rh-trail'))
    assert trail[0][0] == 'Idea 3' and 'Attention' not in json.dumps(trail)
    assert attr('data-rh-pace') == 'Side walk · 1 of 1'

# 2. Small faults

def test_settings_say_one_day(mk):
    "A count unit takes the plural rule: `default 1 day`, `0.5 days`; a short unit (min, s, MB) stays as it is."
    from abhyasa.core.rows import say
    from abhyasa.settings import SETTINGS as ROWS
    r = ROWS['review.solid']
    assert say(r, 1.) == '1 day' and say(r, .5) == '0.5 days' and say(r, 2) == '2 days' and say(ROWS['walks.fresh'], 1) == '1 min'
    assert 'default 1 days' not in mk().get('/settings').text and 'default 1 day' in mk().get('/settings').text

def test_concept_meta_uses_the_walk_words(mk, lr):
    "The concept page says `not learned yet` for an idea with no level, as the needs line does, and not `floor unseen` or `new`."
    t = mk().get('/c/ranking').text
    head = t[t.index('<h1'):]; head = head[:head.index('</p>')]
    assert 'not learned yet' in head and 'floor' not in head and '· new' not in head, head
    lr.update('ranking', floor=2, seen=1, last=__import__('time').time(), stability=3.)
    t = mk().get('/c/ranking').text
    head = t[t.index('<h1'):]; head = head[:head.index('</p>')]
    assert 'level: recall' in head and 'floor' not in head, head

def test_weak_spot_says_why(mk, lr):
    "A weak spot always gives its reason; it does not show its recall, which can read as a strength."
    lr.update('reciprocal-rank-fusion', misses=1, seen=1, last=__import__('time').time(), stability=30.)
    t = mk().get('/you/strengths').text
    weak = t[t.index('Weak spots'):t.index('Practice my weak spots')]
    assert 'missed the last time' in weak and 'recall 100%' not in weak and 'recall ' not in weak.replace('recall is down to', ''), weak

