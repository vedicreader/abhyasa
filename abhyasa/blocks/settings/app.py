"Settings: the speech to text engine and model (pick, look up, get, remove), cut at pauses, the OpenAI key, and the tutor's model."
from fasthtml.common import *
from fastcore.basics import AttrDict
from abhyasa.core import Page, RouteOverrides
from abhyasa import voice
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('speech', 'ask', 'pool')

def connect(app, ctx):
    sp, jobs = ctx.speech, {}
    has_key = lambda: bool(voice.openai_key()[0])
    speech = lambda oob=False: ui.Speech(sp, has_key(), oob)

    def page():
        return Page('Settings', H1('Settings'), speech(), ui.Jobs(jobs), ui.Lookup(), ui.Key(), ui.Tutor(getattr(ctx.ask, 'model', '')),
                    on='Settings', extra=ui.assets())

    def use(engine:str, model:str=''):
        if engine == 'openai' and not has_key(): return speech()
        sp.use(engine, model)
        return speech()

    def segment(on:int=0):
        voice.update_settings('stt', segment=bool(on))
        return Response(status_code=204)

    def get(engine:str, model:str):
        "Download `model` in the background, then use it; the page shows a progress line."
        if voice.cached(model) or engine == 'openai': return use(engine, model)
        if (j := jobs.get(model)) and j.state in ('downloading', 'loading'): return speech(), ui.Jobs(jobs, oob=True)
        for k in [k for k, o in jobs.items() if o.state in ('done', 'failed')]: jobs.pop(k)   # show only the new line
        j = jobs[model] = AttrDict(model=model, engine=engine, total=0, state='downloading', error='', shown=False)
        def run():
            try:
                try: j.total = voice.model_size(model)
                except Exception: j.total = 0   # the line shows bytes without a total
                voice.fetch(model)
                j.state = 'loading'
                sp.use(engine, model).result()
                j.state = 'failed' if sp.status.startswith('failed') else 'done'
                if j.state == 'failed': j.error = sp.status
            except Exception as e: j.state, j.error = 'failed', str(e)
        ctx.pool.submit(run)
        return speech(), ui.Jobs(jobs, oob=True)

    def jobs_():
        "The progress lines; when a job ends, the speech section too."
        ended = [j for j in jobs.values() if j.state in ('done', 'failed') and not j.shown]
        for j in ended: j.shown = True
        return (ui.Jobs(jobs), speech(oob=True)) if ended else ui.Jobs(jobs)

    def status(): return ui.Status(sp)

    def search(q:str=''):
        try: rows = voice.search_models(q)
        except Exception as e: return P(f'Hugging Face did not answer: {e}', cls='mute')
        return ui.Found(rows, voice.current())

    def remove(model:str):
        if voice.current()[1] == model: return speech()   # not the model in use
        try: voice.remove(model)
        except ValueError: pass
        return speech()

    def key(key:str=''):
        voice.set_openai_key(key)
        return ui.Key(), speech(oob=True)

    RouteOverrides.nav.append(('Settings', Routes.base, 9))
    app.get(Routes.base)(page)
    app.post(Routes.use)(use)
    app.post(Routes.segment)(segment)
    app.post(Routes.get)(get)
    app.get(Routes.jobs)(jobs_)
    app.get(Routes.status)(status)
    app.get(Routes.search)(search)
    app.post(Routes.remove)(remove)
    app.post(Routes.key)(key)
