"The home page: what is due, then `today_next` (what to do now), then the `today` hook (what other blocks add)."
import time
from fasthtml.common import *
from abhyasa.core import Page, RouteOverrides, run
from abhyasa.model import learned
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning',)

def n_due(cs, now=None):
    "The number of seen concepts in `cs` with a review due at `now`."
    now = now or time.time()
    return sum(1 for c in cs if c.seen and c.due and c.due <= now)

def connect(app, ctx):
    lr = ctx.learning

    def today(subject:str=''):
        cs = lr.concepts()
        parts = [*run('today_next', subject or None), *run('today', subject or None)]
        return Page('Today', H1(f'Today · {subject}' if subject else 'Today'),
                    P(f"{n_due(cs)} due for review · {sum(learned(c) for c in cs)} of {len(cs)} concepts learned", cls='mute'),
                    *parts, on='Today')

    def due(): return JSONResponse(dict(due=n_due(lr.concepts())))   # the Mac app's Dock badge

    RouteOverrides.nav.append(('Today', Routes.base, 0))
    app.get(Routes.base)(today)
    app.get(Routes.due)(due)
