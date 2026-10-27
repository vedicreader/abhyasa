"""The guided walk: a paper, a text or a topic as one idea at a time, in reading order. The plan, the step page, its check,
Next idea, and the summary at the end of each section. A sitting is a `Session` that the walk feeds itself."""
import json, time
from collections import defaultdict
from threading import Lock
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import Page
from abhyasa.llm import for_task
from abhyasa.profile import profile_text
from abhyasa.method import WALK_WAYS, CHECK_KIND, DEPTH
from abhyasa.tutor import Session, HINTS, public, moved
from abhyasa.journey import journey_from_source, journey_from_text, walk_from_topic, walk_state, short_check
from abhyasa.walk import tutor_note, open_short, step_meta
from abhyasa.demo import queue_demo, job_state, job_age
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'tutor', 'ask', 'pool', 'sessions', 'sources')
FIGURES = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
RUN = dict(read_at=None, done=None, qid=None, note=None)   # the run fields of a step (spec 6.3), empty until the step is used
AIM = dict(demo='', order='order')   # check kind -> the aim of its demo
DEMO_WAIT = 90                       # seconds to wait for a demo; then the step uses a short answer
MAX_STATE = 20_000                   # the most chars of a kept demo state

def connect(app, ctx):
    lr, tutor, sessions = ctx.learning, ctx.tutor, ctx.sessions
    ask = lambda prompt, sp='': for_task(ctx.ask, 'extract')(prompt, sp)   # looked up on each call, so a settings change works at once
    up = [('Today', '/'), ('Journeys', '/journeys')]
    writing = defaultdict(Lock)   # (walk, step) -> a lock, so the note and the check of one step do not write the note twice

    def by(): return {c.slug: c for c in lr.concepts()}
    def go(jid, i): return Redirect(ui.at(Routes.step, jid, i))
    def missing(): return Page('Walk', H1('No such walk'), P(A('Your journeys', href='/journeys')), crumbs=up)

    def walk_of(jid, i=None):
        "The walk `jid`, and step `i` when it is there; None for an unknown walk or step."
        j = lr.journey(jid)
        if not j or j.get('mode') != 'walk' or (i is not None and not 0 <= i < len(j.steps)): return None
        return j

    def sitting(j):
        "The open sitting of walk `j`: in memory, else from the shelf, else a new one."
        sid = j.get('sitting')
        s = sid and (sessions.get(sid) or Session.load(tutor, sid))
        if not s or s.ended:
            s = Session(tutor, journey=j.id)
            lr.put_journey({**j, 'sitting': s.id})
        sessions[s.id] = s
        return s

    def question(j, i):
        "The question of the check of step `i`: open, or closed in this run; None when it is gone."
        qid = j.steps[i].get('qid')
        return qid and (tutor.open.get(qid) or tutor.shut.get(qid))

    def demo(s):
        "The demo of step `s` when its check is a demo or an order, else None."
        k = s['check']['kind']
        return lr.demo_for(s['slug'], AIM[k]) if k in AIM else None

    def card(j, i):
        s = j.steps[i]
        k = s['check']['kind']
        return ui.CHECKS.get(k, ui.Short)(j.id, i, s, demo(s) if k in AIM else question(j, i))

    def as_short(j, i):
        "Walk `j` with the check of step `i` as a short answer in a text way, while its own kind has no card (spec 6.5)."
        s = j.steps[i]
        if s['check']['kind'] in ui.CHECKS: return j
        return AttrDict({**j, 'steps': [*j.steps[:i], {**s, 'check': dict(short_check(lr, lr.concept(s['slug'])))}, *j.steps[i + 1:]]})

    def ahead(j, i):
        "Start the demo of step `i` when its check is a demo or an order, it has no outcome, and it has no demo yet (spec 6.5)."
        if not 0 <= i < len(j.steps) or (s := j.steps[i]).get('done') or s['check']['kind'] not in AIM or demo(s): return
        queue_demo(tutor, s['slug'], aim=AIM[s['check']['kind']])

    def no_demo(j, i):
        "The pending card while the demo of step `i` is made; None when the wait is over, so the step uses a short answer."
        s = j.steps[i]
        slug, aim = s['slug'], AIM[s['check']['kind']]
        if job_state(tutor, slug, aim) == 'none': ahead(j, i)
        if job_state(tutor, slug, aim) == 'running' and job_age(tutor, slug, aim) < DEMO_WAIT: return ui.Pending(j.id, i, s)
        lr.walk_step(j.id, i, check=dict(short_check(lr, lr.concept(slug))))

    def no_check(j, i):
        "The reply to a move on a check that is not open: the closed card, or 409 when the check was never loaded."
        if not j: return Response(status_code=404)
        if j.steps[i].get('done'): return card(j, i)
        return Response('No check is open on this idea. Load the page again.', status_code=409)

    def live(jid, i):
        "The sitting with the open question of step `i` as its question, or None when the check is not open."
        if not (j := walk_of(jid, i)) or (qid := j.steps[i].get('qid')) not in tutor.open: return j, None
        s = sitting(j)
        if not s.q or s.q.id != qid: s.q = public(tutor.open[qid])
        return j, s

    def closed(j, i, r):
        "Mark step `i` done with the outcome of its check."
        lr.walk_step(j.id, i, done=dict(outcome=r.outcome, aid=tutor.shut[j.steps[i]['qid']].get('aid'), at=time.time()))
        return card(lr.journey(j.id), i)

    def new(ref:str='', text:str='', title:str='', topic:str=''):
        try:
            if ref.strip(): j = journey_from_source(lr, ask, ref.strip())
            elif text.strip(): j = journey_from_text(lr, ask, text.strip(), title.strip() or text.strip().splitlines()[0][:60])
            elif topic.strip(): j = walk_from_topic(lr, ask, topic.strip(), profile_text(lr.profile()), ctx.sources)
            else: return P('Name a vault document, paste a text, or write a topic.', cls='req-err')
        except Exception as e: return P(f'The tutor could not make a walk ({e}). Try again.', cls='req-err')
        return Response(headers={'HX-Redirect': ui.at(Routes.one, j.id)})

    def one(jid:str):
        if not (j := walk_of(jid)): return missing()
        st = walk_state(j)
        if j.get('started') and st.current is not None: return go(jid, st.current)
        return Page(j.title, *ui.PlanPage(j, st, by()), crumbs=up, extra=ui.assets())

    def plan(jid:str, i:int, act:str, way:str=''):
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        if act == 'drop':
            j.steps.pop(i)
            j = lr.put_journey(j)
        elif act == 'check' and way in WALK_WAYS:
            kind = CHECK_KIND.get(way, 'short')
            floor = (lr.concept(j.steps[i]['slug']) or {}).get('floor') or 0
            j = lr.walk_step(jid, i, check=dict(way=way, kind=kind, depth=(2 if floor < 2 else 3) if kind == 'short' else DEPTH[kind], why='you chose it'))
        else: return Response(status_code=400)
        return ui.Plan(j, walk_state(j), by())

    def start(jid:str):
        if not (j := walk_of(jid)): return missing()
        if not j.get('started'): j = lr.put_journey({**j, 'started': time.time(), 'steps': [{**RUN, **s} for s in j.steps]})
        sitting(j)
        return go(jid, walk_state(lr.journey(jid)).current or 0)

    def step(jid:str, i:int):
        if not (j := walk_of(jid, i)): return missing()
        if not j.steps[i].get('read_at'): j = lr.walk_step(jid, i, read_at=time.time())
        ahead(j, i + 1)
        return Page(ui.name(b := by(), j.steps[i]), ui.StepPage(j, walk_state(j), b, i), wide=True, extra=ui.assets(),
                    crumbs=[*up, (j.title, ui.at(Routes.one, jid))])

    def note(jid:str, i:int):
        "The tutor note of step `i`, loaded after the page; a failed note shows nothing."
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        try:
            with writing[jid, i]: return ui.Note(tutor_note(lr, ctx.ask, j, i))
        except Exception: return ''

    def check(jid:str, i:int):
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        with writing[jid, i]:
            j = lr.journey(jid)
            if not j.steps[i].get('done') and j.steps[i]['check']['kind'] in AIM and not demo(j.steps[i]):
                if (wait := no_demo(j, i)): return wait
                j = lr.journey(jid)
            if not j.steps[i].get('done') and j.steps[i]['check']['kind'] not in AIM and j.steps[i].get('qid') not in tutor.open:
                s = sitting(j)
                s.q = open_short(tutor, as_short(j, i), i, s.id)
                s.save()
        return card(lr.journey(jid), i)

    def answer(jid:str, i:int, answer:str='', thinking:str='', confidence:int=None):
        j, s = live(jid, i)
        if not s: return no_check(j, i)
        r = s.answer(answer, thinking, confidence)
        return closed(j, i, r) if r.done else card(j, i)

    def hint(jid:str, i:int):
        j, s = live(jid, i)
        if not s: return no_check(j, i)
        if len(tutor.open[s.q.id].hints) < len(HINTS): s.hint()
        return card(j, i)

    def giveup(jid:str, i:int, confidence:int=None):
        j, s = live(jid, i)
        if not s: return no_check(j, i)
        r = s.give_up(confidence=confidence or 0) if tutor.open[s.q.id].tries else s.answer(dont_know=True, confidence=confidence)
        return closed(j, i, r)

    def predict(jid:str, i:int, slug:str, gate:str, picked:str, ans:str='', ok:str='', why:str='', context:str='', confidence:int=None):
        "Log the first prediction on each gate in the demo of step `i` with the walk; the first one closes the step (spec 6.5)."
        j = walk_of(jid, i)
        if not j or (s := j.steps[i])['check']['kind'] not in AIM or not (d := lr.demo(slug)) or d.concept != s['slug']:
            return JSONResponse(dict(ok=False), status_code=404)
        if (s.get('done') or {}).get('outcome') == 'skipped': return JSONResponse(dict(ok=False), status_code=409)
        if first(a for a in lr.attempts(s['slug']) if (a.get('walk'), a.get('step'), a.get('gate')) == (jid, i, gate)):
            return JSONResponse(dict(ok=True, again=True))   # one record for each gate: a second try comes after the answer showed
        st, floor0 = sitting(j), lr.concept(s['slug']).get('floor') or 0
        a = lr.record_prediction(slug, gate, picked, ans, ok == 'true', why, context, st.id, confidence,
                                 kind=s['check']['kind'], method=s['check']['way'], **step_meta(j, i))
        st.noted(a, floor0)
        with writing[jid, i]:
            if not lr.journey(jid).steps[i].get('done'): lr.walk_step(jid, i, done=dict(outcome=a.outcome, aid=a.id, at=time.time()))
        return JSONResponse(dict(ok=True))

    def keep(jid:str, i:int, state:str=''):
        "Keep the state of the demo on the newest prediction of step `i`."
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        try: kept = json.loads(state) if len(state) <= MAX_STATE else None
        except ValueError: kept = None
        if kept is None: return Response('The state is not valid.', status_code=400)
        a = first(a for a in lr.attempts(j.steps[i]['slug']) if a.get('walk') == jid and a.get('step') == i and a.get('demo'))
        if not a: return Response('Make a prediction first.', status_code=409)
        lr.mark_attempt(a.id, keep=kept)
        return JSONResponse(dict(ok=True))

    def next_(jid:str, i:int):
        "Skip step `i` when it has no outcome yet, then go to the next step, or to the summary at the end of a section."
        if not (j := walk_of(jid, i)): return missing()
        st = walk_state(j)
        if not j.steps[i].get('done'):
            if (qid := j.steps[i].get('qid')) in tutor.open:
                tutor.open.pop(qid)
                if (s := sessions.get(j.get('sitting') or '')) and s.q and s.q.id == qid: s.q = None; s.save()
            lr.walk_step(jid, i, done=dict(outcome='skipped', at=time.time()))
        ends = any(ix[-1] == i for _, ix in st.sections)
        return Redirect(ui.at(Routes.done, jid, i)) if ends else go(jid, i + 1)

    def done(jid:str, i:int):
        "The summary of the section of step `i`; it ends the sitting, and the next step opens a new one."
        if not (j := walk_of(jid, i)): return missing()
        sec, ix = next((sec, ix) for sec, ix in walk_state(j).sections if i in ix)
        slugs = {j.steps[k]['slug'] for k in ix}
        s = (sessions.get(sid) or Session.load(tutor, sid)) if (sid := j.get('sitting')) else None
        rows = [r for r in (s.log if s else ()) if r['concept'] in slugs]
        if s and not s.ended: s.end(); sessions.pop(s.id, None)
        nxt = ix[-1] + 1 if ix[-1] + 1 < len(j.steps) else None
        return Page('Section done', *ui.SectionDone(j, sec, ix, moved(rows), nxt, by()), crumbs=[*up, (j.title, ui.at(Routes.one, jid))], extra=ui.assets())

    def img(jid:str, i:int):
        "The figure of step `i`, only from inside the vault assets and only as an image file."
        if not (j := walk_of(jid, i)) or not (f := (j.steps[i].get('read') or {}).get('figure')): return Response(status_code=404)
        root = Path(lr.vault.assets()).resolve()
        p = (root/f).resolve()
        if not p.is_relative_to(root) or p.suffix.lower() not in FIGURES or not p.is_file(): return Response(status_code=404)
        return FileResponse(p)

    app.post(Routes.new)(new)
    app.get(Routes.one)(one)
    app.post(Routes.plan)(plan)
    app.post(Routes.start)(start)
    app.get(Routes.step)(step)
    app.get(Routes.note)(note)
    app.get(Routes.check)(check)
    app.post(Routes.answer)(answer)
    app.post(Routes.hint)(hint)
    app.post(Routes.giveup)(giveup)
    app.post(Routes.predict)(predict)
    app.post(Routes.keep)(keep)
    app.post(Routes.next)(next_)
    app.get(Routes.done)(done)
    app.get(Routes.img)(img)
