"The builder: a conversation that makes and changes a walk or a talk, with a fake agent that calls the real builder tools, and the page that shows them."
from talk_data import *
import re, json, pytest
from pathlib import Path
from fastcore.basics import AttrDict
from fastcore.nbio import new_nb, mk_cell, write_nb
import abhyasa.blocks.build.app as build_app
from abhyasa.blocks.build.events import Emit, fold
from abhyasa.blocks.build import ui as build_ui
from abhyasa.learner import stop_job

POLL = dict(q='Have you used an agent that runs tools?', options=['Yes, often', 'Once or twice', 'Not yet'])

class FakeAgent:
    "A ramabana agent with no model: each turn runs `script(tools, prompt)`, which calls the builder tools as the model would, and gives the reply."
    def __init__(self, script): self.script, self.tools, self.prompts = script, {}, []
    def add_tool(self, f): self.tools[f.__name__] = f
    def ask(self, p, result=True, stop=None, **kw):
        self.prompts.append(p)
        return AttrDict(reply=self.script(self.tools, p, stop), state='complete')
    def close(self): pass

@pytest.fixture
def agent(monkeypatch):
    "The fake agent of the builder, with the names that the builder asked for and the caps it set. `agent.script` is set by each test."
    a = FakeAgent(lambda t, p, s: 'Nothing.')
    def lead(roots, names, **kw):
        a.names, a.kw = names, kw
        return a, AttrDict(scratch='')
    monkeypatch.setattr(build_app, 'ramabana_lead', lead)
    return a

@pytest.fixture
def home(tmp_path, monkeypatch):
    "A temp home with `talks/agents.ipynb`: a title and three sections, one with a short code cell."
    monkeypatch.setattr(Path, 'home', lambda: tmp_path); monkeypatch.setenv('HOME', str(tmp_path))
    p = tmp_path/'talks'/'agents.ipynb'; p.parent.mkdir()
    write_nb(new_nb([mk_cell('# Agents', 'markdown'),
                     mk_cell('## Tool calls', 'markdown'), mk_cell('An agent asks a model what to do.', 'markdown'), mk_cell('tools = ["search"]\nprint(len(tools))'),
                     mk_cell('## The agent loop', 'markdown'), mk_cell('The agent runs in a loop. It stops when the model gives no more tool calls.', 'markdown'),
                     mk_cell('## Memory between turns', 'markdown'), mk_cell('The agent keeps a list of messages. It sends the list again on each turn.', 'markdown')]), p)
    return tmp_path

def new_build(cl):
    "Open Build and give the conversation id."
    return cl.get('/build', follow_redirects=False).headers['location'].split('/')[-1]

def say(cl, lr, bid, text):
    "Send one request and wait for its turn to end; give the conversation part."
    cl.post(f'/build/{bid}/say', data=dict(text=text))
    wait_for(lambda: True if (r := lr.job(f'build:{bid}')) and r.state != 'running' else None, secs=20)
    return cl.get(f'/build/{bid}/chat').text

def make_talk_script(nb):
    def go(t, p, stop):
        t['add_source'](str(nb), 'main'); t['set_brief'](kind='talk', audience='managers', minutes=20, research='off'); t['make_talk'](minutes=20)
        return 'I made the talk for managers, 20 minutes, from your notebook only.'
    return go

def test_build_page_and_start_link(mk, lr, agent):
    "Home links to Build; the page shows the brief, the request box with a mic, and the empty place for the result."
    cl = mk()
    assert 'Make a walk or a talk by talking' in cl.get('/').text
    h = cl.get(f'/build/{new_build(cl)}').text
    assert 'The brief' in h and 'id="build-say"' in h and 'data-mic="label"' in h and 'The walk or the talk shows here' in h

