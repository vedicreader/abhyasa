"The shared pieces in core (design review, section 5): the meta line, counts, one primary button in a view, the outcome tag, the check card, and the space and type steps."
import re
from pathlib import Path
from types import SimpleNamespace
from fasthtml.common import to_xml
from abhyasa.core import meta, n_of, Primary, Secondary, Quiet, Tag, Check, Msg, FirstError, Empty, Part, Confidence
from abhyasa.core.ui import _req

CORE = Path(__file__).parents[1]/'abhyasa/core'
BLOCKS = Path(__file__).parents[1]/'abhyasa/blocks'

def test_meta_and_counts():
    assert meta('floor unseen', '', None, 'due now') == 'floor unseen · due now' and meta('', None) == ''
    assert (n_of(1, 'idea'), n_of(0, 'idea'), n_of(3, 'document'), n_of(2, 'try', 'tries')) == ('1 idea', '0 ideas', '3 documents', '2 tries')

def test_one_primary_in_a_reply():
    "The first `Primary` of a request is filled and has its key; a second one in the same request is a secondary with no key."
    tok = _req.set(SimpleNamespace(scope={}))
    try: a, b = to_xml(Primary('Continue')), to_xml(Primary('Start', href='/start'))
    finally: _req.reset(tok)
    assert 'class="go"' in a and '<kbd>⌥S</kbd>' in a
    assert 'go' not in b and 'kbd' not in b and 'class="btn"' in b and 'href="/start"' in b
    assert 'class="btn go"' in to_xml(Primary('Go on', href='/x'))                  # with no request (a test), each one is the first
    assert 'data-focus' in to_xml(Primary('Next idea', focus=True)) and 'autofocus' not in to_xml(Primary('Next idea', focus=True))
    assert 'class="quiet small"' in to_xml(Quiet('Skip this idea', small=True)) and 'class="go"' not in to_xml(Secondary('Download'))

def test_tag_has_one_colour_map():
    assert 'class="tag ok"' in to_xml(Tag('solid')) and 'Right, but shaky' in to_xml(Tag('fragile')) and 'class="tag ok"' in to_xml(Tag('fragile'))
    assert 'class="tag no"' in to_xml(Tag('gap')) and 'class="tag skip"' in to_xml(Tag('skipped')) and 'Not yet' in to_xml(Tag('nudge'))

def test_check_card():
    h = to_xml(Check(Span_('Check'), 'What does a rank tell you?', Msg('You', 'a sum'), Msg(Tag('nudge'), FirstError('You add raw scores.')), foot='F', shut=True))
    assert h.startswith('<section class="check shut">') and '<div class="md q">' in h and '<ol class="thread">' in h
    assert h.count('<li class="m">') == 2 and 'First error: ' in h and h.rstrip().endswith('F</section>')
    assert 'id="tl-1"' in to_xml(Check('', None, thread_id='tl-1'))               # an empty thread stays as a swap target
    assert FirstError('') == ''

def Span_(t):
    from fasthtml.common import Span
    return Span(t, cls='lbl')

def test_empty_part_and_confidence():
    assert to_xml(Empty('No weak spots now.')) == '<p class="mute empty">No weak spots now.</p>\n'
    p = to_xml(Part('Strong', 'x', more=['y']))
    assert '<h2>Strong</h2>' in p and '<details class="more"><summary>More</summary>y</details>' in p
    assert 'id="c1"' in to_xml(Confidence(keys=True)) and 'id="c1"' not in to_xml(Confidence())

def test_steps_are_tokens():
    "base.css has the space, type, time and top bar steps, and margins, paddings and gaps in the style sheets use them."
    css = (CORE/'base.css').read_text()
    for t in ('--s1: 4px', '--s8: 52px', '--t-lbl: 12px', '--t-q: 21px', '--t-h1: 30px', '--dur-2: 220ms', '--ease:', '--nav-h:'): assert t in css, t
    off = []
    for f in [*CORE.glob('*.css'), *BLOCKS.glob('*/*.css')]:
        for prop, val in re.findall(r'(?<![-\w])((?:margin|padding)(?:-[a-z]+)?|(?:row-|column-)?gap)\s*:\s*([^;}]+)', f.read_text()):
            if 'calc' in val or 'max(' in val or 'var(' in val and 'px' not in val: continue
            if any(4 <= float(n) <= 60 for n in re.findall(r'(\d+(?:\.\d+)?)px', val)): off.append(f'{f.name}: {prop}: {val}')
    assert not off, off
