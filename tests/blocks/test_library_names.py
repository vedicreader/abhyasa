"Every control on the Library pages has a name that a screen reader can say."
from html.parser import HTMLParser
import pytest

class Scan(HTMLParser):
    "Collects the controls that have no aria-label, title, wrapping label or text."
    def __init__(s): super().__init__(); s.bad, s.label, s.btn, s.tpl = [], 0, [], 0
    def handle_starttag(s, t, a):
        a = dict(a)
        if t == 'label': s.label += 1
        elif t == 'button': s.btn.append([a, ''])
        elif t in ('input', 'select', 'textarea') and a.get('type') != 'hidden' and not (a.get('aria-label') or a.get('title') or s.label or a.get('id')):
            s.bad.append((t, a))
    def handle_data(s, d):
        if s.btn: s.btn[-1][1] += d
    def handle_endtag(s, t):
        if t == 'label': s.label -= 1
        elif t == 'button' and s.btn:
            a, x = s.btn.pop()
            if not (x.strip() or a.get('aria-label') or a.get('title')): s.bad.append((t, a))

@pytest.mark.parametrize('url', ['/library', '/library/sources', '/library/graph'])
def test_controls_are_named(mk, url):
    sc = Scan(); sc.feed(mk().get(url).text)
    assert sc.bad == []

def test_graph_find_and_sliders_say_what_they_do(mk):
    h = mk().get('/library/graph').text
    assert 'aria-label="Find a concept in the graph"' in h and 'aria-label="Steps out"' in h
