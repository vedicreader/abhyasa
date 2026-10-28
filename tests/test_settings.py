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
