"""The shared parts of the two editors, the talk editor and the walk path editor: the Undo bar, the history list, the list of rows and a live field.

`edit.js` does the work in the browser: the keys of the list, the drag by the grip, one open row at a time, the post of a live
field to its row, ⌘Z, and the quiet Undo bar after `EDIT_BAR_SECS`. `edit.css` is their style. An editor page loads
`edit_assets()`; `HDRS` does not. The history in the vault, the Undo of a walk path and the rewrite are in `abhyasa.edit`.

An editor page has one `UndoBar()` (empty) in the page. After each change, the route sends `UndoBar(said, undo, history, step)`
with its answer, and htmx puts its content in the bar out of band, so the bar says what changed."""
import json
from pathlib import Path
from fasthtml.common import *
from abhyasa.core.ui import asset_css, asset_js, Quiet, Empty, ago

__all__ = ['EDIT_BAR_SECS', 'LIVE', 'EDIT_KEYS', 'edit_keys', 'edit_assets', 'UndoBar', 'HistoryList', 'EditRow', 'EditList', 'Live']

_here = Path(__file__).parent
EDIT_BAR_SECS = 8   # seconds that the Undo bar of an editor stays bright after a change; then it goes quiet, and Undo still works
LIVE = 'input changed delay:600ms, blur'   # a live field saves when you stop typing for 600 ms, or leave it

#: the keys of an editor list, as (keys, action); the task that binds a list adds them to `KEYS` in `keys.py` with `edit_keys`
EDIT_KEYS = [('W', 'Move the focus to the row above'), ('S', 'Move the focus to the row below'), ('⇧W ⇧S', 'Move the row up or down'),
             ('E', 'Edit the row'), ('esc', 'Close the open row'), ('A', 'Add a row'), ('D', 'Duplicate the row'), ('X', 'Remove the row'),
             ('R', 'Rewrite the row with an instruction'), ('P', 'Split the row in two'), ('M', 'Merge the row with the next row'),
             ('⌘Z', 'Undo the last change. In a text box, ⌘Z undoes the typing')]

def edit_keys(group:str, keys=None) -> list:
    "The rows of `EDIT_KEYS` for the keys table, in the group `group`; only the keys in `keys` when it is given."
    return [(group, k, a) for k, a in EDIT_KEYS if keys is None or k in keys]

def edit_assets() -> tuple:
    "The style and the script of the editors, for the head of an editor page."
    return asset_css(_here/'edit.css'), asset_js(_here/'edit.js')

def UndoBar(said:str='', undo:str='', history:str='', step:str='', oob:bool=True, **kw):
    """The Undo bar of an editor: what changed in one sentence, Undo (⌘Z) and a link to the History. With no `said`, the empty bar
    for the page. Undo posts `step` (the id of the change), so an old bar does nothing. With `oob`, htmx puts the content in the bar
    of the page, and the live region says it. `kw` goes to the Undo button (for example `hx_target`)."""
    c = (Span(said, cls='said'), Button('Undo', ' ', Kbd('⌘Z'), type='button', hx_post=undo, **({'hx_vals': json.dumps(dict(step=step))} if step else {}), **kw),
         A('History', href=history, cls='hist')) if said else ()
    return Div(*c, id='undo-bar', cls='undo-bar', role='status', aria_live='polite', data_secs=str(EDIT_BAR_SECS), **({'hx_swap_oob': 'innerHTML'} if oob else {}))

def HistoryList(rows, restore:str):
    """The history of one talk or one walk, newest first: the time, what changed, who ("you" or "tutor"), and "Restore this version".
    Restore posts the `id` of the change to `restore`; the version is the one before that change."""
    if not rows: return Empty('No changes yet.')
    return Ol(*[Li(Span(ago(r['at']), cls='at'), Span(r['what'], cls='what'), Span(r['who'], cls='who'),
                   Quiet('Restore this version', type='button', hx_post=restore, hx_vals=json.dumps(dict(id=r['id']))), cls='edit-line') for r in rows],
              cls='edit-history', aria_label='Changes, newest first')

def EditRow(i:int, r, n:int):
    """Row `i` of `n` in an editor list. `r` has `id`, `title`, and can have `line` (the short line), `post` (the route of the row:
    live fields and moves post to it), `body` (the fields of the open row), `acts` (its buttons, each with `data_key` for its key),
    `open`, `fresh` (a new row: its first field gets the focus) and `cls`. Move up and Move down are the touch way to move."""
    r = AttrDict(r)
    moves = (Quiet('Move up', type='button', data_move=str(i - 1), disabled=i == 0), Quiet('Move down', type='button', data_move=str(i + 1), disabled=i == n - 1))
    return Li(Span(cls='grip', title='Drag to move', aria_hidden='true'), Span(str(i + 1), cls='no'),
              Div(Span(r.title, cls='ttl'), Span(r.line, cls='line') if r.get('line') else '', cls='head'),
              Details(Summary('Edit', ' ', Kbd('E'), data_key='E'), Div(*r.get('body', ()), Div(*r.get('acts', ()), *moves, cls='row-acts'), cls='fields'),
                      open=bool(r.get('open')), cls='edit-open'),
              tabindex='0', data_id=r.id, data_i=str(i), cls=f"edit-row {r.get('cls', '')}".strip(),
              **({'data_post': r.post} if r.get('post') else {}), **({'data_fresh': '1'} if r.get('fresh') else {}))

def EditList(rows, cls:str, add=(), **kw):
    """The list of an editor: one `EditRow` for each row of `rows`, then the `add` buttons (each with `data_key`, such as `A`) in the
    last item. `edit.js` reads `data-edit`. Give the list an `id` in `kw` when htmx swaps it."""
    rows = list(rows)
    return Ol(*[EditRow(i, r, len(rows)) for i, r in enumerate(rows)], *([Li(*add, cls='edit-add', role='none')] if add else []),
              cls=f'edit-list {cls}', data_edit='1', **kw)

def Live(name:str, el, post:str=None):
    """Make the field `el` a live field named `name`: it posts when you stop typing for 600 ms, or leave it. The post goes to `post`,
    else to the `data-post` of its row (`edit.js`). It posts `act=set` and its own value only; the answer swaps nothing but the
    Undo bar, so the text that you type stays."""
    el.attrs.update({'name': name, 'hx-post': post or '', 'hx-trigger': LIVE, 'hx-swap': 'none', 'hx-vals': json.dumps(dict(act='set')), 'data-live': '1'})
    return el
