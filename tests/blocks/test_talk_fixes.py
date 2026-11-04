"Talks from sources, as the room and the owner see them: notebook slides with points and one short code piece, the handout in markdown, What to change, the ⋯ menu, the title, the words on the pages, and the links of web and vault sources."
from talk_data import *
import re, pytest
from pathlib import Path
from fastcore.nbio import new_nb, mk_cell, write_nb
from abhyasa.show import talk_from_walk, AGAIN
import abhyasa.blocks.talk.ui as talk_ui

POLL = dict(q='Have you used an agent that runs tools?', options=['Yes, often', 'Once or twice', 'Not yet'])

@pytest.fixture
def home(tmp_path, monkeypatch):
    "A temp home with `talks/agents.ipynb`: a title, three sections, a table and code cells."
    monkeypatch.setattr(Path, 'home', lambda: tmp_path); monkeypatch.setenv('HOME', str(tmp_path))
    p = tmp_path/'talks'/'agents.ipynb'; p.parent.mkdir()
    write_nb(new_nb([mk_cell('# Agents', 'markdown'),
                     mk_cell('## Tool calls', 'markdown'), mk_cell('An agent asks a model what to do.\n\n| tool | does |\n|---|---|\n| search | finds pages |', 'markdown'),
                     mk_cell('import json'), mk_cell('tools = ["search"]\nprint(len(tools))'),
                     mk_cell('## The agent loop', 'markdown'), mk_cell('The agent runs in a loop. It stops when the model gives no more tool calls.', 'markdown'),
                     mk_cell('\n'.join(f'step{i} = {i}' for i in range(12))),
                     mk_cell('## Memory between turns', 'markdown'), mk_cell('The agent keeps a list of messages. It sends the list again on each turn.', 'markdown')]), p)
    return tmp_path

def nb_talk(cl, talk_fake, home):
    "Make a talk from the notebook of `home` with Make a talk on Start, and give its id."
    talk_fake.rules['You write one poll'] = POLL
    r = cl.post('/walk/new', data=dict(q='', sources=[f"file:{home/'talks'/'agents.ipynb'}"], chips='1', talk='1')).text
    key = re.search(r'data-job="talk:(src:[^"]+)"', r)[1]
    return wait_for(lambda: cl.get('/talk/job', params=dict(jid=key)).headers.get('hx-redirect'), secs=20).split('/')[-1].split('?')[0]

def ideas(lr, tid): return [s for s in lr.talk(tid).slides if s['kind'] == 'idea']

def test_a_notebook_slide_shows_points_and_one_short_code_piece(mk, lr, talk_fake, home):
    "A: each idea slide has points from the writer, who reads the whole section, and at most one short code piece. The room never sees a heading or a table."
    cl = mk(); tid = nb_talk(cl, talk_fake, home)
    ss = ideas(lr, tid)
    assert len(ss) == 3 and all(s['show'].get('body') == SLIDE['points'] for s in ss)
    assert [s['show']['passage'] for s in ss] == ['```python\ntools = ["search"]\nprint(len(tools))\n```', '', '']   # the import is not the piece; a long cell gives none
    assert ss[0]['ask']['kind'] == 'run' and 'print(len(tools))' in ss[0]['ask']['q']   # the run question still comes from the section
    sent = [c[0] for c in talk_fake.calls if 'You write one slide of a talk' in c[0] + c[1]]
    assert any('The section of the notebook' in p and '| search | finds pages |' in p for p in sent)
    cl.post(f'/t/{tid}/start')
    stage = cl.get(f'/t/{tid}/present').text
    assert '## Tool calls' not in stage and '|---|' not in stage and re.search(r'<ul[^>]*class="points"', stage) and '<pre><code class="language-python">tools' in stage and '```' not in stage

