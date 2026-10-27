"A walk on the page: the plan, then one idea at a time with the outline at the left, the passage, the figure, the tutor note and one check."
import json
from pathlib import Path
from fasthtml.common import *
from rupaka.render import Demo, version
from abhyasa.core import Md, DepthBar, asset_css, asset_js
from abhyasa.model import DEPTHS
from abhyasa.method import LABELS, WALK_WAYS
from abhyasa.tutor import MAX_TRIES, HINTS
from abhyasa.journey import minutes
from .cfg import Routes

_P = Path(__file__).parent
OUTCOME = dict(solid='Solid', fragile='Right, but shaky', misconception='A misconception', gap='A gap', skipped='Skipped')
KIND = dict(short='short answer', code='code', demo='predict · demo', order='predict · order')
STEPS = (10, 30, 50, 70, 90)
GRADING, HINTING, TEACHING, WRITING = 'Grading…', 'Writing a hint…', 'Writing a lesson…', 'Writing the check…'
LEAD = dict(demo='Predict first. Then the demo shows the rest.', order='Put the steps in order first. Then the demo shows the right order.')

def assets(): return asset_css(_P/'walk.css'), asset_js(_P/'walk.js')

def at(r, jid, i=None): return Routes.of(r, jid=jid, **({} if i is None else dict(i=i)))

def name(by, s): return (by.get(s['slug']) or {}).get('name') or s['slug']

def Bar(done, total): return Span(I(style=f"width:{100 * done // max(total, 1)}%"), cls='prog', role='progressbar', aria_valuenow=str(done), aria_valuemax=str(total))

def pages(steps):
    "The pages of `steps` as 'p. 3' or 'p. 3–5'; empty when no step has a page."
    ps = sorted({s['read']['page'] for s in steps if (s.get('read') or {}).get('page')})
    return '' if not ps else f'p. {ps[0]}' if ps[0] == ps[-1] else f'p. {ps[0]}–{ps[-1]}'

# --- the plan --------------------------------------------------------------------------------------------------------

def WayPick(jid, i, s):
    "The way of the check of one step; a change saves it at once."
    way = (s.get('check') or {}).get('way')
    return Select(*[Option(LABELS[w], value=w, selected=w == way) for w in WALK_WAYS], name='way', aria_label='The way of the check',
                  hx_post=at(Routes.plan, jid), hx_vals=json.dumps(dict(i=i, act='check')), hx_trigger='change', hx_target='#plan', hx_swap='outerHTML')

def PlanIdea(jid, i, s, by):
    k = (s.get('check') or {}).get('kind', 'short')
    return Li(Span(name(by, s), cls='n'), Span(KIND.get(k, k), cls='w'), WayPick(jid, i, s),
              Button('Drop', type='button', cls='small quiet', title='Take this idea out of the walk', hx_post=at(Routes.plan, jid),
                     hx_vals=json.dumps(dict(i=i, act='drop')), hx_target='#plan', hx_swap='outerHTML'),
              cls='known' if s.get('status') == 'known' else None)

def Plan(j, st, by):
    "The sections in reading order, each idea with its check. You can change the way of a check, or drop an idea."
    mins = sum(minutes(s) for s in j['steps'])
    secs = [Li(Div(B(sec or 'The ideas'), Small(' · '.join(x for x in (pages([j['steps'][i] for i in ix]), f"{sum(minutes(j['steps'][i]) for i in ix)} min") if x)), cls='sh'),
               Ul(*[PlanIdea(j['id'], i, j['steps'][i], by) for i in ix])) for sec, ix in st.sections]
    return Div(Span(f"The walk · {len(st.sections)} section{'s' * (len(st.sections) != 1)} · {len(j['steps'])} ideas · about {mins} min", cls='lbl'),
               P('Each idea has one check. The tutor picks the check from the idea and from the ways that work for you. You can change any check.', cls='mute'),
               Ol(*secs, cls='plan') if secs else P('The tutor found no ideas in this source.', cls='mute'), id='plan')

