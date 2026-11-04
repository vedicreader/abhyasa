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
    return cl.get('/build', follow_redirects=False).headers['location'].split('/')[2].split('?')[0]

def ends(lr, bid):
    "The count of the turns of conversation `bid` that ended."
    return sum(e['type'] in ('RUN_FINISHED', 'RUN_ERROR') for e in lr.build(bid).events)

def say(cl, lr, bid, text):
    """Send one request and wait for its turn to end; give the conversation part. It waits for the end event of this turn, not for the job row:
    the row of the turn before says `done` until the new turn starts, so a wait on the row can return before the new turn ran."""
    n = ends(lr, bid)
    cl.post(f'/build/{bid}/say', data=dict(text=text))
    wait_for(lambda: True if ends(lr, bid) > n and lr.job(f'build:{bid}').state != 'running' else None, secs=20)
    return cl.get(f'/build/{bid}/chat').text

def make_talk_script(nb):
    def go(t, p, stop):
        t['add_source'](str(nb), 'main'); t['set_brief'](kind='talk', audience='managers', minutes=20, research='off'); t['make_talk'](minutes=20)
        return 'I made the talk for managers, 20 minutes, from your notebook only.'
    return go

def test_build_page_and_start_link(mk, lr, agent):
    "Home links to Build. Build is the empty page at the left with the builder open in the side pane; in the pane, the brief, the first message and the box with a mic."
    cl = mk()
    assert 'Make a walk or a talk by talking' in cl.get('/').text
    loc = cl.get('/build', follow_redirects=False).headers['location']
    bid = new_build(cl)
    assert loc.startswith('/build/') and '?rh=%2Fbuild%2F' in loc
    h = cl.get(loc).text
    assert 'The walk or the talk that you make shows here.' in h and 'id="rh-pane"' in h and 'class="rh-open"' in h
    p = cl.get(f'/build/{bid}?pane=1').text
    assert 'Your brief' in p and 'id="build-say"' in p and 'data-mic="label"' in p and build_ui.FIRST in p and 'No sources yet. abhyasa uses the web.' in p

def test_events_fold_to_items():
    "The adapter folds AG-UI events into the items of the pane: messages, a tool call with its stage, data and result, and a stopped run."
    evs = []; em = Emit(evs.append)
    em.text('user', 'Make a talk.')
    t = em.tool_start('make_talk', dict(minutes=20)); em.stage(t, 'Filing the sources')
    x = fold(evs)[1]
    assert {k: x[k] for k in ('kind', 'id', 'name', 'args', 'result', 'data', 'stages', 'status')} == dict(kind='tool', id=t, name='make_talk', args=dict(minutes=20), result='', data=None, stages=['Filing the sources'], status='running')
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
    assert 'Making the talk' in h and 'I made the talk for managers' in h and 'your material only' in h and 'agents.ipynb' in h
    assert 'Tool calls' in h and 'What I read' in h and 'What changed' in h and 'agents.ipynb (main)' in h   # the outline, and the lines after the turn
    assert cl.get(f'/build/{bid}', follow_redirects=False).headers['location'].startswith(f'/t/{t.id}?rh=')   # Build is the talk now, with the builder open
    e = cl.get(f'/t/{t.id}').text
    assert 'Tool calls' in e and 'Change with the builder' in e
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
    assert 'Changing slide 3' in h and '<b class="bd-n">Slide 3</b>' in h and 'Before' in h and 'After' in h and ']' not in h.split('build-log')[1].split('composer')[0].replace('[', '') and 'A loop asks the model again.' in h
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
    assert 'id="build-say"' in p and 'Your brief' in p and '<nav' not in p   # in the pane: only the builder; the editor is beside it
    agent.script = lambda t, p, s: t['edit_slide'](2, title='How the loop works')
    say(cl, lr, bid, 'call slide 2 How the loop works')
    assert lr.talk(tid).slides[1]['title'] == 'How the loop works' and 'Talk: ' not in agent.prompts[-1][:5]
    assert cl.get(f'/build/open?talk={tid}', follow_redirects=False).headers['location'].startswith(f'/t/{tid}?rh=%2Fbuild%2F{bid}')   # the same conversation again

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
    h = cl.get(f'/build/{bid}/chat').text
    assert 'class="bd-demo"' in h and 'data-demo=' in h and 'On slide 2' in h
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