def test_the_handout_is_markdown_with_no_repeated_title(mk, lr, talk_fake, home):
    "B: the handout draws the code piece as code, shows no raw markdown, and gives the title of a slide one time."
    cl = mk(); tid = nb_talk(cl, talk_fake, home)
    h = cl.get(f'/t/{tid}/handout.html').text
    assert '```' not in h and '## ' not in h and '<pre><code' in h
    assert h.count('>Tool calls<') == 1 and '<p class="meta">Tool calls</p>' not in h

def test_what_to_change_goes_to_the_writer_and_stays_with_undo(mk, lr, talk_fake, home):
    "C: What to change goes into the slide prompt and the poll prompt as an owner marker, the talk keeps it for the next remake, and Undo gives back the talk before it."
    cl = mk(); tid = nb_talk(cl, talk_fake, home); jid = lr.talk(tid).src['walk']
    page = cl.get(f'/t/{tid}').text
    assert 'What to change' in page and 'name="change"' in page
    n = len(talk_fake.calls)
    r = cl.post('/talk/new', data=dict(jid=jid, again='1', tid=tid, fresh='1', change='Less code. For managers.'))
    assert r.status_code == 200
    assert wait_for(lambda: cl.get(f'/talk/job?jid={tid}').headers.get('hx-redirect'))
    new = [c[0] for c in talk_fake.calls[n:]]
    assert any('You write one slide' in c[1] and '<owner>Less code. For managers.</owner>' in c[0] for c in talk_fake.calls[n:])
    assert any('You write one poll' in c[1] and '<owner>Less code. For managers.</owner>' in c[0] for c in talk_fake.calls[n:]) and new
    assert lr.talk(tid).change == 'Less code. For managers.'
    assert '>Less code. For managers.</textarea>' in cl.get(f'/t/{tid}').text   # the next remake shows it again
    assert lr.job(f'talk:{tid}').again['change'] == 'Less code. For managers.'
    r = cl.post(f'/t/{tid}/undo')
    assert not lr.talk(tid).get('change') and 'id="talk-remake"' in r.text   # Undo gives back the talk with no change, and the field shows it
    n = len(talk_fake.calls)   # Make it again with a new change writes each slide again and keeps your edits
    cl.post(f'/t/{tid}/slide', data=dict(sid=ideas(lr, tid)[0]['id'], act='edit', notes='Mine.'))
    cl.post('/talk/new', data=dict(jid=jid, again='1', tid=tid, change='Short points.'))
    assert wait_for(lambda: cl.get(f'/talk/job?jid={tid}').headers.get('hx-redirect')) == f'/t/{tid}?done=again'
    assert sum('<owner>Short points.</owner>' in c[0] for c in talk_fake.calls[n:]) == 3 and ideas(lr, tid)[0]['notes'] == 'Mine.'
    assert lr.edits('talk', tid)[0].what == AGAIN and lr.talk(tid).change == 'Short points.'

def test_the_menu_has_one_look_and_one_walk(mk, lr, talk_fake, home):
    "D: each item of the ⋯ menu has the class `mi`, and a second press of Make a walk from this talk opens the walk of the first press."
    cl = mk(); tid = nb_talk(cl, talk_fake, home)
    menu = re.search(r'<details class="more-menu talk-menu">.*?</details>\s*</div>\s*</details>', cl.get(f'/t/{tid}').text, re.S)[0]
    for item in ('>Handout</a>', '>Make a walk from this talk</button>', '>Make it again</summary>', '>Delete this talk</summary>'):
        assert re.search(r'class="mi"[^>]*' + re.escape(item), menu), item
    a = cl.post(f'/t/{tid}/walk', follow_redirects=False).headers['location']
    b = cl.post(f'/t/{tid}/walk', follow_redirects=False).headers['location']
    assert a == b and sum(j.get('from_talk') == tid for j in lr.journeys()) == 1
    assert f'href="{a}"' in cl.get(f'/t/{tid}').text and 'Open the walk from this talk' in cl.get(f'/t/{tid}').text

