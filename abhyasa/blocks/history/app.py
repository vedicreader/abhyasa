"Your learning: past sessions with what moved, what you learned each week, and Continue: in the top bar and on Today."
import time
from fastcore.basics import AttrDict
from fasthtml.common import *
from abhyasa.core import n_of, moved_words, Page, RouteOverrides, hook, run, ago, Empty
from abhyasa.settings import val
from abhyasa.tutor import moved
from abhyasa.journey import progress, parent_step, for_talk
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
        "Concept names by slug, and walks by id: to name a session."
        return {c.slug: c for c in lr.concepts()}, {j.id: j for j in lr.journeys()}

    def opener(j, js):
        "For a side walk: the walk and the step that opened it, so Continue goes back to the paper. Else (None, None)."
        return parent_step(lr, j, js) if j and j.get('depth') else (None, None)

    def title(s, by, js):
        "What a session was about: its walk (for a side walk, the walk that opened it), its concept, its subject, or its concepts."
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
        groups, lead = {}, True   # the newest open session has the one Continue button
        for s in ss:
            log = s.get('log')
            if not (len(log) if log is not None else s.get('asked', 0)) and (log is None or s.get('ended')): continue   # no answers and not open: nothing to show
            day = ago(day0(s.get('start') or s.get('updated') or 0) + 1).replace(' at 00:00', '')
            day = day[:1].upper() + day[1:]
            first = lead and log is not None and not s.get('ended')
            lead = lead and not first
            groups.setdefault(day, []).append(ui.Row(s, title(s, by, js), moved(s.get('log') or []), back(s, js), lead=first))
        wk = week()
        ups = sum(len(ms) for w, ms in weeks([s for s in ss if (s.get('start') or 0) > time.time() - 7 * DAY], by))
        top = run('learning_top')
        if not groups and not any(n for _, n in wk) and not top:
            return Page('Your learning', ui.css(), H1('Your learning'), Empty('Nothing yet. Do a walk or a review.'), *run('learning_end'), on='You', sub='Your learning')
        return Page('Your learning', ui.css(), H1('Your learning'),
                    P('Each session, with what moved. Open one to read it again or to continue it.', cls='mute'),
                    H2('This week'), ui.Week(wk),
                    P(f"{n_of(sum(n for _, n in wk), 'question')} in the last seven days · {n_of(ups, 'concept')} moved up.", cls='mute week-sum'),
                    *top, H2('What you learned'), ui.Learned(weeks(ss, by)),
                    ui.Runs(list(groups.items())), *run('learning_end'), on='You', sub='Your learning')

    def one(sid:str):
        s = lr.session(sid)
        if not s: return Page('Session', H1('No such session'), P(A('Your learning', href=Routes.base)), on='You', crumbs=[*up, ('Your learning', Routes.base)])
        by, js = names()
        log, ms = s.get('log') or [], moved(s.get('log') or [])
        by_q = {}
        for x in sorted(lr.attempts(session=sid, limit=1000), key=lambda x: x.at): by_q.setdefault((x.concept, x.question), []).append(x)   # oldest first
        own = lambda r: (by_q.get((r['concept'], r['question'])) or [None]).pop(0)   # each log row takes its own attempt, in order
        missed = [m['concept'] for m in ms if m['passed'] < m['asked']]
        acts = [ui.Primary('Continue', href=back(s, js)) if is_open(s) else '',
                A('Review the misses', href=f"{Routes.start}?focus={missed[0]}", cls='btn') if missed else '',
                A('Continue the walk', href=back(s, js) if s.journey in js and js[s.journey].get('mode') == 'walk' else f"{Routes.start}?journey={s.journey}", cls='btn') if s.get('journey') and s.journey in js and not is_open(s) else '']
        return Page('Session', ui.css(), H1(title(s, by, js)),
                    P(f"{ago(s.get('start'))} · {sum(r['correct'] for r in log)} of {len(log)} passed" + (' · open' if is_open(s) else ''), cls='mute'),
                    Div(*acts, cls='row') if any(acts) else '',
                    *([H2('What moved'), Ul(*[Moved(m) for m in ms], cls='plain')] if ms else []),
                    H2('The questions'), *([ui.Question(r, own(r)) for r in log] if log else [P(s.get('summary') or 'No questions.', cls='mute')]),
                    on='You', crumbs=[*up, ('Your learning', Routes.base)])

    def used_at(j):
        "When you last used walk `j`: the idea that you were on, an idea that you read or closed, Open in Leela, or the start. Else the time of its last change."
        ts = [j.get('started') or 0, (j.get('here') or {}).get('at') or 0]
        for s in j.get('steps') or ():
            d = s.get('done')
            ts += [s.get('read_at') or 0, s.get('leela_at') or 0, (d.get('at') or 0) if isinstance(d, dict) else 0]
        return max(ts) or j.get('updated') or 0

    def newest():
        """The place that you used last, or None: the newest open session, or a walk that is not finished and that you used after it.
        Each has `title`, `href`, `at` (the time that you used it) and `done` (what was done there)."""
        by, js = names()
        best = None
        if (s := latest_open()):
            j = js.get(s.get('journey') or '')
            pg = j and j.get('mode') == 'walk' and progress(lr, opener(j, js)[0] or j, by=by)   # a walk says its ideas, not questions
            best = AttrDict(title=title(s, by, js), href=back(s, js), at=s.get('updated') or s.get('end') or s.get('start') or 0,
                            done=f"{pg.done} of {n_of(pg.total, 'idea')}" if pg else n_of(len(s.get('log') or []), 'question') + ' done')
        for j in js.values():   # the newest change first: a use of a walk changes it, so a walk with an older change was not used later
            if best and (j.get('updated') or 0) <= best.at: break
            if for_talk(j) or best and used_at(j) <= best.at: continue   # a side walk of a talk is for the room
            if (pg := progress(lr, j, by=by)).current:
                best = AttrDict(title=j.title, href=f'/w/{j.id}' if j.get('mode') == 'walk' else f"{Routes.start}?journey={j.id}", at=used_at(j),
                                done=f"{pg.done} of {n_of(pg.total, 'idea')}")
        return best

    @hook('nav_extra')
    def continue_link():
        "Continue where you stopped: the place that you used last, an open session or a walk that is not finished."
        if (p := newest()): return ui.Continue(p.title, p.href)

    @hook('today_top')
    def continue_card(subject=None):
        if not (p := newest()): return None
        return ui.css(), ui.Continue(p.title, p.href, big=True, done=p.done, at=p.at)   # the card style is in history.css

    RouteOverrides.nav.append(('You', Routes.base, 3))
    RouteOverrides.subtabs.setdefault('You', []).append(('Your learning', Routes.base, 0))
    app.get(Routes.base)(index)
    app.get(Routes.one)(one)
