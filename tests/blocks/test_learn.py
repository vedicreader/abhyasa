"Home: your walks, Teach with your talks, and Start something new; and the walk row."
from talk_data import *
from bs4 import BeautifulSoup

def paper_walk(cl, lr):
    "A walk from the paper, prepared for a talk; return its id."
    return prep_walk(lr, walk(cl, lr))

def first_row(h):
    "The first walk row of the page `h`."
    return BeautifulSoup(h, 'html.parser').select_one('li.jrow')

# Home lists the walks and the talks; a talk has an Edit link and a quiet Present.

def test_home_lists_walks_talks_and_start(mk, lr, talk_fake):
    cl = mk(); jid = paper_walk(cl, lr); tid = make_talk(cl, jid)
    h = cl.get('/').text
    assert f'href="/t/{tid}"' in h and '>paper<' in h and '>Edit<' in h
    assert f'action="/t/{tid}/start"' in h   # a quiet Present starts the talk
    assert 'data-part="teach"' in h and '>Teach<' in h and 'data-part="start"' in h   # Teach and the Start box are on Home
    assert 'Your talks' not in cl.get('/learning').text   # the talks moved from Your learning

# A row links to its talk, and its button says what comes next.

def test_row_says_open_the_talk_after_a_talk(mk, lr, talk_fake):
    cl = mk(); jid = paper_walk(cl, lr); tid = make_talk(cl, jid)
    row = first_row(cl.get('/').text)
    assert row.select_one('.quiet').get_text().strip() == 'Open the talk' and row.select_one('.quiet')['href'] == f'/t/{tid}'
    assert len(row.select('a.btn, button.go')) == 1 and 'Make it again' not in str(row)

def test_row_says_start_the_walk_before_it_starts(mk, lr, talk_fake):
    cl = mk(); jid = paper_walk(cl, lr)
    assert first_row(cl.get('/').text).select_one('a.btn').get_text().strip() == 'Start the walk'
    cl.post(f'/w/{jid}/start')
    assert first_row(cl.get('/').text).select_one('a.btn').get_text().strip() == 'Continue'

def test_old_list_routes_go_home(mk):
    "The old Learn tab and the old list of walks go to Home."
    cl = mk()
    r = cl.get('/learn', follow_redirects=False)
    assert r.status_code == 301 and r.headers['location'] == '/'
    r = cl.get('/journeys', follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == '/'