def test_a_notebook_talk_has_the_title_of_the_notebook(mk, lr, talk_fake, home):
    "E: the talk takes the first # heading of the notebook, not its vault path."
    cl = mk(); tid = nb_talk(cl, talk_fake, home)
    assert lr.talk(tid).title == 'Agents' and '<h1>Agents, as a talk</h1>' in cl.get(f'/t/{tid}').text

def test_the_words_on_the_pages_are_true(mk, lr, talk_fake, home):
    "F: a goal talk says its goal, the Start box line for a file names Make a talk, a lone notebook shows no web chip, Teach names Make a talk, and the pending card shows the stage."
    lr.put('Tool calls', 'A model names a tool, and the agent runs it.', 'ml', slug='tool-calls')
    lr.put_journey(dict(id='g-talk', title='Agents', goal='Explain agents to managers', mode='walk', parent={'for': 'talk'},
                        steps=[dict(slug='tool-calls', status='todo', check=dict(way='words', kind='short', depth=2))]))
    t = talk_from_walk(lr, talk_fake, 'g-talk')
    cl = mk()
    page = cl.get(f'/t/{t.id}').text
    assert 'Made from your goal: Explain agents to managers' in page and 'Made from your sources' not in page
    nb = home/'talks'/'agents.ipynb'
    box = cl.get('/learn/read', params=dict(q=str(nb))).text
    assert 'Make a talk makes slides from it' in box and 'schip web' not in box and 'press Start or Make a talk' in box
    assert 'press Make a talk in the Start box' in str(talk_ui.Teach([]))   # Home shows Teach when you have a walk or a course
    seen = []   # the row of the job while the tutor writes a slide, and the card that the page shows then
    def slide(p, sp):
        r = next(r for k, r in lr.jobs().items() if k.startswith('talk:src:') and r.state == 'running')
        seen.append((r.said, str(talk_ui.Pending('k', row=r)))); return SLIDE
    talk_fake.rules['You write one slide of a talk'] = slide
    nb_talk(cl, talk_fake, home)
    said, card = seen[0]
    assert said == 'Writing the slides' and 'Writing the slides.' in card and 'The tutor writes the points' in card

def test_a_talk_that_cannot_start_says_why(mk):
    "G: Make a talk that is off says why, and only a held or busy button has the progress cursor."
    box = mk().get('/learn/read', params=dict(q='')).text
    assert 'To make a talk, write a goal or add a source.' in box and 'aria-describedby="start-talk-off"' in box
    css = (Path(talk_ui.__file__).parents[2]/'core'/'base.css').read_text()
    assert 'button:disabled { cursor: not-allowed; }' in css and 'button.busy, button[data-held] { cursor: progress; }' in css

def test_web_and_vault_sources_have_links(mk, lr, talk_fake, home):
    "H: a GitHub repo and a link get a row in the Links panel and a line in the handout; a vault page shows by its name until it gets a shared link."
    cl = mk(); tid = nb_talk(cl, talk_fake, home); jid = lr.talk(tid).src['walk']
    lr.merge_journey(jid, chips=[*lr.journey(jid).chips, 'gh:answerdotai/fastcore', 'link:https://x.org/p', 'vault:karma'])
    page = cl.get(f'/t/{tid}').text
    assert '<code>https://github.com/answerdotai/fastcore</code>' in page and '<code>https://x.org/p</code>' in page and talk_ui.VAULT_SAYS in page
    h = cl.get(f'/t/{tid}/handout.html').text
    assert '<a href="https://github.com/answerdotai/fastcore">' in h and '<a href="https://x.org/p">' in h and '<b>Vault</b> · karma · in your vault' in h
    assert cl.post(f'/t/{tid}/links', data=dict(path='vault:karma', link='https://onedrive.example/karma')).status_code == 200
    assert '<b>Vault</b> · karma · <a href="https://onedrive.example/karma">' in cl.get(f'/t/{tid}/handout.html').text
