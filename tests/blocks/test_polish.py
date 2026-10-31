"Task 19a: one check card, one main button in a view, ⌥S that sends, and the keyboard sheet."
import re
from walk_data import *

HX = {'hx-request': 'true'}

def start(cl, **data): return cl.post('/start', data=data, follow_redirects=False).headers['location'].split('/')[-1]

# F3: one check card for the session and the walk

def test_session_and_walk_draw_the_same_check(mk, walk_fake, lr):
    "A miss in a walk and in a session shows the question, your answer, Not yet and the first error."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    cl.get(f'/w/{jid}/1/check')
    w = cl.post(f'/w/{jid}/1/answer', data=dict(answer='add the scores')).text
    sid = start(cl); cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/answer', data=dict(answer='add the scores'))
    s = cl.get(f'/s/{sid}').text
    for h in (w, s):
        for x in ('What does a rank tell you?', 'add the scores', 'Not yet', 'Error: ', 'You add raw scores.'): assert x in h, x

# F1: one main button in each walk step, and ⌥S is Send

def gos(h): return re.findall(r'class="(?:btn )?go"[^>]*>(.*?)</(?:button|a)>', h, re.S)

def test_open_check_sends_with_alt_s_and_skip_is_quiet(mk, walk_fake, lr):
    "The look is the feature: a step has one main button, Send while the check is open and Next idea when it closes, and ⌥S names it."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    page = cl.get(f'/w/{jid}/1').text
    assert 'Skip this idea' in page and 'Do the check, or skip it' not in page and gos(page) == []   # the page itself has no filled button
    bar = page[page.index('class="next-bar"'):]
    assert '<kbd>' not in bar.split('</div>')[0]                                 # the skip names no key
    card = cl.get(f'/w/{jid}/1/check').text
    assert len(gos(card)) == 1 and 'Send <kbd>⌥S</kbd>' in card and 'id="send"' in card   # Send is the one main button, with ⌥S
    shut = cl.post(f'/w/{jid}/1/answer', data=dict(answer='the rank is a position')).text
    assert len(gos(shut)) == 1 and 'Next idea <kbd>⌥S</kbd>' in shut and 'autofocus' not in shut and 'data-focus="1"' in shut
    page = cl.get(f'/w/{jid}/1').text
    assert 'Skip this idea' not in page                                        # a closed check: the next bar holds only the way back
    assert 'Next idea' not in page.split('id="check"')[1].split('class="next-bar"')[1]

def test_code_check_runs_with_alt_s(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why=''))
    card = cl.get(f'/w/{jid}/1/check').text
    assert gos(card) and 'Run the tests <kbd>⌥S</kbd>' in card and len(gos(card)) == 1
    out = cl.post(f'/w/{jid}/1/run', data=dict(source=GOOD)).text
    assert len(gos(out)) == 1 and 'Next idea <kbd>⌥S</kbd>' in out          # the run button goes off, so ⌥S presses Next idea

def test_keys_say_what_alt_s_does_in_a_walk():
    from abhyasa.core.keys import KEYS, sanketa_pack
    walk = {k: a for g, k, a in KEYS if g == 'Walk'}
    assert walk['⌥S'].startswith('Send the open check') and 'next idea' in walk['⌥S'] and walk['⌥W'] == 'Ask for a hint'
    assert 'Send the open check' in sanketa_pack()                             # the Sanketa pack comes from the same table

# F4: one filled button in each view

def test_each_page_has_at_most_one_filled_button(mk, walk_fake, lr):
    "The look is the feature: one main button in each view, so ⌥S has one meaning on each page."
    cl = mk(); jid = walk(cl, lr); did = add_paper(lr)
    sid = start(cl, focus='ranking'); cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/answer', data=dict(answer='a score', confidence=90))     # a miss: a weak spot, and an open session for the Continue card
    pages = ['/', '/journeys', f'/j/{jid}', f'/w/{jid}', '/settings', '/c/ranking', '/add', f'/v/store/{did}', '/you/strengths', '/you', '/you/start',
             '/learning', f'/learning/{sid}', '/concepts', '/sources', '/keys', '/graph']
    for u in pages:
        t = cl.get(u).text
        assert len(gos(t)) <= 1, (u, gos(t))
        assert u == '/keys' or t.count('<kbd>⌥S</kbd>') <= 1, u                  # the shortcut sheet lists the keys
    assert gos(cl.get('/').text) == ['Continue <kbd>⌥S</kbd>']                 # the Continue card is the main button, and Start is plain
    assert 'autofocus' not in cl.get('/').text
    assert gos(cl.get('/c/ranking').text) == ['Learn this <kbd>⌥S</kbd>'] and re.search(r'<button[^>]*\bdisabled\b[^>]*id="start-go"|<button[^>]*id="start-go"[^>]*\bdisabled\b', cl.get('/add').text)   # an empty Start box: Start is off
    assert gos(cl.get(f'/w/{jid}').text) == ['Start the walk <kbd>⌥S</kbd>']
    cl.get(f'/s/{sid}/end')
    assert len(gos(cl.get(f'/s/{sid}/end').text)) <= 1

