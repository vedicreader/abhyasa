"""Rabbit holes: learn a missing idea beside the step, then come back to the same place (spec 6.10).

The block adds to the walk step only through hooks (`step_needs`, `check_after`, `walk_end`, `term_lookup`), and to Today and to a
lesson (`today_next`, `lesson_extra`). It links to the walk by route strings. The side walk is a normal walk."""
import logging, time
from urllib.parse import urlencode
from fasthtml.common import *
from abhyasa.core import hook, run as run_hook
from abhyasa.journey import needs, pick_way_down, detour, back_from, look_up, walk_state, parent_step, for_talk
from abhyasa.settings import val
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask', 'sources')
HOWS = ('primer', 'walk', 'session')
GOOD = ('solid', 'fragile')
log = logging.getLogger(__name__)

def today(t):
    "Whether time `t` is on the local day of now."
    return t and time.localtime(t)[:3] == time.localtime()[:3]

def connect(app, ctx):
    lr = ctx.learning
    ask = ctx.ask   # the engine picks the model of each task (`for_task`) on each call, so a settings change works at once

    def place(at):
        "The walk and the step of `at` (`'<walk id>/<step>'`), or an error response."
        jid, _, i = (at or '').rpartition('/')
        if not jid or not i.isdigit(): return None, None, Response('Name the step as <walk id>/<step>.', status_code=400)
        j, i = lr.journey(jid), int(i)
        if not j or j.get('mode') != 'walk' or not i < len(j.steps): return None, None, Response('No such step.', status_code=404)
        return j, i, None


    def here(pj, i): return f"idea {i + 1} of {len(pj.steps)}"
    def side(j): return j.get('mode') == 'walk' and (j.get('depth') or 0) > 0 and j.get('parent')

    def offer(c, j, i):
        pick = pick_way_down(lr, c.slug)
        return ui.Offer(c, pick, [(lr.concept(s) or {}).get('name', s) for s in pick.chain], here(j, i), limit=(j.get('depth') or 0) >= val('walks.depth'))

    def found(t):
        "The concept for term `t` by slug, name or alias, or None. It writes nothing."
        return look_up(lr, ask, t) if (t or '').strip() else None

    def open_(slug:str='', at:str='', how:str=''):
        "Make the side walk, or its own session past the depth limit, and give the URL of its first step."
        if how not in HOWS: return Response('Choose primer, walk or session.', status_code=400)
        j, i, err = place(at)
        if err: return err
        if not lr.concept(slug): return Response('No such idea.', status_code=404)
        if how != 'session' and (j.get('depth') or 0) >= val('walks.depth'): how = 'session'
        try: d = detour(lr, ask, slug, dict(walk=j.id, step=i), how, ctx.sources)   # walk, then step: `from` is "<walk id>/<step>"
        except Exception as e:   # the log keeps the words of the library; the page shows a plain line
            log.warning('the tutor could not make the side walk: %r', e)
            return Response('The tutor could not make the side walk. Try again.', status_code=502)
        if not d.steps:
            lr.drop_journey(d.id)
            return Response('The tutor found no steps for this idea.', status_code=502)
        return JSONResponse(dict(url=ui.step_url(d.id, 0), title=d.title, how=how))

    def term(t:str='', at:str=''):
        "The offer for a selected term. This GET only finds the term; an unknown term gets a button that adds it."
        j, i, err = place(at)
        if err: return err
        r = found(t)
        if r: run_hook('concepts_added')   # a new term is a new concept: the concepts block places it
        return offer(lr.concept(r.slug), j, i) if r else ui.NotFound(t.strip()[:80], at)

    def add_term(t:str='', at:str=''):
        "Find the term, or add it as a gap of the idea of the step, then give the offer."
        j, i, err = place(at)
        if err: return err
        if not t.strip(): return Response('Select a term first.', status_code=400)
        try: r = look_up(lr, ask, t.strip()[:80], at=f'{j.id}/{i}', sources=ctx.sources)
        except Exception as e:
            log.warning('the tutor could not add the term: %r', e)
            return P('The tutor could not add this term. Try again.', cls='req-err')
        return offer(lr.concept(r.slug), j, i) if r else P('The tutor could not add this term.', cls='req-err')

    def back(sid:str):
        "Keep the result of side walk `sid` on the step that opened it, one time, then go to that step."
        j = lr.journey(sid)
        pj, i = parent_step(lr, j)
        if not pj: return Response('No such side walk.', status_code=404)
        back_from(lr, sid)
        return Redirect(ui.step_url(pj.id, i))

    @hook('step_needs')
    def on_step(j, i, c):
        "The needs line under the title, and the strip while you just came back from a side walk."
        by = {x.slug: x for x in lr.concepts()}
        ds = j.steps[i].get('detours') or []
        met = {d['slug'] for d in ds if d.get('outcome') in GOOD and today(d.get('at'))}
        rows = [(n, 'learned' if n.ok else 'today' if n.slug in met else 'missing') for n in (needs(lr, c.slug, by) if c and c.slug in by else ())]
        strip, d = None, ds[-1] if ds else None
        if d and time.time() - d.get('at', 0) < val('walks.fresh') * 60 and (sj := lr.journey(d['walk'])):
            outs = [(s.get('done') or {}).get('outcome') for s in sj.steps]
            strip = ui.Strip((by.get(d['slug']) or {}).get('name', d['slug']), d.get('outcome') in GOOD, sj.id, [o for o in outs if o and o != 'skipped'])
        return ui.Needs(f'{j.id}/{i}', rows, strip)

    @hook('check_after')
    def gaps(j, i, q):
        "After a miss that names a gap: the line that offers to learn it beside the step."
        terms = list(dict.fromkeys(t.strip() for t in (q or {}).get('gaps') or () if isinstance(t, str) and t.strip()))
        hits = [(r.slug, r.name) if (r := found(t)) else (t, t) for t in terms]
        return ui.GapLine(hits) if hits else None

    @hook('walk_end')
    def end(j):
        "The end of a side walk: what you learned on the way, the way back, and `rh:done` for the page that opened it."
        pj, i = parent_step(lr, j)
        if not side(j) or not pj: return None
        s = next((s for s in reversed(j.steps) if s['slug'] == j.get('slug')), {})
        o = (s.get('done') or {}).get('outcome') or 'skipped'
        c = lr.concept(j.get('slug') or '') or {}
        return ui.EndNote(c.get('name', j.title), o in GOOD, ui.step_url(pj.id, i), here(pj, i), j.get('slug'), o)

    @hook('term_lookup')
    def term_lookup(t, at=''):
        "A term on the shelf as `{slug, name, statement, url}`, with the URL of its offer; None when it is not on the shelf."
        if not (r := found(t)): return None
        return dict(r, url=f"{Routes.term}?{urlencode(dict(t=r.slug, at=at))}")

    @hook('lesson_extra')
    def first_met(r):
        "Under a lesson on an idea that you first met in a side walk: the step that you were on."
        js = sorted((j for j in lr.journeys() if side(j) and not for_talk(j) and any(s['slug'] == r.get('concept') for s in j.steps)), key=lambda j: j.get('created') or 0)
        for j in js:
            pj, i = parent_step(lr, j)
            if pj:
                name = (lr.concept(pj.steps[i]['slug']) or {}).get('name', pj.steps[i]['slug'])
                return P('You first met this on the way to: ', A(name, href=ui.step_url(pj.id, i)), cls='rh-met')

    app.post(Routes.open)(open_)
    app.get(Routes.term)(term)
    app.post(Routes.term)(add_term)
    app.post(Routes.back)(back)
