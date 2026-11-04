"The talk editor in place: each change saves at once with an Undo, the history, add, copy, move and remove, the passage, the figure and the rewrite."
from talk_data import *
from abhyasa.show import check_talk
import json, re, pytest
from pathlib import Path
from fastcore.nbio import new_nb, mk_cell, write_nb
from starlette.testclient import TestClient
import abhyasa.blocks.talk.app as talk_app

def paper_walk(cl, lr): return prep_walk(lr, walk(cl, lr))
def editor_page(cl, tid): return cl.get(f'/t/{tid}').text
def ids(lr, tid): return [s['id'] for s in lr.talk(tid).slides]

def test_field_saves_at_once_with_undo(mk, lr, talk_fake):
    "A field saves at once, the answer has the Undo bar, and Undo gives back the old text."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr)); old = lr.talk(tid).slides; sid = old[0]['id']
    r = cl.post(f'/t/{tid}/slide', data=dict(sid=sid, act='edit', notes='Show the demo first.'))
    assert lr.talk(tid).slides[0]['notes'] == 'Show the demo first.' and 'id="undo-bar"' in r.text and 'Changed the' in r.text
    assert 'Changed the speaker note of slide 1.' in r.text and 'hx-swap-oob' in r.text
    cl.post(f'/t/{tid}/undo')
    assert lr.talk(tid).slides == old and not lr.edits('talk', tid)   # Undo gives back the exact old slides

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

def test_poll_question_saves_with_undo(mk, lr, talk_fake):
    "A new poll question and its options save with no right answer, and Undo gives back the old poll. The stage draws the poll. The presenter opens the notebook through the server, and the audience sees its path as text."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr)); t = lr.talk(tid)
    blank = dict(section='', show=dict(passage='', figure=None, demo=None), beats=[], notes='')
    poll = dict(blank, id='s90', kind='poll', title='A question for the room', mins=2, ask=dict(kind='choice', q='Have you used an agent?', options=['Yes', 'No']))
    nxt = dict(blank, id='s91', kind='next', title='Now open the notebook', mins=1, ask=None, link='file:///Users/k/agents.ipynb')
    lr.put_talk({**t, 'slides': [poll, *t.slides, nxt]}); old = lr.talk(tid).slides
    assert 'a question about the room, with no right answer' in editor_page(cl, tid)
    r = cl.post(f'/t/{tid}/slide', data=dict(sid='s90', act='edit', kind='choice', q='Have you used an agent that runs tools?', options=['Yes, often', 'Not yet', '', '', '', '']))
    assert r.status_code == 200, r.text
    assert lr.talk(tid).slides[0]['ask'] == dict(kind='choice', q='Have you used an agent that runs tools?', options=['Yes, often', 'Not yet'])
    cl.post(f'/t/{tid}/undo')
    assert lr.talk(tid).slides == old
    cl.post(f'/t/{tid}/start'); run = lr.run(lr.talk(tid).live)
    au = cl.get(f'/t/{tid}/audience?k={run["key"]}').text
    assert 'Have you used an agent?' in au and 'There is no right answer.' in au and '<code>agents.ipynb</code>' in au and '/Users/k/' not in au and 'file://' not in au   # the room sees the file name, never the local path
    assert f'hx-post="/t/{tid}/open"' in cl.get(f'/t/{tid}/present').text

POLL = dict(q='Have you used an agent that runs tools?', options=['Yes, often', 'Once or twice', 'Not yet'])

