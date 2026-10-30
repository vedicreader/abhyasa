"The board renderer in core: the vendored pen libraries, and the rules that keep model text out of the page code."
import hashlib, re
from pathlib import Path
from abhyasa.core.keys import KEYS

CORE = Path(__file__).parents[1]/'abhyasa/core'
PINNED = {'rough.js': '6853af8619532f3939b156cd16824d2e14f31e71d3df306ad5558eeafacab194',              # roughjs 4.6.6, bundled/rough.js
          'perfect-freehand.mjs': '0ddf0e44c727ab39d7211af95685bf12234236f0e2eca376091e5791a71626e4'}  # perfect-freehand 1.2.2, dist/esm/index.mjs

def test_vendored_pens_are_pinned():
    for name, h in PINNED.items(): assert hashlib.sha256((CORE/'vendor'/name).read_bytes()).hexdigest() == h, name

def test_licences_are_kept():
    t = (CORE/'vendor/LICENSES.md').read_text()
    for s in ('Rough.js 4.6.6', 'Preet Shihn', 'perfect-freehand 1.2.2', 'Stephen Ruiz', 'MIT License'): assert s in t, s

def test_model_text_goes_in_as_text():
    "board.js never writes HTML: each say, label, quote and title goes in with textContent, and a link is http(s) or a local path."
    js = (CORE/'board.js').read_text()
    assert 'innerHTML' not in js and 'insertAdjacentHTML' not in js and 'outerHTML' not in js and 'eval(' not in js
    assert 'textContent' in js and "noopener" in js and r"/^(https?:\/\/|\/(?!\/))/" in js

def test_keys_skip_text_boxes():
    js = (CORE/'board.js').read_text()
    assert "matches('textarea, input, select, [contenteditable]')" in js
    rows = {(g, k): a for g, k, a in KEYS}
    assert rows[('Guide', 'A')] == 'Say and draw the step again' and rows[('Guide', 'S')] == 'Go back one step'
    assert rows[('Guide', 'D')] == 'Go to the next step' and rows[('Guide', 'esc')] == 'Stop the board'

def test_every_page_loads_the_board(mk):
    t = mk().get('/').text
    assert re.search(r'/assets/board\.js\?v=', t) and re.search(r'/assets/board\.css\?v=', t)
