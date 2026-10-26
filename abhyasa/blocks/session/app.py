"One sitting with the tutor: ask, struggle, grade, teach. The next question is fetched while you read the feedback."
from concurrent.futures import wait
from fasthtml.common import *
from abhyasa.core import Page, hook
from abhyasa.model import DEPTHS, pick
from abhyasa.tutor import Session, HINTS
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'tutor', 'pool', 'sessions')

def connect(app, ctx):
    tutor, sessions, pre = ctx.tutor, ctx.sessions, {}
    tl, shown = {}, {}   # question id -> its messages after the question; session id -> its questions in order, so a reload keeps the chat
    at = Routes.at

    def nxt(sid):
        "The next question: the one fetched ahead, if there is one."
        f = pre.pop(sid, None)
        q = f.result() if f else sessions[sid].next()
        if q: shown.setdefault(sid, []).append(q)
        return q

    def ahead(sid): pre[sid] = ctx.pool.submit(sessions[sid].next)

    def live(sid):
        "The session and its open question, or None when the question is closed (a second click, an old tab)."
        s = sessions.get(sid)
        return (s, s.q) if s and s.q and s.q.id in tutor.open else (s, None)

    def keep(q, *es): tl.setdefault(q.id, []).extend(es); return es

    def past(sid, but=None): return [(q, tl.get(q.id, ())) for q in shown.get(sid, ()) if q is not but]

    def you_said(q): return next((t['text'] for t in reversed(q.get('turns') or []) if t['who'] == 'you'), '')

    def chosen(q): return {t['text'] for t in q.get('turns') or () if t['who'] == 'you'}

    def start(subject:str='', focus:str=''):
        s = Session(tutor, focus=focus or None, subject=subject or None)
        sessions[s.id] = s
        ahead(s.id)   # the model writes the first question while the page loads
        return Redirect(at(Routes.page, s.id))

    def page(sid:str):
        s, q = live(sid)
        if not s: return Redirect('/')
        if not q or sid in pre:   # the question fetched ahead is not on the page yet
            if sid not in pre: ahead(sid)
            wait([pre[sid]], timeout=.5)
            if not pre[sid].done():
                return Page('Learn', ui.Chat(sid, past(sid), waiting=True), ui.Composer(sid), extra=ui.assets())
            if not (q := nxt(sid)): return Redirect(at(Routes.end, sid))
        return Page('Learn', ui.Chat(sid, past(sid, q), (q, tl.get(q.id, ()))), ui.Composer(sid, q), extra=ui.assets())

    def card(sid:str):
        "The section that `Waiting` loads; it waits for the question that is fetched ahead."
        s, q = live(sid)
        if not s: return ui.Done('This session is over.')
        if not (q and sid not in pre): q = nxt(sid)
        return (ui.Section_(sid, q, tl.get(q.id, ())), ui.Composer(sid, q, oob=True)) if q else ui.Done(s.summary())

    def answer(sid:str, answer:str='', thinking:str='', confidence:int=50):
        s, q = live(sid)
        if not q: return Response(status_code=204)
        r = s.answer(answer, thinking, confidence)
        you = ui.You(you_said(q) or answer, thinking, confidence)
        opts = (ui.Options(sid, q, chosen(q), done=r.done, oob=True, right=r.correct and you_said(q)),) if q.get('options') else ()
        if not r.done:
            return (*keep(q, you, ui.Nudge(r)), *opts, ui.Left(r.tries_left, hx_swap_oob='true'),
                    ui.Out(sid, q, oob=True))
        ahead(sid)
        return (*keep(q, you, ui.Close(r), *ui.Extras(r)), *opts, ui.Composer(sid, ready=False, oob=True))

    def giveup(sid:str, dont_know:int=0, confidence:int=50):
        s, q = live(sid)
        if not q: return Response(status_code=204)
        tried = bool(q.tries)
        r = s.answer(dont_know=True, confidence=confidence) if dont_know and not tried else s.give_up()
        ahead(sid)
        opts = (ui.Options(sid, q, chosen(q), done=True, oob=True),) if q.get('options') else ()
        you = ui.You('Teach me.' if tried else "I don't know.")
        return (*keep(q, you, ui.Close(r), *ui.Extras(r)), *opts, ui.Composer(sid, ready=False, oob=True))

    def hint(sid:str):
        s, q = live(sid)
        if not q: return Response(status_code=204)
        if len(q.hints) >= len(HINTS): return Li(Span('No more hints', cls='lbl'), P('Send your best answer, or ask to be taught.'), cls='m tutor hint')
        h = s.hint()
        return keep(q, ui.Hint(len(q.hints), h))

    def ready(sid:str):
        f = pre.get(sid)
        return ui.Ready(sid, not f or f.done())

    def next_(sid:str):
        if sid not in sessions: return ui.Done('This session is over.')
        s, q = live(sid)
        if q and sid not in pre: return Response(status_code=204)   # a second press: this question is on the page
        q = nxt(sid)
        return (ui.Section_(sid, q), ui.Composer(sid, q, oob=True)) if q else ui.Done(s.summary())

    def end(sid:str):
        s = sessions.pop(sid, None)
        if (f := pre.pop(sid, None)): f.cancel()
        return Page('Session', H1('Session'), P(s.summary() if s else 'This session is over.'), A('Back to today', href='/'))

    @hook('today_next')
    def start_here(subject=None):
        p = pick(ctx.learning.concepts(), subject=subject)
        nxt_ = P(f"Next: {p[0].name} at {DEPTHS[p[1]]}. ", Span(p[2], cls='why')) if p else P('Nothing due. Add a source, or pick a concept.')
        return nxt_, Form(Input(type='hidden', name='subject', value=subject or ''),
                          Button(f"Start{' ' + subject if subject else ''} ", Kbd('⌥S'), cls='go', data_wait='Starting…', autofocus=True), action=Routes.start, method='post')

    @hook('concept_actions')
    def learn_this(c):
        return Form(Input(type='hidden', name='focus', value=c.slug), Button('Learn this ', Kbd('⌥S'), cls='go', data_wait='Starting…'), action=Routes.start, method='post')

    app.post(Routes.start)(start)
    app.get(Routes.page)(page)
    app.get(Routes.card)(card)
    app.get(Routes.ready)(ready)
    app.post(Routes.answer)(answer)
    app.post(Routes.giveup)(giveup)
    app.post(Routes.hint)(hint)
    app.post(Routes.next)(next_)
    app.get(Routes.end)(end)
