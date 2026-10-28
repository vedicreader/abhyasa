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

# F2: a calm end to a walk, and a pass never reads as "nothing happened"

def test_moved_words_never_say_nothing_happened():
    from abhyasa.core import moved_words
    m = lambda b, a, n, ok: dict(before=b, after=a, asked=n, passed=ok)
    assert moved_words(m(0, 0, 1, 1)) == ('first pass', '')                           # not "stays at unseen · 1 of 1 passed"
    assert moved_words(m(0, 0, 3, 2)) == ('on the way to recall', '2 of 3 passed')
    assert moved_words(m(0, 0, 1, 0)) == ('not yet', '')
    assert moved_words(m(2, 2, 1, 1)) == ('stays at recall', '1 of 1 passed')         # a concept that you had seen before
    assert moved_words(m(1, 3, 2, 2)) == ('recognise → explain', '2 of 2 passed')
    for f in ('blocks/walk/ui.py', 'blocks/session/ui.py', 'blocks/history/app.py'): assert 'stays at {' not in css(f), f

def finish(cl, lr, jid, sides=False):
    "Walk to the end: skip idea 1, pass idea 2, and skip idea 3. With `sides`, learn Derivatives beside idea 3 first."
    cl.post(f'/w/{jid}/start')
    cl.post(f'/w/{jid}/0/next')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    cl.get(f'/w/{jid}/1/check'); cl.post(f'/w/{jid}/1/answer', data=dict(answer='the rank is a position', confidence=70))
    if sides:
        needs_gradients(lr)
        sid = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url'].split('/')[2]
        cl.get(f'/w/{sid}/0/check'); cl.post(f'/w/{sid}/0/answer', data=dict(answer='the rank is a position', confidence=90))
        cl.post(f'/rh/back/{sid}')
    cl.post(f'/w/{jid}/2/next')
    return cl.get(f'/w/{jid}/2/done').text

def test_the_end_of_a_walk_is_calm(mk, walk_fake, lr):
    "The last page says You finished the walk, has one dot for each idea, sums up the whole walk, and goes back to Today."
    walk_fake.rules['You grade one answer'] = dict(correct=True, grade=9, first_error='', misconception='', feedback='Yes.')
    cl = mk(); jid = walk(cl, lr)
    t = finish(cl, lr, jid, sides=True)
    assert '<h1>You finished the walk</h1>' in t and 'Section done' not in t and 'You did no checks' not in t
    dots = re.findall(r'<i class="d (\w+)"', t)
    assert dots == ['skipped', 'done', 'skipped'], dots
    assert '3 ideas from Attention Is All You Need. 1 solid, 2 skipped.' in t
    assert 'What moved' in t and 'Softmax' in t.split('What moved')[1] and 'stays at unseen' not in t
    assert 'You also learned Derivatives and gradients on the way.' in t
    assert re.search(r'The first review is (today|tomorrow|in \d+ days)\.', t)
    gos = re.findall(r'class="btn go"[^>]*>(.*?)</a>', t)
    assert gos == ['Back to Today <kbd>⌥S</kbd>'] and 'href="/graph" class="btn">See the graph</a>' in t and 'Back to your journeys' not in t
    assert 'Well walked' not in t and 'p.well' not in css('blocks/walk/walk.css')        # the H1 closes the page: no closing line

def test_a_section_with_no_checks_says_how_to_come_back(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); cl.post(f'/w/{jid}/0/next')
    t = cl.get(f'/w/{jid}/0/done').text
    assert 'You skipped the checks in this section. You can come back to them from the outline.' in t and 'Section done' in t

# F8: the small copy faults

def test_meta_lines_have_no_stray_dot(mk, lr):
    "A concept with no subject: no line starts with a dot, on the concept page and in the list."
    cl = mk(); lr.put('Loose idea', 'An idea with no subject.', '')
    page, lst = cl.get('/c/loose-idea').text, cl.get('/concepts').text
    for t in (page, lst): assert not re.search(r'class="mute">\s*·', t), re.findall(r'class="mute">\s*·[^<]{0,30}', t)

def test_counts_have_the_right_plural(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr)
    assert '1 documents' not in cl.get('/sources').text and ' 1 document' in cl.get('/sources').text
    assert not re.search(r'\b1 concepts\b', cl.get('/concepts').text + cl.get('/').text)
    assert not re.search(r'of 1 (ideas|steps)\b', cl.get('/journeys').text + cl.get(f'/j/{jid}').text)

