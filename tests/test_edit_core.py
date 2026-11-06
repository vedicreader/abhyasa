"The shared editor core: the Undo of a walk path and the history list."
from fasthtml.common import to_xml
from abhyasa.path import restore_steps, undo_line, CODE_GONE
from abhyasa.core.edit import HistoryList

def test_undo_keeps_run_fields_and_research():
    "The walk keeps its progress and the passage that research found after the snapshot; the order and the content come back."
    before = [dict(slug='a', read=dict(text=''), check=dict(kind='short')), dict(slug='b', read=dict(text='p'))]
    now = [dict(slug='b', read=dict(text='p'), done=dict(outcome='solid'), qid='q7', read_at=5.),
           dict(slug='a', read=dict(text='w', researched=True), check=dict(kind='demo'), note='N'), dict(slug='c')]
    out = restore_steps(before, now)
    assert [s['slug'] for s in out] == ['a', 'b']
    assert out[0]['read']['text'] == 'w' and out[0]['check'] == dict(kind='short') and 'note' not in out[0]   # the note is content: Undo takes back the new note
    assert out[1]['done'] == dict(outcome='solid') and out[1]['qid'] == 'q7' and out[1]['read_at'] == 5.

def test_undo_keeps_what_the_walk_wrote_after_the_snapshot():
    "Undo gives back only the fields that the editor changes. A side walk, a notebook, a Leela stamp and the research state that came after the snapshot stay."
    before = [dict(slug='a', status='skip', note='Old.', check=dict(kind='short'), research='pending')]
    now = [dict(slug='a', status='todo', note='New.', check=dict(kind='notebook'), detours=[dict(slug='x', walk='w2')], nb=dict(cells=[]), nb_why='Made.',
                leela_at=7., research='none', research_why='No good source.', research_at=9.)]
    out = restore_steps(before, now)[0]
    assert (out['status'], out['note'], out['check']) == ('skip', 'Old.', dict(kind='short'))
    assert out['detours'] == [dict(slug='x', walk='w2')] and out['nb'] == dict(cells=[]) and out['nb_why'] == 'Made.' and out['leela_at'] == 7.
    assert (out['research'], out['research_why'], out['research_at']) == ('none', 'No good source.', 9.)

def test_undo_gives_back_the_old_note():
    assert restore_steps([dict(slug='a', note='Old.')], [dict(slug='a', note='New.', qid='q1')]) == [dict(slug='a', note='Old.', qid='q1')]

def test_undo_keeps_the_code_of_a_check_made_again():
    "A check made again after the change keeps its new code, and the editor gets one plain line. The same check gets its old code back."
    before, now = [dict(slug='a', qid='q1', code=dict(stub='old'), status='todo')], [dict(slug='a', qid='q2', code=dict(stub='new'), status='skipped')]
    assert restore_steps(before, now) == [dict(slug='a', qid='q2', code=dict(stub='new'), status='todo')]
    assert undo_line(before, now) == CODE_GONE == 'This check was made again after the change. Undo cannot bring the old code back.'
    same = [dict(slug='a', qid='q1', code=dict(stub='new'))]
    assert restore_steps(before, same)[0]['code'] == dict(stub='old') and undo_line(before, same) == ''

def test_history_list_says_who_and_restores():
    rows = [dict(id='e2', at=1e9, what='Rewrote the points of slide 5: simpler.', who='tutor'), dict(id='e1', at=1e9, what='Moved “A” to slide 2.', who='you')]
    h = to_xml(HistoryList(rows, '/t/x/restore'))
    assert h.count('Restore this version') == 2 and '>tutor<' in h and '>you<' in h and '{"id": "e1"}' in h
    assert 'No changes yet.' in to_xml(HistoryList([], '/r'))

def test_history_has_no_restore_for_a_short_form():
    h = to_xml(HistoryList([dict(id='e1', at=1e9, what='Changed all slides.', who='you', before=None)], '/r'))
    assert 'Restore this version' not in h and 'Too large to restore' in h


def test_an_open_row_says_done_and_a_live_field_says_saved():
    "The summary of a row says Edit when it is shut and Done when it is open (edit.css shows one), and edit.js puts Saved beside a live field after each save."
    from pathlib import Path
    from abhyasa.core.edit import EditRow
    h = to_xml(EditRow(0, dict(id='s1', title='A slide', open=True), 1))
    assert '<span class="when-shut">Edit</span>' in h and '<span class="when-open">Done</span>' in h and 'data-key="E"' in h
    core = Path(__file__).parent.parent/'abhyasa'/'core'
    css, js = (core/'edit.css').read_text(), (core/'edit.js').read_text()
    assert '.edit-open[open] > summary .when-shut' in css and '.edit-open:not([open]) > summary .when-open' in css and '.live-saved' in css
    assert "textContent: 'Saved'" in js and 'el.dataset.live' in js.replace('el?.dataset?.live', 'el.dataset.live')
