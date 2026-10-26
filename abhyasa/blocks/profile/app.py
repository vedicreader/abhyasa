"What abhyasa knows about you: the profile page, the first conversation, and the line on Today until you have one."
from fasthtml.common import *
from abhyasa.core import Page, hook
from abhyasa.llm import for_task
from abhyasa.profile import PROFILE, LIST_FIELDS, ONBOARD_QS, onboard, observe
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask')

def connect(app, ctx):
    lr = ctx.learning
    ask = lambda prompt, sp='': for_task(ctx.ask, 'extract')(prompt, sp)
    up = [('Today', '/')]

    def page(new:str=''):
        p = lr.profile()
        return Page('About you', ui.css(), H1('What abhyasa knows about you'),
                    P('The tutor uses this to choose examples, paths and pace. It is all here, and you can change any of it. '
                      'The tutor adds to it from your answers, and each change shows below with its reason.', cls='mute'),
                    P('This is what abhyasa took from what you said. Change what is wrong.', cls='fresh') if new else '',
                    '' if p.known else P(A('Tell abhyasa about you', href=Routes.start), ': four short questions, by voice or text.'),
                    ui.Form_(p),
                    H2('What changed, and why'), ui.Changes(p.changes),
                    H2('Learn about me now'),
                    P('The tutor reads your recent answers after every sixth question. You can ask it to do that now.', cls='mute'),
                    Div(Button('Look at my recent answers', hx_post=Routes.observe, hx_target='#observed', data_wait='Reading your answers…'),
                        Div(id='observed', cls='ix'), cls='row'),
                    Div(H2('Privacy'), P('This stays in your vault on this machine. Nothing goes anywhere else, other than to the model that writes your questions.', cls='mute'),
                        Form(Button('Clear what abhyasa knows about you', cls='small quiet danger'), action=Routes.clear, method='post',
                             hx_confirm='Clear the whole profile and its changes?'), cls='privacy'),
                    crumbs=up)

    async def save(req):
        f = await req.form()
        kv = {k: (f.getlist(k) if k == 'examples' else f.get(k, '')) for k in PROFILE}
        ch = lr.set_profile(by='you', why='you changed it', **kv)
        return Span(f"Saved {len(ch)} change{'s' if len(ch) != 1 else ''}." if ch else 'No changes.', id='saved', cls='mute')

    def start_page():
        return Page('About you', ui.css(), H1('Tell abhyasa about you'),
                    P('Four short questions. Speak or type. Leave out any that you like. You can change all of it later.', cls='mute'),
                    ui.Onboard(), crumbs=[*up, ('About you', Routes.base)])

    def start(who:str='', want:str='', how:str='', time:str=''):
        answers = dict(who=who, want=want, how=how, time=time)
        if any(v.strip() for v in answers.values()):
            try: onboard(lr, ask, answers)
            except Exception as e: return Page('About you', H1('Tell abhyasa about you'), P(f'The model did not answer ({e}). Try again.', cls='req-err'),
                                               ui.Onboard(), crumbs=[*up, ('About you', Routes.base)])
        return Redirect(f'{Routes.base}?new=1')

    def undo(at:float):
        lr.undo_profile(at)
        return Redirect(Routes.base)

    def observe_now():
        try: ch = observe(lr, ask)
        except Exception as e: return P(f'The model did not answer ({e}).', cls='req-err')
        if not ch: return P('No change: the tutor found nothing new in your recent answers.', cls='mute')
        return Div(P(f"{len(ch)} change{'s' if len(ch) != 1 else ''}:", cls='mute'), ui.Changes(ch))

    def clear():
        lr.clear_profile()
        return Redirect(Routes.base)

    @hook('today_top')
    def meet(subject=None):
        if lr.profile().known: return None
        return P(A('Tell abhyasa about you', href=Routes.start), '. Four short questions, by voice or text, so the tutor can use examples from your world.',
                 cls='meet mute')

    @hook('today_end')
    def about(subject=None):
        return P(A('What abhyasa knows about you', href=Routes.base), cls='mute') if lr.profile().known else None

    app.get(Routes.base)(page)
    app.post(Routes.base)(save)
    app.get(Routes.start)(start_page)
    app.post(Routes.start)(start)
    app.post(Routes.undo)(undo)
    app.post(Routes.observe)(observe_now)
    app.post(Routes.clear)(clear)