@pytest.fixture
def home(tmp_path, monkeypatch):
    "A temp home with `talks/agents.ipynb`: a title and three sections."
    monkeypatch.setattr(Path, 'home', lambda: tmp_path); monkeypatch.setenv('HOME', str(tmp_path))
    p = tmp_path/'talks'/'agents.ipynb'; p.parent.mkdir()
    write_nb(new_nb([mk_cell('# Agents', 'markdown'),
                     mk_cell('## Tool calls', 'markdown'), mk_cell('An agent asks a model what to do. The model names a tool, and the agent runs it.', 'markdown'),
                     mk_cell('## The agent loop', 'markdown'), mk_cell('The agent runs in a loop. It stops when the model gives no more tool calls.', 'markdown'),
                     mk_cell('## Memory between turns', 'markdown'), mk_cell('The agent keeps a list of messages. It sends the list again on each turn.', 'markdown')]), p)
    return tmp_path

def test_make_a_talk_from_a_notebook_on_start(mk, lr, talk_fake, home):
    "Make a talk with one notebook chip opens the talk editor. Its hidden walk is not on Home, and the editor links to the source, not to a walk page. Deleting the talk deletes its hidden walk."
    talk_fake.rules['You write one poll'] = POLL
    cl, nb = mk(), home/'talks'/'agents.ipynb'
    r = cl.post('/walk/new', data=dict(q='', sources=[f'file:{nb}'], chips='1', talk='1')).text
    key = re.search(r'data-job="talk:(src:[^"]+)"', r)[1]
    tid = wait_for(lambda: cl.get('/talk/job', params=dict(jid=key)).headers.get('hx-redirect'), secs=20).split('/')[-1]
    t = lr.talk(tid); jid = t.src['walk']
    assert lr.journey(jid).parent == {'for': 'talk'} and sum(s['kind'] == 'idea' for s in t.slides) == 3
    assert f'/w/{jid}' not in cl.get('/').text
    page = editor_page(cl, tid)
    assert 'Made from your sources' in page and f'/w/{jid}' not in page and 'href="/v/' in page
    cl.post(f'/t/{tid}/drop')
    assert lr.talk(tid) is None and not [j for j in lr.journeys() if (j.get('parent') or {}).get('for') == 'talk']

def test_open_runs_only_on_the_notebook_of_the_talk(mk, lr, talk_fake, monkeypatch, tmp_path):
    "Open the notebook runs `open` on the path that the talk keeps, never on a path from the form. A talk with no notebook, or a request from another device, opens nothing."
    calls = []; monkeypatch.setattr(talk_app, '_open', lambda args, **kw: calls.append(args))
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr)); here = TestClient(cl.app, client=('127.0.0.1', 50000))
    assert here.post(f'/t/{tid}/open', data=dict(path='/etc/hosts', notebook='/etc/hosts')).text == talk_app.NO_NB and not calls
    nb = tmp_path/'agents.ipynb'; nb.write_text('{}')
    t = lr.talk(tid); lr.put_talk({**t, 'src': {**t.src, 'notebook': str(nb)}})
    assert cl.post(f'/t/{tid}/open').status_code == 403 and not calls   # the test client is not this Mac
    assert here.post(f'/t/{tid}/open', data=dict(path='/etc/hosts')).status_code == 204 and calls == [['open', str(nb)]]
    assert here.post(f'/t/{tid}/open', headers={'Origin': 'https://evil.example', 'Sec-Fetch-Site': 'cross-site'}).status_code == 403 and len(calls) == 1   # a page of another site
    app = tmp_path/'Run.app'; app.write_text('x'); lr.put_talk({**lr.talk(tid), 'src': {**t.src, 'notebook': str(app)}})
    assert here.post(f'/t/{tid}/open').text == talk_app.NO_NB and len(calls) == 1   # only a notebook opens

def test_a_failed_talk_leaves_no_hidden_walk(lr, talk_fake, home, monkeypatch):
    "When the talk cannot be made after its hidden walk is saved, the hidden walk goes too."
    import abhyasa.show as show
    def boom(*a, **kw): raise RuntimeError('the model failed')
    monkeypatch.setattr(show, 'talk_from_walk', boom)
    with pytest.raises(RuntimeError): show.talk_from_sources(lr, talk_fake, [f"file:{home/'talks'/'agents.ipynb'}"])
    assert not [j for j in lr.journeys() if (j.get('parent') or {}).get('for') == 'talk']

