"""Home, in order of weight: `today_top` (Continue: one card, from `last_place`), `today_next` (the reviews that are due), your courses and walks,
`learn_talks` (Teach), Start something new (`learn_start`), and `today_end` (one line of links)."""
import time
from fasthtml.common import *
from abhyasa.core import Page, RouteOverrides, run, n_of
from abhyasa.model import learned
from abhyasa.journey import walk_state, for_talk
from abhyasa.course import stage_rows
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning',)

def n_due(cs, now=None):
    "The number of seen concepts in `cs` with a review due at `now`."
    now = now or time.time()
    return sum(1 for c in cs if c.seen and c.due and c.due <= now)

def Foot(parts):
    "The links at the foot of Home on one line, with ` · ` between them."
    out = []
    for x in parts: out += [*([' · '] if out else []), *(x if isinstance(x, tuple) else (x,))]
    return P(*out, cls='mute foot') if out else ''

def connect(app, ctx):
    lr = ctx.learning

    def walks(cs):
        "Your courses, each with its stage rows, and each walk of yours that is in no course, with its `walk_state`. One read of the concepts."
        b = {c.slug: c for c in cs}
        courses = [(c, stage_rows(lr, c, b)) for c in lr.courses()]
        staged = {s.get('walk') for c, _ in courses for s in c.stages}
        js = [(j, walk_state(j, b)) for j in lr.journeys() if j.get('mode') == 'walk' and not for_talk(j) and j.id not in staged]   # a side walk of a talk is for the room
        return courses, js, b

    def home(subject:str=''):
        top = run('today_top', subject or None)   # first: the course block gives an older goal walk its course here
        cs = lr.concepts()
        courses, js, b = walks(cs)
        return Page('Home', ui.css(), H1(f'Home · {subject}' if subject else 'Home'),
                    P(f"{sum(learned(c) for c in cs)} of {n_of(len(cs), 'idea')} learned", cls='mute'),
                    *top, *run('today_next', subject or None), ui.Walks(courses, js, b),
                    *(run('learn_talks') if courses or js else ()),
                    Section(H2('Start something new'), *run('learn_start'), id='start', data_part='start'),
                    Foot(run('today_end', subject or None)), on='Home')

    def old(): return RedirectResponse(Routes.base, status_code=301)   # the old Learn tab and list of walks: Home has the walks and the Start box

    def due(): return JSONResponse(dict(due=n_due(lr.concepts())))   # the Mac app's Dock badge

    RouteOverrides.nav.append(('Home', Routes.base, 0))
    app.get(Routes.base)(home)
    for r in (Routes.learn, Routes.journeys): app.get(r)(old)
    app.get(Routes.due)(due)
