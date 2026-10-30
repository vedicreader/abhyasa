"The talk editor in place: each change saves at once with an Undo, the history, add, copy, move and remove, the passage, the figure and the rewrite."
from talk_data import *
import json

def paper_walk(cl, lr): return prep_walk(lr, walk(cl, lr))
def editor_page(cl, tid): return cl.get(f'/t/{tid}').text
def ids(lr, tid): return [s['id'] for s in lr.talk(tid).slides]

def test_field_saves_at_once_with_undo(mk, lr, talk_fake):
    "A field saves at once, the answer has the Undo bar, and Undo gives back the old text."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr)); sid = lr.talk(tid).slides[0]['id']
    r = cl.post(f'/t/{tid}/slide', data=dict(sid=sid, act='edit', notes='Show the demo first.'))
    assert lr.talk(tid).slides[0]['notes'] == 'Show the demo first.' and 'id="undo-bar"' in r.text and 'Changed the' in r.text
    assert 'Changed the speaker note of slide 1.' in r.text and 'hx-swap-oob' in r.text
    cl.post(f'/t/{tid}/undo')
    assert lr.talk(tid).slides[0]['notes'] != 'Show the demo first.'

def test_a_live_field_answers_with_the_bar_only(mk, lr, talk_fake):
    "A live field (act=set, the slide in the query) answers with the bar only, so the text that you type stays; two saves of one field join."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr))
    r = cl.post(f'/t/{tid}/slide?sid=s2', data=dict(act='set', title='Softmax, in short'))
    assert r.status_code == 200 and 'id="deck"' not in r.text and 'Changed the title of slide 2.' in r.text
    cl.post(f'/t/{tid}/slide?sid=s2', data=dict(act='set', title='Softmax, in brief'))
    es = lr.edits('talk', tid)
    assert lr.talk(tid).slides[1]['title'] == 'Softmax, in brief' and len(es) == 1 and es[0].before[1]['title'] == 'Softmax'
    assert cl.post(f'/t/{tid}/slide?sid=s2', data=dict(act='set', title='Softmax, in brief')).status_code == 204   # no change: nothing kept
    assert cl.post(f'/t/{tid}/slide?sid=s2', data=dict(act='set', title='  ')).text == 'Write a title.'

def test_move_add_dup_remove(mk, lr, talk_fake):
    "Move to a place, copy below with a new id, remove with no question; each says what changed."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr)); ss = lr.talk(tid).slides
    r = cl.post(f'/t/{tid}/slide', data=dict(sid=ss[2]['id'], act='move', to=0))
    assert lr.talk(tid).slides[0]['id'] == ss[2]['id'] and f'Moved “{ss[2]["title"]}” to slide 1.' in r.text
    r = cl.post(f'/t/{tid}/slide', data=dict(sid=ss[0]['id'], act='dup'))
    assert len(lr.talk(tid).slides) == len(ss) + 1 and f'Copied “{ss[0]["title"]}”.' in r.text and 'data-fresh="1"' in r.text
    new = lr.talk(tid).slides[2]
    assert new['id'] not in [s['id'] for s in ss] and new['title'] == ss[0]['title']
    r = cl.post(f'/t/{tid}/slide', data=dict(sid=ss[1]['id'], act='drop'))
    assert 'hx-confirm' not in r.text and 'Removed' in r.text and ss[1]['id'] not in ids(lr, tid)
    assert cl.post(f'/t/{tid}/slide', data=dict(sid=ss[0]['id'], act='move', to=99)).status_code == 400

