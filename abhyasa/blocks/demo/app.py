"Interactive demos from rupaka: a page per demo, the concept-page action, the demo under a lesson, and the prediction log."
from fasthtml.common import *
from rupaka.render import bundle, version
from abhyasa.core import Page, hook
from abhyasa.demo import queue_demo, job_state, said
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
