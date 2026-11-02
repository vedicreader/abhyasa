"A walk on the page: the plan, then one idea at a time with the outline at the left, the passage, the figure, the tutor note and one check."
import hashlib, json, re, time
from pathlib import Path
from urllib.parse import urlencode
from fasthtml.common import *
from rupaka.render import Demo, version
from abhyasa.core import run as run_hook, pane_link, side_link, SourceLine, SourceLinks, TutorWords, source_of, n_of, moved_words, Md, DepthBar, asset_css, asset_js, Check, Msg, Tag, FirstError, OUTCOMES, Confidence, Primary, Quiet, Feedback, in_talk, Inline, can_undo, meta, UndoBar, HistoryList, JobStop, JobAgain, JobTools
from abhyasa.learner import STOPPED
from abhyasa.learner import DEPTHS, METHOD_LABELS as LABELS, WALK_WAYS
from abhyasa.tutor import HINTS
from abhyasa.learner import val
from abhyasa.models import dflt_model, where_chip
from abhyasa.core.leela import leela_line, leela_base, OpenInLeela, LEELA_INSTALL
from abhyasa.path import minutes, TOOL_WAYS, hands_count, hands_most
from abhyasa.learner import SHAKY, walk_state
from abhyasa.path import wants_source, missing_data
from .cfg import Routes

_P = Path(__file__).parent
OUTCOME = {k: t for k, (t, _) in OUTCOMES.items() if k != 'nudge'}
KIND = dict(short='short answer', demo='predict · demo', order='predict · order', notebook='notebook · in Leela')
GRADING, HINTING, TEACHING, WRITING = 'Grading…', 'Writing a hint…', 'Writing a lesson…', 'The tutor writes the check…'
LOOKING = 'Looking for a source…'
NO_SOURCE = 'The tutor found no good source on the web.'
LEAD = dict(demo='Predict first. Then the demo shows the rest.', order='Put the steps in order first. Then the demo shows the right order.')

def assets(): return asset_css(_P/'walk.css'), asset_js(_P/'walk.js')

def at(r, jid, i=None): return Routes.of(r, jid=jid, **({} if i is None else dict(i=i)))

WAIT = 'job, every 30s'   # a part that waits for a job: it loads again on an event of the stream (core.js), and every 30 seconds when the stream is not there

def name(by, s): return (by.get(s['slug']) or {}).get('name') or s['slug']

def Bar(done, total, oob=False):
    "The progress line of the outline. An answer that closes a check swaps it out of band, and its width moves (htmx settles the style)."
    return Span(I(style=f"width:{100 * done // max(total, 1)}%", id='rail-bar'), cls='prog', role='progressbar', aria_valuenow=str(done), aria_valuemax=str(total),
                id='rail-prog', **({'hx_swap_oob': 'true'} if oob else {}))

def pages(steps):
    "The pages of `steps` as 'p. 3' or 'p. 3–5'; empty when no step has a page."
    ps = sorted({s['read']['page'] for s in steps if (s.get('read') or {}).get('page')})
    return '' if not ps else f'p. {ps[0]}' if ps[0] == ps[-1] else f'p. {ps[0]}–{ps[-1]}'

def build_key(k) -> str:
    "The key of the job row of the walk made from the link or the goal key `k`."
    return 'build:' + hashlib.sha1(str(k).encode()).hexdigest()[:12]

def LinkPending(url, said, row=None):
    "A walk from a link or a goal that is still being made, with Stop for its job row `row`: the card loads again when its job changes (the event stream), or every 30 seconds."
    return Div(P(B(said if said.endswith('…') else f'{said}…')),
               P('When the walk is ready, it opens here. You can leave this page. The chip at the top tells you when it is ready. ', A('See the job', href='#activity'), cls='mute'),
               Div(JobStop(row), cls='row acts') if row is not None else '',
               cls='walk-link pending', style='animation: none', hx_get=f"{Routes.job}?{urlencode(dict(url=url))}", hx_trigger=WAIT, hx_swap='outerHTML', data_job=build_key(url))


