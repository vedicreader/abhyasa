"""Home, in order of weight: `today_top` (Continue: one card, from `last_place`), `today_next` (the reviews that are due), your courses and walks,
`learn_talks` (Teach), Start something new (`learn_start`), and `today_end` (one line of links)."""
import time
from fasthtml.common import *
from abhyasa.core import Page, RouteOverrides, run, n_of, paged, ListTools, Pager, AllLink, HOME_ROWS
from abhyasa.learner import learned, walk_state, fold
from abhyasa.path import for_talk, stage_rows, used_at
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

def learned_line(cs) -> str:
    "`2 of 286 ideas learned · 4 started`: an idea that you answered on but did not learn yet is started, so the line agrees with Progress."
    n, k = sum(learned(c) for c in cs), sum(bool(c.get('seen')) and not learned(c) for c in cs)
    return f"{n} of {n_of(len(cs), 'idea')} learned" + (f" · {k} started" if k else '')

def connect(app, ctx):
    lr = ctx.learning

    def items():
        """Your courses and the walks of yours that are in no course (not a side walk, not a walk of a talk), each as `(kind, thing, used, made)`.
        Cheap: no `walk_state` and no stage rows. A course was used when one of its stage walks was used."""
        cs, js = lr.courses(), [j for j in lr.journeys() if j.get('mode') == 'walk' and not for_talk(j)]
        byid, staged = {j.id: j for j in js}, {s.get('walk') for c in cs for s in c.stages}
        out = [('course', c, max([used_at(byid[s['walk']]) for s in c.stages if s.get('walk') in byid] + [c.get('created') or 0]), c.get('created') or 0) for c in cs]
        out += [('walk', j, used_at(j), j.get('created') or 0) for j in js if j.id not in staged and not j.get('depth')]
        return out, [j for j in js if j.id not in staged and j.get('depth')]

    def shown(rows, sides, b):
        "The courses and walks of the rows to show, with their stage rows and `walk_state`, and the side walks of those walks only."
        ids = {t.id for k, t, *_ in rows if k == 'walk'}
        mine = [j for j in sides if (j.get('parent') or {}).get('walk') in ids]   # the side walks of the walks on this page
        courses = [(t, stage_rows(lr, t, b)) for k, t, *_ in rows if k == 'course']
        js = [(t, walk_state(t, b)) for k, t, *_ in rows if k == 'walk'] + [(j, walk_state(j, b)) for j in mine]
        return courses, js

    def home(subject:str=''):
        top = run('today_top', subject or None)   # first: the course block gives an older goal walk its course here
        cs = lr.concepts(); b = {c.slug: c for c in cs}
        all_, sides = items()
        courses, js = shown(sorted(all_, key=lambda x: -x[2])[:HOME_ROWS], sides, b)
        return Page('Home', ui.css(), H1(f'Home · {subject}' if subject else 'Home'),
                    P(learned_line(cs), cls='mute'),
                    *top, *run('today_next', subject or None), ui.Walks(courses, js, b), AllLink('All walks', Routes.walks, len(all_)),
                    *(run('learn_talks') if courses or js else ()),
                    Section(H2('Start something new'), *run('learn_start'), id='start', data_part='start'),
                    Foot(run('today_end', subject or None)), on='Home')

    def walks(q:str='', sort:str='used', page:int=1):
        "All your courses and walks, 20 on a page, newest use first (or newest made first), with a filter on the title."
        all_, sides = items()
        rows = [x for x in all_ if fold(q.strip()) in fold(x[1].get('title') or '')] if q.strip() else all_
        rows = sorted(rows, key=lambda x: -(x[3] if sort == 'new' else x[2]))
        part, page, pages = paged(rows, page)
        b = {c.slug: c for c in lr.concepts()}
        courses, js = shown(part, sides, b)
        lst = Div(ui.Walks(courses, js, b, title=f'{n_of(len(rows), "course or walk", "courses and walks")}') or P('No course or walk has this title.', cls='mute'),
                  Pager(Routes.walks, page, pages, q=q, sort=sort if sort != 'used' else ''), id='list')
        return Page('All walks', ui.css(), H1('All walks'), ListTools(Routes.walks, q, sort), lst, on='Home', crumbs=[('Home', Routes.base)])

    def old(): return RedirectResponse(Routes.walks, status_code=301)   # the old Learn tab and list of walks: the list of all walks

    def due(): return JSONResponse(dict(due=n_due(lr.concepts())))   # the Mac app's Dock badge

    RouteOverrides.nav.append(('Home', Routes.base, 0))
    app.get(Routes.base)(home)
    for r in (Routes.learn, Routes.journeys): app.get(r)(old)
    app.get(Routes.due)(due)
    app.get(Routes.walks)(walks)
