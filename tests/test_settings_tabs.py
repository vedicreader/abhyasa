"The tabs of the Settings page: each tab holds its groups, ?tab= and an old link such as #g-voice pick the tab, and the keys move along the row."
import re, socket, threading, time
from pathlib import Path
import pytest
from abhyasa import llm
from abhyasa.settings import GROUPS, SETTINGS
from abhyasa.core import help_parts, row_id
from abhyasa.blocks.settings.ui import TABS, TAB_OF, DFLT_TAB, tab_ids
from test_board_js import _chromium

ROOT = Path(__file__).parents[1]/'abhyasa'

@pytest.fixture(autouse=True)
def own_config(monkeypatch, tmp_path):
    "Each test gets its own settings folder, and a short model list with no network."
    monkeypatch.setenv('ABHYASA_CONFIG', str(tmp_path))
    monkeypatch.setattr(llm, 'catalog', lambda ttl=300.: [dict(value='claude/sonnet', name='Claude Sonnet', provider='claude'),
                                                         dict(value='codex/gpt-6-astra', name='GPT-6 Astra', provider='codex')])

def panel(t, h):
    "The HTML of the panel of tab `t`, from its start to the start of the next panel."
    m = re.search(rf'<div role="tabpanel"[^>]*id="t-{t}"[^>]*>(.*?)(?=<div role="tabpanel"|$)', h, re.S)
    return m.group(0) if m else ''

def hidden(t, h): return ' hidden ' in panel(t, h).split('>', 1)[0]

def tab_words(h): return [re.sub(r'<[^>]+>', '', a).strip() for a in re.findall(r'<a [^>]*role="tab"[^>]*>(.*?)</a>', h, re.S)]

def test_each_group_is_in_one_tab():
    "There are 7 tabs or fewer, and each group of the settings is in one tab, one time."
    assert len(TABS) <= 7 and sorted(TAB_OF) == sorted(GROUPS)
    assert sum(len(gs) for _, gs in TABS.values()) == len(GROUPS)

def test_the_tab_row_and_the_first_tab(mk):
    "The page has the row of tabs. Only the first tab shows, and it is the selected tab."
    h = mk().get('/settings').text
    assert tab_words(h) == [l for l, _ in TABS.values()] == ['Models', 'Voice', 'Screen guide', 'Learning', 'Walks and talks', 'Sources', 'Look']
    assert re.search(rf'<a href="\?tab={DFLT_TAB}" role="tab"[^>]*aria-selected="true"', h) and h.count('aria-selected="true"') == 1
    for t, (_, gs) in TABS.items():
        p = panel(t, h)
        assert re.findall(r'<section id="g-(\w+)"', p) == list(gs), t                      # each tab has its groups, in order
        assert hidden(t, h) == (t != DFLT_TAB), t                       # only the first tab shows

def test_each_tab_has_its_rows(mk):
    "Each row of the settings is in the panel of the tab of its group. The model rows load after the page, in Models."
    h = mk().get('/settings').text
    for r in SETTINGS.values():
        if r.ui and r.group != 'models': assert f'id="{row_id(r)}"' in panel(TAB_OF[r.group], h), r.name
    assert 'hx-get="/settings/catalog"' in panel('models', h)

def test_a_query_names_the_tab(mk):
    "?tab=voice draws the Voice tab first, so a reload keeps the tab. An unknown tab gives the first tab."
    cl = mk()
    h = cl.get('/settings?tab=voice').text
    assert re.search(r'<a href="\?tab=voice" role="tab"[^>]*aria-selected="true"', h)
    assert not hidden('voice', h) and hidden('models', h)
    assert re.search(rf'<a href="\?tab={DFLT_TAB}" role="tab"[^>]*aria-selected="true"', cl.get('/settings?tab=nope').text)

def test_old_links_map_to_their_tab():
    "An old link names a group or a row: the map gives its tab. Each /settings#… link in the app is in the map."
    ids = tab_ids()
    assert (ids['g-voice'], ids['g-walks'], ids['g-research'], ids['g-lists']) == ('voice', 'walks', 'sources', 'look')
    assert (ids['sr-walks-hands'], ids['sr-sources-roots'], ids['sr-models-guide'], ids['sr-guide-voice']) == ('walks', 'sources', 'models', 'guide')
    code = '\n'.join(p.read_text() for p in [*ROOT.glob('blocks/*/*.py'), *ROOT.glob('blocks/*/*.js'), *ROOT.glob('core/*.py'), *ROOT.glob('core/*.js')])
    links = set(re.findall(r"/settings#([\w-]+)", code))
    assert links >= {'g-voice', 'g-walks', 'g-research'} and all(l in ids for l in links), links

def test_a_change_counts_on_its_tab(mk):
    "A changed value gives its tab a dot and a count, and the reply changes the count in place."
    cl = mk()
    t = cl.post('/settings/value', data=dict(name='research.per_walk', value='4')).text
    assert '<span hx-swap-oob="true" id="ixn-sources"><span class="n"> · 1</span><span class="dot on"></span></span>' in t
    assert 'Sources<span id="ixn-sources"><span class="n"> · 1' in cl.get('/settings').text

