"The settings table: each group has the values that the code used before, and the engine reads a saved value when it uses it."
import json
import pytest
from abhyasa.settings import SETTINGS, GROUPS, FIXED, val, set_val, settings, cfg_dir

@pytest.fixture(autouse=True)
def own_config(monkeypatch, tmp_path):
    "Each test gets its own settings folder, so a saved value does not leak into the next test."
    monkeypatch.setenv('ABHYASA_CONFIG', str(tmp_path))

def dflts(group): return {r.name: r.dflt for r in SETTINGS.values() if r.group == group}

def test_groups_in_order():
    assert list(GROUPS) == ['look', 'learning', 'walks', 'checks', 'review', 'links', 'runner', 'stt', 'models', 'lists', 'prompts']

def test_bad_values():
    (cfg_dir()/'settings.json').write_text(json.dumps(dict(walks=dict(steps=99, note='long', depth=2.6), checks=dict(one_ask='yes'), mine=dict(a=1))))
    assert (val('walks.steps'), val('walks.note'), val('walks.depth'), val('checks.one_ask')) == (30, 60, 3, True)   # clamped, default, rounded, default
    assert 'mine' not in settings()                                                                                  # an unknown key is ignored
    assert set_val('walks.chain', -3) == 2 and json.loads((cfg_dir()/'settings.json').read_text())['walks']['chain'] == 2

def test_fixed_items_have_no_setting():
    "No setting for the closed code runner, the link checks for local addresses, plain HTTP, link kinds, the HTML allowlist, the pane URL check, local-only hosts, the test allowlist, the grade scale or the depth ladder."
    assert not [n for n in SETTINGS for w in FIXED if w in n]
    labels = ' '.join(f'{r.name} {r.label} {r.help}'.lower() for r in SETTINGS.values())
    for w in ('sandbox', 'audit hook', 'network', 'localhost', 'allowlist', 'grade scale', 'depth ladder', 'python -i'): assert w not in labels

# Walks

def test_walks_defaults():
    from abhyasa import journey
    assert dflts('walks') == {'walks.steps': 12, 'walks.hands': 1/3, 'walks.chain': 4, 'walks.passage': 600, 'walks.note': 60,
                              'walks.depth': 2, 'walks.fresh': 10, 'walks.demo_wait': 90}
    assert [journey.hands_most(n) for n in (2, 3, 12)] == [0, 1, 4]

def test_walk_of_five_steps():
    from abhyasa.store import temp_learning
    from abhyasa.llm import Fake
    from abhyasa.journey import journey_from_text
    text = ' '.join(f'Sentence number {k} of the long text is here.' for k in range(9))
    many = dict(concepts=[dict(name=f'Idea {k}', statement=f'Idea {k} is one idea.', quote=f'Sentence number {k} of the long text', ways=['words']) for k in range(9)])
    ask = Fake({'Return JSON: {"concepts"': many, 'Return JSON: {"pick"': dict(pick=[])})
    assert len(journey_from_text(temp_learning(), ask, text, 'Notes').steps) == 9   # the default is 12, so all 9 ideas
    set_val('walks.steps', 5)
    j = journey_from_text(temp_learning(), ask, text, 'Notes')
    assert len(j.steps) == 5 and len(j.more) == 4

# Checks and grading

def test_checks_defaults():
    assert dflts('checks') == {'checks.tries': 3, 'checks.sources': True, 'checks.one_ask': True, 'checks.near': 7, 'checks.goal': 4,
                               'checks.high': 60, 'checks.hints': 2, 'checks.demo_misses': 2, 'checks.retest': 2}

def test_tries_read_when_used(lr, fake):
    from abhyasa.tutor import Tutor
    t = Tutor(lr, fake, context=False)
    q = t.next()
    assert t.answer(q.id, 'scores').tries_left == 2           # 3 tries by default
    set_val('checks.tries', 1)
    q = t.next()
    assert t.answer(q.id, 'scores').done                      # 1 try: the first miss closes the question

def test_learned_depth_and_sure_confidence():
    from abhyasa.model import learned, outcome
    assert not learned(dict(floor=3)) and outcome(True, 55) == 'fragile'
    set_val('checks.goal', 3); set_val('checks.high', 50)
    assert learned(dict(floor=3)) and outcome(True, 55) == 'solid'

# Review

def test_review_defaults():
    from abhyasa.model import grow
    assert dflts('review') == {'review.solid': 1., 'review.per_day': 0, 'review.shaky': .5, 'review.growth': 3., 'review.fading': .6}
    assert (grow(0, 0, 'solid'), grow(0, 0, 'fragile'), grow(2, .5, 'solid')) == (1., .5, 2 * (1 + 3 * .5 + .2))

def test_review_values_read_when_used():
    from abhyasa.model import grow
    set_val('review.solid', 2); set_val('review.growth', 1)
    assert (grow(0, 0, 'solid'), grow(2, .5, 'solid')) == (2., 2 * (1 + .5 + .2))

