"The shared editor core: the Undo of a walk path, the Undo bar, the history list, the editor list, a live field and the rewrite prompt."
from fasthtml.common import to_xml, Input
from abhyasa.edit import restore_steps, undo_line, CODE_GONE
from abhyasa.core.edit import UndoBar, HistoryList, EditList, Live, edit_keys, edit_assets, EDIT_BAR_SECS
from abhyasa.core.keys import KEYS

def test_undo_keeps_run_fields_and_research():
    "The walk keeps its progress and the passage that research found after the snapshot; the order and the content come back."
    before = [dict(slug='a', read=dict(text=''), check=dict(kind='short')), dict(slug='b', read=dict(text='p'))]
    now = [dict(slug='b', read=dict(text='p'), done=dict(outcome='solid'), qid='q7', read_at=5.),
           dict(slug='a', read=dict(text='w', researched=True), check=dict(kind='demo'), note='N'), dict(slug='c')]
    out = restore_steps(before, now)
    assert [s['slug'] for s in out] == ['a', 'b']
    assert out[0]['read']['text'] == 'w' and out[0]['check'] == dict(kind='short') and 'note' not in out[0]   # the note is content: Undo takes back the new note
    assert out[1]['done'] == dict(outcome='solid') and out[1]['qid'] == 'q7' and out[1]['read_at'] == 5.

def test_undo_gives_back_the_old_note():
    assert restore_steps([dict(slug='a', note='Old.')], [dict(slug='a', note='New.', qid='q1')]) == [dict(slug='a', note='Old.', qid='q1')]

def test_undo_keeps_the_code_of_a_check_made_again():
    "A check made again after the change keeps its new code, and the editor gets one plain line. The same check gets its old code back."
    before, now = [dict(slug='a', qid='q1', code=dict(stub='old'), status='todo')], [dict(slug='a', qid='q2', code=dict(stub='new'), status='skipped')]
    assert restore_steps(before, now) == [dict(slug='a', qid='q2', code=dict(stub='new'), status='todo')]
    assert undo_line(before, now) == CODE_GONE == 'This check was made again after the change. Undo cannot bring the old code back.'
    same = [dict(slug='a', qid='q1', code=dict(stub='new'))]
    assert restore_steps(before, same)[0]['code'] == dict(stub='old') and undo_line(before, same) == ''

def test_undo_bar_is_polite_and_names_the_change():
    h = to_xml(UndoBar('Moved “Softmax” to slide 5.', '/t/x/undo', '/t/x/history'))
    assert 'aria-live="polite"' in h and 'Moved “Softmax” to slide 5.' in h and '⌘Z' in h and 'data-secs="8"' in h
    assert 'hx-swap-oob="innerHTML"' in h and 'hx-post="/t/x/undo"' in h and 'href="/t/x/history"' in h

def test_undo_bar_posts_its_step_and_is_empty_on_the_page():
    "Undo posts the id of its change, so an old bar does nothing. The page has the empty bar, so the live region is there first."
    assert '{"step": "ab12"}' in to_xml(UndoBar('Removed “Softmax”.', '/u', '/h', step='ab12'))
    h = to_xml(UndoBar(oob=False))
    assert 'id="undo-bar"' in h and 'Undo' not in h and 'hx-swap-oob' not in h and EDIT_BAR_SECS == 8

def test_history_list_says_who_and_restores():
    rows = [dict(id='e2', at=1e9, what='Rewrote the points of slide 5: simpler.', who='tutor'), dict(id='e1', at=1e9, what='Moved “A” to slide 2.', who='you')]
    h = to_xml(HistoryList(rows, '/t/x/restore'))
    assert h.count('Restore this version') == 2 and '>tutor<' in h and '>you<' in h and '{"id": "e1"}' in h
    assert 'No changes yet.' in to_xml(HistoryList([], '/r'))

def test_edit_list_rows():
    "Each row has a grip that a screen reader skips, a number, the title, a short line, Edit (E) and the touch moves. The ends cannot move out."
    rows = [dict(id='s1', title='Softmax', line='passage · 5 min', post='/t/x/s/s1'), dict(id='s2', title='Scaling', post='/t/x/s/s2', open=True)]
    h = to_xml(EditList(rows, 'talk', add=[Input(type='button', value='Add a slide', data_key='A')], id='slides'))
    assert 'class="edit-list talk"' in h and 'data-edit="1"' in h and h.count('class="grip"') == 2 and 'aria-hidden="true"' in h
    assert '>Softmax<' in h and 'passage · 5 min' in h and h.count('<kbd>E</kbd>') == 2 and 'data-post="/t/x/s/s1"' in h
    assert h.count('Move up') == 2 and h.count('disabled') == 2 and '<details open' in h and 'data-key="A"' in h

def test_live_field_saves_after_600_ms():
    h = to_xml(Live('title', Input(value='Softmax')))
    assert 'hx-trigger="input changed delay:600ms, blur"' in h and 'name="title"' in h and 'hx-swap="none"' in h and 'data-live="1"' in h
    assert 'hx-post="/s1"' in to_xml(Live('notes', Input(), '/s1'))

def test_editor_keys_are_for_the_editor_pages_only():
    "The keys table gets the editor keys from the tasks that bind them. The editor assets are not in every page."
    assert edit_keys('Walk path', ('P', 'M')) == [('Walk path', 'P', 'Split the row in two'), ('Walk path', 'M', 'Merge the row with the next row')]
    assert not any(g == 'Walk path' for g, *_ in KEYS) and len(edit_assets()) == 2

def test_rewrite_prompt_is_in_settings(mk):
    assert 'Rewrite with an instruction' in mk().get('/settings').text

def test_editor_assets_are_not_in_every_page(mk):
    assert 'edit.js' not in mk().get('/').text
