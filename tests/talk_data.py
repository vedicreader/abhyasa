"The shared data for the talk tests: the walk of `walk_data.py`, prepared with two short checks, a note and a demo check."
from walk_data import *
from abhyasa.journey import journey_from_source
from abhyasa.llm import Fake
from rupaka.spec import gallery

CHOICE = dict(q='What does softmax give for a list of scores?',
              options=['Weights above 0 that add to 1', 'The largest score only', 'The scores in order', 'Scores that are all above 1'], answer=0)
TALK_RULES = {'Return JSON: {"concepts"': EXTRACT_REPLY, 'You turn one check into a choice question': CHOICE}
PNG = b'\x89PNG\r\n\x1a\n'

def prep_walk(lr, jid):
    "Give the walk a short check on ideas 1 and 2, a note on idea 2, and a demo check on idea 3 with the softmax demo."
    lr.walk_step(jid, 0, check=dict(way='words', kind='short', depth=2, why=''))
    lr.walk_step(jid, 1, check=dict(way='maths', kind='short', depth=2, why=''), note='Softmax makes weights from scores.')
    lr.put_demo(gallery()['softmax-temperature'], 'scaling-by-the-root-of-dk')
    lr.walk_step(jid, 2, check=dict(way='demo', kind='demo', depth=2, why=''))
    return jid

def talk_walk(lr):
    "File the paper, make its walk in the engine, and prepare it; return the journey id."
    return prep_walk(lr, journey_from_source(lr, Fake(TALK_RULES), add_paper(lr)).id)

def make_talk(cl, jid):
    "Make a talk from walk `jid` through the app and wait for the job; return the talk id."
    cl.post('/talk/new', data=dict(jid=jid))
    loc = wait_for(lambda: cl.get(f'/talk/job?jid={jid}').headers.get('hx-redirect'))
    return loc.split('/')[-1]

def free_port():
    "A free TCP port on 127.0.0.1."
    import socket
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); return s.getsockname()[1]
