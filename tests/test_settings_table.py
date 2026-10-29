"The settings table: each group has the values that the code used before, and the engine reads a saved value when it uses it."
import json, os, threading
import pytest
from abhyasa.settings import SETTINGS, GROUPS, FIXED, val, set_val, settings, cfg_dir, rows

@pytest.fixture(autouse=True)
def own_config(monkeypatch, tmp_path):
    "Each test gets its own settings folder, so a saved value does not leak into the next test."
    monkeypatch.setenv('ABHYASA_CONFIG', str(tmp_path))

def dflts(group): return {r.name: r.dflt for r in SETTINGS.values() if r.group == group}

def test_groups_in_order():
    assert list(GROUPS) == ['look', 'learning', 'walks', 'talks', 'checks', 'review', 'links', 'research', 'runner', 'stt', 'models', 'lists', 'prompts']

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

# Talks

def test_talks_defaults():
    assert [r.name for r in rows('talks')] == ['talks.choice', 'talks.ask_min', 'talks.pair_min', 'talks.weak', 'talks.split_lo', 'talks.split_hi',
                                               'talks.laser_ms', 'talks.image_mb', 'talks.port', 'talks.room_hours', 'talks.phones', 'talks.nets']
    assert (val('talks.choice'), val('talks.ask_min'), val('talks.pair_min'), val('talks.port'), val('talks.room_hours'), val('talks.phones')) == (True, 1, 2, 5180, 3, 300)
    assert (val('talks.weak'), val('talks.split_lo'), val('talks.split_hi'), val('talks.image_mb'), val('talks.laser_ms')) == (.7, .3, .7, 5, 1500)
    assert set_val('talks.phones', 900) == 300 and {'bind', 'join_code', 'rate', 'body', 'room_headers'} <= set(FIXED)

# Checks and grading

def test_checks_defaults():
    assert dflts('checks') == {'checks.tries': 3, 'checks.sources': True, 'checks.one_ask': True, 'checks.near': 7, 'checks.goal': 4,
                               'checks.high': 60, 'checks.hints': 2, 'checks.demo_misses': 2, 'checks.retest': 2, 'checks.demo_ladder': True, 'checks.feedback_row': True, 'checks.open_days': 7}

def test_demo_ladder_setting(mk):
    "The demo ladder is an on/off value in Checks and grading, on by default, with a help line on the Settings page."
    r = SETTINGS['checks.demo_ladder']
    assert (r.group, r.kind, r.dflt, r.ui) == ('checks', 'bool', True, True) and r.help.endswith('.')
    t = mk().get('/settings').text
    assert r.label in t and r.help in t
    set_val('checks.demo_ladder', False)
    assert val('checks.demo_ladder') is False

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

def test_runner_values_out_of_range_are_clamped(monkeypatch):
    "A runner value out of range in the file reaches the closed process at the top of its range: 60 s, 10 s a test, 100 MB."
    from abhyasa import check
    (cfg_dir()/'settings.json').write_text(json.dumps(dict(runner=dict(total=999, per_test='99', file_mb=10**6))))
    seen, fed = {}, threading.Event()
    class Stdin:
        def write(self, code): seen.update(code=code.decode()); fed.set()
        def close(self): pass
    def empty():
        r, w = os.pipe(); os.close(w)
        return open(r, 'rb')
    class Popen:
        def __init__(self, cmd, **kw): self.pid, self.returncode, self.stdin, self.stdout, self.stderr = 0, 0, Stdin(), empty(), empty()
        def __enter__(self): return self
        def __exit__(self, *a): self.stdout.close(); self.stderr.close()
        def wait(self, timeout=None): seen.update(timeout=timeout); return 0
    monkeypatch.setattr(check.subprocess, 'Popen', Popen)
    check.run_isolated('assert', 'f', 'def f(): return 1', ['assert f() == 1'])
    assert fed.wait(2) and round(seen['timeout']) == 62 and 'RUN_SECONDS = 60.0' in seen['code'] and 'TEST_SECONDS = 10.0' in seen['code']
    assert 'RLIMIT_CPU, (61, 62)' in seen['code'] and f'({100 * 2**20}, {100 * 2**20})' in seen['code']

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
    assert {k: v for k, v in ms.items() if k.startswith('models.')} == {f'models.{t}': '' for t in ('default', *TASKS, 'plan', 'pick', 'note', 'profile', 'exercise', 'talk')}
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

