"Settings: the speech to text engine and model (pick, look up, get, remove), cut at pauses, the OpenAI key, the model and the reply cap of each tutor task, and the theme."
from fasthtml.common import *
from fastcore.basics import AttrDict
from abhyasa.core import Page, RouteOverrides, THEMES, MODES
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
        return Page('Settings', H1('Settings'), ui.Look(), speech(), ui.Jobs(jobs), ui.Lookup(), ui.Key(), ui.Tutor(ctx.ask),
                    on='Settings', extra=ui.assets(), crumbs=[('Today', '/')])

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
        try: voice.set_openai_key(key)
        except ValueError as e: return ui.Key(err=str(e))
        return ui.Key(), speech(oob=True)

    def model(task:str, model:str=''):
        from abhyasa.llm import TASKS, catalog
        if task not in TASKS: return Response('unknown task', status_code=400)
        cur = voice.settings()['models'].get(task, '')
        if model == ui.OTHER: return ui.TaskRow(task, cur, ctx.ask.model, [], typing=True)
        voice.update_settings('models', **{task: model.strip()})
        return ui.TaskRow(task, model.strip(), ctx.ask.model, catalog())

    def test(task:str, model:str=''):
        import time
        model = '' if model == ui.OTHER else model.strip()
        ask, t = ctx.ask.for_(task, model), time.time()   # the same route as the task's calls
        try: out = ask('Reply with the one word: ready.', '')
        except Exception as e: return Span(f'Failed: {str(e)[:160]}', cls='no')
        return Span(f"{time.time() - t:.1f} s: “{(out or '').strip()[:40]}”" if out else 'No answer.', cls='ok' if out else 'no')

    def tokens(task:str, tokens:str=''):
        "Save the reply cap of `task`; a bad value is not saved, and the box says what to type."
        from abhyasa.llm import TASKS, check_tokens
        if task not in TASKS: return Response('unknown task', status_code=400)
        try: n = check_tokens(tokens)
        except ValueError as e: return ui.Cap(task, tokens, err=str(e))
        voice.update_settings('tokens', **{task: n})
        return ui.Cap(task, n)

    def catalog():
        from abhyasa.llm import catalog as cat
        return ui.Tasks(ctx.ask, cat())

    def look_(theme:str='', mode:str=''):
        "Save the theme and the mode; core.js already shows them."
        if theme not in THEMES or mode not in MODES: return Response('unknown theme or mode', status_code=400)
        voice.update_settings('look', theme=theme, mode=mode)
        return Response(status_code=204)

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
    app.post(Routes.model)(model)
    app.post(Routes.test)(test)
    app.post(Routes.tokens)(tokens)
    app.get(Routes.catalog)(catalog)
    app.post(Routes.look)(look_)
