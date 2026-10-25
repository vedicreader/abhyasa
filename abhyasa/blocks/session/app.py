"One sitting with the tutor: ask, struggle, grade, teach. The next question is fetched while you read the feedback."
from fasthtml.common import *
from abhyasa.core import Page, hook
from abhyasa.model import DEPTHS, pick
from abhyasa.tutor import Session
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'tutor', 'pool', 'sessions')

def connect(app, ctx):
    tutor, sessions, pre = ctx.tutor, ctx.sessions, {}
    at = Routes.at

    def nxt(sid):
        "The next question: the one fetched ahead, if there is one."
        f = pre.pop(sid, None)
        return f.result() if f else sessions[sid].next()

    def ahead(sid): pre[sid] = ctx.pool.submit(sessions[sid].next)

    def start(subject:str='', focus:str=''):
        s = Session(tutor, focus=focus or None, subject=subject or None)
        sessions[s.id] = s
        return Redirect(at(Routes.page, s.id))

    def page(sid:str):
        s = sessions.get(sid)
        if not s: return Redirect('/')
        q = s.q if s.q and s.q.id in tutor.open else nxt(sid)
        if not q: return Redirect(at(Routes.end, sid))
        return Page('Learn', ui.QuestionCard(sid, q), extra=ui.assets())

    def answer(sid:str, answer:str='', thinking:str='', confidence:int=50):
        r = sessions[sid].answer(answer, thinking, confidence)
        if r.done: ahead(sid)
        return ui.Feedback(sid, r)

    def giveup(sid:str, dont_know:int=0):
        s = sessions[sid]
        r = s.answer(dont_know=True) if dont_know else s.give_up()
        ahead(sid)
        return ui.Feedback(sid, r)

    def hint(sid:str): return Li(ui.Md(sessions[sid].hint()))

    def next_(sid:str):
        q = nxt(sid)
        return ui.QuestionCard(sid, q) if q else ui.Done(sessions[sid].summary())

    def end(sid:str):
        s = sessions.pop(sid, None)
        if (f := pre.pop(sid, None)): f.cancel()
        return Page('Session', H1('Session'), P(s.summary() if s else 'This session is over.'), A('Back to today', href='/'))

    @hook('today')
    def start_here(subject=None):
        p = pick(ctx.learning.concepts(), subject=subject)
        nxt_ = P(f"Next: {p[0].name} at {DEPTHS[p[1]]}. ", Span(p[2], cls='why')) if p else P('Nothing due. Add a source, or pick a concept.')
        return nxt_, Form(Input(type='hidden', name='subject', value=subject or ''),
                          Button(f"Start{' ' + subject if subject else ''}", cls='go'), action=Routes.start, method='post')

    @hook('concept_actions')
    def learn_this(c):
        return Form(Input(type='hidden', name='focus', value=c.slug), Button('Learn this', cls='go'), action=Routes.start, method='post')

    app.post(Routes.start)(start)
    app.get(Routes.page)(page)
    app.post(Routes.answer)(answer)
    app.post(Routes.giveup)(giveup)
    app.post(Routes.hint)(hint)
    app.post(Routes.next)(next_)
    app.get(Routes.end)(end)
