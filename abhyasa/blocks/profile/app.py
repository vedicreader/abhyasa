"What abhyasa knows about you: the profile page, the first conversation, and the line on Today until you have one."
from fasthtml.common import *
from abhyasa.core import n_of, Page, hook, parse_value, RangeLine, row_id
from abhyasa.settings import SETTINGS, fit
from abhyasa.profile import PROFILE, LIST_FIELDS, ONBOARD_QS, onboard, observe, calibration
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask')

def connect(app, ctx):
    lr = ctx.learning
    ask = ctx.ask   # the engine picks the model of each task (`for_task`) on each call, so a settings change works at once
    up = [('Today', '/')]

    def page(new:str=''):
        p = lr.profile()
        return Page('About you', ui.css(), H1('What abhyasa knows about you'),
                    P('The tutor uses this to choose examples, paths and pace. All of it is here, and you can change any of it. '
                      'The tutor adds to it from your answers. Each change shows below with its reason.', cls='mute'),
                    P('This is what abhyasa took from what you said. Change what is wrong.', cls='fresh') if new else '',
                    '' if p.known else ui.Invite(),
                    H2('How the tutor teaches you'), P('The Settings page shows the same three values. A change saves at once.', cls='mute'), ui.Learning(p),
                    H2('About you'), ui.Form_(p) if p.known else Details(Summary('Edit by hand'), ui.Form_(p), cls='more by-hand'),
                    *((H2('What changed, and why'), ui.Changes(p.changes)) if p.changes else ()),
                    H2('How well you know what you know'), ui.Calibration(calibration(lr)),
                    H2('Learn about me now'),
                    P('The tutor reads your recent answers after every sixth question. You can ask it to do that now.', cls='mute'),
                    Div(Button('Look at my recent answers', hx_post=Routes.observe, hx_target='#observed', data_wait='Reading your answers…'),
                        Div(id='observed', cls='ix'), cls='row'),
                    Div(H2('Privacy'), P('This stays in your vault on this Mac. Only the model that writes your questions gets it.', cls='mute'),
                        Form(Button('Clear what abhyasa knows about you', cls='small quiet danger'), action=Routes.clear, method='post',
                             hx_confirm='Clear the whole profile and its changes?'), cls='privacy'),
                    crumbs=up)

    async def save(req):
        f = await req.form()
        kv = {k: (f.getlist(k) if k == 'examples' else f.get(k, '')) for k in PROFILE if k == 'examples' or k in f}   # a field that the form does not have stays
        ch = lr.set_profile(by='you', why='you changed it', **kv)
        return Span(f"Saved {n_of(len(ch), 'change')}." if ch else 'No changes.', id='saved', cls='mute')

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

    def undo(id:str='', at:str=''):
        lr.undo_profile(id or at)
        return Redirect(Routes.base)

    def learn_row(name):
        r = SETTINGS.get(name)
        return r if r is not None and r.store == 'profile' else None

    def setting(name:str, value:str=''):
        "Save pace, questions in a session or new ways, as the Settings page does. The reply is the row."
        if (r := learn_row(name)) is None: return Response('unknown setting', status_code=400)
        try: v = parse_value(r, value)
        except ValueError: return RangeLine(r, lr.profile()[r.key], ui.reset_attrs(r), err='Type a number.')
        lr.set_profile(by='you', why='you changed it', **{r.key: fit(r, v)})
        got = lr.profile()[r.key]
        if got != v: return ui.LearnRow(r, lr.profile()), *HtmxResponseHeaders(retarget=f'#{row_id(r)}', reswap='outerHTML')   # clamped: the box shows the value in use
        return (RangeLine(r, got, ui.reset_attrs(r), saved=True),
                Span(cls='dot' + (' on' if got != r.dflt else ''), id=f'{row_id(r)}-dot', hx_swap_oob='true'))

    def setting_default(name:str):
        if (r := learn_row(name)) is None: return Response('unknown setting', status_code=400)
        lr.set_profile(by='you', why='you used the default', **{r.key: r.dflt})
        return ui.LearnRow(r, lr.profile())

    def observe_now():
        try: ch = observe(lr, ask)
        except Exception as e: return P(f'The model did not answer ({e}).', cls='req-err')
        if not ch: return P('No change: the tutor found nothing new in your recent answers.', cls='mute')
        return Div(P(f"{n_of(len(ch), 'change')}:", cls='mute'), ui.Changes(ch))

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
        return A('What abhyasa knows about you', href=Routes.base) if lr.profile().known else None

    app.get(Routes.base)(page)
    app.post(Routes.base)(save)
    app.get(Routes.start)(start_page)
    app.post(Routes.start)(start)
    app.post(Routes.undo)(undo)
    app.post(Routes.setting)(setting)
    app.post(Routes.setting_default)(setting_default)
    app.post(Routes.observe)(observe_now)
    app.post(Routes.clear)(clear)