def test_add_a_slide_and_a_pause(mk, lr, talk_fake):
    "Add a slide goes after the slide that it names, or at the end; it is a blank idea slide, open, with its title selected."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr)); n = len(ids(lr, tid))
    r = cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='add'))
    s = lr.talk(tid).slides[1]
    assert s['kind'] == 'idea' and s['concept'] == '' and s['title'] == 'New slide' and 'Added a slide.' in r.text and 'data-fresh="1"' in r.text
    cl.post(f'/t/{tid}/slide', data=dict(act='add'))
    assert len(ids(lr, tid)) == n + 2 and lr.talk(tid).slides[-1]['title'] == 'New slide'
    r = cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='pause', prompt='Talk to your neighbour.', secs=120))
    assert lr.talk(tid).slides[1]['kind'] == 'pause' and 'Added a pause.' in r.text

def test_rewrite_changes_points_not_passage(mk, lr, talk_fake):
    "The tutor rewrites the points and the note; the passage stays, and the history says the tutor did it."
    talk_fake.rules['Rewrite'] = dict(body=['Short.'], notes='New note.', passage='NOT THIS')
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr)); s = lr.talk(tid).slides[0]
    r = cl.post(f'/t/{tid}/slide', data=dict(sid=s['id'], act='rewrite', text='simpler'))
    n = lr.talk(tid).slides[0]
    assert n['show']['body'] == ['Short.'] and n['show']['passage'] == s['show']['passage'] and lr.edits('talk', tid)[0].who == 'tutor'
    assert n['notes'] == 'New note.' and 'Rewrote the points of slide 1: simpler.' in r.text
    p = next(c[0] for c in talk_fake.calls if c[0].startswith('Rewrite these fields'))
    assert 'NOT THIS' not in p and '"passage"' not in p   # the passage goes in as the source only, never as a field
    cl.post(f'/t/{tid}/slide', data=dict(sid=s['id'], act='rewrite', chip='Add an example', text=''))
    assert 'Add an example' in lr.edits('talk', tid)[0].what

def test_failed_rewrite_changes_nothing(mk, lr, talk_fake):
    "A bad reply from the model changes nothing and keeps nothing."
    talk_fake.rules['Rewrite'] = 'not json'
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr)); before = lr.talk(tid).slides
    r = cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='rewrite', text='simpler'))
    assert r.status_code == 400 and 'The tutor could not rewrite this. Nothing changed.' in r.text and lr.talk(tid).slides == before
    assert not lr.edits('talk', tid)
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='rewrite', text=' ')).text == 'Tell the tutor what to change.'

def test_history_restore(mk, lr, talk_fake):
    "Two changes show in the history with \"you\"; Restore gives back the talk as it was before a change, and the restore can be undone."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr)); first_state = lr.talk(tid).slides
    cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', notes='One.'))
    cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='edit', notes='Two.'))
    h = cl.get(f'/t/{tid}/history').text
    assert h.count('<span class="who">you</span>') == 2 and 'Changed the speaker note of slide 1.' in h and 'Restore this version' in h
    r = cl.post(f'/t/{tid}/restore', data=dict(k=1))
    assert r.headers.get('hx-redirect') == f'/t/{tid}' and lr.talk(tid).slides == first_state
    assert lr.edits('talk', tid)[0].what.startswith('Restored the version before')
    cl.post(f'/t/{tid}/undo')
    assert lr.talk(tid).slides[1]['notes'] == 'Two.'
    assert cl.post(f'/t/{tid}/restore', data=dict(k=9)).status_code == 404 and cl.get('/t/nope/history').status_code == 404

def test_an_old_undo_bar_does_nothing(mk, lr, talk_fake):
    "Undo posts the id of its change: when a newer change came after it, it does nothing."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr))
    cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', notes='One.')); old = lr.edits('talk', tid)[0].id
    cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='edit', notes='Two.'))
    r = cl.post(f'/t/{tid}/undo', data=dict(step=old))
    assert 'Nothing to undo.' in r.text and lr.talk(tid).slides[1]['notes'] == 'Two.'