def LinkEnded(url, line, row, *c):
    "A walk from a link or a goal that ended with no walk: the line, Plan it again for its job row `row`, and `c` (what Start filed, with its Undo). Plan it again loads the card again."
    return Div(P(line, cls='req-err'), Div(JobAgain(row, 'Plan it again'), cls='row acts') if row is not None else '', *c,
               hx_get=f"{Routes.job}?{urlencode(dict(url=url))}", hx_trigger='job', hx_swap='outerHTML', data_job=build_key(url))

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
    tag = 'known (learned elsewhere)' if s.get('elsewhere') else dict(now='now', shaky='shaky', skipped='skipped', known='you know it').get(s.dot, '')
    got = Span(' · has a source', cls='k src-ready') if (s.get('read') or {}).get('researched') or (s.get('read') or {}).get('gathered') else ''   # research found it
    return Li(A(Inline(name(by, s)), href=at(Routes.step, j['id'], k)), Span(f' · {tag}', cls='k') if tag else '', got, id=f'rail-{k}',
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
        rows.append(Li(Inline(sec) if sec else 'The ideas', cls='sec' + (' on' if i in ix else '')))
        rows += [Idea(j, by, st.steps[k], k, i) for k in ix]
    src = (' · ', A('Sources', href=walk_url(j['id'], 'sources'), cls='see-build')) if has_sources_line(j) else ()
    edit = P(A('Change the walk', href=walk_url(j['id'], 'plan')), *src, cls='change-walk')   # the plan and the line of research, on the walk page
    return Aside(P(A(Inline(j['title']), href=walk_url(j['id']), data_act='walk'), cls='rail-title'), Details(Summary(Span(f"{lbl} · {i + 1} of {len(st.steps)}", cls='lbl'), Bar(st.done, st.total)), Ol(*rows), edit), *([Div(*present, cls='rail-acts')] if present else []),
                 id='rail', cls='outline', aria_label='The walk', data_part='outline')

def FindSource(jid, i, s, looking=False):
    """Under the tutor's words of step `i`: while the tutor looks for a source on the web, a quiet line (the passage asks again in
    3 seconds); else `Find a source`, or `Look again` under `No good source was found on the web.` on its own line when a search
    found nothing, with the line that says why (`research_why`). Nothing when research is off."""
    if not val('research.on'): return ''
    if s.get('research') == 'pending' and looking: return P(LOOKING, cls='mute looking', aria_live='polite')
    none = s.get('research') == 'none'
    go = Quiet('Look again' if none else 'Find a source', small=True, type='button', hx_post=at(Routes.source, jid, i), hx_target='#passage', hx_swap='outerHTML', data_wait=LOOKING)
    if s.get('gather_err') and s.get('research') is None:   # the agent stopped with an error: Find a source, with the reason
        return (P(s.get('research_why') or '', cls='mute no-source-why'), P(go, cls='mute find-source'))
    if none and s.get('gather_none'):   # the gather agent read for this idea and found nothing: what it read is in its log
        return (P(s.get('research_why') or NO_SOURCE, cls='mute no-source'), P(ShowLog(jid), ' ', go, cls='mute find-source'))
    why = P(s['research_why'], cls='mute no-source-why') if none and s.get('research_why') else ''
    return (P(NO_SOURCE, cls='mute no-source') if none else '', why, P(go, cls='mute find-source'))

# --- the gather agent: the band, and the log of what it read and filed ------------------------------------------------

TOOL_WORDS = dict(web_search='Searched the web', fetch_page='Read a page', gh_clone='Cloned a repo', read_gh_repo='Listed files in a repo',
                  read_file='Read a file', file_source='Opened a source', docs='Listed documents', read_doc='Read a document',
                  put_passage='Gave a passage', put_notebook='Gave a notebook', note='Note from the agent', spend='Spend',
                  start='Could not start the agent')

def hm(t) -> str: return time.strftime('%H:%M', time.localtime(t)) if t else ''

def idea_no(j, slug) -> int|None:
    "The number (from 1) of the step on the concept `slug` in walk `j` now, or None."
    return next((k + 1 for k, s in enumerate(j['steps']) if s['slug'] == slug), None) if slug else None

def ShowLog(jid): return pane_link('Show what it did', at(Routes.gather_log, jid), 'What the agent did', cls='pane-link show-log', data_act='show-log')

def gather_counts(j) -> AttrDict:
    "The documents that the agent read, the documents of the sources (at least the ones read), and the ideas with a passage of all the ideas."
    read = sum(r.get('outcome') == 'read' for r in j.get('gather') or ())
    ideas = [s for s in j['steps'] if s.get('status') != 'skip']
    return AttrDict(read=read, total=max(j.get('gather_total') or 0, read), have=sum(bool((s.get('read') or {}).get('text')) for s in ideas), ideas=len(ideas))

def of_ideas(have, ideas, what) -> str:
    "`7 of 10 ideas have a source`, with `has` when one idea is meant: `1 of 9 ideas has a source`."
    return f"{have} of {n_of(ideas, 'idea')} {'has' if have == 1 or ideas == 1 else 'have'} {what}"

def gather_words(j) -> tuple:
    "`38 of 120 documents read` and `7 of 10 ideas have a passage`."
    n = gather_counts(j)
    docs = f"{n.read} of {n_of(n.total, 'document')} read" if n.total > n.read else f"{n_of(n.read, 'document')} read"
    return docs, of_ideas(n.have, n.ideas, 'a passage')

START_NOW = "You can start now. Ideas without a source show the tutor's note, and they fill in as sources come."

def left_words(secs) -> str:
    "The time left as the learner reads it: `About 6 minutes left.`; nothing when it is not known."
    if secs is None: return ''
    if secs < 60: return 'Less than a minute left.'
    m = round(secs / 60)
    return f"About {m} minute{'' if m == 1 else 's'} left."

def beat_words(secs) -> str:
    "The time since the last step of research, so the learner sees that it is alive: `Last step 12 s ago.`"
    if secs is None: return ''
    return f'Last step {int(secs)} s ago.' if secs < 120 else f'Last step {int(secs // 60)} min ago.'

def doing_words(s) -> str:
    "What research does now: `Reads train_dreambooth_lora.py for idea 3.`"
    if not s.doing: return 'Starts the search.'
    return f"{'Does' if s.doing.startswith('a web search') else 'Reads'} {s.doing}" + (f' for idea {s.idea}' if s.idea else '') + '.'

def ended_words(s) -> str:
    "How research of a walk ended, with the time: `Research ended at 13:42.`"
    t = hm(s.end_at)
    return {'done': f'Research ended at {t}.', 'you': f'You stopped research at {t}.', 'time': f'The time for research ended at {t}.',
            'closed': 'Research stopped because abhyasa closed.'}.get(s.ended, '')

def who_words(j) -> str:
    "Who does the research of an agent, and where the words go: `The agent runs on claude/sonnet (hosted · Anthropic). Search words go to the web.`"
    if (j.get('gather_at') or 0) < (j.get('research_start') or 0): return 'Search words go to the web.'
    m = dflt_model()
    return f'The agent runs on {m} ({where_chip(m)}). Search words go to the web.'

def walk_url(jid, part='') -> str: return at(Routes.one, jid) + (f'#{part}' if part else '')

def has_sources_line(j) -> bool:
    "Whether walk `j` has a line of research to show: research ran, or research is on and an idea has no source."
    return bool(j.get('research_start') or j.get('gather_at') or (val('research.on') and any(wants_source(s) for s in j['steps'])))

def GatherBand(j, s, stopping=False, plan=False):
    """The line of research of walk `j`, from its state `s` (`research.research_state`), on the plan page and on each step. While it
    runs: what it reads now, the ideas with a source, the time left, the time since its last step, `Stop`, `Show what it did` and
    on the walk page, that the walk can start now. It loads again on each event of its walk in the stream. After it ends: the ideas with a source,
    how it ended and when, the quotes that abhyasa refused, and `Find sources again` for the ideas with no source. Nothing before research starts."""
    jid = j['id']
    if not (s.running or s.ended or j.get('gather_at')):   # research never ran: Find sources for the ideas with no source, when research is on
        n = gather_counts(j)
        if not (val('research.on') and n.have < n.ideas): return Div(id='gather')
        go = Quiet('Find sources', small=True, type='button', hx_post=at(Routes.gather_again, jid), hx_target='#gather', hx_swap='outerHTML', data_wait='Starting…', data_act='find-again')
        return Div(P(f"{of_ideas(n.have, n.ideas, 'a source')}. Research did not look for sources yet."),
                   Div(go, cls='row'), id='gather', cls='gather-band')
    log = ShowLog(jid) if j.get('gather') else ''
    n = gather_counts(j)   # each idea of the walk that is not skipped, not only the ideas that research looked at
    have = f"{of_ideas(n.have, n.ideas, 'a source')}."
    if s.running:
        stop = (Span('Stopping…', cls='mute') if stopping else
                Quiet('Stop', small=True, type='button', hx_post=at(Routes.gather_stop, jid), hx_target='#gather', hx_swap='outerHTML', data_wait='Stopping…', data_act='stop'))
        line = ' '.join(x for x in (doing_words(s), have, left_words(s.left), beat_words(s.beat)) if x)
        return Div(P(line), P(who_words(j), cls='mute') if who_words(j) else '', P(START_NOW, cls='mute start-now') if plan else '', Div(log, stop, cls='row'), id='gather', cls='gather-band running',
                   aria_live='polite', hx_get=at(Routes.gather, jid) + ('?plan=1' if plan else ''), hx_trigger=WAIT, hx_swap='outerHTML', data_job=f'walk:{jid}')
    why = j.get('gather_why') or ''
    refused = f" abhyasa left out {n_of(s.refused, 'quote')} that did not match the source word for word." if s.refused else ''
    again = (Quiet('Find sources again', small=True, type='button', hx_post=at(Routes.gather_again, jid), hx_target='#gather', hx_swap='outerHTML',
                   data_wait='Starting…', data_act='find-again') if n.have < n.ideas and val('research.on') else '')
    return Div(P(f"{have} {ended_words(s)}{refused}"), P(why, cls='mute') if why else '', Div(log, again, cls='row'), id='gather', cls='gather-band')

def SourceReady(jid, i):
    "The quiet line on a step whose source came while the learner reads: the page does not change until the learner asks."
    return P(A('A source is ready. Show it', href='#', hx_get=at(Routes.source, jid, i), hx_target='#passage', hx_swap='outerHTML'), cls='mute source-ready')

def _target(r):
    "The target of log row `r`: a link to the page on the web (a new tab) or to the document in your vault, else plain text."
    t, u = r.get('target') or '', r.get('link') or ''
    return side_link(t or u, u, t) if u.startswith(('http://', 'https://', '/')) else Span(t)

def GatherLog(j):
    "The log of the gather agent of walk `j`, newest first: the time, what it did, the target with its link, and the outcome. A note from the agent is marked as its own words."
    rows = list(reversed(j.get('gather') or ()))
    docs, ideas = gather_words(j)
    def item(r):
        idea = f" · idea {n}" if (n := idea_no(j, r.get('idea'))) else ''
        if r.get('tool') == 'note': return Li(Span(hm(r.get('at')), cls='k'), ' ', B(TOOL_WORDS['note']), ' ', Q(r.get('outcome') or '', cls='agent-note'), cls='glog note')
        bad = str(r.get('outcome') or '').startswith(('refused', 'not read'))
        return Li(Span(hm(r.get('at')), cls='k'), ' ', B(TOOL_WORDS.get(r.get('tool'), r.get('tool') or '')), ' ', _target(r), Span(f" · {r.get('outcome') or ''}{idea}", cls='mute'),
                  cls='glog refused' if bad else 'glog')
    return (H1('What the agent did'), P(f'{docs}. {ideas}. A note from the agent is its own words, not a source.', cls='mute'),
            Ol(*map(item, rows), cls='gather-log') if rows else P('The agent did nothing yet.', cls='mute'))

def Passage(j, s, c, i=None, looking=False, quiet=False):
    """The passage from the source, word for word, with its `SourceLine`; with no passage, the statement of the idea, marked as the
    tutor's words. With `i`, a step with no passage can look for a source (`FindSource`).
    `data-moves` holds the words that the idea moves: walk.js links them to the parts of the demo."""
    r = s.get('read') or {}
    mv = dict(data_moves=json.dumps(list((c or {}).get('moves') or []))) if (c or {}).get('moves') else {}
    if r.get('text') and quiet and i is not None:   # the source came while the learner reads: say so, and change nothing
        return TutorWords((c or {}).get('statement', ''), SourceReady(j['id'], i), id='passage', data_part='passage', **mv)
    if r.get('text'):
        also = [Div(Md(a.get('text') or ''), SourceLine(source_of(a, j)), cls='also') for a in r.get('also') or () if a.get('text')]   # a merge keeps both passages
        cell = r['cells'][0] if isinstance(r.get('cells'), list) and r['cells'] and isinstance(r['cells'][0], int) else None
        go = CopyGo(j, i) if i is not None and (j.get('notebook') or {}).get('path') else None   # a notebook walk opens its learning copy at this section
        return Blockquote(Md(r['text']), SourceLine(source_of(r, j), cell=cell, leela=go), SourceLinks(r.get('links')), *also, id='passage', cls='quote web' if r.get('src') == 'web' else 'quote', data_part='passage', **mv)   # `links`: the lesson notebook and the video of a transcript
    wait = i is not None and s.get('research') == 'pending' and looking and val('research.on')
    poll = dict(hx_get=at(Routes.source, j['id'], i) + '?quiet=1', hx_trigger=WAIT, hx_swap='outerHTML', data_job=f"walk:{j['id']}") if wait else {}
    return TutorWords((c or {}).get('statement', ''), FindSource(j['id'], i, s, looking) if i is not None else '',
                      id='passage', cls='pending' if wait else '', data_part='passage', **poll, **mv)

def fig_caption(r) -> str:
    "The caption of the figure of a passage, as the paper gives it: `caption`, or the alt text of the image of `figure` in the passage."
    if r.get('caption'): return r['caption']
    m = next((m for m in re.finditer(r'!\[([^\]]+)\]\(([^)\s]+)', r.get('text') or '') if m[2] == r.get('figure')), None)
    return m[1].strip() if m else ''

def Figure_(jid, i, s, c):
    "The figure of the step. Its alt is the caption of the paper when the data has it."
    r = s.get('read') or {}
    if not r.get('figure'): return ''
    return Figure(Img(src=at(Routes.img, jid, i), alt=fig_caption(r) or f"A figure for {(c or {}).get('name', 'this idea')}", loading='lazy'), id='figure')

def NextBar(jid, i, st, by):
    """Back to the idea before, and a quiet `Skip this idea` while the check is open. Once the check closes, the card holds
    Next idea, the one main button, and the skip goes (walk.css hides it at once, with no reload)."""
    back = A('← ', Inline(name(by, st.steps[i - 1])), href=at(Routes.step, jid, i - 1), cls='mute') if i else Span()   # a name can hold maths, as in the outline
    done = (st.steps[i].get('done') or {}).get('outcome')
    skip = '' if done else Form(Quiet('Skip this idea', small=True, id='skip'), action=at(Routes.next, jid, i), method='post', cls='skip')
    return Div(back, skip, cls='next-bar')

def Words(rows, oob=False):
    """Words to know, before the passage: each term that you do not know yet in bold, as a link to its concept in the side pane (so the
    place stays), and one plain line on what it means. An empty place when you know them all. `oob` swaps it in after the check came."""
    kw = dict(hx_swap_oob='true') if oob else {}
    if not rows: return Div(id='words', **kw)
    items = [Li(side_link(B(Inline(r.name)), f'/c/{r.slug}', r.name, cls='pane-link term', data_act='word'), ': ', Span(Inline(r.line), cls='line')) for r in rows]
    return Div(Span('Words to know', cls='lbl'), Ul(*items, cls='terms'), id='words', cls='words', data_part='words', **kw)

def Note(text):
    "The tutor note under the passage, with its label: it is the tutor's words, not a quote."
    return TutorWords(text, note=True) if text else ''

def NoteSlot(jid, i, oob=False):
    "The place of the tutor note, which loads after the page. Out of band, it loads the note again: a new passage gives a new note."
    return Div(id='note', hx_get=at(Routes.note, jid, i), hx_trigger='load', hx_swap='innerHTML', data_quiet='1', data_part='note', **({'hx_swap_oob': 'true'} if oob else {}))

def BackFoot(b, pace=''):
    """In a side walk: the way back to the step that opened it. In the side pane it stays at the foot, and ⌥Z does the same.
    It tells the pane bar the trail and the pace (`Side walk · 1 of 1`); the bar reads the progress line from the outline."""
    return A(f"← Back to {b.get('title') or 'the paper'}: {b.here} ", Kbd('⌥Z'), href=b.href, cls='rh-back walk-back', data_rh_trail=json.dumps(b.trail), data_rh_pace=pace)

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

def TalkStep(j, st, by, i, figure=True):
    """One idea in the side pane of a talk (`in_talk`), for the room to read: a line that says where it is, the title, a short passage
    (`talk_text`), and the figure, in the talk type (pane.css, core/talktype.js fits it to the window). It has no check, no outline,
    no skip and no tutor note (the note prepares a learner for the check), so no question opens and nothing is logged."""
    s, c, n = st.steps[i], by.get(st.steps[i]['slug']), len(st.steps)
    said = 'a quick primer' if n == 1 else f'idea {i + 1} of {n}'
    r = s.get('read') or {}
    short = {**s, 'read': {**r, 'text': talk_text(r['text'])}} if r.get('text') else s
    return Div(Div(Span(f'Beside the slide · {said}'), cls='sec-lbl'), H1(name(by, s), cls='idea', data_concept=s.get('slug')), Passage(j, short, c), Figure_(j['id'], i, s, c) if figure else '',
               P('Back to the slide: ', Kbd('⌥Z'), Span(cls='talk-page', hidden=True), cls='talk-back'), cls='walk-main talk-step')

def StepPage(j, st, by, i, needs=(), back=None, present=(), looking=False, vault=None, result=None, figure=True, words=()):
    """One idea: the outline, the passage, the figure, the note and the check. `needs` is what other blocks add under the title, `present` under the outline.
    `result` is the card "From Leela": it takes the place of the check, so the page has it with no second request. `figure=False`: the file of the figure is not there, so no image.
    `words` are the terms of Words to know, under the needs line and before the passage."""
    if in_talk(): return TalkStep(j, st, by, i, figure)
    s, c = st.steps[i], by.get(st.steps[i]['slug'])
    r = s.get('read') or {}
    head = Div(*[Inline(x) for x in (r.get('section'), r.get('page') and f"p. {r['page']}") if x], cls='sec-lbl')   # a section name can hold markdown, such as *gradient descent*
    slot = Div(Div(Span(WRITING, cls='lbl'), Div(I(), I(), I(cls='short'), cls='skel'), cls='check'),
               id='check', hx_get=at(Routes.check, j['id'], i), hx_trigger='load', hx_swap='innerHTML', data_wait=WRITING, data_part='check') if result is None else Div(result, id='check', data_part='check')
    return Div(Rail(j, st, by, i, present),
               Div(BackFoot(back, f"Side walk · {i + 1} of {len(st.steps)}") if back else '', head, H1(name(by, s), cls='idea', data_concept=s.get('slug')), *needs, Words(words), Passage(j, s, c, i, looking), Figure_(j['id'], i, s, c) if figure else '',
                   NoteSlot(j['id'], i), slot, leela_line(j, i, vault=vault) if s.get('leela') and (s.get('check') or {}).get('kind') != 'notebook' else '', NextBar(j['id'], i, st, by), cls='walk-main'),
               cls='walk-layout')

# --- the short-answer check ------------------------------------------------------------------------------------------

BARE_TEX = re.compile(r'(?<![\w\\$])([A-Za-z])_(\{[^{}\s]{1,12}\}|[A-Za-z0-9]{1,3})(?!\w)')

def bare_tex(s:str) -> str:
    "The words of a board as maths for `Md`: a bare W_Q or d_{k} (one letter with a short subscript) goes between $ signs. Text with a $ stays as it is."
    return s if '$' in (s or '') else BARE_TEX.sub(r'$\1_\2$', s or '')

def Turn(t, n):
    "One message on the check after the question: your try, a nudge, a hint, or the close."
    k = t.get('kind')
    if t['who'] == 'you':
        sure = f" · {t['confidence']}% sure" if t.get('confidence') is not None else ''
        return Msg(f'You{sure}', Md(t['text']) if t.get('text') else P('No answer.', cls='mute'), cls='you')
    if k == 'nudge': return Msg(Tag('nudge'), Md(t.get('text', '')), FirstError(t.get('first_error')))
    if k == 'hint' and t.get('via') == 'board': return Msg(f'Hint {n} of {len(HINTS)} (from the board)', Md(bare_tex(t.get('text', ''))), cls='hint')
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

def GoOn(jid, i, hidden=False, main=None):
    """Next idea: the one main button of a step once its check is closed. A demo check holds it hidden until the first prediction.
    On the last idea of a side walk, `main` is the name of the main idea, the step that opened the side walk: the button goes back to it."""
    label, act = (f'Back to the main idea: {main}', 'back') if main else ('Next idea', 'next')
    return Form(Primary(label, focus=True, data_act=act), action=at(Routes.next, jid, i), method='post', cls='row go-on', hidden=hidden)

def CardHead(s, q=None):
    ck = s.get('check') or {}
    depth = DEPTHS[q.depth] if q else DEPTHS[ck.get('depth', 2)]
    way = LABELS.get(q.get('method') if q else ck.get('way'), '')
    why = '' if re.fullmatch(r'.* fits? this idea', ck.get('why') or '') else ck.get('why') or ''   # an old plan says only "<way> fits this idea": the label names the way already
    return Div(Span(' · '.join(x for x in ('Check', way.lower(), depth) if x)), Span(why, cls='why') if why else '', cls='lbl')

LONG_Q = 160   # a question longer than this is folded in a done check

def Did(a, where=('', '')):
    """What you did in a closed check: the question (folded when it is long), your answer, the grade and the feedback of the tutor, and
    when and where, with a link to that walk or session in the side pane."""
    q = str(a.get('question') or '')
    ask = Details(Summary('The question'), Md(q), cls='did-q') if len(q) > LONG_Q else Div(Md(q), cls='did-q')
    grade = f" · {a['grade']}/10" if isinstance(a.get('grade'), int) else ''
    title, href = where
    when = time.strftime('%-d %b', time.localtime(a['at'])) if a.get('at') else ''
    return Div(ask, P(Span('You said', cls='lbl'), ' ', a.get('answer') or "I don't know", cls='did-a'),
               P(Span(f"{'Right' if a.get('correct') else 'Not yet'}{grade}", cls='lbl'), ' ', Inline(a.get('feedback') or ''), cls='did-f') if a.get('feedback') or grade else '',
               P(when, ', in ' if when and title else 'In ' if title else '', side_link(title, href, title) if title else '', cls='mute did-at') if when or title else '', cls='did')

OLD_DONE = 'Marked done when your old path became this walk. Its answer is not kept.'

def Done(jid, i, s):
    """A check that is done, when its thread is not in memory any more: what you did (`Did`, from `s['did']`), or a plain line when its
    answer is not kept, and a quiet Do it again. Next idea stays the main button."""
    o = (s.get('done') or {}).get('outcome')
    say = ('You skipped this check.' if o == 'skipped' else f"You did this check: {OUTCOME[o].lower()}." if o in OUTCOME
           else 'This check is not open. Load the page again.')
    if (a := s.get('did')): body = (P(say), Did(a, s.get('did_where') or ('', '')))
    elif o in OUTCOME and o != 'skipped': body = (P(say), P(OLD_DONE if not (s.get('done') or {}).get('aid') else 'Its answer is not kept.', cls='mute'))
    else: body = (P(say),)
    redo = Quiet('Do it again', small=True, type='button', hx_post=at(Routes.again, jid, i), hx_target='#check', hx_swap='innerHTML', data_act='do-again') if o in OUTCOME else ''
    return Check(CardHead(s), *body, foot=(GoOn(jid, i, main=s.get('main')), redo), cls='done')

def Explain():
    "Explain in the row of a check: it opens the guide (guide.js), as Caps+E does."
    return Button('Explain', type='button', cls='quiet', data_guide_open='1', data_act='explain', title='The tutor explains what you see on this page. Caps+E does the same.')

def walk_q(q, jid):
    "Question `q` as the tools of a walk check see it: its `meta` names walk `jid`, also when an older question on the shelf has no `walk`, so the demo block adds no second Show me."
    return AttrDict({**q, 'meta': {**(q.get('meta') or {}), 'walk': jid}})

def Short(jid, i, s, q, after=()):
    "A short-answer check: the question, the thread so far, what other blocks add (`after`), then the answer box, or the close and Next idea."
    if q is None: return Done(jid, i, s)
    shut = any(t.get('kind') == 'close' for t in q.get('turns') or ())
    tgt = dict(hx_target='#check', hx_swap='innerHTML')
    if shut: foot = GoOn(jid, i, main=s.get('main'))
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
                    Div(Primary('Send', id='send', data_wait=GRADING, title='⌘↵ sends too', data_act='send'), hint, Explain(), *run_hook('check_show', jid, i, s), out,
                        *run_hook('check_stuck', jid, i, s, q), *run_hook('answer_tools', walk_q(q, jid), 'ans'), cls='row acts'),   # stuck: Hint, Explain, Show (the demo block), Teach me, Learn it (the detour block); then the voice block: Speak ⌥D
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
                                                            Slot(jid, i, s), GoOn(jid, i, hidden=not shut, main=s.get('main'))), shut=shut, cls='walk-demo', data_step=str(i), data_demo=d.slug, data_kind=k, data_url=at(Routes.predict, jid, i), data_keep=at(Routes.keep, jid, i))

