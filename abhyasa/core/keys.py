"""Every keyboard shortcut of abhyasa in one table: the Keyboard shortcuts page shows it, and Sanketa reads it as a pack.

The keys work in `core.js` and in each block's js; `tests/test_keys.py` checks that each ⌥ key here is one that the js binds."""
import json, os, re
from pathlib import Path
from abhyasa.core.stage import PLAN_KEYS, TALK_KEYS
from abhyasa.core.edit import edit_keys   # the editor keys: the talk editor and the walk path editor add their group with it

__all__ = ['edit_keys', 'KEYS', 'MENU', 'SHORT', 'short', 'pack_keys', 'FLOAT', 'page_group', 'float_rows', 'has_float', 'BUNDLE', 'sanketa_pack', 'write_sanketa_pack']

BUNDLE = 'dev.vedicreader.abhyasa'
#: (group, keys, action), in the order the page shows them; the keys are in Sanketa's key style
KEYS = [
    ('Everywhere', '⌥S', 'Press the main button'),
    ('Everywhere', '⌥T', 'Go to Today'),
    ('Everywhere', '⌥C', 'Continue where you stopped'),
    ('Everywhere', '⌥Q', 'Go to Learn'),
    ('Everywhere', '⌥R', 'Go to Library'),
    ('Everywhere', '⌥G', 'Go to You'),
    ('Everywhere', '⌥1–⌥3', 'Pick a sub-tab'),
    ('Everywhere', '⌥F or ?', 'Show the keyboard shortcuts'),
    ('Everywhere', '⌥⇧F', 'Open or close the Keys panel'),
    ('Everywhere', '⌥D', 'Speak into the text box'),
    ('Everywhere', '/', 'Search what you learned'),
    ('Everywhere', '⌘↩', 'Send the form from a box'),
    ('Everywhere', 'esc', 'Go up one level'),
    ('Settings', '⌥1–⌥7', 'Pick a tab'),
    ('Settings', '← →', 'Go to the tab before or after, from a tab'),
    ('Session', '⌥S', 'Send, or go to the next question'),
    ('Session', '⌥W', 'Ask for a hint'),
    ('Session', '⌥X', "I don't know, or teach me"),
    ('Session', '⌥A', 'Teach it in another way'),
    ('Session', '⌥1–⌥5', 'How sure you are'),
    ('Session', '1–4', 'Pick option 1 to 4 on a choice question'),
    ('Session', '⌥↑ ⌥↓', 'Read an earlier question'),
    ('Concept', '⌥E', 'Show me a demo'),
    ('Concepts', '⌘Z', 'Undo the last change that you made by hand'),
    ('Walk', '⌥S', 'Send the open check, or run the tests. Once the check closes, go to the next idea'),
    ('Walk', '⌥W', 'Ask for a hint'),
    ('Walk', '⌘↩', 'Send the answer, or run the tests'),
    ('Walk', '⌥V', 'Keep the state of the demo'),
    ('Walk', '⌥B', 'Learn a missing idea in a side walk'),
    ('Side pane', '⌥Z', 'Back to the paper: close the side pane'),
    ('Guide', '⌃⌥⇧⌘E', 'Explain this: hold to talk, tap to type (Caps+E)'),
    ('Guide', 'A', 'Say and draw the step again'),
    ('Guide', 'S', 'Go back one step'),
    ('Guide', 'D', 'Go to the next step'),
    ('Guide', 'esc', 'Stop the board'),
    ('Side pane', 'esc', 'Close the side pane'),
    *PLAN_KEYS,
    ('Change the walk', 'W', 'Move the focus to the idea above'), ('Change the walk', 'S', 'Move the focus to the idea below'),
    ('Change the walk', '⇧W ⇧S', 'Move the idea up or down'), ('Change the walk', 'E', 'Edit the idea'), ('Change the walk', 'A', 'Add an idea after the idea'),
    ('Change the walk', 'P', 'Split the idea into smaller ideas'), ('Change the walk', 'M', 'Merge the idea with the next idea'),
    ('Change the walk', 'X', 'Remove the idea. Undo gives it back'), ('Change the walk', 'R', 'Ask the tutor to rewrite the note and the check question'),
    ('Change the walk', '⌘Z', 'Undo the last change. In a text box, ⌘Z undoes the typing'), ('Change the walk', '⌥S', 'Continue the walk'),
    *TALK_KEYS,
    ('Graph', '1–4', 'Layout: free, path, rings, groups'),
    ('Graph', 'S', 'Find a concept'),
    ('Graph', 'E', 'Focus on the concept'),
    ('Graph', 'F', 'Fit the graph'),
    ('Graph', 'R', 'Lay out again'),
    ('Graph', 'space', 'Freeze or unfreeze'),
    ('Graph', 'W', 'Change the labels'),
    ('Graph', 'D', 'Show only what is due'),
    ('Graph', 'esc', 'Clear the focus'),
]
#: the menu keys of Abhyasa.app; Sanketa reads menus by itself, so these are on the page only
MENU = [('Mac app', '⌘N', 'New session'), ('Mac app', '⌘[', 'Back'), ('Mac app', '⌘]', 'Forward'),
        ('Mac app', '⇧⌘H', 'Today'), ('Mac app', '⌘F', 'Search')]
