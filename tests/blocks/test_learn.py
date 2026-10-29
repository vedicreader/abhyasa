"The Learn page: your walks, your talks and Start something new; and the walk row that Today and Learn share."
from talk_data import *
from bs4 import BeautifulSoup

def paper_walk(cl, lr):
    "A walk from the paper, prepared for a talk; return its id."
    return prep_walk(lr, walk(cl, lr))

def side_walk(lr, jid):
    "A side walk of walk `jid`, opened from its first idea; return its id."
    j = lr.journey(jid)
    return lr.put_journey({**j, 'id': 'side-walk-ab12', 'title': 'Side walk', 'depth': 1, 'parent': dict(walk=jid, step=0)}).id

def first_row(h):
    "The first walk row of the page `h`."
    return BeautifulSoup(h, 'html.parser').select_one('li.jrow')

# The page has three parts in order, and a talk shows with an Edit link and a walk with its pill.

def test_learn_lists_walks_talks_and_start(mk, lr, talk_fake):
    cl = mk(); jid = paper_walk(cl, lr); tid = make_talk(cl, jid)
    h = cl.get('/learn').text
    assert h.index('Your walks') < h.index('Your talks') < h.index('Start something new')
    assert f'href="/t/{tid}"' in h and '>paper<' in h and '>Edit<' in h
    assert f'action="/t/{tid}/start"' in h   # a quiet Present starts the talk
    assert 'Your talks' not in cl.get('/learning').text   # the talks moved from Your learning

# A row has the title, the progress and the step to do now on one line, one Continue, a quiet Present and its side walks folded under it.

def test_walk_row_one_line_one_continue(mk, lr, talk_fake):
    cl = mk(); jid = paper_walk(cl, lr); side_walk(lr, jid)
    row = first_row(cl.get('/learn').text)
    head = row.select_one('.jrow-head').get_text(' ')
    assert 'of' in head and 'ideas' in head and 'Now:' in head
    assert len(row.select('a.btn, button.go')) == 1
    assert row.select_one('.quiet').get_text().strip() in ('Present', 'Open the talk')
    assert row.select_one('details.side-walks summary').get_text().startswith('1 side walk')
    assert 'Make it again' not in str(row) and 'Present this walk' not in str(row)

def test_row_says_open_the_talk_after_a_talk(mk, lr, talk_fake):
    cl = mk(); jid = paper_walk(cl, lr); tid = make_talk(cl, jid)
    row = first_row(cl.get('/learn').text)
    assert row.select_one('.quiet').get_text().strip() == 'Open the talk' and row.select_one('.quiet')['href'] == f'/t/{tid}'
    assert len(row.select('a.btn, button.go')) == 1 and 'Make it again' not in str(row)

def test_row_says_start_the_walk_before_it_starts(mk, lr, talk_fake):
    cl = mk(); jid = paper_walk(cl, lr)
    assert first_row(cl.get('/learn').text).select_one('a.btn').get_text().strip() == 'Start the walk'
    cl.post(f'/w/{jid}/start')
    assert first_row(cl.get('/learn').text).select_one('a.btn').get_text().strip() == 'Continue'

# Today keeps a short list of rows, and links to Learn.

def test_today_shows_rows_and_links(mk, lr, talk_fake):
    cl = mk(); paper_walk(cl, lr)
    h = cl.get('/').text
    assert 'Your walks' in h and 'href="/learn#start"' in h and 'Start something new' in h
    assert 'What do you want to learn?' not in h   # the goal box left Today

def test_old_list_routes_redirect_to_learn(mk):
    r = mk().get('/journeys', follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == '/learn'

def test_learn_empty(mk):
    h = mk().get('/learn').text
    assert 'No walks yet. Paste something below.' in h and 'Your talks' not in h and 'id="start"' in h
