"Easier screens (0.0.15): each main screen has one next step, and a rare action that moved is still there by its key and its More menu."
from talk_data import *
from bs4 import BeautifulSoup

def soup(h): return BeautifulSoup(h, 'html.parser')

# Today: the reason for the next idea is one plain sentence, and the walk rows leave the one button to the top of the page.

def test_today_says_why_in_plain_words(mk, lr):
    lr.put('Ranking', 'Order items by a score.', 'ml')
    h = mk().get('/').text
    assert 'You know the ideas that it needs.' in h and 'frontier' not in h and 'prereqs' not in h

def test_today_rows_have_no_button(mk, lr, talk_fake):
    cl = mk(); walk(cl, lr)
    rows = soup(cl.get('/').text).select('li.jrow')
    assert rows and not any(r.select('a.btn') for r in rows)
    assert rows[0].select_one('a.onward').get_text().startswith('Start the walk')   # the way on is still a link on the row