def Slot(jid, i, s):
    "The place for the help under a demo check. walk.js fills it after a wrong prediction; a reload fills it when the step has help."
    return Div(id='ladder', cls='ladder', **(dict(hx_get=at(Routes.ladder, jid, i), hx_trigger='load', hx_swap='outerHTML') if s.get('ladder') else {}))

def Ladder(jid, i, ld, demo=None, show=False, pending='', failed='', retry=False, more=False, job='', stop='', again='Try again'):
    """The help under a demo check after a wrong prediction, as one quiet block with no main button: the lesson in another way (`ld`),
    then a simpler demo. `pending` says what the tutor makes; the block loads again on the event of its job row `job`, and every 30 seconds. `more` adds the quiet button that asks for the simpler demo.
    `failed` is the plain line after a job failed or you stopped it; `retry` adds a button (with the words `again`) that POSTs to start the job again. `stop` is Stop of the job that runs."""
    url = at(Routes.ladder, jid, i)
    out = [Div(Span(f"Lesson · {LABELS[ld['way']].lower()}" if ld.get('way') in LABELS else 'Lesson', cls='lbl'), Md(ld['lesson']),
               Feedback('lesson', aid=ld.get('aid', ''), way=ld.get('way', '')), cls='lesson')] if ld.get('lesson') else []
    if pending: out += [P(pending, cls='mute making'), Div(stop, cls='row acts') if stop else '']
    elif failed: out += [P(f'{failed} Read the passage again, or go on to the next idea.', cls='mute'), *([Div(Quiet(again, type='button', hx_post=url, hx_target='#ladder', hx_swap='outerHTML'), cls='row acts')] if retry else [])]
    elif demo is not None and show: out += [Span('A simpler demo', cls='lbl'), Demo(demo.spec), Feedback('demo', slug=demo.slug)]
    elif more: out.append(Div(Quiet('Show a simpler demo', type='button', hx_post=f'{url}?simpler=1', hx_target='#ladder', hx_swap='outerHTML'), cls='row acts'))
    elif demo is not None: out.append(Div(Span('A simpler demo', cls='lbl'), Quiet('Show a simpler demo', type='button', hx_get=f'{url}?show=1', hx_target='#ladder', hx_swap='outerHTML'), cls='row acts'))
    poll = dict(hx_get=url, hx_trigger=WAIT, hx_swap='outerHTML', data_job=job) if pending else {}
    return Div(*out, id='ladder', cls='ladder' + (' pending' if pending else ''), aria_live='polite', **poll, **({'data_demo': demo.slug} if demo is not None and show else {}))

