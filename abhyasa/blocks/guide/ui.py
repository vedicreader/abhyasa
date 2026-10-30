"The parts of the guide on each page: the Explain button, the one-line box, and the strip under the board."
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import asset_js, asset_css
from .cfg import Routes

_P = Path(__file__).parent
KEY = '⌃⌥⇧⌘E'
ASK = 'What do you not understand?'

def Go():
    "The Explain button, for a learner with no Hyper key. Hyper+E does the same."
    return Button('Explain', type='button', id='guide-go', cls='guide-go', aria_keyshortcuts='Control+Alt+Shift+Meta+E',
                  title=f'Ask the tutor to explain a part of this page. {KEY} (Caps+E): hold to talk, tap to type.')

def Box():
    "The one-line box. A tap of Hyper+E opens it; held, the key fills it with what you say."
    return Form(Input(type='text', name='said', id='guide-box', aria_label=ASK, placeholder="I don't get …", autocomplete='off', maxlength='300'),
                Button('Explain', type='submit', cls='small'), Span(cls='guide-heard mute', aria_live='polite'),
                id='guide-form', cls='guide-form', hidden=True)

def Strip():
    "The strip under the board: the tier, the step and its line, the sources, and the keys. board.js fills it, with text only."
    return Div(id='guide-strip', cls='guide-strip', hidden=True, aria_live='polite', role='status')

def Parts():
    return (Box(), Strip(), asset_css(_P/'guide.css'),
            asset_js(_P/'guide.js', data_ask=Routes.ask, data_figure=Routes.figure, data_cues=Routes.of(Routes.cues, vid='')))
