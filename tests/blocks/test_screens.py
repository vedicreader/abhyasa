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

# A concept page: Learn this is the one button; Rename or move and Add an explainer video are closed parts that still post.

def test_concept_page_folds_rename_move_and_video(mk, lr):
    lr.put('Ranking', 'Order items by a score.', 'ml')
    s = soup(mk().get('/c/ranking').text)
    assert [b.get_text(' ').split()[0] for b in s.select('main .go')] == ['Learn']
    edit = s.select_one('details.concept-edit')
    assert edit.summary.get_text() == 'Rename or move' and not edit.has_attr('open')
    assert edit.select_one('#group-field')['hx-post'] == '/c/ranking/group' and edit.select_one('#name-field')['hx-post'] == '/c/ranking/rename'
    vid = s.select_one('#guide-video-slot details')
    assert vid.summary.get_text() == 'Add an explainer video' and vid.select_one('form.guide-paste')['hx-post'] == '/guide/video/ranking'

def test_concept_rename_still_works(mk, lr):
    lr.put('Ranking', 'Order items by a score.', 'ml')
    cl = mk(); cl.post('/c/ranking/rename', data=dict(name='Rank order'))
    assert lr.concept('ranking').name == 'Rank order'

def test_video_tools_open_after_a_message(mk, lr):
    lr.put('Ranking', 'Order items by a score.', 'ml')
    h = mk().post('/guide/video/ranking/drop').text
    assert 'The video is gone' in h and soup(h).select_one('details').has_attr('open')

# A vault document: Learn as a walk is the one button; Only find its ideas stays, as a quiet action on the same route as before.

def test_vault_doc_has_one_main_and_a_quiet_find(mk, lr):
    d = lr.vault.add([(0, 'Ranking orders items by a score.')], 'Ranking notes', source='/tmp/rank.txt', kind='text')
    s = soup(mk().get(f"/v/store/{d['doc_id']}").text)
    mains = s.select('main .go')
    assert len(mains) == 1 and mains[0].get_text().strip() == 'Learn as a walk' and mains[0]['hx-post'] == '/walk/new'
    find = next(b for b in s.select('main button') if b.get_text().strip() == 'Only find its ideas')
    assert find['hx-post'] == f"/v/store/{d['doc_id']}/learn"
    assert s.select_one('main .lbl').get_text() == 'Your vault' and 'Concepts linked here' not in s.get_text()

# The talk editor: Present is the one button; the long help and the list keys are in closed parts.

def test_talk_editor_folds_help_and_keys(mk, talk_fake, lr):
    cl = mk(); jid = walk(cl, lr); tid = make_talk(cl, jid)
    s = soup(cl.get(f'/t/{tid}').text)
    assert [b.get_text(' ').split()[0] for b in s.select('main .go')] == ['Present']
    about = s.select_one('main details.about')
    assert about and 'speaker note is for you only' in about.get_text() and not about.has_attr('open')
    assert 'duplicate' in s.select_one('main details.more .keys-line').get_text()

# Sources: one closed part, Add more sources, holds the rare imports; its buttons still post.

def test_sources_fold_add_more(mk):
    s = soup(mk().get('/sources').text)
    more = s.select_one('section.sources-more > details.more')
    assert more.summary.get_text() == 'Add more sources' and not more.has_attr('open')
    assert more.select_one('button[hx-post="/add/vedicreader"]') and more.select_one('button[hx-post="/sources/index/ramabana"]')
