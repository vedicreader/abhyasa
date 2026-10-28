"A walk on the page: the plan, then one idea at a time with the outline at the left, the passage, the figure, the tutor note and one check."
import json
from pathlib import Path
from urllib.parse import urlencode
from fasthtml.common import *
from rupaka.render import Demo, version
from abhyasa.core import Md, DepthBar, asset_css, asset_js, Check, Msg, Tag, FirstError, OUTCOMES, Confidence
from abhyasa.model import DEPTHS
from abhyasa.method import LABELS, WALK_WAYS
from abhyasa.tutor import HINTS
from abhyasa.settings import val
from abhyasa.core.leela import leela_line
from abhyasa.journey import minutes, TOOL_WAYS
from .cfg import Routes

_P = Path(__file__).parent
OUTCOME = {k: t for k, (t, _) in OUTCOMES.items() if k != 'nudge'}
KIND = dict(short='short answer', code='code', demo='predict · demo', order='predict · order')
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

def WayPick(jid, i, s, ways=WALK_WAYS):
    "The way of the check of one step; a change saves it at once."
    way = (s.get('check') or {}).get('way')
    return Select(*[Option(LABELS[w], value=w, selected=w == way) for w in ways], name='way', aria_label='The way of the check',
                  hx_post=at(Routes.plan, jid), hx_vals=json.dumps(dict(i=i, act='check')), hx_trigger='change', hx_target='#plan', hx_swap='outerHTML')

def PlanIdea(jid, i, s, by, ways=WALK_WAYS):
    k = (s.get('check') or {}).get('kind', 'short')
    return Li(Span(name(by, s), cls='n'), Span(KIND.get(k, k), cls='w'), WayPick(jid, i, s, ways),
              Button('Drop', type='button', cls='small quiet', title='Take this idea out of the walk', hx_post=at(Routes.plan, jid),
                     hx_vals=json.dumps(dict(i=i, act='drop')), hx_target='#plan', hx_swap='outerHTML'),
              cls='known' if s.get('status') == 'known' else None)

def page_of(j, i):
    "The title of the page of step `i` in a walk from a link; None in other walks."
    return (j['steps'][i].get('read') or {}).get('title') if (j.get('source') or {}).get('docs') else None

def Plan(j, st, by):
    "The sections in reading order, each idea with its check. You can change the way of a check, or drop an idea. A walk from a link names each page once."
    mins = sum(minutes(s) for s in j['steps'])
    secs, page = [], None
    ways = TOOL_WAYS if j.get('tool') else WALK_WAYS
    for sec, ix in st.sections:
        if (t := page_of(j, ix[0])) and t != page: secs.append(Li(H3(t), cls='page')); page = t
        secs.append(Li(Div(B(sec or 'The ideas'), Small(' · '.join(x for x in (pages([j['steps'][i] for i in ix]), f"{sum(minutes(j['steps'][i]) for i in ix)} min") if x)), cls='sh'),
                       Ul(*[PlanIdea(j['id'], i, j['steps'][i], by, ways) for i in ix])))
    n = len(j.get('more') or ())
    return Div(Span(f"The walk · {len(st.sections)} section{'s' * (len(st.sections) != 1)} · {len(j['steps'])} ideas · about {mins} min", cls='lbl'),
               P('Each idea has one check. The tutor picks the check from the idea and from the ways that work for you. You can change any check.', cls='mute'),
               P(f"The tutor picked the main ideas. The source has {n} more idea{'s' * (n != 1)}. They are in your concepts. "
                 'When a step needs one of them, you can open it beside the walk.', cls='mute') if n else '',
               Ol(*secs, cls='plan') if secs else P('The tutor found no ideas in this source.', cls='mute'), id='plan')

def PlanPage(j, st, by):
    src = j.get('source') or {}
    go = (Form(Button('Start the walk ', Kbd('⌥S'), cls='go', data_wait='Starting…'), action=at(Routes.start, j['id']), method='post')
          if j['steps'] else '')
    return (H1(j['title']), P(f"From your vault: {src['title']}." if src.get('title') else f"From the link: {src['url']} · {len(src['docs'])} page{'s' * (len(src['docs']) != 1)}." if src.get('docs') else j.get('goal', ''), cls='mute'),
            leela_line(j) if j.get('tool') else '', Plan(j, st, by), Div(go, Span('The walk is a journey, so it shows on Today.', cls='mute'), cls='row'))

