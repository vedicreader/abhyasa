"""One sitting with the tutor: ask, struggle, grade, teach. The next question is fetched while you read the feedback.
Each session is saved on the shelf as it goes; a URL of a session that is not in memory loads it from the shelf."""
import time
from concurrent.futures import wait
from fasthtml.common import *
from fastcore.utils import AttrDict
from abhyasa.core import Page, hook, Primary, n_of, Feedback
from abhyasa.model import DEPTHS, pick
from abhyasa.tutor import Session, HINTS, moved
from abhyasa.journey import progress, related
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'tutor', 'pool', 'sessions')

WHY = {'its prereqs are in place': 'You know the ideas that it needs.', 'you started it': 'You started it.',
       'it is next to the concept you chose': 'It is next to the idea you chose.'}

def plain_why(why:str) -> str:
    "The reason of `pick` as one plain sentence for Today: `next on the frontier: its prereqs are in place` -> `You know the ideas that it needs.`"
    w = why.removeprefix('next on the frontier: ')
    if w in WHY: return WHY[w]
    return (w[:1].upper() + w[1:] + ('' if w.endswith('.') else '.')) if w else ''

def connect(app, ctx):
    tutor, sessions, pre, lr = ctx.tutor, ctx.sessions, {}, ctx.learning
    tl, shown, outcomes = {}, {}, {}   # question id -> its messages; session id -> its questions in order; question id -> its outcome
    at = Routes.at

    def get(sid):
        "The session: in memory, else from the shelf, with its earlier questions rebuilt from its log."
        if (s := sessions.get(sid)) is not None: return s
        if (s := Session.load(tutor, sid)) is None: return None
        sessions[sid] = s
        shown[sid] = [AttrDict(id=r['qid'], concept=r['concept'], name=r['name'], depth=r['depth'], why=r.get('why', ''), question=r['question'],
                               floor=r.get('floor0', 0), turns=r.get('turns') or []) for r in s.log if r.get('qid')]
        outcomes.update({r['qid']: r['outcome'] for r in s.log if r.get('qid')})
        if s.q: shown[sid].append(s.q)
        for q in shown[sid]: tl[q.id] = list(ui.Turns((tutor.open.get(q.id) or q).get('turns') or []))
        return s

    def nxt(sid):
        "The next question: the one fetched ahead, if there is one."
        f = pre.pop(sid, None)
        q = f.result() if f else sessions[sid].next()
        if q: shown.setdefault(sid, []).append(q)
        return q

    def ahead(sid): pre[sid] = ctx.pool.submit(sessions[sid].next)

    def live(sid):
        "The session and its open question, or None when the question is closed (a second click, an old tab)."
        s = get(sid)
        return (s, s.q) if s and s.q and s.q.id in tutor.open else (s, None)

    def keep(q, *es): tl.setdefault(q.id, []).extend(es); return es

    def entries(q): return tl.get(q.id, ())

    def redraw_close(q, add):
        "Put `add` in the close message of `q` in place of its lesson buttons, so a new draw of the page shows the lesson once and no old button."
        for e in tl.get(q.id, ()):
            if 'close' in (getattr(e, 'attrs', {}).get('class') or ''):
                kids = [c for c in e.children if getattr(c, 'attrs', {}).get('id') not in ('teach', 'another')]
                at = next((i for i, c in enumerate(kids) if 'now' in (getattr(c, 'attrs', {}).get('class') or '')), len(kids))
                e.children = (*kids[:at], *add, *kids[at:])

    def past(sid, but=None): return [q for q in shown.get(sid, ()) if q is not but]

    def you_said(q): return next((t['text'] for t in reversed(q.get('turns') or []) if t['who'] == 'you'), '')

    def chosen(q): return {t['text'] for t in q.get('turns') or () if t['who'] == 'you'}

    def crumbs(s):
        "Today, then the walk of the session, if it has one."
        j = lr.journey(s.journey) if s and s.journey else None
        return [('Today', '/'), *([(j.title, f'/path/{j.id}')] if j else [])]

    def start(subject:str='', focus:str='', journey:str='', drill:str=''):
        s = Session(tutor, focus=focus or None, subject=subject or None, journey=journey or None, drill=bool(drill))
        sessions[s.id] = s
        ahead(s.id)   # the model writes the first question while the page loads
        return Redirect(at(Routes.page, s.id))

    def layout(s, chat, composer, cur=None, viewing=None):
        "The page: the earlier questions on the left, and one question with the composer on the right."
        rail = ui.Rail(s.id, past(s.id, cur), outcomes, cur, viewing)
        return Page('Learn', Div(rail, Div(chat, composer, cls='main'), cls='session-layout'), wide=True, extra=ui.assets(), on='Learn', crumbs=crumbs(s))

    def page(sid:str, q:str=''):
        s, cur = live(sid)
        if not s: return Redirect('/learning')
        if s.ended: return Redirect(at(Routes.end, sid))
        if q and (old := next((x for x in shown.get(sid, ()) if x.id == q and x is not cur), None)):
            return layout(s, ui.Chat(sid, viewing=(old, entries(old))), Div(id='composer'), cur, viewing=q)
        if not cur or sid in pre:   # the question fetched ahead is not on the page yet
            if sid not in pre: ahead(sid)
            wait([pre[sid]], timeout=.5)
            if not pre[sid].done(): return layout(s, ui.Chat(sid, waiting=True), ui.Composer(sid))
            if not (cur := nxt(sid)): return Redirect(at(Routes.end, sid))
        return layout(s, ui.Chat(sid, (cur, entries(cur))), ui.Composer(sid, cur), cur)

    def over(sid): return Response(headers={'HX-Redirect': at(Routes.end, sid)})

    def card(sid:str):
        "The section that `Waiting` loads; it waits for the question that is fetched ahead."
        s, q = live(sid)
        if not s: return ui.Done()
        if not (q and sid not in pre): q = nxt(sid)
        return (ui.Section_(sid, q, entries(q)), ui.Composer(sid, q, oob=True)) if q else over(sid)

    def answer(sid:str, answer:str='', thinking:str='', confidence:int=None):
        s, q = live(sid)
        if not q: return Response(status_code=204)
        try: r = s.answer(answer, thinking, confidence)
        except KeyError:
            if q.id in tutor.open: raise   # a real error, not a closed question
            return Response(status_code=204)   # another request closed it while this one waited
        you = ui.You(you_said(q) or answer, thinking, confidence)
        opts = (ui.Options(sid, q, chosen(q), done=r.done, oob=True, right=r.correct and you_said(q)),) if q.get('options') else ()
        if not r.done:
            return (*keep(q, you, ui.Nudge(r)), *opts, ui.Left(r.tries_left, hx_swap_oob='true'),
                    ui.Out(sid, q, oob=True))
        ahead(sid); outcomes[q.id] = r.outcome
        return (*keep(q, you, ui.Close(r, sid=sid, qid=q.id), *ui.Extras(r)), *opts, ui.Composer(sid, ready=False, oob=True))

    def giveup(sid:str, dont_know:int=0, confidence:int=None):
        s, q = live(sid)
        if not q: return Response(status_code=204)
        tried = bool(q.tries)
        try: r = s.answer(dont_know=True, confidence=confidence) if dont_know and not tried else s.give_up()
        except KeyError:
            if q.id in tutor.open: raise
            return Response(status_code=204)
        ahead(sid); outcomes[q.id] = r.outcome
        opts = (ui.Options(sid, q, chosen(q), done=True, oob=True),) if q.get('options') else ()
        you = ui.You('Teach me.' if tried else "I don't know.")
        return (*keep(q, you, ui.Close(r, sid=sid, qid=q.id), *ui.Extras(r)), *opts, ui.Composer(sid, ready=False, oob=True))

    def hint(sid:str):
        s, q = live(sid)
        if not q: return Response(status_code=204)
        if len(q.hints) >= len(HINTS): return Li(Span('No more hints', cls='lbl'), P('Send your best answer, or ask the tutor to teach you.'), cls='m tutor hint')
        try: h = s.hint()
        except KeyError:
            if q.id in tutor.open: raise
            return Response(status_code=204)
        return keep(q, ui.Hint(len(q.hints), h))

    def teach(sid:str, qid:str, another:int=0):
        "A lesson when you ask for it, or the same idea in another way; the outcome stays as it is."
        s = get(sid)
        if not s or qid not in tutor.shut: return Response(status_code=204)
        lesson = s.teach(qid, bool(another))
        sq = tutor.shut[qid]
        out = ui.Lesson(lesson, sq.get('method', '') if another else ''), Feedback('lesson', aid=sq.get('aid', ''), way=sq.get('method', '')), ui.AnotherWay(sid, qid)
        if (q := next((x for x in shown.get(sid, ()) if x.id == qid), None)): redraw_close(q, out)
        return out

    def ready(sid:str):
        f = pre.get(sid)
        return ui.Ready(sid, not f or f.done())

    def next_(sid:str):
        if not (s := get(sid)): return ui.Done()
        s, q = live(sid)
        if q and sid not in pre: return Response(status_code=204)   # a second press: this question is on the page
        q = nxt(sid)
        if not q: return over(sid)
        rail = ui.Rail(sid, past(sid, q), outcomes, q, oob=True)
        return ui.Section_(sid, q), ui.Composer(sid, q, oob=True), rail

    def end(sid:str):
        "End the session, and show what moved and what comes next."
        if (f := pre.pop(sid, None)): f.cancel()
        s = get(sid)
        if not s: return Page('Session', H1('No such session'), P('It is not on the shelf.', cls='mute'), on='Learn', crumbs=[('Today', '/')])
        if not s.ended: s.end()
        sessions.pop(sid, None)
        for q in shown.pop(sid, ()): tl.pop(q.id, None); outcomes.pop(q.id, None)   # get() builds them again from the shelf
        j = lr.journey(s.journey) if s.journey else None
        by = {c.slug: c for c in lr.concepts()}
        nxt_ = progress(lr, j, by=by) if j else None
        last = s.log[-1]['concept'] if s.log else s.focus
        rel = [] if j else related(lr, last, 4, by=by) if last else []
        return Page('Session', *ui.EndPage(s, moved(s.log), j, nxt_, rel), on='Learn', crumbs=crumbs(s), extra=ui.assets())

    @hook('today_next')
    def start_here(subject=None):
        cs, now = ctx.learning.concepts(subject), time.time()
        n = sum(1 for c in cs if c.seen and c.due and c.due <= now)
        p = None if n else pick(ctx.learning.concepts(), subject=subject)
        said = (f"Review: {n_of(n, 'idea')} {'is' if n == 1 else 'are'} due.",) if n else \
               (f"Next: {DEPTHS[p[1]]} {p[0].name}. ", Span(plain_why(p[2]), cls='why')) if p else ('Nothing is due. Start something new, or pick a concept.',)
        return Div(P(*said, cls='review-line'),
                   Form(Input(type='hidden', name='subject', value=subject or ''),
                        Primary(f"Start{' ' + subject if subject else ''}", data_wait='Starting…', focus=True, rank=3), action=Routes.start, method='post'),
                   cls='review')

    @hook('concept_actions')
    def learn_this(c):
        return Form(Input(type='hidden', name='focus', value=c.slug), Primary('Learn this', data_wait='Starting…'), action=Routes.start, method='post')

    app.post(Routes.start)(start)
    app.get(Routes.start)(start)   # a plain link can start a session too: Continue in the top bar, a step of a path
    app.get(Routes.page)(page)
    app.get(Routes.card)(card)
    app.get(Routes.ready)(ready)
    app.post(Routes.answer)(answer)
    app.post(Routes.giveup)(giveup)
    app.post(Routes.hint)(hint)
    app.post(Routes.teach)(teach)
    app.post(Routes.next)(next_)
    app.get(Routes.end)(end)
