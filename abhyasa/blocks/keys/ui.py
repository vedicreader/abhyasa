"The keyboard shortcuts page: each group with its keys, large and plain."
import re
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import asset_css, asset_js
from abhyasa.core.keys import short, page_group, float_rows

_P = Path(__file__).parent
WHERE = {'Everywhere': 'On every page.', 'Session': 'While you answer a question.', 'Concept': 'On a concept page.',
         'Walk': 'On a step of a walk.', 'Side pane': 'While a side walk is open beside the paper.',
         'Talk plan': 'In the editor of a talk.', 'Walk path': 'In the editor of a walk path.', 'Talk': 'In the presenter window of a talk.',
         'Graph': 'When the graph has the focus: click it first.', 'Mac app': 'In the menus of Abhyasa.app.'}

def css(): return asset_css(_P/'keys.css')

def Group(name, rows):
    "One group: its heading, where it works, and a row for each key."
    return Section(H2(name), P(WHERE.get(name, ''), cls='mute'),
                   Dl(*[x for _, k, a in rows for x in (Dt(Kbd(k)), Dd(a))], cls='keys'))

# --- the Keys panel: a quiet pill at the bottom left of each page ---------------------------------------------------------
GUIDE_LINE = 'Explain: press Caps+E on any page, and the tutor draws on it.'
TALK_LINE = 'Hold Caps+E to talk to the guide. ⌥D types what you say into a box.'
MAC_GUIDE = 'Use the guide over other apps…'
GUIDE_LINK = 'abhyasa://guide/start'   # Abhyasa.app shows the first-use sheet of its screen guide (WebController.swift)
SHOWN = {'⌃⌥⇧⌘E': 'Caps+E'}          # the name of a key in the panel, when its symbols are long
LABEL = {'⌃⌥⇧⌘E': 'Explain this'}    # the panel button for the guide: the line under the list says how to talk
ACTS = {'⌃⌥⇧⌘E': 'explain', '⌥D': 'dictate', '/': 'search'}

def act(g, k) -> dict:
    "The data attributes that tell keys_float.js what a row does: a named act, an ⌥ key, or a plain key on the graph."
    if k in ACTS: return dict(data_act=ACTS[k])
    if m := re.fullmatch(r'⌥([A-Z0-9])', k): return dict(data_code=('Digit' if m[1].isdigit() else 'Key') + m[1], data_alt='1')
    if g == 'Graph' and re.fullmatch('[A-Z]', k): return dict(data_code='Key' + k, data_on='#graph')
    return {}

def Row(g, k, a):
    "One key of the panel: a button that does what the key does, with the key at its right."
    return Li(Button(Span(LABEL.get(k) or short(a)), Kbd(SHOWN.get(k, k), cls='kf-key'), type='button', cls='kf-do', title=f'{a} ({k})', **act(g, k)))

def Float(path:str, base:str, set_url:str):
    "The pill and its panel, closed in the HTML: keys_float.js opens it the first time and when you open it. Nothing takes the focus on load."
    g = page_group(path)
    return Div(Button('Keys', type='button', id='kf-pill', cls='kf-pill', aria_expanded='false', aria_controls='kf-panel',
                      title='The most useful keys of this page. ⌥⇧F opens it too.'),
               Div(P('Keys on this page' if g == 'Everywhere' else f'Keys: {g.lower()}', cls='kf-head'),
                   Ul(*[Row(*r) for r in float_rows(path)], cls='kf-rows'),
                   P(GUIDE_LINE, cls='kf-line'), P(TALK_LINE, cls='kf-line mute'),
                   A(MAC_GUIDE, href=GUIDE_LINK, id='kf-mac', cls='kf-mac', hidden=True),
                   Div(A('All keys ', Kbd('?'), href=base, cls='kf-all'), Button('Hide this', type='button', id='kf-hide', cls='kf-quiet', data_url=set_url),
                       Button('Close', type='button', id='kf-close', cls='kf-quiet', title='Esc'), cls='kf-foot'),
                   id='kf-panel', cls='kf-panel', role='region', aria_label='Keys on this page', hidden=True),
               asset_css(_P/'keys_float.css'), asset_js(_P/'keys_float.js'), id='kf', cls='kf', data_group=g)
