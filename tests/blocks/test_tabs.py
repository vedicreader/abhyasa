"The top bar: three tabs, Continue, Search and a gear; the tab in force; the sub-tabs of Library and You; and the old URLs."
import re

def _top(h): return re.search(r'<nav[^>]*aria-label="Main"[^>]*>(.*?)</nav>', h, re.S).group(1)
def _text(a): return re.sub(r'<[^>]+>', '', a).strip()

def nav_words(h):
    "The link text of the top bar, less the brand, Continue, Search and the gear."
    return [_text(a) for c, a in re.findall(r'<a ([^>]*)>(.*?)</a>', _top(h), re.S) if not re.search(r'brand|nav-search|gear|id="continue"', c)]

def current_tab(h):
    "The text of the top bar link with `aria-current=\"page\"`, or '' when none has it."
    m = [a for c, a in re.findall(r'<a ([^>]*)>(.*?)</a>', _top(h), re.S) if 'aria-current="page"' in c]
    return _text(m[0]) if m else ''

def sub_words(h):
    m = re.search(r'<nav[^>]*class="subtabs"[^>]*>(.*?)</nav>', h, re.S)
    return [_text(a) for a in re.findall(r'<a [^>]*>(.*?)</a>', m.group(1), re.S)] if m else []

def sub_in_force(h):
    m = re.search(r'<nav[^>]*class="subtabs"[^>]*>.*?<a [^>]*aria-current="page"[^>]*>(.*?)</a>', h, re.S)
    return _text(m.group(1)) if m else ''

def test_bar_has_three_tabs_and_a_gear(mk):
    h = mk().get('/').text
    assert nav_words(h) == ['Home', 'Library', 'You'] and 'href="/settings"' in h

def test_tab_on_every_page(mk, talk_fake, lr):
    "Each page marks its tab: Home, a walk, a path, a session and a talk are in Home; a concept, a demo and a vault document are in Library."
    from talk_data import walk, prep_walk, make_talk
    cl = mk(); jid = walk(cl, lr); tid = make_talk(cl, prep_walk(lr, walk(cl, lr)))
    sid = cl.post('/start', data={}, follow_redirects=False).headers['location'].split('/')[-1]
    for u, tab in (('/', 'Home'), ('/learn', 'Home'), (f'/w/{jid}', 'Home'), (f'/w/{jid}/1', 'Home'), (f'/path/{jid}', 'Home'), (f'/j/{jid}', 'Home'), (f'/s/{sid}', 'Home'),
                   (f'/t/{tid}', 'Home'), ('/w/nope', 'Home'), ('/c/ranking', 'Library'), ('/c/nope', 'Library'), ('/v/learning/nope', 'Library'),
                   (f'/learning/{sid}', 'You'), ('/settings', ''), ('/search?q=rank', ''), ('/keys', '')):
        assert current_tab(cl.get(u).text) == tab, u

def test_subtabs(mk):
    "Library and You have sub-tabs; the page in force is marked. Strengths is part of Progress. /library is Concepts."
    h = mk().get('/library/sources').text
    assert sub_words(h) == ['Concepts', 'Sources', 'Graph'] and sub_in_force(h) == 'Sources'
    assert sub_in_force(mk().get('/library').text) == 'Concepts'
    assert sub_words(mk().get('/you').text) == ['Progress', 'Profile'] and sub_in_force(mk().get('/you/profile').text) == 'Profile'
    assert sub_in_force(mk().get('/you/strengths').text) == 'Progress'

def test_old_urls_still_work(mk):
    cl = mk()
    for u in ('/learn', '/journeys', '/add', '/learning', '/graph', '/sources', '/you', '/you/strengths', '/settings', '/keys'): assert cl.get(u).status_code == 200, u

def test_no_learn_query_link(mk):
    "A Leela link starts with /learn?; no abhyasa link may look like one."
    assert '/learn?' not in mk().get('/').text
