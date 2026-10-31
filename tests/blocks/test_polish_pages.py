"Task 19c, the other pages: Add finds concepts, Home, Your learning, search and Profile."
import re
from walk_data import *

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

# F12: Home

def test_today_review_line_counts_due_ideas(mk, lr):
    "The review line says how many ideas are due, with Start; with nothing due it names the next idea."
    import time
    lr.update('ranking', seen=1, due=time.time() - 60, floor=1)
    h = mk().get('/').text
    line = re.search(r'<p class="review-line">(.*?)</p>', h, re.S).group(1)
    assert 'Review: 1 idea is due' in line
    assert 'Start' in h[h.index('class="review-line"'):][:900]
    assert '0 due for review' not in h

def test_your_learning_has_the_week_and_subjects(mk, lr):
    "With no answer yet, Your learning has one line and the subjects; after a review it has the week."
    cl = mk(); h = cl.get('/learning').text
    assert 'Nothing yet. Do a walk or a review.' in h and 'This week' not in h and '>Subjects<' in h and '2 concepts' in h
    lr.update('ranking', seen=1, floor=1)
    assert 'This week' in cl.get('/learning').text

# Search shows each hit by its kind

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

def test_your_learning_leaves_out_closed_empty_sessions(mk, lr):
    "A session with no answers that is closed does not show; an open one does, so you can continue it."
    lr.log_session('gone1', '0 of 0 passed.', start=1., updated=1., log=[], ended=2.)
    lr.log_session('open1', 'An open session.', start=3., updated=3., log=[])
    h = mk().get('/learning').text
    i = h.find('gone1'); assert i < 0, h[i - 300:i + 40]
    assert 'no answers yet · open' in h

# F13: Profile

def test_empty_profile_hides_what_has_no_data(mk, lr):
    "An empty profile with no answers has no calibration, no Learn about me now and no Clear; a known one has them."
    h = mk().get('/you').text
    for x in ('How well you know what you know', 'Learn about me now', 'Clear what abhyasa knows about you'): assert x not in h, x
    assert 'This stays in your vault on this Mac.' in h
    lr.set_profile(by='you', why='test', background=['nurse'])
    h = mk().get('/you').text
    for x in ('How well you know what you know', 'Learn about me now', 'Clear what abhyasa knows about you'): assert x in h, x