class NativeAgent(FakeAgent):
    "A ramabana agent that gives AG-UI events itself (`Agent.events`, `emit`), as ramabana's branch `agui-events` does."
    def __init__(self, calls): super().__init__(None); self.calls, self.q = calls, []
    def emit(self, name, value=None): self.q.append(dict(type='CUSTOM', name=name, value=value))
    def events(self, p, on_registered=None, **kw):
        self.prompts.append(p)
        yield dict(type='RUN_STARTED', runId='r1')
        for k, (name, args) in enumerate(self.calls):
            yield dict(type='TOOL_CALL_START', toolCallId=f'c{k}', toolCallName=name); yield dict(type='TOOL_CALL_ARGS', toolCallId=f'c{k}', delta=json.dumps(args))
            yield dict(type='TOOL_CALL_END', toolCallId=f'c{k}')
            out = self.tools[name](**args)
            yield from self.q; self.q.clear()
            yield dict(type='TOOL_CALL_RESULT', toolCallId=f'c{k}', content=out)
        yield dict(type='TEXT_MESSAGE_START', messageId='m1', role='assistant')
        for w in ('Made ', 'the ', 'talk.'): yield dict(type='TEXT_MESSAGE_CONTENT', messageId='m1', delta=w)
        yield dict(type='TEXT_MESSAGE_END', messageId='m1'); yield dict(type='RUN_FINISHED', runId='r1', result=dict(state='completed'))

def test_native_events_of_ramabana(mk, lr, talk_fake, home, monkeypatch):
    "With a ramabana that gives AG-UI events, the pane reads them as they come: the tool lines, the outline from `emit`, and one message for the reply."
    talk_fake.rules['You write one poll'] = POLL
    nb = home/'talks'/'agents.ipynb'
    a = NativeAgent([('add_source', dict(ref=str(nb), role='main')), ('make_talk', dict(minutes=20))])
    monkeypatch.setattr(build_app, 'ramabana_lead', lambda roots, names, **kw: (a, AttrDict(scratch='')))
    cl = mk(); bid = new_build(cl)
    h = say(cl, lr, bid, f'Make a talk from {nb}.')
    its = fold(lr.build(bid).events)
    assert [i['kind'] for i in its] == ['user', 'tool', 'tool', 'assistant'] and its[-1]['text'] == 'Made the talk.'
    assert its[2]['data']['outline'] and 'Filing the sources' in its[2]['stages'] and 'Tool calls' in h
    assert sum(e['type'] == 'TEXT_MESSAGE_CONTENT' for e in lr.build(bid).events) == 2   # the user message and one for the reply, not one for each piece

def test_askable_follows_rupaka():
    "The preview asks rupaka for the ask control only when this rupaka has `askable`."
    from inspect import signature
    from rupaka.render import Demo
    assert build_ui.askable(True) == ({'askable': True} if 'askable' in signature(Demo).parameters else {})

def test_keep_all_and_drop_all(mk, lr, agent, monkeypatch):
    "Keep all keeps each open find; a find that you dropped first stays dropped."
    monkeypatch.setattr(build_app, 'web_search', lambda q, n: [dict(href=f'https://ex.org/{k}', title=f'T{k}', body='') for k in range(3)])
    cl = mk(); bid = new_build(cl)
    agent.script = lambda t, p, s: t['research']('x')
    h = say(cl, lr, bid, 'research x')
    assert '3 of 3 are open. The builder adds only what you keep.' in h and 'bd-call done ask' in h
    cl.post(f'/build/{bid}/item', data=dict(url='https://ex.org/0', role='dropped'))
    h = cl.post(f'/build/{bid}/item', data=dict(url='*', role='extra', urls='https://ex.org/0 https://ex.org/1 https://ex.org/2')).text
    roles = {f['url']: f['role'] for f in lr.build(bid).brief['found']}
    assert roles == {'https://ex.org/0': 'dropped', 'https://ex.org/1': 'extra', 'https://ex.org/2': 'extra'} and 'You decided each find.' in h
    assert [s['id'] for s in lr.build(bid).brief['sources']] == ['link:https://ex.org/1', 'link:https://ex.org/2']

