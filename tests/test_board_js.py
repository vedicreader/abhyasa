"The board of the screen guide comes from rupaka: the app serves rupaka's files under the old URLs, so each page and the Mac overlay load it by name."
import re
from pathlib import Path
from rupaka.board import assets, bundle

MAC = Path(__file__).parents[1]/'mac/Sources/AbhyasaGuide/OverlayPage.swift'

def _chromium():
    "True when Playwright's bundled Chromium is installed."
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p: return Path(p.chromium.executable_path).exists()
    except Exception: return False

def test_every_page_loads_the_board(mk):
    t = mk().get('/').text
    assert re.search(r'/assets/board\.js\?v=', t) and re.search(r'/assets/board\.css\?v=', t)
    assert 'texparts.js' not in t   # the board bundle has the formula parts first

def test_the_board_urls_serve_rupakas_bundles(mk):
    "`/assets/board.js` is rupaka's script with the formula parts first and the old name `abhyasaBoard`; `/assets/board.css` starts with the paper tokens."
    c = mk()
    js, css = c.get('/assets/board.js'), c.get('/assets/board.css')
    assert (js.status_code, css.status_code) == (200, 200)
    assert js.text == bundle('js') and css.text == bundle('css')
    assert js.headers['content-type'].startswith('text/javascript') and css.headers['content-type'].startswith('text/css')
    assert 'abhyasaBoard' in js.text and 'abhyasaTex' in js.text and js.text.index('rupakaTex') < js.text.index('rupakaBoard')

def test_the_pen_libraries_come_from_rupaka(mk):
    "The board loads its pen libraries from `/vendor/` by default: the app serves rupaka's copies there, and the other vendor files as before."
    c = mk()
    for name in ('rough.js', 'perfect-freehand.mjs'):
        r = c.get(f'/vendor/{name}')
        assert r.status_code == 200 and r.headers['content-type'].startswith('text/javascript'), name
        assert r.content == (assets().libs/name).read_bytes(), name
    assert c.get('/vendor/htmx.min.js').status_code == 200 and c.get('/vendor/LICENSES.md').status_code == 404

def test_the_mac_overlay_names_the_served_files(mk):
    "The Mac overlay loads the board, its style and the hand font by name, and the pen libraries from `/vendor/`: each URL is served."
    swift, c = MAC.read_text(), mk()
    for url in ('/assets/board.js', '/assets/board.css', '/assets/hand.css'): assert f'href="{url}"' in swift or f'src="{url}"' in swift and c.get(url).status_code == 200, url
    assert "assets: '/vendor/'" in swift
    fonts = re.findall(r"url\('?/assets/([^')]+\.woff2)", c.get('/assets/hand.css').text)
    assert fonts and all(c.get(f'/assets/{f}').status_code == 200 for f in fonts)
