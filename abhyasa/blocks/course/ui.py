"The course page and its parts: the goal, You are here, the next idea and why, the stages, what blocks the goal, the sources, your data, and Where you start."
import json
from pathlib import Path
from urllib.parse import urlencode
from fasthtml.common import *
from abhyasa.core import asset_css, Primary, Secondary, Quiet, Part, Empty, n_of, run as run_hook, JobStop, JobAgain
from abhyasa.path import ANSWERS, level_done, stage_stays
from .cfg import Routes

_P = Path(__file__).parent
STATE = dict(done='done', ready='ready', planned='planned', building='abhyasa plans it now', skipped='skipped', known='known (learned elsewhere)')
SOURCE = dict(ready='ready', filing='filing', failed='failed', unknown='no record')
PLANNING = 'abhyasa plans the stages of your course. This takes about half a minute.'
ASKING = 'The tutor writes a few short questions.'
BUILDING = 'abhyasa plans the ideas of this stage. This takes about half a minute.'
FIXING = 'abhyasa plans again each stage that you did not lock or start. This takes about half a minute.'
FIX_SAY = 'Lock each stage that is good. Fix the rest plans again each stage that you did not lock or start.'
LOCK_SVG = NotStr('<svg viewBox="0 0 12 14" width="10" height="12" aria-hidden="true"><rect x="1" y="6" width="10" height="7.5" rx="1.5" fill="currentColor"/>'
                  '<path d="M3.5 6V4a2.5 2.5 0 0 1 5 0v2" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>')
DATA_SAY = 'The exercises in Leela run on the files in these folders. abhyasa does not file them and does not learn from them.'

DROP_SAYS = 'Delete this course? Its walks stay, with your answers and what you learned. Each walk shows on Home by itself.'

def assets(): return (asset_css(_P/'course.css'),)

def CourseMenu(c):
    "The ⋯ menu of a course, on its page and on its row on Home: Delete this course, with one confirm in place. The form posts, then Home opens."
    drop = Details(Summary('Delete this course', cls='small'),
                   Form(P(DROP_SAYS), Div(Button('Delete the course', cls='small danger', data_act='drop-course'), cls='row'),
                        action=Routes.of_(Routes.drop, cid=c['id']), method='post', hx_boost='false', cls='drop-confirm'), cls='drop-walk')
    return Details(Summary('⋯', title='More for this course', aria_label='More for this course'), Div(drop, cls='menu-items'), cls='more-menu walk-menu course-menu')

def at(cid): return Routes.of_(Routes.one, cid=cid)

def href(go, cid) -> str:
    "The link of a `go` of `next_up`: a step, a review session, a stage, or the course page."
    k = (go or {}).get('kind')
    if k == 'step': return Routes.of_(Routes.step, jid=go['walk'], i=go['step'])
    if k == 'review': return f"{Routes.start}?{urlencode(dict(focus=go['slug']))}"
    if k == 'stage': return Routes.of_(Routes.stage, cid=cid, key=go['key'])
    return at(cid)

def Bar(done, total):
    "A thin progress line."
    return Span(I(style=f"width:{100 * done // max(total, 1)}%"), cls='course-bar', role='progressbar', aria_valuenow=str(done), aria_valuemax=str(total))

def Here(st):
    "You are here: the stage and the idea."
    h = st.here
    if h: return P(f"Stage {h.stage} of {len(st.stages)}, idea {h.n} of {h.of}: ", B(h.name), '.', cls='course-here')
    if st.finished: return P('You finished all the stages.', cls='course-here')
    if st.current: return P(f"Stage {st.current.n} of {len(st.stages)}: ", B(st.current['name']), '.', cls='course-here')
    return P('The course has no stage yet.', cls='course-here')

def why_once(st) -> str:
    "The reason of the next thing, without \"Next: X.\" when X is the idea of You are here."
    nx, pre = st.next, f"Next: {st.next.name}. "
    return nx.why[len(pre):] if st.here and nx.slug == st.here.slug and nx.why.startswith(pre) else nx.why

