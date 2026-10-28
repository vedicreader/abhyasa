"Your learning: past sessions with what moved, what you learned each week, and Continue: in the top bar and on Today."
import time
from fasthtml.common import *
from abhyasa.core import n_of, moved_words, Page, RouteOverrides, hook, ago
from abhyasa.settings import val
from abhyasa.tutor import moved
from abhyasa.journey import progress
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning',)
DAY = 86400

def day0(t):
    "The start of the local day of `t`."
    lt = time.localtime(t)
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))

def Moved(m):
    "One concept of a filed session: what moved, and the count when it adds something."
    said, count = moved_words(m)
    return Li(ui.Move(m) if m['after'] != m['before'] else Span(m['name'], f" {said}"), Span(f"  · {count}", cls='mute') if count else '')

def connect(app, ctx):
    lr = ctx.learning
    up = [('Today', '/')]

    def names():
        "Concept names by slug, and journeys by id: to name a session."
        return {c.slug: c for c in lr.concepts()}, {j.id: j for j in lr.journeys()}

    def opener(j, js):
        "For a side walk: the walk and the step that opened it, so Continue goes back to the paper. Else (None, None)."
        p = (j or {}).get('parent') or {}
        pj = js.get(p.get('walk')) if j and j.get('depth') else None
        return (pj, p.get('step')) if pj and isinstance(p.get('step'), int) else (None, None)

    def title(s, by, js):
        "What a session was about: its journey (for a side walk, the walk that opened it), its concept, its subject, or its concepts."
        if s.get('journey') and (j := js.get(s.journey)): return (opener(j, js)[0] or j).title
        if s.get('focus') and (c := by.get(s.focus)): return c.name
        if s.get('subject'): return f"Review: {s.subject}"
        return ', '.join(by[x].name for x in (s.get('concepts') or [])[:3] if x in by) or 'Review'

    def back(s, js):
        "Where Continue goes: the walk for a sitting of a walk, else the session page."
        j = js.get(s.get('journey') or '')
        pj, i = opener(j, js)
        if pj: return f'/w/{pj.id}/{i}'
        return f'/w/{j.id}' if j and j.get('mode') == 'walk' else Routes.of(Routes.page, sid=s['id'])

    def is_open(s): return s.get('log') is not None and not s.get('ended') and bool(s.get('log') or s.get('open'))

    def latest_open():
        return next((s for s in lr.sessions(30) if is_open(s)), None)

    def week(now=None):
        "Questions answered on each of the last seven days, oldest first."
        t0 = day0(now or time.time())
        n = [0] * 7
        for a in lr.attempts(limit=2000):
            if a.get('final') and a.get('kind') != 'demo' and (k := int((t0 - day0(a.at)) // DAY)) < 7 and k >= 0: n[6 - k] += 1
        return [(time.strftime('%a', time.localtime(t0 - (6 - i) * DAY)), n[i]) for i in range(7)]

    def weeks(ss, by, most=None):
        "For each week, newest first: the concepts that moved up, with the floor before the first session and after the last."
        out = {}
        for s in sorted(ss, key=lambda s: s.get('start') or 0):
            if not s.get('log'): continue
            lt = time.localtime(s['start'])
            wk = time.strftime('Week of %d %b', time.localtime(day0(s['start']) - lt.tm_wday * DAY))
            w = out.setdefault(wk, {})
            for m in moved(s['log']):
                o = w.setdefault(m['concept'], dict(m))
                o['after'] = m['after']
        rows = [(wk, [m for m in w.values() if m['after'] > m['before']]) for wk, w in out.items()]
        return [(wk, ms) for wk, ms in rows[::-1] if ms][:most or val('lists.weeks')]

    def index():
        ss, (by, js) = lr.sessions(500), names()
        groups = {}
        for s in ss:
            day = ago(day0(s.get('start') or s.get('updated') or 0) + 1).replace(' at 00:00', '')
            day = day[:1].upper() + day[1:]
            groups.setdefault(day, []).append(ui.Row(s, title(s, by, js), moved(s.get('log') or []), back(s, js)))
        wk = week()
        ups = sum(len(ms) for w, ms in weeks([s for s in ss if (s.get('start') or 0) > time.time() - 7 * DAY], by))
        return Page('Your learning', ui.css(), H1('Your learning'),
                    P('This page keeps each session, with what moved. Open a session to read its questions again, or to continue it.', cls='mute'),
                    H2('This week'), ui.Week(wk),
                    P(f"{sum(n for _, n in wk)} questions in the last seven days · {n_of(ups, 'concept')} moved up.", cls='mute week-sum'),
                    H2('What you learned'), ui.Learned(weeks(ss, by)),
                    ui.Runs(list(groups.items())), on='Your learning', crumbs=up)

    def one(sid:str):
        s = lr.session(sid)
        if not s: return Page('Session', H1('No such session'), P(A('Your learning', href=Routes.base)), crumbs=[*up, ('Your learning', Routes.base)])
        by, js = names()
        log, ms = s.get('log') or [], moved(s.get('log') or [])
        missed = [m['concept'] for m in ms if m['passed'] < m['asked']]
        acts = [ui.Primary('Continue', href=back(s, js)) if is_open(s) else '',
                A('Review the misses', href=f"{Routes.start}?focus={missed[0]}", cls='btn') if missed else '',
                A('Continue the journey', href=back(s, js) if s.journey in js and js[s.journey].get('mode') == 'walk' else f"{Routes.start}?journey={s.journey}", cls='btn') if s.get('journey') and s.journey in js and not is_open(s) else '']
        return Page('Session', ui.css(), H1(title(s, by, js)),
                    P(f"{ago(s.get('start'))} · {sum(r['correct'] for r in log)} of {len(log)} passed" + (' · open' if is_open(s) else ''), cls='mute'),
                    Div(*acts, cls='row') if any(acts) else '',
                    *([H2('What moved'), Ul(*[Moved(m) for m in ms], cls='plain')] if ms else []),
                    H2('The questions'), *(map(ui.Question, log) if log else [P(s.get('summary') or 'No questions.', cls='mute')]),
                    crumbs=[*up, ('Your learning', Routes.base)])

    @hook('nav_extra')
    def continue_link():
        "Continue where you stopped: the newest open session, else the newest journey that is not finished."
        if (s := latest_open()):
            by, js = names()
            return ui.Continue(s, title(s, by, js), href=back(s, js))
        for j in lr.journeys()[:3]:
            if (pg := progress(lr, j)).current: return A(f'Continue: {j.title}', ui.Kbd('⌥C'), href=f'/w/{j.id}' if j.get('mode') == 'walk' else f"{Routes.start}?journey={j.id}", id='continue')

    @hook('today_top')
    def continue_card(subject=None):
        if not (s := latest_open()): return None
        by, js = names()
        return ui.Continue(s, title(s, by, js), big=True, href=back(s, js))

    @hook('today')
    def this_week(subject=None):
        wk = week()
        if not sum(n for _, n in wk): return None
        return H2('This week'), ui.css(), ui.Week(wk), P(A('Your learning', href=Routes.base), ': what you learned, and each past session.', cls='mute week-sum')

    RouteOverrides.nav.append(('Your learning', Routes.base, 0.7))
    app.get(Routes.base)(index)
    app.get(Routes.one)(one)