def test_events_fold_to_items():
    "The adapter folds AG-UI events into the items of the pane: messages, a tool call with its stage, data and result, and a stopped run."
    evs = []; em = Emit(evs.append)
    em.text('user', 'Make a talk.')
    t = em.tool_start('make_talk', dict(minutes=20)); em.stage(t, 'Filing the sources')
    assert fold(evs)[1] | {} == dict(kind='tool', id=t, name='make_talk', args=dict(minutes=20), result='', data=None, stages=['Filing the sources'], status='running')
    em.data(t, dict(outline=['A'])); em.tool_end(t, 'Made it.'); em.text('assistant', 'Done.'); em.ev('RUN_FINISHED', state='stopped', message='You stopped it.')
    its = fold(evs)
    assert [i['kind'] for i in its] == ['user', 'tool', 'assistant', 'run'] and its[1]['status'] == 'done' and its[1]['data'] == dict(outline=['A'])

def test_flow_make_a_talk(mk, lr, talk_fake, agent, home):
    "Flow 1: the talk shows on the right, and the brief has the notebook as main, research off, the audience and the minutes. The agent has no web tool."
    talk_fake.rules['You write one poll'] = POLL
    cl = mk(); bid = new_build(cl); nb = home/'talks'/'agents.ipynb'
    agent.script = make_talk_script(nb)
    h = say(cl, lr, bid, f'Make a talk from {nb} for managers, 20 minutes. Use only this notebook.')
    b = lr.build(bid)
    assert b.brief['sources'] == [dict(id=f'file:{nb}', name='agents.ipynb', role='main')] and b.brief['research'] is False
    assert (b.brief['audience'], b.brief['minutes'], b.brief['kind']) == ('managers', 20, 'talk') and b.target.startswith('talk:')
    t = lr.talk(b.target[5:])
    assert t.minutes == 20 and t.brief['audience'] == 'managers' and t.build == bid
    assert 'Making the talk' in h and 'I made the talk for managers' in h and 'research off' in h and 'agents.ipynb' in h
    assert 'Tool calls' in h   # the outline of the talk shows under the tool line
    r = cl.get(f'/build/{bid}/result').text
    assert 'Tool calls' in r and 'a slot of 20 minutes' in r and 'Undo the last change' in r and 'tools = [' in r
    assert agent.kw['web'] is False and 'make_talk' in agent.names and 'research' in agent.names
    p = agent.prompts[0]
    assert 'The owner says:' in p and 'Use only this notebook' in p

def test_flow_change_one_slide_keep_another_and_undo(mk, lr, talk_fake, agent, home):
    "Flow 2: slide 3 changes, slide 2 stays word for word, the pane shows the points before and after, and Undo takes the change back."
    talk_fake.rules['You write one poll'] = POLL
    talk_fake.rules['Rewrite these fields'] = dict(body=['A loop asks the model again.', 'It stops with no tool call.'], notes='Say it simply.')
    cl = mk(); bid = new_build(cl); nb = home/'talks'/'agents.ipynb'
    agent.script = make_talk_script(nb); say(cl, lr, bid, f'Make a talk from {nb}.')
    tid = lr.build(bid).target[5:]; before = lr.talk(tid).slides
    def change(t, p, stop):
        t['keep']('2'); t['edit_slide'](3, show_code='off'); t['change_talk']('Make it simpler, with less code', slides='3')
        return 'Slide 3 is simpler now. Slide 2 stays as it is.'
    agent.script = change
    h = say(cl, lr, bid, 'slide 3 has too much code, make it simpler, and leave slide 2 as it is.')
    after = lr.talk(tid).slides
    assert after[1] == before[1] and after[2]['show']['body'] == ['A loop asks the model again.', 'It stops with no tool call.'] and after[2] != before[2]
    assert lr.build(bid).brief['keep'] == [before[1]['id']]
    assert 'Changing slide 3' in h and 'Before' in h and 'After' in h and 'A loop asks the model again.' in h
    cl.post(f'/build/{bid}/undo')
    assert lr.talk(tid).slides[2]['show']['body'] == before[2]['show']['body'] and lr.talk(tid).slides[1] == before[1]   # Undo takes back the rewrite
    def again(t, p, stop):   # a change to a kept slide is refused, and the agent is told why
        return t['change_talk']('Shorter', slides='2')
    agent.script = again
    say(cl, lr, bid, 'make slide 2 shorter')
    assert 'is kept' in fold(lr.build(bid).events)[-2]['result'] and lr.talk(tid).slides[1] == before[1]

