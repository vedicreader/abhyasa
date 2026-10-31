"You → Progress: a quiet week of columns, what moved each week, and each past session with what moved and a way to continue."
import time
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import n_of, meta, Md, DepthBar, asset_css, ago, Primary, Onward, Said
from abhyasa.model import DEPTHS
from .cfg import Routes

_P = Path(__file__).parent
OUTCOME = {'solid': 'Solid', 'fragile': 'Right, but shaky', 'misconception': 'A misconception', 'gap': 'A gap'}

def css(): return asset_css(_P/'history.css')

def Week(days):
    "Seven columns, one for each day, as high as the questions answered. An empty day is only empty."
    top = max([n for _, n in days] + [1])
    col = lambda d, n: Div(Span(str(n) if n else '', cls='n'), I(style=f"height:{max(3, 46 * n // top) if n else 0}px"), Span(d, cls='d'),
                           cls='col' + (' none' if not n else ''), title=f'{n} questions')
    return Div(*[col(d, n) for d, n in days], cls='week', role='img', aria_label='Questions answered on each of the last seven days')

def Move(m):
    return Span(A(m['name'], href=f"/c/{m['concept']}"), f" {DEPTHS[m['before']]} → {DEPTHS[m['after']]}", cls='mv')

def Continue(title, href, big=False, done='', at=0):
    "The way back to the place that you used last, one key away. `done` says what was done there; `at` is the time that you used it."
    if not big: return A(f'Continue: {title}', Kbd('⌥C'), href=href, id='continue', title='Continue where you stopped', data_part='continue', data_act='continue')
    return Div(Span('Continue where you stopped', cls='lbl'),
               P(A(title, href=href), Span(f"  · {done} · {ago(at)}", cls='mute')),
               Div(Primary('Continue', href=href, rank=1, data_act='continue'), cls='row'), cls='continue-card', data_part='continue-card')

def Row(s, title, ms, href=None, lead=False):
    """One past session: when, what, how it went, what moved, and what you can do next. The head is a fold: it opens the session in place.
    Only the `lead` row (the newest open session) has the Continue button; an older open one has a quiet `Continue →` link."""
    log, open_ = s.get('log'), s.get('log') is not None and not s.get('ended')
    n, ok = (len(log), sum(r['correct'] for r in log)) if log is not None else (s.get('asked', 0), s.get('passed', 0))
    up = [m for m in ms if m['after'] > m['before']]
    mis = [x for m in ms for x in m['misconceptions']]
    missed = [m['concept'] for m in ms if m['passed'] < m['asked']]
    when = time.strftime('%H:%M', time.localtime(s.get('start') or s.get('updated') or 0))
    go = href or Routes.of(Routes.page, sid=s['id'])
    acts = [A('Review the misses', href=f"{Routes.start}?focus={missed[0]}", cls='btn small quiet') if missed else '',   # first, so it lines up on each row
            (A('Continue', href=go, cls='btn small') if lead else Onward('Continue', go)) if open_ else '']
    head = Summary(Span(when, cls='t'), Span(title, cls='tt'), Span('  ' + meta(f"{ok} of {n} passed" if n else 'no answers yet', 'open' if open_ else ''), cls='mute'), cls='rh')
    fold = Details(head, Div(cls='fold'), hx_get=Routes.of(Routes.one, sid=s['id']), hx_trigger='toggle once', hx_target='find .fold', hx_swap='innerHTML', cls='past-fold') if log else Div(*head.children, cls='rh')
    return Li(fold, P(*[x for m in up for x in (Move(m), '; ')][:-1], cls='moves') if up else '',
              P('Misconceptions found: ', '; '.join(mis), cls='mute mis') if mis else '',
              Div(*acts, cls='acts') if any(acts) else '', cls='run' + (' open' if open_ else ''), id=f"s-{s['id']}")

def Runs(groups):
    "The sessions, grouped by day, newest first."
    if not groups: return P('No sessions yet. Start one on Today, or start a walk.', cls='mute')
    return Div(*[Div(H2(day), Ul(*rows, cls='plain runs')) for day, rows in groups], cls='days')

def Learned(weeks):
    "For each week: the concepts that moved up, and the depth each one reached."
    if not weeks: return P('Nothing has moved up yet. Each concept that you learn shows here.', cls='mute')
    return Ul(*[Li(Span(w, cls='wk'), P(*[x for m in ms for x in (Move(m), ' · ')][:-1], cls='moves')) for w, ms in weeks], cls='plain learned')

def Turn(t):
    "One turn of a past question, compact."
    if t['who'] == 'you':
        return Li(Span('You' + (f" · {t['confidence']}% sure" if t.get('confidence') is not None else ''), cls='lbl'), Md(t['text'], cls='said') if t.get('text') else P('No answer.', cls='said'),
                  Div(Span('Thinking: ', cls='k'), Md(t['thinking']), cls='mute') if t.get('thinking') else '', cls='you')
    lbl = dict(nudge='Not yet', hint='Hint', close=OUTCOME.get(t.get('outcome'), 'Closed')).get(t.get('kind'), 'Tutor')
    return Li(Span(lbl, cls='lbl'), Md(t['text']) if t.get('text') else '', Div(Span('Lesson', cls='lbl'), Md(t['lesson'])) if t.get('lesson') else '', cls='tutor')

def Question(r, a=None):
    "One past question with its turns, and what you said about it (attempt `a`), if anything."
    return Section(Span(f"{r['name']} · {DEPTHS[r['depth']]} · {OUTCOME.get(r['outcome'], r['outcome'])}", DepthBar(r.get('floor', 0), asked=r['depth']), cls='lbl'),
                   Md(r['question'], cls='q'), Ol(*[Turn(t) for t in (r.get('turns') or [])[1:]], cls='turns'), *(Said(a) if a else []), cls='pq')
