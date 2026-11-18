"A demo step gets a notebook spec with a checked Rupaka demo for Leela, and abhyasa's own demo check stays as it is. Fixed data, no network."
from walk_data import *
from flows import change
from abhyasa.contract import NB_SPEC_CASES
from abhyasa.core import run as run_hook
from abhyasa.path import missing_data

GOOD = NB_SPEC_CASES[0][0]
NB_RULE = 'Write one exercise and one real run'
PROPOSE = 'You propose changes to one learning walk'
DESIGN = 'You design one interactive demo'
NB_KINDS = ('notebook', 'demo')   # the check kinds that get a notebook spec in the background


def kinds(lr, jid): return [s['check']['kind'] for s in lr.journey(jid).steps]
def designs(fake, name): return [p for p, sp in fake.calls if DESIGN in p + sp and f'Concept: {name} (' in p]   # the rule of the demo is in the system prompt


def demo_step(lr, jid, i=2):
    "Make step `i` a demo check, as a plan from a notebook does, and say that the walk is new again: the hook writes the spec of each step that wants one."
    lr.walk_step(jid, i, check=dict(way='demo', kind='demo', depth=3, why=''))
    assert kinds(lr, jid)[i] == 'demo'
    run_hook('walk_made', lr.journey(jid))


def test_a_new_walk_queues_the_spec_of_a_demo_step(mk, lr, walk_fake, monkeypatch):
    "The notebook step and the demo step of a walk get a spec job; the step with a short check does not."
    queued = []; monkeypatch.setattr('abhyasa.path.nb_spec', lambda lr, ask, j, i, stop=None: queued.append(i))
    cl = mk(); jid = walk(cl, lr); wait_for(lambda: True if 1 in queued else None)
    demo_step(lr, jid)
    assert wait_for(lambda: True if 2 in queued else None), queued
    time.sleep(.3)
    assert 0 not in queued and set(queued) == {1, 2}, queued


def test_the_box_queues_the_spec_of_a_step_made_a_demo(mk, lr, walk_fake, monkeypatch):
    "A check that the box makes a demo gets its spec job, as one that it makes a notebook does."
    queued = []; monkeypatch.setattr('abhyasa.path.nb_spec', lambda lr, ask, j, i, stop=None: queued.append(i))
    walk_fake.rules[PROPOSE] = dict(changes=[dict(op='kind', idea='sequential-computation', kind='demo', why='x')])
    cl = mk(); jid = walk(cl, lr)
    change(cl, jid, 'make idea 1 a demo')
    assert lr.journey(jid).steps[0]['check']['kind'] == 'demo'
    assert wait_for(lambda: True if 0 in queued else None), queued


def test_the_spec_of_a_demo_step_has_a_checked_demo(mk, lr, walk_fake):
    "The demo step gets a spec whose demo is a Rupaka demo with a predict gate, also when the idea does not ask for one. The step keeps its demo check."
    from rupaka.spec import validate
    from abhyasa.show import gates_of
    walk_fake.rules[NB_RULE] = GOOD
    cl = mk(); jid = walk(cl, lr); demo_step(lr, jid, 0); s = lr.journey(jid).steps[0]   # idea 1 has no `demo` way and no visual: nothing asks for a demo but its check
    assert 'demo' not in lr.concept(s['slug']).get('ways', []) and not lr.concept(s['slug']).get('visual')
    spec = wait_for(lambda: lr.journey(jid).steps[0].get('nb'), 10)
    assert spec and spec['demo'], spec
    d = lr.demo(spec['demo'])
    assert d.concept == s['slug'] and not list(validate(d.spec)) and gates_of(d.spec)
    assert lr.journey(jid).steps[0]['check']['kind'] == 'demo'
    name = lr.concept(s['slug']).name
    time.sleep(.3)
    mine, total = len(designs(walk_fake, name)), len(walk_fake.calls)
    nbc = sum(NB_RULE in p + sp for p, sp in walk_fake.calls)
    cl.get(f'/w/{jid}/0/check'); time.sleep(.5)   # abhyasa's own check opens: it finds the demo, so it asks nothing more
    print(f'CALLS demo step: design={mine} (after the card {len(designs(walk_fake, name))}) nb-spec prompts={nbc} all={total} (after the card {len(walk_fake.calls)})')
    assert mine == 1 and len(designs(walk_fake, name)) == 1


def test_abhyasa_shows_its_own_demo_check_for_the_demo_step(mk, lr, walk_fake):
    "With a spec on the step, the demo step still shows the demo check: no notebook card, no Open in Leela, no folder to set."
    walk_fake.rules[NB_RULE] = GOOD
    cl = mk(); jid = walk(cl, lr); demo_step(lr, jid, 0)
    assert wait_for(lambda: lr.journey(jid).steps[0].get('nb'), 10)
    card = cl.get(f'/w/{jid}/0/check').text
    assert 'runs in Leela' not in card and 'Open in Leela' not in card and 'Write the notebook' not in card
    j = lr.journey(jid)
    assert j.steps[0]['nb']['data'] == [] and missing_data(j, 0) == []   # a demo step asks for no folder