def LinkPending(url, said):
    "A walk from a link that is still being made: the card asks the server again in 2 seconds."
    return Div(P(said), P('This can take some minutes. When the walk is ready, it opens here and shows in your journeys.', cls='mute'),
               cls='walk-link pending', style='animation: none', hx_get=f"{Routes.job}?{urlencode(dict(url=url))}", hx_trigger='load delay:2s', hx_swap='outerHTML')

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
        if r.get('src') or (j.get('source') or {}).get('docs'): src = f"From {r.get('title') or 'your sources'}"
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

def BackFoot(b):
    "In a side walk: the way back to the step that opened it. In the side pane it stays at the foot, and ⌥Z does the same."
    return A(f"← Back to the paper: {b.here} ", Kbd('⌥Z'), href=b.href, cls='rh-back walk-back', data_rh_trail=json.dumps(b.trail))

def StepPage(j, st, by, i, needs=(), back=None):
    "One idea: the outline, the passage, the figure, the note and the check. `needs` is what other blocks add under the title."
    s, c = st.steps[i], by.get(st.steps[i]['slug'])
    r = s.get('read') or {}
    head = Div(*[Span(x) for x in (r.get('section'), r.get('page') and f"p. {r['page']}") if x], cls='sec-lbl')
    slot = Div(Div(Span(WRITING, cls='lbl'), Div(I(), I(), I(cls='short'), cls='skel'), cls='check'),
               id='check', hx_get=at(Routes.check, j['id'], i), hx_trigger='load', hx_swap='innerHTML', data_wait=WRITING)
    return Div(Rail(j, st, by, i),
               Div(BackFoot(back) if back else '', head, H1(name(by, s), cls='idea'), *needs, Passage(j, s, c), Figure_(j['id'], i, s, c),
                   Div(id='note', hx_get=at(Routes.note, j['id'], i), hx_trigger='load', hx_swap='innerHTML', data_quiet='1'), slot, leela_line(j, i) if s.get('leela') else '', NextBar(j['id'], i, st, by), cls='walk-main'),
               cls='walk-layout')

# --- the short-answer check ------------------------------------------------------------------------------------------

def Turn(t, n):
    "One message on the check after the question: your try, a nudge, a hint, or the close."
    k = t.get('kind')
    if t['who'] == 'you':
        sure = f" · {t['confidence']}% sure" if t.get('confidence') is not None else ''
        return Msg(f'You{sure}', Md(t['text']) if t.get('text') else P('No answer.', cls='mute'), cls='you')
    if k == 'nudge': return Msg(Tag('nudge'), Md(t.get('text', '')), FirstError(t.get('first_error')))
    if k == 'hint': return Msg(f'Hint {n}', Md(t.get('text', '')), cls='hint')
    if k == 'lesson': return Msg('Lesson', Md(t.get('text', '')))
    if k == 'close':
        ok = t.get('outcome') in ('solid', 'fragile')
        return Msg(Tag(t.get('outcome')), Md(t['text']) if t.get('text') and (ok or not t.get('lesson')) else '',
                   Div(Span('Lesson', cls='lbl'), Md(t['lesson']), cls='lesson') if t.get('lesson') else '', cls='close')
    return ''

def Thread(q):
    "The messages of the check after the question."
    out, n = [], 0
    for t in (q.get('turns') or [])[1:]:   # the first turn is the question, shown above
        n += t.get('kind') == 'hint'
        out.append(Turn(t, n))
    return out

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
    return Check(CardHead(s), P(say), foot=GoOn(jid, i), cls='done')

