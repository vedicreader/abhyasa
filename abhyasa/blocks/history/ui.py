"Your learning: a quiet week of columns, what moved each week, and each past session with what moved and a way to continue."
import time
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import Md, DepthBar, asset_css, ago, Primary
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

def Continue(s, title, big=False, href=None):
    "The way back into an open session, one key away; `href` is where it goes when it is not the session page."
    href = href or Routes.of(Routes.page, sid=s['id'])
    if not big: return A(f'Continue: {title}', Kbd('⌥C'), href=href, id='continue', title='Continue where you stopped')
    n = len(s.get('log') or [])
    return Div(Span('Continue where you stopped', cls='lbl'),
               P(A(title, href=href), Span(f"  · {n} question{'s' if n != 1 else ''} done · {ago(s.get('updated'))}", cls='mute')),
               Div(Primary('Continue', href=href), cls='row'), cls='continue-card')

def Row(s, title, ms, href=None):
    "One past session: when, what, how it went, what moved, and what you can do next."
    log, open_ = s.get('log'), s.get('log') is not None and not s.get('ended')
    n, ok = (len(log), sum(r['correct'] for r in log)) if log is not None else (s.get('asked', 0), s.get('passed', 0))
    up = [m for m in ms if m['after'] > m['before']]
    mis = [x for m in ms for x in m['misconceptions']]
    missed = [m['concept'] for m in ms if m['passed'] < m['asked']]
    when = time.strftime('%H:%M', time.localtime(s.get('start') or s.get('updated') or 0))
    acts = [A('Continue', href=href or Routes.of(Routes.page, sid=s['id']), cls='btn small') if open_ else '',
            A('Review the misses', href=f"{Routes.start}?focus={missed[0]}", cls='btn small quiet') if missed else '',
            A('Open', href=Routes.of(Routes.one, sid=s['id']), cls='btn small quiet') if log else '']
    return Li(Div(Span(when, cls='t'), A(title, href=Routes.of(Routes.one, sid=s['id']) if log else None, cls='tt'),
                  Span(f"  {ok} of {n} passed" + (' · open' if open_ else ''), cls='mute'), cls='rh'),
              P(*[x for m in up for x in (Move(m), '; ')][:-1], cls='moves') if up else '',
              P('Misconceptions found: ', '; '.join(mis), cls='mute mis') if mis else '',
              Div(*acts, cls='acts') if any(acts) else '', cls='run' + (' open' if open_ else ''))

def Runs(groups):
    "The sessions, grouped by day, newest first."
    if not groups: return P('No sessions yet. Start one on Today, or start a journey.', cls='mute')
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

def Question(r):
    return Section(Span(f"{r['name']} · {DEPTHS[r['depth']]} · {OUTCOME.get(r['outcome'], r['outcome'])}", DepthBar(r.get('floor', 0), asked=r['depth']), cls='lbl'),
                   Md(r['question'], cls='q'), Ol(*[Turn(t) for t in (r.get('turns') or [])[1:]], cls='turns'), cls='pq')