# Lists

def test_lists_defaults():
    assert dflts('lists') == {'lists.strengths': 10, 'lists.journeys': 3, 'lists.beside': 4, 'lists.weeks': 8, 'lists.search': 12,
                              'lists.elsewhere': 2, 'lists.snippet': 300, 'lists.attempts': 10, 'lists.changes': 40, 'lists.sort_batch': 40}
    assert all(r.more for r in SETTINGS.values() if r.group == 'lists')

def test_journeys_on_today_read_when_used(mk, lr):
    for k in range(4): lr.put_journey(dict(id=f'j{k}', title=f'Journey {k}', goal='g', subject='', steps=[], created=k))
    cl = mk()
    assert 'See all 4 in Learn' in cl.get('/').text
    set_val('lists.journeys', 5)
    assert 'See all 4 in Learn' not in cl.get('/').text

# Prompts

def test_all_prompts_registered(mk):
    from abhyasa.prompts import PROMPTS, set_prompt, prompt
    from abhyasa.tutor import depth_ask
    t = mk().get('/settings').text
    for n in ('primer', 'profile.onboard', 'profile.observe', 'stt', 'exercise', 'demo.order', 'demo.simpler', 'depths', 'tutor', 'hints', 'walk.pick', 'walk.plan'):
        assert n in PROMPTS and f'pr-{n.replace(".", "-")}' in t
    with pytest.raises(ValueError, match='5 lines'): set_prompt('depths', 'one line only')
    with pytest.raises(ValueError, match='6 lines'): set_prompt('hints', 'one\ntwo')
    assert depth_ask(4).startswith('apply it')
    set_prompt('depths', 'see it\nsay it\nwhy it\nuse it\nmove it')
    assert depth_ask(4) == 'use it'

def test_simpler_demo_prompt_is_editable(mk, lr):
    "The prompt for a simpler demo is on the Settings page. A saved text goes into the next simpler demo that the tutor makes."
    from abhyasa.prompts import prompt
    from abhyasa.demo import make_demo, SIMPLER_AIM
    from abhyasa.llm import Fake
    from rupaka.spec import gallery
    cl = mk()
    assert 'pr-demo-simpler' in cl.get('/settings').text and prompt('demo.simpler') == SIMPLER_AIM
    assert cl.post('/settings/prompt', data=dict(name='demo.simpler', text='Use one slider only.')).status_code == 200
    ask = Fake({'You design one interactive demo': gallery()['reciprocal-rank-fusion']})
    d = make_demo(lr, ask, 'reciprocal-rank-fusion', check=False, aim='simpler')
    assert d.aim == 'simpler' and 'Use one slider only.' in ask.calls[0][0] and SIMPLER_AIM not in ask.calls[0][0]

# The Settings page

def test_page_lists_every_group_in_order(mk):
    import re
    from abhyasa.core import say
    t = mk().get('/settings').text
    ids = re.findall(r'<section id="g-(\w+)"', t)
    assert ids == list(GROUPS)
    for r in SETTINGS.values():
        if not r.ui or r.group == 'models': continue                       # the model rows load after the page
        assert r.help in t.replace('&quot;', '"'), r.name
        if r.kind in ('int', 'float'): assert f'to {say(r, r.hi if not isinstance(r.hi, str) else 20)} · default {say(r, r.dflt)}' in t, r.name
    assert 'More in Walks: passage length, note length, rabbit-hole depth, and 2 more' in t
    assert 'Use the default (' not in t and 'Use the defaults for this group' not in t     # all defaults: the page stays quiet

