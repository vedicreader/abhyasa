"""Interactive demos from rupaka: Show. One engine (`abhyasa.demo.show`) and one card for each place: the Show slot of a walk step and of a
concept page, the thread of a session, the card under a lesson, and "show me …" to the guide. Each Show is an ask, so `/demo/asked/{aid}`
is its one wait. The kind of each ask says why, and 3D and Leela are one click away.
A 3D explainer is a rupaka scene. rupaka loads three.js from `Routes.three` only when a scene mounts, so a page with no scene never loads it."""
import json, re
from fasthtml.common import *
from fastcore.utils import AttrDict
from starlette.responses import RedirectResponse
from rupaka.render import bundle, version
from abhyasa.core import hook, Msg
from abhyasa.core.leela import leela_link
from abhyasa.demo import show, queue_demo, job_state, job_age, job_stage, ROUTES, REFUSED
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
    def rk_three(): return Response(three(), media_type='text/javascript', headers=cache)
    three = lambda: _three.setdefault('js', bundle('three'))   # built on first use, from the copy in rupaka: no network
    _three = {}

    def spec(slug:str):
        d = lr.demo(slug)
        return JSONResponse(d.spec) if d else JSONResponse(dict(error='no such demo'), status_code=404)

    def page(slug:str):
        "A demo has no page of its own: it opens in the Show slot of its idea, on the concept page."
        d = lr.demo(slug)
        return RedirectResponse(f'/c/{d.concept}' if d and lr.concept(d.concept) else '/library', status_code=301)   # one 301: not through the old /concepts

    def open_q(at):
        "The open question of the place `at`: by `qid` (a session), or the check of the walk step; None when no check is open."
        qid = at.get('qid')
        if not qid and at.get('walk') and (j := lr.journey(at['walk'])) and 0 <= int(at.get('step', -1)) < len(j.steps): qid = j.steps[int(at['step'])].get('qid')
        return tutor.open.get(qid) if qid else None

    def shown(a, kind=''):
        """The demo of ask `a` (its 3D explainer for the kind `explainer`, or for `kind='3d'`; its simpler demo for the aim `simpler`), or its wait,
        or the line that says the model made none. When the model makes no valid 3D explainer, the card says so and gives the 2D demo."""
        three = (kind or ('3d' if a.get('kind') == 'explainer' else 'demo')) == '3d'
        aim = '3d' if three else a.get('aim', '') if not kind else ''
        if job_state(tutor, a.concept, aim, a.ask) == 'running':
            wait = ui.AskPending(a, '3d' if three else kind, aim, job_age(tutor, a.concept, aim, a.ask), job_stage(tutor, a.concept, aim, a.ask),
                                 ui.WHILE_3D if three and not kind else '')
            if not (three and not kind): return wait
            if not lr.demo_for(a.concept, key=a.key or None) and job_state(tutor, a.concept, '', a.ask) != 'running': queue_demo(tutor, a.concept, said=a.ask)
            return ui.WhileThree(wait, shown(a, 'demo'))   # the 2D demo while the 3D explainer builds
        if (d := lr.demo_for(a.concept, aim=aim, key=a.key or None)): return ui.DemoCard(d, session=a.get('session', ''), ask=a.id, lead=False)   # the kind line of the card says how it works
        if not three: return ui.Failed()
        if not lr.demo_for(a.concept, key=a.key or None): queue_demo(tutor, a.concept, aim='', said=a.ask)
        return Div(P(REFUSED, cls='mute refused'), shown(a, 'demo'))

    def values_of(at, q):
        "The values of the place `at` that the demo starts from: what the guide read on the page, the tests that a notebook step shows, else the open check."
        if at.get('values'): return at['values']
        if at.get('walk') and (j := lr.journey(at['walk'])) and 0 <= int(at.get('step', -1)) < len(j.steps):
            if (ts := [t['test'] for t in (j.steps[int(at['step'])].get('nb') or {}).get('tests') or () if isinstance(t, dict) and t.get('shown') and t.get('test')]): return ' '.join(ts)
        return ''

    def answer_ask(words, at, kind='', aim='', into=''):
        """One ask for a demo at the place `at` (`where`, `concept`, `walk` and `step`, or `qid`): Show files it, picks its kind and starts its demo;
        this gives its card. The demo is made from your `words`, else from the open check; with neither, it is the plain demo of the idea.
        `kind='demo'` asks for the 2D demo, `kind='3d'` for the 3D explainer, and `aim='simpler'` for a simpler demo. With `into` (the id of a
        card with a 2D demo), the 3D explainer comes in that card, above its 2D demo: the demo that you predict on stays, with the same values."""
        q = open_q(at)
        c = lr.concept(at.get('concept') or (q or {}).get('concept') or '')
        if c is None: return P('No such concept.', cls='mute')
        words = ' '.join(str(words or '').split())[:300]
        text = words or (f"The idea behind this check: {q['question']}" if q else '')
        where = at.get('where') if at.get('where') in ('walk', 'session', 'guide') else 'concept'
        place = dict(walk=at['walk'], step=int(at['step'])) if where == 'walk' else dict(session=(q or {}).get('session', '') or at.get('session', '')) if where == 'session' else {}
        a, route = show(tutor, c.slug, words, where=where, kind=kind or None, ask=text, aim=aim if aim in ui.AIMS else '', values=values_of(at, q), **place)
        if into:   # Show it in 3D on a 2D card: only the 3D part, into the card; the button goes
            return Div(Span(ui.KINDS['explainer'], cls='lbl'), P(route.why, cls='mute kind-why'), shown(a, '3d'), Span(id=f'three-btn-{into}', hx_swap_oob='true'))
        vals = {**{k: str(v) for k, v in at.items() if v not in (None, '')}, 'said': words}
        def other(k): return dict(hx_post=Routes.ask, hx_vals=json.dumps({**vals, 'kind': k}), hx_target=f'#ask-{a.id}', hx_swap='outerHTML')   # the other kind, one click away
        def three(): return dict(hx_post=Routes.ask, hx_vals=json.dumps({**vals, 'kind': '3d', 'into': a.id}), hx_target=f'#three-{a.id}', hx_swap='innerHTML', id=f'three-btn-{a.id}')
        body = P('Open it in Leela to try it in code. Or see a 2D demo or a 3D explainer first.', cls='mute') if route.kind == 'notebook' else shown(a)
        return ui.ShowCard(a, route, body, leela_link(None, topic=c.name, vault=lr.vault.path),
                           two_d=other('demo') if route.kind == 'notebook' else None,
                           three_d=(three() if route.kind == 'demo' else other('3d')) if route.kind != 'explainer' else None)   # a 3D card has its 2D demo under it

    def ask(concept:str='', said:str='', where:str='', walk:str='', step:str='', qid:str='', kind:str='', aim:str='', session:str='', values:str='', into:str=''):
        "Show me: a demo for the place in the form. In a session, it is a tutor message in the thread of the question. `values` are the values of the page that the guide read, so each job of the ask starts from them."
        at = dict(where=where, concept=concept, walk=walk, step=step, qid=qid, session=session, values=values)
        if where == 'walk' and not (walk and step.isdecimal()): return Response('Name the walk and the step.', status_code=400)
        out = answer_ask(said, at, kind, aim, into=into if kind == '3d' and re.fullmatch(r'[0-9a-f]{12}', into or '') else '')
        return Msg('', out, cls='tutor extra') if where == 'session' and not kind else out

    def asked(aid:str, kind:str=''):
        "The demo of an ask (or with `kind`, its 3D explainer or its 2D demo), when it is ready; else the wait again."
        a = lr.asked(aid)
        return shown(a, kind if kind in ('3d', 'demo') else '') if a else ui.Failed()

    @hook('show_me')
    def typed(words, at):
        "\"show me …\" in an answer box or to the guide: the card of the ask. On a walk step it goes in the Show slot under the title."
        out = answer_ask(words, at)
        return Div(out, id='show-slot', hx_swap_oob='innerHTML') if at.get('where') == 'walk' else out

    @hook('step_needs')
    def step_show(j, i, c):
        "The Show slot under the title of a walk step. Its Show me button is here, unless the step has an open short check: then it is in the row of the check."
        s = j.steps[i]
        mine = (s.get('check') or {}).get('kind', 'short') == 'short' and not s.get('done')
        return ui.StepShow(dict(where='walk', concept=s['slug'], walk=j.id, step=i), button=not mine)

    @hook('check_show')
    def check_show(jid, i, s):
        "Show me in the row of an open short check of walk `jid`, step `i`, after Hint and Explain: the stuck order is Hint, Explain, Show, Teach me."
        return ui.ShowMe(dict(where='walk', concept=s['slug'], walk=jid, step=i))

    @hook('answer_tools')
    def session_show(q, into):
        "Show me in the composer of a session. A walk check has its own button in the row of the check."
        if (q.get('meta') or {}).get('walk'): return None
        return ui.SessionShow(q['id'])

    def predict(slug:str, gate:str, picked:str, ans:str='', ok:str='', why:str='', context:str='', session:str='', confidence:int=None, ask:str=''):
        try: lr.record_prediction(slug, gate, picked, ans, ok == 'true', why, context, session, confidence, **({'asked': ask} if ask else {}))
        except KeyError: return JSONResponse(dict(ok=False), status_code=404)
        return JSONResponse(dict(ok=True))

    @hook('concept_actions')
    def show_me(c): return ui.StepShow(dict(where='concept', concept=c.slug))   # the Show slot of the concept page; /c/{slug}?show=<words> presses it

    @hook('lesson_extra')
    def under_lesson(r):
        "The demo under a lesson after a miss, or its wait: an ask, so it has the one wait of Show."
        if r.get('demo') and (d := lr.demo(r.demo)): return ui.DemoCard(d, session=r.get('session', ''))
        if r.get('demo_pending'):
            if not (a := r.get('demo_ask') and lr.asked(r.demo_ask)):
                a = lr.put_ask(r.concept, where='session', kind='demo', session=r.get('session', ''), **({'aim': r.demo_aim} if r.get('demo_aim') in ui.AIMS else {}))
                r['demo_ask'] = a.id
            c = lr.concept(r.concept)
            return ui.ShowCard(a, AttrDict(kind='demo', why='You missed it again. Predict first. Then the demo shows the rest.'), shown(a), leela_link(None, topic=c.name if c else r.concept, vault=lr.vault.path))   # the one card of Show

    for r, f in ((Routes.js, rk_js), (Routes.css, rk_css), (Routes.three, rk_three), (Routes.spec, spec)):
        app.get(r)(f)
        app.router.routes.insert(0, app.router.routes.pop())   # before fast_app's own `/{fname}.{ext:static}` route
    app.get(Routes.page)(page)
    app.post(Routes.ask)(ask)
    app.get(Routes.asked)(asked)
    app.post(Routes.predict)(predict)
