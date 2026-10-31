"""The spec test: for each page and state in `tests/data/flows.json`, build the data, GET the page, and check what the spec says it shows,
what it hides, where its links go, that each action goes somewhere, and that it has one main button. Then walk each workflow with real requests."""
import pytest
from flows import SPEC, BUILD, DRIVE, check_spec, page, route_of, two_walks

STATES = [(p, s) for p, v in SPEC['pages'].items() for s in v['states']]

def test_spec_shape():
    "The spec is whole: each page has its path, states, entries and exits, and each workflow step names a page."
    check_spec(SPEC)

@pytest.mark.parametrize('pid,sid', STATES, ids=[f'{p}-{s}' for p, s in STATES])
def test_page_state(pid, sid, mk, lr, walk_fake, monkeypatch):
    "The page `pid` in state `sid` shows what the spec says, hides what it says, links only to its exits, and has one main button."
    v = SPEC['pages'][pid]
    st = v['states'][sid]
    if st.get('pending'): pytest.skip(f"the spec leads: {st.get('pending_why', 'no code yet')}")
    assert (pid, sid) in BUILD, f'{pid}/{sid} has no builder'
    cl = mk()
    url, ctx = BUILD[pid, sid](lr, cl, monkeypatch)
    pg = page(cl, url)
    for x in st['must_show']: assert pg.has(x, ctx), f'{pid}/{sid}: no {x}'
    for x in st['must_not_show']: assert not pg.has(x, ctx), f'{pid}/{sid}: {x} shows'
    ok = {*(x.split()[0] for x in v['exits']), pid}
    for h in pg.links: assert route_of(h) in ok | {None}, f'{pid}/{sid}: a link to {h}'
    for a in pg.acts: assert pg.works(a), f'{pid}/{sid}: {a} goes nowhere'
    if st['actions']:
        assert len(pg.primary) == 1, f'{pid}/{sid}: {len(pg.primary)} main buttons'
        assert pg.primary[0].get('data-act') in [x.split()[0] for a in st['actions'] for x in a.split(' or ')], f"{pid}/{sid}: the main button is {pg.primary[0].get('data-act')}"

@pytest.mark.parametrize('wid', SPEC['workflows'])
def test_workflow(wid, mk, lr, walk_fake, monkeypatch):
    "Each step of workflow `wid` works with real requests, and lands on the next page in the right state."
    w = SPEC['workflows'][wid]
    if w.get('pending'): pytest.skip(f"the spec leads: {w.get('pending_why', 'no code yet')}")
    assert wid in DRIVE, f'{wid} has no driver'
    DRIVE[wid](lr, mk(), monkeypatch, walk_fake)

def test_nav_continue(mk, lr, walk_fake):
    "nav.continue: on the walk of the place the top bar has no Continue; on Home there is none in the bar and the card points at the newest place; elsewhere the bar points at it."
    a, b = two_walks(lr); cl = mk()
    assert 'continue' not in page(cl, f'/w/{b}/1').parts   # B is the place: on B there is no Continue
    home = page(cl, '/')
    assert 'continue' not in home.parts and home.parts.count('continue-card') == 1 and {e.get('href') for e in home.acts['continue']} == {f'/w/{b}/1'}
    assert [e.get('href') for e in page(cl, '/library').acts['continue']] == [f'/w/{b}/1']
    assert 'continue' not in page(cl, f'/w/{a}/0').parts   # you open A: A is the place now
    assert [e.get('href') for e in page(cl, '/library').acts['continue']] == [f'/w/{a}/0']
