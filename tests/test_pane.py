"The side pane: local URLs only, the host markup, a page in a pane, the keys, and the pane in a browser."
from pathlib import Path
import pytest
from fasthtml.common import to_xml
from abhyasa.core.pane import is_local, is_web, pane_url, pane_link, PaneHost
from abhyasa.core.keys import KEYS

HOSTILE = ('https://evil.example/x', '//evil.example', '/\\evil.example', '\\\\evil.example', 'javascript:alert(1)', 'JaVaScRiPt:alert(1)',
           'data:text/html,hi', 'w/g', '', None, 3, '/\t/evil.example', '/\n/evil.example', ' /w/g', '/w/g\x00', '/w\\..\\x')

def test_pane_url_is_local_only():
    assert pane_url('/w/g-1a2b/0') == '/w/g-1a2b/0?pane=1' and pane_url('/w/g?x=1') == '/w/g?x=1&pane=1'
    assert pane_url('/w/g?pane=1') == '/w/g?pane=1' and pane_url('/w/g#check') == '/w/g?pane=1#check'   # one flag, before the fragment
    for bad in HOSTILE: assert not is_local(bad) and pane_url(bad) is None, bad

def test_pane_url_in_talk_type():
    assert pane_url('/w/g-1a2b/0', talk=True) == '/w/g-1a2b/0?pane=1&talk=1' and pane_url('https://evil.example/', talk=True) is None
    assert pane_url('/w/g?talk=0&pane=1', talk=True) == '/w/g?pane=1&talk=1'   # one of each flag

def test_walk_step_in_talk_type_has_no_check(mk, walk_fake, lr):
    from walk_data import walk
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    page = cl.get(f'/w/{jid}/1?pane=1&talk=1').text
    assert 'id="check"' not in page and 'talk-type' in page and 'apply a softmax function' in page
    assert not lr.journey(jid).steps[1].get('qid')
    assert 'id="skip"' not in page and 'Back to the slide' in page   # no skip, so nothing is logged; the way back is ⌥Z
    assert 'id="check"' in cl.get(f'/w/{jid}/1?pane=1').text   # a pane that is not in a talk keeps its check

WEB_BAD = ('javascript:alert(1)', 'JaVaScRiPt:alert(1)', 'data:text/html,hi', 'file:///etc/passwd', 'ftp://example.org/', 'blob:https://x/y',
           '/w/g', '//evil.example', 'https:evil.example', 'http://', ' https://example.org', 'https://exa mple.org', 'https://example.org/\n', '', None, 3)

def test_rh_link_takes_only_http_and_https():
    "A page in the pane asks the host to open a link outside the pane with `rh:link {url}`. Only an http or https URL is a link."
    for good in ('https://example.org/x?y=1#z', 'http://example.org', 'HTTPS://Example.org/a'): assert is_web(good), good
    for bad in WEB_BAD: assert not is_web(bad), bad

def test_pane_link_is_a_real_link():
    h = to_xml(pane_link('Derivatives', '/w/g-1a2b/0', 'Side walk'))
    assert 'href="/w/g-1a2b/0"' in h and 'data-pane="/w/g-1a2b/0?pane=1"' in h and 'target="_blank"' in h and 'data-title="Side walk"' in h
    assert 'data-pane' not in to_xml(pane_link('Out', 'https://evil.example/'))   # a link out of the app is only a link

def test_host_draws_the_pane_or_nothing():
    h = to_xml(PaneHost('/w/g-1a2b/0', 'Derivatives', trail=[('Attention · idea 5', '/w/a/4')]))
    assert 'id="rh-pane"' in h and 'src="/w/g-1a2b/0?pane=1"' in h and 'role="separator"' in h and 'aria-orientation="vertical"' in h
    assert 'Its own session ↗' in h and 'href="/w/g-1a2b/0" target="_blank"' in h and 'Attention · idea 5' in h and '<b>Derivatives</b>' in h
    for bad in HOSTILE: assert PaneHost(bad) == '', bad
    assert 'evil' not in to_xml(PaneHost('/w/g', trail=[('Out', 'https://evil.example/')]))   # a trail part that leaves the app has no link