def Next(st, cid):
    "The next thing to do, its reason in one line, and the one main button."
    if not st.stages: return Div(P('Answer the questions of Where you start. Then abhyasa plans the stages.', cls='course-why'), cls='course-next')   # not "You reached your goal"
    nx = st.next
    btn = '' if nx.rule == 8 else Primary('Continue', href=href(nx.go, cid), focus=True, rank=1, data_act='continue')
    return Div(P(why_once(st), cls='course-why'), Div(btn, cls='row') if btn else '', cls='course-next')

def StageLock(r, cid):
    "The quiet Lock toggle of a stage: Keep this stage. A replan and Fix the rest do not change a locked stage."
    on = bool(r.get('locked'))
    return Quiet('Locked' if on else 'Lock', small=True, type='button', data_act='lock', aria_pressed='true' if on else 'false',
                 title='Unlock this stage' if on else 'Keep this stage: a new plan does not change it', hx_post=Routes.of_(Routes.lock, cid=cid),
                 hx_vals=json.dumps(dict(key=r['key'], on='' if on else '1')), hx_target='#course-stages', hx_swap='outerHTML')

def Stage(r, cid):
    "One stage: its name (a link to its walk), its lock mark, its state, its progress, what it makes, and its Lock toggle."
    name = A(r['name'], href=Routes.of_(Routes.walk, jid=r.j.id)) if r.j else Span(r['name'])
    count = f" · {r.done} of {n_of(r.total, 'idea')}" if r.state in ('ready', 'done') else f" · about {n_of(r.total, 'idea')}" if r.state == 'planned' else ''
    act = Quiet('Plan it now', href=Routes.of_(Routes.stage, cid=cid, key=r['key']), small=True) if r.state == 'planned' else ''
    why = r.get('why') if r.state in ('skipped', 'planned') else ''
    mark = Span(LOCK_SVG, cls='lock-mark', role='img', aria_label='Locked', title='Locked: a new plan does not change this stage') if r.get('locked') else ''
    return Li(Div(Span(f'{r.n}', cls='k'), name, mark, Span(f" · {STATE.get(r.state, r.state)}{count}", cls='mute'), act, StageLock(r, cid), cls='row'),
              Bar(r.done, r.total) if r.state in ('ready', 'done') else '',
              P(f"Makes: {r['makes']}", cls='mute') if r.get('makes') else '', P(why, cls='mute') if why else '',
              cls=f"course-stage {r.state}")

def Stages(st, cid):
    "The stages, each with its Lock toggle, then Fix the rest: it plans again each stage that you did not lock or start. It does not show when there is none."
    n = sum(not stage_stays(r, r.j, fix=True) for r in st.stages)
    fix = Div(Quiet('Fix the rest', small=True, type='button', data_act='fix', hx_post=Routes.of_(Routes.fix, cid=cid), hx_target='#course-level', hx_swap='outerHTML',
                    hx_confirm=f"Fix the rest plans again the stages that you did not lock or start: {n_of(n, 'stage')}. Your walks stay on Home."),
              Span(FIX_SAY, cls='mute'), cls='row course-fix') if n else ''
    return Part('Stages', Ol(*[Stage(r, cid) for r in st.stages], cls='plain course-stages'), fix, id='course-stages')

def Act(b, st, cid):
    "The one action of a row: a link, or for a data name with no folder, Set it, which opens the folder setter in place (from the add block)."
    if b.get('data') and (got := run_hook('data_setter', b.data, b.walk, closed=True)): return got[0]
    return A(b.act, href=href(b.go, cid) if b.go else href(st.next.go, cid))

def Blocking(st, cid):
    "What stands between you and the goal: one line and at most one action for each row."
    rows = [Li(b.line, *((' ', Act(b, st, cid)) if b.act else ()), cls=f'course-block {b.kind}') for b in st.blocking]
    return Part('What stands between you and the goal', Ul(*rows, cls='plain') if rows else Empty('Nothing. You reached your goal.' if st.finished else 'Nothing now.'))

