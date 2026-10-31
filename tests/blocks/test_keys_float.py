"The Keys panel: the keys that it lists on each page, the setting `look.keys_float`, and the pill in a browser."
import socket, threading
import pytest
from walk_data import walk, wait_for
from abhyasa.core.keys import float_rows, page_group, has_float, FLOAT_MAX
from abhyasa.blocks.keys.ui import GUIDE_LINE, TALK_LINE, GUIDE_LINK
from abhyasa.settings import val, reset

def keys_of(path): return [k for _, k, _ in float_rows(path)]

# --- the rows of each page -------------------------------------------------------------------------------------------

def test_each_page_gets_its_group():
    "The path of a page names its group of keys; a page with no keys of its own gets Everywhere."
    want = {'/': 'Everywhere', '/learn': 'Everywhere', '/s/abc': 'Session', '/w/j1/2': 'Walk', '/w/j1': 'Walk', '/w/j1/edit': 'Change the walk',
            '/c/ranking': 'Concept', '/graph': 'Graph', '/settings': 'Settings', '/concepts': 'Concepts', '/t/t1': 'Talk plan'}
    assert {p: page_group(p) for p in want} == want

def test_the_windows_of_a_talk_have_no_panel():
    "The presenter and the audience windows of a talk show on a room screen: they get no Keys panel. The talk editor does."
    assert not has_float('/t/t1/present') and not has_float('/t/t1/audience') and has_float('/t/t1') and has_float('/')

def test_every_page_starts_with_explain_dictate_and_search():
    "The first three rows are the same on each page: the guide, dictation and search. Each key shows once, and a page has at most seven rows."
    for p in ('/', '/s/abc', '/w/j1/2', '/c/ranking', '/graph', '/settings', '/w/j1/edit'):
        ks = keys_of(p)
        assert ks[:3] == ['⌃⌥⇧⌘E', '⌥D', '/'] and len(ks) == len(set(ks)) and 4 <= len(ks) <= FLOAT_MAX, (p, ks)

def test_the_rows_of_a_page_come_from_its_group():
    "A session and a walk step add their own ⌥S, hint and more; Today adds the main button and Continue; the graph adds its own letters."
    rows = {p: [(g, k) for g, k, _ in float_rows(p)] for p in ('/', '/s/abc', '/w/j1/2', '/c/ranking', '/graph')}
    assert rows['/'][3:] == [('Everywhere', '⌥S'), ('Everywhere', '⌥C')]
    assert rows['/s/abc'][3:] == [('Session', '⌥S'), ('Session', '⌥W'), ('Session', '⌥X'), ('Session', '⌥A')]
    assert rows['/w/j1/2'][3:] == [('Walk', '⌥S'), ('Walk', '⌥W'), ('Walk', '⌥B'), ('Everywhere', '⌥C')]
    assert rows['/c/ranking'][3:] == [('Concept', '⌥E'), ('Everywhere', '⌥C')]
    assert ('Graph', 'F') in rows['/graph'] and ('Everywhere', '⌥S') not in rows['/s/abc']

# --- the pill on a page --------------------------------------------------------------------------------------------------

def test_the_pill_is_on_each_page_but_the_side_pane(mk):
    "The page has the pill, the panel closed in the HTML, the two lines about the guide and the speech, and the Mac link hidden until the script finds the app."
    cl = mk()
    t = cl.get('/').text
    assert 'id="kf"' in t and 'id="kf-panel"' in t and GUIDE_LINE in t and TALK_LINE in t and f'href="{GUIDE_LINK}"' in t
    assert 'Explain this' in t and 'data-act="explain"' in t and 'data-act="dictate"' in t and 'data-act="search"' in t and 'All keys' in t
    assert 'id="kf"' not in cl.get('/?pane=1').text
    assert 'Keys: concept' in cl.get('/c/ranking').text and 'Show me a demo' in cl.get('/c/ranking').text

def test_a_walk_check_shows_the_walk_keys_and_a_mic(mk, walk_fake, lr):
    "A walk step lists Ask for a hint and a side walk for a missing idea; its short check has the Speak button with ⌥D, from the voice block."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    t = cl.get(f'/w/{jid}/1').text
    assert 'Keys: walk' in t and 'Ask for a hint' in t and 'Side walk for a missing idea' in t and 'data-code="KeyW"' in t
    card = cl.get(f'/w/{jid}/1/check').text
    assert 'data-into="ans"' in card and '⌥D' in card

def test_the_guide_box_says_how_to_talk(mk):
    "The guide box shows the talk key where the mic shows while you talk."
    assert 'Hold Caps+E to talk' in mk().get('/').text

