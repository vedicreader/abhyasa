"The home page: what is due, what comes next, and what the other blocks add through the `today` hook."
import time
from fasthtml.common import *
from abhyasa.core import Page, RouteOverrides, run
from abhyasa.model import learned
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning',)

def connect(app, ctx):
    lr = ctx.learning

    def today(subject:str=''):
        cs, now = lr.concepts(), time.time()
        due = sum(1 for c in cs if c.seen and c.due and c.due <= now)
        parts = run('today', subject or None)
        return Page('Today', H1(f'Today · {subject}' if subject else 'Today'),
                    P(f"{due} due for review · {sum(learned(c) for c in cs)} of {len(cs)} concepts learned", cls='mute'),
                    *parts, on='Today')

    RouteOverrides.nav.append(('Today', Routes.base, 0))
    app.get(Routes.base)(today)
