"The course page and its parts: the goal, You are here, the next idea and why, the stages, what blocks the goal, the sources, and Where you start."
import json
from pathlib import Path
from urllib.parse import urlencode
from fasthtml.common import *
from abhyasa.core import asset_css, Primary, Secondary, Quiet, Part, Empty, n_of
from abhyasa.course import ANSWERS, level_done
from .cfg import Routes

_P = Path(__file__).parent
STATE = dict(done='done', ready='ready', planned='planned', building='abhyasa plans it now', skipped='skipped', known='known (learned elsewhere)')
SOURCE = dict(ready='ready', filing='filing', failed='failed')
PLANNING = 'abhyasa plans the stages of your course. This takes about half a minute.'
ASKING = 'The tutor writes a few short questions.'
BUILDING = 'abhyasa plans the ideas of this stage. This takes about half a minute.'

def assets(): return (asset_css(_P/'course.css'),)

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
    nx = st.next
    btn = '' if nx.rule == 8 else Primary('Continue', href=href(nx.go, cid), focus=True, rank=1)
    return Div(P(why_once(st), cls='course-why'), Div(btn, cls='row') if btn else '', cls='course-next')

def Stage(r, cid):
    "One stage: its name (a link to its walk), its state, its progress, what it makes."
    name = A(r['name'], href=Routes.of_(Routes.walk, jid=r.j.id)) if r.j else Span(r['name'])
    count = f" · {r.done} of {n_of(r.total, 'idea')}" if r.state in ('ready', 'done') else f" · about {n_of(r.total, 'idea')}" if r.state == 'planned' else ''
    act = Quiet('Plan it now', href=Routes.of_(Routes.stage, cid=cid, key=r['key']), small=True) if r.state == 'planned' else ''
    why = r.get('why') if r.state in ('skipped', 'planned') else ''
    return Li(Div(Span(f'{r.n}', cls='k'), name, Span(f" · {STATE.get(r.state, r.state)}{count}", cls='mute'), act, cls='row'),
              Bar(r.done, r.total) if r.state in ('ready', 'done') else '',
              P(f"Makes: {r['makes']}", cls='mute') if r.get('makes') else '', P(why, cls='mute') if why else '',
              cls=f"course-stage {r.state}")

def Stages(st, cid):
    return Part('Stages', Ol(*[Stage(r, cid) for r in st.stages], cls='plain course-stages'))

def Blocking(st, cid):
    "What stands between you and the goal: one line and at most one action for each row."
    rows = [Li(b.line, *((' ', A(b.act, href=href(b.go, cid) if b.go else href(st.next.go, cid))) if b.act else ()), cls=f'course-block {b.kind}') for b in st.blocking]
    return Part('What stands between you and the goal', Ul(*rows, cls='plain') if rows else Empty('Nothing. You reached your goal.' if st.finished else 'Nothing now.'))

def Sources(c):
    "The sources of the course, each with its state."
    rows = [Li(B(s['root']), Span(f" · {s['kind']} · {SOURCE.get(s.get('status'), s.get('status'))}" + (f" · {n_of(s['count'], 'document')}" if s.get('count') else ''), cls='mute'),
               P(s['why'], cls='mute') if s.get('status') == 'failed' and s.get('why') else '') for s in c.get('sources') or ()]
    return Part('Sources', Ul(*rows, cls='plain course-sources') if rows else Empty('This course has no sources of its own. The tutor reads your vault.'))

def Made(st):
    if not st.made: return ''
    return Part('What you made', Ul(*[Li(f"Stage {m.stage}: {m.name} · {n_of(m.images, 'image')} from Leela") for m in st.made], cls='plain'))

def Skipped(cid, s):
    "A skipped stage: why you skipped it, and a quiet button that plans its walk anyway."
    return Div(P('You skipped this stage. ' + (s.get('why') or ''), cls='mute'),
               Form(Quiet('Plan it anyway', small=True), action=Routes.of_(Routes.stage, cid=cid, key=s['key']), method='post'),
               P(A('Back to the course', href=at(cid))), cls='course-skipped')

def Pending(cid, k, said):
    "A pool job of the course that is still running: the part asks the server again in 2 seconds."
    return Div(P(said), cls='course-pending', hx_get=f"{Routes.of_(Routes.job, cid=cid)}?{urlencode(dict(k=k))}", hx_trigger='load delay:2s', hx_swap='outerHTML')

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

def CoursePage(st, level):
    "The whole course page, in order of weight: the goal, You are here, the next idea, the stages, what blocks the goal, Where you start, the sources."
    c = st.course
    return (H1(c['title']), P('Your goal: ', Q(c['goal']), *([' · ', f"You make {c['makes']}."] if c.get('makes') else []), cls='mute'),
            Div(Span('You are here', cls='lbl'), Here(st), P(f"{st.done} of {n_of(st.total, 'idea')} done.", cls='mute'), Bar(st.done, st.total), Next(st, c['id']), cls='course-card'),
            Stages(st, c['id']), Blocking(st, c['id']), Made(st), level, Sources(c), *assets())

def TodayCard(st):
    "Today's top line for the course of the place that you used last: the course, what comes next and why, and Continue."
    c, nx = st.course, st.next
    return Div(Span('Your course', cls='lbl'), P(A(c['title'], href=at(c['id'])), Span(f"  · {st.done} of {n_of(st.total, 'idea')}", cls='mute')),
               P(nx.why, cls='course-why', data_part='course-why'), Div(Primary('Continue', href=href(nx.go, c['id']), rank=1, data_act='continue'), cls='row') if nx.rule != 8 else '',
               *assets(), cls='course-card today-course', data_part='continue-card')