def Pending(jid, i, s, job='', row=None):
    """The demo of the step is not ready: Stop for its job row `row`, or Make it again after you stopped it. The card loads again on the
    event of its job row `job`, and every 30 seconds."""
    if row is not None and row.state == 'stopped':
        return Check(CardHead(s), P(f'{STOPPED} The demo is not made.', cls='mute'), foot=Div(JobAgain(row, 'Make it again'), cls='row acts'),
                     cls='pending', hx_get=at(Routes.check, jid, i), hx_trigger=WAIT, hx_target='#check', hx_swap='innerHTML', data_job=job)
    return Check(CardHead(s), P('The tutor is making the demo for this idea. This can take a minute. You can read the passage while you wait.', cls='mute'),
                 foot=Div(JobStop(row), cls='row acts') if row is not None else '',
                 cls='pending', hx_get=at(Routes.check, jid, i), hx_trigger=WAIT, hx_target='#check', hx_swap='innerHTML', data_job=job)


# --- the notebook check: it runs in Leela ---------------------------------------------------------------------------

NB_WRITING = 'Writing the notebook…'
NB_LATER = 'the notebook is not written yet'
NB_NOT_YET = 'The notebook is not written yet.'
NB_NONE = 'the tutor could not write the notebook'
NB_HEAD = 'Check · notebook · runs in Leela'
NO_LEELA = 'Leela is not running. Start Leela, then press {} again.'