def Sources(c):
    "The sources of the course, each with its state."
    name = lambda s: A(s['root'], href=s['href'], **({'target': '_blank', 'rel': 'noopener'} if str(s['href']).startswith('http') else {})) if s.get('href') else B(s['root'])
    rows = [Li(name(s), Span(f" · {s['kind']} · {SOURCE.get(s.get('status'), s.get('status'))}" + (f" · {n_of(s['count'], 'document')}" if s.get('count') else ''), cls='mute'),
               *([Span(' · ', A('the page', href=s['page'], target='_blank', rel='noopener'), cls='mute')] if s.get('page') else []),
               P(s['why'], cls='mute') if s.get('status') in ('failed', 'unknown') and s.get('why') else '') for s in c.get('sources') or ()]
    return Part('Sources', Ul(*rows, cls='plain course-sources') if rows else Empty('This course has no sources of its own. The tutor reads your vault.'))

def Data(c, err=''):
    "Your data: the folders that the exercises run on, each with its note and ×, and the field that adds one."
    cid, go = c['id'], dict(hx_target='#course-data', hx_swap='outerHTML')
    rows = [Li(B(d['path']), Span(f" · {d['note']}", cls='mute') if d.get('note') else '',
               Button('×', type='button', cls='x', aria_label=f"Remove {d['path']}", hx_post=Routes.of_(Routes.data_drop, cid=cid), hx_vals=json.dumps(dict(path=d['path'])), **go))
            for d in c.get('data') or ()]
    add = Form(Input(name='path', placeholder='~/path/to/your/data', aria_label='The path of a data folder', autocomplete='off'),
               Input(name='note', placeholder='What is in it (optional)', aria_label='A note on this data', autocomplete='off'),
               Button('Add', cls='quiet small'), hx_post=Routes.of_(Routes.data, cid=cid), cls='course-add', **go)
    return Part('Your data', P(DATA_SAY, cls='mute'), Ul(*rows, cls='plain course-data') if rows else '', add, P(err, cls='req-err') if err else '', id='course-data')

def Made(st):
    if not st.made: return ''
    return Part('What you made', Ul(*[Li(f"Stage {m.stage}: {m.name} · {n_of(m.images, 'image')} from Leela") for m in st.made], cls='plain'))

def Skipped(cid, s):
    "A skipped stage: why you skipped it, and a quiet button that plans its walk anyway."
    return Div(P('You skipped this stage. ' + (s.get('why') or ''), cls='mute'),
               Form(Quiet('Plan it anyway', small=True), action=Routes.of_(Routes.stage, cid=cid, key=s['key']), method='post'),
               P(A('Back to the course', href=at(cid))), cls='course-skipped')

JOB_WORDS = dict(level='Where you start', plan='The stages')   # the job of a course, in the activity chip; another job builds a stage

def Pending(cid, k, said, row=None):
    "A pool job of the course that is still running, with Stop for its job row `row`: the part loads again when the job changes (the event stream), or every 30 seconds."
    return Div(P(said), Div(JobStop(row), cls='row acts') if row is not None else '', cls='course-pending', hx_get=f"{Routes.of_(Routes.job, cid=cid)}?{urlencode(dict(k=k))}", hx_trigger='job, every 30s', hx_swap='outerHTML',
               data_job=f'course:{cid}')

def Ended(cid, k, line, row):
    "A pool job of the course that you stopped: the line, and Do it again for its job row `row`, which loads the part again."
    return Div(P(line, cls='mute'), Div(JobAgain(row), cls='row acts'), cls='course-pending', hx_get=f"{Routes.of_(Routes.job, cid=cid)}?{urlencode(dict(k=k))}",
               hx_trigger='job', hx_swap='outerHTML', data_job=f'course:{cid}')

def _answer(cid, q, a):
    return Button(ANSWERS[a], type='button', cls='small', hx_post=Routes.of_(Routes.answer, cid=cid), hx_vals=json.dumps(dict(key=q['key'], answer=a)),
                  hx_target='#course-level', hx_swap='outerHTML')