def test_leaving_a_side_walk_early_says_so_plainly(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    sid = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url'].split('/')[2]
    cl.post(f'/rh/back/{sid}')
    strip = cl.get(f'/w/{jid}/2').text.split('class="rh-strip"')[1].split('class="rh-line"')[0]
    assert 'You looked at <b>Derivatives and gradients</b> on the way. You did not do its check yet.' in strip
    assert 'Finish the side walk' in strip and '0 ideas' not in strip and 'See the side walk' not in strip

def test_best_way_needs_two_passes():
    from fasthtml.common import to_xml
    from abhyasa.blocks.strengths.ui import Ways
    assert 'Your best way' not in to_xml(Ways(dict(methods={'*': {'example': (0, 1)}})))
    assert 'Your best way' in to_xml(Ways(dict(methods={'*': {'example': (2, 0)}})))

def test_code_check_counts_tries_in_one_place(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why=''))
    card = cl.get(f'/w/{jid}/1/check').text
    assert 'tries left' not in card
    out = cl.post(f'/w/{jid}/1/run', data=dict(source=NAIVE)).text
    assert re.search(r'Try 1 of 3 · \d of 3 tests pass', out) and 'try 1 ·' not in out

def test_concept_page_copy(mk, walk_fake, lr):
    "The journey select has a label, and a source on a vault shelf says in your vault, not its machine name."
    from fasthtml.common import to_xml
    from abhyasa.core import Cites
    cl = mk(); walk(cl, lr)
    t = cl.get('/c/ranking').text
    assert 'Add this idea to a journey' in t
    assert 'in your vault' in to_xml(Cites([dict(title='Notes', src='vault:store', ref='d1')])) and 'vault:store' not in to_xml(Cites([dict(title='Notes', src='vault:store', ref='d1')]))

def test_today_says_next_as_a_verb(mk, lr):
    lr.put('Ranking', 'Order items by a score.', 'ml')
    t = mk().get('/').text
    assert not re.search(r'Next: [^<]+ at (recognise|recall|explain|apply|transfer)\.', t) and re.search(r'Next: (recognise|recall|explain|apply|transfer) Ranking\.', t)

# Magic touches. Each one stops under reduced motion: the rule in base.css stops every animation and transition.

def test_reduced_motion_stops_all_motion():
    b = css('core/base.css')
    rule = b[b.index('@media (prefers-reduced-motion: reduce)'):]
    assert 'animation: none !important; transition: none !important' in rule and '::view-transition-group(*)' in rule

def test_m4_the_dots_fill_one_by_one_then_the_sum_fades_in(mk, walk_fake, lr):
    w = css('blocks/walk/walk.css')
    assert re.search(r'\.walk-dots \.d:is\(\.done, \.known, \.shaky\) \{[^}]*animation: dot-fill var\(--dur-3\) var\(--ease\) both; animation-delay: calc\(var\(--i\) \* 60ms\)', w)
    assert re.search(r'\.walk-sum \{[^}]*animation: fade var\(--dur-2\) var\(--ease\) both; animation-delay: calc\(var\(--n\) \* 60ms \+ var\(--dur-3\)\)', w)
    cl = mk(); jid = walk(cl, lr)
    t = finish(cl, lr, jid)
    assert 'class="walk-sum" style="--n:3"' in t and 'style="--i:2"' in t

def test_m1_the_next_idea_comes_in_gently():
    "htmx swaps a whole page in a view transition, only with motion; a part of a page swaps with none. Only the idea moves."
    js, w = css('core/core.js'), css('blocks/walk/walk.css')
    from fastcore.utils import AttrDict
    from fasthtml.common import to_xml
    from abhyasa.blocks.walk.ui import Dots
    long = to_xml(Dots(AttrDict(steps=[AttrDict(dot='done')] * 30, done=30)))
    assert 'style="--i:5"' in long and 'style="--i:6"' not in long                  # the stagger stops at 5, so the sum shows within 600 ms
    assert 'htmx.config.globalViewTransitions = abhyasaMotion()' in js and "'htmx:beforeTransition'" in js and 'document.body' in js
    assert '.walk-main { view-transition-name: idea; }' in w and '::view-transition-old(root), ::view-transition-new(root) { animation: none; }' in css('core/base.css')   # no page crossfades
    assert re.search(r'::view-transition-old\(idea\) \{ animation: idea-out 120ms', w) and re.search(r'::view-transition-new\(idea\) \{ animation: idea-in var\(--dur-2\)', w)
    assert re.search(r'@keyframes idea-in \{ from \{ opacity: 0; transform: translateY\(8px\); \} \}', w)

