"Task 19d: the outline, the pane trail, lists of the same button, and small copy faults."
import re, json, html
from walk_data import *

# 1. The outline folds into one line

def test_outline_is_one_line_that_opens(mk, walk_fake, lr):
    "The outline is a details: its summary is the label and the progress line; the list of ideas is in the fold."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    h = cl.get(f'/w/{jid}/2').text
    rail = h[h.index('id="rail"'):]; rail = rail[:rail.index('</aside>')]
    summary = rail[rail.index('<summary'):rail.index('</summary>')]
    assert 'The paper · 3 of 3' in summary and 'id="rail-prog"' in summary, rail[:400]
    assert 'id="rail-0"' in rail[rail.index('</summary>'):]

# 2. The pane trail and the pace of the side walk

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

# 3. A list has one button: on the current journey, or the current open session; the other rows have a quiet link

def test_journeys_have_one_button(mk, walk_fake, lr):
    "The look is the feature: in a list, only the current walk has a button, so it stands out; the others have a quiet `Start the walk →` link."
    cl = mk()
    for _ in range(3): walk(cl, lr)
    h = cl.get('/learn').text
    rows = h.split('class="jrow lrow"')[1:]
    assert len(rows) == 3 and sum('class="btn small"' in r for r in rows) == 1 and 'class="btn small">Start the walk' in rows[0], rows
    assert all('Start the walk →</a>' in r for r in rows[1:])

def test_your_learning_has_one_continue_and_no_open(mk, lr):
    "The look is the feature: only the newest open session has the Continue button; an older open one has a quiet link; no row has Open."
    row = [dict(concept='ranking', correct=True, depth=1, question='q', turns=[])]
    lr.log_session('old1', 'An older open session.', start=3., updated=3., log=row)
    lr.log_session('new1', 'An open session.', start=5., updated=5., log=row)
    h = mk().get('/learning').text
    runs = h[h.index('class="days"'):]
    assert runs.count('class="btn small">Continue') == 1 and runs.index('/s/new1') < runs.index('class="btn small">Continue') < runs.index('/s/old1'), runs[:3000]
    assert re.search(r'<a [^>]*href="/s/old1"[^>]*>Continue →</a>', runs) and '>Open<' not in runs

# 4. Small faults

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
    assert 'missed the last time' in weak and 'recall 100%' not in weak and 'recall ' not in weak.replace('fading: recall', ''), weak

