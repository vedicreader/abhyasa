"Your strengths and weak spots: each subject, the strong and the weak concepts with the reasons, and the ways you learn."
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import asset_css, DepthBar
from abhyasa.method import METHODS, LABELS, EXPLORE, posterior, mean, improving
from .cfg import Routes

_P = Path(__file__).parent
STATES = dict(strong='strong', learning='learning', fading='fading', weak='weak', gap='gap you named', unseen='not started')
PLURAL = dict(gap='gaps you named')
SAY_EXPLORE = dict(never='Never: always use my best way', sometimes='Sometimes (about one question in seven)', often='Often (about one in three)')

def assets(): return (asset_css(_P/'strengths.css'),)

def Subject(name, rows):
    "One subject: the count in each state, and the mean depth."
    n = {k: sum(u.state == k for _, u in rows) for k in STATES}
    seen = [u for _, u in rows if u.state != 'unseen']
    fl = round(sum(u.floor for u in seen) / len(seen)) if seen else 0
    return Li(A(name or 'general', href=f'{Routes.base}?subject={name}', cls='n'), DepthBar(fl),
              Span(', '.join(f'{n[k]} {PLURAL.get(k, STATES[k]) if n[k] > 1 else STATES[k]}' for k in ('strong', 'weak', 'fading', 'gap') if n[k]) or f"{len(rows)} not started", cls='mute'))

def Concept(c, u):
    "One concept with the reasons for its state."
    return Li(A(c.name, href=f'/c/{c.slug}', cls='n'), DepthBar(u.floor), Span(f'recall {u.recall:.0%}', cls='mute') if c.get('seen') else '',
              Ul(*[Li(r) for r in u.reasons], cls='plain why') if u.reasons else '', cls=f'st-{u.state}')

def Ways(st, subject='', prior=()):
    "Each way to learn with its count, best first: the best way, and a way that got better."
    ms = (st.get('methods') or {}).get(subject or '*') or {}
    if not ms: return P('After a few questions, this shows which ways work for you: code, maths, analogies, worked examples, pictures or plain words.', cls='mute')
    ps = {m: posterior(st, m, subject, prior) for m in METHODS}
    order = sorted(ms, key=lambda m: -mean(ps[m]))
    def row(m):
        a, b = ms[m]
        tag = 'Your best way.' if m == order[0] else 'Getting better.' if improving(st, m) else ''
        return Li(Span(LABELS[m], cls='n'), Span(f'{round(a)} of {round(a + b)}', cls='k'), Span(tag, cls='tag') if tag else '')
    return Ul(*map(row, order), cls='plain ways')

def Explore(v):
    "How often the tutor tries a new way."
    return Form(*[Label(Input(type='radio', name='explore', value=k, checked=v == k), Span(SAY_EXPLORE[k])) for k in EXPLORE],
                Span(id='explored', cls='mute'), hx_post=Routes.explore, hx_trigger='change', hx_target='#explored', cls='explore')