def test_page_in_a_pane_has_no_nav(mk):
    cl = mk()
    assert '<nav' in cl.get('/').text
    t = cl.get('/?pane=1').text
    assert '<nav' not in t and 'in-pane' in t and 'rh-pane' not in t

def test_page_with_rh_draws_the_pane_open(mk):
    cl = mk()
    t = cl.get('/?rh=/concepts').text
    assert 'src="/concepts?pane=1"' in t and 'class="rh-open"' in t and '<nav' in t
    for bad in ('https://evil.example/', '//evil.example', '/\\evil.example', 'javascript:alert(1)'):
        t = cl.get('/', params=dict(rh=bad)).text
        assert 'rh-pane' not in t and 'rh-open' not in t, bad
    assert 'rh-pane' not in cl.get('/', params=dict(rh='/concepts', pane='1')).text   # no pane in a pane

def test_pane_keys_are_in_the_table():
    assert ('Side pane', '⌥Z', 'Back to the paper: close the side pane') in KEYS
    assert ('Side pane', 'esc', 'Close the side pane') in KEYS

def _chromium():
    "True when Playwright's bundled Chromium is installed."
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p: return Path(p.chromium.executable_path).exists()
    except Exception: return False

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_pane_in_a_browser(mk):
    import socket, threading, time, uvicorn
    from playwright.sync_api import sync_playwright
    cl = mk(); sid = cl.post('/start', follow_redirects=False).headers['location'].split('/')[-1]   # a session page: the composer and the mic
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    base = f'http://127.0.0.1:{port}'
    shown = lambda pg: pg.evaluate("() => { const p = document.getElementById('rh-pane'); return !!p && getComputedStyle(p).display !== 'none' }")
    rh = lambda pg: pg.evaluate("() => new URLSearchParams(location.search).get('rh')")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page(viewport=dict(width=1400, height=900))
                pg.goto(base + '/'); pg.wait_for_load_state()
                pg.evaluate("abhyasaPane.open('/keys', 'Keyboard shortcuts')")
                pg.wait_for_function("() => document.querySelector('#rh-pane iframe').contentDocument?.documentElement?.classList.contains('in-pane')")
                assert rh(pg) == '/keys' and '?rh=/keys' in pg.url and shown(pg)            # the place is in the URL, readable
                fr = pg.frame_locator('#rh-pane iframe')
                assert fr.locator('nav').count() == 0 and fr.locator('h1').count() >= 1    # a page in a pane has no nav
                pg.wait_for_function("() => document.querySelector('#rh-pane .rh-trail b').textContent.includes('Keyboard shortcuts')")   # rh:at came back

                pg.evaluate("window.opened = []; window.open = (...a) => { opened.push(a); return null; }; 0")
                inner = next(f for f in pg.frames if 'pane=1' in f.url)
                for u in ('https://example.org/x', 'javascript:alert(1)', 'data:text/html,hi', 'file:///etc/passwd', '/keys', 'http://example.org/y'):
                    inner.evaluate("u => parent.postMessage({type: 'rh:link', url: u}, location.origin)", u)
                pg.wait_for_function('opened.length >= 2'); time.sleep(.2)
                assert pg.evaluate('opened') == [['https://example.org/x', '_blank', 'noopener'], ['http://example.org/y', '_blank', 'noopener']]   # rh:link: http(s) only, in a new tab

                pg.reload(); pg.wait_for_load_state()
                assert shown(pg) and rh(pg) == '/keys'                                       # a reload keeps the pane
                pg.go_back(); pg.wait_for_function("() => !new URLSearchParams(location.search).get('rh')")
                assert not shown(pg)                                                         # browser Back closes it

                pg.evaluate("abhyasaPane.open('/keys', 'Keyboard shortcuts')"); pg.wait_for_function("() => document.documentElement.classList.contains('rh-open')")
                g = pg.locator('#rh-pane .grip').bounding_box(); w0 = pg.locator('#rh-pane').bounding_box()['width']
                x, y = g['x'] + g['width'] / 2, g['y'] + 200
                pg.mouse.move(x, y); pg.mouse.down(); pg.mouse.move(x - 60, y, steps=4); pg.mouse.move(x - 100, y, steps=4); pg.mouse.up()
                w1 = pg.locator('#rh-pane').bounding_box()['width']
                assert abs(w1 - w0 - 100) < 4 and pg.evaluate("+localStorage.getItem('rh-w')") == round(w1)   # the grip drags, and the width is kept
                pg.locator('#rh-pane .grip').focus(); pg.keyboard.press('ArrowLeft')
                assert abs(pg.locator('#rh-pane').bounding_box()['width'] - w1 - 24) < 2      # an arrow key moves it 24 px
                body = pg.evaluate("() => parseFloat(getComputedStyle(document.body).paddingRight)")
                assert abs(body - pg.locator('#rh-pane').bounding_box()['width']) < 2       # the page only makes room; it is not drawn again

                pg.evaluate("window.got = 0; addEventListener('message', () => got++)")
                pg.evaluate("window.opened = []; window.open = (...a) => { opened.push(a); return null; }; 0")
                other = ("data:text/html,<script>parent.postMessage({type:'rh:close'}, '*'); parent.postMessage({type:'rh:at', url:'/evil'}, '*');"
                         "parent.postMessage({type:'rh:open', url:'/learning'}, '*'); parent.postMessage({type:'rh:link', url:'https://evil.example/'}, '*')</script>")   # a page in the pane frame, from another origin
                pg.evaluate("u => document.querySelector('#rh-pane iframe').contentWindow.location.replace(u)", other)   # replace: no new history entry
                pg.wait_for_function('got >= 4'); time.sleep(.3)
                assert shown(pg) and rh(pg) == '/keys' and pg.evaluate('opened') == []                                       # messages from another origin change nothing
                pg.evaluate("window.postMessage({type:'rh:close'}, location.origin)"); time.sleep(.2)
                assert shown(pg)                                                             # nor do messages that do not come from the pane

                pg.evaluate("document.querySelector('#rh-pane iframe').contentWindow.location.replace('/keys?pane=1')")
                pg.wait_for_function("() => document.querySelector('#rh-pane iframe').contentDocument?.documentElement?.classList.contains('in-pane')")
                fr.locator('body').click(position=dict(x=5, y=5)); pg.keyboard.press('Escape')
                pg.wait_for_function("() => !document.documentElement.classList.contains('rh-open')")
                assert not rh(pg)                                                            # Esc in the pane closes it

                pg.evaluate("abhyasaPane.open('/keys', 'Keyboard shortcuts')"); pg.wait_for_function("() => document.documentElement.classList.contains('rh-open')")
                pg.locator('body').click(position=dict(x=5, y=300)); pg.keyboard.press('Alt+z')
                pg.wait_for_function("() => !document.documentElement.classList.contains('rh-open')")
                assert not rh(pg)                                                            # ⌥Z goes back to the page

                pg.goto(f'{base}/s/{sid}'); pg.wait_for_selector('#composer textarea')
                pg.evaluate("document.querySelector('.mic-float').classList.add('on')")
                pg.evaluate("abhyasaPane.open('/keys', 'Keyboard shortcuts')"); pg.wait_for_function("() => document.documentElement.classList.contains('rh-open')")
                box = lambda sel: pg.locator(sel).bounding_box()
                def clear():                                                                 # the fixed parts of the page keep out of the pane
                    left = box('#rh-pane')['x']
                    for sel in ('.mic-float', '#composer'): assert box(sel)['x'] + box(sel)['width'] <= left + 1, sel
                clear()
                g = box('#rh-pane .grip'); x, y = g['x'] + g['width'] / 2, g['y'] + 200
                pg.mouse.move(x, y); pg.mouse.down(); pg.mouse.move(x - 120, y, steps=6); pg.mouse.up()
                clear()                                                                      # also after the grip makes the pane wider
                pg.evaluate('abhyasaPane.close()'); pg.wait_for_function("() => !document.documentElement.classList.contains('rh-open')")
                assert box('#composer')['x'] + box('#composer')['width'] >= 1400 - 20        # closed: the composer is full width again

                pg.set_viewport_size(dict(width=900, height=900))
                pg.evaluate("abhyasaPane.open('/keys', 'Keyboard shortcuts')"); pg.wait_for_url(base + '/keys')
                pg.wait_for_selector('main a.rh-back'); assert pg.locator('main a.rh-back').get_attribute('href') == f'/s/{sid}'   # narrow: the same tab, with a way back
            finally: b.close()
    finally: srv.should_exit = True; th.join(5)