def NbHead(): return Div(Span(NB_HEAD), cls='lbl')

def Opened(t):
    "The line after Open in Leela: the time of the press, and where the result comes."
    return f"Opened in Leela at {time.strftime('%H:%M', time.localtime(t))}. The result comes back here."

def NbGo(jid, i, link=None, spec=True, opened=None):
    """Open in Leela: when Leela runs, a form that notes the time on the step and opens Leela in a new tab, else a press that looks again,
    with how to get Leela. `opened` is the time of the last press (`leela_at`). It is the main button only when the notebook `spec` is written."""
    btn = Primary if spec else Quiet
    if link: return Form(btn('Open in Leela', type='submit', data_act='open-leela'),
                         Span(Opened(opened) if opened else f"Leela runs at {link.split('//', 1)[-1].split('/', 1)[0]}.", cls='mute state'),
                         method='post', action=at(Routes.leela, jid, i), target='_blank', rel='noopener', hx_boost='false', data_check=at(Routes.check, jid, i),
                         cls='row acts nb-go leela-go')
    return Div(btn('Open in Leela', type='button', hx_get=at(Routes.check, jid, i), hx_target='#check', hx_swap='innerHTML', data_act='open-leela'),
               P(NO_LEELA.format('⌥S' if spec else 'Open in Leela'), ' ', A('Get Leela', href=LEELA_INSTALL, target='_blank', rel='noopener'), cls='mute state'), cls='row acts nb-go')

def NbPending(jid, i, link=None, opened=None, row=None):
    "The notebook spec is not written yet, with Stop for its job row `row`: the card loads again when its job ends (the event stream). Leela can open the step now."
    return Check(NbHead(), P(NB_WRITING, cls='mute making'), foot=(Div(JobStop(row), cls='row acts') if row is not None else '', NbGo(jid, i, link, spec=False, opened=opened)), cls='pending nb-check', aria_live='polite',
                 hx_get=at(Routes.check, jid, i), hx_trigger=WAIT, hx_target='#check', hx_swap='innerHTML', data_job=f'walk:{jid}')

def NbNotYet(jid, i, link=None, opened=None, stopped=False):
    """The notebook spec is not written and no job writes it (`stopped`: you stopped the job): Write the notebook, the main button, starts the job.
    Open in Leela is a quiet action."""
    return Check(NbHead(), P(f'{STOPPED} {NB_NOT_YET}' if stopped else NB_NOT_YET, cls='mute'),
                 foot=(Div(Primary('Write the notebook', type='button', data_act='write-notebook', hx_post=at(Routes.check, jid, i), hx_target='#check', hx_swap='innerHTML'), cls='row acts'),
                       NbGo(jid, i, link, spec=False, opened=opened)), cls='nb-check')

def NbFailed(jid, i, why, link=None, opened=None):
    "The tutor could not write the notebook spec: the reason and Try again, the main button. Leela can still open the step and make its own lesson."
    return Check(NbHead(), P(f'The tutor could not write the notebook: {why}.', cls='mute'),
                 foot=(Div(Primary('Try again', type='button', data_act='write-notebook', hx_post=at(Routes.check, jid, i), hx_target='#check', hx_swap='innerHTML'), cls='row acts'),
                       NbGo(jid, i, link, spec=False, opened=opened)), cls='nb-check')

def DataRow(d):
    "One data entry of the notebook: its name, its folder under Your data, and what it holds. An entry with no path is a folder that you must add."
    return Div(Code(d['name']), ' ', Span(d['path'], cls='path') if d.get('path') else '', Span(f" · {d['what']}", cls='mute') if d.get('what') else '',
               cls='nb-data' if d.get('path') else 'nb-data need')

def setters(jid, data):
    "The folder setter of each data entry in `data` (from the add block), for walk `jid`."
    return [x for d in data for x in run_hook('data_setter', d, jid)]

def DataNeed(jid, i, data):
    """Before Open in Leela: `This step needs 2 folders on this Mac:` and a folder setter for each data entry with no folder under Your data.
    When the walk needs no more folders (the event `data-done`), the card loads again. None when each entry has a folder."""
    if not (gone := [d for d in data if not d.get('path')]): return None
    return Div(P(f"This step needs {n_of(len(gone), 'folder')} on this Mac:", cls='nb-need-say'), Div(*setters(jid, gone), cls='data-sets'),
               cls='nb-need', data_part='data-need', hx_get=at(Routes.check, jid, i), hx_trigger='data-done from:body', hx_target='#check', hx_swap='innerHTML')

def NotebookCard(jid, i, s, link=None):
    """The card "The notebook" of a step whose check runs in Leela: the task, the tests you can see, the data, the packages, what the run
    makes, its time and the prediction. Open in Leela is the main button (a link when Leela runs)."""
    nb = s['nb']
    r = nb['run']
    shown = [t['test'] for t in nb['tests'] if t['shown']]
    hidden = len(nb['tests']) - len(shown)
    parts = [Dt('Data'), Dd(*[DataRow(d) for d in nb['data']] or ['none']),
             Dt('Packages'), Dd(', '.join(nb.get('requires', [])) or 'none for this one'),
             *([Dt('It makes'), Dd(Code(r['makes']))] if r.get('makes') else []),
             Dt('Run time'), Dd(f"about {r['minutes']:g} min (an estimate)"),
             *([Dt('Before the run'), Dd(f"Predict: {r['predict']}")] if r.get('predict') else [])]
    tests = Div(Pre('\n'.join(shown), cls='tests') if shown else '', P(n_of(hidden, 'more test') + ' that you cannot see.', cls='mute') if hidden else '')
    return Check(NbHead(), Div(Div(Md(nb['task']), cls='q'), tests, Dl(*parts, cls='nb-parts'),
                               P('This step runs in Leela, in a notebook with its packages. abhyasa does not run this code.', cls='mute nb-where'), DataNeed(jid, i, nb['data'])),
                 foot=NbGo(jid, i, link, opened=s.get('leela_at')), cls='nb-check')

CHECKS = dict(short=Short, demo=DemoCheck, order=DemoCheck)   # check kind -> card; `notebook` has its own card (NotebookCard)

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
    return Li(side_link(m['name'], f"/c/{m['concept']}", m['name']), DepthBar(m['after']), ' ', Span(said, cls='moved'), Span(f"  · {count}", cls='mute') if count else '')

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
            P('Next: ', Inline(name(by, j['steps'][nxt])), '.', cls='next-step'), Div(Primary('Go on', href=at(Routes.step, j['id'], nxt)), cls='row'))

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

def weak_of(j) -> list:
    "The concepts of the ideas of walk `j` that a check closed with a miss or as shaky, in order."
    return [s['slug'] for s in j['steps'] if (o := (s.get('done') or {}).get('outcome')) and o not in ('solid', 'skipped')]

def WalkEnd(j, st, ms, by, sides=(), due=None, end=(), made=''):
    """The end of a walk, on its page: a row of dots for all the ideas, a short sum, what moved, the side walks that you did, what you
    made in Leela (`made`), the first review, what other blocks add (`walk_end`), and Review the weak ideas, the main button. `sides` is `(name, learned)`."""
    outs = [(s.get('done') or {}).get('outcome') for s in j['steps']]
    counts = [f"{outs.count('solid')} solid", f"{sum(o in SHAKY for o in outs)} shaky", f"{outs.count('skipped')} skipped"]
    counts = ', '.join(c for c in counts if not c.startswith('0 '))
    lead = f"{n_of(len(outs), 'idea')} from {j['title']}." + (f" {counts}." if counts else '')
    learned, looked = [n for n, ok in sides if ok], [n for n, ok in sides if not ok]
    also = [P(f"You also {verb} {' and '.join(ns)} on the way.", cls='mute') for verb, ns in (('learned', learned), ('looked at', looked)) if ns]
    weak = weak_of(j)
    to = weak[0] if weak else next((s['slug'] for s in j['steps'] if (s.get('done') or {}).get('outcome') not in (None, 'skipped')), j['steps'][0]['slug'])
    go = Primary('Review the weak ideas' if weak else 'Review this walk', href=f'/start?{urlencode(dict(focus=to))}', data_act='review')
    return Section(H2('You finished the walk.'), Dots(st),
                   Div(P(lead, cls='lead-sum'), *([H3('What moved'), Ul(*map(Moved, ms), cls='plain moved-list')] if ms else []), *also,
                       P(f"The first review is {when_review(due)}.", cls='next-step') if due else '', cls='walk-sum', style=f"--n:{min(len(outs), 5)}"),
                   made, *end, Div(go, cls='row'), id='result', data_part='result', cls='walk-result')

