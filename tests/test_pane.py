"The side pane: local URLs only, the host markup, a page in a pane, the keys, and the pane in a browser."
import re
from pathlib import Path
import pytest
from fasthtml.common import to_xml
from abhyasa.core.pane import is_local, is_web, pane_url, pane_link, PaneHost

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
    assert 'New tab ↗' in h and 'href="/w/g-1a2b/0" target="_blank"' in h and 'Attention · idea 5' in h and '<b>Derivatives</b>' in h
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

def test_source_links_open_the_pane():
    "A vault source is a pane link; a web source stays a plain link; a source with no page stays text."
    from abhyasa.core import Cites
    h = to_xml(Cites([dict(title='Rasi Characteristics', src='vault:store', ref='d1#4'), dict(title='Notes', src='notes', ref='n', url='https://example.org/n'),
                      dict(title='Ashtadhyayi 1 2', src='vedicreader', ref='a:1', url='')]))
    assert 'href="/v/store/d1"' in h and 'data-pane="/v/store/d1?pane=1"' in h and 'data-title="Rasi Characteristics"' in h
    assert h.count('data-pane') == 2 and 'href="https://example.org/n"' in h and '<span>Ashtadhyayi 1 2</span>' in h

def test_side_link_is_the_one_rule():
    "A local page that supports the exercise opens in the pane; a web page opens in a new tab with noopener; any other link is text."
    from abhyasa.core import side_link
    assert 'data-pane="/c/softmax?pane=1"' in to_xml(side_link('Softmax', '/c/softmax'))
    w = to_xml(side_link('Paper', 'https://arxiv.org/abs/1706.03762'))
    assert 'target="_blank"' in w and 'noopener' in w and 'data-pane' not in w
    for bad in ('javascript:alert(1)', '//evil.example/', 'file:///etc/passwd', ''): assert 'href' not in to_xml(side_link('x', bad)), bad

def test_step_links_that_support_the_exercise_open_in_the_pane(mk, walk_fake, lr):
    "On a step, Open in your vault and the names in the needs line open in the pane; the outline stays in the same tab."
    from walk_data import walk
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.put('Derivatives and gradients', 'The slope of a function at a point.', 'ml', slug='gradients'); lr.update('scaling-by-the-root-of-dk', prereqs=['softmax', 'gradients'])
    t = cl.get(f'/w/{jid}/2').text
    assert re.search(r'<a [^>]*data-pane="/v/[^"]*"[^>]*class="pane-link src-open"[^>]*>Open in your vault', t)
    assert 'data-pane="/c/gradients?pane=1"' in t and f'href="/w/{jid}/1"' in t and f'data-pane="/w/{jid}/1' not in t

def test_vault_page_in_the_pane(mk, lr):
    "The document page in the pane has no nav; a page with the document in `rh` names it in the pane bar."
    d = lr.vault.add([(0, 'Aries is a fire sign.')], 'Rasi Characteristics', source='/tmp/rasi.pdf', kind='pdf')['doc_id']
    cl = mk()
    t = cl.get(f'/v/store/{d}?pane=1').text
    assert 'Aries is a fire sign' in t and '<nav' not in t and 'in-pane' in t
    t = cl.get(f'/?rh=/v/store/{d}').text
    assert f'src="/v/store/{d}?pane=1"' in t and '<b>Rasi Characteristics</b>' in t

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


@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_grip_tip_covers_nothing(mk):
    "At 1440 px, the first-time tip of the grip stands between the bar and the page in the pane: it covers no part of the bar or of the page."
    import socket, threading, time, uvicorn
    from playwright.sync_api import sync_playwright
    cl = mk()
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page(viewport=dict(width=1440, height=900))
                pg.goto(f'http://127.0.0.1:{port}/'); pg.wait_for_load_state()
                pg.evaluate("localStorage.removeItem('rh-grip-tip'); abhyasaPane.open('/keys', 'Keyboard shortcuts')")
                pg.wait_for_selector('#rh-pane .grip-tip')
                box = lambda sel: pg.locator(sel).bounding_box()
                tip, bar, fr = box('#rh-pane .grip-tip'), box('#rh-pane .rh-bar'), box('#rh-pane iframe')
                assert tip['height'] > 0 and bar['y'] + bar['height'] <= tip['y'] + 1     # under the bar
                assert tip['y'] + tip['height'] <= fr['y'] + 1                             # over the page in the pane, not on it
            finally: b.close()
    finally: srv.should_exit = True; th.join(5)

YT = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1m5s'

def test_side_link_embeds_youtube_and_sends_other_links_out():
    "A YouTube link opens the watch page in the pane; a YouTube search and a web page open in a new tab with noopener; a local page keeps the pane."
    from abhyasa.core.pane import side_link, yt_embed, watch_url
    assert yt_embed(YT) == 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?start=65'
    assert yt_embed('https://youtu.be/dQw4w9WgXcQ?t=65') == 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?start=65'
    assert yt_embed('https://www.youtube.com/playlist?list=PLfYUBJiXbdtRUvTUYpLdfHHp9a58nWVXP') == 'https://www.youtube-nocookie.com/embed/videoseries?list=PLfYUBJiXbdtRUvTUYpLdfHHp9a58nWVXP'
    yt = to_xml(side_link('Video', YT))
    assert f'data-local="{watch_url(YT)}"' in yt and 'data-pane="/watch?u=' in yt and 'target="_blank"' in yt and 'noopener' in yt   # a narrow screen: the link itself, out
    for u in ('https://www.youtube.com/results?search_query=softmax', 'https://example.org/page', 'https://github.com/a/b', 'https://arxiv.org/abs/1706.03762'):
        x = to_xml(side_link('Out', u))
        assert yt_embed(u) is None and 'data-pane' not in x and 'target="_blank"' in x and 'rel="noopener noreferrer"' in x and 'out-link' in x, u
    assert 'data-pane="/keys?pane=1"' in to_xml(side_link('Keys', '/keys'))
    for bad in WEB_BAD: assert yt_embed(bad) is None

def test_watch_page_embeds_only_youtube(mk):
    "The watch page frames the video at its start, with the link out and the offline line; its CSP frames only the embed host. Another link is refused."
    from abhyasa.core.pane import watch_url
    cl = mk(['vault'])
    r = cl.get(watch_url(YT) + '&pane=1')
    assert 'src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?start=65"' in r.text and 'Watch on YouTube ↗' in r.text and 'The video needs the internet.' in r.text
    assert r.headers['content-security-policy'] == "frame-src https://www.youtube-nocookie.com; connect-src 'self' https://www.youtube-nocookie.com"
    assert 'No such video' in cl.get('/watch?u=https%3A%2F%2Fexample.org%2F').text and 'nocookie' not in cl.get('/watch?u=https%3A%2F%2Fexample.org%2F').text
