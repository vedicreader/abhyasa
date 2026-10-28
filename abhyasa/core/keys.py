"""Every keyboard shortcut of abhyasa in one table: the Keyboard shortcuts page shows it, and Sanketa reads it as a pack.

The keys work in `core.js` and in each block's js; `tests/test_keys.py` checks that each ⌥ key here is one that the js binds."""
import json, os
from pathlib import Path

__all__ = ['KEYS', 'MENU', 'BUNDLE', 'sanketa_pack', 'write_sanketa_pack']

BUNDLE = 'dev.vedicreader.abhyasa'
#: (group, keys, action), in the order the page shows them; the keys are in Sanketa's key style
KEYS = [
    ('Everywhere', '⌥S', 'Press the main button'),
    ('Everywhere', '⌥T', 'Go to Today'),
    ('Everywhere', '⌥C', 'Continue where you stopped'),
    ('Everywhere', '⌥G', 'Your strengths and weak spots'),
    ('Everywhere', '⌥F or ?', 'Show the keyboard shortcuts'),
    ('Everywhere', '⌥D', 'Dictate into the box with focus'),
    ('Everywhere', '/', 'Search what you learned'),
    ('Everywhere', '⌘↩', 'Send the form from a box'),
    ('Everywhere', 'esc', 'Go up one level'),
    ('Session', '⌥S', 'Send, or go to the next question'),
    ('Session', '⌥W', 'Ask for a hint'),
    ('Session', '⌥X', "I don't know, or teach me"),
    ('Session', '⌥A', 'Teach it in another way'),
    ('Session', '⌥1–⌥5', 'How sure you are'),
    ('Session', '1–4', 'Pick option 1 to 4 on a choice question'),
    ('Session', '⌥↑ ⌥↓', 'Read an earlier question'),
    ('Concept', '⌥E', 'Show me a demo'),
    ('Walk', '⌥S', 'Send the open check, or run the tests. Once the check closes, go to the next idea'),
    ('Walk', '⌥W', 'Ask for a hint'),
    ('Walk', '⌘↩', 'Send the answer, or run the tests'),
    ('Walk', '⌥V', 'Keep the state of the demo'),
    ('Walk', '⌥B', 'Open beside: learn a missing idea in the side pane'),
    ('Side pane', '⌥Z', 'Back to the paper: close the side pane'),
    ('Side pane', 'esc', 'Close the side pane'),
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

def sanketa_pack() -> str:
    "The keys as a Sanketa pack: for Abhyasa.app, and for a browser tab whose title ends in ` · abhyasa`."
    q = json.dumps   # a JSON string is a valid TOML basic string
    out = [_MARK, 'id = "abhyasa"', 'name = "abhyasa"', f'apps = [{q(BUNDLE)}]',
           "titles = ['^.+ · abhyasa(?: [-–] .*)?$']", '']
    for g, k, a in KEYS: out += ['[[keys]]', f'keys = {q(k)}', f'action = {q(a)}', f'group = {q(g)}', '']
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