def test_a_bad_change_saves_nothing(mk, lr, talk_fake):
    "check_talk runs on each change: a change with a problem gives 400 with the first problem, and nothing is saved or kept."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr)); before = lr.talk(tid).slides
    r = cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='edit', beats='lit:gradients'))
    assert r.status_code == 400 and 'lights text that is not in the passage' in r.text and lr.talk(tid).slides == before and not lr.edits('talk', tid)

def test_the_right_answer_stays_one(mk, lr, talk_fake):
    "A choice keeps exactly one right answer: the line says which, a change of options moves it with its text, and the room never gets it."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr))
    assert 'Option 1 is the right answer. The room does not see this.' in editor_page(cl, tid)
    opts = ['The largest score only', 'Weights above 0 that add to 1', 'The scores in order', '', '', '']
    r = cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', kind='choice', q='What does softmax give?', options=opts, answer='1'))
    a = lr.talk(tid).slides[0]['ask']
    assert a['answer'] == 1 and a['options'][1] == 'Weights above 0 that add to 1' and 'Option 2 is the right answer.' in r.text
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', kind='choice', q='Q?', options=opts, answer='4')).text == 'Pick an option that has text.'
    cl.post(f'/t/{tid}/start'); run = lr.run(lr.talk(tid).live)
    au = cl.get(f'/t/{tid}/audience?k={run["key"]}').text
    assert 'right answer' not in au and '"answer"' not in au

def test_passage_and_figure(mk, lr, talk_fake):
    "Remove the passage takes its beats out; Pick another passage takes one of the idea, word for word; the figure comes only from the idea."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr)); s = lr.talk(tid).slides[1]
    assert s['show']['figure'] and 'Remove the figure' in editor_page(cl, tid)
    r = cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='figure', asset=''))
    n = lr.talk(tid).slides[1]
    assert n['show']['figure'] is None and 'figure' not in n['beats'] and 'Changed the figure of slide 2.' in r.text
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='figure', asset='asset:attention/../../x.png')).text == 'Pick a figure of this idea.'
    cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='figure', asset=s['show']['figure']))
    assert lr.talk(tid).slides[1]['show']['figure'] == s['show']['figure'] and 'figure' in lr.talk(tid).slides[1]['beats']
    cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='passage', k=''))
    n = lr.talk(tid).slides[1]
    assert n['show']['passage'] == '' and 'passage' not in n['beats'] and 'src' not in n['show']
    cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='passage', k='0'))
    n = lr.talk(tid).slides[1]
    assert n['show']['passage'] == s['show']['passage'] and 'passage' in n['beats'] and n['show']['src']['doc_id'] == s['show']['src']['doc_id']
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='passage', k='9')).status_code == 400

def test_editor_has_no_save_button(mk, lr, talk_fake):
    "The editor is an EditList with live fields: no Save button and no Change summary, one main button, the rewrite box and the history link."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr))
    h = editor_page(cl, tid)
    assert 'Save the slide' not in h and '<summary>Change' not in h and 'Option 1 is the right answer.' in h
    assert 'data-edit="1"' in h and 'id="deck"' in h and h.count('class="go"') == 1 and 'Present <kbd>⌥S</kbd>' in h
    assert 'Points the room sees' in h and 'Speaker note · only you see it' in h and 'Question for the room' in h
    assert all(c in h for c in ('Simpler', 'Add an example', 'Shorter')) and 'It never changes the passage.' in h
    assert 'Earlier versions' in h and 'Made from your walk' in h and 'Add a slide' in h and 'Add a pause' in h
    assert 'id="undo-bar"' in h and '/assets/edit.js' in h and h.count('data-key="D"') == len(lr.talk(tid).slides)

def test_talk_plan_keys():
    "The keys table has the keys of the talk editor."
    from abhyasa.core.keys import KEYS
    plan = {k for g, k, _ in KEYS if g == 'Talk plan'}
    assert plan == {'W', 'S', '⇧W ⇧S', 'E', 'A', 'D', 'X', 'Q', 'R', '⌘Z', '⌥S'}