_MARK = '# Written by abhyasa from abhyasa/core/keys.py. abhyasa writes it again when it starts. Delete this line to keep your edits.'

#: the short label of each action that has more than six words: Sanketa's panel and the Keys panel are narrow. The page shows the long one.
SHORT = {
    'Go to the tab before or after, from a tab': 'Tab before or after',
    'Send, or go to the next question': 'Send, or next question',
    'Pick option 1 to 4 on a choice question': 'Pick option 1 to 4',
    'Undo the last change that you made by hand': 'Undo your last change',
    'Send the open check, or run the tests. Once the check closes, go to the next idea': 'Send, run tests, or next idea',
    'Send the answer, or run the tests': 'Send the answer, or run tests',
    'Learn a missing idea in a side walk': 'Side walk for a missing idea',
    'Back to the paper: close the side pane': 'Close the side pane',
    'Explain this: hold to talk, tap to type (Caps+E)': 'Explain this. Hold to talk',
    'Move the focus to the slide above': 'Focus the slide above', 'Move the focus to the slide below': 'Focus the slide below',
    'Remove the slide. Undo gives it back': 'Remove the slide', 'Ask the tutor to rewrite the slide': 'Tutor rewrites the slide',
    'Undo the last change. In a text box, ⌘Z undoes the typing': 'Undo the last change',
    'Move the focus to the idea above': 'Focus the idea above', 'Move the focus to the idea below': 'Focus the idea below',
    'Merge the idea with the next idea': 'Merge with the next idea', 'Remove the idea. Undo gives it back': 'Remove the idea',
    'Ask the tutor to rewrite the note and the check question': 'Tutor rewrites note and check',
    'Ask the room, or close the question': 'Ask the room, or close', 'Show the result and the right answer': 'Show the result and answer',
    'The main button: start the talk, ask the room, vote again, end the talk': 'Press the main button',
    'Go into the demo. Esc comes out': 'Go into the demo', 'Go to a slide: G, then its number': 'G, then a slide number',
    'With no phones: the option that most hands chose': 'Option that most hands chose',
    'In the audience window: fill the screen': 'Fill the screen (audience window)',
    'Learn a missing idea in a side walk, next to the slide': 'Side walk for a missing idea',
    'Back to the paper: close the side pane, and the slide grows back': 'Close the side pane',
    'Close the open question, the demo focus or the side pane. It never ends the talk': 'Close the question, demo or pane',
}

def short(a:str) -> str:
    "The label of action `a` in six words or fewer."
    return SHORT.get(a, a)

