"Task 19c, the other pages: Add asks for one thing, an empty Graph, Today has an order of weight, and Profile invites."
import re
from walk_data import *
def gos(h): return re.findall(r'class="(?:btn )?go"[^>]*>(.*?)</(?:button|a)>', h)

# F9: Find concepts only

def test_add_finds_concepts_from_the_text(mk, walk_fake, lr):
    "Find concepts only shows for pasted text, with a Subject box; it posts to /add, and the concepts get that subject. A vault document works too."
    f = mk().get('/learn/read', params=dict(q='A rank is a position.\nRanks are places.')).text
    assert 'Find concepts only' in f and 'name="subject"' in f and 'hx-post="/add"' in f
    t = mk(['add']).post('/add', data=dict(text='A rank is a position.', subject='ranks')).text
    assert '<li>' in t and all(c.subject == 'ranks' for c in lr.concepts() if c.slug not in ('ranking', 'reciprocal-rank-fusion'))
    did = add_paper(lr)
    t = mk(['add']).post('/add', data=dict(ref=did, subject='papers')).text
    assert '<li>' in t and any(c.subject == 'papers' for c in lr.concepts())

# F10: an empty graph

def test_empty_graph_says_what_shows_here():
    "A graph with no concepts: one line in the middle and a link to Add, and no levers."
    from abhyasa.store import temp_learning
    from abhyasa.app import mk_app
    from starlette.testclient import TestClient
    from abhyasa.llm import Fake
    cl = TestClient(mk_app(temp_learning(), Fake({}), hosts=('testserver',)))
    h = cl.get('/graph').text
    assert 'Each idea that you learn shows here. Start with a walk.' in h and 'href="/add"' in h and 'id="levers"' not in h

# F12: Today has an order of weight

def today_order(h, *marks):
    at = [h.find(m) for m in marks]
    assert all(a >= 0 for a in at), [m for m, a in zip(marks, at) if a < 0]
    return at == sorted(at)

def test_today_has_an_order_of_weight(mk, walk_fake, lr):
    "The order is the feature: the Continue card, then one review line, then at most three walks with See all and Start something new; no goal box, no week or subjects."
    cl = mk()
    for i in range(5): walk(cl, lr)
    lr.update('ranking', seen=1, floor=1)   # a seen idea: the strengths link shows
    sid = cl.post('/start', data={}, follow_redirects=False).headers['location'].split('/')[-1]; cl.get(f'/s/{sid}')   # an open session: the Continue card
    h = cl.get('/').text
    assert today_order(h, 'Continue where you stopped', 'class="review-line"', 'Your walks', 'See all 5 in Learn', 'href="/learn#start"')
    assert 'Review and practice' not in h and 'This week' not in h and '>Subjects<' not in h
    assert h.count('class="jrow lrow"') == 3 and 'What do you want to learn?' not in h
    foot = h[h.index('class="mute foot"'):]
    assert 'Your strengths</a>' in foot and 'href="/keys"' in foot and '<kbd>⌥F</kbd>' in foot

def test_today_review_line_counts_due_ideas(mk, lr):
    "The review line says how many ideas are due, with Start; with nothing due it names the next idea."
    import time
    lr.update('ranking', seen=1, due=time.time() - 60, floor=1)
    h = mk().get('/').text
    line = re.search(r'<p class="review-line">(.*?)</p>', h, re.S).group(1)
    assert 'Review: 1 idea is due' in line
    assert 'Start' in h[h.index('class="review-line"'):][:900]
    assert '0 due for review' not in h

def test_today_with_no_walk_links_to_start(mk):
    h = mk().get('/').text
    assert 'What do you want to learn?' not in h and 'No walks yet' in h and 'href="/learn#start"' in h

def test_your_learning_has_the_week_and_subjects(mk, lr):
    "With no answer yet, Your learning has one line and the subjects; after a review it has the week."
    cl = mk(); h = cl.get('/learning').text
    assert 'Nothing yet. Do a walk or a review.' in h and 'This week' not in h and '>Subjects<' in h and '2 concepts' in h
    lr.update('ranking', seen=1, floor=1)
    assert 'This week' in cl.get('/learning').text