def PlanPage(j, st, by):
    src = j.get('source') or {}
    go = (Form(Button('Start the walk ', Kbd('⌥S'), cls='go', data_wait='Starting…'), action=at(Routes.start, j['id']), method='post')
          if j['steps'] else '')
    return (H1(j['title']), P(f"From your vault: {src['title']}." if src.get('title') else j.get('goal', ''), cls='mute'),
            Plan(j, st, by), Div(go, Span('The walk is a journey, so it shows on Today.', cls='mute'), cls='row'))

# --- the step page ---------------------------------------------------------------------------------------------------

def Rail(j, st, by, i):
    "The outline at the left: each section, and the ideas in it with a dot for each state."
    lbl = 'The paper' if j.get('source') else 'The walk'
    rows = []
    for sec, ix in st.sections:
        rows.append(Li(sec or 'The ideas', cls='sec' + (' on' if i in ix else '')))
        for k in ix:
            s = st.steps[k]
            tag = dict(now='now', shaky='shaky', skipped='skipped', known='you know it').get(s.dot, '')
            rows.append(Li(A(name(by, s), href=at(Routes.step, j['id'], k)), Span(f' · {tag}', cls='k') if tag else '',
                           cls=f"c {s.dot}" + (' on' if k == i else '')))
    return Aside(Span(f"{lbl} · {i + 1} of {len(st.steps)}", cls='lbl'), Bar(st.done, st.total), Ol(*rows), id='rail', cls='outline', aria_label='The walk')

def Passage(j, s, c):
    "The passage from the source, word for word; with no passage, the statement of the idea, marked as the tutor's words."
    r = s.get('read') or {}
    if r.get('text'):
        if r.get('src'): src = f"From {r.get('title') or 'your sources'}"
        else: src = ', '.join(x for x in ('From the paper' if j.get('source') else 'From the text',
                                          r.get('section') and f"section {r['section'].split()[0]}", r.get('page') and f"p. {r['page']}") if x)
        return Blockquote(Md(r['text']), Span(src, cls='src'), id='passage', cls='quote')
    return Div(Span("In the tutor's words", cls='lbl'), Md((c or {}).get('statement', '')), id='passage', cls='stated')

def Figure_(jid, i, s, c):
    if not (s.get('read') or {}).get('figure'): return ''
    return Figure(Img(src=at(Routes.img, jid, i), alt=f"A figure for {(c or {}).get('name', 'this idea')}", loading='lazy'), id='figure')

def NextBar(jid, i, st, by):
    "Back to the idea before, and Next idea. Next works at any time: with no check done, it skips the idea."
    back = A(f"← {name(by, st.steps[i - 1])}", href=at(Routes.step, jid, i - 1), cls='mute') if i else Span()
    done = (st.steps[i].get('done') or {}).get('outcome')
    say = '' if done else 'Do the check, or skip it, to go on.'
    return Div(back, Span(Span(say, cls='mute'), Form(Button('Next idea ', Kbd('⌥S'), id='next', cls='small go'), action=at(Routes.next, jid, i), method='post'),
                          cls='row'), cls='next-bar')

def Note(text): return Md(text, cls='note') if text else ''

def StepPage(j, st, by, i):
    s, c = st.steps[i], by.get(st.steps[i]['slug'])
    r = s.get('read') or {}
    head = Div(*[Span(x) for x in (r.get('section'), r.get('page') and f"p. {r['page']}") if x], cls='sec-lbl')
    slot = Div(Div(Span(WRITING, cls='lbl'), Div(I(), I(), I(cls='short'), cls='skel'), cls='check'),
               id='check', hx_get=at(Routes.check, j['id'], i), hx_trigger='load', hx_swap='innerHTML', data_wait=WRITING)
    return Div(Rail(j, st, by, i),
               Div(head, H1(name(by, s), cls='idea'), Passage(j, s, c), Figure_(j['id'], i, s, c),
                   Div(id='note', hx_get=at(Routes.note, j['id'], i), hx_trigger='load', hx_swap='innerHTML', data_quiet='1'), slot, NextBar(j['id'], i, st, by), cls='walk-main'),
               cls='walk-layout')