def pack_keys(k:str) -> str:
    "Key text `k` in Sanketa's key style: ` / ` between choices, and a plain letter in lower case (`A` is shift-a for Sanketa)."
    k = k.replace(' or ', ' / ')
    if re.fullmatch(r'[A-Z]', k): return k.lower()
    if ' ' in k and '/' not in k and k != 'space': return ' / '.join(k.split())   # `← →` and `⇧W ⇧S` are choices, not a sequence
    return k

#: the rows of the Keys panel: three on every page, then the rows of the group of the page, then Continue while there is room
FLOAT_TOP = [('Guide', '⌃⌥⇧⌘E'), ('Everywhere', '⌥D'), ('Everywhere', '/')]
FLOAT = {'Everywhere': [('Everywhere', '⌥S'), ('Everywhere', '⌥C')],
         'Session': [('Session', '⌥S'), ('Session', '⌥W'), ('Session', '⌥X'), ('Session', '⌥A')],
         'Walk': [('Walk', '⌥S'), ('Walk', '⌥W'), ('Walk', '⌥B')],
         'Concept': [('Concept', '⌥E'), ('Everywhere', '⌥C')],
         'Graph': [('Graph', 'S'), ('Graph', 'F'), ('Graph', 'R')],
         'Change the walk': [('Change the walk', '⌥S')], 'Talk plan': [('Talk plan', '⌥S')]}
FLOAT_MAX = 7

def page_group(path:str) -> str:
    "The group of keys for the page at `path`; `Everywhere` for a page with no keys of its own."
    for pre, g in (('/s/', 'Session'), ('/c/', 'Concept'), ('/graph', 'Graph'), ('/settings', 'Settings'), ('/concepts', 'Concepts')):
        if path.startswith(pre): return g
    if re.fullmatch(r'/w/[^/]+/edit/?', path): return 'Change the walk'
    if path.startswith('/w/'): return 'Walk'
    if re.fullmatch(r'/t/[^/]+/?', path): return 'Talk plan'
    return 'Everywhere'

def has_float(path:str) -> bool:
    "Whether the page at `path` has the Keys panel: not the presenter and audience windows of a talk, which a room can see."
    return not re.fullmatch(r'/t/[^/]+/(present|audience)/?', path)

def float_rows(path:str) -> list:
    "The (group, keys, action) rows of the Keys panel on the page at `path`: at most `FLOAT_MAX`, each key once."
    rows, seen = {(g, k): (g, k, a) for g, k, a in KEYS}, set()
    out = []
    for gk in [*FLOAT_TOP, *FLOAT.get(page_group(path), []), ('Everywhere', '⌥C')]:
        if gk[1] in seen or len(out) >= FLOAT_MAX: continue
        seen.add(gk[1]); out.append(rows[gk])
    return out

def sanketa_pack() -> str:
    "The keys as a Sanketa pack: for Abhyasa.app, and for a browser tab whose title ends in ` · abhyasa`."
    q = json.dumps   # a JSON string is a valid TOML basic string
    out = [_MARK, 'id = "abhyasa"', 'name = "abhyasa"', f'apps = [{q(BUNDLE)}]',
           "titles = ['^.+ · abhyasa(?: [-–] .*)?$']", '']
    for g, k, a in KEYS: out += ['[[keys]]', f'keys = {q(pack_keys(k))}', f'action = {q(short(a))}', f'group = {q(g)}', '']
    return '\n'.join(out)

def write_sanketa_pack(folder=None) -> Path|None:
    "Write the pack to Sanketa's packs folder, when Sanketa is set up; never over a pack without the abhyasa line. Return the path."
    d = Path(folder or os.getenv('SANKETA_PACKS') or Path.home()/'.config/sanketa/packs')
    if not d.parent.exists() and folder is None: return None   # no Sanketa on this Mac
    p, text = d/'abhyasa.toml', sanketa_pack()
    if p.exists():
        old = p.read_text(errors='replace')
        if old == text: return p
        if not old.startswith(_MARK): return None   # your own pack: keep it
    d.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p
