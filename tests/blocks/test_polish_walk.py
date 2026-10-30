"Task 19b, the walk, the side pane and the end of a walk: the way beside, the copy, and the outline that answers in place."
import re
from walk_data import *

def needs_gradients(lr):
    lr.put('Derivatives and gradients', 'The slope of a function at a point, one for each input.', 'ml', slug='gradients')
    lr.update('scaling-by-the-root-of-dk', prereqs=['softmax', 'gradients'])

# F6: the side pane in a narrow window

def test_narrow_view_names_the_open_side_walk(mk, walk_fake, lr):
    "Under 1100 px the pane does not show, so a line over the title names the side walk and opens it."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    sid = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url'].split('/')[2]
    t = cl.get(f'/w/{jid}/2?rh=/w/{sid}/0').text
    narrow = re.search(r'<a [^>]*class="rh-back rh-narrow"[^>]*>(.*?)</a>', t)
    assert narrow and f'href="/w/{sid}/0"' in narrow.group(0) and 'You have a side walk open: <b>Derivatives and gradients' in narrow.group(1) and 'Open it →' in narrow.group(1), t[:3000]
    assert '<b>Derivatives and gradients' in t.split('id="rh-pane"')[1]                   # the pane bar has the title on a reload too
    assert 'rh-narrow' not in cl.get(f'/w/{jid}/2').text

# F5: the way beside is easy to find, and one act has one name

def test_each_unmet_need_can_be_learned_beside(mk, walk_fake, lr):
    "Each need that you have not learned has Learn beside; only the first shows ⌥B."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    page = cl.get(f'/w/{jid}/2').text
    line = page[page.index('class="rh-line"'):].split('id="rh-offer"')[0]
    assert line.count('Learn beside') == 2 and line.count('<kbd>⌥B</kbd>') == 1 and 'data-t="softmax"' in line and 'data-t="gradients"' in line
    assert 'not learned yet' in line and 'you have not learned it' not in line and 'open beside' not in page

def test_one_name_for_each_way_beside():
    "Learn beside on the gap line and the keys; Its own session in the pane bar."
    from fasthtml.common import to_xml
    from abhyasa.blocks.detour.ui import GapLine
    from abhyasa.core.pane import PaneHost
    from abhyasa.core.keys import KEYS
    assert 'Learn beside <kbd>⌥B</kbd>' in to_xml(GapLine([('gradients', 'Derivatives')])) and 'Learn it beside' not in to_xml(GapLine([('g', 'G')]))
    assert 'Its own session ↗' in to_xml(PaneHost('/w/g/0'))
    assert ('Walk', '⌥B', 'Learn beside: learn a missing idea in the side pane') in KEYS

# F2: a calm end to a walk, and a pass never reads as "nothing happened"

def test_moved_words_never_say_nothing_happened():
    from abhyasa.core import moved_words
    m = lambda b, a, n, ok: dict(before=b, after=a, asked=n, passed=ok)
    assert moved_words(m(0, 0, 1, 1)) == ('first pass', '')                           # not "stays at unseen · 1 of 1 passed"
    assert moved_words(m(0, 0, 3, 2)) == ('on the way to recall', '2 of 3 passed')
    assert moved_words(m(0, 0, 1, 0)) == ('not yet', '')
    assert moved_words(m(2, 2, 1, 1)) == ('stays at recall', '1 of 1 passed')         # a concept that you had seen before
    assert moved_words(m(1, 3, 2, 2)) == ('recognise → explain', '2 of 2 passed')

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
    assert gos == ['Back to Today <kbd>⌥S</kbd>'] and re.search(r'href="/graph"[^>]*>See the graph</a>', t) and 'Back to your walks' not in t
    assert 'Well walked' not in t                                                     # the H1 closes the page: no closing line

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
    assert '1 documents' not in cl.get('/sources').text
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
    syn = cl.post(f'/w/{jid}/1/run', data=dict(source='def softmax(:')).text
    assert 'Try 2 of 3. A syntax error does not count as a try.' in syn

def test_concept_page_copy(mk, walk_fake, lr):
    "The journey select has a label, and a source on a vault shelf says in your vault, not its machine name."
    from fasthtml.common import to_xml
    from abhyasa.core import Cites
    cl = mk(); walk(cl, lr)
    t = cl.get('/c/ranking').text
    assert 'Add this idea to a walk' in t
    assert 'in your vault' in to_xml(Cites([dict(title='Notes', src='vault:store', ref='d1')])) and 'vault:store' not in to_xml(Cites([dict(title='Notes', src='vault:store', ref='d1')]))

def test_today_says_next_as_a_verb(mk, lr):
    lr.put('Ranking', 'Order items by a score.', 'ml')
    t = mk().get('/').text
    assert not re.search(r'Next: [^<]+ at (recognise|recall|explain|apply|transfer)\.', t) and re.search(r'Next: (recognise|recall|explain|apply|transfer) Ranking\.', t)

# The outline and the passage answer the check

def test_m3_the_outline_dot_fills(mk, walk_fake, lr):
    "The answer that closes a check also swaps the idea in the outline (class `just`, so its dot fills) and the progress line."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    page = cl.get(f'/w/{jid}/1').text
    assert 'id="rail-1"' in page and 'id="rail-prog"' in page and 'id="rail-bar"' in page
    cl.get(f'/w/{jid}/1/check')
    r = cl.post(f'/w/{jid}/1/answer', data=dict(answer='the rank is a position')).text
    li = re.search(r'<li [^>]*id="rail-1"[^>]*>', r).group(0)
    assert 'hx-swap-oob="true"' in li and re.search(r'class="c (done|shaky) on just"', li)
    assert 'hx-swap-oob="true"' in re.search(r'<span [^>]*id="rail-prog"[^>]*>', r).group(0)
    miss = cl.post(f'/w/{jid}/2/answer', data=dict(answer='x')).text
    assert 'rail-' not in miss                                                       # no swap while a check stays open

def test_m6_words_in_the_passage_point_at_the_demo(mk, walk_fake, lr):
    "The passage names the words that the idea moves, so the page can point them at the demo (walk_look m6 checks the pointing)."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    page = cl.get(f'/w/{jid}/2').text
    quote = re.search(r'<blockquote [^>]*id="passage"[^>]*>', page).group(0)
    assert 'data-moves=\'["dot products", "weights"]\'' in quote