def test_start_opens_the_builder(mk, lr, agent, home):
    "Start in the Start box opens the page with the builder open: the text is the first message, the chips are main sources, and the turn runs."
    cl = mk(); nb = home/'talks'/'agents.ipynb'
    agent.script = lambda t, p, s: 'Fine.'
    r = cl.post('/build/start', data=dict(q='for managers', sources=[f'file:{nb}'], talk='1')).json()
    bid = r['url'].split('/')[2].split('?')[0]
    wait_for(lambda: True if (j := lr.job(f'build:{bid}')) and j.state != 'running' else None, secs=10)
    b = lr.build(bid)
    assert b.brief['kind'] == 'talk' and b.brief['sources'][0] == dict(id=f'file:{nb}', name='agents.ipynb', role='main')
    assert fold(b.events)[0] == dict(kind='user', text='for managers') and 'The owner says:\nfor managers' in agent.prompts[0]
    assert cl.post('/build/start', data=dict(q='')).status_code == 422   # an empty box: the Start box does its own work

def test_no_change_while_the_talk_runs(mk, lr, talk_fake, agent, home):
    "During a run of the talk the builder changes nothing, and says why."
    talk_fake.rules['You write one poll'] = POLL
    cl = mk(); bid = new_build(cl); nb = home/'talks'/'agents.ipynb'
    agent.script = make_talk_script(nb); say(cl, lr, bid, f'Make a talk from {nb}.')
    tid = lr.build(bid).target[5:]; cl.post(f'/t/{tid}/start'); before = lr.talk(tid).slides
    agent.script = lambda t, p, s: t['edit_slide'](2, title='New')
    say(cl, lr, bid, 'rename slide 2')
    assert lr.talk(tid).slides == before and build_ui.RUNNING in fold(lr.build(bid).events)[-2]['result']

def test_walk_from_your_sources_only(mk, lr, walk_fake, agent, home):
    """With research off, a walk reads only your sources, and a remake of the walk is one change with an Undo on the same walk.
    The plan picks the check of each idea at random (`check_for`), so two plans of one source can differ: the remake is always one change."""
    md = home/'notes.md'; md.write_text('# Attention\n\nScores become weights with softmax. The output is a weighted sum of the values.\n')
    cl = mk(); bid = new_build(cl)
    agent.script = lambda t, p, s: (t['add_source'](str(md), 'main'), t['set_brief'](kind='walk', goal='attention', research='off'), t['make_walk']())[2]
    say(cl, lr, bid, f'Make me a walk on attention from {md}. Use only my notes.')
    jid = lr.build(bid).target[5:]; j = lr.journey(jid)
    assert j and j.steps and not j.get('parent') and lr.build(bid).brief['research'] is False
    assert all((s.get('read') or {}).get('src', 'vault').startswith('vault') for s in j.steps)
    before = lr.journey(jid).steps
    lr.merge_journey(jid, steps=[{**s, 'note': 'my old note'} for s in before])   # the walk now differs from a fresh walk of the notes
    agent.script = lambda t, p, s: t['make_walk']()
    say(cl, lr, bid, 'make it again')
    r = fold(lr.build(bid).events)[-2]['result']
    assert r.startswith('Made the walk again from the brief') and lr.edits('walk', jid)[0].what == 'Made the walk again from the brief.' and 'have a passage' in r
    assert lr.build(bid).target == f'walk:{jid}' and not any(s.get('note') == 'my old note' for s in lr.journey(jid).steps)
    assert sum((w.get('parent') or {}).get('for') == 'talk' for w in lr.journeys()) == 0   # the plan of the remake is not left behind
    cl.post(f'/build/{bid}/undo')
    assert all(s.get('note') == 'my old note' for s in lr.journey(jid).steps)