def test_most_reviews_a_day(lr, fake):
    import time
    from abhyasa.tutor import Tutor
    lr.update('ranking', seen=1, floor=4, stability=1., last=time.time() - 9 * 86400, due=time.time() - 86400)
    t = Tutor(lr, fake, context=False)
    q = t.next()
    assert q.why.startswith('due for review') and q.meta == dict(review=True)
    t.answer(q.id, 'rank position')                           # a pass closes the review
    lr.update('ranking', due=time.time() - 60)
    set_val('review.per_day', 1)
    assert not t.next().why.startswith('due for review')      # one review a day: the next question is a new idea

# Links

def test_links_defaults():
    from abhyasa.sources import fetch_opts
    assert dflts('links') == {'links.pages': 8, 'links.cap': 20, 'links.timeout': 30, 'links.speed': 1., 'links.kept': 400_000, 'links.read': 100_000}
    assert fetch_opts() == dict(timeout=30, max_recv_speed=1_000_000, retries=1)

def test_link_reads_the_new_page_count():
    from abhyasa.store import temp_learning
    from abhyasa.sources import file_link
    lr, calls = temp_learning(), []
    def read(how, target, **kw):
        calls.append(kw)
        return [lr.vault.add(f'Page {k} has some text on the idea of the folder, enough to read.', f'Page {k}', source=f'https://example.org/docs/p{k}', kind='web') for k in range(9)]
    file_link(lr, 'https://example.org/docs/', read=read, final=lambda u: u)
    set_val('links.pages', 3); set_val('links.timeout', 10)
    assert len(file_link(lr, 'https://example.org/docs/', read=read, final=lambda u: u)) == 3
    assert [c['max_pages'] for c in calls] == [8, 3] and calls[1]['timeout'] == 10

# Code runner

def test_runner_defaults():
    from abhyasa import check
    assert dflts('runner') == {'runner.total': 10, 'runner.per_test': 2, 'runner.file_mb': 10}
    assert (check.TEST_SECONDS, check.RUN_SECONDS) == (2., 10.)
    assert 'RLIMIT_CPU, (11, 12)' in check._limits(10.) and f'({10 * 2**20}, {10 * 2**20})' in check._limits(10.)

def test_run_reads_the_new_limits():
    from abhyasa.check import run_isolated, snippet, _limits
    slow = 'def f():\n    import time\n    time.sleep(1.2)\n    return 1'
    assert run_isolated('assert', 'f', slow, ['assert f() == 1'])['checks'][0]['status'] == 'pass'   # 2 s for each test
    set_val('runner.per_test', 1); set_val('runner.total', 5); set_val('runner.file_mb', 1)
    assert run_isolated('assert', 'f', slow, ['assert f() == 1'])['checks'][0]['status'] != 'pass'   # 1 s: the test stops
    assert "RUN_SECONDS = 5.0" in snippet('assert', 'f', []) and 'RLIMIT_CPU, (6, 7)' in _limits(5.) and f'({2**20}, {2**20})' in _limits(5.)

# Speech to text

def test_stt_defaults():
    assert dflts('stt') == {'stt.engine': 'gemma', 'stt.model': '', 'stt.segment': True, 'stt.pause': 700, 'stt.longest': 12}

def test_mic_gets_the_pause_values(mk):
    cl = mk()
    assert {k: v for k, v in cl.post('/voice/start').json().items() if k in ('segment', 'pause', 'longest')} == dict(segment=True, pause=700, longest=12)
    set_val('stt.pause', 1200); set_val('stt.longest', 40)
    r = cl.post('/voice/start').json()
    assert (r['pause'], r['longest']) == (1200, 30)
    from pathlib import Path
    import abhyasa.blocks.voice as v
    js = (Path(v.__file__).parent/'vad.js').read_text()
    assert 'op.pause' in js and 'op.longest' in js and 'HANG = 35' not in js

# Models

def test_models_defaults():
    from abhyasa.llm import TOKENS, TASKS
    ms = dflts('models')
    assert {k: v for k, v in ms.items() if k.startswith('models.')} == {f'models.{t}': '' for t in ('default', *TASKS, 'plan', 'pick', 'note', 'profile', 'exercise')}
    assert {k[7:]: v for k, v in ms.items() if k.startswith('tokens.')} == TOKENS == dict(question=4096, grade=2048, hint=512, lesson=2048, extract=4096)
    assert 'extract' in settings()['models']

def test_default_model_and_own_rows(monkeypatch):
    from abhyasa.llm import dflt_model, RouteAsk, Router, Fake
    monkeypatch.delenv('ABHYASA_MODEL', raising=False)
    ra = RouteAsk()
    assert dflt_model() == ra.model == 'claude/sonnet'
    set_val('models.default', 'claude/haiku')
    assert ra.model == 'claude/haiku' and dflt_model('claude/opus') == 'claude/opus'      # --model still wins
    monkeypatch.setenv('ABHYASA_MODEL', 'env/model'); assert ra.model == 'env/model'       # and so does the environment
    r = Router(Fake())
    set_val('models.extract', 'x/extract')
    assert r.name('plan') == 'x/extract'                                                   # plan borrows the model of extract
    set_val('models.plan', 'x/plan')
    assert r.name('plan') == 'x/plan'
