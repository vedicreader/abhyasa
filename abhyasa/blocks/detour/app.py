"""Rabbit holes: "I don't get X", at three depths, then back to the same place (spec 6.10, design flows/rabbit.md).

The chooser offers a quick primer and a side walk, both in the side pane, and its own course for a big gap. The tutor's pick
comes first, with its reason. The block adds to the walk step only through hooks (`step_needs`, `check_after`, `check_stuck`,
`walk_end`), to the concept page (`concept_actions`) and to a lesson (`lesson_extra`). It links to the walk and the course by
route strings. The side walk is a normal walk; its own course is a normal course (`course_from`) with the place as its origin."""
import logging, re, time
from fasthtml.common import *
from fastcore.utils import first
from abhyasa.core import hook, run as run_hook
from abhyasa.core import is_local
from abhyasa.journey import needs, pick_way_down, detour, back_from, look_up, name_gaps, parent_step, for_talk
from abhyasa.course import course_from, courses_from, course_state
from abhyasa.settings import val
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask', 'sources')
HOWS = ('primer', 'walk', 'course')
GOOD = ('solid', 'fragile')
log = logging.getLogger(__name__)

def today(t):
    "Whether time `t` is on the local day of now."
    return t and time.localtime(t)[:3] == time.localtime()[:3]

