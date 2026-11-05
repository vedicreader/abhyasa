"What the builder shows after a refused step and after an Undo, how it sorts a shape rule into the rules, how it names a find, and when it makes a walk."
from talk_data import *
from fastcore.basics import AttrDict
from fastcore.xml import to_xml
import abhyasa.blocks.build.app as build_app
from abhyasa.blocks.build import ui as build_ui
from abhyasa.blocks.build.events import fold
from test_build import agent, home, new_build, say, make_talk_script, POLL

def last_turn(h): return h.split('class="bd-me"')[-1]

def test_a_refused_step_is_not_a_change(mk, lr, talk_fake, agent, home):
    "A step that changes nothing is said in the line of the turn, but it is not under What changed, and it has no See it and no Undo."
    talk_fake.rules['You write one poll'] = POLL
    cl = mk(); bid = new_build(cl); nb = home/'talks'/'agents.ipynb'
    agent.script = make_talk_script(nb); say(cl, lr, bid, f'Make a talk from {nb}.')
    n = cl.get(f'/build/{bid}/chat').text.split('data-changes="')[1].split('"')[0]
    agent.script = lambda t, p, s: (t['edit_slide'](2), t['make_talk'](), 'I did not change it.')[2]
    h = say(cl, lr, bid, 'change slide 2')
    last = last_turn(h)
    assert 'Nothing to change.' in last and 'A talk exists.' in last
    assert 'What changed' not in last and 'See it' not in last and 'data-undo' not in last
    assert h.split('data-changes="')[1].split('"')[0] == n   # the page at the left does not load again

def test_refused_words_match_the_tools():
    "Each refusal of a tool that changes things reads as no change; a real change, also with a near step left out, does not."
    r = lambda t: build_ui.refused(dict(status='done', result=t))
    assert all(map(r, ['The walk has a step on this already: step 2, “Alliances”. Nothing changed. Say “add it anyway” for a second step.',
                       'The tutor found nothing new to change.', 'Nothing to change.', 'Nothing changed.', 'A talk exists. Use change_talk to change it.',
                       'The walk from the brief is the same as the walk now. Nothing changed.', 'Nothing to undo.', build_app.RESEARCH_FIRST.format('walk')]))
    assert not any(map(r, ['Changed the walk: 1 change. Added “Treaties” as step 3. The walk has a step on this already: step 2, “Alliances”.', 'Undone: Changed slide 2.']))

def test_after_an_undo_only_the_last_words_show_marked(mk, lr, talk_fake, agent, home):
    "After Undo, What the builder said shows only the last words of the turn, marked as before the Undo. The summary line says the Undo."
    talk_fake.rules['You write one poll'] = POLL
    cl = mk(); bid = new_build(cl); nb = home/'talks'/'agents.ipynb'
    agent.script = make_talk_script(nb); say(cl, lr, bid, f'Make a talk from {nb}.')
    agent.script = lambda t, p, s: (t['edit_slide'](2, title='Tools'), 'I renamed slide 2 to Tools.')[1]
    say(cl, lr, bid, 'rename slide 2 to Tools')
    h = cl.post(f'/build/{bid}/undo').text
    said = last_turn(h).split('What the builder said')[1]
    assert 'Before the Undo:' in said and 'I renamed slide 2 to Tools.' in said and 'Undone:' in last_turn(h).split('What the builder said')[0]

def test_earlier_words_of_a_turn_fold():
    "A turn with words before and after its tool calls shows only its last words, so the words cannot contradict each other."
    items = [dict(kind='user', text='rename slide 2'), dict(kind='assistant', text='I will rename slide 3.'),
             dict(kind='tool', id='1', name='edit_slide', args=dict(slide=2), result='Changed the title of slide 2.', data=None, stages=[], status='done', secs=1),
             dict(kind='assistant', text='I renamed slide 2.')]
    h = to_xml(build_ui.Turn(build_ui.turns(items)[0], AttrDict(id='b1', brief={}), build_app.CHANGERS, last=True))
    said = h.split('What the builder said')[1]
    assert 'I renamed slide 2.' in said and 'rename slide 3' not in said and 'Before the Undo' not in said