def Short(jid, i, s, q, after=()):
    "A short-answer check: the question, the thread so far, what other blocks add (`after`), then the answer box, or the close and Next idea."
    if q is None: return Done(jid, i, s)
    shut = any(t.get('kind') == 'close' for t in q.get('turns') or ())
    tgt = dict(hx_target='#check', hx_swap='innerHTML')
    if shut: foot = GoOn(jid, i)
    else:
        tries = len(q.get('tries') or ())
        left = val('checks.tries') - tries
        out = Button('Teach me' if tries else "I don't know", type='button', id='idk', cls='quiet', hx_post=at(Routes.giveup, jid, i),
                     hx_include='closest form', data_wait=TEACHING, **tgt)
        hint = Button('Hint ', Kbd('⌥W'), type='button', id='hint', cls='quiet', hx_post=at(Routes.hint, jid, i), data_wait=HINTING, **tgt,
                      disabled=len(q.get('hints') or ()) >= len(HINTS))
        foot = Form(Textarea(name='answer', id='ans', rows=2, autofocus=True, aria_label='Your answer', placeholder='Your answer. ⌘↵ sends.'),
                    Textarea(name='thinking', id='think', rows=1, aria_label='Think aloud', placeholder='Think aloud: how did you get there?'),
                    Div(Confidence(), Span(f"{left} {'try' if left == 1 else 'tries'} left" if tries else '', cls='mute'), cls='row conf'),
                    Div(Button('Send ', Kbd('⌘↵'), cls='go', id='send', data_wait=GRADING), hint, out, cls='row acts'),
                    hx_post=at(Routes.answer, jid, i), data_qid=q['id'], **tgt)
    return Check(CardHead(s, q), q['question'], *Thread(q), foot=(*after, foot), shut=shut)

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
    return Check(CardHead(s), P(LEAD[k], cls='mute'), foot=(Demo(d.spec), *rk_assets(), Div(keep, Span(cls='mute said', aria_live='polite'), cls='row acts')),
                 cls='walk-demo', data_demo=d.slug, data_kind=k, data_url=at(Routes.predict, jid, i), data_keep=at(Routes.keep, jid, i))

def Pending(jid, i, s):
    "The demo of the step is not ready: the card asks the server again in 2 seconds."
    return Check(CardHead(s), P('The tutor is making the demo for this idea. This can take a minute. You can read the passage while you wait.', cls='mute'),
                 cls='pending', hx_get=at(Routes.check, jid, i), hx_trigger='load delay:2s', hx_target='#check', hx_swap='innerHTML')


# --- the code check --------------------------------------------------------------------------------------------------

RUNNING = 'Running the tests…'
RESULT = dict(error='error', timeout='timeout')   # a status that is not pass or fail, as its own word

def Result(c, texts):
    "One test result. A hidden test shows its label and status only: never its text, its expected value or your value."
    return Li(Span(RESULT.get(c['status'], c['status']), cls='st'), Span(c['label']), '' if c['hidden'] else Code(texts[c['i']]), cls=c['status'])

def CodeOut(jid, i, q, r=None):
    "The results part of a code check: hints, the results of the last run, the first error, and the close. The editor is not in it."
    texts = [t if isinstance(t, str) else t['test'] for t in q.tests]
    close = first(t for t in q.get('turns') or () if t.get('kind') == 'close')
    out = [Div(Span(f'Hint {n}', cls='lbl'), Md(h), cls='hint') for n, h in enumerate(q.get('hints') or (), 1)]
    if r and r.get('syntax'):
        out += [Div(Span('Syntax error: ', cls='k'), f'{r.syntax}.', cls='err'), P(f'try {val('checks.tries') - r.tries_left + 1} · no try used', cls='mute')]
    elif r and 'checks' in r:
        n = val('checks.tries') - r.tries_left + bool(r.done and r.get('correct'))
        out += [Ul(*[Result(c, texts) for c in r.checks], cls='results') if r.checks else '',
                FirstError(r.first_error),
                P(f'try {n} · {r.passed} of {r.total} pass', cls='mute')]
    if close:
        out += [Tag(close.get('outcome')),
                Div(Span('Lesson', cls='lbl'), Md(close['lesson']), cls='lesson') if close.get('lesson') else '', GoOn(jid, i),
                Button('Run the tests', type='submit', form='run-form', id='run', disabled=True, hx_swap_oob='true')]   # no longer the main button, so ⌥S goes to Next idea
    return Div(*out, id='code-out', aria_live='polite')

