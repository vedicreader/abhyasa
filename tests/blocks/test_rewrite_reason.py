"A rewrite of a slide that shows only a passage, the reason of a failed rewrite in the editor and in the builder, two slides with one passage, and no blind retry."
from talk_data import *
import logging, pytest
from copy import deepcopy
import abhyasa.blocks.build.app as build_app
from abhyasa.blocks.build.events import fold
from fastcore.nbio import new_nb, mk_cell, write_nb
from abhyasa.path import file_chip
from test_build import FakeAgent, agent, home, new_build, say, make_talk_script, POLL

def paper_talk(cl, lr): return make_talk(cl, prep_walk(lr, walk(cl, lr)))

def only_passage(lr, tid, k=0):
    "Slide `k` of talk `tid` shows only its passage: no points, as a slide made from a notebook section."
    t = lr.talk(tid); ss = deepcopy(list(t.slides))
    ss[k] = {**ss[k], 'show': {**ss[k]['show'], 'body': []}, 'beats': ['passage']}
    lr.put_talk({**t, 'slides': ss})
    return ss[k]

def test_a_slide_with_only_a_passage_can_be_rewritten(mk, lr, talk_fake):
    "The owner's case: the slide has no points, and the model keeps the points empty. The note changes; before, each try failed."
    talk_fake.rules['Rewrite these fields'] = dict(body=[], notes='The notebook shows this in its first part.')
    cl = mk(); tid = paper_talk(cl, lr); s = only_passage(lr, tid)
    assert s['show']['passage']
    r = cl.post(f'/t/{tid}/slide', data=dict(sid=s['id'], act='rewrite', text='introduce the notebook'))
    n = lr.talk(tid).slides[0]
    assert r.status_code == 200 and n['notes'] == 'The notebook shows this in its first part.' and n['show']['body'] == [] and n['show']['passage'] == s['show']['passage']

def test_a_failed_model_says_why_and_logs_the_traceback(mk, lr, talk_fake, caplog):
    "A model that raises gives a short reason, never the words of the library; the server log has the whole traceback."
    def boom(p, sp): raise RuntimeError('socket closed by peer 0x1f')
    talk_fake.rules['Rewrite these fields'] = boom
    cl = mk(); tid = paper_talk(cl, lr); before = lr.talk(tid).slides
    with caplog.at_level(logging.WARNING):
        r = cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='rewrite', text='simpler'))
    assert r.status_code == 400 and r.text == 'The tutor could not rewrite slide 2: the model did not answer. Nothing changed.'
    assert 'socket' not in r.text and lr.talk(tid).slides == before
    rec = next(x for x in caplog.records if 'could not rewrite slide 2' in x.getMessage())
    assert rec.exc_info and 'socket closed by peer' in caplog.text and 'Traceback' in caplog.text

def test_a_failed_check_says_its_words(mk, lr, talk_fake):
    "A rewrite that the slide check refuses gives the words of the check."
    talk_fake.rules['Rewrite these fields'] = dict(body=['x' * 5000], notes='N.')
    cl = mk(); tid = paper_talk(cl, lr)
    r = cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='rewrite', text='longer'))
    assert r.status_code == 400 and r.text.startswith('The tutor could not rewrite slide 1: write at most') and 'characters' in r.text

def test_two_slides_with_one_passage_get_two_passages(mk, lr, talk_fake):
    "Slides 1 and 2 show the same passage. A rewrite of slide 2 gives it another passage of its idea from the walk's source, and the source goes to the model."
    talk_fake.rules['Rewrite these fields'] = dict(body=[], notes='Different now.')
    cl = mk(); tid = paper_talk(cl, lr); t = lr.talk(tid); ss = deepcopy(list(t.slides))
    ss[1] = {**ss[1], 'show': {**ss[1]['show'], 'passage': ss[0]['show']['passage'], 'src': ss[0]['show'].get('src'), 'body': []}, 'beats': ['passage']}
    lr.put_talk({**t, 'slides': ss})
    r = cl.post(f'/t/{tid}/slide', data=dict(sid=ss[1]['id'], act='rewrite', text='slide 1 and slide 2 are the same'))
    a, b = lr.talk(tid).slides[:2]
    assert r.status_code == 200 and b['show']['passage'] and b['show']['passage'] != a['show']['passage'] and 'another passage' in r.text
    p = next(c[0] for c in reversed(talk_fake.calls) if c[0].startswith('Rewrite these fields'))
    assert b['show']['passage'][:60] in p.replace('\n', ' ') or b['show']['passage'][:60] in p

def test_the_reason_reaches_the_builder_and_it_does_not_retry_blindly(mk, lr, talk_fake, agent, home):
    "change_talk and edit_slide give the agent the reason. A third identical call that failed two times does not run again."
    talk_fake.rules['You write one poll'] = POLL
    cl = mk(); bid = new_build(cl); nb = home/'talks'/'agents.ipynb'
    agent.script = make_talk_script(nb); say(cl, lr, bid, f'Make a talk from {nb}.')
    calls = []
    def boom(p, sp): calls.append(p); raise RuntimeError('no route')
    talk_fake.rules['Rewrite these fields'] = boom
    out = []
    def tries(t, p, stop):
        out.extend(t['change_talk']('Make it different', slides='3') for _ in range(4))
        out.append(t['edit_slide'](3, points='x' * 5000))
        return 'Done.'
    agent.script = tries
    say(cl, lr, bid, 'slide 3 repeats slide 2')
    assert out[0] == 'It did not work: The tutor could not rewrite slide 3: the model did not answer. Nothing changed.' and out[1] == out[0]
    assert 'two times with the same arguments' in out[2] and 'the model did not answer' in out[2] and out[3] == out[2]
    assert len([c for c in calls]) == 2   # the third and the fourth call did not run the model
    assert out[4].startswith('It did not work: Write at most') and 'characters' in out[4]

def test_the_builder_passages_search_the_files_of_the_brief(mk, lr, talk_fake, agent, home):
    "passages reads the documents of the brief, so a notebook that is one of many on its shelf still gives its passage."
    talk_fake.rules['You write one poll'] = POLL
    cl = mk(); bid = new_build(cl); nb = home/'talks'/'agents.ipynb'
    agent.script = make_talk_script(nb); say(cl, lr, bid, f'Make a talk from {nb}.')
    for k in range(12):   # other notebooks on the same shelf that name the loop more often: a search of the whole vault gives only these
        p = home/'talks'/f'loop{k}.ipynb'
        write_nb(new_nb([mk_cell(f'# Loop note {k}', 'markdown'), mk_cell(f'The agent loop. The agent loop runs. The agent loop, note {k}: the agent loop again and the agent loop once more.', 'markdown')]), p)
        file_chip(lr, f'file:{p}')
    got = []
    agent.script = lambda t, p, s: got.append(t['passages']('the agent loop')) or 'Done.'
    say(cl, lr, bid, 'what does it say about the loop?')
    assert got[0].startswith('[main] agents.ipynb') and 'runs in a loop' in got[0]