def nb_talk(cl, talk_fake, home):
    "Make a talk from the notebook of `home` on Start, and give its id."
    talk_fake.rules['You write one poll'] = POLL
    r = cl.post('/walk/new', data=dict(q='', sources=[f"file:{home/'talks'/'agents.ipynb'}"], chips='1', talk='1')).text
    key = re.search(r'data-job="talk:(src:[^"]+)"', r)[1]
    return wait_for(lambda: cl.get('/talk/job', params=dict(jid=key)).headers.get('hx-redirect'), secs=20).split('/')[-1]

def test_handout_gives_the_answers_only_at_the_end(mk, lr, talk_fake, home):
    "The Handout item opens one HTML file with no script: one page for each slide with content, each question with no answer, the notebook link, then Answers."
    cl = mk(); tid = nb_talk(cl, talk_fake, home)
    assert f'href="/t/{tid}/handout.html"' in editor_page(cl, tid)
    r = cl.get(f'/t/{tid}/handout.html')
    assert r.status_code == 200 and "default-src 'none'" in r.headers['content-security-policy'] and '<script' not in r.text
    body, answers = r.text.split('<h2>Answers</h2>')
    ss = lr.talk(tid).slides
    assert body.count('class="slide"') == sum(s['kind'] in ('idea', 'poll', 'next') for s in ss)
    poll = next(s for s in ss if s['kind'] == 'poll')
    assert f"Question 1. {poll['ask']['q']}" in body and 'class="right"' not in body
    assert (home/'talks'/'agents.ipynb').resolve().as_uri() in body and 'There is no right answer.' in answers

def test_links_panel_keeps_a_shared_link_with_undo(mk, lr, talk_fake, home):
    "A folder link goes to each file in the folder, a file link wins over it, Undo gives the old link back, and a bad link or a path that is not a row is refused."
    cl = mk(); tid = nb_talk(cl, talk_fake, home)
    nb = (home/'talks'/'agents.ipynb').resolve()
    page = editor_page(cl, tid)
    assert 'Links in the handout' in page and str(nb) in page and 'Only this Mac opens this link.' in page
    handout = lambda: cl.get(f'/t/{tid}/handout.html').text
    r = cl.post(f'/t/{tid}/links', data=dict(path=str(nb.parent), link='https://onedrive.example/talks'))
    assert r.status_code == 200 and 'Changed the shared link of talks.' in r.text and 'Only this Mac opens this link.' not in r.text
    assert 'href="https://onedrive.example/talks"' in handout() and 'file://' not in handout()
    cl.post(f'/t/{tid}/links', data=dict(path=str(nb), link='https://onedrive.example/agents'))
    assert 'href="https://onedrive.example/agents"' in handout()
    r = cl.post(f'/t/{tid}/undo')
    assert lr.talk(tid)['links'] == {str(nb.parent): 'https://onedrive.example/talks'} and 'id="talk-links"' in r.text
    assert 'href="https://onedrive.example/agents"' not in handout()
    assert cl.post(f'/t/{tid}/links', data=dict(path=str(nb), link='javascript:alert(1)')).status_code == 400
    assert cl.post(f'/t/{tid}/links', data=dict(path='/etc/hosts', link='https://x.org')).text == 'This path is not a link of the handout.'
    assert lr.talk(tid)['links'] == {str(nb.parent): 'https://onedrive.example/talks'}

