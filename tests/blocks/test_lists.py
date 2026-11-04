"Long lists: Home shows the 5 walks and talks that you used last, with a link to all of them; a list page shows 20 at a time, with a filter and a sort."
import re, time
import abhyasa.blocks.today.app as today_app
from abhyasa.show import TALK_SCHEMA

def walks(lr, n):
    "`n` walks, each used a second after the one before."
    for k in range(n):
        lr.put_journey(dict(id=f'w{k}', title=f'Walk {k:02d}', goal='', mode='walk', created=1000 + k, steps=[dict(slug='ranking', status='todo', check=dict(way='words', kind='short', depth=2))]))

def talks(lr, n):
    for k in range(n):
        lr.put_talk(dict(id=f't{k}', kind='talk', schema=TALK_SCHEMA, title=f'Talk {k:02d}', src={'walk': 'w0'}, made=1000 + k, minutes=10, phones=False, live=None, slides=[]))
        time.sleep(.002)

def test_home_shows_5_walks_and_the_link_to_all(mk, lr):
    "With 7 walks, Home shows the 5 that you used last and the link All walks (7)."
    walks(lr, 7)
    h = mk().get('/').text
    assert len(re.findall(r'href="/w/w\d+" class="jt"', h)) == 5 and 'All walks (7)' in h and 'href="/walks"' in h
    assert 'Walk 06' in h and 'Walk 01' not in h

def test_the_walks_page_filters_and_counts_walk_state(mk, lr, monkeypatch):
    "The walks page asks for `walk_state` only for the rows on its page; the filter narrows the list; the old /journeys goes to /walks."
    walks(lr, 25)
    n = []
    real = today_app.walk_state
    monkeypatch.setattr(today_app, 'walk_state', lambda *a, **kw: (n.append(1), real(*a, **kw))[1])
    cl = mk()
    h = cl.get('/walks').text
    assert len(n) <= 20 and len(re.findall(r'href="/w/w\d+" class="jt"', h)) == 20 and 'Page 1 of 2' in h
    h2 = cl.get('/walks', params=dict(page=2)).text
    assert len(re.findall(r'href="/w/w\d+" class="jt"', h2)) == 5
    h3 = cl.get('/walks', params=dict(q='walk 07')).text
    assert len(re.findall(r'href="/w/w\d+" class="jt"', h3)) == 1 and 'Walk 07' in h3
    assert cl.get('/journeys', follow_redirects=False).headers['location'] == '/walks'

def test_talks_page_2_and_home_teach(mk, lr):
    "With 25 talks, Teach on Home shows 5 and All talks (25); page 2 of the talks page shows 5; the filter narrows it."
    walks(lr, 1); talks(lr, 25)
    cl = mk()
    h = cl.get('/').text
    assert 'All talks (25)' in h and len(re.findall(r'href="/t/t\d+" class="jt"', h)) == 5
    p2 = cl.get('/talks', params=dict(page=2)).text
    assert len(re.findall(r'href="/t/t\d+" class="jt"', p2)) == 5 and 'Page 2 of 2' in p2
    f = cl.get('/talks', params=dict(q='Talk 03')).text
    assert len(re.findall(r'href="/t/t\d+" class="jt"', f)) == 1