def test_make_talk_fits_the_slot(mk, lr, talk_fake, agent, home):
    "A talk for a short slot leaves out ideas from the end until it fits, and the tool says the real minutes against the slot, as the editor counts them."
    from abhyasa.show import talk_minutes
    talk_fake.rules['You write one poll'] = POLL
    cl = mk(); bid = new_build(cl); nb = home/'talks'/'agents.ipynb'
    agent.script = lambda t, p, s: (t['add_source'](str(nb), 'main'), t['make_talk'](minutes=15))[1]
    say(cl, lr, bid, f'Make a 15 minute talk from {nb}.')
    t = lr.talk(lr.build(bid).target[5:])
    r = fold(lr.build(bid).events)[-2]['result']
    assert t.minutes == 15 and talk_minutes(t) <= 15 and f'about {talk_minutes(t)} minutes for a slot of 15 minutes' in r and 'over the slot' not in r
    assert 'To fit the slot, I left out' in r and len([s for s in t.slides if s['kind'] == 'idea']) < 3
    assert f'About {talk_minutes(t)} min of a 15 min slot' in cl.get(f'/t/{t.id}').text   # the editor says the same

def test_research_ends_the_turn(mk, lr, agent, monkeypatch):
    "After research the turn ends: a later tool in the same turn is refused, and the builder says that the finds wait for you."
    monkeypatch.setattr(build_app, 'web_search', lambda q, n: [dict(href='https://ex.org/a', title='A', body=''), dict(href='https://ex.org/b', title='B', body='')])
    cl = mk(); bid = new_build(cl)
    agent.script = lambda t, p, s: (t['set_brief'](kind='walk', goal='attention'), t['research']('attention'), t['make_walk']())[2]
    h = say(cl, lr, bid, 'Make a walk on attention. Research extra material.')
    assert lr.build(bid).target == '' and fold(lr.build(bid).events)[-1]['text'] == 'I found 2 items. Keep or drop each one, then tell me what to do next.'
    assert 'make_walk' not in [i.get('name') for i in fold(lr.build(bid).events)] or build_app.WAIT_FINDS in str(agent.prompts)

def test_one_summary_line_for_each_turn(mk, lr, agent):
    "The steps that the builder tells as it works fold into What I did; only its last line shows."
    cl = mk(); bid = new_build(cl)
    def go(t, p, s):
        Emit(lambda e: build_app_emit(lr, bid, e)).text('assistant', 'I keep slide 2 first.')
        return 'I changed nothing.'
    def build_app_emit(lr, bid, e): lr.put_build({**lr.build(bid), 'events': [*lr.build(bid).events, e]})
    agent.script = go
    h = say(cl, lr, bid, 'hello')
    assert h.count('class="bd-said"') == 1 and 'What I did' in h and 'I keep slide 2 first.' in h.split('What I did')[1]

def test_keep_on_the_talk_page_and_hand_edit_lines(mk, lr, talk_fake, agent, home):
    "Keep on a slide of the talk editor writes keep of the brief, which the builder reads; a hand edit adds a quiet line to the conversation and a note for the next turn."
    talk_fake.rules['You write one poll'] = POLL
    cl = mk(); bid = new_build(cl); nb = home/'talks'/'agents.ipynb'
    agent.script = make_talk_script(nb); say(cl, lr, bid, f'Make a talk from {nb}.')
    tid = lr.build(bid).target[5:]; sid = lr.talk(tid).slides[1]['id']
    h = cl.post(f'/t/{tid}/slide', data=dict(sid=sid, act='keep')).text
    assert lr.talk(tid).brief['keep'] == [sid] and 'pill kept' in h and '>Kept <kbd>F</kbd>' in h.replace('\n', '')
    cl.post(f'/t/{tid}/slide', data=dict(sid=lr.talk(tid).slides[2]['id'], act='edit', title='My title'))
    c = cl.get(f'/build/{bid}/chat').text
    assert 'You changed it by hand: You kept slide 2.' in c and 'class="bd-note"' in c and 'title of slide 3' in c
    agent.script = lambda t, p, s: t['change_talk']('shorter', slides='2')
    say(cl, lr, bid, 'make slide 2 shorter')
    assert 'by hand: You kept slide 2.' in agent.prompts[-1] and 'is kept' in fold(lr.build(bid).events)[-2]['result']

