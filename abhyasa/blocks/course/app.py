"""The course: one page for each goal, with where you are, what comes next and why, the stages, what blocks the goal, the sources,
your data and "Where you start". It adds the course line to Today (`today_top`), keeps your place from each step of a course walk (`step_needs`),
links a course walk to its course (`walk_actions`, `walk_end`), and joins a new goal walk to its course (`goal_walk`)."""
import logging, re
from fasthtml.common import *
from abhyasa.core import Page, NotFound, hook, run as run_hook
from abhyasa.core.leela import leela_base
from abhyasa.jobs import track, seen_jobs
from abhyasa.profile import profile_text
from abhyasa.journey import last_place, parent_at
from abhyasa.core import is_local
from abhyasa.course import (course_state, join_course, course_of, ensure_courses, ask_level, answer_level, level_done, plan_stages,
                            build_stage, due_stage, set_here, add_ask, is_goal_walk, add_data, drop_data, lock_stage, go_back)
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask', 'pool', 'sources')
log = logging.getLogger(__name__)

def connect(app, ctx):
    lr, ask = ctx.learning, ctx.ask
    up = [('Home', '/')]
    jobs = {}   # (course, kind) -> AttrDict(job, said): one pool job of each kind for each course

    def who(): return profile_text(lr.profile())

    def submit(cid, k, said, f, *a):
        "Start the pool job `k` of course `cid`, unless one runs, with its job row. The job."
        st = jobs.get((cid, k))
        if not st or st.job.done():
            c = lr.course(cid)
            what = ui.JOB_WORDS.get(k) or first(s['name'] for s in c.get('stages') or () if s['key'] == k) or 'A stage'
            stage = k not in ui.JOB_WORDS   # a stage build makes a walk: the row links to it when it is ready
            st = jobs[cid, k] = AttrDict(said=said, job=track(lr, f'course:{cid}:{k}', ctx.pool.submit(f, *a), 'course', title=f'{c.title}: {what}', said=said,
                                                            url=ui.at(cid), obj=f'course:{cid}', why=lambda e: 'abhyasa could not do it. Try again.',
                                                            ok=(lambda jid: dict(url=Routes.of_(Routes.walk, jid=jid), obj=f'walk:{jid}')) if stage else None))
        return st

    def running(cid, k) -> bool:
        "Whether the job `k` of course `cid` runs now, from its job row."
        return (r := lr.job(f'course:{cid}:{k}')) is not None and r.state == 'running' and (cid, k) in jobs

    def build(cid, key):
        "On the pool: make the walk of stage `key`, then let the walk block look for its sources (`walk_made`)."
        j = build_stage(lr, ask, cid, key, ctx.sources, who())
        run_hook('concepts_added'); run_hook('walk_made', j)
        return j.id

    def grow(c):
        "Start the job that builds the stage that is due (the current one with no walk, or the next one at 60%). Never in a request."
        if c and (key := due_stage(lr, c)) and not running(c.id, key): submit(c.id, key, ui.BUILDING, build, c.id, key)

    def plan_then_build(cid, fix=False):
        "On the pool: plan the stages from your answers (with `fix`, each stage that is not locked), then build the current stage when it has no walk."
        c = plan_stages(lr, ask, cid, who(), fix=fix)
        if (key := due_stage(lr, c)) and first(s for s in c.stages if s['key'] == key and not s.get('walk')) and lr.course(cid):
            try: build(cid, key)
            except Exception as e: log.warning('abhyasa could not build stage %s of %s: %r', key, cid, e)
        return cid

    def missing(): return NotFound('Course', H1('No such course'), P(A('Home', href='/')), on='Home', crumbs=up)

    def state(cid): return course_state(lr, cid, leela=leela_base() is not None)

    def one(cid:str):
        if not (st := state(cid)): return missing()
        seen_jobs(lr, f'course:{cid}')
        grow(st.course)
        pend = ui.Pending(cid, 'level', jobs[cid, 'level'].said) if running(cid, 'level') else ui.Pending(cid, 'plan', ui.PLANNING) if running(cid, 'plan') else None
        return Page(st.course.title, *ui.CoursePage(st, ui.Level(st.course, pending=pend), origin(st.course)), on='Home', crumbs=up)

    def origin(c):
        "The place that opened course `c` as a rabbit hole, as `(url, name)`: the step (found by its concept), or the local page. None for another course."
        o = c.get('origin') or {}
        if (pj := lr.journey(o['walk']) if isinstance(o.get('walk'), str) else None) and (i := parent_at(pj, o)) is not None:
            return Routes.of_(Routes.step, jid=pj.id, i=i), f"{pj.title}, idea {i + 1}"
        if is_local(o.get('page')): return o['page'], o.get('title') or 'the page'
        return None

    def enough(cid:str):
        "Enough: keep the time that you went back, then go to the place that opened the course."
        if not (c := lr.course(cid)) or not (b := origin(c)): return Response(status_code=404)
        go_back(lr, cid)
        return Redirect(b[0])

    def level(cid:str):
        "Write the questions of Where you start on the pool. The part asks again until they come."
        if not (c := lr.course(cid)): return Response(status_code=404)
        st = submit(cid, 'level', ui.ASKING, ask_level, lr, ask, cid, who())
        return ui.Level(c, pending=ui.Pending(cid, 'level', st.said))

    def answer(cid:str, key:str='', answer:str=''):
        "Keep one answer. With the last answer, plan the stages on the pool."
        if not (c := lr.course(cid)): return Response(status_code=404)
        try: c = answer_level(lr, cid, key, answer)
        except (KeyError, ValueError) as e: return ui.Level(c, err=str(e) if isinstance(e, ValueError) else 'This question is not there now.')
        if not level_done(c): return ui.Level(c)
        submit(cid, 'plan', ui.PLANNING, plan_then_build, cid)
        return ui.Level(c, pending=ui.Pending(cid, 'plan', ui.PLANNING))

    def open_stage(cid, key, plan):
        "Open the walk of stage `key`; a stage with no walk is built on the pool first. A GET does not build a skipped stage: it offers Plan it anyway."
        if not (c := lr.course(cid)) or not (s := first(s for s in c.stages if s['key'] == key)): return missing()
        if s.get('walk') and lr.journey(s['walk']): return Redirect(Routes.of_(Routes.walk, jid=s['walk']))
        crumbs = [*up, (c.title, ui.at(cid))]
        if s.get('status') == 'skipped' and not plan and not running(cid, key):
            return Page(s['name'], H1(s['name']), ui.Skipped(cid, s), on='Home', crumbs=crumbs)
        st = submit(cid, key, ui.BUILDING, build, cid, key)
        return Page(s['name'], H1(s['name']), ui.Pending(cid, key, st.said), on='Home', crumbs=crumbs)

    def stage(cid:str, key:str): return open_stage(cid, key, plan=False)
    def plan_stage(cid:str, key:str): return open_stage(cid, key, plan=True)

    def job(cid:str, k:str=''):
        "The state of the pool job `k` of course `cid`: the pending part, the result, or a plain line."
        if not (c := lr.course(cid)): return Response(status_code=404)
        st = jobs.get((cid, k))
        if st is None: return ui.Level(c) if k in ('level', 'plan') else Response(headers={'HX-Redirect': ui.at(cid)})
        if not st.job.done(): return ui.Pending(cid, k, st.said)
        if (e := st.job.exception()):
            log.warning('the course job %s of %s failed: %r', k, cid, e)
            if k == 'level': return ui.Level(c, err='The tutor could not write the questions. Try again.')
            if k == 'plan': return ui.Level(c, err='abhyasa could not plan the stages. Try again.')
            return Div(P('abhyasa could not plan this stage. Try again.', cls='req-err'), P(A('Back to the course', href=ui.at(cid))))
        if k == 'level': return ui.Level(lr.course(cid))
        if k == 'plan': return Response(headers={'HX-Redirect': ui.at(cid)})
        return Response(headers={'HX-Redirect': Routes.of_(Routes.walk, jid=st.job.result())})

    def lock(cid:str, key:str='', on:str=''):
        "Lock stage `key` (`on`), or unlock it. A replan and Fix the rest keep a locked stage as it is."
        if not lr.course(cid): return Response(status_code=404)
        try: lock_stage(lr, cid, key, bool(on))
        except KeyError: return Response('This stage is not there now.', status_code=404)
        return ui.Stages(state(cid), cid)

    def fix(cid:str):
        "Fix the rest: plan again each stage that you did not lock or start, on the pool. The locked stages, the stages that you started, and their walks stay."
        if not (c := lr.course(cid)): return Response(status_code=404)
        st = submit(cid, 'plan', ui.FIXING, plan_then_build, cid, True)
        return ui.Level(c, pending=ui.Pending(cid, 'plan', st.said))

    def data(cid:str, path:str='', note:str=''):
        "Keep the folder `path` as your data on the course and its walks. It is not filed."
        if not lr.course(cid): return Response(status_code=404)
        try: return ui.Data(add_data(lr, cid, path, note))
        except ValueError as e: return ui.Data(lr.course(cid), err=str(e))

    def data_drop(cid:str, path:str=''):
        "Remove one data folder from the course and its walks. The folder stays on the disk."
        return ui.Data(drop_data(lr, cid, path)) if lr.course(cid) else Response(status_code=404)

    @hook('goal_walk')
    def joined(j):
        "The walk block made goal walk `j`: it joins its course."
        try:
            c = join_course(lr, j)
            for d in (lr.journey(j['id']) or {}).get('data') or () if c else ():   # your data from the Start box goes on the course
                if d['path'] not in {x['path'] for x in lr.course(c.id).get('data') or ()}: c = add_data(lr, c.id, d['path'], d.get('note', ''))
            return c
        except Exception as e: log.warning('abhyasa could not join walk %s to a course: %r', j.get('id'), e)

    @hook('step_needs')
    def here(j, i, c):
        "A step of a course walk opened: keep it as the place where you are, and build the next stage when it is due. Nothing on the page."
        if not j.get('course'): return None
        try: grow(set_here(lr, j, i))
        except Exception as e: log.warning('abhyasa could not keep the place in the course: %r', e)
        return None

    @hook('walk_actions')
    def link(j, quiet=False, row=False):
        "A quiet link to the course of a course walk."
        if row or not j.get('course') or not (c := course_of(lr, j['id'])): return None
        return A('Course', href=ui.at(c.id), cls='btn quiet', title=f'The course: {c.title}')

    @hook('walk_end')
    def back(j):
        "The end of a course walk: what comes next in the course."
        if not j.get('course') or not (c := course_of(lr, j['id'])) or not (st := state(c.id)): return None
        return P('This walk is a stage of your course. ', Span(st.next.why, cls='why'), ' ', A('Back to the course', href=ui.at(c.id)), cls='course-end')

    @hook('today_top')
    def today(subject=None):
        "Today's top line when the place that you used last (`last_place`) is in a course walk: what comes next in the course, with its reason, and Continue."
        try: ensure_courses(lr)   # an older goal walk gets its course, one time
        except Exception as e: log.warning('abhyasa could not give a course to the goal walks: %r', e)
        if subject or not (p := last_place(lr)) or not p.get('walk') or not (c := course_of(lr, p.walk)) or not (st := state(c.id)): return None
        return ui.TodayCard(st)

    @hook('guide_board')
    def board(page, b):
        "A board of the screen guide on a step of a course walk: one ask on the course, with no page text. It gives no hint line."
        m = re.fullmatch(r'/w/([^/]+)/(\d+)', str(page or ''))
        if not m or not (j := lr.journey(m[1])) or not j.get('course') or not (c := course_of(lr, j.id)) or not 0 <= int(m[2]) < len(j.steps): return None
        try: add_ask(lr, c.id, 'guide', j.steps[int(m[2])]['slug'], 'board')
        except Exception as e: log.warning('abhyasa could not keep the ask on the course: %r', e)
        return None

    app.get(Routes.job)(job)
    app.post(Routes.data)(data)
    app.post(Routes.data_drop)(data_drop)
    app.post(Routes.lock)(lock)
    app.post(Routes.fix)(fix)
    app.post(Routes.back)(enough)
    app.post(Routes.level)(level)
    app.post(Routes.answer)(answer)
    app.get(Routes.stage)(stage)
    app.post(Routes.stage)(plan_stage)
    app.get(Routes.one)(one)