CHANGE_SAY = 'What should change? For example: make idea 3 simpler, add a demo of the noise schedule, drop the U-Net idea.'
CHANGE_HELP = 'Enter sends. Shift+Enter starts a new line. The tutor does not change a locked idea. A link in your words becomes a source.'

def ChangeBox(j, out=''):
    """The one box that changes the walk, at the top of the plan. Enter sends and Shift+Enter starts a new line (walk.js). The tutor turns your
    words into the changes of the editor and makes them at once, as one change with Undo. A locked idea stays as it is. `out` goes under it:
    the line of Make this walk again while its job runs."""
    return Section(Form(Textarea(name='words', rows='1', maxlength='1000', placeholder=CHANGE_SAY, aria_label='What should change in the walk?', data_enter='1', id='change-words'),
                        P(CHANGE_HELP, cls='mute help'),
                        hx_post=at(Routes.improve, j['id']), hx_target='#change-out', hx_swap='innerHTML', data_wait='The tutor reads what you asked…', cls='change-form'),
                   Div(out, id='change-out', aria_live='polite'), id='change', cls='walk-change', data_part='change', data_act='change')

def ImprovePending(jid, key, said, row=None):
    "The box while the tutor works: the line of what it does now, and Stop for its job row `row`. It loads again on each event of its job row `key`, and every 30 seconds."
    return Div(P(said + '…', cls='mute'), Div(JobStop(row), cls='row acts') if row is not None else '', hx_get=f"{at(Routes.improve, jid)}?{urlencode(dict(key=key))}", hx_trigger=WAIT, hx_swap='outerHTML', cls='improve-wait', data_job=key)

def ImproveEnded(jid, key, line, row):
    "The box after the job ended with no change (you stopped it, or it failed): the line, and Do it again for its job row `row`, which loads the box again."
    return Div(P(line, cls='mute' if row is not None and row.state == 'stopped' else 'req-err'), Div(JobAgain(row), cls='row acts') if row is not None else '',
               hx_get=f"{at(Routes.improve, jid)}?{urlencode(dict(key=key))}", hx_trigger='job', hx_swap='outerHTML', cls='improve-wait', data_job=key)

KIND_SAYS = dict(demo='a demo', short='a short answer', order='put in order', notebook='a notebook')

def change_words(c, by) -> str:
    "One change in words: `Made the check of “Softmax” easier.`"
    n = name(by, dict(slug=c.slug)) if c.get('slug') else c.get('name')
    kind = KIND_SAYS.get(c.get('kind') or '', '')
    return dict(add=f"Added “{c.get('name')}”" + (f" as idea {c.to}" if c.get('to') else '') + (f" with {kind}" if kind else '') + (f", from {c.link}" if c.get('link') else '') + '.',
                remove=f"Removed “{n}”.", skip=f"Skipped “{n}”. You can bring it back.", move=f"Moved “{n}” to idea {c.get('to')}.", split=f"Split “{n}” into smaller ideas.",
                merge=f"Merged “{n}” with the next idea.", rewrite=f"Rewrote the note and the question of “{n}”: {c.get('text')}.",
                kind=f"Changed the check of “{n}” to {kind or 'another kind'}.", source=f"Looks for a source for “{n}”.",
                easier=f"Made the check of “{n}” easier.", harder=f"Made the check of “{n}” harder.").get(c.op, '')

def Changed(jid, cs, by, eid=''):
    "What the box changed: one short line for each change, and Undo, which takes them all back as one change. Nothing changed: a plain line."
    if not cs: return P('The tutor found nothing to change. Say it in other words.', cls='mute')
    undo = Quiet('Undo', ' ', Kbd('⌘Z'), small=True, type='button', hx_post=at(Routes.undo, jid), hx_vals=json.dumps(dict(step=eid)), hx_target='#steps', hx_swap='outerHTML', data_act='undo-change') if eid else ''
    return Div(Span('What changed', cls='lbl'), Ul(*[Li(change_words(c, by)) for c in cs], cls='plain changes'), Div(undo, cls='row') if undo else '', cls='changed')

def phase(j, st) -> str:
    "The state of walk `j` on its page: `empty`, `side` (a side walk), `new`, `going` or `finished`."
    if not j['steps']: return 'empty'
    if j.get('parent'): return 'side'
    if not j.get('started'): return 'new'
    return 'going' if st.current is not None else 'finished'

def Here(j, st, by):
    "Where you are in a walk that you started: the idea to do now, and Continue: idea n of N, the main button."
    i = st.current
    return Div(P('Next: ', Inline(name(by, st.steps[i])), cls='mute'),
               Div(Primary(f"Continue: idea {i + 1} of {len(st.steps)}", href=at(Routes.step, j['id'], i), data_act='continue'), cls='row'),
               cls='walk-here', data_part='here')

def SideTop(j, st, back):
    "A side walk: Back to the walk that opened it (by its short title), the main button, and a quiet way on to the idea to do now."
    go = A(f"Continue: idea {st.current + 1} of {len(st.steps)} →", href=at(Routes.step, j['id'], st.current), cls='onward', data_act='continue') if st.current is not None else ''
    return Div(Primary(f"Back to {back.get('title') or 'the paper'}" if back else 'Back to the paper', href=back.href if back else '/', data_act='back'), go, cls='row walk-top')

DATA_SAY = 'The exercises of this walk run on these folders. abhyasa does not file them.'

def YourData(j):
    """Your data: each folder that the exercises run on (`walk.data`), as `EPISODES · ~/path · note` with ×, then a folder setter for each data name that the
    steps need and that has no folder yet. Add a source adds one too."""
    need = setters(j['id'], missing_data(j))
    need = Div(P(f"The steps need {n_of(len(need), 'more folder')} on this Mac:", cls='mute'), Div(*need, cls='data-sets'), cls='walk-need') if need else ''
    rows = [Li(*((Code(d['name']), ' · ') if d.get('name') else ()), B(d['path']), Span(f" · {d['note']}", cls='mute') if d.get('note') else '',
               Button('×', type='button', cls='x', aria_label=f"Remove {d['path']}", hx_post=at(Routes.data_drop, j['id']), hx_vals=json.dumps(dict(path=d['path'])),
                      hx_target='#walk-data', hx_swap='outerHTML')) for d in j.get('data') or ()]
    if not (rows or need): return Div(id='walk-data')
    return Div(H3('Your data'), P(DATA_SAY, cls='mute') if rows else '', Ul(*rows, cls='plain walk-data') if rows else '', need, id='walk-data', data_part='data')

def Sources(j, band, more=()):
    "The sources of the walk: the line of research with Stop, Show what it did and Find sources again, what Start filed with its Undo, your data, and Add a source (`more`)."
    return Section(H2('Sources'), band, Filed(j), YourData(j), *more, id='sources', data_part='sources', cls='walk-sources')

def Talks(talks=(), changed=(), actions=()):
    "Quiet, at the foot: the talks made from the walk, and what other blocks add (Present, the course)."
    if not (talks or actions): return ''
    return Div(TalkLine(talks, changed), Div(*actions, cls='row') if actions else '', data_part='talks', cls='walk-talks')

def side_lead(j, by, back) -> str:
    "The short lead of side walk `j`: its idea and the short title of the walk that opened it. '' for another walk, or when the walk that opened it is gone."
    if not back or not j.get('slug'): return ''
    return f"{name(by, dict(slug=j['slug']))}: the basics, for {back.title}"

DROP_SAYS = 'Delete the plan of this walk? Your answers, your attempts and what you learned stay. Its side walks go with it.'

def DropWalk(jid):
    "Delete this walk, with one confirm in place: the line says what goes and what stays. The form posts, then the list of walks opens."
    return Details(Summary('Delete this walk', cls='small'),
                   Form(P(DROP_SAYS), Div(Button('Delete the walk', cls='small danger', data_act='drop'), cls='row'),
                        action=at(Routes.drop, jid), method='post', hx_boost='false', cls='drop-confirm'), cls='drop-walk')