def test_a_shape_rule_in_the_aim_goes_to_the_rules(mk, lr, agent):
    "A rule about the shape of the talk that the agent or the owner puts in the aim goes to the rules when the brief is set; the rest stays the aim."
    cl = mk(); bid = new_build(cl)
    agent.script = lambda t, p, s: t['set_brief'](kind='talk', aim='Make them technical. Start with a poll.', rules='Where they conflict, use the notebook.')
    h = say(cl, lr, bid, 'a technical talk that starts with a poll')
    br = lr.build(bid).brief
    assert br['aim'] == 'Make them technical.' and br['rules'] == 'Where they conflict, use the notebook. Start with a poll.'
    assert 'value="Make them technical."' in h and 'Start with a poll.' in h.split('Rules')[1]
    cl.post(f'/build/{bid}/brief', data=dict(aim='End with the notebook.'))   # by hand too, and a rule that is there already is not added again
    cl.post(f'/build/{bid}/brief', data=dict(aim='End with the notebook.'))
    br = lr.build(bid).brief
    assert br['aim'] == '' and br['rules'].count('End with the notebook.') == 1

def test_a_find_has_a_clean_name_and_takes_the_title_of_its_page(mk, lr, agent, monkeypatch):
    "Research gives each find a clean name: no markup, no word of the link glued on, and a name from the link for an untitled page. A kept find takes the title of its page when it is filed."
    monkeypatch.setattr(build_app, 'web_search', lambda q, n: [dict(href='https://ex.org/fourier-series.html', title='untitled', body=''),
                                                               dict(href='https://ex.org/a', title='__What is a Fourier Series?', body=''),
                                                               dict(href='https://bbc.co.uk/articles/x', title='articlesCauses of World War One - BBC', body='')])
    cl = mk(); bid = new_build(cl)
    agent.script = lambda t, p, s: (t['set_brief'](kind='walk', goal='Fourier series', research='on'), t['research']('Fourier series'))[1]
    h = say(cl, lr, bid, 'Research Fourier series.')
    assert [f['title'] for f in lr.build(bid).brief['found']] == ['Fourier series', 'What is a Fourier Series?', 'Causes of World War One - BBC']
    assert 'untitled' not in h and '__What' not in h and 'articlesCauses' not in h
    cl.post(f'/build/{bid}/item', data=dict(url='https://ex.org/fourier-series.html', role='extra'))
    monkeypatch.setattr(build_app, 'file_link', lambda l, u, max_pages=None: [AttrDict(doc_id='d1', shelf='store', title='Fourier Series - Math is Fun', url=u)])
    def spy(l, ask, chips, *a, **kw): raise ValueError('stop here')
    monkeypatch.setattr(build_app, 'walk_for_talk', spy)
    agent.script = lambda t, p, s: t['make_walk']()
    h = say(cl, lr, bid, 'make the walk')
    assert lr.build(bid).brief['sources'][0]['name'] == 'Fourier Series - Math is Fun' and 'Fourier Series - Math is Fun' in h

def test_research_comes_before_the_walk(mk, lr, agent, monkeypatch):
    "When the owner asks for research, a make before research changes nothing; after the owner keeps the finds, the walk is made one time, from the filed pages."
    monkeypatch.setattr(build_app, 'web_search', lambda q, n: [dict(href='https://ex.org/a', title='Attention notes', body='')])
    monkeypatch.setattr(build_app, 'file_link', lambda l, u, max_pages=None: [AttrDict(doc_id='d1', shelf='store', title='Attention notes', url=u)])
    made = []
    def spy(l, ask, chips, *a, **kw): made.append(list(chips)); raise ValueError('stop here')
    monkeypatch.setattr(build_app, 'walk_for_talk', spy)
    cl = mk(); bid = new_build(cl)
    agent.script = lambda t, p, s: (t['set_brief'](kind='walk', goal='attention', research='on'), t['make_walk'](), t['research']('attention'))[2]
    h = say(cl, lr, bid, 'Make me a walk on attention. Research extra material.')
    mk_call = next(i for i in fold(lr.build(bid).events) if i.get('name') == 'make_walk')
    assert made == [] and mk_call['result'].startswith('Nothing changed. The owner asked for research') and 'What changed' not in last_turn(h)
    agent.script = lambda t, p, s: t['make_walk']()
    cl.post(f'/build/{bid}/item', data=dict(url='https://ex.org/a', role='extra'))   # each find is decided: the turn with the kept finds starts
    wait_for(lambda: True if made else None, secs=20)
    assert made == [['doc:d1']]