def test_make_a_walk_from_this_talk(mk, lr, talk_fake, home):
    "Make a walk from this talk gives a walk of your own with the ideas in slide order and no parent. A talk from your own walk does not offer it."
    cl = mk(); tid = nb_talk(cl, talk_fake, home)
    assert 'Make a walk from this talk' in editor_page(cl, tid)
    ss = lr.talk(tid).slides; ideas = [k for k, s in enumerate(ss) if s['kind'] == 'idea']
    cl.post(f'/t/{tid}/slide', data=dict(sid=ss[ideas[-1]]['id'], act='move', to=ideas[0]))   # the last idea goes first
    order = [s['concept'] for s in lr.talk(tid).slides if s['kind'] == 'idea']
    r = cl.post(f'/t/{tid}/walk', follow_redirects=False)
    assert r.status_code == 303
    w = lr.journey(r.headers['location'].split('/')[-1])
    assert [s['slug'] for s in w.steps] == order and order[0] == ss[ideas[-1]]['concept'] and not w.get('parent')
    own = make_talk(cl, paper_walk(cl, lr))
    assert 'Make a walk from this talk' not in editor_page(cl, own) and cl.post(f'/t/{own}/walk').status_code == 400

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

def test_figure_shows_as_a_picture(mk, lr, talk_fake):
    "The figure shows as a small picture with its caption from the source, not as a path; Pick another figure offers the figures of the source."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr)); f = lr.talk(tid).slides[1]['show']['figure']
    h = editor_page(cl, tid)
    row = h[h.index('data-id="s2"'):h.index('data-id="s3"')]
    assert f'/t/{tid}/fig?f=asset%3Aattention%2Fimages%2Ffig2.png' in row and '<figcaption>Figure 2</figcaption>' in row
    assert '<p class="mute">attention/images/fig2.png</p>' not in row and 'Remove the figure' in row
    r = cl.get(f'/t/{tid}/fig', params=dict(f=f))
    assert r.status_code == 200 and r.content.startswith(PNG) and r.headers['content-type'] == 'image/png'
    assert cl.get(f'/t/{tid}/fig', params=dict(f='asset:attention/../vault.db')).status_code == 404 and cl.get('/t/nope/fig', params=dict(f=f)).status_code == 404
    cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='figure', asset=''))
    h = editor_page(cl, tid); row = h[h.index('data-id="s2"'):h.index('data-id="s3"')]
    assert 'Pick another figure' in row and 'class="fig-choice"' in row and '<span class="cap">Figure 2</span>' in row   # the figure of the source, by its caption

def test_beats_are_chips(mk, lr, talk_fake):
    "The beats show as chips in plain words; a beat moves, goes and comes back through its own route, and the stored form stays the same."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr))
    beats = lambda: lr.talk(tid).slides[1]['beats']
    h = editor_page(cl, tid)
    assert 'name="beats"' not in h and 'id="beats-s2"' in h and '<span class="chip-name">Passage</span>' in h and 'Add a beat' in h
    url = f'/t/{tid}/beat'
    r = cl.post(f'{url}?sid=s2&at=1', data=dict(act='move', to=0))
    assert beats() == ['figure', 'passage'] and 'Changed the beats of slide 2.' in r.text and 'id="beats-s2"' in r.text and 'hx-swap-oob' in r.text
    r = cl.post(f'{url}?sid=s2', data=dict(act='add', words='softmax function'))
    assert beats() == ['figure', 'passage', 'lit:softmax function'] and 'Light: softmax function' in r.text
    assert cl.post(f'{url}?sid=s2', data=dict(act='add', words='gradients')).status_code == 400 and len(beats()) == 3   # not in the passage
    assert cl.post(f'{url}?sid=s2', data=dict(act='add', kind='passage')).text == 'The slide shows this part already.'
    cl.post(f'{url}?sid=s2&at=0', data=dict(act='drop'))
    assert beats() == ['passage', 'lit:softmax function']
    r = cl.post(f'{url}?sid=s2', data=dict(act='add', kind='figure'))
    assert beats() == ['passage', 'lit:softmax function', 'figure'] and '>Question<' in r.text   # the menu now offers only what the slide does not show
    assert cl.post(f'{url}?sid=s2&at=9', data=dict(act='drop')).status_code == 400 and cl.post(f'{url}?sid=s99', data=dict(act='drop', at=0)).status_code == 404
    assert len(lr.edits('talk', tid)) == 1   # one field: the beats of slide 2 join in one change
    cl.post(f'/t/{tid}/undo')
    assert beats() == ['passage', 'figure']

