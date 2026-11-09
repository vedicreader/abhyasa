"A hosted app: no empty try, no desktop link, and a short box for a missing page."
import pytest
from starlette.testclient import TestClient
from abhyasa.agent_tools import plain
from abhyasa.app import mk_app, stop_app
from test_hosted import HostAsk, HOSTED
from walk_data import walk

@pytest.fixture
def host(lr, walk_fake, tmp_path):
    "A hosted app: it has the folder of its host (`config`)."
    h = HostAsk(walk_fake)
    app = mk_app(lr, h, names=HOSTED, hosts=('testserver',), warm_speech=False, config=tmp_path/'host')
    yield h, app
    stop_app(app, 1)

HX = {'HX-Request': 'true'}

def test_an_empty_answer_is_refused_and_spends_no_try(host, lr, walk_fake):
    h, app = host; cl = TestClient(app)
    jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); cl.get(f'/w/{jid}/0/check')
    for a in ('', '  \n '):
        r = cl.post(f'/w/{jid}/0/answer', data=dict(answer=a))
        assert (r.status_code, r.text) == (400, 'Type an answer first.')
    assert not lr.attempts()
    assert cl.post(f'/w/{jid}/0/answer', data=dict(answer='the rank', confidence=70)).status_code == 200 and lr.attempts()

def test_a_hosted_keys_panel_has_no_desktop_link(host):
    h, app = host; cl = TestClient(app)
    assert 'abhyasa://' not in cl.get('/keys/panel?path=/').text

def test_a_missing_walk_in_a_host_is_a_short_box_not_a_page(host):
    h, app = host; cl = TestClient(app)
    r = cl.get('/w/nope/0', headers=HX)
    assert r.status_code == 200 and 'This walk is not here.' in r.text and 'Go Home' in r.text and 'canonical' not in r.text and '<html' not in r.text
    assert cl.get('/w/nope/0').status_code == 404

def test_a_host_note_block_never_reaches_a_walk_goal():
    assert plain('learn ranking\n<beat>\nabhyasa-index: no callback registered\n</beat>') == 'learn ranking'
    assert plain('learn <BEAT> never closed') == 'learn'

def test_a_user_request_wrapper_never_reaches_a_walk_goal():
    assert plain("<user-request> I don't get this </user-request>") == "I don't get this"
    assert plain('<notebook path="a">cell</notebook>\n\n<user-request>\nteach me fractions\n</user-request>') == 'teach me fractions'
    assert plain("<user-request> I don't get this") == "I don't get this"

def test_a_hosted_page_never_offers_leela_to_a_page_in_leela(tmp_path):
    from fasthtml.common import to_xml
    from abhyasa.blocks.demo.ui import TryLeela
    from abhyasa.core.leela import leela_line
    from abhyasa.learner import use_config
    assert 'Get Leela' in to_xml(TryLeela('')) and 'Get Leela' in to_xml(leela_line(None))
    with use_config(tmp_path): assert (TryLeela(''), TryLeela('http://x/'), leela_line(None)) == ('', '', '')

def test_a_hosted_page_says_learn_where_it_said_abhyasa(host):
    from abhyasa.app import hosted_words
    assert hosted_words('<a href="/abhyasa/x" title="abhyasa">abhyasa files it.</a> <script>abhyasa()</script> abhyasa://x abhyasa-index') == \
        '<a href="/abhyasa/x" title="abhyasa">Learn files it.</a> <script>abhyasa()</script> abhyasa://x abhyasa-index'
    h, app = host; cl = TestClient(app)
    t = cl.get('/you/start').text
    assert 'Tell Learn about you' in t and 'abhyasa about you' not in t
