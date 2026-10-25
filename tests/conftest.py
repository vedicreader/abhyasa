import pytest
from starlette.testclient import TestClient
from abhyasa.store import temp_learning
from abhyasa.llm import Fake
from abhyasa.app import mk_app

def grader(p, sp):
    ans = p.split("Learner's answer:")[1]
    return dict(correct='rank' in ans, grade=8, first_error='You add raw scores.', misconception='scores are comparable', feedback='Look at positions.')

@pytest.fixture
def fake():
    return Fake({'You grade one answer': grader, 'Give hint level': 'Think about positions.',
                 'Teach the smallest step': 'Positions are shared. Check: what if k = 0?',
                 'Return JSON: {"concepts"': dict(concepts=[dict(name='Rank', statement='A position in a list.', aliases=[], prereqs=[])])},
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
    def f(names=None): return TestClient(mk_app(lr, fake, transcribe=lambda a, hint='': f'{len(a)} bytes about {hint}', names=names))
    return f
