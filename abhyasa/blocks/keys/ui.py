"The keyboard shortcuts page: each group with its keys, large and plain."
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import asset_css

_P = Path(__file__).parent
WHERE = {'Everywhere': 'On every page.', 'Session': 'While you answer a question.', 'Concept': 'On a concept page.',
         'Walk': 'On a step of a walk.', 'Side pane': 'While a side walk is open beside the paper.',
         'Talk plan': 'In the editor of a talk.', 'Talk': 'In the presenter window of a talk.',
         'Graph': 'When the graph has the focus: click it first.', 'Mac app': 'In the menus of Abhyasa.app.'}

def css(): return asset_css(_P/'keys.css')

def Group(name, rows):
    "One group: its heading, where it works, and a row for each key."
    return Section(H2(name), P(WHERE.get(name, ''), cls='mute'),
                   Dl(*[x for _, k, a in rows for x in (Dt(Kbd(k)), Dd(a))], cls='keys'))
