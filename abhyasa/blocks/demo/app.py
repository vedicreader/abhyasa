"Interactive demos from rupaka: a page per demo, the concept-page action, the demo under a lesson, and the prediction log."
from fasthtml.common import *
from rupaka.render import bundle, version
from abhyasa.core import Page, hook
from abhyasa.demo import queue_demo, job_state
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
        if not d: return Page('Demo', H1('Demo'), P('No such demo.', cls='mute'), crumbs=[('Today', '/')])
        c = lr.concept(d.concept)
        back = P('A demo for ', A(c.name, href=f'/c/{c.slug}'), '.', cls='mute') if c else ''
        return Page(d.spec.get('title') or 'Demo', back, ui.DemoCard(d, link=False), crumbs=[('Today', '/'), *([(c.name, f'/c/{c.slug}')] if c else [])])

    def made(concept, session='', aim=''):
        "The newest demo of `concept` with the aim `aim` (a plain demo or a simpler demo, never a walk order check), or the state of its job."
        aim = aim if aim in ui.AIMS else ''
        if (d := lr.demo_for(concept, aim=aim)): return ui.DemoCard(d, session=session)
        return ui.Pending(concept, aim) if job_state(tutor, concept, aim) == 'running' else ui.Failed()

    def make(concept:str):
        if not lr.concept(concept): return P('No such concept.', cls='mute')
        if not lr.demo_for(concept, aim=''): queue_demo(tutor, concept)
        return made(concept)

    def wait(concept:str, session:str='', aim:str=''): return made(concept, session, aim)

    def predict(slug:str, gate:str, picked:str, ans:str='', ok:str='', why:str='', context:str='', session:str='', confidence:int=None):
        try: lr.record_prediction(slug, gate, picked, ans, ok == 'true', why, context, session, confidence)
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
    app.get(Routes.wait)(wait)
    app.post(Routes.predict)(predict)
