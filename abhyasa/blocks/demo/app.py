"""Interactive demos from rupaka: a page per demo, the concept-page action, the demo under a lesson, and the prediction log.
Show me (⌥E) on a walk step and in a session: a demo made from your words or from the open check, with its kind and why, and 3D and Leela one click away."""
import json
from fasthtml.common import *
from fastcore.utils import AttrDict
from rupaka.render import bundle, version
from abhyasa.core import Page, hook, Msg
from abhyasa.core.leela import leela_link
from abhyasa.demo import queue_demo, job_state, said, route_ask, can_explain
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'tutor')

def connect(app, ctx):
    lr, tutor = ctx.learning, ctx.tutor
    js, css, v = bundle('js'), bundle('css'), version()
    cache = {'Cache-Control': 'public, max-age=31536000, immutable'}

    def rk_js(): return Response(js, media_type='text/javascript', headers=cache)
    def rk_css(): return Response(css, media_type='text/css', headers=cache)

    def spec(slug:str):
        d = lr.demo(slug)
        return JSONResponse(d.spec) if d else JSONResponse(dict(error='no such demo'), status_code=404)

    def page(slug:str):
        d = lr.demo(slug)
        if not d: return Page('Demo', H1('Demo'), P('No such demo.', cls='mute'), on='Library', crumbs=[('Today', '/')])
        c = lr.concept(d.concept)
        back = P('A demo for ', A(c.name, href=f'/c/{c.slug}'), '.', cls='mute') if c else ''
        return Page(d.spec.get('title') or 'Demo', back, ui.DemoCard(d, link=False), on='Library', crumbs=[('Today', '/'), *([(c.name, f'/c/{c.slug}')] if c else [])])

    def made(concept, session='', aim=''):
        "The newest demo of `concept` with the aim `aim` (a plain demo or a simpler demo, never a walk order check), or the state of its job."
        aim = aim if aim in ui.AIMS else ''
        if job_state(tutor, concept, aim) == 'running': return ui.Pending(concept, aim)
        return ui.DemoCard(d, session=session) if (d := lr.demo_for(concept, aim=aim)) else ui.Failed()

    def make(concept:str, aim:str=''):
        "The newest demo of `concept` with the aim `aim` (a plain demo, or a simpler demo after \"Not clear\"), or a job that makes it."
        if not lr.concept(concept): return P('No such concept.', cls='mute')
        aim = aim if aim in ui.AIMS else ''
        if not lr.demo_for(concept, aim=aim) or (aim and said(lr, concept, 'unclear')): queue_demo(tutor, concept, aim=aim)   # after "Not clear", a new simpler demo
        return made(concept, aim=aim)

    def wait(concept:str, session:str='', aim:str=''): return made(concept, session, aim)

    def three_d():
        "Why Show it in 3D is not ready yet."
        return 'abhyasa does not make 3D explainers yet.' if can_explain() else 'It needs rupaka 0.0.8, with 3D scenes.'

    def open_q(at):
        "The open question of the place `at`: by `qid` (a session), or the check of the walk step; None when no check is open."
        qid = at.get('qid')
        if not qid and at.get('walk') and (j := lr.journey(at['walk'])) and 0 <= int(at.get('step', -1)) < len(j.steps): qid = j.steps[int(at['step'])].get('qid')
        return tutor.open.get(qid) if qid else None

    def shown(a):
        "The demo of ask `a`, or its wait, or the line that says the model made none."
        if (d := lr.demo_for(a.concept, aim='', key=a.key or None)): return DemoCard(d, a)
        return ui.AskPending(a) if job_state(tutor, a.concept, said=a.ask) == 'running' else ui.Failed()

    def DemoCard(d, a): return ui.DemoCard(d, session=a.get('session', ''), ask=a.id)

    def answer_ask(words, at, kind=''):
        """One ask for a demo at the place `at` (`where`, `concept`, `walk` and `step`, or `qid`): file it, pick its kind, start its demo, and give its card.
        The demo is made from your `words`, else from the open check; with neither, it is the plain demo of the idea. `kind='demo'` asks for the 2D demo."""
        q = open_q(at)
        c = lr.concept(at.get('concept') or (q or {}).get('concept') or '')
        if c is None: return P('No such concept.', cls='mute')
        words = ' '.join(str(words or '').split())[:300]
        text = words or (f"The idea behind this check: {q['question']}" if q else '')
        route = AttrDict(kind='demo', why='You asked for a 2D demo: you predict first, then you see.') if kind == 'demo' else route_ask(words, c)
        where = at.get('where') if at.get('where') in ('walk', 'session', 'guide') else 'concept'
        place = dict(walk=at['walk'], step=int(at['step'])) if where == 'walk' else dict(session=(q or {}).get('session', '')) if where == 'session' else {}
        a = lr.put_ask(c.slug, said=words, ask=text, where=where, kind=route.kind, **place)
        two_d = None
        if route.kind == 'notebook':
            body = P('Open it in Leela to try it in code. Or see a 2D demo first.', cls='mute')
            two_d = dict(hx_post=Routes.ask, hx_vals=json.dumps({**{k: str(v) for k, v in at.items() if v not in (None, '')}, 'said': words, 'kind': 'demo'}),
                         hx_target=f'#ask-{a.id}', hx_swap='outerHTML')
        else:
            if route.kind == 'explainer': route = AttrDict(route, why=f'{route.why} 3D explainers are not ready yet, so here is a 2D demo.')
            if not lr.demo_for(c.slug, aim='', key=a.key or None): queue_demo(tutor, c.slug, said=text)
            body = shown(a)
        return ui.AskCard(a, route, body, three_d(), leela_link(None, topic=c.name, vault=lr.vault.path), two_d)

    def ask(concept:str='', said:str='', where:str='', walk:str='', step:str='', qid:str='', kind:str=''):
        "Show me: a demo for the place in the form. In a session, it is a tutor message in the thread of the question."
        at = dict(where=where, concept=concept, walk=walk, step=step, qid=qid)
        if where == 'walk' and not (walk and step.isdecimal()): return Response('Name the walk and the step.', status_code=400)
        out = answer_ask(said, at, kind)
        return Msg('', out, cls='tutor extra') if where == 'session' and not kind else out

    def asked(aid:str):
        "The demo of an ask, when it is ready; else the wait again."
        a = lr.asked(aid)
        return shown(a) if a else ui.Failed()

    @hook('show_me')
    def typed(words, at):
        "\"show me …\" in an answer box: the card of the ask. On a walk step it goes in the place under the title."
        out = answer_ask(words, at)
        return Div(out, id='show-slot', hx_swap_oob='innerHTML') if at.get('where') == 'walk' else out

    @hook('step_needs')
    def step_show(j, i, c):
        "Show me under the title of a walk step."
        return ui.StepShow(dict(where='walk', concept=j.steps[i]['slug'], walk=j.id, step=i))

    @hook('answer_tools')
    def session_show(q, into):
        "Show me in the composer of a session. A walk check has its own button under the title."
        if (q.get('meta') or {}).get('walk'): return None
        return ui.SessionShow(q['id'])

    def predict(slug:str, gate:str, picked:str, ans:str='', ok:str='', why:str='', context:str='', session:str='', confidence:int=None, ask:str=''):
        try: lr.record_prediction(slug, gate, picked, ans, ok == 'true', why, context, session, confidence, **({'asked': ask} if ask else {}))
        except KeyError: return JSONResponse(dict(ok=False), status_code=404)
        return JSONResponse(dict(ok=True))

    @hook('concept_actions')
    def show_me(c): return ui.ShowButton(c)

    @hook('lesson_extra')
    def under_lesson(r):
        if r.get('demo') and (d := lr.demo(r.demo)): return ui.DemoCard(d, session=r.get('session', ''))
        if r.get('demo_pending'): return ui.Pending(r.concept, r.get('demo_aim', ''))

    for r, f in ((Routes.js, rk_js), (Routes.css, rk_css), (Routes.spec, spec)):
        app.get(r)(f)
        app.router.routes.insert(0, app.router.routes.pop())   # before fast_app's own `/{fname}.{ext:static}` route
    app.get(Routes.page)(page)
    app.post(Routes.make)(make)
    app.post(Routes.ask)(ask)
    app.get(Routes.wait)(wait)
    app.get(Routes.asked)(asked)
    app.post(Routes.predict)(predict)
