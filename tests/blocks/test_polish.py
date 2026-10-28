"Task 19a, design polish: one check card, one main button in a view, ⌥S that sends, the keyboard sheet, native controls on the theme, and the dark and Signal rules."
import re
from pathlib import Path
from walk_data import *

ROOT = Path(__file__).parents[2]/'abhyasa'
HX = {'hx-request': 'true'}

def start(cl, **data): return cl.post('/start', data=data, follow_redirects=False).headers['location'].split('/')[-1]

def shape(h):
    "The check markup of a reply: the card, its question, the thread and each kind of message, in order and with no text."
    return [re.sub(r'<section[^>]*', 'card', x) for x in re.findall(r'<section[^>]*class="check[^"]*"|<div class="md q">|<ol class="thread"|<li class="m you|class="tag (?:ok|no)"|<span class="k">First error: </span>', re.sub(r' id="[^"]*"', '', h))]

# F3: one check card for the session and the walk

def test_session_and_walk_draw_the_same_check(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    cl.get(f'/w/{jid}/1/check')
    w = cl.post(f'/w/{jid}/1/answer', data=dict(answer='add the scores')).text
    sid = start(cl); cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/answer', data=dict(answer='add the scores'))
    s = cl.get(f'/s/{sid}').text
    s = s[s.index('class="check qa"') - 40:]
    assert shape(w)[:6] == shape(s)[:6] == ['card', '<div class="md q">', '<ol class="thread"', '<li class="m you',
                                            'class="tag no"', '<span class="k">First error: </span>']
    css = (ROOT/'blocks/session/session.css').read_text()
    assert '.m.you { align-self' not in css and '.m .k' not in css and '.m.tutor' not in css   # "You" at the left, one style for First error
    assert '.check .q' in (ROOT/'core/base.css').read_text() and '.check .q' not in (ROOT/'blocks/walk/walk.css').read_text()

# F1: one main button in each walk step, and ⌥S is Send

def gos(h): return re.findall(r'class="(?:btn )?go"[^>]*>(.*?)</(?:button|a)>', h, re.S)

def test_open_check_sends_with_alt_s_and_skip_is_quiet(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    page = cl.get(f'/w/{jid}/1').text
    assert 'Skip this idea' in page and 'Do the check, or skip it' not in page and gos(page) == []   # the page itself has no filled button
    bar = page[page.index('class="next-bar"'):]
    assert '<kbd>' not in bar.split('</div>')[0] and 'class="quiet small"' in bar
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

def test_closed_check_hides_the_skip_with_no_reload():
    css = (ROOT/'blocks/walk/walk.css').read_text()
    assert '.walk-main:has(' in css and '.next-bar .skip' in css and 'display: none' in css.split('.next-bar .skip')[1][:40]

def test_alt_s_presses_the_first_visible_main_button():
    js = (ROOT/'core/core.js').read_text()
    assert "KeyS: ['#send', 'main .go']" in js and 'checkVisibility' in js and 'focusVisible: false' in js

def test_keys_say_what_alt_s_does_in_a_walk():
    from abhyasa.core.keys import KEYS, sanketa_pack
    walk = {k: a for g, k, a in KEYS if g == 'Walk'}
    assert walk['⌥S'].startswith('Send the open check') and 'next idea' in walk['⌥S'] and walk['⌥W'] == 'Ask for a hint'
    assert 'Send the open check' in sanketa_pack()                             # the Sanketa pack comes from the same table

# F4: one filled button in each view

def test_each_page_has_at_most_one_filled_button(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); did = add_paper(lr)
    sid = start(cl, focus='ranking'); cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/answer', data=dict(answer='a score', confidence=90))     # a miss: a weak spot, and an open session for the Continue card
    pages = ['/', '/journeys', f'/j/{jid}', f'/w/{jid}', '/settings', '/c/ranking', '/add', f'/v/store/{did}', '/you/strengths', '/you', '/you/start',
             '/learning', f'/learning/{sid}', '/concepts', '/sources', '/keys', '/graph']
    for u in pages:
        t = cl.get(u).text
        assert len(gos(t)) <= 1, (u, gos(t))
        assert u == '/keys' or t.count('<kbd>⌥S</kbd>') <= 1, u                  # the shortcut sheet lists the keys
    today = cl.get('/').text
    assert 'Continue <kbd>⌥S</kbd>' in today and re.search(r'class="btn"[^>]*>Start|>Start</button>', today) and 'autofocus' not in today
    cl.get(f'/s/{sid}/end')
    assert len(gos(cl.get(f'/s/{sid}/end').text)) <= 1

def test_model_table_has_no_filled_button():
    from abhyasa.blocks.settings.ui import UseBtn
    from fasthtml.common import to_xml
    b = to_xml(UseBtn('mlx', 'm', get=True))
    assert '>Download<' in b and 'class="go"' not in b and '/get' in b

# F11: native controls on the theme

def test_native_controls_use_the_accent():
    css = (ROOT/'core/base.css').read_text()
    assert re.search(r'input\[type=radio\], input\[type=checkbox\][^{]*\{[^}]*accent-color: var\(--acc\)', css)
    assert re.search(r'select \{[^}]*appearance: none', css)      # the select arrow in the theme colours, not the system one

# F14: the keyboard sheet lines up, and no ⌥ key has two meanings

def test_sheet_has_one_key_column_and_no_slashes(mk):
    from abhyasa.core.keys import KEYS
    assert 'grid-template-columns: 10em 1fr' in (ROOT/'blocks/keys/keys.css').read_text()
    assert not [k for _, k, _ in KEYS if ' / ' in k]
    t = mk().get('/keys').text
    assert '⌥Q' not in t and 'On a step of a walk.' in t and 'While a side walk is open' in t

def test_no_alt_key_has_two_meanings():
    "⌥W is only a hint and ⌥E only a demo: a choice question picks its options with 1 to 4, with no ⌥."
    from abhyasa.core.keys import KEYS
    alt = {}
    for g, k, a in KEYS:
        for x in re.findall(r'⌥[A-Z]', k): alt.setdefault(x, set()).add(a.split(',')[0].split('.')[0])
    assert {x: v for x, v in alt.items() if len(v) > 1 and x != '⌥S'} == {}
    js = (ROOT/'blocks/session/session.js').read_text()
    assert 'KeyQ' not in js and 'KeyE' not in js and 'KeyR' not in js and "'#o1'" not in js
    assert ('Session', '1–4', 'Pick option 1 to 4 on a choice question') in KEYS

def test_options_show_their_digit(mk, fake):
    from abhyasa.blocks.session.ui import Options
    from fasthtml.common import to_xml
    from fastcore.utils import AttrDict
    h = to_xml(Options('s', AttrDict(id='q', options=['a', 'b', 'c'])))
    assert '<kbd>1</kbd>' in h and '<kbd>3</kbd>' in h and '⌥' not in h
