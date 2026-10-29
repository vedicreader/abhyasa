"One setting row: the label and its help at the left, the control, the range and the default at the right. The Settings page and the Profile page use it."
from fasthtml.common import *
from abhyasa.settings import top

__all__ = ['row_id', 'shown', 'say', 'parse_value', 'Choice', 'SettingRow', 'RangeLine']

def row_id(r) -> str: return 'sr-' + r.name.replace('.', '-').replace('_', '-')

def shown(r, v):
    "The value `v` of row `r` as the control shows it: a share as a whole percent."
    return round(v * 100) if r.pct else v

def _num(r, v) -> str: return f'{round(v * 100)}%' if r.pct else f'{v:,}' if isinstance(v, int) and v >= 10_000 else f'{v:g}'

def unit(r, v) -> str:
    "The unit of row `r` for the value `v`, with the plural rule of `n_of`: `1 day`, `2 days`. A short unit (`min`, `s`, `MB`) stays as it is."
    u = r.unit
    return u[:-1] if v == 1 and len(u) > 2 and u.isalpha() and u.islower() and u.endswith('s') else u

def say(r, v) -> str:
    "The value `v` of row `r` in words: `12`, `33%`, `400,000 characters`, `1 day`, `on`."
    if r.kind == 'bool': return 'on' if v else 'off'
    if r.kind in ('choice', 'str'): return str(v) or 'none'
    return f'{_num(r, v)} {unit(r, v)}' if r.unit and not r.pct else _num(r, v)

def parse_value(r, s):
    "The value that a form sent for row `r`, before `settings.fit`. Raise `ValueError` for text that is not a number."
    if r.kind == 'bool': return str(s).lower() in ('1', 'true', 'on', 'yes')
    if r.kind in ('choice', 'str'): return str(s).strip()
    v = float(str(s).strip())
    return v / 100 if r.pct else int(round(v)) if r.kind == 'int' else v

def _step(r):
    if r.pct or r.kind == 'int': return 1
    return .05 if r.hi <= 1 else .1 if r.hi <= 10 else 1

def RangeLine(r, v, reset=None, saved=False, file=None, err=''):
    "The line under a control: the range and the default, `Use the default (x)` when the value is not the default, a note on a clamped value, and `Saved`."
    lo_hi = f'{_num(r, r.lo)} to {say(r, top(r))} · ' if r.kind in ('int', 'float') else ''
    use = A(f'Use the default ({say(r, r.dflt)})', href='#', cls='use', **reset) if reset and v != r.dflt else ''
    most = file is not None and file > top(r)
    clamp = (Span(f"Your file had {file:g}. The {'most' if most else 'least'} is {say(r, top(r) if most else r.lo)}, so abhyasa uses {say(r, v)}.", cls='no')
             if file is not None else '')
    return Div(Span(f'{lo_hi}default {say(r, r.dflt)}'), use, clamp, Span(err, cls='no', role='alert') if err else '',
               Span('Saved', cls='saved', role='status') if saved else '', cls='rng', id=f'{row_id(r)}-m')

def Choice(name, options, value, **kw):
    "A choice of 2 to 5 options as pills (`.modes-pick`). `options` is a list of `(value, label)`."
    return Div(*[Label(Input(type='radio', name=name, value=k, checked=k == value), t) for k, t in options], cls='modes-pick', role='radiogroup', **kw)

def _control(r, v, post):
    "The control of row `r` with value `v`. A change posts `name` and `value` to `post`, and the range line takes the reply."
    i, h = row_id(r), dict(hx_post=post, hx_vals={'name': r.name}, hx_target=f'#{row_id(r)}-m', hx_swap='outerHTML')
    if r.kind == 'bool':
        return Input(type='checkbox', checked=bool(v), id=f'{i}-c', cls='toggle', hx_trigger='change', hx_post=post, hx_target=h['hx_target'],
                     hx_swap='outerHTML', hx_vals=f'js:{{name: "{r.name}", value: event.target.checked ? 1 : 0}}')
    if r.kind == 'choice': return Form(Choice('value', [(c, c.capitalize()) for c in r.choices], v, aria_label=r.label), hx_trigger='change', **h)
    if r.kind == 'str':   # a text list, such as the source folders: one item on each line
        return Textarea(v, name='value', id=f'{i}-c', rows=3, spellcheck='false', autocomplete='off', aria_label=r.label, hx_trigger='change', **h)
    lo, hi, n = shown(r, r.lo), shown(r, top(r)), shown(r, v)
    box = Input(type='number', name='value', value=n, min=lo, max=hi, step=_step(r), id=f'{i}-c', inputmode='decimal', aria_label=r.label,
                hx_trigger='input changed delay:400ms, change', **h)
    if r.pct or r.name == 'learning.session_len':   # a slider where the feel matters more than the number; the box beside it shows the number
        return Div(Input(type='range', min=lo, max=hi, step=_step(r), value=n, aria_label=r.label, data_box=f'{i}-c', tabindex='-1'), box, cls='num slide')
    return Div(Button('−', type='button', cls='quiet step', data_step='-1', data_box=f'{i}-c', aria_label=f'Less: {r.label}'), box,
               Button('+', type='button', cls='quiet step', data_step='1', data_box=f'{i}-c', aria_label=f'More: {r.label}'), cls='num')

def SettingRow(r, v, post, reset=None, file=None, control=None, help=None):
    "One setting row. `reset` is the htmx attributes of `Use the default`, `file` a saved number that was out of range, `control` a control in place of the usual one."
    i = row_id(r)
    return Li(Div(Span(cls='dot' + (' on' if v != r.dflt else ''), id=f'{i}-dot'), Label(r.label, fr=f'{i}-c'), P(help or r.help, cls='help'), cls='lft'),
              Div(control if control is not None else _control(r, v, post), RangeLine(r, v, reset, file=file), cls='rgt'),
              cls='srow', id=i, data_find=f'{r.label} {help or r.help}'.lower())