def Question(cid, q):
    "One question: Yes, A little or No by a tap, or an answer that you say or type."
    if q.get('answer'):
        return Li(P(q['q'], ' ', Span(ANSWERS[q['answer']] + (' (from what you learned)' if q.get('by') == 'shelf' else ''), cls='course-ans')), cls='course-q done')
    box = Form(Input(type='hidden', name='key', value=q['key']),
               Input(name='answer', id=f"lv-{q['key']}", data_mic='1', placeholder='Or say or type your answer', aria_label=f"Your answer: {q['q']}", autocomplete='off'),
               hx_post=Routes.of_(Routes.answer, cid=cid), hx_target='#course-level', hx_swap='outerHTML', cls='course-say')
    return Li(P(q['q']), Div(*[_answer(cid, q, a) for a in ANSWERS], cls='row'), box, cls='course-q')

def Level(c, err='', pending=None):
    "Where you start: the button that asks, the questions, or what you answered."
    cid, lv = c['id'], c.get('level') or {}
    qs, ask = lv.get('qs') or [], Secondary('Ask me where I start', type='button', hx_post=Routes.of_(Routes.level, cid=c['id']), hx_target='#course-level', hx_swap='outerHTML')
    if pending is not None: body = [pending]
    elif not qs: body = [P('Answer a few short questions. abhyasa uses your answers to plan where the course starts and how many stages it has.', cls='mute'), Div(ask, cls='row')]
    elif not level_done(c): body = [P('Answer each question with a tap, or say it.', cls='mute'), Ol(*[Question(cid, q) for q in qs], cls='plain course-qs')]
    else: body = [Ol(*[Question(cid, q) for q in qs], cls='plain course-qs'),
                  Div(Quiet('Ask me where I start', type='button', hx_post=Routes.of_(Routes.level, cid=cid), hx_target='#course-level', hx_swap='outerHTML'), cls='row')]
    return Section(H2('Where you start'), *body, P(err, cls='req-err') if err else '', id='course-level', cls='course-level')

def Origin(st, back):
    """The line of a course that a rabbit hole opened: where it came from, and the way back. `back` is `(url, name)` of the place.
    When the course is done, the way back is the main button; before that, it is a quiet "Enough: go back"."""
    c, (url, name) = st.course, back
    go = Routes.of_(Routes.back, cid=c['id'])
    if st.finished: return Div(P('You finished this course. Go back to the place where you asked: ', A(name, href=url), '.'),
                               Form(Primary(f'Go back to {name}', type='submit', rank=1, data_act='go-back'), method='post', action=go), cls='course-origin', data_part='origin')
    return Div(P('You are learning ', B(c['title']), ' as its own course, from ', A(name, href=url), '. '),
               Form(Quiet('Enough: go back', type='submit', small=True, data_act='go-back'), method='post', action=go), cls='course-origin', data_part='origin')

def CoursePage(st, level, back=None):
    """The whole course page, in order of weight: the goal, You are here, the next idea, the stages, what blocks the goal, Where you start, the sources, your data.
    A course with no stage puts Where you start first. A course from a rabbit hole has its origin line under the goal (`back`)."""
    c = st.course
    first = not c.get('stages')
    return (Div(H1(c['title']), CourseMenu(c), cls='course-head'), P('Your goal: ', Q(c['goal']), *([' · ', f"You make {c['makes']}."] if c.get('makes') else []), cls='mute'),
            Origin(st, back) if back else '', level if first else '',
            Div(Span('You are here', cls='lbl'), Here(st), P(f"{st.done} of {n_of(st.total, 'idea')} done.", cls='mute'), Bar(st.done, st.total), Next(st, c['id']), cls='course-card'),
            Stages(st, c['id']), Blocking(st, c['id']), Made(st), '' if first else level, Sources(c), Data(c), *assets())

def TodayCard(st):
    "Today's top line for the course of the place that you used last: the course, what comes next and why, and Continue."
    c, nx = st.course, st.next
    return Div(Span('Your course', cls='lbl'), P(A(c['title'], href=at(c['id'])), Span(f"  · {st.done} of {n_of(st.total, 'idea')}", cls='mute')),
               P(nx.why, cls='course-why', data_part='course-why'), Div(Primary('Continue', href=href(nx.go, c['id']), rank=1, data_act='continue'), cls='row') if nx.rule != 8 else '',
               *assets(), cls='course-card today-course', data_part='continue-card')