def test_an_order_keeps_its_mix(mk, lr, talk_fake):
    "An order question mixes its cards again only when the cards change, not on a save that changes nothing else."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr))
    right = ['Dot products', 'Divide by the root of dk', 'Softmax', 'Weigh the values']
    post = lambda **kw: cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', kind='order', options=right, **kw))
    post(q='Put the steps in order.'); a = lr.talk(tid).slides[0]['ask']
    for _ in range(5): post(q='Put the steps in order.')
    assert lr.talk(tid).slides[0]['ask'] == a and len(lr.edits('talk', tid)) == 1   # the same save: no new mix, and nothing kept
    post(q='Put the four steps in order.')
    b = lr.talk(tid).slides[0]['ask']
    assert (b['options'], b['answer']) == (a['options'], a['answer']) and b['q'] == 'Put the four steps in order.'   # a new question keeps the mix
    cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', kind='order', q='Q?', options=[*right[:3], 'Add them up']))
    c = lr.talk(tid).slides[0]['ask']
    assert [c['options'][i] for i in c['answer']] == [*right[:3], 'Add them up']   # new cards: mixed again, and the right order stays

def test_sections_are_labels_not_rows(mk, lr, talk_fake):
    "Each section of the walk shows as a quiet label where it starts; it is not a row, so the keys and the moves skip it."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr))
    h = editor_page(cl, tid); ss = lr.talk(tid).slides
    secs = list(dict.fromkeys(s['section'] for s in ss if s.get('section')))
    assert h.count('<li role="presentation" class="sec">') == len(secs) == 2
    deck = h[h.index('id="deck"'):]
    assert deck.index(secs[0]) < deck.index('data-id="s1"') < deck.index(secs[1]) < deck.index('data-id="s2"')
    assert 'data-i="1"' in deck[deck.index('data-id="s2"') - 200:deck.index('data-id="s2"') + 200]   # the row index skips the labels

def test_no_control_marks_in_a_field(mk, lr, talk_fake):
    "Each field that the editor sends loses its control and direction marks: the title, the points, the note, the question, the options, the Light words and the rewrite."
    talk_fake.rules['Rewrite'] = dict(body=['Short.'], notes='New note.')
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr))
    post = lambda **kw: cl.post(f'/t/{tid}/slide', data=dict(sid='s1', **kw))
    post(act='edit', title='Seq\u202euential', body='One\x00 point.\nTwo\u200b points.', notes='A\x07 note.\nLine two.')
    s = lr.talk(tid).slides[0]
    assert (s['title'], s['show']['body'], s['notes']) == ('Sequential', ['One point.', 'Two points.'], 'A note.\nLine two.')
    post(act='edit', kind='choice', q='Wh\u2066at?', options=['A\x1b', 'B', '', '', '', ''], answer='0')
    assert lr.talk(tid).slides[0]['ask']['q'] == 'What?' and lr.talk(tid).slides[0]['ask']['options'] == ['A', 'B']
    cl.post(f'/t/{tid}/beat?sid=s2', data=dict(act='add', words='softmax\u200b function'))
    assert lr.talk(tid).slides[1]['beats'][-1] == 'lit:softmax function'
    post(act='rewrite', text='simpler\u202e')
    assert lr.edits('talk', tid)[0].what == 'Rewrote the points of slide 1: simpler.'
    assert not check_talk(lr.talk(tid)) and check_talk({**lr.talk(tid), 'slides': [{**lr.talk(tid).slides[0], 'title': 'A\u202eB'}]}) == ['s1: the title has a control mark']

