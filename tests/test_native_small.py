"Small fixes for the native Learn work: labels are no concepts, a hosted app owns its settings, ⌥D types ∂ with no mic, and a search with no match."
import pytest
from starlette.testclient import TestClient
from test_guide_page import page, _chromium   # the page fixture: one headless page of the app

from pathlib import Path
DETOUR = Path(__file__).parent.parent/"abhyasa/blocks/detour/detour.js"
browser = pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")

PASSAGE = """() => {
  document.querySelectorAll('#passage, .rh-needs').forEach(x => x.remove());
  const n = document.createElement('div'); n.className = 'rh-needs'; n.dataset.at = 'j/0'; document.querySelector('main').prepend(n);
  const p = document.createElement('div'); p.id = 'passage';
  p.innerHTML = '<span class="lbl">In the tutor\\'s words</span><p id="body">Gradient descent walks downhill.</p>';
  document.querySelector('main').prepend(p);
}"""
SELECT = """id => { const e = document.querySelector(id), r = document.createRange(); r.selectNodeContents(e);
  getSelection().removeAllRanges(); getSelection().addRange(r); e.dispatchEvent(new MouseEvent('mouseup', {bubbles: true})); }"""

@browser
def test_a_label_is_not_a_concept(page):
    "The label of a passage gives no `Learn it` button; the words of the passage do."
    if not page.evaluate('!!window.abhyasaDetour'): page.add_script_tag(path=str(DETOUR))   # the home page may not load the block
    page.evaluate(PASSAGE)
    page.evaluate(SELECT, '#passage .lbl'); page.wait_for_timeout(100)
    assert page.query_selector('#rh-sel') is None
    page.evaluate(SELECT, '#body'); page.wait_for_selector('#rh-sel')

@browser
def test_option_d_types_when_there_is_no_mic(page):
    "With no mic and no box to dictate into, ⌥D is not stopped; in a box with a mic it is."
    page.evaluate("() => document.querySelectorAll('.mic, #mic, #mic-float').forEach(x => x.remove())")
    key = "() => { const e = new KeyboardEvent('keydown', {altKey: true, code: 'KeyD', bubbles: true, cancelable: true}); document.dispatchEvent(e); return e.defaultPrevented; }"
    assert page.evaluate(key) is False
    page.evaluate("() => { const t = document.createElement('textarea'); t.id = 'answer'; t.dataset.mic = '1'; document.querySelector('main').prepend(t); abhyasaMics(); t.focus(); navigator.mediaDevices.getUserMedia = () => new Promise(() => {}); }")
    assert page.evaluate(key) is True

def test_a_hosted_app_refuses_to_write_its_settings(lr, fake, tmp_path):
    "A host owns the settings: each writing route says so and writes nothing, and the page has no key field. Standalone saves as before."
    from abhyasa.app import mk_app, stop_app
    from abhyasa.blocks.settings.app import OWNED
    own = tmp_path/'host'
    app = mk_app(lr, fake, names=['settings'], hosts=('testserver',), warm_speech=False, config=own)
    try:
        cl = TestClient(app)
        assert 'name="key"' not in cl.get('/settings').text and 'Leela owns this setting' in cl.get('/settings').text
        for url, data in [('/settings/key', dict(key='sk-abcdefgh12345')), ('/settings/value', dict(name='walks.steps', value='9')), ('/settings/look', dict(theme='x', mode='y'))]:
            r = cl.post(url, data=data)
            assert r.status_code == 403 and r.text == OWNED, (url, r.status_code)
        assert not (own/'keys.env').exists() and not (own/'settings.json').exists()
    finally: stop_app(app, 1)

def test_a_standalone_app_saves_its_settings(lr, fake, tmp_path, monkeypatch):
    from abhyasa.app import mk_app, stop_app
    monkeypatch.setenv('ABHYASA_CONFIG', str(tmp_path)); monkeypatch.setenv('RAMABANA_CONFIG', str(tmp_path/'r.toml'))
    app = mk_app(lr, fake, names=['settings'], hosts=('testserver',), warm_speech=False)
    try:
        cl = TestClient(app)
        assert 'name="key"' in cl.get('/settings').text
        assert cl.post('/settings/key', data=dict(key='sk-abcdefgh12345')).status_code == 200
        assert (tmp_path/'keys.env').exists()
    finally: stop_app(app, 1)

def test_a_search_with_no_word_match_says_so(lr, fake):
    "The hybrid search ranks every document for any query: 'In what you learned' keeps only the hits that name a word of the query."
    from abhyasa.app import mk_app, stop_app
    lr.put('Fractions', 'A fraction is a part of a whole.', 'math', order=5)
    lr.put('Diffusion noise', 'The forward process adds noise in small steps.', 'ml', order=6)
    app = mk_app(lr, fake, names=['search', 'concepts'], hosts=('testserver',), warm_speech=False)
    try:
        cl = TestClient(app)
        t = cl.get('/search?q=noise').text
        assert 'Diffusion noise' in t and 'Fractions' not in t
        t = cl.get('/search?q=zebra').text
        assert 'Fractions' not in t and 'Nothing that you learned names' in t
    finally: stop_app(app, 1)
