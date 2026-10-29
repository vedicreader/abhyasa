import os, tempfile
os.environ['VISHALAKSHI_VAULT'] = os.environ['ABHYASA_VAULT'] = os.path.join(tempfile.mkdtemp(), 'vault.db')   # never the real vault
os.environ['ABHYASA_CONFIG'] = tempfile.mkdtemp()   # nor the real settings and keys
os.environ['RAMABANA_CONFIG'] = os.path.join(tempfile.mkdtemp(), 'config.toml')   # nor the real ramabana config
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

def demo_rule(p, sp):
    "The gallery demo, with an id from the concept in the prompt, so each concept gets its own spec."
    import re
    from abhyasa.store import slugify
    return {**gallery()['reciprocal-rank-fusion'], 'id': slugify(re.search(r'^Concept: (.+?) \(subject', p, re.M).group(1))}

@pytest.fixture
def fake():
    return Fake({'You grade one answer': grader, 'Give hint level': 'Think about positions.',
                 'Teach the smallest step': 'Positions are shared. Check: what if k = 0?',
                 'Return JSON: {"concepts"': dict(concepts=[dict(name='Rank', statement='A position in a list.', aliases=[], prereqs=[])]),
                 'You design one interactive demo': demo_rule},
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

@pytest.fixture
def walk_fake(fake, monkeypatch):
    "The `fake` that `mk` uses, with the replies for a walk: the extract of the paper, the tutor note, and the code exercise. No demo check starts a browser."
    monkeypatch.setattr('rupaka.check.can_check', lambda: False)
    from walk_data import EXTRACT_REPLY, EXERCISE
    fake.rules.update({'Return JSON: {"concepts"': EXTRACT_REPLY, 'You write a short note': 'Softmax makes weights from scores. Look at what a large score does.',
                       'You write one small Python exercise': EXERCISE})
    return fake

@pytest.fixture
def talk_fake(walk_fake):
    "The walk `fake`, with the replies for a talk: a choice question from each short check."
    from talk_data import TALK_RULES
    walk_fake.rules.update(TALK_RULES)
    return walk_fake

@pytest.fixture(autouse=True)
def no_leela(monkeypatch, tmp_path_factory):
    "No test reads the owner's real Leela address file."
    from abhyasa.core.cfg import cfg
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path_factory.mktemp('xdg'))); monkeypatch.setitem(cfg, 'leela', '')

@pytest.fixture(autouse=True)
def no_web(monkeypatch):
    "No test searches the web or fetches a page: the default search finds nothing, and the default fetch fails. A test passes its own fakes."
    import abhyasa.research
    def fetch(url): raise AssertionError(f'a test tried to fetch {url}')
    monkeypatch.setattr(abhyasa.research, 'web_search', lambda q, n: [])
    monkeypatch.setattr(abhyasa.research, 'web_fetch', fetch)
