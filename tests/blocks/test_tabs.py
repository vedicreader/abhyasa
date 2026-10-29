"The top bar: four tabs, Continue, Search and a gear; the tab in force; the sub-tabs of Library and You; and the old URLs."
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

def test_bar_has_four_tabs_and_a_gear(mk):
    h = mk().get('/').text
    assert nav_words(h) == ['Today', 'Learn', 'Library', 'You']
    assert 'aria-label="Settings"' in h and 'href="/settings"' in h and 'aria-label="Main"' in h
    assert h.index('nav-search') < h.index('aria-label="Settings"')   # order: Continue, Search, gear

def test_tab_in_force(mk):
    cl = mk()
    for u, tab in (('/', 'Today'), ('/learn', 'Learn'), ('/journeys', 'Learn'), ('/add', 'Learn'), ('/concepts', 'Library'), ('/sources', 'Library'),
                   ('/graph', 'Library'), ('/learning', 'You'), ('/you', 'You'), ('/you/strengths', 'You'), ('/settings', '')):
        assert current_tab(cl.get(u).text) == tab, u
    assert 'class="gear on"' in cl.get('/settings').text and 'class="gear on"' not in cl.get('/').text   # the gear is ruled under on Settings

def test_tab_on_every_page(mk, talk_fake, lr):
    "Each page marks its tab: a walk, a path, a session and a talk are in Learn; a concept, a demo and a vault document are in Library."
    from talk_data import walk, prep_walk, make_talk
    cl = mk(); jid = walk(cl, lr); tid = make_talk(cl, prep_walk(lr, walk(cl, lr)))
    sid = cl.post('/start', data={}, follow_redirects=False).headers['location'].split('/')[-1]
    for u, tab in ((f'/w/{jid}', 'Learn'), (f'/w/{jid}/1', 'Learn'), (f'/path/{jid}', 'Learn'), (f'/j/{jid}', 'Learn'), (f'/s/{sid}', 'Learn'),
                   (f'/t/{tid}', 'Learn'), ('/w/nope', 'Learn'), ('/c/ranking', 'Library'), ('/c/nope', 'Library'), ('/v/learning/nope', 'Library'),
                   (f'/learning/{sid}', 'You'), ('/settings', ''), ('/search?q=rank', ''), ('/keys', '')):
        assert current_tab(cl.get(u).text) == tab, u

def test_subtabs(mk):
    h = mk().get('/sources').text
    assert sub_words(h) == ['Concepts', 'Sources', 'Graph'] and sub_in_force(h) == 'Sources'
    assert 'role="tab' not in h and 'aria-selected' not in h   # plain links in a nav, as in the top bar
    assert 'title="⌥1"' in h and 'title="⌥3"' in h
    assert h.index('<h1>Sources</h1>') < h.index('class="subtabs"')   # under the page title
    assert sub_words(mk().get('/you').text) == ['Your learning', 'Profile']
    st = mk().get('/you/strengths').text
    assert sub_in_force(st) == 'Your learning'   # Strengths is part of Your learning
    assert re.search(r'class="crumbs".*?>Today<.*?>You<.*?>Your learning<', st, re.S)
    assert sub_words(mk().get('/').text) == [] and sub_words(mk().get('/learn').text) == [] and sub_words(mk().get('/c/ranking').text) == []
    assert mk().get('/library', follow_redirects=False).headers['location'] == '/concepts'

def test_old_urls_still_work(mk):
    cl = mk()
    for u in ('/journeys', '/add', '/learning', '/graph', '/sources', '/you', '/you/strengths', '/settings', '/keys'): assert cl.get(u).status_code == 200, u

def test_no_learn_query_link(mk):
    "walk_look finds Leela links by /learn?; no abhyasa link may look like one."
    assert '/learn?' not in mk().get('/').text