REPLAN_SAYS = 'Make the plan of this walk again from its source? Locked ideas stay. Your answers stay.'

def MakeAgain(jid):
    "Make this walk again, with one confirm in place. The form posts, then the walk page opens with the line of the job, which has Stop."
    return Details(Summary('Make this walk again', cls='small'),
                   Form(P(REPLAN_SAYS), Div(Button('Make the walk again', cls='small', data_act='replan'), cls='row'),
                        action=at(Routes.replan, jid), method='post', hx_boost='false', cls='drop-confirm'), cls='drop-walk replan-walk')

def Replanned(jid, key, r, eid=''):
    """The line of Make this walk again, for its job row `r` (`key`): what it does now and Stop while it runs, then the end. Done: the line
    and Undo (`eid`, the change). Stopped or failed: the line and Plan it again. It loads again on each event of its row."""
    url = f"{at(Routes.replan, jid)}?{urlencode(dict(key=key))}"
    if r is None: return ''
    if r.state == 'running':
        return Div(P((r.get('said') or 'Making the plan again') + '…', cls='mute'), Div(JobStop(r), cls='row acts'), hx_get=url, hx_trigger=WAIT, hx_swap='outerHTML', cls='improve-wait', data_job=key)
    if r.state == 'done':
        undo = Quiet('Undo', ' ', Kbd('⌘Z'), small=True, type='button', hx_post=at(Routes.undo, jid), hx_vals=json.dumps(dict(step=eid)), hx_target='#steps', hx_swap='outerHTML', data_act='undo-change') if eid else ''
        return Div(P('The tutor made the plan again from its source. Locked ideas stayed.', cls='mute'), Div(undo, cls='row') if undo else '', cls='changed', data_job=key)
    line = f'{STOPPED} The plan did not change.' if r.state == 'stopped' else r.get('why') or 'The tutor could not make the plan again. The plan did not change.'
    return Div(P(line, cls='mute' if r.state == 'stopped' else 'req-err'), Div(JobAgain(r, 'Plan it again'), cls='row acts'), hx_get=url, hx_trigger='job', hx_swap='outerHTML', cls='improve-wait', data_job=key)

def WalkMenu(j):
    "The ⋯ menu of a walk, on its page and on its row in the list of walks: Make this walk again, and Delete this walk."
    return Details(Summary('⋯', title='More for this walk', aria_label='More for this walk'), Div(MakeAgain(j['id']), DropWalk(j['id']), cls='menu-items'), cls='more-menu walk-menu')

def CopyGo(j, i=None):
    """Open in Leela for notebook walk `j`: one press writes the learning copy (or keeps the one you changed) and opens it in Leela at the
    section of idea `i`. Leela runs it in the folder of your notebook. It says when you last opened it, or that Leela is not running."""
    t = (j.get('notebook') or {}).get('opened')
    href = at(Routes.notebook, j['id']) + ('' if i is None else f'?i={i}') if leela_base() else None
    return Span(OpenInLeela(href, 'Open in Leela', post=True),
                Span(f"Opened in Leela at {time.strftime('%H:%M', time.localtime(t))}.", cls='mute nb-opened') if href and type(t) in (int, float) else '', cls='nb-copy-go')

def NotebookLine(j, copy=''):
    """A walk made from one of your notebooks: Learn it in Leela opens a learning copy of the notebook, with the demos of the walk as rupaka cells
    next to their sections. `copy` is the path of the copy. Your own notebook file never changes."""
    nb = j.get('notebook') or {}
    if not nb.get('path'): return ''
    i = walk_state(j).current
    href = at(Routes.notebook, j['id']) + ('' if i is None else f'?i={i}') if leela_base() else None
    return Div(OpenInLeela(href, 'Learn the notebook in Leela', post=True),
               P(f"Leela opens a learning copy with the demos of this walk, at the idea you are on. It runs in the folder of your notebook {Path(nb['path']).name}, "
                 f"which does not change. The copy is in {copy}.", cls='mute'),
               cls='walk-notebook', data_part='notebook')

def Size(j, oob=False):
    "The size of walk `j` in its head, as `7 ideas · about 18 min`. A change of the plan sends it again out of band, so the head does not stay old."
    mins = sum(minutes(s) for s in j['steps'] if s.get('status') != 'skip')
    return Span(meta(n_of(len(j['steps']), 'idea'), f'about {mins} min' if j['steps'] else ''), id='walk-size', **({'hx_swap_oob': 'true'} if oob else {}))

def WalkPage(j, st, by, plan, band, top=None, more=(), talks=(), changed=(), actions=(), vault=None, lead='', copy='', change=''):
    """One page for one walk. The head says what the walk is, with its ⋯ menu (Delete this walk) and, for a notebook walk, Learn the notebook in Leela.
    Then the part of its state (`phase`): Start the walk, where you are, the end of the walk (`top`, the `WalkEnd`), or Back to the paper.
    Then the box that changes the walk (with `change` under it), the plan (`plan`), the sources (`band`, `more`) and the talks."""
    src, ph = j.get('source') or {}, phase(j, st)
    whence = lead or (f"From your vault: {src['title']}" if src.get('title') else f"From the link: {src['url']}" if src.get('docs') else j.get('goal', ''))
    claim = ' '.join(str((j.get('map') or {}).get('claim') or '').split())   # the one thing that the source shows, from the walk map
    head = (Div(H1(j['title']), WalkMenu(j), cls='walk-head'), P(*((whence, ' · ') if whence else ()), Size(j), cls='mute'),
            P(Span('The main idea', cls='lbl'), claim, cls='walk-claim', data_part='claim') if claim else '',
            leela_line(j, vault=vault) if j.get('tool') else '', NotebookLine(j, copy))
    if ph == 'empty': return (*head, P('The tutor found no ideas in this source.', cls='mute'), Filed(j), Div(Primary('Home', href='/', data_act='home'), cls='row'))   # what Start filed keeps its Undo
    if ph == 'new': top = Div(Form(Primary('Start the walk', data_wait='Starting…', data_act='start'), action=at(Routes.start, j['id']), method='post'), cls='row walk-top')
    elif ph == 'going': top = Here(j, st, by)
    return (*head, top, '' if ph == 'side' else ChangeBox(j, change), plan, Sources(j, band, more), '' if ph == 'side' else Talks(talks, changed, actions))

def InWalks(c, rows, js):
    "On a concept page: the walks that have idea `c` (`(walk, index)`), each linked to its idea, and a way to add it to another walk."
    pick = [j for j in js if j['id'] not in {j['id'] for j, _ in rows}]
    return Div(*([H2('In your walks'), Ul(*[Li(A(j['title'], href=at(Routes.step, j['id'], i)), Span(f"  idea {i + 1} of {len(j['steps'])}", cls='mute')) for j, i in rows], cls='plain')] if rows else []),
               Form(Label('Add this idea to a walk', fr='attach-jid', cls='lbl'), Select(*[Option(j['title'], value=j['id']) for j in pick], name='jid', id='attach-jid'),
                    Input(type='hidden', name='slug', value=c.slug), Button('Add to the walk', cls='small', data_act='add-to-walk'),
                    hx_post=Routes.attach, hx_target='this', hx_swap='outerHTML', cls='attach row') if pick else '', cls='in-journeys')

def StepDone(c, nxt):
    "A note in the thread when an idea of the walk is learned."
    return Div(Span('Idea done', cls='lbl'), P(f"You learned {c.name}. " + (f"Next in the walk: {nxt}." if nxt else 'That was the last idea of the walk.')), cls='step-done')

# --- the walk path editor (core/edit.py: an `EditList`; each change saves at once, with an Undo) ----------------------

SETTING = '/settings#g-walks'   # the Walks group of Settings, with the hands-on share

def edit_url(jid, slug=''): return at(Routes.edit, jid) + (f'?{urlencode(dict(slug=slug))}' if slug else '')

def hands_words(j):
    "The hands-on line of walk `j`, and whether the walk is over its share. It only warns."
    h, n, nb = hands_count(j['steps'])
    m, pct = h + nb, round(100 * val('walks.hands'))   # a notebook that builds the goal is hands-on, but the setting does not count it
    line = f"{m} of {n_of(n, 'idea')} {'has' if m == 1 or n == 1 else 'have'} a hands-on check"
    if not nb: return f"{line}. You set about {pct}%.", h > hands_most(n)
    return f"{line}: {nb} {'is a notebook' if nb == 1 else 'are notebooks'} for your goal. You set about {pct}% for the other ideas.", h > hands_most(n)

