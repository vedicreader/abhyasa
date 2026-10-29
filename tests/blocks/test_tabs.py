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

def test_subtabs(mk):
    h = mk().get('/sources').text
    assert 'role="tablist"' in h and sub_words(h) == ['Concepts', 'Sources', 'Graph'] and 'aria-selected="true">Sources' in h
    assert 'title="⌥1"' in h and 'title="⌥3"' in h
    assert sub_words(mk().get('/you').text) == ['Your learning', 'Profile']
    assert 'aria-selected="true">Your learning' in mk().get('/you/strengths').text   # Strengths is part of Your learning
    assert sub_words(mk().get('/').text) == [] and sub_words(mk().get('/learn').text) == []   # Today and Learn have no sub-tabs
    assert mk().get('/library', follow_redirects=False).headers['location'] == '/concepts'

def test_old_urls_still_work(mk):
    cl = mk()
    for u in ('/journeys', '/add', '/learning', '/graph', '/sources', '/you', '/you/strengths', '/settings', '/keys'): assert cl.get(u).status_code == 200, u

def test_no_learn_query_link(mk):
    "walk_look finds Leela links by /learn?; no abhyasa link may look like one."
    assert '/learn?' not in mk().get('/').text
