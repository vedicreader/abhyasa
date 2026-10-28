"Task 19a, design polish: one check card, one main button in a view, ⌥S that sends, the keyboard sheet, native controls on the theme, and the dark and Signal rules."
import re
from pathlib import Path
from walk_data import *

ROOT = Path(__file__).parents[2]/'abhyasa'
HX = {'hx-request': 'true'}

def start(cl, **data): return cl.post('/start', data=data, follow_redirects=False).headers['location'].split('/')[-1]

def shape(h):
    "The check markup of a reply: the card, its question, the thread and each kind of message, in order and with no text."
    return [re.sub(r'<section[^>]*', 'card', x) for x in re.findall(r'<section[^>]*class="check[^"]*"|<div class="md q">|<ol class="thread"|<li class="m you|class="tag (?:ok|no)"|<span class="k">First error: </span>', re.sub(r' id="[^"]*"', '', h))]

# F3: one check card for the session and the walk

def test_session_and_walk_draw_the_same_check(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    cl.get(f'/w/{jid}/1/check')
    w = cl.post(f'/w/{jid}/1/answer', data=dict(answer='add the scores')).text
    sid = start(cl); cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/answer', data=dict(answer='add the scores'))
    s = cl.get(f'/s/{sid}').text
    s = s[s.index('class="check qa"') - 40:]
    assert shape(w)[:6] == shape(s)[:6] == ['card', '<div class="md q">', '<ol class="thread"', '<li class="m you',
                                            'class="tag no"', '<span class="k">First error: </span>']
    css = (ROOT/'blocks/session/session.css').read_text()
    assert '.m.you { align-self' not in css and '.m .k' not in css and '.m.tutor' not in css   # "You" at the left, one style for First error
    assert '.check .q' in (ROOT/'core/base.css').read_text() and '.check .q' not in (ROOT/'blocks/walk/walk.css').read_text()
