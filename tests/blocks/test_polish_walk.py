"Task 19b, design polish of the walk, the side pane and the end of a walk: the layout, the way beside, the copy, and the magic touches."
import re
from pathlib import Path
from walk_data import *

ROOT = Path(__file__).parents[2]/'abhyasa'
def css(p): return (ROOT/p).read_text()

def needs_gradients(lr):
    lr.put('Derivatives and gradients', 'The slope of a function at a point, one for each input.', 'ml', slug='gradients')
    lr.update('scaling-by-the-root-of-dk', prereqs=['softmax', 'gradients'])

# F7: the step page lines up

def test_step_page_lines_up():
    "The crumbs start where the outline starts, the layout fits a 1000 px window, and the outline goes under 1040 px."
    w = css('blocks/walk/walk.css')
    assert re.search(r'main\.wide:has\(\.walk-layout\) > \.crumbs \{[^}]*max-width: 984px[^}]*margin-inline: auto', w)
    assert 'grid-template-columns: 220px minmax(0, 720px); gap: var(--s7)' in w
    assert '@media (max-width: 1040px) { .walk-layout' in w and '900px' not in w

# F6: the side pane

def test_top_bar_fits_beside_the_pane():
    "With the pane open, the top bar drops Continue and the search box and keeps one row; under 1100 px it drops Continue. ⌥C and / still work."
    p, b, js = css('core/pane.css'), css('core/base.css'), css('core/core.js')
    assert re.search(r'html\.rh-open body > nav \{[^}]*gap: var\(--s3\)', p) and 'html.rh-open body > nav :is(#continue, form) { display: none; }' in p
    assert 'flex-wrap: wrap; }   /* the narrower page' not in p
    assert re.search(r'@media \(max-width: 1099px\) \{ body > nav \{ gap: var\(--s4\); \} body > nav #continue \{ display: none; \} \}', b)
    assert "e.code === 'KeyC'" in js and "location.assign('/search')" in js

def test_pane_does_not_repeat_the_outline_and_its_bar_lines_up():
    w, p = css('blocks/walk/walk.css'), css('core/pane.css')
    assert 'html.in-pane .walk-layout { grid-template-columns: minmax(0, 1fr); }' in w and 'html.in-pane .walk-layout > .outline { display: none; }' in w
    assert re.search(r'\.rh-bar \{[^}]*min-height: var\(--nav-h\)', p)

def test_narrow_view_names_the_open_side_walk(mk, walk_fake, lr):
    "Under 1100 px the pane does not show, so a line over the title names the side walk and opens it."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    sid = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url'].split('/')[2]
    t = cl.get(f'/w/{jid}/2?rh=/w/{sid}/0').text
    assert re.search(rf'<a href="/w/{sid}/0" data-pane="/w/{sid}/0\?pane=1" class="rh-back rh-narrow">You have a side walk open: <b>Derivatives and gradients[^<]*</b>. Open it →</a>', t), t[:3000]
    assert '<b>Derivatives and gradients' in t.split('id="rh-pane"')[1]                   # the pane bar has the title on a reload too
    assert 'rh-narrow' not in cl.get(f'/w/{jid}/2').text
    assert "pane?.checkVisibility()" in css('blocks/walk/walk.js')                      # the check does not wait for a pane that does not show
    assert re.search(r'main > a\.rh-narrow \{ display: none; \}', css('core/pane.css')) and '@media (max-width: 1099px) { main > a.rh-narrow { display: inline-block; } }' in css('core/pane.css')

# F5: the way beside is easy to find, and one act has one name

def test_each_unmet_need_can_be_learned_beside(mk, walk_fake, lr):
    "Each need that you have not learned has Learn beside; only the first shows ⌥B. The state is muted, and no line starts with a dot."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    page = cl.get(f'/w/{jid}/2').text
    line = page[page.index('class="rh-line"'):].split('id="rh-offer"')[0]
    assert line.count('Learn beside') == 2 and line.count('<kbd>⌥B</kbd>') == 1 and 'data-t="softmax"' in line and 'data-t="gradients"' in line
    assert 'not learned yet' in line and 'you have not learned it' not in line and 'open beside' not in page
    d = css('blocks/detour/detour.css')
    assert '.need + .need::before' not in d and re.search(r'\.rh-line \{[^}]*column-gap: var\(--s5\)', d) and re.search(r'\.rh-line \.need \{[^}]*inline-flex', d)
    assert re.search(r'\.rh-line \.st\.missing \{[^}]*color: var\(--mute\)', d)

def test_one_name_for_each_way_beside():
    "Learn beside on the needs line, the gap line, the selected word and the keys; Its own session in the offer and the pane bar."
    from fasthtml.common import to_xml
    from abhyasa.blocks.detour.ui import GapLine
    from abhyasa.core.pane import PaneHost
    from abhyasa.core.keys import KEYS
    assert 'Learn beside <kbd>⌥B</kbd>' in to_xml(GapLine([('gradients', 'Derivatives')])) and 'Learn it beside' not in to_xml(GapLine([('g', 'G')]))
    assert 'Its own session ↗' in to_xml(PaneHost('/w/g/0')) and 'Its own session ↗' in css('core/pane.js')
    js = css('blocks/detour/detour.js')
    assert "'Learn beside '" in js and "I don't know this" not in js
    assert ('Walk', '⌥B', 'Learn beside: learn a missing idea in the side pane') in KEYS

def test_one_tip_says_that_you_can_select_a_word():
    "Under the first passage of a walk, one quiet tip, shown once (localStorage `rh-tip`). It goes after one use."
    js, d = css('blocks/detour/detour.js'), css('blocks/detour/detour.css')
    assert 'Select a word that you do not know, then press ⌥B.' in js and "'rh-tip'" in js and 'localStorage' in js
    assert re.search(r'\.rh-tip \{[^}]*font-size: var\(--t-small\)[^}]*color: var\(--mute\)', d)