def test_hide_this_turns_the_setting_off_and_the_keys_page_brings_it_back(mk):
    "Hide this posts on=0: the setting goes off, no page has the pill, and the keys page offers to show it again."
    cl = mk()
    try:
        assert val('look.keys_float') is True
        assert cl.post('/keys/float', data=dict(on='0')).status_code == 204 and val('look.keys_float') is False
        assert 'id="kf"' not in cl.get('/').text and 'Show the Keys button' in cl.get('/keys').text
        cl.post('/keys/float', data=dict(on='1'))
        assert val('look.keys_float') is True and 'id="kf"' in cl.get('/').text and 'Show the Keys button' not in cl.get('/keys').text
    finally: reset('look.keys_float')

# --- in a browser ------------------------------------------------------------------------------------------------------

def _chromium():
    try:
        from pathlib import Path
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p: return Path(p.chromium.executable_path).exists()
    except Exception: return False

COVERS = """sel => { const o = document.querySelector(sel); if (!o) return 'none';
  const vis = el => el && el.checkVisibility({checkVisibilityCSS: true, visibilityProperty: true}), r = o.getBoundingClientRect();
  return ['kf-pill', 'kf-panel'].map(id => document.getElementById(id)).filter(vis).map(e => e.getBoundingClientRect())
    .filter(a => a.left < r.right && a.right > r.left && a.top < r.bottom && a.bottom > r.top).length; }"""

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_the_pill_in_a_browser(mk, walk_fake, lr):
    "Open once with no focus, then closed; click and Esc; Search acts; it never covers Send or the guide box; Hide this lasts after a reload."
    import uvicorn
    from playwright.sync_api import sync_playwright
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    assert wait_for(lambda: srv.started or None, secs=30), 'the server did not start'
    base = f'http://127.0.0.1:{port}'
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page(viewport=dict(width=1280, height=800))
                pg.goto(base + '/'); pg.wait_for_function('window.abhyasaKF && document.getElementById("kf").dataset.ready')
                assert pg.is_visible('#kf-panel')                                                 # a new learner sees it open one time
                assert pg.evaluate('!document.getElementById("kf").contains(document.activeElement)')   # and it takes no focus
                pg.reload(); pg.wait_for_function('document.getElementById("kf").dataset.ready')
                assert not pg.is_visible('#kf-panel')                                             # then it is closed
                pg.click('#kf-pill'); assert pg.is_visible('#kf-panel') and pg.get_attribute('#kf-pill', 'aria-expanded') == 'true'
                pg.keyboard.press('Escape'); assert not pg.is_visible('#kf-panel')                # Esc closes it, and the page stays
                assert pg.url == base + '/'
                pg.click('#kf-pill'); pg.click('#kf-close'); assert not pg.is_visible('#kf-panel')
                pg.keyboard.press('Alt+Shift+F'); assert pg.is_visible('#kf-panel') and pg.url == base + '/'   # ⌥⇧F opens it, and not the keys page
                pg.click('#kf [data-act=search]')                                                 # a row does what its key does
                assert pg.evaluate("document.activeElement.matches('nav input[type=search]')") and not pg.is_visible('#kf-panel')
                for w, h in ((1280, 800), (800, 600)):
                    pg.set_viewport_size(dict(width=w, height=h))
                    pg.goto(f'{base}/w/{jid}/1'); pg.wait_for_selector('#send'); pg.wait_for_function('document.getElementById("kf").dataset.ready')
                    pg.evaluate('document.activeElement.blur()')
                    for opened in (False, True):
                        pg.evaluate(f'abhyasaKF.show({str(opened).lower()}, false)')
                        for at in ('end', 'center', 'start'):
                            pg.evaluate(f"document.querySelector('#send').scrollIntoView({{block: '{at}'}}); abhyasaKF.place()")
                            assert pg.evaluate(COVERS, '#send') == 0, (w, h, opened, at)
                        assert pg.evaluate("document.getElementById('kf-pill').checkVisibility({visibilityProperty: true})")   # Send at the top: the pill shows
                    pg.evaluate('abhyasaKF.show(true, false)'); pg.click('#guide-go'); pg.wait_for_selector('#guide-form:not([hidden])')
                    pg.evaluate('abhyasaKF.place()')
                    assert pg.evaluate(COVERS, '#guide-form') == 0, (w, h, 'guide box')
                assert not pg.is_visible('#kf-mac')                                               # a browser has no guide over other apps
                mac = b.new_page(user_agent=pg.evaluate('navigator.userAgent') + ' Abhyasa/0.0.16')
                try:
                    mac.goto(base + '/'); mac.wait_for_function('document.getElementById("kf").dataset.ready')
                    mac.evaluate('abhyasaKF.show(true, false)')
                    assert mac.is_visible('#kf-mac') and mac.get_attribute('#kf-mac', 'href') == GUIDE_LINK   # Abhyasa.app shows the link
                finally: mac.close()
                pg.goto(base + '/'); pg.wait_for_function('document.getElementById("kf").dataset.ready')
                pg.evaluate('abhyasaKF.show(true, false)'); pg.click('#kf-hide')
                pg.wait_for_function('!document.getElementById("kf")')
                pg.reload(); pg.wait_for_load_state('load')
                assert pg.query_selector('#kf') is None                                           # hidden after a reload too
            finally: b.close()
    finally:
        reset('look.keys_float')
        srv.should_exit = True; th.join(5)

