"The block contract: `NAMES` matches the folders, each block declares `CAPS` and `connect`, and every page answers."
from pathlib import Path
import pytest
import abhyasa.blocks as B
from abhyasa.core.block import Ctx, block_caps

def test_names_match_folders():
    dirs = {p.name for p in Path(B.__file__).parent.iterdir() if p.is_dir() and (p/'__init__.py').exists()}
    assert set(B.NAMES) == dirs

@pytest.mark.parametrize('m', B.blocks(), ids=B.NAMES)
def test_block_shape(m):
    assert callable(m.connect)
    block_caps(m)

def test_undeclared_capability_is_named():
    c = Ctx('graph', ('learning',), learning=1, tutor=2)
    assert c.learning == 1
    with pytest.raises(AttributeError, match="'graph' used capability 'tutor'"): c.tutor

def test_every_get_page_answers(mk):
    cl = mk()
    for path in ('/', '/concepts', '/c/ranking', '/graph', '/graph.json', '/search?q=rank', '/add', '/health'):
        r = cl.get(path)
        assert r.status_code == 200, path

def test_nav_from_blocks(mk):
    page = mk().get('/').text
    assert page.index('>Today<') < page.index('>Graph<') < page.index('>Concepts<') < page.index('>Add<')

def test_assets_served_with_hash(mk):
    cl = mk()
    page = cl.get('/graph').text
    assert '/assets/graph.js?v=' in page
    r = cl.get('/assets/graph.js')
    assert r.status_code == 200 and 'forceSimulation' in r.text and 'immutable' in r.headers['cache-control']
    assert cl.get('/assets/nope.js').status_code == 404