def connect(app, ctx):
    lr = ctx.learning
    ask = ctx.ask   # the engine picks the model of each task (`for_task`) on each call, so a settings change works at once

    def place(at):
        """The place of `at`: a walk step (`'<walk id>/<step>'`), or a concept page (`'/c/<slug>'`). `(walk, step, None)`,
        `(None, slug, None)` for a concept page, or `(None, None, error response)`."""
        at = at or ''
        if at.startswith('/'):
            m = re.fullmatch(r'/c/([^/?#]+)', at)
            if not is_local(at) or not m: return None, None, Response('Name the step as <walk id>/<step>, or the concept page.', status_code=400)
            return (None, m[1], None) if lr.concept(m[1]) else (None, None, Response('No such idea.', status_code=404))
        jid, _, i = at.rpartition('/')
        if not jid or not i.isdigit(): return None, None, Response('Name the step as <walk id>/<step>.', status_code=400)
        j, i = lr.journey(jid), int(i)
        if not j or j.get('mode') != 'walk' or not i < len(j.steps): return None, None, Response('No such step.', status_code=404)
        return j, i, None

    def origin(j, i): return dict(walk=j.id, step=i) if j else dict(page=f'/c/{i}', title=(lr.concept(i) or {}).get('name', ''))
    def here(pj, i): return f"idea {i + 1} of {len(pj.steps)}" if pj else 'this page'
    def side(j): return j.get('mode') == 'walk' and (j.get('depth') or 0) > 0 and j.get('parent')
    def deep(j): return bool(j) and (j.get('depth') or 0) >= val('walks.depth')

    def offer(c, j, i):
        pick = pick_way_down(lr, c.slug)
        return ui.Offer(c, pick, [(lr.concept(s) or {}).get('name', s) for s in pick.chain], here(j, i), limit=deep(j))

    def found(t):
        "The concept for term `t` by slug, name or alias, or None. It writes nothing."
        return look_up(lr, ask, t) if (t or '').strip() else None

    def open_(slug:str='', at:str='', how:str=''):
        """Make the side walk and give the URL of its first step, for the side pane. For its own course (or past the depth limit),
        make the course of the idea with this place as its origin, and give the URL of the course page."""
        if how not in HOWS: return Response('Choose primer, walk or course.', status_code=400)
        j, i, err = place(at)
        if err: return err
        if not (c := lr.concept(slug)): return Response('No such idea.', status_code=404)
        if deep(j): how = 'course'
        if how == 'course':
            try: k = course_from(lr, slug, origin(j, i))
            except (KeyError, ValueError) as e: return Response(str(e), status_code=400)
            return JSONResponse(dict(url=ui.course_url(k.id), title=k.title, how=how))
        try: d = detour(lr, ask, slug, dict(walk=j.id, step=i) if j else dict(page=f'/c/{i}'), how, ctx.sources)   # walk, then step: `from` is "<walk id>/<step>"
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
        return offer(lr.concept(r.slug), j, i) if r else ui.NotFound(t.strip()[:80], at)

    def add_term(t:str='', at:str=''):
        "Find the term, or add it as a gap of the idea of the step, then give the offer."
        j, i, err = place(at)
        if err: return err
        if not t.strip(): return Response('Select a term first.', status_code=400)
        try: r = look_up(lr, ask, t.strip()[:80], at=f'{j.id}/{i}', sources=ctx.sources) if j else found(t) or (
                 (g := first(name_gaps(lr, ask, i, [t.strip()[:80]], ctx.sources))) and lr.concept(g))   # on a concept page: a gap of the concept
        except Exception as e:
            log.warning('the tutor could not add the term: %r', e)
            return P('The tutor could not add this term. Try again.', cls='req-err')
        if r: run_hook('concepts_added')   # a new term is a new concept: the concepts block places it
        return offer(lr.concept(r.slug), j, i) if r else P('The tutor could not add this term.', cls='req-err')

    def back(sid:str):
        "Keep the result of side walk `sid` on the step that opened it, one time, then go to that step."
        j = lr.journey(sid)
        pj, i = parent_step(lr, j)
        if not pj and side(j or {}) and is_local(p := j.parent.get('page')): return Redirect(p)   # a side walk from a concept page
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
        own = [ui.OwnCourse(k, course_state(lr, k.id)) for k in courses_from(lr, j.id, j.steps[i]['slug'])]   # its own course: the link, and the count when you came back
        return ui.Needs(f'{j.id}/{i}', rows, strip, own)

    @hook('check_after')
    def gaps(j, i, q):
        "After a miss that names a gap: the line that offers to learn it beside the step."
        terms = list(dict.fromkeys(t.strip() for t in (q or {}).get('gaps') or () if isinstance(t, str) and t.strip()))
        hits = [(r.slug, r.name) if (r := found(t)) else (t, t) for t in terms]
        return ui.GapLine(hits) if hits else None

    @hook('check_stuck')
    def stuck(jid, i, s, q):
        "In the stuck row of an open check, after Teach me: Learn it, for the gap that your answer shows, else the first idea that the step needs and you did not learn."
        c = lr.concept(s.get('slug') or '')
        by = {x.slug: x for x in lr.concepts()} if c else {}
        gaps = [g for g in (q or {}).get('gaps') or () if isinstance(g, str) and g.strip()]
        t = (gaps and ((r := found(gaps[0])) and r.slug or gaps[0])) or next((n.slug for n in (needs(lr, c.slug, by) if c else ()) if not n.ok), None)
        return ui.Ask('Learn it', t, cls='rh-ask rh-stuck') if t else None

    @hook('concept_actions')
    def dont_get(c):
        "On a concept page: I don't get this. The chooser opens under the actions; the side walk opens beside the page."
        return Span(ui.Ask("I don't get this", c.slug, cls='rh-ask rh-page', data_at=f'/c/{c.slug}'), *ui.assets(), cls='rh-dont-get')

    @hook('walk_end')
    def end(j):
        "The end of a side walk: what you learned on the way, the way back, and `rh:done` for the page that opened it."
        pj, i = parent_step(lr, j)
        if side(j) and not pj and is_local(p := j.parent.get('page')):   # a side walk from a concept page
            s = next((s for s in reversed(j.steps) if s['slug'] == j.get('slug')), {})
            o = (s.get('done') or {}).get('outcome') or 'skipped'
            c = lr.concept(j.get('slug') or '') or {}
            return ui.EndNote(c.get('name', j.title), o in GOOD, p, 'its page', j.get('slug'), o, (lr.concept(p[3:]) or {}).get('name', ''))
        if not side(j) or not pj: return None
        s = next((s for s in reversed(j.steps) if s['slug'] == j.get('slug')), {})
        o = (s.get('done') or {}).get('outcome') or 'skipped'
        c = lr.concept(j.get('slug') or '') or {}
        return ui.EndNote(c.get('name', j.title), o in GOOD, ui.step_url(pj.id, i), here(pj, i), j.get('slug'), o, pj.title)

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
