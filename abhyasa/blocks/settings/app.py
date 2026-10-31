"Settings: every value that you can change, in groups, in a few tabs. Each value saves when it changes. The rarely changed values are under a closed `More`."
import os, time, base64
from fasthtml.common import *
from fastcore.basics import AttrDict
from abhyasa.core import Page, RouteOverrides, THEMES, MODES, parse_value
from abhyasa import voice
from abhyasa.settings import GROUPS, SETTINGS, rows, val, fit, set_val, reset, reset_group
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('speech', 'speaker', 'ask', 'pool', 'learning')

def connect(app, ctx):
    sp, lr, jobs, spk = ctx.speech, ctx.learning, {}, ctx.speaker
    has_key = lambda: bool(voice.openai_key()[0])
    speech = lambda oob=False: ui.Speech(sp, has_key(), oob)
    out_part = lambda oob=False: ui.VoiceOut(spk, has_key(), oob)

    def value_of(r):
        "The value of row `r` now: from the profile for a Learning row, else from the settings file."
        return lr.profile().get(r.key, r.dflt) if r.store == 'profile' else val(r.name)

    def count(g) -> int:
        "How many values of group `g` are not their default. For Prompts: how many prompts have your text."
        if g == 'prompts':
            from abhyasa.prompts import saved
            return len(saved())
        return sum(value_of(r) != r.dflt for r in rows(g) if r.reset)

    def tab_count(t) -> int: return sum(map(count, ui.TABS[t][1]))

    def set_by() -> str:
        "What sets the default model outside this page, if anything."
        if os.getenv('ABHYASA_MODEL'): return '$ABHYASA_MODEL'
        return '"abhyasa --model"' if getattr(ctx.ask.dflt, '_model', None) else ''

    def section(g):
        n = count(g)
        if g == 'look': return ui.Look(n)
        if g == 'stt': return ui.SpeechGroup(sp, has_key(), jobs, n)
        if g == 'voice': return ui.VoiceGroup(spk, has_key(), n)
        if g == 'models': return ui.ModelsGroup(n)
        if g == 'prompts': return ui.Prompts(n)
        return ui.RowGroup(g, n, value_of)

    def page(tab:str=''):
        "The page with the tab `tab` in force (`?tab=voice`); a link such as #g-voice picks its tab in settings.js."
        on = ui.tab_for(tab)
        return Page('Settings', H1('Settings'), P('The tutor works well with the defaults. Change a value only when you want to.', cls='mute lead-page'),
                    Div(ui.Tabs(on, {t: tab_count(t) for t in ui.TABS}),
                        Div(*[ui.Panel(t, on, *map(section, gs)) for t, (_, gs) in ui.TABS.items()], cls='sgroups'), cls='slayout'),
                    extra=ui.assets(), crumbs=[('Today', '/')], wide=True)

    def store(r, v):
        "Save the value `v` of row `r`, made to fit its row. Return the value in use."
        if r.store == 'profile':
            lr.set_profile(by='you', why='you changed it on the Settings page', **{r.key: fit(r, v)})
            return value_of(r)
        return set_val(r.name, v)

    def after(r):
        "The parts that change with a value: the dot of the row, the index line and the group reset."
        g = r.group
        return (Span(cls='dot' + (' on' if value_of(r) != r.dflt else ''), id=f'{ui.row_id(r)}-dot', hx_swap_oob='true'),
                tab_part(g), ui.GroupReset(g, count(g), oob=True))

    def tab_part(g): return ui.TabCount(ui.TAB_OF[g], tab_count(ui.TAB_OF[g]), oob=True)

    def value(name:str, value:str=''):
        "Save one value. A value out of range is saved as the nearest end of the range. The reply is the range line, with `Saved`."
        if (r := SETTINGS.get(name)) is None or not r.ui: return Response('unknown setting', status_code=400)
        try: v = parse_value(r, value)
        except ValueError: return ui.RangeLine(r, value_of(r), ui.reset_attrs(name), err='Type a number.')
        got = store(r, v)
        if got != v and r.kind in ('int', 'float'):   # clamped: the whole row comes again, so the box shows the value in use
            return ui.Row(r, got), *HtmxResponseHeaders(retarget=f'#{ui.row_id(r)}', reswap='outerHTML'), *after(r)[1:]
        return ui.RangeLine(r, got, ui.reset_attrs(name), saved=True, err=ui.dropped() if name == 'sources.roots' else ''), *after(r)   # a source folder that breaks a rule is named at once

    def default(name:str):
        "Use the default of one value."
        if (r := SETTINGS.get(name)) is None or not r.ui: return Response('unknown setting', status_code=400)
        if r.store == 'profile': store(r, r.dflt)
        else: reset(name)
        return ui.Row(r, value_of(r)), *after(r)[1:]

    def group_ask(group:str, no:int=0):
        "Ask one time before the group goes back to its defaults; `no` puts the link back."
        if group not in GROUPS: return Response('unknown group', status_code=400)
        return ui.GroupReset(group, count(group), ask=not no)

    def group_default(group:str):
        "Use the default of each value of the group that a group reset can change."
        if group not in GROUPS: return Response('unknown group', status_code=400)
        ps = {r.key: r.dflt for r in rows(group) if r.store == 'profile'}
        if ps: lr.set_profile(by='you', why='you used the defaults on the Settings page', **ps)
        reset_group(group)
        return section(group), tab_part(group)

    def use(engine:str, model:str=''):
        if engine == 'openai' and not has_key(): return speech()
        sp.use(engine, model)
        return speech()

    def get(engine:str, model:str):
        "Download `model` in the background, then use it; the page shows a progress line."
        if voice.cached(model) or engine == 'openai': return use(engine, model)
        return fetch_job(engine, model, lambda: sp.use(engine, model), sp, speech)

    def fetch_job(engine, model, then, worker, part):
        "Download `model` on the pool, then `then()` (a future that loads it on `worker`). The reply is `part()` with the progress lines."
        if (j := jobs.get(model)) and j.state in ('downloading', 'loading'): return part(), ui.Jobs(jobs, oob=True)
        for k in [k for k, o in jobs.items() if o.state in ('done', 'failed')]: jobs.pop(k)   # show only the new line
        j = jobs[model] = AttrDict(model=model, engine=engine, total=0, state='downloading', error='', shown=False)
        def run():
            try:
                try: j.total = voice.model_size(model)
                except Exception: j.total = 0   # the line shows bytes without a total
                voice.fetch(model)
                j.state = 'loading'
                if (f := then()) is not None: f.result()
                j.state = 'failed' if worker.status.startswith('failed') else 'done'
                if j.state == 'failed': j.error = worker.status
            except Exception as e: j.state, j.error = 'failed', str(e)
        ctx.pool.submit(run)
        return part(), ui.Jobs(jobs, oob=True)

    def jobs_():
        "The progress lines; when a job ends, the speech section too."
        ended = [j for j in jobs.values() if j.state in ('done', 'failed') and not j.shown]
        for j in ended: j.shown = True
        return (ui.Jobs(jobs), speech(oob=True), out_part(oob=True)) if ended else ui.Jobs(jobs)

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
        "Save the model of one task; '' uses the default. `ui.OTHER` shows a box for a model id that the list does not have."
        from abhyasa.llm import ALL_TASKS, catalog
        if task not in ('default', *ALL_TASKS): return Response('unknown task', status_code=400)
        r = SETTINGS[f'models.{task}']
        if model == ui.OTHER: return ui.ModelRow(task, ctx.ask, [], typing=True)
        set_val(r.name, model.strip())
        return ui.ModelRow(task, ctx.ask, catalog(), set_by=set_by() if task == 'default' else ''), *after(r)[1:]

    def figure_test(model:str):
        "Send the test picture with the labels `FIGURE_TEST` to the model of figure labels, and say whether it read them."
        import time
        from pathlib import Path
        from abhyasa.guide import figure_check, vision_ask, vision_why
        if (why := vision_why(ctx.ask, model)): return Span(f'Failed: {why}', cls='no')
        v, t = vision_ask(ctx.ask, model, job='test:guide_vision'), time.time()
        try: r = figure_check(v, (Path(__file__).parent/'figure-test.png').read_bytes())
        except Exception as e: return Span(f'Failed: {str(e)[:160]}', cls='no')
        s = f'{time.time() - t:.1f} s: '
        if r.ok: return Span(s + f"passed. It read {' and '.join(r.got)}.", cls='ok')
        return Span(s + f"failed. It did not read {' and '.join(r.missing)}" + (f" (it read {', '.join(r.got)})." if r.got else '.'), cls='no')

    def test(task:str, model:str=''):
        import time
        model = '' if model == ui.OTHER else model.strip()
        if task == 'guide_vision': return figure_test(model)
        ask, t = ctx.ask.for_(task, model, job=f'test:{task}'), time.time()   # its own job, so a test does not move the task's route
        try: out = ask('Reply with the one word: ready.', '')
        except Exception as e: return Span(f'Failed: {str(e)[:160]}', cls='no')
        return Span(f"{time.time() - t:.1f} s: “{(out or '').strip()[:40]}”" if out else 'No answer.', cls='ok' if out else 'no')

    def catalog():
        from abhyasa.llm import catalog as cat
        return ui.Models(ctx.ask, cat(), set_by())

    def look_(theme:str='', mode:str=''):
        "Save the theme and the mode; core.js already shows them."
        if theme not in THEMES or mode not in MODES: return Response('unknown theme or mode', status_code=400)
        voice.update_settings('look', theme=theme, mode=mode)
        return Response(status_code=204)

    def prompt_(name:str, text:str=''):
        "Save the text of one prompt. A text that fails its check is not saved: the box keeps it, with the reason."
        from abhyasa.prompts import set_prompt, saved
        if (p := ui.registry().get(name)) is None: return Response('unknown prompt', status_code=400)
        try: set_prompt(name, text)
        except ValueError as e: return ui.PromptItem(p, text, err=str(e))
        return ui.PromptItem(p, said='Saved.' if name in saved() else 'The default is in use.'), tab_part('prompts')

    def prompt_default(name:str): return prompt_(name, '')

    def out(engine:str='', model:str='', voice_:str=''):
        "Save the speaking engine, its model and its voice. A new engine starts from its own defaults. The voice model warms when it is here."
        if engine not in voice.OUT_ENGINES: return Response('unknown voice engine', status_code=400)
        if engine == 'openai' and not has_key(): return out_part()
        same = engine == val('voice.out')
        keep = lambda v, k: v.strip() or (val(k) if same else '')
        m, v = ('', '') if engine == 'browser' else (keep(model, 'voice.out_model'), keep(voice_, 'voice.out_voice'))
        voice.update_settings('voice', out=engine, out_model=m, out_voice=v)
        spk.warm()
        return out_part()

    def out_route(engine:str='', model:str='', voice:str=''): return out(engine, model, voice)   # the form names it `voice`

    def out_get(engine:str, model:str):
        "Download a voice model in the background, then use it."
        if engine not in ('kokoro', 'hf'): return Response('unknown voice engine', status_code=400)
        if voice.cached(model): return out(engine, model)
        def then():
            voice.update_settings('voice', out=engine, out_model=model, out_voice='')
            return spk.warm()
        return fetch_job(engine, model, then, spk, out_part)

    def out_search(q:str=''):
        try: rows = voice.search_models(q, kind='tts')
        except Exception as e: return P(f'Hugging Face did not answer: {e}', cls='mute')
        return ui.OutFound(rows, val('voice.out_model') or (voice.DFLT_KOKORO if val('voice.out') == 'kokoro' else ''))

    async def out_sample():
        "The sample line in the voice of the settings, with the time to the audio: JSON {audio, words, ms, where}."
        import asyncio
        t = time.time()
        try: r = await asyncio.to_thread(spk.say, ui.SAMPLE)
        except Exception as e: return JSONResponse(dict(error=str(e)[:200]), status_code=409 if 'browser' in str(e) else 400)
        return JSONResponse(dict(audio=base64.b64encode(r.pop('wav')).decode(), **r, ms=round((time.time() - t) * 1000)))

    def out_status(): return ui.OutStatus(spk)


    RouteOverrides.gear = Routes.base
    app.get(Routes.base)(page)
    app.post(Routes.value)(value)
    app.post(Routes.default)(default)
    app.get(Routes.group_ask)(group_ask)
    app.post(Routes.group_default)(group_default)
    app.post(Routes.use)(use)
    app.post(Routes.get)(get)
    app.get(Routes.jobs)(jobs_)
    app.get(Routes.status)(status)
    app.get(Routes.search)(search)
    app.post(Routes.remove)(remove)
    app.post(Routes.key)(key)
    app.post(Routes.model)(model)
    app.post(Routes.test)(test)
    app.get(Routes.catalog)(catalog)
    app.post(Routes.look)(look_)
    app.post(Routes.prompt)(prompt_)
    app.post(Routes.prompt_default)(prompt_default)
    app.post(Routes.out)(out_route)
    app.post(Routes.out_get)(out_get)
    app.get(Routes.out_search)(out_search)
    app.post(Routes.out_sample)(out_sample)
    app.get(Routes.out_status)(out_status)