# F13: Profile is not a wall of empty boxes

def test_empty_profile_is_one_invitation(mk):
    "An empty profile: one card with Start ⌥S; the fields are under a closed Edit by hand; no empty change log."
    h = mk().get('/you').text
    assert 'Tell abhyasa about you.' in h and 'Four short questions, by voice or text. About two minutes.' in h
    assert gos(h) == ['Start <kbd>⌥S</kbd>'] and 'href="/you/start"' in h
    by_hand = h[h.index('<summary>Edit by hand</summary>'):]
    assert 'name="background"' in by_hand and re.search(r'<details[^>]*>\s*<summary>Edit by hand', h) and not re.search(r'<details[^>]* open[^>]*>\s*<summary>Edit by hand', h)
    assert 'No changes yet.' not in h

def test_known_profile_shows_the_fields(mk, lr):
    lr.set_profile(by='you', why='test', background=['nurse'])
    h = mk().get('/you').text
    assert 'invite' not in h and 'Edit by hand' not in h and 'name="background"' in h and gos(h) == ['Save <kbd>⌥S</kbd>']

# The whole-app pass

def test_concept_page_has_no_none_lines(mk):
    "A concept with no links and no attempts: one muted line for each, not three `none` lines; the journey part has no gap at the top."
    h = mk().get('/c/ranking').text
    assert '>none<' not in h and '>none yet<' not in h
    assert 'You did not answer a question on this idea yet.' in h

def test_your_learning_counts_with_plurals(mk, lr):
    cl = mk(); sid = cl.post('/start', data={}, follow_redirects=False).headers['location'].split('/')[-1]; cl.get(f'/s/{sid}')
    h = cl.get('/learning').text
    assert '0 questions in the last seven days' in h   # n_of: 1 question, 2 questions
    assert '0 of 0 passed' not in h and 'no answers yet · open' in h


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
    assert 'Nothing found.' in to_xml(Elsewhere([]))

def test_session_rail_names_this_session():
    "With no earlier question, the rail says This session; with some, Earlier questions · N (not the current one)."
    from fasthtml.common import to_xml
    from fastcore.utils import AttrDict
    from abhyasa.blocks.session.ui import Rail
    q = AttrDict(id='q1', name='Ranking', depth=2)
    assert '<summary>This session</summary>' in to_xml(Rail('s1', current=q))
    assert '<summary>Earlier questions · 1</summary>' in to_xml(Rail('s1', past=[AttrDict(id='q0', name='Softmax', depth=1)], current=q))

def test_today_has_one_way_to_continue_a_walk(mk, walk_fake, lr):
    "No walk line and no side walk line over the journeys; the profile line is in the foot, not over the card."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    h = cl.get('/').text
    assert 'Continue the walk:' not in h and 'Unfinished side walk' not in h and 'walk-next' not in h
    assert 'href="/you/start">Tell abhyasa about you</a>' in h[h.index('class="mute foot"'):]
    assert h.count('Tell abhyasa about you') == 1

def test_your_learning_leaves_out_closed_empty_sessions(mk, lr):
    "A session with no answers that is closed does not show; an open one does, so you can continue it."
    lr.log_session('gone1', '0 of 0 passed.', start=1., updated=1., log=[], ended=2.)
    lr.log_session('open1', 'An open session.', start=3., updated=3., log=[])
    h = mk().get('/learning').text
    i = h.find('gone1'); assert i < 0, h[i - 300:i + 40]
    assert 'no answers yet · open' in h

def test_empty_profile_hides_what_has_no_data(mk, lr):
    "An empty profile with no answers has no calibration, no Learn about me now and no Clear; a known one has them."
    h = mk().get('/you').text
    for x in ('How well you know what you know', 'Learn about me now', 'Clear what abhyasa knows about you'): assert x not in h, x
    assert 'This stays in your vault on this Mac.' in h
    lr.set_profile(by='you', why='test', background=['nurse'])
    h = mk().get('/you').text
    for x in ('How well you know what you know', 'Learn about me now', 'Clear what abhyasa knows about you'): assert x in h, x
