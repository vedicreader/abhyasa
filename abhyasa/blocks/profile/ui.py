"What abhyasa knows about you: every field in the open, each change with who made it and why, and a short first conversation."
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import asset_css, ago, SettingRow, row_id
from abhyasa.settings import val, SETTINGS
from abhyasa.profile import LABELS, LIST_FIELDS, EXAMPLES, PACES, ONBOARD_QS, calibration_text
from .cfg import Routes

_P = Path(__file__).parent
WHO = dict(you='You', onboarding='Your first conversation', tutor='The tutor')

def css(): return asset_css(_P/'profile.css')

def Box(k, p, note='', rows=2):
    v = p[k]
    return Div(Label(LABELS[k], Span(note, cls='note') if note else '', fr=f'pf-{k}'),
               Textarea('\n'.join(v) if isinstance(v, list) else v, name=k, id=f'pf-{k}', rows=rows, data_mic='1'))

def Form_(p):
    "Each field, open to change. A list field takes one item on each line."
    ex = Div(Label(LABELS['examples']), Div(*[Label(Input(type='checkbox', name='examples', value=e, checked=e in p.examples), Span(e)) for e in EXAMPLES],
                                            cls='chips'))
    return Form(Box('background', p, 'what you do and know; one on each line'), Box('goals', p, 'what you want to learn, and why'),
                Box('interests', p), ex, Box('confuses', p, 'the tutor adds to this from your answers'), Box('notes', p, 'anything else', rows=2),
                Div(Button('Save ', Kbd('⌥S'), cls='go', data_wait='Saving…'), Span(id='saved', cls='mute'), cls='row'),
                hx_post=Routes.base, hx_target='#saved', cls='profile')

def reset_attrs(r): return dict(hx_post=Routes.setting_default, hx_vals={'name': r.name}, hx_target=f'#{row_id(r)}', hx_swap='outerHTML')

def LearnRow(r, p):
    "Pace, questions in a session or new ways: the same value as on the Settings page. It saves when it changes."
    return SettingRow(r, p.get(r.key, r.dflt), Routes.setting, reset_attrs(r))

def Learning(p):
    "The three values of your profile that the Settings page shows too."
    return Ul(*[LearnRow(r, p) for r in SETTINGS.values() if r.group == 'learning'], cls='plain srows', id='learning')

def said(c):
    "One change in words."
    f = LABELS.get(c['field'], c['field'])
    if c['field'] in LIST_FIELDS:
        add = [x for x in c['new'] if x not in (c['old'] or [])]
        rem = [x for x in c['old'] or [] if x not in c['new']]
        return f"{f}: " + '; '.join([*([f"added “{', '.join(add)}”"] if add else []), *([f"took out “{', '.join(rem)}”"] if rem else [])]) or f'{f}: changed'
    return f"{f}: {c['old'] or 'empty'} → {c['new'] or 'empty'}"

def Changes(cs):
    "Each change, newest first, with who made it and why, and an undo."
    if not cs: return P('No changes yet.', cls='mute')
    def row(c):
        return Li(Div(Span(WHO.get(c['by'], c['by']), cls='who'), Span(f"  {ago(c['at'])}", cls='mute'), cls='ch-head'), P(said(c), cls='what'),
                  P('Why: ', c['why'], cls='mute why-line') if c.get('why') else '',
                  Form(Input(type='hidden', name='id', value=c['id']) if c.get('id') else Input(type='hidden', name='at', value=repr(c['at'])),
                       Button('Undo', cls='small quiet'), action=Routes.undo, method='post'))
    return Ul(*map(row, cs[:val('lists.changes')]), cls='plain changes')

def Calibration(r):
    "How often you were right when you felt sure, and when you felt unsure."
    t = calibration_text(r)
    return P(t, cls='calib') if t else P('After five answers with a “Sure?” choice, this shows how often you are right when you feel sure.', cls='mute')

def Onboard():
    "The first conversation: four questions in the tutor's voice, each answered by voice or text."
    qs = [Li(Span('abhyasa asks', cls='lbl'), P(q, cls='ask'), Textarea(name=k, id=f'ob-{k}', rows=2, data_mic='1', placeholder=ex, aria_label=q))
          for k, q, ex in ONBOARD_QS]
    return Form(Ol(*qs, cls='onboard'),
                Div(Button('Done ', Kbd('⌥S'), cls='go', data_wait='Reading what you said…'), A('Not now', href='/', cls='btn quiet'), cls='row'),
                action=Routes.start, method='post')
