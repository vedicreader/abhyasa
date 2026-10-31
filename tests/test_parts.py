"The shared pieces in core (design review, section 5): the meta line, counts, one primary button in a view, and the check card."
import re
from fasthtml.common import to_xml
from abhyasa.core import meta, n_of, one_main, Primary, Secondary, Quiet, Tag, Check, Msg, FirstError

def test_meta_and_counts():
    assert meta('floor unseen', '', None, 'due now') == 'floor unseen · due now' and meta('', None) == ''
    assert (n_of(1, 'idea'), n_of(0, 'idea'), n_of(3, 'document'), n_of(2, 'try', 'tries')) == ('1 idea', '0 ideas', '3 documents', '2 tries')

def test_one_primary_in_a_page():
    "A page keeps the shown `Primary` with the lowest rank, in any order; the others lose the fill, the key and the focus. A hidden one does not count."
    from fasthtml.common import Div, Form
    for order in (1, -1):
        a, b = Primary('Start', href='/start', rank=3, focus=True), Primary('Continue', rank=1)
        h = to_xml(Div(*one_main([a, b][::order])))
        assert re.search(r'class="go"[^>]*>Continue <kbd>⌥S</kbd>', h) and 'href="/start" class="btn">Start</a>' in h and 'data-focus' not in h
    h = to_xml(Div(*one_main([Form(Primary('Next idea'), hidden=True), Primary('Send')])))
    assert re.search(r'class="go"[^>]*>Next idea', h) and re.search(r'class="go"[^>]*>Send', h)   # the hidden one is not the main button yet
    assert 'data-focus' in to_xml(Primary('Next idea', focus=True)) and 'autofocus' not in to_xml(Primary('Next idea', focus=True))
    assert 'class="go"' not in to_xml(Quiet('Skip this idea', small=True)) and 'class="go"' not in to_xml(Secondary('Download'))

def test_check_card():
    "A closed card shows the question, each message, the first error and the foot."
    h = to_xml(Check(Span_('Check'), 'What does a rank tell you?', Msg('You', 'a sum'), Msg(Tag('nudge'), FirstError('You add raw scores.')), foot='F', shut=True))
    for x in ('What does a rank tell you?', 'a sum', 'Not yet', 'Error: ', 'You add raw scores.', 'F</section>'): assert x in h, x
    assert 'id="tl-1"' in to_xml(Check('', None, thread_id='tl-1'))               # an empty thread stays as a swap target
    assert FirstError('') == ''

def Span_(t):
    from fasthtml.common import Span
    return Span(t, cls='lbl')

