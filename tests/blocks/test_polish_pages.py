"Task 19c, design polish of the other pages: Add asks for one thing, Graph shows more graph, Today has an order of weight, Profile invites, and the graph shows what moved."
import re
from pathlib import Path
from walk_data import *

ROOT = Path(__file__).parents[2]/'abhyasa'
def src(p): return (ROOT/p).read_text()
def gos(h): return re.findall(r'class="(?:btn )?go"[^>]*>(.*?)</(?:button|a)>', h)

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

def test_add_finds_concepts_from_the_text(mk, walk_fake, lr):
    "Find concepts only is in A paper and in A text, each with a Subject box; it posts to /add, and the concepts get that subject."
    h = mk().get('/add').text
    for k in ('doc', 'text'):
        f = h[h.index(f'class="add-{k}"'):]; f = f[:f.index('</fieldset>')]
        assert 'Find concepts only' in f and 'name="subject"' in f and 'hx-post="/add"' in f, k
    t = mk(['add']).post('/add', data=dict(text='A rank is a position.', subject='ranks')).text
    assert '<li>' in t and all(c.subject == 'ranks' for c in lr.concepts() if c.slug not in ('ranking', 'reciprocal-rank-fusion'))
    did = add_paper(lr)
    t = mk(['add']).post('/add', data=dict(ref=did, subject='papers')).text
    assert '<li>' in t and any(c.subject == 'papers' for c in lr.concepts())

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

# Magic touch 5: the graph grows as you learn

def test_graph_marks_what_moved_since_the_last_visit():
    "graph.js keeps the floors of the last visit, pulses each moved idea once, and says how many moved; with no motion, only the line."
    js, css = src('blocks/graph/graph.js'), src('blocks/graph/graph.css')
    assert "'abhyasa.graph.seen'" in js and 'abhyasaMotion()' in js
    assert "went up since your last visit." in js and "n.floor > before[n.id]" in js and "n === 1 ? 'idea' : 'ideas'" in js
    assert 'PULSE = 600' in js
    assert '#graph .moved' in css

# F12: Today has an order of weight

def today_order(h, *marks):
    at = [h.find(m) for m in marks]
    assert all(a >= 0 for a in at), [m for m, a in zip(marks, at) if a < 0]
    return at == sorted(at)

def test_today_has_an_order_of_weight(mk, walk_fake, lr):
    "Continue card, then one review line with Start, then at most three journeys with See all, then the goal closed to one line; no week or subjects."
    cl = mk()
    for i in range(5): walk(cl, lr)
    lr.update('ranking', seen=1, floor=1)   # a seen idea: the strengths link shows
    sid = cl.post('/start', data={}, follow_redirects=False).headers['location'].split('/')[-1]; cl.get(f'/s/{sid}')   # an open session: the Continue card
    h = cl.get('/').text
    assert today_order(h, 'Continue where you stopped', 'class="review-line"', 'Your journeys', 'See all 5 journeys', 'What do you want to learn?')
    assert 'Review and practice' not in h and 'This week' not in h and '>Subjects<' not in h
    assert h.count('class="jrow"') == 3
    assert re.search(r'<details class="goal-fold"><summary>What do you want to learn\?</summary>', h)
    assert re.search(r'<p class="mute foot">.*Your strengths</a> <kbd>⌥G</kbd> · <a href="/keys">Keyboard shortcuts</a> <kbd>⌥F</kbd>', h, re.S)

def test_today_review_line_counts_due_ideas(mk, lr):
    "The review line says how many ideas are due, with Start; with nothing due it names the next idea."
    import time
    lr.update('ranking', seen=1, due=time.time() - 60, floor=1)
    h = mk().get('/').text
    line = re.search(r'<p class="review-line">(.*?)</p>', h, re.S).group(1)
    assert 'Review: 1 idea is due' in line
    assert 'Start' in h[h.index('class="review-line"'):][:900]
    assert '0 due for review' not in h

def test_today_goal_is_open_with_no_journey(mk):
    h = mk().get('/').text
    assert 'goal-fold' not in h and 'What do you want to learn?' in h and 'No journeys yet' in h

def test_your_learning_has_the_week_and_subjects(mk):
    h = mk().get('/learning').text
    assert 'This week' in h and '>Subjects<' in h and '2 concepts' in h

# F13: Profile is not a wall of empty boxes

