"The home page, in order of weight: `today_top` (continue), `today_next` (the review line), `today` (your walks, the goal), and `today_end` (one line of links)."
import time
from fasthtml.common import *
from abhyasa.core import Page, RouteOverrides, run, n_of
from abhyasa.model import learned
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning',)

def n_due(cs, now=None):
    "The number of seen concepts in `cs` with a review due at `now`."
    now = now or time.time()
    return sum(1 for c in cs if c.seen and c.due and c.due <= now)

def _at(x):
    "The `data-at` of a top card in part `x` (an FT, or a tuple with one), or None."
    for y in (x if isinstance(x, (tuple, list)) else (x,)):
        if isinstance(y, FT) and 'data-at' in y.attrs: return float(y.attrs['data-at'] or 0)
    return None

def newest(parts):
    "The `today_top` parts with one top card: a part with `data-at` (the course card, the Continue card) stays only when it is the newest."
    ats = [a for a in map(_at, parts) if a is not None]
    keep = max(ats) if ats else None
    out, kept = [], False
    for x in parts:
        a = _at(x)
        if a is None: out.append(x)
        elif a == keep and not kept: out.append(x); kept = True
    return out

def Foot(parts):
    "The links at the foot of Today on one line, with ` · ` between them."
    out = []
    for x in parts: out += [*([' · '] if out else []), *(x if isinstance(x, tuple) else (x,))]
    return P(*out, cls='mute foot') if out else ''

def connect(app, ctx):
    lr = ctx.learning

    def today(subject:str=''):
        cs = lr.concepts()
        parts = [*newest(run('today_top', subject or None)), *run('today_next', subject or None), *run('today', subject or None)]
        return Page('Today', H1(f'Today · {subject}' if subject else 'Today'),
                    P(f"{sum(learned(c) for c in cs)} of {n_of(len(cs), 'idea')} learned", cls='mute'),
                    *parts, Foot(run('today_end', subject or None)), on='Today')

    def due(): return JSONResponse(dict(due=n_due(lr.concepts())))   # the Mac app's Dock badge

    RouteOverrides.nav.append(('Today', Routes.base, 0))
    app.get(Routes.base)(today)
    app.get(Routes.due)(due)