# --- the short-answer check ------------------------------------------------------------------------------------------

def Turn(t, n):
    "One message on the check after the question: your try, a nudge, a hint, or the close."
    k = t.get('kind')
    if t['who'] == 'you':
        sure = f" · {t['confidence']}% sure" if t.get('confidence') is not None else ''
        return Li(Span(f'You{sure}', cls='lbl'), Md(t['text']) if t.get('text') else P('No answer.', cls='mute'), cls='m you')
    if k == 'nudge': return Li(Span('Not yet', cls='tag no'), Md(t.get('text', '')), Div(Span('First error: ', cls='k'), Md(t['first_error']), cls='err') if t.get('first_error') else '', cls='m')
    if k == 'hint': return Li(Span(f'Hint {n}', cls='lbl'), Md(t.get('text', '')), cls='m hint')
    if k == 'lesson': return Li(Span('Lesson', cls='lbl'), Md(t.get('text', '')), cls='m')
    if k == 'close':
        ok = t.get('outcome') in ('solid', 'fragile')
        return Li(Span(OUTCOME.get(t.get('outcome'), 'Closed'), cls='tag ' + ('ok' if ok else 'no')), Md(t['text']) if t.get('text') and (ok or not t.get('lesson')) else '',
                  Div(Span('Lesson', cls='lbl'), Md(t['lesson']), cls='lesson') if t.get('lesson') else '', cls='m close')
    return ''

def Thread(q):
    out, n = [], 0
    for t in (q.get('turns') or [])[1:]:   # the first turn is the question, shown above
        n += t.get('kind') == 'hint'
        out.append(Turn(t, n))
    return Ol(*out, cls='thread') if out else ''

def Confidence():
    "Five steps for how sure you are."
    return Div(Span('Sure?', cls='lbl'), *[Label(Input(type='radio', name='confidence', value=v), Span(f'{v}%')) for v in STEPS],
               cls='steps', role='radiogroup', aria_label='How sure you are')

def GoOn(jid, i):
    return Form(Button('Next idea ', Kbd('⌥S'), cls='go', autofocus=True), action=at(Routes.next, jid, i), method='post', cls='row')

def CardHead(s, q=None):
    ck = s.get('check') or {}
    depth = DEPTHS[q.depth] if q else DEPTHS[ck.get('depth', 2)]
    way = LABELS.get(q.get('method') if q else ck.get('way'), '')
    return Div(Span(' · '.join(x for x in ('Check', way.lower(), depth) if x)), Span(ck.get('why', ''), cls='why') if ck.get('why') else '', cls='lbl')

def Done(jid, i, s):
    "A check that is done, when its thread is not in memory any more."
    o = (s.get('done') or {}).get('outcome')
    say = ('You skipped this check.' if o == 'skipped' else f"You did this check: {OUTCOME[o].lower()}." if o in OUTCOME
           else 'This check is not open. Load the page again.')
    return Section(CardHead(s), P(say), GoOn(jid, i), cls='check done')

def Short(jid, i, s, q):
    "A short-answer check: the question, the thread so far, then the answer box, or the close and Next idea."
    if q is None: return Done(jid, i, s)
    shut = any(t.get('kind') == 'close' for t in q.get('turns') or ())
    tgt = dict(hx_target='#check', hx_swap='innerHTML')
    if shut: foot = GoOn(jid, i)
    else:
        tries = len(q.get('tries') or ())
        left = MAX_TRIES - tries
        out = Button('Teach me' if tries else "I don't know", type='button', id='idk', cls='quiet', hx_post=at(Routes.giveup, jid, i),
                     hx_include='closest form', data_wait=TEACHING, **tgt)
        hint = Button('Hint ', Kbd('⌥W'), type='button', id='hint', cls='quiet', hx_post=at(Routes.hint, jid, i), data_wait=HINTING, **tgt,
                      disabled=len(q.get('hints') or ()) >= len(HINTS))
        foot = Form(Textarea(name='answer', id='ans', rows=2, autofocus=True, aria_label='Your answer', placeholder='Your answer. ⌘↵ sends.'),
                    Textarea(name='thinking', id='think', rows=1, aria_label='Think aloud', placeholder='Think aloud: how did you get there?'),
                    Div(Confidence(), Span(f"{left} {'try' if left == 1 else 'tries'} left" if tries else '', cls='mute'), cls='row conf'),
                    Div(Button('Send ', Kbd('⌘↵'), cls='go', id='send', data_wait=GRADING), hint, out, cls='row acts'),
                    hx_post=at(Routes.answer, jid, i), **tgt)
    return Section(CardHead(s, q), Md(q['question'], cls='q'), Thread(q), foot, cls='check' + (' shut' if shut else ''))