def test_send_from_the_page_solo_tabs_and_labels(mk, lr, talk_fake, agent, home):
    "The change box and Change this slide open the builder with the words sent at once; a narrow window has the Builder and Result tabs; a change shows the label of each source."
    talk_fake.rules['You write one poll'] = POLL
    talk_fake.rules['Rewrite these fields'] = dict(body=['Short point one.', 'Short point two.'], notes='Note.')
    cl = mk(); bid = new_build(cl); nb = home/'talks'/'agents.ipynb'
    agent.script = make_talk_script(nb); say(cl, lr, bid, f'Make a talk from {nb}.')
    tid = lr.build(bid).target[5:]
    agent.script = lambda t, p, s: t['change_talk']('shorter', slides='3')
    n = ends(lr, bid)
    loc = cl.get(f'/build/open?talk={tid}&pane=1&say=Slide 3: shorter&send=1', follow_redirects=False).headers['location']
    assert 'say=' not in loc
    wait_for(lambda: True if ends(lr, bid) > n and lr.job(f'build:{bid}').state != 'running' else None, secs=20)
    its = fold(lr.build(bid).events)
    assert [i for i in its if i['kind'] == 'user'][-1]['text'] == 'Slide 3: shorter' and its[-2]['name'] == 'change_talk'
    c = cl.get(f'/build/{bid}/chat').text
    assert 'data-landed="3"' in c and ('Your source' in c or "abhyasa&#x27;s words, no source" in c or "abhyasa's words, no source" in c)
    s = cl.get(f'/build/{bid}?solo=1').text
    assert 'class="subtabs bd-tabs"' in s and f'href="/t/{tid}"' in s and 'id="build-say"' in s
    assert 'bd-tabs' in cl.get(f'/t/{tid}').text and 'Change this slide' in cl.get(f'/t/{tid}').text

def test_a_walk_titled_with_a_path_shows_a_readable_title():
    "A walk whose title is a path shows the title of its notebook, else its file name in words; the path stays in a tooltip. A plain title stays."
    from abhyasa.blocks.walk.ui import walk_title, Rail
    assert walk_title(dict(title='panchanga/00_what_is_panchanga')) == 'What is panchanga'
    assert walk_title(dict(title='Attention, step by step')) == 'Attention, step by step'
    from fastcore.xml import to_xml
    from abhyasa.path import walk_state
    j = AttrDict(id='w1', title='panchanga/00_what_is_panchanga', steps=[])
    h = to_xml(Rail(j, AttrDict(sections=[], steps=[], done=0, total=0), {}, 0))
    assert '>What is panchanga<' in h and 'title="panchanga/00_what_is_panchanga"' in h
    css = (Path(build_app.__file__).parents[1]/'walk'/'walk.css').read_text()
    assert '.walk-layout > * { min-width: 0; }' in css and 'overflow-wrap: anywhere' in css

def test_the_line_of_a_turn_comes_from_the_tools(mk, lr, talk_fake, agent, home):
    "The line of a turn says what the tools did; a reply that claims a change that no tool made is flagged; a call that did not work goes into What did not work."
    talk_fake.rules['You write one poll'] = POLL
    cl = mk(); bid = new_build(cl); nb = home/'talks'/'agents.ipynb'
    agent.script = make_talk_script(nb); say(cl, lr, bid, f'Make a talk from {nb}.')
    agent.script = lambda t, p, s: (t['edit_slide'](99, title='x'), 'I added the rule of 72 to slide 3.')[1]
    h = say(cl, lr, bid, 'add the rule of 72')
    last = h.split('class="bd-me"')[-1]
    assert 'Nothing changed in the walk or the talk in this turn.' in last and 'What did not work' in last and 'Changing slide 99' not in last.split('What did not work')[0]
    agent.script = lambda t, p, s: (t['edit_slide'](2, title='New title'), 'I renamed it and also added a demo.')[1]
    h = say(cl, lr, bid, 'rename slide 2')
    last = h.split('class="bd-me"')[-1]
    assert 'Changed the title of slide 2.' in last.split('What the builder said')[0] and 'also added a demo' in last.split('What the builder said')[1]