def test_today_with_no_open_session_starts(mk, walk_fake, lr):
    assert gos(mk().get('/').text) == ['Start <kbd>⌥S</kbd>']

def test_reloaded_closed_code_check_has_next_idea_as_main(mk, walk_fake, lr):
    "A code check that closed in this run, drawn again: Next idea is the one main button, and Run the tests is off."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why=''))
    cl.get(f'/w/{jid}/1/check'); cl.post(f'/w/{jid}/1/run', data=dict(source=GOOD))
    card = cl.get(f'/w/{jid}/1/check').text
    assert gos(card) == ['Next idea <kbd>⌥S</kbd>'] and card.count('id="run"') == 1 and 'hx-swap-oob' not in card
    assert re.search(r'<button[^>]*id="run"[^>]*disabled|<button[^>]*disabled[^>]*id="run"', card) and 'data-focus="1"' in card

def test_each_closed_walk_card_has_next_idea_as_main(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    cl.get(f'/w/{jid}/1/check'); cl.post(f'/w/{jid}/1/answer', data=dict(answer='the rank is a position'))
    assert gos(cl.get(f'/w/{jid}/1/check').text) == ['Next idea <kbd>⌥S</kbd>']

def test_side_walk_end_names_alt_s_on_back_to_the_paper():
    "At the end of a side walk, Back to the paper is the main button with ⌥S, before or after the section summary."
    from fasthtml.common import Div, to_xml
    from abhyasa.core import one_main, Primary
    from abhyasa.blocks.detour.ui import EndNote
    for order in (1, -1):
        parts = [EndNote('Derivatives', True, '/w/x/2', 'idea 3 of 3', 'gradients', 'solid'), Primary('Back to your journeys', href='/journeys')]
        assert gos(to_xml(Div(*one_main(parts[::order])))) == ['← Back to the paper: idea 3 of 3 <kbd>⌥S</kbd>']

def test_model_table_has_no_filled_button():
    from abhyasa.blocks.settings.ui import UseBtn
    from fasthtml.common import to_xml
    b = to_xml(UseBtn('mlx', 'm', get=True))
    assert '>Download<' in b and 'class="go"' not in b and '/get' in b

# F14: the keyboard sheet, and no ⌥ key has two meanings

def test_sheet_has_one_key_column_and_no_slashes(mk):
    from abhyasa.core.keys import KEYS
    assert not [k for _, k, _ in KEYS if ' / ' in k]
    t = mk().get('/keys').text
    assert t.count('⌥Q') == 1 and 'Go to Learn' in t and 'On a step of a walk.' in t and 'While a side walk is open' in t

def test_no_alt_key_has_two_meanings():
    "⌥W is only a hint and ⌥E only a demo: a choice question picks its options with 1 to 4, with no ⌥."
    from abhyasa.core.keys import KEYS
    alt = {}
    for g, k, a in KEYS:
        for x in re.findall(r'⌥[A-Z]', k): alt.setdefault(x, set()).add(a.split(',')[0].split('.')[0])
    assert {x: v for x, v in alt.items() if len(v) > 1 and x != '⌥S'} == {}
    assert ('Session', '1–4', 'Pick option 1 to 4 on a choice question') in KEYS

def test_options_show_their_digit(mk, fake):
    from abhyasa.blocks.session.ui import Options
    from fasthtml.common import to_xml
    from fastcore.utils import AttrDict
    h = to_xml(Options('s', AttrDict(id='q', options=['a', 'b', 'c'])))
    assert '<kbd>1</kbd>' in h and '<kbd>3</kbd>' in h and '⌥' not in h

# Fix round 1: the small items

def test_small_items():
    from abhyasa.core.keys import KEYS
    assert ('Walk', '⌥V', 'Keep the state of the demo') in KEYS and not [k for _, k, _ in KEYS if k == 'K']   # left hand only