def test_one_help_line_and_about_this(mk):
    "A row shows one help line. The other sentences are under a closed `About this`. A row with one sentence has no `About this`."
    assert help_parts('How big each step is. Gentle uses small steps.') == ('How big each step is.', 'Gentle uses small steps.')
    assert help_parts('The most tokens in one reply.') == ('The most tokens in one reply.', '')
    assert help_parts('Gives a passage. abhyasa checks it.') == ('Gives a passage.', 'abhyasa checks it.')
    h = mk().get('/settings').text
    row = re.search(r'<li[^>]*id="sr-learning-pace".*?</li>', h, re.S).group(0)
    assert '<p class="help">How big each step is.</p>' in row and re.search(r'<details class="about">\s*<summary>About this</summary>', row)
    row = re.search(r'<li[^>]*id="sr-walks-chain".*?</li>', h, re.S).group(0)
    assert 'About this' not in row

def test_review_words_on_the_page(mk):
    "The page uses the words of the design review: on this Mac, hosted, walk, side walk, idea, your vault."
    h = re.sub(r'(?is)<(script|style|textarea)\b.*?</\1>', ' ', mk().get('/settings').text)
    t = re.sub(r'(?s)<[^>]*>', ' ', h)
    for w in ('Rabbit-hole', 'rabbit-hole', 'Steps to research', 'off this machine', 'cloud'): assert w not in t, w
    assert 'Side walk depth' in t and 'Ideas to research in a walk' in t and 'on this Mac' in t

# --- in a headless browser ---------------------------------------------------------------------------------------------

@pytest.fixture
def site(mk):
    "One headless page and the base URL of the app. Playwright's bundled Chromium, one browser, closed at the end."
    import uvicorn
    from playwright.sync_api import sync_playwright
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(mk().app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try: yield b.new_page(viewport=dict(width=1200, height=800)), f'http://127.0.0.1:{port}'
            finally: b.close()
    finally:
        srv.should_exit = True; th.join(5)

SHOWN = "[...document.querySelectorAll('.stab')].filter(p => p.checkVisibility()).map(p => p.dataset.tab)"
SELECTED = "[...document.querySelectorAll('[role=tab][aria-selected=true]')].map(a => a.dataset.tab)"
IN_VIEW = "id => { const r = document.getElementById(id).getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight && r.height > 0; }"
ROW_BOX = "() => { const r = document.querySelector('.stop').getBoundingClientRect(); return [r.top, r.height]; }"

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_tabs_in_a_browser(site):
    "A click and the keys switch the tab, the URL keeps it, the tab row does not move, and the page takes no focus on load."
    pg, url = site
    pg.goto(f'{url}/settings'); pg.wait_for_selector('#sr-models-default select')
    assert pg.evaluate(SHOWN) == ['models'] and pg.evaluate('document.activeElement === document.body')
    xs = pg.evaluate("[...document.querySelectorAll('#models li.srow.model select')].filter(s => s.checkVisibility()).map(s => Math.round(s.getBoundingClientRect().left))")
    assert len(xs) >= 5 and max(xs) - min(xs) <= 1, xs                                          # the Default list starts where the others start
    box = pg.evaluate(ROW_BOX)
    pg.click('#ix-voice')
    assert pg.evaluate(SHOWN) == ['voice'] and pg.evaluate(SELECTED) == ['voice'] and pg.url.endswith('/settings?tab=voice')
    assert pg.evaluate(ROW_BOX) == box                                                         # no layout jump
    pg.keyboard.press('ArrowRight')
    assert pg.evaluate(SHOWN) == ['guide'] and pg.evaluate("document.activeElement.id") == 'ix-guide'
    pg.keyboard.press('End'); assert pg.evaluate(SHOWN) == ['look']
    pg.keyboard.press('ArrowRight'); assert pg.evaluate(SHOWN) == ['models']                   # it goes round
    pg.keyboard.press('ArrowLeft'); assert pg.evaluate(SHOWN) == ['look']
    pg.keyboard.press('Home'); assert pg.evaluate(SHOWN) == ['models']
    pg.keyboard.press('Alt+Digit4')
    assert pg.evaluate(SHOWN) == ['learning'] and pg.url.endswith('?tab=learning')
    pg.reload(); pg.wait_for_selector('#t-learning')
    assert pg.evaluate(SHOWN) == ['learning'] and pg.evaluate(SELECTED) == ['learning']
    pg.fill('#sfind', 'side walk depth')                                                        # Find looks in all the tabs
    assert pg.evaluate(IN_VIEW, 'sr-walks-depth') or pg.evaluate("document.getElementById('sr-walks-depth').checkVisibility()")
    assert not pg.evaluate("document.getElementById('sr-checks-tries').checkVisibility()")

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_old_links_in_a_browser(site):
    "/settings#g-voice opens the Voice tab with the group in view. A link to a row under More opens its tab and its More. No focus moves."
    pg, url = site
    pg.goto(f'{url}/settings#g-voice'); pg.wait_for_function("!document.documentElement.dataset.stab")
    assert pg.evaluate(SHOWN) == ['voice'] and pg.evaluate(SELECTED) == ['voice'] and pg.evaluate(IN_VIEW, 'g-voice')
    assert pg.evaluate('document.activeElement === document.body')
    pg.goto(f'{url}/settings#sr-walks-depth'); pg.wait_for_function("!document.documentElement.dataset.stab")
    assert pg.evaluate(SHOWN) == ['walks'] and pg.evaluate(IN_VIEW, 'sr-walks-depth')
    assert pg.evaluate("document.getElementById('sr-walks-depth').closest('details.more').open")
    pg.goto(f'{url}/settings#g-research'); pg.wait_for_function("!document.documentElement.dataset.stab")
    assert pg.evaluate(SHOWN) == ['sources']
