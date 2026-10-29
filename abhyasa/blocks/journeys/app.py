"""Walks: a goal and a path of steps to it, that you can see and change. The list, the path page, and what they add to Today,
to a concept page and to a session. The code calls a walk a journey; the page says walk."""
from fasthtml.common import *
from abhyasa.core import Page, RouteOverrides, hook, run
from abhyasa.settings import val
from abhyasa.profile import profile_text
from abhyasa.journey import plan, progress, add_topic, split, beyond, with_step, for_talk
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask', 'sources')

def connect(app, ctx):
    lr = ctx.learning
    ask = ctx.ask   # the engine picks the model of each task (`for_task`) on each call, so a settings change works at once
    up = [('Today', '/'), ('Walks', Routes.base)]

    def by(): return {c.slug: c for c in lr.concepts()}
    def yours(): return [j for j in lr.journeys() if not for_talk(j)]   # a side walk of a talk is for the room, not yours
    def listed(skip=None):
        b = by()
        return [(j, progress(lr, j, by=b)) for j in yours() if j.id != skip]

    def path(jid): return ui.Path_(j := lr.journey(jid), progress(lr, j))

    def index():
        return Page('Walks', H1('Walks'),
                    P('A walk is a goal and a path of steps to it. The tutor suggests the path from your concepts and what it knows '
                      'about you. You can move, skip, add or split a step.', cls='mute'),
                    ui.GoalForm(), H2('Your walks'), ui.JourneyList(listed()), on='Learn', crumbs=[('Today', '/')], extra=ui.assets())

    def new(goal:str=''):
        if not goal.strip(): return P('Say or type what you want to learn.', cls='req-err')
        try: j = plan(lr, ask, goal.strip(), profile_text(lr.profile()), ctx.sources)
        except Exception as e: return P(f'The planner did not give a path ({e}). Try again, or say the goal in other words.', cls='req-err')
        return Response(headers={'HX-Redirect': Routes.of(Routes.path, jid=j.id)})

    def one(jid:str):
        j = lr.journey(jid)
        if not j: return Page('Walk', H1('No such walk'), P(A('All walks', href=Routes.base)), on='Learn', crumbs=up)
        pg = progress(lr, j)
        return Page(j.title, *ui.JourneyPage(j, pg, beyond(lr, j), listed(jid)[:val('lists.beside')], run('walk_actions', j)), on='Learn', crumbs=up, extra=ui.assets())

    def step(jid:str, slug:str, act:str):
        if not lr.journey(jid): return Response(status_code=404)
        lr.journey_step(jid, slug, act)
        return path(jid)

    def add(jid:str, name:str=''):
        if name.strip(): add_topic(lr, ask, jid, name.strip(), sources=ctx.sources); run('concepts_added')   # the concepts block places the new concept
        return path(jid)

    def split_(jid:str, slug:str):
        split(lr, ask, jid, slug, ctx.sources); run('concepts_added')
        return path(jid)

    def drop(jid:str):
        lr.drop_journey(jid)
        return Redirect(Routes.base)

    def old(jid:str, req):
        "An old link to `/j/{jid}`, from a page, Leela or a vault document: go to the path, with the same query."
        return RedirectResponse(Routes.of(Routes.path, jid=jid) + (f'?{q}' if (q := req.url.query) else ''), status_code=303)

    def attach(jid:str, slug:str, src:str=''):
        "Add a concept to a walk: from a concept page (a note), or from the path page (the path again)."
        if not (j := lr.journey(jid)) or not lr.concept(slug): return P('No such walk or concept.', cls='mute')
        lr.journey_add(jid, slug, why='you added it')
        if src == 'concept': return P('Added to ', A(j.title, href=Routes.of(Routes.path, jid=jid)), '.', cls='mute')
        return path(jid)

    @hook('today')
    def on_today(subject=None):
        js = listed()
        goal = Details(Summary('What do you want to learn?'), ui.GoalForm(compact=True, label=False), cls='goal-fold') if js else ui.GoalForm()
        return (H2('Your walks'), ui.JourneyList(js[:(n := val('lists.journeys'))]),
                *([P(A(f'See all {len(js)} walks', href=Routes.base), cls='mute')] if len(js) > n else []),
                goal, *ui.assets())

    @hook('concept_more')
    def in_journeys(c):
        rows, js = [(j, i) for j, i in with_step(lr, c.slug) if not for_talk(j)], yours()
        return ui.InJourneys(c, rows, js) if rows or js else None

    @hook('lesson_extra')
    def step_done(r):
        "A note when the close makes a step of the walk of this session learned."
        if not (r.get('correct') and r.get('floor', 0) >= val('checks.goal') and r.get('depth') == r.get('floor')): return None
        s = lr.session(r.get('session') or '') if r.get('session') else None
        if not (s and s.get('journey') and (j := lr.journey(s.journey))) or r.concept not in [x['slug'] for x in j.steps]: return None
        pg = progress(lr, j)
        return ui.StepDone(lr.concept(r.concept), pg.current.name if pg.current else '')

    RouteOverrides.nav.append(('Learn', Routes.learn, 1))
    app.get(Routes.base)(index)
    app.get(Routes.learn)(index)
    app.post(Routes.new)(new)
    app.post(Routes.attach)(attach)
    app.get(Routes.path)(one)
    app.get(Routes.one)(old)
    for r in (Routes.path_step, Routes.step): app.post(r)(step)
    for r in (Routes.path_add, Routes.add): app.post(r)(add)
    for r in (Routes.path_split, Routes.split): app.post(r)(split_)
    for r in (Routes.path_drop, Routes.drop): app.post(r)(drop)
