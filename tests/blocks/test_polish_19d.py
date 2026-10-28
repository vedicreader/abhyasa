"Task 19d, the last design faults: the 1000 px band, the pane bar, lists of the same button, the session answer bar, and small copy faults."
import re
from pathlib import Path
from walk_data import *

ROOT = Path(__file__).parents[2]/'abhyasa'
def src(p): return (ROOT/p).read_text()

# 1. The 1000 px band: the outline folds into one line, and Continue goes when it has no room

def test_outline_is_one_line_that_opens(mk, walk_fake, lr):
    "The outline is a details: its summary is the label and the progress line; the list of ideas is in the fold."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    h = cl.get(f'/w/{jid}/2').text
    rail = h[h.index('id="rail"'):]; rail = rail[:rail.index('</aside>')]
    assert re.search(r'<details[^>]*><summary[^>]*><span class="lbl">The paper · 3 of 3</span><span[^>]*id="rail-prog"', rail), rail[:400]
    assert rail.index('</summary>') < rail.index('<ol>') and 'id="rail-0"' in rail

def test_outline_folds_only_under_1040_px():
    "Over 1040 px the fold is always open and the summary is only a label; under it, the summary opens the fold and has an arrow."
    w = src('blocks/walk/walk.css')
    assert re.search(r'@supports selector\(::details-content\) \{ @media \(min-width: 1041px\) \{[^}]*::details-content \{ content-visibility: visible', w)
    assert re.search(r"\.outline summary::after \{[^}]*content: '▸'", w) and "details[open] > summary::after" in w

def test_continue_goes_when_it_has_no_room():
    "core.js hides Continue in the top bar when it would show less than its first words; ⌥C still finds it."
    js, b = src('core/core.js'), src('core/base.css')
    assert "classList.toggle('no-room'" in js and 'nav #continue.no-room { display: none; }' in b
    assert "e.code === 'KeyC' && document.querySelector('#continue')" in js
