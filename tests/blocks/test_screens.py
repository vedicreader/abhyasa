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

# The walk step: with a talk, the rail shows one way to the talk; Make it again and Make a second talk are under More, and still post.

def test_step_rail_puts_talk_again_under_more(mk, talk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); tid = make_talk(cl, jid)
    rail = soup(cl.get(f'/w/{jid}/1').text).select_one('aside')
    more = rail.select_one('details.talk-more')
    assert rail.select_one(f'a[href="/t/{tid}"]').get_text().strip() == 'Open the talk'
    assert 'Make the talk again' in more.get_text() and 'Make a second talk' in more.get_text()
    assert more.select_one('input[name="again"]')['value'] == '1' and all(f['hx-post'] == '/talk/new' for f in more.select('form'))

# The plan of the walk: one short lead; the rest of the help and the list keys are in closed parts.

def test_plan_editor_folds_help_and_keys(mk, talk_fake, lr):
    cl = mk(); jid = walk(cl, lr)
    s = soup(cl.get(f'/w/{jid}/edit').text)
    assert s.h1.get_text().endswith('the plan of the walk')
    about = s.select_one('main details.about')
    assert about and about.summary.get_text() == 'About this' and 'removed idea keeps your answers' in about.get_text() and not about.has_attr('open')
    keys = s.select_one('main details.more .keys-line')
    assert keys and 'merge' in keys.get_text()