def test_empty_profile_is_one_invitation(mk):
    "An empty profile: one raised card with Start ⌥S; the fields are under a closed Edit by hand; no empty change log."
    h = mk().get('/you').text
    card = re.search(r'<section class="raised invite">(.*?)</section>', h, re.S)
    assert card and 'Tell abhyasa about you.' in card.group(1) and 'Four short questions, by voice or text. About two minutes.' in card.group(1)
    assert gos(h) == ['Start <kbd>⌥S</kbd>'] and 'href="/you/start"' in card.group(1)
    assert re.search(r'<details class="more by-hand"><summary>Edit by hand</summary>.*name="background"', h, re.S)
    assert 'No changes yet.' not in h

def test_known_profile_shows_the_fields(mk, lr):
    lr.set_profile(by='you', why='test', background=['nurse'])
    h = mk().get('/you').text
    assert 'invite' not in h and 'Edit by hand' not in h and 'name="background"' in h and gos(h) == ['Save <kbd>⌥S</kbd>']

def test_speak_sits_in_the_label_row():
    "A box with data-mic=label gets its Speak in the label row; only the first one names ⌥D."
    js, css = src('blocks/voice/voice.js'), src('blocks/voice/voice.css')
    assert "box.dataset.mic === 'label'" in js and 'mic in-label' in js and '⌥D' in js
    assert '.mic.in-label' in css
    assert "data_mic='label'" in src('blocks/profile/ui.py') and "data_mic='label'" in src('blocks/journeys/ui.py')

# The whole-app pass

def test_concept_page_has_no_none_lines(mk):
    "A concept with no links and no attempts: one muted line for each, not three `none` lines; the journey part has no gap at the top."
    h = mk().get('/c/ranking').text
    assert '>none<' not in h and '>none yet<' not in h
    assert 'You did not answer a question on this idea yet.' in h and 'class="mute empty"' in h
    assert '.refs .in-journeys:not(:first-child)' in src('blocks/concepts/concepts.css')

def test_your_learning_counts_with_plurals(mk, lr):
    cl = mk(); sid = cl.post('/start', data={}, follow_redirects=False).headers['location'].split('/')[-1]; cl.get(f'/s/{sid}')
    h = cl.get('/learning').text
    assert '0 questions in the last seven days' in h   # n_of: 1 question, 2 questions
    assert '0 of 0 passed' not in h and 'no answers yet · open' in h


def test_graph_fits_again_at_a_new_width():
    "The saved camera keeps the width; at another width the graph fits again, so labels do not go past the edge."
    js = src('blocks/graph/graph.js')
    assert 'w: W}' in js and 'Math.abs((cam.w || W) - W) < 40' in js

def test_empty_part_of_refs_keeps_the_section_gap():
    assert '.refs > p.empty:not(:first-child) { margin-top: var(--s6); }' in src('core/base.css')

# Fix round 1: search shows each hit by its kind

def test_search_shows_hits_by_kind(mk, walk_fake, lr):
    "No raw index text, no stats, no session with no answers, no slot that is not filled; each hit has a plain title."
    cl = mk(); jid = walk(cl, lr)
    sid = cl.post('/start', data={}, follow_redirects=False).headers['location'].split('/')[-1]; cl.get(f'/s/{sid}')   # a session with no answers
    lr.record('ranking', 'What does a rank tell you?', answer='its position', correct=True)
    import abhyasa.method; lr.set_stats(rank=dict(words=[1, 1]))   # the method stats doc
    h = cl.get('/search?q=rank').text
    body = h[h.index('<main'):]
    for bad in ('Subject:', 'Journey:', 'Goal:', 'Steps:', 'Question:', 'Answer:', 'Also:', 'Concepts:', 'How you learn', '0 of 0 passed', 'Session '):
        assert bad not in body, bad
    assert not re.search(r'\{[\w.]+\}', re.sub(r'<script.*?</script>', '', body, flags=re.S))
    assert 'class="hit"' in body and 'An idea · ml' in body and 'What does a rank tell you?' in body and 'Your answer' in body
    from fasthtml.common import to_xml
    from abhyasa.blocks.search.app import Elsewhere
    assert 'class="mute empty">Nothing found.<' in to_xml(Elsewhere([]))

def test_session_rail_names_this_session():
    "With no earlier question, the rail says This session; with some, Earlier questions · N (not the current one)."
    from fasthtml.common import to_xml
    from fastcore.utils import AttrDict
    from abhyasa.blocks.session.ui import Rail
    q = AttrDict(id='q1', name='Ranking', depth=2)
    assert '<summary>This session</summary>' in to_xml(Rail('s1', current=q))
    assert '<summary>Earlier questions · 1</summary>' in to_xml(Rail('s1', past=[AttrDict(id='q0', name='Softmax', depth=1)], current=q))