def Hands(j, oob=False):
    "The hands-on share of the walk against your setting. Over the share, a quiet link to the setting. Nothing blocks."
    line, over = hands_words(j)
    return P(line, *((' ', A('Change the setting', href=SETTING)) if over else ()), id='hands', cls='hands over' if over else 'hands', aria_live='polite',
             **({'hx_swap_oob': 'true'} if oob else {}))

def edit_act(jid, act, **kw):
    "The htmx attributes of a button that makes the change `act` and swaps the list of ideas."
    return dict(hx_post=at(Routes.edit, jid), hx_vals=json.dumps(dict(act=act, **kw)), hx_target='#steps', hx_swap='outerHTML', type='button')

def step_line(j, s, writing=False):
    "The short line of a step row: the kind of its check, its way, and the source of its passage. A notebook step says `writing` only while its job runs."
    if s.get('status') == 'skip': return 'skipped · you can bring it back'
    ck, r = s.get('check') or {}, s.get('read') or {}
    kind = ck.get('kind', 'short')
    if kind == 'notebook' and not s.get('nb'): return meta(KIND.get(kind), NB_WRITING if writing else NB_NONE if s.get('nb_why') else NB_LATER)
    return meta(KIND.get(kind, kind), LABELS.get(ck.get('way'), '').lower() if kind == 'short' else '',
                f"passage: {source_of(r, j).label}" if (r.get('text') or '').strip() else 'no source yet')

DOT_SAYS = dict(done='done', shaky='shaky', known='you know it', skipped='skipped', now='now', todo='to do')

def PlanDot(dot):
    "The dot of an idea in the plan, as in the outline: filled when it is done or known, half filled when it is shaky."
    return Span(cls=f'plan-dot {dot}', role='img', aria_label=DOT_SAYS.get(dot, dot), title=DOT_SAYS.get(dot, dot))

LOCK_SVG = NotStr('<svg viewBox="0 0 12 14" width="10" height="12" aria-hidden="true"><rect x="1" y="6" width="10" height="7.5" rx="1.5" fill="currentColor"/>'
                  '<path d="M3.5 6V4a2.5 2.5 0 0 1 5 0v2" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>')
LOCKED_SAYS = 'Locked: the box does not change this idea. A change by hand unlocks it.'

def LockMark(slug, on):
    "The small lock mark of a locked idea in the plan; an empty mark when it is not locked."
    return Span(LOCK_SVG if on else '', id=f'mark-{slug}', cls='lock-mark', role='img' if on else None, aria_label='Locked' if on else None,
                title=LOCKED_SAYS if on else None)

def LockBtn(jid, slug, on):
    "The quiet Lock toggle of an idea: Keep this idea. It posts lock or unlock, with Undo. F presses it from the row (walk.js)."
    return Quiet('Locked' if on else 'Lock', small=True, id=f'lock-{slug}', data_lock='1', data_act='lock', data_key='F', aria_pressed='true' if on else 'false',
                 title='Unlock this idea' if on else 'Keep this idea: the box does not change it', **edit_act(jid, 'unlock' if on else 'lock', slug=slug))

def RowMenu(jid, s):
    "The ⋯ menu of an idea: Skip (or Bring back) and Remove. D and X press them from the row (core/edit.js); Undo takes each one back."
    skip, slug = s.get('status') == 'skip', s['slug']
    return Details(Summary('⋯', title='More for this idea', aria_label='More for this idea'),
                   Div(Quiet('Bring back' if skip else 'Skip', ' ', Kbd('D'), small=True, data_key='D', data_skip='1', **edit_act(jid, 'back' if skip else 'skip', slug=slug)),
                       Quiet('Remove', ' ', Kbd('X'), small=True, data_key='X', data_act='remove', **edit_act(jid, 'remove', slug=slug)), cls='menu-items'),
                   cls='more-menu row-menu')

def PlanRow(j, k, s, by, fresh='', nb=(), dot='todo'):
    """Idea `k` of the plan: the grip, its number, its dot, its name (a link to the idea), its lock mark and short line, then Lock and the ⋯ menu.
    The row is an `edit-row` of an `EditList`, so core/edit.js gives it its keys: W and S move the focus, ⇧W and ⇧S move the idea, and the drag by the grip."""
    slug = s['slug']
    return Li(Span(cls='grip', title='Drag to move', aria_hidden='true'), Span(str(k + 1), cls='no'),
              Div(Span(PlanDot(dot), A(Inline(name(by, s)), href=at(Routes.step, j['id'], k), tabindex='-1'), ' ', LockMark(slug, s.get('locked')), cls='ttl'),
                  Span(q, cls='ask') if (q := ' '.join(str(s.get('question') or '').split())) else '', Span(step_line(j, s, slug in nb), cls='line'), cls='head'),
              LockBtn(j['id'], slug, s.get('locked')), RowMenu(j['id'], s),
              tabindex='0', data_id=slug, data_i=str(k), data_post=edit_url(j['id'], slug), cls='edit-row' + (' skipped' if s.get('status') == 'skip' else '') + (' fresh' if slug == fresh else ''))

def Steps(j, by, fresh='', nb=(), oob=False):
    "The ideas of the walk as one list, with a quiet label where a section starts. Each row has Lock and the ⋯ menu. Each change swaps the list whole."
    ss, st = j['steps'], walk_state(j, by)   # the same dots as the outline
    kids, sec = [], None
    for k, s in enumerate(ss):
        if (x := (s.get('read') or {}).get('section')) and x != sec: sec = x; kids.append(Li(Inline(x), cls='sec', role='presentation'))
        kids.append(PlanRow(j, k, s, by, fresh, nb, st.steps[k].dot))
    return Ol(*kids, cls='edit-list walk-path', data_edit='1', id='steps', aria_label='The ideas of the walk', **({'hx_swap_oob': 'true'} if oob else {}))

def TalkLine(talks, changed=()):
    """The talks made from this walk, each with a link; a talk in `changed` is older than the walk now. A change here does not change a talk:
    the talk offers Make it again, which keeps your edits to its slides."""
    if not talks: return ''
    links = [x for k, t in enumerate(talks) for x in ((', ' if k else ''), A(f"{t['title']}, as a talk", href=f"/t/{t['id']}"),
                                                       ' (older than this walk)' if t['id'] in changed else '')]
    head = '1 talk was made from this walk: ' if len(talks) == 1 else f'{len(talks)} talks were made from this walk: '
    return P(head, *links, '. A change here does not change a talk. To bring it in, open the talk and press “Make it again”.', cls='mute talk-line')

def PlanPart(j, by, nb=()):
    "The plan of the walk: the hands-on share, the ideas (each with Lock and the ⋯ menu; each change saves at once, with Undo), and the earlier versions in a fold."
    n = len(j.get('more') or ())
    more = P(f"The source has {n} more {'idea' if n == 1 else 'ideas'}. Learn one in a side walk when you need it.", cls='mute') if n else ''
    return Section(H2('The plan'), more,
                   Details(Summary('About this'), P('An idea keeps your progress, its passage and its side walks when it moves. A removed idea keeps your answers in the vault.'), cls='about'),
                   Hands(j), Steps(j, by, nb=nb), UndoBar(oob=False),   # in the page under the list (walk.css)
                   Details(Summary('Earlier versions'), Div(Span('Reading the changes…', cls='mute'), hx_get=at(Routes.history, j['id']), hx_trigger='intersect once', hx_swap='innerHTML'),
                           id='history', cls='more'),
                   Details(Summary('Keys'), P('With an idea in focus: ', Kbd('W'), ' ', Kbd('S'), ' move the focus · ', Kbd('⇧W'), ' ', Kbd('⇧S'), ' move the idea · ', Kbd('F'), ' lock · ',
                     Kbd('E'), ' the ⋯ menu · ', Kbd('D'), ' skip · ', Kbd('X'), ' remove · ', Kbd('⌘Z'), ' undo. With no idea in focus, ', Kbd('E'), ' goes to the box', cls='mute keys-line'), cls='more'),
                   id='plan', data_part='plan', cls='walk-plan')

def History(j, rows):
    "The earlier versions of walk `j`, for the fold on the walk page: each change, newest first, with Restore this version."
    return (P('Each line is one change. “Restore this version” puts the walk back as it was before that change. Your progress stays. You can undo a restore too.', cls='mute'),
            HistoryList(rows, at(Routes.restore, j['id'])))