def test_an_old_mark_is_cleaned_on_the_next_change(mk, lr, talk_fake):
    "A slide saved before the check, with a mark in its note, gets clean on the next change, so the talk can still change."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr))
    t = dict(lr.talk(tid)); ss = [dict(x) for x in t['slides']]; ss[1]['notes'] = 'Old\r\n note.'
    lr.v.set_meta(t['doc_id'], **{**{k: v for k, v in t.items() if k != 'doc_id'}, 'slides': ss})   # as an old version saved it
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', notes='New.')).status_code == 200
    assert lr.talk(tid).slides[1]['notes'] == 'Old\n note.'

def test_a_primer_asks_the_model_outside_the_lock(mk, lr, talk_fake, monkeypatch):
    "The primer act writes its question before it takes the lock of the talk, so a slow model never holds up another change."
    import abhyasa.blocks.talk.app as ta
    from abhyasa.path import edit_lock
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr)); held = []
    real = ta.ask_for_concept
    def spy(*a, **kw):   # another thread tries the lock: it gets it only when the request does not hold it
        import threading
        lk, res = edit_lock('talk', tid), []
        th = threading.Thread(target=lambda: res.append(lk.acquire(blocking=False) and (lk.release() or True))); th.start(); th.join()
        held.append(not res[0])
        return real(*a, **kw)
    monkeypatch.setattr(ta, 'ask_for_concept', spy)
    r = cl.post(f'/t/{tid}/slide', data=dict(sid='s3', act='primer', slug='softmax'))
    assert r.status_code == 200 and held == [False] and lr.talk(tid).slides[2]['kind'] == 'primer'

def test_figures_of_a_document_are_read_once(mk, lr, talk_fake, monkeypatch):
    "The editor reads the text of a source document once for its figures, and again only when the document changes."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr)); f = lr.talk(tid).slides[1]['show']['figure']
    reads = []
    real = type(lr.vault).document
    monkeypatch.setattr(type(lr.vault), 'document', lambda self, ref, *a, **kw: (reads.append(ref), real(self, ref, *a, **kw))[1])
    editor_page(cl, tid); editor_page(cl, tid)
    for _ in range(3): assert cl.get(f'/t/{tid}/fig', params=dict(f=f)).status_code == 200
    assert len(reads) == 1

def test_a_rewrite_keeps_your_edit(mk, lr, talk_fake):
    "A field that you change while the tutor writes keeps your edit; the rewrite goes only on the fields that you did not change."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr))
    def slow(p, sp):   # while the model writes, you change the note
        cl.post(f'/t/{tid}/slide?sid=s1', data=dict(act='set', notes='My note.'))
        return dict(body=['Short.'], notes='Tutor note.')
    talk_fake.rules['Rewrite'] = slow
    r = cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='rewrite', text='simpler'))
    s = lr.talk(tid).slides[0]
    assert s['notes'] == 'My note.' and s['show']['body'] == ['Short.'] and 'Your edit of the speaker note was kept.' in r.text
    def both(p, sp):   # you change both fields: nothing of the rewrite is used
        cl.post(f'/t/{tid}/slide?sid=s1', data=dict(act='set', notes='Mine again.', body='My point.'))
        return dict(body=['Tutor point.'], notes='Tutor note.')
    talk_fake.rules['Rewrite'] = both
    r = cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='rewrite', text='shorter'))
    s = lr.talk(tid).slides[0]
    assert r.status_code == 400 and r.text == 'Your edit was kept. The rewrite was not used.' and (s['notes'], s['show']['body']) == ('Mine again.', ['My point.'])

def test_other_digits_give_400(mk, lr, talk_fake):
    "A digit that int() cannot read, such as ², gives a 400 or a 404, never a 500."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr))
    cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', notes='One.'))
    assert cl.post(f'/t/{tid}/restore', data=dict(k='²')).status_code == 404
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', kind='choice', q='Q?', options=['a', 'b', '', '', '', ''], answer='²')).status_code == 400