def test_page_saves_clamps_and_uses_the_default(mk):
    cl = mk()
    r = cl.post('/settings/value', data=dict(name='walks.steps', value='50'))
    assert val('walks.steps') == 30 and 'value="30"' in r.text                             # out of range: the most, and the box shows it
    t = cl.post('/settings/value', data=dict(name='walks.steps', value='8')).text
    assert val('walks.steps') == 8 and 'Saved' in t and 'Use the default (12)' in t and 'Walks<span class="n"> · 1' in t
    assert 'Use the default for 1 value in Walks?' in cl.get('/settings/group/ask', params=dict(group='walks')).text
    t = cl.post('/settings/default', data=dict(name='walks.steps')).text
    assert val('walks.steps') == 12 and 'Use the default (' not in t
    cl.post('/settings/value', data=dict(name='walks.hands', value='50'))                    # a share comes as a percent
    cl.post('/settings/value', data=dict(name='checks.one_ask', value='0'))
    assert (val('walks.hands'), val('checks.one_ask')) == (.5, False)
    cl.post('/settings/group/default', data=dict(group='walks'))
    assert val('walks.hands') == 1/3 and val('checks.one_ask') is False                     # only the walks went back
    assert cl.post('/settings/value', data=dict(name='mine.x', value='1')).status_code == 400

def test_page_says_when_the_file_had_a_value_out_of_range(mk):
    (cfg_dir()/'settings.json').write_text(json.dumps(dict(walks=dict(steps=50))))
    assert 'Your file had 50. The most is 30, so abhyasa uses 30.' in mk().get('/settings').text

# Learning: stored once, in the profile, and edited on both pages

def test_learning_defaults_and_choices():
    from abhyasa.profile import PROFILE, PACES
    from abhyasa.method import EXPLORE
    assert dflts('learning') == {'learning.pace': 'steady', 'learning.session_len': 12, 'learning.explore': 'sometimes'}
    assert (PROFILE['pace'], PROFILE['session_len'], PROFILE['explore']) == ('steady', 12, 'sometimes')
    assert tuple(PACES) == SETTINGS['learning.pace'].choices and tuple(EXPLORE) == SETTINGS['learning.explore'].choices
    assert SETTINGS['learning.session_len'].lo == 3 and SETTINGS['learning.session_len'].hi == 40

def test_learning_on_both_pages(mk, lr):
    cl = mk()
    cl.post('/settings/value', data=dict(name='learning.pace', value='gentle'))
    cl.post('/settings/value', data=dict(name='learning.session_len', value='99'))
    p = lr.profile()
    assert (p.pace, p.session_len) == ('gentle', 40)
    t = cl.get('/you').text
    assert 'value="gentle" checked' in t and 'value="40"' in t and 'Use the default (12)' in t
    cl.post('/you/setting', data=dict(name='learning.explore', value='often'))
    cl.post('/you/setting/default', data=dict(name='learning.pace'))
    assert (lr.profile().explore, lr.profile().pace) == ('often', 'steady')
    t = cl.get('/settings').text
    assert 'value="often" checked' in t and 'Learning<span class="n"> · 2' in t
    cl.post('/you', data=dict(background='writes code'))                                     # the main form does not touch them
    assert (lr.profile().explore, lr.profile().session_len) == ('often', 40)

def test_saves_from_many_threads():
    "The web app saves from many threads at once. No save fails, and no change is lost."
    from concurrent.futures import ThreadPoolExecutor
    names = [r.name for r in SETTINGS.values() if r.kind == 'int' and r.store == 'file' and r.lo <= 3 <= (r.hi if not isinstance(r.hi, str) else 3)]
    with ThreadPoolExecutor(8) as ex: list(ex.map(lambda n: set_val(n, 3), names))
    assert all(val(n) == 3 for n in names)

# Research

def test_research_defaults():
    assert dflts('research') == {'research.on': True, 'research.per_walk': 12, 'research.results': 5, 'research.wait': 90, 'research.told': False}
    assert set_val('research.per_walk', 99) == 30 and set_val('research.results', 1) == 3
