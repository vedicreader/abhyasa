"Task 19c, design polish of the other pages: Add asks for one thing, Graph shows more graph, Today has an order of weight, Profile invites, and the graph shows what moved."
import re
from pathlib import Path
from walk_data import *

ROOT = Path(__file__).parents[2]/'abhyasa'
def src(p): return (ROOT/p).read_text()
def gos(h): return re.findall(r'class="go"[^>]*>(.*?)</(?:button|a)>', h)

# F9: the Add page asks for one thing

def test_add_asks_for_one_choice(mk):
    "One choice at the top; only the fields of that choice show; one main button; find concepts is a quiet action under A text."
    h = mk().get('/add').text
    assert h.count('class="modes-pick"') == 1
    for v, t in (('doc', 'A paper or document'), ('topic', 'A topic'), ('link', 'A link'), ('text', 'A text')): assert f'value="{v}"' in h and t in h
    assert re.search(r'<input type="radio" name="kind" value="doc" checked', h)
    sets = re.findall(r'<fieldset([^>]*)class="add-([a-z]+)"', h)
    assert [k for _, k in sets] == ['doc', 'topic', 'link', 'text']
    assert ['disabled' in a for a, _ in sets] == [False, True, True, True]   # the other fields do not show and do not send
    assert ' Or ' not in h and '>Or ' not in h and len(re.findall(r'<form(?![^>]*action="/search")', h)) == 1
    assert gos(h) == ['Make a walk <kbd>⌥S</kbd>']
    text = h[h.index('class="add-text"'):]
    assert 'Find concepts only' in text[:text.index('</fieldset>')]
    link = h[h.index('class="add-link"'):]; link = link[:link.index('</fieldset>')]
    assert 'It is a library or a command-line tool. Code opens in Leela.' in link and 'name="tool"' in link and h.count('name="tool"') == 1
    assert re.search(r'<details class="more"><summary>More sources</summary>.*Import vedicreader', h, re.S)
    assert 'add.js' in h

def test_add_finds_concepts_from_the_text(mk):
    "Find concepts only posts the text of the choice to the old route."
    h = mk().get('/add').text
    assert re.search(r'<button[^>]*hx-post="/add"[^>]*>Find concepts only', h) or re.search(r'hx-post="/add"', h[h.index('Find concepts only') - 300:])
    t = mk(['add']).post('/add', data=dict(text='A rank is a position.')).text
    assert '<li>' in t or 'Paste' in t

# F10: the Graph page has fewer controls than graph

def test_graph_keeps_find_layout_and_legend_open(mk):
    "Find, Layout and the legend are open; Space, Look, Show and Focus are in a closed Adjust the view."
    h = mk().get('/graph').text
    adj = re.search(r'<details class="adjust"><summary>Adjust the view</summary>(.*?)</details>', h, re.S)
    assert adj, 'no Adjust the view'
    inner = adj.group(1)
    for k in ('name="spacing"', 'name="sizeBy"', 'name="colorBy"', 'name="dueOnly"', 'name="steps"', 'name="levers"'): assert k in inner, k
    out = h.replace(adj.group(0), '')
    for k in ('name="q"', 'name="mode"', 'class="legend"'): assert k in out, k
    assert '<details class="adjust" open' not in h

def test_graph_unseen_nodes_and_labels(mk):
    "Unseen nodes are filled with --sunken and ringed with --rule; labels are 13 px in --ink2."
    js = src('blocks/graph/graph.js')
    assert "sunken: v('--sunken')" in js and "ink2: v('--ink2')" in js
    assert "n.floor ? C.floor((n.floor - 1) / 4) : C.sunken;" in js and 'hollow(n) ? C.rule' in js
    assert "'13px ' + C.serif" in js and "'12px ' + C.serif" not in js and 'C.ink2' in js

def test_empty_graph_says_what_shows_here():
    "A graph with no concepts: one line in the middle and a link to Add, and no levers."
    from abhyasa.store import temp_learning
    from abhyasa.app import mk_app
    from starlette.testclient import TestClient
    from abhyasa.llm import Fake
    cl = TestClient(mk_app(temp_learning(), Fake({}), hosts=('testserver',)))
    h = cl.get('/graph').text
    assert 'Each idea that you learn shows here. Start with a walk.' in h and 'href="/add"' in h and 'id="levers"' not in h
    assert 'class="mute empty graph-empty"' in h
    assert "'Each idea that you learn shows here. Start with a walk.'" in src('blocks/graph/graph.js')   # a subject with no concepts