def test_m2_the_check_answers_in_place():
    "When a check closes, its tag fades in and a 2 px line in the outcome colour grows under the question, in the walk and the session."
    b = css('core/base.css')
    assert re.search(r'\.check \.close > \.tag, #code-out > \.tag \{ animation: fade var\(--dur-2\)', b)
    assert re.search(r'\.check:has\(\.thread > \.close > \.tag, #code-out > \.tag\) > \.q::after \{[^}]*height: 2px[^}]*background: var\(--ok\)[^}]*transform-origin: left[^}]*animation: grow var\(--dur-3\)', b)
    assert re.search(r':has\(\.close > \.tag\.no, #code-out > \.tag\.no\) > \.q::after \{ background: var\(--no\); \}', b)
    assert '@keyframes grow { from { transform: scaleX(0); } }' in b

def test_m3_the_outline_dot_fills(mk, walk_fake, lr):
    "The answer that closes a check also swaps the idea in the outline (class `just`, so its dot fills) and the progress line."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    page = cl.get(f'/w/{jid}/1').text
    assert 'id="rail-1"' in page and 'id="rail-prog"' in page and 'id="rail-bar"' in page
    cl.get(f'/w/{jid}/1/check')
    r = cl.post(f'/w/{jid}/1/answer', data=dict(answer='the rank is a position')).text
    assert re.search(r'<li hx-swap-oob="true" id="rail-1" class="c (done|shaky) on just"', r) and re.search(r'<span [^>]*hx-swap-oob="true" id="rail-prog"', r)
    miss = cl.post(f'/w/{jid}/2/answer', data=dict(answer='x')).text
    assert 'rail-' not in miss                                                       # no swap while a check stays open
    w, b = css('blocks/walk/walk.css'), css('core/base.css')
    assert re.search(r'\.outline li\.c\.just::before \{ animation: dot-grow var\(--dur-3\) var\(--ease\) both; \}', w) and '@keyframes dot-grow { from { transform: scale(.4); } }' in w
    assert re.search(r'\.prog i \{[^}]*transition: width var\(--dur-3\) var\(--ease\)', b)
    assert "'rail-' + " in css('blocks/walk/walk.js')                                  # a demo check fills its dot from the reply of the prediction

def test_m6_words_in_the_passage_point_at_the_demo(mk, walk_fake, lr):
    "The passage names the words that the idea moves; walk.js marks them and the demo labels, and rings the matching part of the demo."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    page = cl.get(f'/w/{jid}/2').text
    assert '<blockquote data-moves=\'["dot products", "weights"]\' id="passage" class="quote">' in page
    js, w = css('blocks/walk/walk.js'), css('blocks/walk/walk.css')
    assert 'dataset.moves' in js and "'.rk-b'" in js and "'mv-hot'" in js and 'rkReady' in js
    assert '[hidden] { display: none !important; }' in css('core/base.css')          # the demo's hidden Next idea stays hidden in its flex row
    assert re.search(r'#passage \.mv \{[^}]*text-decoration: underline dotted', w) and re.search(r'\.walk-demo \.rk-b\.mv-hot \{[^}]*box-shadow: 0 0 0 2px', w)

def test_m7_the_side_walk_returns_you():
    "The pane slides out to the right when it closes; the new needs line and the strip come in on the paper. The focus goes back to the answer."
    p, pj, d, dj = css('core/pane.css'), css('core/pane.js'), css('blocks/detour/detour.css'), css('blocks/detour/detour.js')
    assert re.search(r'html\.rh-open\.rh-leave #rh-pane \{[^}]*transform: translateX\(100%\)[^}]*transition: transform var\(--dur-2\) var\(--ease\)', p)
    assert "classList.add('rh-leave')" in pj and 'prefers-reduced-motion: reduce' in pj and "classList.remove('rh-open', 'rh-leave')" in pj and 'focusCheck()' in pj
    assert "fresh.classList.add('fresh')" in dj
    assert re.search(r'\.rh-needs\.fresh \.st\.today \{ animation: fade var\(--dur-3\)', d) and re.search(r'\.rh-needs\.fresh \.rh-strip \{ animation: rise var\(--dur-2\)', d)