RAIL_TEXT = """() => { const p = document.getElementById('kf-panel');
  if (!p.checkVisibility({checkVisibilityCSS: true, visibilityProperty: true})) return 0;
  const a = p.getBoundingClientRect(), r = document.createRange();
  return [...document.querySelectorAll('#rail summary, #rail li, #rail .rail-acts > *')].filter(e => e.checkVisibility()).filter(e => {
    r.selectNodeContents(e); return [...r.getClientRects()].some(o => o.width && a.left < o.right && a.right > o.left && a.top < o.bottom && a.bottom > o.top); }).length; }"""

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_the_panel_closes_on_the_next_page_keeps_off_the_rail_and_lets_the_guide_card_go_first(mk, walk_fake, lr):
    "The panel that you open does not stay open on the next page; at 1440x900 on a walk step it covers no text of the outline; Esc closes a guide demo card before the panel."
    import json, uvicorn
    from playwright.sync_api import sync_playwright
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    assert wait_for(lambda: srv.started or None, secs=30), 'the server did not start'
    base, ready = f'http://127.0.0.1:{port}', 'window.abhyasaKF && document.getElementById("kf").dataset.ready'
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page(viewport=dict(width=1440, height=900))
                pg.goto(base + '/'); pg.wait_for_function(ready)                              # the first visit: it opens one time
                pg.goto(base + '/learn'); pg.wait_for_function(ready)
                assert not pg.is_visible('#kf-panel')
                pg.click('#kf-pill'); assert pg.is_visible('#kf-panel')                      # you open it on this page
                pg.goto(f'{base}/w/{jid}/1'); pg.wait_for_selector('#rail'); pg.wait_for_function(ready)
                assert not pg.is_visible('#kf-panel')                                         # the next page opens with it closed
                pg.evaluate("const o = document.querySelector('#rail ol'); [...o.children].forEach(li => o.append(li.cloneNode(true), li.cloneNode(true)))")
                assert pg.evaluate("document.getElementById('rail').getBoundingClientRect().bottom") > 500   # a long walk: its outline goes down past the panel
                pg.evaluate('document.activeElement.blur()'); pg.click('#kf-pill'); pg.evaluate('abhyasaKF.place()')
                assert pg.evaluate(RAIL_TEXT) == 0                                            # open on a walk step, it covers no text of the outline
                assert pg.is_visible('#kf-panel') and pg.evaluate("document.getElementById('kf-panel').getBoundingClientRect().width") < 256   # it gets narrow at the left of the outline
                pg.evaluate('abhyasaKF.show(false, true)')
                pg.route('**/guide/ask', lambda r: r.fulfill(status=200, headers={'Content-Type': 'text/event-stream'},
                                                              body=f"data: {json.dumps(dict(show=dict(href='/c/ranking')))}\n\n"))
                pg.evaluate("abhyasaGuideQuiet = true; abhyasaGuide.ask('show me the ranks')"); pg.wait_for_selector('#guide-show')
                pg.click('#kf-pill'); assert pg.is_visible('#kf-panel')
                pg.evaluate('document.activeElement.blur()')
                pg.keyboard.press('Escape')                                                   # the first Esc closes the card, which is on top
                assert pg.evaluate("!document.getElementById('guide-show')") and pg.is_visible('#kf-panel')
                pg.keyboard.press('Escape'); assert not pg.is_visible('#kf-panel')           # the second Esc closes the panel
            finally: b.close()
    finally:
        srv.should_exit = True; th.join(5)

def test_settings_look_has_the_keys_button_switch(mk):
    "Settings, Look shows the switch of the Keys button under the themes, so you can turn it on again there too."
    t = mk().get('/settings?tab=look').text
    sec = t[t.index('id="g-look"'):t.index('id="g-lists"')]
    assert 'Keys button' in sec and 'type="checkbox"' in sec and 'value="sage"' in sec
