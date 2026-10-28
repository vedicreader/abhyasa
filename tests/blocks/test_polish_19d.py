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

# 2. The pane bar shows the place, and the pace of the side walk

def test_pane_trail_starts_at_the_idea(mk, walk_fake, lr):
    "A side walk tells the pane a trail that starts at the idea (`Idea 3`), with no walk title, and its pace: `Side walk · 1 of 1`."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.put('Derivatives and gradients', 'The slope of a function at a point, one for each input.', 'ml', slug='gradients')
    lr.update('scaling-by-the-root-of-dk', prereqs=['softmax', 'gradients'])
    url = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url']
    h = cl.get(url + '?pane=1').text
    back = re.search(r'<a href="[^"]*" data-rh-trail=\'([^\']*)\' data-rh-pace="([^"]*)" class="rh-back walk-back"', h)
    assert back, h[h.find('walk-back') - 300:h.find('walk-back') + 50]
    assert back.group(1).startswith('[["Idea 3", ') and 'Attention' not in back.group(1)
    assert back.group(2) == 'Side walk · 1 of 1'

def test_pane_bar_draws_the_pace():
    "pane.js sends the pace and the progress of the page in the pane, and the bar draws them on a second row with the thin line."
    js, c = src('core/pane.js'), src('core/pane.css')
    assert 'dataset.rhPace' in js and "querySelector('#rail-prog')" in js and "'rh-pace'" in js and "className = 'prog'" in js
    assert re.search(r'\.rh-pace \{[^}]*display: flex', c) and re.search(r'\.rh-bar \{[^}]*flex-direction: column', c)

# 3. A list has one button: on the current journey, or the current open session; the other rows have a quiet link

def test_journeys_have_one_button(mk, walk_fake, lr):
    "Journeys: only the first journey with a step to do has a button; the others have a quiet `Continue →` link that shows on hover and focus."
    cl = mk()
    for _ in range(3): walk(cl, lr)
    h = cl.get('/journeys').text
    rows = h.split('class="jrow"')[1:]
    assert len(rows) == 3 and sum('class="btn small"' in r for r in rows) == 1 and 'class="btn small">Continue the walk' in rows[0], rows
    assert all(re.search(r'<a href="[^"]*" class="onward">Continue →</a>', r) for r in rows[1:])
    b = src('core/base.css')
    assert re.search(r'\.onward \{[^}]*opacity: 0', b) and ':focus-within .onward' in b and '@media (hover: none) { .onward { opacity: 1; } }' in b

def test_your_learning_has_one_continue_and_no_open(mk, lr):
    "Your learning: only the newest open session has the Continue button; an older open one has a quiet link; no row has Open."
    row = [dict(concept='ranking', correct=True, depth=1, question='q', turns=[])]
    lr.log_session('old1', 'An older open session.', start=3., updated=3., log=row)
    lr.log_session('new1', 'An open session.', start=5., updated=5., log=row)
    h = mk().get('/learning').text
    runs = h[h.index('class="days"'):]
    assert runs.count('class="btn small">Continue') == 1 and runs.index('/s/new1') < runs.index('class="btn small">Continue') < runs.index('/s/old1'), runs[:3000]
    assert re.search(r'<a href="/s/old1" class="onward">Continue →</a>', runs) and '>Open<' not in runs
