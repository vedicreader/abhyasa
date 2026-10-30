"A walk on the page: the plan, then one idea at a time with the outline at the left, the passage, the figure, the tutor note and one check."
import json, re, time
from pathlib import Path
from urllib.parse import urlencode
from fasthtml.common import *
from rupaka.render import Demo, version
from abhyasa.core import pane_link, SourceLine, TutorWords, source_of, n_of, moved_words, Secondary, Md, DepthBar, asset_css, asset_js, Check, Msg, Tag, FirstError, OUTCOMES, Confidence, Primary, Quiet, Feedback, in_talk, Inline, can_undo
from abhyasa.model import DEPTHS
from abhyasa.method import LABELS, WALK_WAYS
from abhyasa.tutor import HINTS
from abhyasa.settings import val
from abhyasa.core.leela import leela_line, LEELA_INSTALL
from abhyasa.journey import minutes, TOOL_WAYS, SHAKY
from .cfg import Routes

_P = Path(__file__).parent
OUTCOME = {k: t for k, (t, _) in OUTCOMES.items() if k != 'nudge'}
KIND = dict(short='short answer', code='code', demo='predict · demo', order='predict · order', notebook='notebook · in Leela')
GRADING, HINTING, TEACHING, WRITING = 'Grading…', 'Writing a hint…', 'Writing a lesson…', 'Writing the check…'
LOOKING = 'Looking for a source…'
NO_SOURCE = 'No good source was found on the web.'
LEAD = dict(demo='Predict first. Then the demo shows the rest.', order='Put the steps in order first. Then the demo shows the right order.')

def assets(): return asset_css(_P/'walk.css'), asset_js(_P/'walk.js')

def at(r, jid, i=None): return Routes.of(r, jid=jid, **({} if i is None else dict(i=i)))

def name(by, s): return (by.get(s['slug']) or {}).get('name') or s['slug']

