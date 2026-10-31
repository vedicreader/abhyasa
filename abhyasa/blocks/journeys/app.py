"""Walks: a goal and a path of steps to it, that you can see and change. The list, the path page, and what they add to Today,
to a concept page and to a session. The code calls a walk a journey; the page says walk."""
from fasthtml.common import *
from abhyasa.core import Page, hook, run
from abhyasa.settings import val
from abhyasa.profile import profile_text
from fastcore.basics import AttrDict
from abhyasa.journey import plan, progress, walk_state, add_topic, split, beyond, with_step, for_talk
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask', 'sources')

def connect(app, ctx):
    lr = ctx.learning
    ask = ctx.ask   # the engine picks the model of each task (`for_task`) on each call, so a settings change works at once
    up = [('Home', '/')]

    def by(): return {c.slug: c for c in lr.concepts()}
    def yours(): return [j for j in lr.journeys() if not for_talk(j)]   # a side walk of a talk is for the room, not yours
    def state(j, b=None):
        "How far `j` is: `walk_state` for a walk, `progress` for an old path. `current` is the step to do now, with its `name` and its place `i`, or None."
        b = by() if b is None else b
        if j.get('mode') != 'walk': return progress(lr, j, by=b)
        ws = walk_state(j, b); i = ws.current
        cur = None if i is None else AttrDict(ws.steps[i], i=i, name=(b.get(ws.steps[i]['slug']) or {}).get('name', ws.steps[i]['slug']))
        return AttrDict(ws, current=cur, finished=cur is None and bool(ws.steps))

    def path(jid): return ui.Path_(j := lr.journey(jid), state(j))

    def index(): return RedirectResponse('/', status_code=303)   # the old list: Home has it now

    def new(goal:str=''):
        if not goal.strip(): return P('Say or type what you want to learn.', cls='req-err')
        try: j = plan(lr, ask, goal.strip(), profile_text(lr.profile()), ctx.sources)
        except Exception as e: return P(f'The tutor could not plan a walk ({e}). Try again, or say the goal in other words.', cls='req-err')
        return Response(headers={'HX-Redirect': Routes.of(Routes.path, jid=j.id)})

    def one(jid:str):
        j = lr.journey(jid)
        if not j: return Page('Walk', H1('No such walk'), P(A('Your walks', href='/')), on='Home', crumbs=up)
        if j.get('mode') == 'walk' and not for_talk(j): return RedirectResponse(Routes.of(Routes.walk, jid=jid), status_code=301)   # a walk has its own page
        pg = state(j)
        return Page(j.title, *ui.JourneyPage(j, pg, beyond(lr, j), run('walk_actions', j)), on='Home', crumbs=up, extra=ui.assets())

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
        return Redirect('/')

    def use_sources(jid:str):
        "Make the path `jid` a walk with a passage from your sources on each step. The walk block does it on the pool (`walk_from_path`) and gives the pending card."
        if not (j := lr.journey(jid)): return P('This walk is not there now.', cls='req-err')
        if j.get('mode') == 'walk': return Response(headers={'HX-Redirect': Routes.of(Routes.walk, jid=jid)})
        return first(run('walk_from_path', j)) or P('abhyasa cannot make a walk here.', cls='req-err')

    def old(jid:str, req):
        "An old link to `/j/{jid}`, from a page, Leela or a vault document: go to the path, with the same query."
        j = lr.journey(jid)
        to = Routes.of(Routes.walk if j and j.get('mode') == 'walk' else Routes.path, jid=jid)
        return RedirectResponse(to + (f'?{q}' if (q := req.url.query) else ''), status_code=301 if j and j.get('mode') == 'walk' else 303)

    def attach(jid:str, slug:str, src:str=''):
        "Add a concept to a walk: from a concept page (a note), or from the path page (the path again)."
        if not (j := lr.journey(jid)) or not lr.concept(slug): return P('No such walk or concept.', cls='mute')
        lr.journey_add(jid, slug, why='you added it')
        if src == 'concept': return P('Added to ', A(j.title, href=Routes.of(Routes.path, jid=jid)), '.', cls='mute')
        return path(jid)

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
        pg = state(j)
        return ui.StepDone(lr.concept(r.concept), pg.current.name if pg.current else '')

    app.get(Routes.base)(index)
    app.post(Routes.new)(new)
    app.post(Routes.attach)(attach)
    app.get(Routes.path)(one)
    app.get(Routes.one)(old)
    for r in (Routes.path_step, Routes.step): app.post(r)(step)
    for r in (Routes.path_add, Routes.add): app.post(r)(add)
    for r in (Routes.path_split, Routes.split): app.post(r)(split_)
    for r in (Routes.path_drop, Routes.drop): app.post(r)(drop)
    app.post(Routes.path_sources)(use_sources)