def test_undo_takes_back_a_whole_turn(mk, lr, talk_fake, agent, home):
    "A turn that changed three slides comes back whole with one Undo."
    talk_fake.rules['You write one poll'] = POLL
    cl = mk(); bid = new_build(cl); nb = home/'talks'/'agents.ipynb'
    agent.script = make_talk_script(nb); say(cl, lr, bid, f'Make a talk from {nb}.')
    tid = lr.build(bid).target[5:]; before = lr.talk(tid).slides
    agent.script = lambda t, p, s: [t['edit_slide'](n, title=f'T{n}') for n in (2, 3, 4)][-1]
    say(cl, lr, bid, 'rename slides 2 to 4')
    assert [s['title'] for s in lr.talk(tid).slides[1:4]] == ['T2', 'T3', 'T4']
    cl.post(f'/build/{bid}/undo')
    assert [s['title'] for s in lr.talk(tid).slides] == [s['title'] for s in before]

def test_a_second_demo_goes_on_a_new_slide_and_a_walk_gets_demos(mk, lr, talk_fake, agent, home, monkeypatch):
    "A slide with a demo keeps it, and a second demo goes on a new slide after it; a walk step can get a demo too."
    from rupaka.spec import gallery
    talk_fake.rules['You write one poll'] = POLL
    monkeypatch.setattr(build_app, 'demo_maker', lambda l, ask, slug, said='': l.put_demo({**gallery()['softmax-temperature'], 'id': 'demo-' + said.split()[1]}, slug))
    cl = mk(); bid = new_build(cl); nb = home/'talks'/'agents.ipynb'
    agent.script = make_talk_script(nb); say(cl, lr, bid, f'Make a talk from {nb}.')
    tid = lr.build(bid).target[5:]; n = len(lr.talk(tid).slides)
    agent.script = lambda t, p, s: (t['make_demo'](2, 'a first demo'), t['make_demo'](2, 'a second demo'))[1]
    say(cl, lr, bid, 'two demos on slide 2')
    ss = lr.talk(tid).slides
    assert len(ss) == n + 1 and ss[1]['show']['demo'] and ss[2]['show']['demo'] and ss[2]['title'].endswith('a second demo') and ss[2]['beats'] == ['demo']
    md = home/'n.md'; md.write_text('# Attention\n\nScores become weights with softmax.\n')
    bid2 = new_build(cl)
    agent.script = lambda t, p, s: (t['add_source'](str(md)), t['set_brief'](kind='walk', research='off'), t['make_walk'](), t['make_demo'](1, 'move the scores'))[3]
    say(cl, lr, bid2, 'a walk with a demo on step 1')
    j = lr.journey(lr.build(bid2).target[5:])
    assert j.steps[0]['check']['kind'] == 'demo' and lr.demo_for(j.steps[0]['slug'])

def test_page_titles_and_rules_and_tables():
    "A search result loses its breadcrumb; a slide fix is not a rule; a table in a passage is a real table, and an entity shows as its sign."
    from fastcore.xml import to_xml
    from abhyasa.blocks.talk.ui import Said
    assert build_app.page_title('www.geeksforgeeks.org › nlp › self-attention-in-nlpSelf - Attention in NLP - GeeksforGeeks') == 'Self - Attention in NLP - GeeksforGeeks'
    h = to_xml(Said('| a | b |\n|---|---|\n| the Moon&#x27;s | 2 |'))
    assert '<table>' in h and "Moon's" in h and '&amp;#x27;' not in h

def test_a_kept_find_is_filed_and_read_as_a_document(mk, lr, agent, monkeypatch):
    "A kept web find is filed first and goes to the planner as a document (`doc:`), so its passages can reach the steps."
    seen = []
    monkeypatch.setattr(build_app, 'file_chip', lambda l, c: [AttrDict(doc_id='d1', shelf='store', title='Kept page', url=c[5:])])
    def spy(l, ask, chips, *a, **kw): seen.append(list(chips)); raise ValueError('stop here')
    monkeypatch.setattr(build_app, 'walk_for_talk', spy)
    cl = mk(); bid = new_build(cl)
    lr.put_build({**lr.build(bid), 'brief': {**lr.build(bid).brief, 'kind': 'walk', 'goal': 'war', 'sources': [dict(id='link:https://ex.org/a', name='A', role='extra', found=True)]}})
    agent.script = lambda t, p, s: t['make_walk']()
    say(cl, lr, bid, 'make the walk')
    assert seen == [['doc:d1']]