def Bar(done, total, oob=False):
    "The progress line of the outline. An answer that closes a check swaps it out of band, and its width moves (htmx settles the style)."
    return Span(I(style=f"width:{100 * done // max(total, 1)}%", id='rail-bar'), cls='prog', role='progressbar', aria_valuenow=str(done), aria_valuemax=str(total),
                id='rail-prog', **({'hx_swap_oob': 'true'} if oob else {}))

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
    "One idea of the plan: its name, the label of its passage in small type, its check, and Drop."
    k = (s.get('check') or {}).get('kind', 'short')
    return Li(Span(name(by, s), Small(source_of(s.get('read')).label, cls='src-lbl'), cls='n'), Span(KIND.get(k, k), cls='w'), WayPick(jid, i, s, ways),
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
    return Div(Span(f"The walk · {n_of(len(st.sections), 'section')} · {n_of(len(j['steps']), 'idea')} · about {mins} min", cls='lbl'),
               P('Each idea has one check. The tutor picks the check from the idea and from the ways that work for you. You can change any check.', cls='mute'),
               P(f"The tutor picked the main ideas. The source has {n} more {'idea' if n == 1 else 'ideas'}. They are in your concepts. "
                 'When a step needs one of them, you can learn it beside the walk.', cls='mute') if n else '',
               Ol(*secs, cls='plan') if secs else P('The tutor found no ideas in this source.', cls='mute'), id='plan')

def PlanPage(j, st, by, actions=(), vault=None):
    src = j.get('source') or {}
    go = (Form(Primary('Start the walk', data_wait='Starting…'), action=at(Routes.start, j['id']), method='post')
          if j['steps'] else '')
    return (H1(j['title']), P(f"From your vault: {src['title']}." if src.get('title') else f"From the link: {src['url']} · {n_of(len(src['docs']), 'page')}." if src.get('docs') else j.get('goal', ''), cls='mute'),
            leela_line(j, vault=vault) if j.get('tool') else '', Plan(j, st, by), Div(go, *actions, cls='row'))

def LinkPending(url, said):
    "A walk from a link that is still being made: the card asks the server again in 2 seconds."
    return Div(P(said), P('This can take some minutes. When the walk is ready, it opens here and shows in your walks.', cls='mute'),
               cls='walk-link pending', style='animation: none', hx_get=f"{Routes.job}?{urlencode(dict(url=url))}", hx_trigger='load delay:2s', hx_swap='outerHTML')


def filed_words(f) -> str:
    "`11 notebooks`, `11 notebooks and 3 other files`, or `3 files`: what one filing added."
    nb, n = f.get('notebooks', 0), len(f.get('docs') or ())
    if not nb: return n_of(n, 'file')
    return n_of(nb, 'notebook') + (f" and {n_of(n - nb, 'other file')}" if n > nb else '')

def Filed(j, now=None, job=''):
    "What Start filed for walk `j` (or, when the walk failed, for the pool job `job`), each with Undo for one hour, and the sources that it could not file."
    who = dict(job=job) if job else dict(jid=j['id'])
    rows = [Div(f"Added {f['root']}: {filed_words(f)}.", ' ',
                Quiet('Undo', small=True, type='button', hx_post=Routes.unfile, hx_vals=dict(**who, root=f['root']), hx_target='this', hx_swap='outerHTML'),
                cls='filed') for f in j.get('filed') or () if can_undo(f, now)]
    notes = [P(n, cls='req-err') for n in j.get('notes') or ()]
    return Div(*rows, *notes, cls='walk-filed') if rows or notes else ''

# --- the step page ---------------------------------------------------------------------------------------------------

def Idea(j, by, s, k, i, just=False):
    "One idea in the outline, with a dot for its state. `just`: its check closed now, so the dot fills (walk.css); it is swapped out of band."
    tag = dict(now='now', shaky='shaky', skipped='skipped', known='you know it').get(s.dot, '')
    return Li(A(Inline(name(by, s)), href=at(Routes.step, j['id'], k)), Span(f' · {tag}', cls='k') if tag else '', id=f'rail-{k}',
              cls=f"c {s.dot}" + (' on' if k == i else '') + (' just' if just else ''), **({'hx_swap_oob': 'true'} if just else {}))

def Filled(j, st, by, i):
    "The parts of the outline that change when the check of step `i` closes: its idea and the progress line, out of band."
    return Idea(j, by, st.steps[i], i, i, just=True), Bar(st.done, st.total, oob=True)

def Rail(j, st, by, i, present=()):
    """The outline at the left: each section, and the ideas in it with a dot for each state. Under 1040 px it folds into
    its first line, `The paper · 3 of 3` and the progress line, and a click opens it (walk.css). `present` is what other blocks add under it."""
    lbl = 'The paper' if j.get('source') else 'The walk'
    rows = []
    for sec, ix in st.sections:
        rows.append(Li(sec or 'The ideas', cls='sec' + (' on' if i in ix else '')))
        rows += [Idea(j, by, st.steps[k], k, i) for k in ix]
    return Aside(Details(Summary(Span(f"{lbl} · {i + 1} of {len(st.steps)}", cls='lbl'), Bar(st.done, st.total)), Ol(*rows)), *([Div(*present, cls='rail-acts')] if present else []),
                 id='rail', cls='outline', aria_label='The walk')

def FindSource(jid, i, s, looking=False):
    """Under the tutor's words of step `i`: while the tutor looks for a source on the web, a quiet line (the passage asks again in
    3 seconds); else `Find a source`, or `Look again` under `No good source was found on the web.` on its own line when a search
    found nothing, with the line that says why (`research_why`). Nothing when research is off."""
    if not val('research.on'): return ''
    if s.get('research') == 'pending' and looking: return P(LOOKING, cls='mute looking', aria_live='polite')
    none = s.get('research') == 'none'
    go = Quiet('Look again' if none else 'Find a source', small=True, type='button', hx_post=at(Routes.source, jid, i), hx_target='#passage', hx_swap='outerHTML', data_wait=LOOKING)
    if none and s.get('gather_none'):   # the gather agent read for this idea and found nothing: what it read is in its log
        return (P(s.get('research_why') or NO_SOURCE, cls='mute no-source'), P(ShowLog(jid), ' ', go, cls='mute find-source'))
    why = P(s['research_why'], cls='mute no-source-why') if none and s.get('research_why') else ''
    return (P(NO_SOURCE, cls='mute no-source') if none else '', why, P(go, cls='mute find-source'))

# --- the gather agent: the band, and the log of what it read and filed ------------------------------------------------

TOOL_WORDS = dict(web_search='Searched the web', fetch_page='Read a page', gh_clone='Cloned a repo', read_gh_repo='Listed files in a repo',
                  read_file='Read a file', file_source='Opened a source', docs='Listed documents', read_doc='Read a document',
                  put_passage='Gave a passage', put_notebook='Gave a notebook', note='Note from the agent')

def hm(t) -> str: return time.strftime('%H:%M', time.localtime(t)) if t else ''

def ShowLog(jid): return pane_link('Show what it did', at(Routes.gather_log, jid), 'What the agent did', cls='pane-link show-log')

def gather_counts(j) -> AttrDict:
    "The documents that the agent read, the documents of the sources (at least the ones read), and the ideas with a passage of all the ideas."
    read = sum(r.get('outcome') == 'read' for r in j.get('gather') or ())
    ideas = [s for s in j['steps'] if s.get('status') != 'skip']
    return AttrDict(read=read, total=max(j.get('gather_total') or 0, read), have=sum(bool((s.get('read') or {}).get('text')) for s in ideas), ideas=len(ideas))

def gather_words(j) -> tuple:
    "`38 of 120 documents read` and `7 of 10 ideas have a passage`."
    n = gather_counts(j)
    docs = f"{n.read} of {n_of(n.total, 'document')} read" if n.total > n.read else f"{n_of(n.read, 'document')} read"
    return docs, f"{n.have} of {n_of(n.ideas, 'idea')} {'has' if n.ideas == 1 else 'have'} a passage"

def GatherBand(j, running=False, stopping=False):
    """The band of the gather agent of walk `j`: while it runs, what it read and the ideas with a passage, the document that it reads now,
    `Show what it did` and `Stop`, and it asks again every 3 seconds. After it ends, one line that says how it ended. Nothing before it starts."""
    if not j.get('gather_at'): return Div(id='gather')
    docs, ideas = gather_words(j)
    log = ShowLog(j['id']) if j.get('gather') else ''
    if running:
        nw = j.get('gather_now') or {}
        now = ' '.join(x for x in ('Now: reading', nw.get('title') or '', f"({nw['site']})" if nw.get('site') else '', f"for idea {nw['i'] + 1}" if type(nw.get('i')) is int else '') if x)
        stop = (Span('Stopping the agent…', cls='mute') if stopping else
                Quiet('Stop', small=True, type='button', hx_post=at(Routes.gather_stop, j['id']), hx_target='#gather', hx_swap='outerHTML', data_wait='Stopping…'))
        return Div(P(f"An agent is reading your sources. {docs}. {ideas}. Started {hm(j['gather_at'])}."),
                   P(now, cls='mute now') if nw.get('title') else '', Div(log, stop, cls='row'),
                   id='gather', cls='gather-band running', aria_live='polite', hx_get=at(Routes.gather, j['id']), hx_trigger='every 3s', hx_swap='outerHTML')
    why = j.get('gather_why') or ''
    if why.startswith('The agent could not start'): return Div(P(why, cls='mute'), id='gather', cls='gather-band')
    how = {'you': 'You stopped the agent.', 'time': 'The time for the agent ended.'}.get(j.get('gather_stopped'))
    if not how and not j.get('gather_end'): how = 'The agent stopped when abhyasa closed.'
    line = f"{how} It read {docs.replace(' read', '')}." if how else f"The agent read {docs.replace(' read', '')}."
    return Div(P(f"{line} {ideas}."), P(why, cls='mute') if why else '', Div(log, cls='row') if log else '', id='gather', cls='gather-band')

def _target(r):
    "The target of log row `r`: a link to the page on the web (a new tab) or to the document in your vault, else plain text."
    t, u = r.get('target') or '', r.get('link') or ''
    if u.startswith(('http://', 'https://')): return A(t or u, href=u, target='_blank', rel='noopener noreferrer')
    if u.startswith('/'): return A(t or u, href=u)
    return Span(t)

def GatherLog(j):
    "The log of the gather agent of walk `j`, newest first: the time, what it did, the target with its link, and the outcome. A note from the agent is marked as its own words."
    rows = list(reversed(j.get('gather') or ()))
    docs, ideas = gather_words(j)
    def item(r):
        idea = f" · idea {r['i'] + 1}" if type(r.get('i')) is int else ''
        if r.get('tool') == 'note': return Li(Span(hm(r.get('at')), cls='k'), ' ', B(TOOL_WORDS['note']), ' ', Q(r.get('outcome') or '', cls='agent-note'), cls='glog note')
        bad = str(r.get('outcome') or '').startswith(('refused', 'not read'))
        return Li(Span(hm(r.get('at')), cls='k'), ' ', B(TOOL_WORDS.get(r.get('tool'), r.get('tool') or '')), ' ', _target(r), Span(f" · {r.get('outcome') or ''}{idea}", cls='mute'),
                  cls='glog refused' if bad else 'glog')
    return (H1('What the agent did'), P(f'{docs}. {ideas}. A note from the agent is its own words, not a source.', cls='mute'),
            Ol(*map(item, rows), cls='gather-log') if rows else P('The agent did nothing yet.', cls='mute'))

def Passage(j, s, c, i=None, looking=False):
    """The passage from the source, word for word, with its `SourceLine`; with no passage, the statement of the idea, marked as the
    tutor's words. With `i`, a step with no passage can look for a source (`FindSource`).
    `data-moves` holds the words that the idea moves: walk.js links them to the parts of the demo."""
    r = s.get('read') or {}
    mv = dict(data_moves=json.dumps(list((c or {}).get('moves') or []))) if (c or {}).get('moves') else {}
    if r.get('text'):
        return Blockquote(Md(r['text']), SourceLine(source_of(r, j)), id='passage', cls='quote web' if r.get('src') == 'web' else 'quote', **mv)
    wait = i is not None and s.get('research') == 'pending' and looking and val('research.on')
    poll = dict(hx_get=at(Routes.source, j['id'], i), hx_trigger='load delay:3s', hx_swap='outerHTML') if wait else {}
    return TutorWords((c or {}).get('statement', ''), FindSource(j['id'], i, s, looking) if i is not None else '',
                      id='passage', cls='pending' if wait else '', **poll, **mv)

def Figure_(jid, i, s, c):
    if not (s.get('read') or {}).get('figure'): return ''
    return Figure(Img(src=at(Routes.img, jid, i), alt=f"A figure for {(c or {}).get('name', 'this idea')}", loading='lazy'), id='figure')

def NextBar(jid, i, st, by):
    """Back to the idea before, and a quiet `Skip this idea` while the check is open. Once the check closes, the card holds
    Next idea, the one main button, and the skip goes (walk.css hides it at once, with no reload)."""
    back = A(f"← {name(by, st.steps[i - 1])}", href=at(Routes.step, jid, i - 1), cls='mute') if i else Span()
    done = (st.steps[i].get('done') or {}).get('outcome')
    skip = '' if done else Form(Quiet('Skip this idea', small=True, id='skip'), action=at(Routes.next, jid, i), method='post', cls='skip')
    return Div(back, skip, cls='next-bar')

def Note(text):
    "The tutor note under the passage, with its label: it is the tutor's words, not a quote."
    return TutorWords(text, note=True) if text else ''

def NoteSlot(jid, i, oob=False):
    "The place of the tutor note, which loads after the page. Out of band, it loads the note again: a new passage gives a new note."
    return Div(id='note', hx_get=at(Routes.note, jid, i), hx_trigger='load', hx_swap='innerHTML', data_quiet='1', **({'hx_swap_oob': 'true'} if oob else {}))

def BackFoot(b, pace=''):
    """In a side walk: the way back to the step that opened it. In the side pane it stays at the foot, and ⌥Z does the same.
    It tells the pane bar the trail and the pace (`Side walk · 1 of 1`); the bar reads the progress line from the outline."""
    return A(f"← Back to the paper: {b.here} ", Kbd('⌥Z'), href=b.href, cls='rh-back walk-back', data_rh_trail=json.dumps(b.trail), data_rh_pace=pace)

TALK_TEXT = 240   # about the characters of the passage of a primer in a talk: a short note, as in the mockup (shots/a5-beside.png)

def talk_text(text, most=TALK_TEXT):
    """The passage of a primer for the room: no picture and no heading, then whole sentences up to about `most` characters.
    The first sentence always stays; a first sentence that is very long is cut at a word, with an ellipsis."""
    t = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', text or '')
    ps = [x for x in (y.strip() for y in re.split(r'\n\s*\n', t)) if x]
    # a heading: a line that starts with #, or a short line with no end mark that has text after it
    keep = [x for k, x in enumerate(ps) if not x.startswith('#') and not (k < len(ps) - 1 and len(x) < 80 and not re.search(r'[.!?:;)"”]$', x))]
    out = []
    for x in re.split(r'(?<=[.!?])\s+', ' '.join(' '.join(p.split()) for p in keep)):
        if out and len(' '.join(out + [x])) > most: break
        out.append(x)
    said = ' '.join(out).strip()
    return said if len(said) <= 2 * most else said[:2 * most].rsplit(' ', 1)[0] + '…'

def TalkStep(j, st, by, i):
    """One idea in the side pane of a talk (`in_talk`), for the room to read: a line that says where it is, the title, a short passage
    (`talk_text`), and the figure, in the talk type (pane.css, core/talktype.js fits it to the window). It has no check, no outline,
    no skip and no tutor note (the note prepares a learner for the check), so no question opens and nothing is logged."""
    s, c, n = st.steps[i], by.get(st.steps[i]['slug']), len(st.steps)
    said = 'a quick primer' if n == 1 else f'idea {i + 1} of {n}'
    r = s.get('read') or {}
    short = {**s, 'read': {**r, 'text': talk_text(r['text'])}} if r.get('text') else s
    return Div(Div(Span(f'Beside the slide · {said}'), cls='sec-lbl'), H1(name(by, s), cls='idea'), Passage(j, short, c), Figure_(j['id'], i, s, c),
               P('Back to the slide: ', Kbd('⌥Z'), Span(cls='talk-page', hidden=True), cls='talk-back'), cls='walk-main talk-step')

def StepPage(j, st, by, i, needs=(), back=None, present=(), looking=False, vault=None, result=None):
    """One idea: the outline, the passage, the figure, the note and the check. `needs` is what other blocks add under the title, `present` under the outline.
    `result` is the card "From Leela": it takes the place of the check, so the page has it with no second request."""
    if in_talk(): return TalkStep(j, st, by, i)
    s, c = st.steps[i], by.get(st.steps[i]['slug'])
    r = s.get('read') or {}
    head = Div(*[Span(x) for x in (r.get('section'), r.get('page') and f"p. {r['page']}") if x], cls='sec-lbl')
    slot = Div(Div(Span(WRITING, cls='lbl'), Div(I(), I(), I(cls='short'), cls='skel'), cls='check'),
               id='check', hx_get=at(Routes.check, j['id'], i), hx_trigger='load', hx_swap='innerHTML', data_wait=WRITING) if result is None else Div(result, id='check')
    return Div(Rail(j, st, by, i, present),
               Div(BackFoot(back, f"Side walk · {i + 1} of {len(st.steps)}") if back else '', head, H1(name(by, s), cls='idea'), *needs, Passage(j, s, c, i, looking), Figure_(j['id'], i, s, c),
                   NoteSlot(j['id'], i), slot, leela_line(j, i, vault=vault) if s.get('leela') and (s.get('check') or {}).get('kind') != 'notebook' else '', NextBar(j['id'], i, st, by), cls='walk-main'),
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

def GoOn(jid, i, hidden=False):
    "Next idea: the one main button of a step once its check is closed. A demo check holds it hidden until the first prediction."
    return Form(Primary('Next idea', focus=True), action=at(Routes.next, jid, i), method='post', cls='row go-on', hidden=hidden)

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
        foot = Form(Textarea(name='answer', id='ans', rows=2, autofocus=True, data_draft='answer', aria_label='Your answer', placeholder='Your answer. ⌘↵ sends.'),
                    Textarea(name='thinking', id='think', rows=1, data_draft='thinking', aria_label='Think aloud', placeholder='Think aloud: how did you get there?'),
                    Div(Confidence(), Span(f"{left} {'try' if left == 1 else 'tries'} left" if tries else '', cls='mute'), cls='row conf'),
                    Div(Primary('Send', id='send', data_wait=GRADING, title='⌘↵ sends too'), hint, out, cls='row acts'),
                    hx_post=at(Routes.answer, jid, i), data_qid=q['id'], **tgt)
    return Check(CardHead(s, q), q['question'], *Thread(q), foot=(*after, foot), shut=shut)

# --- the demo and order checks ---------------------------------------------------------------------------------------

def rk_assets():
    "The rupaka runtime, which the demo block serves."
    v = version()
    return Link(rel='stylesheet', href=f'/rupaka/rupaka.css?v={v}'), Script(src=f'/rupaka/rupaka.js?v={v}')

def DemoCheck(jid, i, s, d):
    "A demo or an order check: the rupaka demo of the step, closed when you skipped it. walk.js sends each prediction, and ⌥V keeps the state."
    if d is None or (s.get('done') or {}).get('outcome') == 'skipped': return Done(jid, i, s)
    k = s['check']['kind']
    keep = Button('Keep this state ', Kbd('⌥V'), type='button', id='keep', cls='small quiet', title='Save the inputs of the demo with your last prediction')
    shut = bool(s.get('done'))
    more = dict(hx_post=at(Routes.ladder, jid, i) + '?simpler=1', hx_target='#ladder', hx_swap='outerHTML') if k == 'demo' and val('checks.demo_ladder') else None
    return Check(CardHead(s), P(LEAD[k], cls='mute'), foot=(Demo(d.spec), *rk_assets(), Feedback('demo', slug=d.slug, simpler=more), Div(keep, Span(cls='mute said', aria_live='polite'), cls='row acts'),
                                                            Slot(jid, i, s), GoOn(jid, i, hidden=not shut)), shut=shut, cls='walk-demo', data_step=str(i), data_demo=d.slug, data_kind=k, data_url=at(Routes.predict, jid, i), data_keep=at(Routes.keep, jid, i))

def Slot(jid, i, s):
    "The place for the help under a demo check. walk.js fills it after a wrong prediction; a reload fills it when the step has help."
    return Div(id='ladder', cls='ladder', **(dict(hx_get=at(Routes.ladder, jid, i), hx_trigger='load', hx_swap='outerHTML') if s.get('ladder') else {}))

def Ladder(jid, i, ld, demo=None, show=False, pending='', failed='', retry=False, more=False):
    """The help under a demo check after a wrong prediction, as one quiet block with no main button: the lesson in another way (`ld`),
    then a simpler demo. `pending` says what the tutor makes while the page asks again in 2 seconds. `more` adds the quiet button that asks for the simpler demo.
    `failed` is the plain line after a job failed; `retry` adds a button that POSTs to start the job again."""
    url = at(Routes.ladder, jid, i)
    out = [Div(Span(f"Lesson · {LABELS[ld['way']].lower()}" if ld.get('way') in LABELS else 'Lesson', cls='lbl'), Md(ld['lesson']),
               Feedback('lesson', aid=ld.get('aid', ''), way=ld.get('way', '')), cls='lesson')] if ld.get('lesson') else []
    if pending: out.append(P(pending, cls='mute making'))
    elif failed: out += [P(f'{failed} Read the passage again, or go on to the next idea.', cls='mute'), *([Div(Quiet('Try again', type='button', hx_post=url, hx_target='#ladder', hx_swap='outerHTML'), cls='row acts')] if retry else [])]
    elif demo is not None and show: out += [Span('A simpler demo', cls='lbl'), Demo(demo.spec), Feedback('demo', slug=demo.slug)]
    elif more: out.append(Div(Quiet('Show a simpler demo', type='button', hx_post=f'{url}?simpler=1', hx_target='#ladder', hx_swap='outerHTML'), cls='row acts'))
    elif demo is not None: out.append(Div(Span('A simpler demo', cls='lbl'), Quiet('Show a simpler demo', type='button', hx_get=f'{url}?show=1', hx_target='#ladder', hx_swap='outerHTML'), cls='row acts'))
    poll = dict(hx_get=url, hx_trigger='load delay:2s', hx_swap='outerHTML') if pending else {}
    return Div(*out, id='ladder', cls='ladder' + (' pending' if pending else ''), aria_live='polite', **poll, **({'data_demo': demo.slug} if demo is not None and show else {}))

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

def closed(q): return first(t for t in q.get('turns') or () if t.get('kind') == 'close')

def passing(ok, n):
    "How many tests pass, as people say it: `2 of 3 tests pass`, `the test passes`."
    return f"{ok} of {n} tests pass" if n != 1 else 'the test passes' if ok else 'the test fails'

def CodeOut(jid, i, q, r=None, oob=True):
    """The results part of a code check: hints, the results of the last run, the first error, and the close. The editor is not in it.
    After a run that closes the check, `oob` also turns off Run the tests, so Next idea is the one main button."""
    texts = [t if isinstance(t, str) else t['test'] for t in q.tests]
    close = closed(q)
    out = [Div(Span(f'Hint {n}', cls='lbl'), Md(h), cls='hint') for n, h in enumerate(q.get('hints') or (), 1)]
    if r and r.get('syntax'):
        out += [Div(Span('Syntax error: ', cls='k'), f'{r.syntax}.', cls='err'), P(f"Try {val('checks.tries') - r.tries_left + 1} of {val('checks.tries')}. A syntax error does not count as a try.", cls='mute')]
    elif r and 'checks' in r:
        n = val('checks.tries') - r.tries_left + bool(r.done and r.get('correct'))
        out += [Ul(*[Result(c, texts) for c in r.checks], cls='results') if r.checks else '',
                FirstError(r.first_error),
                P(f"Try {n} of {val('checks.tries')} · {passing(r.passed, r.total)}", cls='mute')]
    if close:
        out += [Tag(close.get('outcome')),
                Div(Span('Lesson', cls='lbl'), Md(close['lesson']), cls='lesson') if close.get('lesson') else '', GoOn(jid, i),
                RunOff(oob=True) if oob else '']
    return Div(*out, id='code-out', aria_live='polite')

def RunOff(oob=False):
    "Run the tests on a closed check: plain and off, so ⌥S presses Next idea."
    return Button('Run the tests', type='submit', form='run-form', id='run', disabled=True, **({'hx_swap_oob': 'true'} if oob else {}))

def CodeCheck(jid, i, s, q, after=(), vault=None):
    "A code check: the task, a plain editor with the stub, the visible tests, and Run. A run swaps only the results."
    if q is None: return Done(jid, i, s)
    if not s.get('code'): return Short(jid, i, s, q, after)
    c = s['code']
    draft = q['tries'][-1]['answer'] if q.get('tries') else c['stub']
    tgt = dict(hx_target='#code-out', hx_swap='innerHTML')
    hint = Button('Hint ', Kbd('⌥W'), type='button', id='hint', cls='quiet', hx_post=at(Routes.hint, jid, i), data_wait=HINTING, **tgt,
                  disabled=len(q.get('hints') or ()) >= len(HINTS))
    idk = Button('Teach me' if q.get('tries') else "I don't know", type='button', id='idk', cls='quiet', hx_post=at(Routes.giveup, jid, i),
                 data_wait=TEACHING, **tgt)
    form = Form(Textarea(draft, name='source', id='source', cls='code-editor', rows=max(6, draft.count('\n') + 3), spellcheck='false', autofocus=True,
                         aria_label='Your code'),
                Details(Summary('The tests you can see'), Ul(*[Li(Code(t)) for t in c['tests']], cls='tests'), open=True),
                id='run-form', hx_post=at(Routes.run, jid, i), **tgt)
    # Run is outside the form, so the results can hold Next idea with no nested form. On a closed check, Next idea is the main button.
    run = RunOff() if closed(q) else Primary('Run the tests', type='submit', form='run-form', id='run', data_wait=RUNNING, title='⌘↵ runs them too')
    return Check(CardHead(s, q), q['question'], foot=(form, CodeOut(jid, i, q, oob=False), Div(run, hint, idk, cls='row acts'),
                                                   leela_line(AttrDict(id=jid), i, say='Go further with real code in Leela', quiet=True, vault=vault)), cls='code-check')

# --- the notebook check: it runs in Leela ---------------------------------------------------------------------------

NB_WRITING = 'Writing the notebook…'
NB_HEAD = 'Check · notebook · runs in Leela'
NO_LEELA = 'Leela is not running. Start Leela, then press ⌥S again.'
PICK_FOLDER = 'Pick the folder of your images'

def NbHead(): return Div(Span(NB_HEAD), cls='lbl')

def Opened(t):
    "The line after Open in Leela: the time of the press, and where the result comes."
    return f"Opened in Leela at {time.strftime('%H:%M', time.localtime(t))}. The result comes back here."

def NbGo(jid, i, link=None, spec=True, opened=None):
    """Open in Leela, the main button: when Leela runs, a form that notes the time on the step and opens Leela in a new tab, else a press
    that looks again, with how to get Leela. `spec` adds Download the notebook. `opened` is the time of the last press (`leela_at`)."""
    dl = Quiet('Download the notebook', href=at(Routes.notebook, jid, i), download=True) if spec else ''
    if link: return Form(Primary('Open in Leela', type='submit'), dl,
                         Span(Opened(opened) if opened else f"Leela runs at {link.split('//', 1)[-1].split('/', 1)[0]}.", cls='mute state'),
                         method='post', action=at(Routes.leela, jid, i), target='_blank', rel='noopener', hx_boost='false', data_check=at(Routes.check, jid, i),
                         cls='row acts nb-go leela-go')
    return Div(Primary('Open in Leela', type='button', hx_get=at(Routes.check, jid, i), hx_target='#check', hx_swap='innerHTML'), dl,
               P(NO_LEELA, ' ', A('Get Leela', href=LEELA_INSTALL, target='_blank', rel='noopener'), cls='mute state'), cls='row acts nb-go')

def NbPending(jid, i, link=None, opened=None):
    "The notebook spec is not written yet: the card asks the server again in 2 seconds. Leela can open the step now."
    return Check(NbHead(), P(NB_WRITING, cls='mute making'), foot=NbGo(jid, i, link, spec=False, opened=opened), cls='pending nb-check', aria_live='polite',
                 hx_get=at(Routes.check, jid, i), hx_trigger='load delay:2s', hx_target='#check', hx_swap='innerHTML')

def NbFailed(jid, i, why, link=None, opened=None):
    "The tutor could not write the notebook spec: the reason and Try again. Leela can still open the step and make its own lesson."
    return Check(NbHead(), P(f'The tutor could not write the notebook: {why}.', cls='mute'),
                 foot=(Div(Quiet('Try again', type='button', hx_post=at(Routes.check, jid, i), hx_target='#check', hx_swap='innerHTML'), cls='row acts'),
                       NbGo(jid, i, link, spec=False, opened=opened)), cls='nb-check')

def DataRow(jid, i, d):
    "One data path of the notebook. An entry with `need` is a folder that you name, so it has a path field."
    if not d.get('need'): return Div(Code(d['name']), ' ', Span(d['path'], cls='path'), Span(f" · {d['what']}", cls='mute') if d.get('what') else '', cls='nb-data')
    return Form(Label(Span(PICK_FOLDER, cls='lbl'), Input(name='path', value=d['path'], spellcheck='false', aria_label=f"The folder for {d['name']}"), cls='nb-pick'),
                Input(type='hidden', name='name', value=d['name']), Quiet('Keep', small=True), Span(Code(d['name']), f" · {d['what']}" if d.get('what') else '', cls='mute'),
                hx_post=at(Routes.data, jid, i), hx_target='#check', hx_swap='innerHTML', cls='nb-data need')

def NotebookCard(jid, i, s, link=None):
    """The card "The notebook" of a step whose check runs in Leela: the task, the tests you can see, the data, the packages, what the run
    makes, its time and the prediction. Open in Leela is the main button (a link when Leela runs). Download the notebook is quiet."""
    nb = s['nb']
    r = nb['run']
    shown = [t['test'] for t in nb['tests'] if t['shown']]
    hidden = len(nb['tests']) - len(shown)
    parts = [Dt('Data'), Dd(*[DataRow(jid, i, d) for d in nb['data']] or ['none']),
             Dt('Packages'), Dd(', '.join(nb.get('requires', [])) or 'none for this one'),
             *([Dt('It makes'), Dd(Code(r['makes']))] if r.get('makes') else []),
             Dt('Run time'), Dd(f"about {r['minutes']:g} min (an estimate)"),
             *([Dt('Before the run'), Dd(f"Predict: {r['predict']}")] if r.get('predict') else [])]
    tests = Div(Pre('\n'.join(shown), cls='tests') if shown else '', P(n_of(hidden, 'more test') + ' that you cannot see.', cls='mute') if hidden else '')
    return Check(NbHead(), Div(Div(Md(nb['task']), cls='q'), tests, Dl(*parts, cls='nb-parts'),
                               P('This step runs in Leela, in a notebook with its packages. abhyasa does not run this code.', cls='mute nb-where')),
                 foot=NbGo(jid, i, link, opened=s.get('leela_at')), cls='nb-check')

CHECKS = dict(short=Short, demo=DemoCheck, order=DemoCheck, code=CodeCheck)   # check kind -> card; `notebook` has its own card (NotebookCard)

# --- what comes back from Leela: every text is Leela's data, so it is cut to one plain line and the page escapes it ---------

DEVICES = dict(mps='Apple GPU (mps)', cuda='NVIDIA GPU (cuda)', cpu='CPU')
COPIES = 'Images are copies in your vault.'
LEELA_WROTE = "abhyasa wrote this from Leela's attempts. Leela never changes the walk."

def plain(x, most=120) -> str:
    "`x` as one line of printable text, at most `most` characters."
    t = ' '.join(''.join(ch if ch.isprintable() else ' ' for ch in str(x if x is not None else '')).split())
    return t if len(t) <= most else t[:most - 1] + '…'

def num(v) -> str:
    "A number of a run in words: `1,000`, `0.083`, `38.5`."
    return f'{v:,.0f}' if abs(v) >= 1000 or v == int(v) else f'{v:.3g}'

def took(secs) -> str:
    "A run time in words: `45 s`, `38 min 30 s`, `2 h 5 min`."
    s = round(secs)
    if s < 60: return f'{s} s'
    if s < 3600: return f'{s // 60} min' + (f' {s % 60} s' if s % 60 else '')
    return f'{s // 3600} h' + (f' {s // 60 % 60} min' if s // 60 % 60 else '')

def run_words(r) -> str:
    "The run line: `1,000 steps in 38 min 30 s on Apple GPU (mps). Last loss 0.083.` and the other numbers."
    m = r.get('metrics') or {}
    dev = r.get('device') or ''
    said = ' '.join(x for x in (f"{num(m['steps'])} steps" if 'steps' in m else 'It ran', f"in {took(r['secs'])}" if 'secs' in r else '',
                                f"on {DEVICES.get(dev, plain(dev, 40))}" if dev else '') if x) + '.'
    if 'loss' in m: said += f" Last loss {num(m['loss'])}."
    if more := [f'{plain(k, 40)} {num(v)}' for k, v in m.items() if k not in ('steps', 'loss')]: said += f" Other numbers: {', '.join(more)}."
    return said

def check_words(c, s) -> str:
    "The check line from a `code` attempt of Leela. Leela files a check only when all the tests pass."
    if c.get('correct') is not True: return 'Not yet. Some tests do not pass.'
    n = len((s.get('nb') or {}).get('tests') or ())
    return f'Right. {n} of {n} tests pass.' if n else 'Right. The tests pass.'

def said_words(p) -> str:
    "The prediction line: `You said 0.15. It was 0.091.`"
    was = p.get('actual') if p.get('actual') not in (None, '') else p.get('expected')
    return f"You said {plain(p.get('answer'), 80)}." + (f' It was {plain(was, 80)}.' if was not in (None, '') else '')

def result_n(p) -> str:
    "The number `n` of an image path `leela/<walk>/<step>/<n>.png`."
    return p.rsplit('/', 1)[-1].split('.')[0]

def Results(jid, i, r, cls='thumbs'):
    "The images of run `r`, each from the result route of step `i`."
    ims = r.get('images') or []
    return Div(*[Img(src=Routes.of(Routes.result, jid=jid, i=i, n=result_n(p)), alt=f'Image {k + 1} of {len(ims)} from the run', loading='lazy')
                 for k, p in enumerate(ims)], cls=cls) if ims else ''

def FromLeela(j, i, b, foot=''):
    """The card "From Leela" of step `i`: when Leela filed it and the notebook, the check, the prediction against the real value,
    the run and its images. `b` is `AttrDict(check, prediction, run)` from `leela_back`. `foot` is Next idea, or Open in Leela."""
    s = j['steps'][i]
    last = max((x for x in b.values() if x), key=lambda x: x.get('at') if type(x.get('at')) in (int, float) else 0)
    nb = next((x['notebook'] for x in (b.run, b.check, b.prediction) if x and isinstance(x.get('notebook'), str) and x['notebook']), '')
    when = f"filed {time.strftime('%H:%M', time.localtime(last['at']))}" if type(last.get('at')) in (int, float) else ''
    said = ' · '.join(x for x in (when, plain('/'.join(Path(nb).parts[-2:]), 80) if nb else '') if x)
    head = Div(Span('From Leela'), Span(said, cls='why') if said else '', cls='lbl')
    rows = [*([Dt('The check'), Dd(check_words(b.check, s))] if b.check else []),
            *([Dt('Your prediction'), Dd(said_words(b.prediction))] if b.prediction else []),
            *([Dt('The run'), Dd(run_words(b.run))] if b.run else [])]
    ims = b.run and b.run.get('images')
    return Section(head, Dl(*rows), Results(j['id'], i, b.run) if ims else '', P(COPIES, cls='mute copies') if ims else '', foot,
                   cls='check raised fromleela', aria_label='From Leela')

def WhatYouMade(j, i, b):
    "The end of the walk: the last image that came back, on step `i`, with the name of its idea and the source line of its passage."
    r, s = b.run, j['steps'][i]
    p = r['images'][-1]
    rd = s.get('read') or {}
    return Section(H2('What you made'),
                   Div(Img(src=Routes.of(Routes.result, jid=j['id'], i=i, n=result_n(p)), alt=f'What you made in idea {i + 1}'),
                       Div(P(f'Idea {i + 1}', cls='lbl'), P(plain(r['makes'], 200), cls='cap') if r.get('makes') else '',
                           SourceLine(source_of(rd, j)) if rd.get('text') else '', cls='made-text'), cls='raised made'),
                   P(LEELA_WROTE, cls='mute copies'), cls='walk-made', aria_label='What you made')

# --- the end of a section --------------------------------------------------------------------------------------------

def Moved(m):
    "One concept after the checks: from what depth to what depth, in words that never read as nothing happened."
    said, count = moved_words(m)
    return Li(A(m['name'], href=f"/c/{m['concept']}"), DepthBar(m['after']), ' ', Span(said, cls='moved'), Span(f"  · {count}", cls='mute') if count else '')

def SectionDone(j, sec, ix, ms, nxt, by):
    "The end of a section that is not the last one: what moved, the ideas you skipped, and Go on."
    skipped = [name(by, j['steps'][k]) for k in ix if (j['steps'][k].get('done') or {}).get('outcome') == 'skipped']
    up, ok, n = sum(m['after'] > m['before'] for m in ms), sum(m['passed'] for m in ms), sum(m['asked'] for m in ms)
    lead = (f"{n_of(up, 'idea')} moved up." if up else f"You passed {ok} of {n_of(n, 'check')}." if ok else
            'You did not pass a check in this section yet. These ideas come back in your review.' if ms else
            'You skipped the checks in this section. You can come back to them from the outline.')
    return (Span(sec or 'The ideas', cls='lbl'), H1('Section done'), P(lead, cls='lead-sum'),
            *([H2('What moved'), Ul(*map(Moved, ms), cls='plain moved-list')] if ms else []),
            *([P('You skipped: ', ', '.join(skipped), '.', cls='mute')] if skipped else []),
            P(f"Next: {name(by, j['steps'][nxt])}.", cls='next-step'), Div(Primary('Go on', href=at(Routes.step, j['id'], nxt)), cls='row'))

def Dots(st):
    "One dot for each idea of the walk, in the colours of the outline. The fill steps stop at 5, so the sum shows within 600 ms on any walk."
    n = len(st.steps)
    return Div(*[I(cls=f'd {s.dot}', style=f'--i:{min(k, 5)}') for k, s in enumerate(st.steps)], cls='walk-dots', role='img',
               aria_label=f"{st.done} of {n_of(n, 'idea')} done")

def when_review(due, now=None):
    "The day of the first review: `today`, `tomorrow` or `in 3 days`."
    lt, now = time.localtime(due), time.localtime(now or time.time())
    days = round((time.mktime(lt[:3] + (12, 0, 0) + lt[6:]) - time.mktime(now[:3] + (12, 0, 0) + now[6:])) / 86400)
    return 'today' if days <= 0 else 'tomorrow' if days == 1 else f'in {days} days'

def WalkDone(j, st, ms, by, sides=(), due=None, end=(), present=(), made=''):
    """The end of a walk: a row of dots for all the ideas, a short sum of the walk, what moved, the side walks that you did, the
    first review, and Back to Today. `sides` is `(name, learned)`. `end` is what other blocks add (`walk_end`): when it holds
    a way out (the end of a side walk), the page does not add its own. `present` is the quiet Present of the talk block (`walk_actions`).
    `made` is what came back from Leela last (`WhatYouMade`)."""
    outs = [(s.get('done') or {}).get('outcome') for s in j['steps']]
    counts = [f"{outs.count('solid')} solid", f"{sum(o in SHAKY for o in outs)} shaky", f"{outs.count('skipped')} skipped"]
    counts = ', '.join(c for c in counts if not c.startswith('0 '))
    lead = f"{n_of(len(outs), 'idea')} from {j['title']}." + (f" {counts}." if counts else '')
    learned, looked = [n for n, ok in sides if ok], [n for n, ok in sides if not ok]
    also = [P(f"You also {verb} {' and '.join(ns)} on the way.", cls='mute') for verb, ns in (('learned', learned), ('looked at', looked)) if ns]
    go = '' if end else Div(Primary('Back to Today', href='/'), Secondary('See the graph', href='/graph'), cls='row')
    return (H1('You finished the walk'), Dots(st),
            Div(P(lead, cls='lead-sum'), *([H2('What moved'), Ul(*map(Moved, ms), cls='plain moved-list')] if ms else []), *also,
                P(f"The first review is {when_review(due)}.", cls='next-step') if due else '', cls='walk-sum', style=f"--n:{min(len(outs), 5)}"),
            made, *end, go, *([Div(*present, cls='row')] if present else []))
