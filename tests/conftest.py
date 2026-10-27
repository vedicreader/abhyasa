import os, tempfile
os.environ['VISHALAKSHI_VAULT'] = os.environ['ABHYASA_VAULT'] = os.path.join(tempfile.mkdtemp(), 'vault.db')   # never the real vault
os.environ['ABHYASA_CONFIG'] = tempfile.mkdtemp()   # nor the real settings and keys
for k in ('ABHYASA_STT', 'OPENAI_API_KEY'): os.environ.pop(k, None)
import pytest
from starlette.testclient import TestClient
from abhyasa.store import temp_learning
from abhyasa.llm import Fake
from abhyasa.app import mk_app
from abhyasa.ground import passage
from pathlib import Path
from rupaka.spec import gallery
import abhyasa.voice
abhyasa.voice.RAMABANA_KEYS = Path(tempfile.mkdtemp())/'keys.env'   # never read the real ramabana keys

class Notes:
    "A source with one passage that names Ranking."
    name = 'notes'
    def search(self, q, k=4): return [passage('vault:notes', 'n1', 'My ranking notes', 'Ranking orders items by score.', url='https://example.org/notes')]

def grader(p, sp):
    ans = p.split("Learner's answer:")[1].split("Learner's think-aloud:")[0]
    return dict(correct='rank' in ans, grade=8 if 'rank' in ans else 3, first_error='You add raw scores.', misconception='scores are comparable', feedback='Look at positions.')

@pytest.fixture
def fake():
    return Fake({'You grade one answer': grader, 'Give hint level': 'Think about positions.',
                 'Teach the smallest step': 'Positions are shared. Check: what if k = 0?',
                 'Return JSON: {"concepts"': dict(concepts=[dict(name='Rank', statement='A position in a list.', aliases=[], prereqs=[])]),
                 'You design one interactive demo': gallery()['reciprocal-rank-fusion']},
                dflt=dict(question='What does a rank tell you?', answer='Its position.', rubric=['position']))

@pytest.fixture
def lr():
    l = temp_learning()
    l.put('Ranking', 'Order items by a score.', 'ml', order=0)
    l.put('Reciprocal rank fusion', 'Sum 1/(k + rank) over lists.', 'ml', prereqs=['ranking'], order=1)
    return l

@pytest.fixture
def mk(lr, fake):
    "A client for an app with some blocks, or all of them."
    def f(names=None): return TestClient(mk_app(lr, fake, transcribe=lambda a, hint='': f'{len(a)} bytes about {hint}', names=names, sources=[Notes()], hosts=('testserver', '127.0.0.1', 'localhost')))
    return f