# --- the demo and order checks ---------------------------------------------------------------------------------------

def rk_assets():
    "The rupaka runtime, which the demo block serves."
    v = version()
    return Link(rel='stylesheet', href=f'/rupaka/rupaka.css?v={v}'), Script(src=f'/rupaka/rupaka.js?v={v}')

def DemoCheck(jid, i, s, d):
    "A demo or an order check: the rupaka demo of the step, closed when you skipped it. walk.js sends each prediction, and K keeps the state."
    if d is None or (s.get('done') or {}).get('outcome') == 'skipped': return Done(jid, i, s)
    k = s['check']['kind']
    keep = Button('Keep this state ', Kbd('K'), type='button', id='keep', cls='small quiet', title='Save the inputs of the demo with your last prediction')
    return Section(CardHead(s), P(LEAD[k], cls='mute'), Demo(d.spec), *rk_assets(), Div(keep, Span(cls='mute said', aria_live='polite'), cls='row acts'),
                   cls='check walk-demo', data_demo=d.slug, data_kind=k, data_url=at(Routes.predict, jid, i), data_keep=at(Routes.keep, jid, i))

def Pending(jid, i, s):
    "The demo of the step is not ready: the card asks the server again in 2 seconds."
    return Section(CardHead(s), P('The tutor is making the demo for this idea. This can take a minute. You can read the passage while you wait.', cls='mute'),
                   cls='check pending', hx_get=at(Routes.check, jid, i), hx_trigger='load delay:2s', hx_target='#check', hx_swap='innerHTML')

CHECKS = dict(short=Short, demo=DemoCheck, order=DemoCheck)   # check kind -> card; Task 8 adds code

# --- the end of a section --------------------------------------------------------------------------------------------

def Moved(m):
    up, down = m['after'] > m['before'], m['after'] < m['before']
    said = f"{DEPTHS[m['before']]} → {DEPTHS[m['after']]}" if up or down else f"stays at {DEPTHS[m['after']]}"
    return Li(A(m['name'], href=f"/c/{m['concept']}"), DepthBar(m['after']), ' ', Span(said, cls='moved'),
              Span(f"  · {m['passed']} of {m['asked']} passed", cls='mute'))

def SectionDone(j, sec, ix, ms, nxt, by):
    "What moved in this section, the ideas you skipped, and Go on."
    skipped = [name(by, j['steps'][k]) for k in ix if (j['steps'][k].get('done') or {}).get('outcome') == 'skipped']
    up = sum(m['after'] > m['before'] for m in ms)
    lead = (f"{up} idea{'s' * (up != 1)} moved up." if up else 'Nothing moved up in this section.' if ms else 'You did no checks in this section.')
    go = (A('Go on ', Kbd('⌥S'), href=at(Routes.step, j['id'], nxt), cls='btn go') if nxt is not None
          else A('Back to your journeys ', Kbd('⌥S'), href='/journeys', cls='btn go'))
    return (Span(sec or 'The ideas', cls='lbl'), H1('Section done'), P(lead, cls='lead-sum'),
            *([H2('What moved'), Ul(*map(Moved, ms), cls='plain moved-list')] if ms else []),
            *([P('You skipped: ', ', '.join(skipped), '.', cls='mute')] if skipped else []),
            P(f"Next: {name(by, j['steps'][nxt])}." if nxt is not None else 'You finished the walk.', cls='next-step'),
            Div(go, cls='row'))