def test_remake_keeps_kept_slides(mk, lr, talk_fake, agent, home):
    "A remake of the whole talk with a new instruction keeps each kept slide word for word."
    talk_fake.rules['You write one poll'] = POLL
    cl = mk(); bid = new_build(cl); nb = home/'talks'/'agents.ipynb'
    agent.script = make_talk_script(nb); say(cl, lr, bid, f'Make a talk from {nb}.')
    tid = lr.build(bid).target[5:]
    talk_fake.rules['You write one slide of a talk'] = dict(SLIDE, points=['Other words.', 'More other words.'])
    lr.put_talk({**lr.talk(tid), 'slides': [{**s, 'notes': ''} if s.get('kind') == 'idea' else s for s in lr.talk(tid).slides]})
    kept = lr.talk(tid).slides[1]
    agent.script = lambda t, p, s: (t['keep']('2'), t['change_talk']('for engineers'))[1]
    say(cl, lr, bid, 'make it again for engineers, but keep slide 2')
    assert lr.talk(tid).slides[1] == kept and lr.talk(tid).change and 'for engineers' in lr.talk(tid).change

def test_owner_brief_change_goes_to_the_next_turn(mk, lr, agent):
    "A change to the brief by hand saves at once, shows in the pane, and the next turn starts with a note of it."
    cl = mk(); bid = new_build(cl)
    h = cl.post(f'/build/{bid}/brief', data=dict(research='off', aim='become technical')).text
    assert lr.build(bid).brief['research'] is False and 'research off' in h
    say(cl, lr, bid, 'hello')
    assert agent.prompts[-1].startswith('The owner changed: aim = become technical; research off.') and lr.build(bid).note == ''

def test_research_items_wait_for_the_owner(mk, lr, agent, monkeypatch):
    "Research gives items with Keep and Drop; nothing is kept until the owner presses Keep, and a kept item is an extra source."
    monkeypatch.setattr(build_app, 'web_search', lambda q, n: [dict(href='https://ex.org/a', title='Attention notes', body='About attention.'), dict(href='https://ex.org/b', title='B', body='')])
    cl = mk(); bid = new_build(cl)
    agent.script = lambda t, p, s: (t['set_brief'](kind='walk', goal='attention in transformers', research='on'), t['research']('attention in transformers'))[1]
    h = say(cl, lr, bid, 'Make me a walk on attention in transformers. Research extra material.')
    assert 'Attention notes' in h and 'Keep' in h and 'Drop' in h and lr.build(bid).brief['sources'] == []
    h = cl.post(f'/build/{bid}/item', data=dict(url='https://ex.org/a', role='extra')).text
    b = lr.build(bid)
    assert b.brief['sources'] == [dict(id='link:https://ex.org/a', name='Attention notes', role='extra', found=True)] and 'Kept' in h
    cl.post(f'/build/{bid}/item', data=dict(url='https://ex.org/b', role='dropped'))
    agent.script = lambda t, p, s: t['set_brief'](research='off')
    say(cl, lr, bid, 'drop the extra material and use only my sources')
    b = lr.build(bid)
    assert b.brief['research'] is False and b.brief['sources'][0]['role'] == 'dropped' and 'kept Attention notes' in agent.prompts[-1]
    agent.script = lambda t, p, s: t['research']('more')
    say(cl, lr, bid, 'research more')
    assert 'Research is off' in fold(lr.build(bid).events)[-2]['result']

