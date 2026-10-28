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