def CodeCheck(jid, i, s, q, after=()):
    "A code check: the task, a plain editor with the stub, the visible tests, and Run. A run swaps only the results."
    if q is None: return Done(jid, i, s)
    if not s.get('code'): return Short(jid, i, s, q, after)
    c = s['code']
    draft = q['tries'][-1]['answer'] if q.get('tries') else c['stub']
    tgt = dict(hx_target='#code-out', hx_swap='innerHTML')
    left = val('checks.tries') - len(q.get('tries') or ())
    hint = Button('Hint ', Kbd('⌥W'), type='button', id='hint', cls='quiet', hx_post=at(Routes.hint, jid, i), data_wait=HINTING, **tgt,
                  disabled=len(q.get('hints') or ()) >= len(HINTS))
    idk = Button('Teach me' if q.get('tries') else "I don't know", type='button', id='idk', cls='quiet', hx_post=at(Routes.giveup, jid, i),
                 data_wait=TEACHING, **tgt)
    form = Form(Textarea(draft, name='source', id='source', cls='code-editor', rows=max(6, draft.count('\n') + 3), spellcheck='false', autofocus=True,
                         aria_label='Your code'),
                Details(Summary('The tests you can see'), Ul(*[Li(Code(t)) for t in c['tests']], cls='tests'), open=True),
                id='run-form', hx_post=at(Routes.run, jid, i), **tgt)
    run = Button('Run the tests ', Kbd('⌘↵'), type='submit', form='run-form', id='run', cls='go', data_wait=RUNNING)   # outside the form, so the results hold Next idea with no nested form
    return Check(CardHead(s, q), q['question'], foot=(form, CodeOut(jid, i, q), Div(run, hint, idk, Span(f"{left} {'try' if left == 1 else 'tries'} left", cls='mute'), cls='row acts'),
                                                   leela_line(AttrDict(id=jid), i, say='Go further with real code in Leela', quiet=True)), cls='code-check')

CHECKS = dict(short=Short, demo=DemoCheck, order=DemoCheck, code=CodeCheck)   # check kind -> card

# --- the end of a section --------------------------------------------------------------------------------------------

def Moved(m):
    up, down = m['after'] > m['before'], m['after'] < m['before']
    said = f"{DEPTHS[m['before']]} → {DEPTHS[m['after']]}" if up or down else f"stays at {DEPTHS[m['after']]}"
    return Li(A(m['name'], href=f"/c/{m['concept']}"), DepthBar(m['after']), ' ', Span(said, cls='moved'),
              Span(f"  · {m['passed']} of {m['asked']} passed", cls='mute'))

def SectionDone(j, sec, ix, ms, nxt, by, end=()):
    "What moved in this section, the ideas you skipped, and Go on. At the end of the walk, `end` is what other blocks add (`walk_end`)."
    skipped = [name(by, j['steps'][k]) for k in ix if (j['steps'][k].get('done') or {}).get('outcome') == 'skipped']
    up = sum(m['after'] > m['before'] for m in ms)
    lead = (f"{up} idea{'s' * (up != 1)} moved up." if up else 'Nothing moved up in this section.' if ms else 'You did no checks in this section.')
    go = (A('Go on ', Kbd('⌥S'), href=at(Routes.step, j['id'], nxt), cls='btn go') if nxt is not None
          else A('Back to your journeys ', Kbd('⌥S'), href='/journeys', cls='btn go'))
    return (Span(sec or 'The ideas', cls='lbl'), H1('Section done'), P(lead, cls='lead-sum'),
            *([H2('What moved'), Ul(*map(Moved, ms), cls='plain moved-list')] if ms else []),
            *([P('You skipped: ', ', '.join(skipped), '.', cls='mute')] if skipped else []),
            P(f"Next: {name(by, j['steps'][nxt])}." if nxt is not None else 'You finished the walk.', cls='next-step'),
            *end, Div(go, cls='row'))