def test_change_with_the_builder_beside_a_talk(mk, lr, talk_fake, agent, home):
    "Flow 4: the talk editor offers Change with the builder in the side pane; it opens the conversation of the talk with a brief from the talk."
    talk_fake.rules['You write one poll'] = POLL
    cl = mk(); nb = home/'talks'/'agents.ipynb'
    r = cl.post('/walk/new', data=dict(q='', sources=[f'file:{nb}'], chips='1', talk='1')).text
    key = re.search(r'data-job="talk:(src:[^"]+)"', r)[1]
    tid = wait_for(lambda: cl.get('/talk/job', params=dict(jid=key)).headers.get('hx-redirect'), secs=20).split('/')[-1].split('?')[0]
    h = cl.get(f'/t/{tid}').text
    assert 'Change with the builder' in h and f'/build/open?talk={tid}' in h
    loc = cl.get(f'/build/open?talk={tid}&pane=1', follow_redirects=False).headers['location']
    bid = loc.split('/')[2].split('?')[0]
    assert lr.talk(tid).build == bid and lr.build(bid).brief['sources'][0]['id'] == f'file:{nb}'
    p = cl.get(loc).text
    assert 'id="build-say"' in p and 'build-result' not in p   # in the pane: only the conversation; the editor is beside it
    agent.script = lambda t, p, s: t['edit_slide'](2, title='How the loop works')
    say(cl, lr, bid, 'call slide 2 How the loop works')
    assert lr.talk(tid).slides[1]['title'] == 'How the loop works' and 'Talk: ' not in agent.prompts[-1][:5]
    assert cl.get(f'/build/open?talk={tid}', follow_redirects=False).headers['location'] == f'/build/{bid}'   # the same conversation again

def test_make_demo_puts_a_live_demo_on_the_slide(mk, lr, talk_fake, agent, home, monkeypatch):
    "Flow 5: make_demo wraps the demo maker, and the slide shows the demo live in the preview."
    from rupaka.spec import gallery
    talk_fake.rules['You write one poll'] = POLL
    cl = mk(); bid = new_build(cl); nb = home/'talks'/'agents.ipynb'
    agent.script = make_talk_script(nb); say(cl, lr, bid, f'Make a talk from {nb}.')
    tid = lr.build(bid).target[5:]
    asked = []
    def maker(l, ask, slug, said=''):
        asked.append((slug, said)); return l.put_demo(gallery()['softmax-temperature'], slug)
    monkeypatch.setattr(build_app, 'demo_maker', maker)
    agent.script = lambda t, p, s: t['make_demo'](2, 'move the temperature and see the probabilities change')
    say(cl, lr, bid, 'add an interactive demo on slide 2 where people move the temperature')
    s = lr.talk(tid).slides[1]
    assert s['show']['demo'] and 'demo' in s['beats'] and asked[0][1].startswith('move the temperature')
    r = cl.get(f'/build/{bid}/result').text
    assert 'class="demo"' in r and 'data-demo=' in r
    cl.post(f'/t/{tid}/start')
    assert 'data-demo=' in cl.get(f'/t/{tid}/present').text

def test_stop_ends_the_turn(mk, lr, agent):
    "Stop on the job of a turn: the tools refuse after it, and the conversation says that you stopped it."
    import threading
    cl = mk(); bid = new_build(cl); go = threading.Event(); seen = []
    def slow(t, p, stop):
        go.wait(5); seen.append(t['show']()); return ''
    agent.script = slow
    cl.post(f'/build/{bid}/say', data=dict(text='do something'))
    wait_for(lambda: True if (r := lr.job(f'build:{bid}')) and r.state == 'running' else None)
    from abhyasa.core.ui import JOB_STOP
    cl.post(JOB_STOP, data=dict(key=f'build:{bid}')); go.set()
    wait_for(lambda: True if lr.job(f'build:{bid}').state != 'running' else None, secs=10)
    assert 'Stop' in seen[0] and lr.job(f'build:{bid}').state == 'stopped'
    assert 'You stopped it.' in cl.get(f'/build/{bid}/chat').text

def test_the_agent_continues_after_a_restart(mk, lr, agent):
    "A new agent for a saved conversation gets a recap of it in its first prompt."
    cl = mk(); bid = new_build(cl)
    agent.script = lambda t, p, s: 'Hello. What do you want to make?'
    say(cl, lr, bid, 'hi')
    cl2 = mk()   # a new app: no agent in memory
    say(cl2, lr, bid, 'make a walk')
    assert 'Earlier in this conversation:' in agent.prompts[-1] and 'The owner: hi' in agent.prompts[-1]

def test_rk_ask_goes_to_the_request_box():
    "The page listens for rk-ask from a rupaka demo, and puts a message about the demo and its state in the request box."
    js = (Path(build_app.__file__).parent/'build.js').read_text()
    assert "addEventListener('rk-ask'" in js and 'About the demo' in js and "closest('[data-slide]')" in js
