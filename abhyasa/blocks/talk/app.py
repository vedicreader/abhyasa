"""The talk: a walk made into slides for a group. "Present this walk" makes the talk on the pool, and the editor changes its slides.
On a walk planned from a goal, "Present this walk" first makes a walk for the talk from its steps, in their order, and a second press opens
the same talk. A change to the talk never changes the walk. Each change runs `check_talk`, and a talk with a problem is not saved.

"Present" starts a run. The presenter window and the audience window (`/t/{tid}/audience?k=<run key>`) stay in step over the
stage channel. Each key posts to the server first (`at`, `ask`), and the window sends the stage messages from the reply, so the
run log on the server always has the place. The hands of the room and the result never go into the learner model.

When the room is lost, ⌥B offers a primer on an idea that the slide needs, and the primer opens in the side pane of both windows,
in the talk type (`pane=1&talk=1`). "End the talk" ends the run and opens "After the talk": where the room was unsure, the
recap file for the room, a follow-up walk, and the primers to add to the talk."""
import math, random, re, secrets, time
from copy import deepcopy
from fasthtml.common import *
from starlette.responses import JSONResponse, RedirectResponse
from abhyasa.core import Page, UndoBar, hook, n_of, pane_url, room_spec, run as run_hook
from abhyasa.edit import edit_lock, rewrite as tutor_rewrite
from abhyasa.journey import needs, pick_way_down, detour, walk_from_topic, for_talk, journey_walk, journey_changed
from abhyasa.llm import for_task
from abhyasa.settings import val
from abhyasa.talk import (check_talk, talk_from_walk, talk_from_journey, fill_talk, walk_talk, ask_for_concept, slide_minutes, ASK_KINDS, WORDS_MOST, QUESTIONS_MIN,
                          public_deck, public_ask, asset_resolver, BODY_MOST, POINT_MOST, SOURCE_KEYS, new_run, log_go, log_main, end_run, log_beside,
                          recap, recap_html)
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask', 'pool', 'sources', 'research')
NO_TALK = 'abhyasa could not make the talk.'
PARTS = ('passage', 'body', 'figure', 'demo')   # the parts that a slide can show, in the order of their beats
PAUSE = 'Talk to your neighbour.'
ASKS = ('idea', 'primer')              # the slide kinds that can ask the room
SLOT = (5, 240)                         # the most and the least minutes of a slot
SECS = (10, 1800)                       # the time of a pause
Q_MOST, OPT_MOST, NOTE_MOST = 500, 200, 5000   # as the `ask` message of the stage allows
WALK_STEP = re.compile(r'/w/[a-z0-9-]{1,48}/[0-9]{1,3}')   # the only page that the side pane of a talk opens (spec 9.2)
HASH = re.compile(r'[0-9a-f]{64}')
NO_ASK = 'This slide has no question for the room.'
SIDE_HOWS = ('primer', 'walk')          # the ways that open beside a slide; its own session never opens in a talk (spec 12)
NO_RUN = 'The talk does not run now.'

class Bad(Exception):
    "A change that cannot be made; its text goes back to the editor."

def text(s): return Response(s, status_code=400, media_type='text/plain')

def new_id(ss):
    "The next free slide id: one more than the largest number."
    return f"s{max((int(s['id'][1:]) for s in ss if str(s.get('id', ''))[1:].isdigit()), default=0) + 1}"

def blank(sid, kind, title, mins, **kw):
    "A slide with no step: a pause or a questions slide."
    return dict(id=sid, kind=kind, title=title, section='', show=dict(passage='', figure=None, demo=None), beats=[], notes='', ask=None, mins=mins, **kw)

def lines(s): return [x.strip() for x in str(s).splitlines() if x.strip()]

def number(s, lo, hi, say):
    "The whole number in `s` from `lo` to `hi`, else `Bad(say)`."
    try: n = int(str(s).strip())
    except ValueError: raise Bad(say)
    if not lo <= n <= hi: raise Bad(say)
    return n

def mixed(n):
    "A random order of `n` cards that is not the right order (spec 7.5): the position of each right card in the order that the room sees."
    order = list(range(n))
    while n > 1 and order == list(range(n)): random.shuffle(order)
    return order

def with_part(beats, p, on):
    "`beats` with the part `p` shown or not; a new part goes after the parts before it."
    beats = [b for b in beats if b != p]
    if not on: return beats
    at = max((k + 1 for k, b in enumerate(beats) if b in PARTS[:PARTS.index(p)]), default=0)
    return [*beats[:at], p, *beats[at:]]

def new_ask(old, f):
    "The question from the ask fields in `f`, over the question `old`; None for no question."
    old = old or {}
    kind = f.get('kind', old.get('kind') or 'none')
    if kind not in ASK_KINDS: raise Bad(f'Unknown kind of question: {kind}.')
    if kind == 'none': return None
    q = f['q'].strip() if 'q' in f else old.get('q') or ''
    if not q: raise Bad('Write the question.')
    if len(q) > Q_MOST: raise Bad(f'Write the question in at most {Q_MOST} characters.')
    a = dict(kind=kind, q=q)
    if kind == 'words': return dict(a, most=WORDS_MOST)
    opts = lines(f['options']) if 'options' in f else list(old.get('options') or [])
    if any(len(o) > OPT_MOST for o in opts): raise Bad(f'Write each option in at most {OPT_MOST} characters.')
    ans, same = str(f.get('answer', '')).strip(), old.get('kind') == kind
    if kind == 'scale':
        if len(opts) != 5: raise Bad('A scale needs 5 labels, one on each line.')
        return dict(a, options=opts)
    if kind == 'run':   # the answer comes after the run: no right option, and the options keep their order
        if opts and not 2 <= len(opts) <= 6: raise Bad('A run question needs 2 to 6 options, one on each line, or none.')
        return dict(a, options=opts) if opts else a
    if kind == 'choice':
        if not 2 <= len(opts) <= 6: raise Bad('A choice needs 2 to 6 options, one on each line.')
        n = number(ans, 0, len(opts) - 1, 'Pick the right option.') if ans else old.get('answer') if same else None
        if n is None: raise Bad('Pick the right option.')
        return dict(a, options=opts, answer=n)
    if not 3 <= len(opts) <= 6: raise Bad('An order needs 3 to 6 options, one on each line.')
    if ',' in ans:   # the API can give the right order; the editor lists the options in the right order and sends no order
        try: order = [int(x) for x in ans.split(',')]
        except ValueError: raise Bad('Give the right order as the numbers of the options, with commas.')
        return dict(a, options=opts, answer=order)
    if 'options' not in f and same: return dict(a, options=opts, answer=old.get('answer'))
    if 'options' not in f: raise Bad('Write the options in the right order, one on each line.')
    at = mixed(len(opts))   # the options are in the right order: the room sees them mixed
    shown = [None] * len(opts)
    for k, p in enumerate(at): shown[p] = opts[k]
    return dict(a, options=shown, answer=at)

def rows(f, opts):
    "The editor sends one box for each option and a radio button on the right one: make them the lines of `options` and the index of `answer`."
    if len(opts) < 2: return f
    keep = [k for k, o in enumerate(opts) if isinstance(o, str) and o.strip()]
    f = {**f, 'options': '\n'.join(opts[k].strip() for k in keep)}
    if (a := f.get('answer', '').strip()).isdigit():
        if int(a) not in keep: raise Bad('Pick an option that has text.')
        f['answer'] = str(keep.index(int(a)))
    return f

TITLE_MOST = 200
NO_REWRITE = 'The tutor could not rewrite this. Nothing changed.'

def points(s, pts):
    "Slide `s` with the points `pts`: a new list shows with its beat, and no points take the beat out."
    had = bool((s.get('show') or {}).get('body'))
    if len(pts) > BODY_MOST or any(len(p) > POINT_MOST for p in pts): raise Bad(f'Write at most {BODY_MOST} points, each in at most {POINT_MOST} characters.')
    s['show'] = {**(s.get('show') or {}), 'body': pts}
    if not pts or not had: s['beats'] = with_part(s.get('beats') or [], 'body', bool(pts))
    return s

def note(s, n):
    if len(n) > NOTE_MOST: raise Bad(f'Write the note in at most {NOTE_MOST} characters.')
    s['notes'] = n.strip()
    return s

def changed(f):
    "The names of the fields that the form `f` changes, in the order of `ui.FIELDS`."
    keys = {'title': 'title', 'body': 'body', 'notes': 'notes', 'prompt': 'prompt', 'beats': 'beats',
            **{f'show_{p}': 'show' for p in PARTS}, **{k: 'ask' for k in ('kind', 'q', 'options', 'answer')}}
    have = {keys[k] for k in f if k in keys}
    return [k for k in ui.FIELDS if k in have]

def edit(s, f):
    "Change slide `s` with the fields that the form `f` sends, and only those."
    if 'title' in f:
        if not (x := ' '.join(f['title'].split())): raise Bad('Write a title.')
        if len(x) > TITLE_MOST: raise Bad(f'Write the title in at most {TITLE_MOST} characters.')
        s['title'] = x
    if 'prompt' in f:
        if s.get('kind') != 'pause': raise Bad('Only a pause has a prompt.')
        if not (x := f['prompt'].strip()) or len(x) > OPT_MOST: raise Bad(f'Write the prompt in 1 to {OPT_MOST} characters.')
        s['prompt'] = x
    if 'notes' in f: note(s, f['notes'])
    if 'beats' in f: s['beats'] = lines(f['beats'])
    if 'body' in f: points(s, lines(f['body']))
    for p in PARTS:
        if (v := f.get(f'show_{p}')) is None: continue
        if v not in ('on', 'off'): raise Bad(f'show_{p} is on or off.')
        s['beats'] = with_part(s.get('beats') or [], p, v == 'on')
    if not {'kind', 'q', 'options', 'answer'} & set(f): return s
    if s.get('kind') not in ASKS: raise Bad('This slide has no question for the room.')
    old, a = s.get('ask'), new_ask(s.get('ask'), f)
    if a and old and all(a.get(k) == old.get(k) for k in ('kind', 'q', 'options', 'answer')) and 'src' in old: a['src'] = old['src']
    if bool(a) != bool(old and old.get('kind') != 'none'):   # a question takes its minutes, and gives them back when it goes
        s['mins'] = max(1, (s.get('mins') or 0) + (val('talks.ask_min') if a else -val('talks.ask_min')))
    s['ask'] = a
    return s

def lit_ok(b, passage):
    "True when beat `b` is not a `lit:` beat on words of the passage, or its words are in `passage`."
    return not str(b).startswith('lit:') or b[4:].startswith('#') or b[4:] in passage

def set_passage(s, p):
    "Slide `s` with the passage `p` (a dict with `text` and `src`, word for word from a source), or with no passage when `p` is None."
    sh = {k: v for k, v in (s.get('show') or {}).items() if k != 'src'}
    sh['passage'] = p['text'] if p else ''
    if p and p.get('src'): sh['src'] = p['src']
    s['show'] = sh
    s['beats'] = with_part([b for b in s.get('beats') or [] if lit_ok(b, sh['passage'])], 'passage', bool(p))
    return s

def set_figure(s, f):
    "Slide `s` with the figure `f` (an image id), or with no figure when `f` is empty."
    s['show'] = {**(s.get('show') or {}), 'figure': f or None}
    s['beats'] = with_part(s.get('beats') or [], 'figure', bool(f))
    return s

def title_of(s): return s.get('prompt') or 'Pause' if s.get('kind') == 'pause' else s.get('title') or 'Untitled'

def stage_log(r):
    "The room parts of run `r` that a reload must show again: the result that shows, the pair prompt, and the slides whose answer was shown."
    return r.setdefault('stage', dict(result=None, pair=None, revealed=[]))

MOST_PAGES = 20   # the pages of a primer beside a slide; each window shows page `page` at its own size (core/talktype.js)

def place_msgs(at, old, page=0):
    "The stage messages for the place `at`, with page `page` of the primer beside the slide; a question of the slide before closes."
    pane = pane_url(at['pane'], talk=True) if at['pane'] else None
    out = [dict(v=1, t='go', slide=at['slide'], beat=at['beat']), dict(v=1, t='blank', on=at['blank']), dict(v=1, t='pane', url=pane, page=page if pane else 0)]
    if old['ask'] and not at['ask']: out.append(dict(v=1, t='ask', slide=old['ask'], ask=None))
    return out

def close_side(r, now):
    "Keep the primer that is open beside a slide in the run log (`beside`), with the time it was open and the room's question on it, and close it."
    if (sd := r.get('side')): log_beside(r, sd['slug'], sd['slide'], sd['at'], round(max(0., now - sd['at']), 1), ask=sd.get('ask'), main=sd.get('main'))
    r['side'] = None

def connect(app, ctx):
    lr = ctx.learning
    jobs = {}   # walk id -> the pool job that makes its talk

    def ask(): return for_task(ctx.ask, 'talk')   # on each call, so a change in Settings works at once
    def walk_of(jid):
        j = lr.journey(jid)
        return j if j and j.get('mode') == 'walk' and j.steps else None

    def new(jid:str=''):
        "Start the pool job that makes a talk from walk `jid`, unless one runs. The request does not wait for the model."
        if not walk_of(jid := jid.strip()): return P('No such walk.', cls='req-err')
        if not (job := jobs.get(jid)) or job.done(): jobs[jid] = ctx.pool.submit(lambda: talk_from_walk(lr, ask(), jid, sources=ctx.sources).id)
        return ui.Pending(jid)

    def find_sources(w):
        "Before the slides are made: mark the steps of walk `w` with no passage as pending, look for their web sources on the research pool, and wait."
        ctx.research.run(w.id)

    def plain(j): return bool(j and j.get('mode') != 'walk' and not for_talk(j) and j.steps)   # a path: a walk with no source

    def from_journey(jid:str='', again:str=''):
        "Start the pool job that makes a talk from path `jid`, or finds the one made before. `again` makes a new walk and a new talk."
        if not plain(lr.journey(jid := jid.strip())): return P('No such walk.', cls='req-err')
        if not (job := jobs.get(jid)) or job.done(): jobs[jid] = ctx.pool.submit(lambda: talk_from_journey(lr, ask(), jid, ctx.sources, again=bool(again), research=find_sources).id)
        return ui.Pending(jid)

    def fill(tid:str):
        "Start the pool job that writes the content of the slides of talk `tid` that have none (Fill the slides). The request does not wait for the model."
        if not lr.talk(tid): return Response('No such talk.', status_code=404)
        if not (job := jobs.get(tid)) or job.done(): jobs[tid] = ctx.pool.submit(lambda: fill_talk(lr, ask(), tid, ctx.sources).id)
        return ui.Pending(tid, fill=True)

    def job(jid:str=''):
        "The state of the talk from walk `jid`, or of Fill the slides of talk `jid`: the pending card, a redirect to the editor, or a message."
        if not (j := jobs.get(jid.strip())): return P('No talk is being made from this walk. Try again.', cls='req-err')
        if not j.done(): return ui.Pending(jid.strip(), fill=bool(lr.talk(jid.strip())))
        if j.exception(): return P(NO_TALK, cls='req-err')   # never the words of a library
        return Response(headers={'HX-Redirect': Routes.of(Routes.one, tid=j.result())})

    def walk_for(t): return lr.journey((t.get('src') or {}).get('walk') or '')

    def one(req, tid:str):
        if not (t := lr.talk(tid)): return Response('No such talk.', status_code=404)
        j = walk_for(t)
        pj = lr.journey(((j or {}).get('parent') or {}).get('journey') or '') if for_talk(j) else None
        up = [(pj.title, f'/path/{pj.id}')] if pj else [(j.title, f'/w/{j.id}')] if j else []
        page = Page(f'{t.title}, as a talk', *ui.Editor(t, j, pj, pj and journey_changed(lr, j), choices(t)), on='Learn', crumbs=[('Today', '/'), ('Learn', '/learn'), *up],
                    extra=ui.editor_assets(), wide=True)
        req.htmlkw['class'] = ' '.join(x for x in (req.htmlkw.get('class'), 'talk') if x)   # the editor keys work only here
        return page

    # --- the editor: each change saves at once, with an Undo, and goes into the history of the talk ------------------------

    def passages(t, s, j=None):
        "The passages of the idea of slide `s`, word for word: from the steps of its walk first, then from each place of the idea in its sources."
        if not (slug := s.get('concept')): return []
        rs = [st.get('read') or {} for st in ((j or {}).get('steps') or []) if st.get('slug') == slug]
        rs += [{**p, 'text': p.get('passage') or ''} for p in reversed((lr.concept(slug) or {}).get('provenance') or ())]
        out, seen = [], set()
        for r in rs:
            if not (x := (r.get('text') or '').strip()) or x in seen: continue
            seen.add(x)
            out.append(dict(text=r['text'], src={k: v for k in SOURCE_KEYS if (v := r.get(k) if k != 'src' else r.get(k) or 'doc') not in (None, '')}))
        return out

    def figures(t, s, j=None):
        "The figures that slide `s` can show: its own, the figure of its walk step, and the figures of its idea in its sources. Only files that are there."
        ok, slug = asset_resolver(lr), s.get('concept')
        fs = [(s.get('show') or {}).get('figure')]
        if slug:
            fs += [f"asset:{(st.get('read') or {}).get('figure')}" for st in ((j or {}).get('steps') or []) if st.get('slug') == slug and (st.get('read') or {}).get('figure')]
            c = lr.concept(slug) or {}
            fs += [f'asset:{x}' for x in (c.get('image'), *[p.get('figure') for p in c.get('provenance') or ()]) if x]
        return [f for f in dict.fromkeys(fs) if f and ok(f)]

    def choices(t):
        "The passages and the figures that each slide of talk `t` can pick, by slide id."
        j = walk_for(t)
        return {s['id']: dict(passages=passages(t, s, j), figures=figures(t, s, j)) for s in t['slides'] if s.get('kind') in ASKS}

    def deck(t, **kw): return ui.Deck(t, choices(t), **kw), ui.Total(t, oob=True)

    def bar(t, said, rows, row=''):
        "The Undo bar after a change: what changed, and Undo for the newest change."
        return UndoBar(said, Routes.of(Routes.undo, tid=t['id']), Routes.of(Routes.history, tid=t['id']), step=rows[0].id if rows else '', row=row,
                       hx_target='#deck', hx_swap='outerHTML')

    def save(t, ss, said, who='you', field=None):
        "Save the slides `ss` of talk `t` and keep the change in its history, as one step; call under `edit_lock`. A talk with a problem raises `Bad`."
        if (ps := check_talk({**t, 'slides': ss})): raise Bad(ps[0])
        out = []
        rows = lr.add_edit('talk', t['id'], said, who, list(t['slides']), field=field, apply=lambda: out.append(lr.put_talk({**t, 'slides': ss})))
        return out[0], rows

    async def slide(req, tid:str):
        form = await req.form()
        f = {**dict(req.query_params), **{k: v for k, v in form.items() if isinstance(v, str)}}
        try: f = rows(f, form.getlist('options'))
        except Bad as e: return text(str(e))
        act = f.get('act', '')
        if act == 'rewrite': return redo(tid, f)
        with edit_lock('talk', tid):
            if not (t := lr.talk(tid)): return Response('No such talk.', status_code=404)
            ss = deepcopy(list(t.slides))
            i = next((k for k, s in enumerate(ss) if s.get('id') == f.get('sid')), None)
            if i is None and not (act in ('add', 'pause') and not f.get('sid')): return Response('No such slide.', status_code=404)
            at_end = len(ss) - 1 if i is None else i
            said, field, row, opened, fresh = '', None, ss[i]['id'] if i is not None else '', '', ''
            try:
                if act in ('up', 'down', 'move'):
                    k = (i - 1 if act == 'up' else i + 1) if act != 'move' else number(f.get('to', ''), 0, len(ss) - 1, 'Give a place in the list.')
                    if 0 <= k < len(ss) and k != i: ss.insert(k, ss.pop(i))
                    said = f'Moved “{title_of(ss[k])}” to slide {k + 1}.' if 0 <= k < len(ss) else ''
                elif act == 'drop':
                    s = ss.pop(i)
                    said, row = f'Removed “{title_of(s)}”.', s['id']   # Undo gives the focus back to the slide that comes back
                elif act in ('edit', 'set', 'title'):
                    names = changed(f)
                    ss[i] = edit(ss[i], f)
                    said = f"Changed the {' and the '.join(ui.FIELDS[n] for n in names)} of slide {i + 1}." if names else ''
                    field = f"{ss[i]['id']}/{names[0]}" if len(names) == 1 else None
                    opened = ss[i]['id'] if act == 'edit' and 'ask' in names else ''
                elif act == 'add':
                    sec = ss[at_end].get('section') or '' if ss else ''
                    new = dict(id=new_id(ss), kind='idea', concept='', title='New slide', section=sec, show=dict(passage='', figure=None, demo=None, body=[]),
                               beats=[], notes='', ask=None, mins=1)
                    ss.insert(at_end + 1, new)
                    said, row, opened, fresh = 'Added a slide.', new['id'], new['id'], new['id']
                elif act == 'dup':
                    new = {**deepcopy(ss[i]), 'id': new_id(ss)}
                    ss.insert(i + 1, new)
                    said, row, opened, fresh = f'Copied “{title_of(new)}”.', new['id'], new['id'], new['id']
                elif act == 'passage':
                    if ss[i].get('kind') not in ASKS: raise Bad('This slide has no passage.')
                    k = f.get('k', '').strip()
                    ps = passages(t, ss[i], walk_for(t))
                    p = ps[number(k, 0, len(ps) - 1, 'Pick a passage of this idea.')] if k else None
                    ss[i] = set_passage(ss[i], p)
                    said, opened = f'Changed the passage of slide {i + 1}.', ss[i]['id']
                elif act == 'figure':
                    if ss[i].get('kind') not in ASKS: raise Bad('This slide has no figure.')
                    if (a := f.get('asset', '').strip()) and a not in figures(t, ss[i], walk_for(t)): raise Bad('Pick a figure of this idea.')
                    ss[i] = set_figure(ss[i], a)
                    said, opened = f'Changed the figure of slide {i + 1}.', ss[i]['id']
                elif act == 'pause':
                    prompt = f.get('prompt', '').strip() or PAUSE
                    if len(prompt) > OPT_MOST: raise Bad(f'Write the prompt in at most {OPT_MOST} characters.')
                    secs = number(f.get('secs') or 120, *SECS, f'A pause is {SECS[0]} to {SECS[1]} seconds.')
                    ss.insert(at_end + 1, new := blank(new_id(ss), 'pause', 'Pause', math.ceil(secs / 60), prompt=prompt, secs=secs))
                    said, row = 'Added a pause.', new['id']
                elif act == 'questions':
                    ss.insert(i + 1, new := blank(new_id(ss), 'questions', 'Questions', QUESTIONS_MIN))
                    said, row = 'Added a slide for questions.', new['id']
                elif act == 'primer':
                    if not (c := lr.concept(f.get('slug', ''))): raise Bad('No such idea.')
                    a, p = ask_for_concept(lr, ask(), c.slug), c.get('statement') or ''
                    ss.insert(i, new := dict(id=new_id(ss), kind='primer', concept=c.slug, title=c.name, section=ss[i].get('section') or '',
                                             show=dict(passage=p, figure=None, demo=None), beats=['passage'] if p else [], notes='', ask=a,
                                             mins=slide_minutes(dict(read=dict(text=p)), a)))
                    said, row = f'Added “{c.name}”.', new['id']
                else: return text(f'Unknown change: {act}.')
                if ss == list(t.slides) or not said:   # nothing changed: nothing to keep
                    return Response(status_code=204) if act == 'set' else deck(t, opened=opened)
                t2, hist = save(t, ss, said, field=field)
            except Bad as e: return text(str(e))
        if f.get('from') == 'after': return ui.Added(t['id'], ss[i]['title'])   # from After the talk
        if act == 'set': return bar(t2, said, hist, row)   # a live field: the text that you type stays, and only the bar changes
        out = (*deck(t2, opened=opened, fresh=fresh), bar(t2, said, hist, row))
        return (*out, ui.Right(row, (slide_of(t2, row) or {}).get('ask'), oob=True)) if field and field.endswith('/ask') else out

    def redo(tid, f):
        "Rewrite the points and the note of a slide with a short instruction. The model call runs outside the lock; a failed rewrite changes nothing."
        if not (t := lr.talk(tid)): return Response('No such talk.', status_code=404)
        if not (s := slide_of(t, f.get('sid'))): return Response('No such slide.', status_code=404)
        if s.get('kind') not in ASKS: return text('The tutor rewrites only a slide of an idea.')
        ins = ' '.join((f.get('chip') or f.get('text') or '').split()).rstrip('.')
        if not ins: return text('Tell the tutor what to change.')
        sh = s.get('show') or {}
        try: new = tutor_rewrite(ask(), dict(body=list(sh.get('body') or []), notes=s.get('notes') or ''), ins, context=sh.get('passage') or '')
        except Exception: return text(NO_REWRITE)   # never the words of a library
        with edit_lock('talk', tid):
            t = lr.talk(tid); ss = deepcopy(list(t.slides))
            if (i := next((k for k, x in enumerate(ss) if x.get('id') == s['id']), None)) is None: return Response('No such slide.', status_code=404)
            try:
                note(points(ss[i], [p for p in new['body'] if p.strip()][:BODY_MOST]), new['notes'])
                t2, hist = save(t, ss, f'Rewrote the points of slide {i + 1}: {ins}.', who='tutor')
            except Bad: return text(NO_REWRITE)
        return (*deck(t2, opened=s['id']), bar(t2, f'Rewrote the points of slide {i + 1}: {ins}.', hist, s['id']))

    def undo(tid:str, step:str=''):
        "Take back the newest change of the talk (`step` is its id, so an old bar does nothing)."
        with edit_lock('talk', tid):
            if not (t := lr.talk(tid)): return Response('No such talk.', status_code=404)
            top = first(lr.edits('talk', tid))
            if top and top.before is None: return text('This change was too large to keep. Undo cannot take it back.')
            try: e = lr.pop_edit('talk', tid, step or None, apply=lambda e: lr.put_talk({**lr.talk(tid), 'slides': e.before}))
            except ValueError: return text('Undo cannot take back this change.')
            t, hist = lr.talk(tid), lr.edits('talk', tid)
        said = f'Undone: {e.what}' if e else 'Nothing to undo.'
        return (*deck(t), bar(t, said, hist))

    def history(tid:str):
        if not (t := lr.talk(tid)): return Response('No such talk.', status_code=404)
        return Page(f"Earlier versions of {t.title}", *ui.History(t, lr.edits('talk', tid)), on='Learn',
                    crumbs=[('Learn', '/learn'), (f"{t.title}, as a talk", Routes.of(Routes.one, tid=tid))], extra=ui.editor_assets(), wide=True)

    def restore(tid:str, id:str='', k:str=''):
        "Go back to the version of the talk before one change (by its `id`, or by its place `k` in the history, newest first). A restore is a change too."
        with edit_lock('talk', tid):
            if not (t := lr.talk(tid)): return Response('No such talk.', status_code=404)
            es = lr.edits('talk', tid)
            e = first(x for x in es if x.id == id) if id else es[int(k)] if k.strip().isdigit() and int(k) < len(es) else None
            if not e: return Response('No such change.', status_code=404)
            if e.before is None: return text('This change was too large to keep. It cannot come back.')
            try: save(t, e.before, f'Restored the version before “{e.what}”')
            except Bad as x: return text(str(x))
        return Response(headers={'HX-Redirect': Routes.of(Routes.one, tid=tid)})

    def slot(tid:str, minutes:str=None, phones:str=None):
        "The minutes of the slot (5 to 240), and room phones (`on` or `off`); each only when the form sends it."
        if not (t := lr.talk(tid)): return Response('No such talk.', status_code=404)
        t = {**t}
        if minutes is not None:
            try: t['minutes'] = number(minutes, *SLOT, f'A slot is {SLOT[0]} to {SLOT[1]} minutes.')
            except Bad as e: return text(str(e))
        if phones is not None:
            if phones not in ('on', 'off'): return text('Room phones is on or off.')
            t['phones'] = phones == 'on'
        return deck(lr.put_talk(t))

    # --- the run: the presenter window, the audience window, the place and the questions ----------------------------------

    def slide_of(t, sid): return next((s for s in t['slides'] if s.get('id') == sid), None)

    def live(tid):
        "Talk `tid` and its open run (None when no run is open)."
        if not (t := lr.talk(tid)): return None, None
        r = lr.run(t.get('live') or '') if t.get('live') else None
        return t, (dict(r) if r and not r.get('ended') else None)

    def specs(t):
        "The demo spec of each slide that shows a demo, by slide id."
        out = {}
        for s in t['slides']:
            if (slug := (s.get('show') or {}).get('demo')) and (d := lr.demo(slug)) and d.get('spec'): out[s['id']] = (slug, d.spec)
        return out

    def start(tid:str):
        "Start a run of talk `tid`, or go back to the run that is open."
        t, r = live(tid)
        if not t: return Response('No such talk.', status_code=404)
        if not r:
            r = new_run(t); lr.put_run(r); lr.put_talk({**t, 'live': r['id']})
        return RedirectResponse(Routes.of(Routes.present, tid=tid), status_code=303)

    def page(req, title, c, cls):
        out = Page(title, c, extra=(*ui.stage_assets(), *ui.rupaka_assets(), *ui.assets()), pane=True)
        req.htmlkw['class'] = cls   # no nav and no crumbs (pane=True); the talk keys (talk.js) work only with `talk`
        return out

    def presenter(req, tid:str):
        t, r = live(tid)
        if not t: return Response('No such talk.', status_code=404)
        if not r: return RedirectResponse(Routes.of(Routes.one, tid=tid), status_code=303)
        deck = public_deck(t, asset_resolver(lr))
        return page(req, f"{t.title}, presenter", ui.Presenter(t, deck, r, specs(t)), 'talk present')

    def audience(req, tid:str, k:str=''):
        t, r = live(tid)
        if not r or not secrets.compare_digest(str(k).encode(), str(r['key']).encode()): return Response('This is not the audience window of the talk that runs now.', status_code=403)
        deck = public_deck(t, asset_resolver(lr))
        room = {sid: (slug, room_spec(sp)) for sid, (slug, sp) in specs(t).items()}
        return page(req, t.title, ui.Audience(t, deck, r, room, fade=val('talks.laser_ms')), 'talk audience')

    def img(tid:str, h:str):
        "The bytes of one image of the public deck, by its sha256."
        if not HASH.fullmatch(h) or not (t := lr.talk(tid)): return Response('No such image.', status_code=404)
        if not (got := public_deck(t, asset_resolver(lr)).images.get(h)): return Response('No such image.', status_code=404)
        return Response(got[0], media_type=got[1], headers={'Cache-Control': 'private, max-age=3600'})

    async def at(req, tid:str):
        """Move the place of the run: `slide`, `beat`, and `blank` (0 or 1), `pane` (a walk step path, or empty) and `page` (the page of the
        primer beside the slide, from 0) when they change."""
        t, r = live(tid)
        if not r: return text(NO_RUN)
        f = {k: v for k, v in (await req.form()).items() if isinstance(v, str)}
        if not (s := slide_of(t, f.get('slide'))): return text('No such slide.')
        try: beat = number(f.get('beat', ''), 1, max(1, len(s.get('beats') or [])), 'No such beat on this slide.')
        except Bad as e: return text(str(e))
        blank, pane = f.get('blank'), f.get('pane')
        if blank not in (None, '0', '1'): return text('blank is 0 or 1.')
        if pane not in (None, '') and pane != (r.get('side') or {}).get('url'): return text('The side pane opens only the primer that the talk made beside this slide.')
        page = f.get('page')
        if page is not None:
            if not r.get('side'): return text('No side pane is open.')
            try: page = number(page, 0, MOST_PAGES - 1, f'A page is from 0 to {MOST_PAGES - 1}.')
            except Bad as e: return text(str(e))
        old = dict(r['at']); new = s['id'] != old['slide']
        log_go(r, s['id'], beat, time.time())
        a = r['at']
        if new:   # a new slide opens clean: no blank screen, no pane, no question, no result and no pair prompt
            a.update(blank=False, pane=None, ask=None); stage_log(r).update(result=None, pair=None)
        if blank is not None: a['blank'] = blank == '1'
        if pane is not None: a['pane'] = pane or None
        if not a['pane']: close_side(r, time.time())   # a new slide or an empty pane closes the primer beside the slide
        elif page is not None: r['side']['page'] = page
        lr.put_run(r)
        return JSONResponse(dict(at=a, msgs=place_msgs(a, old, (r.get('side') or {}).get('page', 0))))

    async def ask_(req, tid:str):
        "A question for the room: `act` is open, close, main (the option that most hands chose), reveal or pair."
        t, r = live(tid)
        if not r: return text(NO_RUN)
        f = {k: v for k, v in (await req.form()).items() if isinstance(v, str)}
        if not (s := slide_of(t, f.get('slide'))): return text('No such slide.')
        if f.get('pane') == '1': return side_ask(r, s['id'], f)
        if not (a := s.get('ask')) or a.get('kind') == 'none': return text(NO_ASK)
        sid, act = s['id'], f.get('act', '')
        if act == 'open':
            r['at']['ask'] = sid; stage_log(r).update(result=None, pair=None); lr.put_run(r)
            return JSONResponse(dict(v=1, t='ask', slide=sid, ask=public_ask(a)))
        if act == 'close':
            if r['at']['ask'] == sid: r['at']['ask'] = None
            stage_log(r).update(result=None, pair=None); lr.put_run(r)
            return JSONResponse(dict(v=1, t='ask', slide=sid, ask=None))
        if act == 'main':
            opts = a.get('options') or []
            if not opts: return text('This question has no options to count hands for.')
            try: n = number(f.get('main', ''), 0, len(opts) - 1, 'Pick one of the options of the question.')
            except Bad as e: return text(str(e))
            log_main(r, sid, a['kind'], n); lr.put_run(r)   # in the run log only, never in Learning.record
            return JSONResponse(dict(slide=sid, main=n))
        if act == 'reveal':
            lg = r['asks'].get(sid) or {}
            rounds = [{k: v for k, v in x.items() if k in ('counts', 'n')} for x in lg.get('rounds') or []]
            right = a.get('answer') if a['kind'] in ('choice', 'order') else None
            m = dict(v=1, t='result', slide=sid, kind=a['kind'], rounds=rounds, right=right, main=lg.get('main'))
            st = stage_log(r); st['result'] = m
            if sid not in st['revealed']: st['revealed'].append(sid)
            lr.put_run(r)
            return JSONResponse(m)
        if act == 'pair':
            if (on := f.get('on', '1')) not in ('0', '1'): return text('on is 0 or 1.')
            m = dict(v=1, t='pair', on=on == '1', prompt=f"Talk to your neighbour for {n_of(val('talks.pair_min'), 'minute')}.")
            stage_log(r)['pair'] = m if m['on'] else None; lr.put_run(r)
            return JSONResponse(m)
        return text(f'Unknown act: {act}.')

    def side_ask(r, sid, f):
        """The question for the room on the idea of the primer beside slide `sid` (Q with the pane open): one model call on the first
        open, then the run keeps it. The reply of `open` is `{msg, ask}`: the stage message, and the whole question for the presenter."""
        if not (sd := r.get('side')): return text('No side pane is open.')
        act = f.get('act', '')
        if act == 'open':
            if not sd.get('ask'): sd['ask'] = ask_for_concept(lr, ask(), sd['slug'])
            r['at']['ask'] = sid; sd['main'] = None; stage_log(r).update(result=None, pair=None); lr.put_run(r)
            return JSONResponse(dict(msg=dict(v=1, t='ask', slide=sid, ask=public_ask(sd['ask'])), ask=sd['ask']))
        if not (a := sd.get('ask')): return text('Ask the room first.')
        if act == 'close':
            if r['at']['ask'] == sid: r['at']['ask'] = None
            stage_log(r).update(result=None, pair=None); lr.put_run(r)
            return JSONResponse(dict(v=1, t='ask', slide=sid, ask=None))
        if act == 'main':
            opts = a.get('options') or []
            if not opts: return text('This question has no options to count hands for.')
            try: sd['main'] = number(f.get('main', ''), 0, len(opts) - 1, 'Pick one of the options of the question.')
            except Bad as e: return text(str(e))
            lr.put_run(r)   # in the run log only, never in Learning.record
            return JSONResponse(dict(slide=sid, main=sd['main']))
        if act == 'reveal':
            m = dict(v=1, t='result', slide=sid, kind=a['kind'], rounds=[], right=a.get('answer') if a['kind'] in ('choice', 'order') else None, main=sd.get('main'))
            stage_log(r)['result'] = m; lr.put_run(r)
            return JSONResponse(m)
        return text(f'Unknown act: {act}.')

    async def beside(req, tid:str):
        """The side pane of a talk (spec 12). With `slide` only: the offer for the presenter, with the needs of the idea of the slide.
        With `slide`, `slug` and `how`: make the primer or the side walk, and give its URL. With `close=1`: keep it in the run log."""
        t, r = live(tid)
        if not r: return text(NO_RUN)
        f = {k: v for k, v in (await req.form()).items() if isinstance(v, str)}
        if f.get('close') == '1':
            close_side(r, time.time()); old = dict(r['at']); r['at']['pane'] = None; lr.put_run(r)
            return JSONResponse(dict(at=r['at'], msgs=[m for m in place_msgs(r['at'], old) if m['t'] == 'pane']))
        if not (s := slide_of(t, f.get('slide'))): return text('No such slide.')
        slug, how = f.get('slug', ''), f.get('how', '')
        if slug and how not in SIDE_HOWS: return text('Choose a primer or a short side walk. Its own session does not open in a talk.')
        if r.get('side') or r['at']['pane']: return Response('Close the side pane first (⌥Z).', status_code=409, media_type='text/plain')
        if not slug:
            c = lr.concept(s.get('concept') or '')
            ns = list(needs(lr, c.slug)) if c else []
            if not ns: return ui.BesideNone(c)
            n = next((x for x in ns if x.slug == f.get('need')), None) or next((x for x in ns if not x.ok), ns[0])
            return ui.BesideOffer(s, c, ns, n, pick_way_down(lr, n.slug))
        if not (c := lr.concept(slug)): return text('No such idea.')
        try: d = detour(lr, ctx.ask, c.slug, dict(talk=tid, slide=s['id']), how, ctx.sources)
        except Exception: return Response('The tutor could not make the primer. Try again.', status_code=502, media_type='text/plain')
        url = f'/w/{d.id}/0'
        if not d.steps or not WALK_STEP.fullmatch(url):
            lr.drop_journey(d.id)
            return Response('The tutor found no steps for this idea.', status_code=502, media_type='text/plain')
        r['side'] = dict(slug=c.slug, slide=s['id'], at=time.time(), url=url, title=c.name, ask=None, main=None); lr.put_run(r)
        return JSONResponse(dict(url=url, pane=pane_url(url, talk=True), title=c.name))

    def end(tid:str):
        "End the run: the place, the primer beside a slide and the time of the last slide go into the run log. Then After the talk."
        t, r = live(tid)
        if not t: return Response('No such talk.', status_code=404)
        if not r:
            if (rs := lr.runs(tid)): return RedirectResponse(f"{Routes.of(Routes.after, tid=tid)}?run={rs[0]['id']}", status_code=303)
            return text(NO_RUN)
        now = time.time(); close_side(r, now); end_run(r, now); lr.put_run(r)
        lr.put_talk({**t, 'live': None})
        return RedirectResponse(f"{Routes.of(Routes.after, tid=tid)}?run={r['id']}", status_code=303)

    def run_of(tid, rid):
        "Talk `tid` and its run `rid` (the newest run when `rid` is empty), or (talk, None)."
        if not (t := lr.talk(tid)): return None, None
        if not rid: return t, (lr.runs(tid) or [None])[0]
        r = lr.run(rid)
        return t, (r if r and r.get('talk') == tid else None)

    def after(tid:str, run:str=''):
        t, r = run_of(tid, run)
        if not t: return Response('No such talk.', status_code=404)
        if not r: return Response('This talk has no such run.', status_code=404)
        names = {s['id']: name_of(s) for s in t['slides']}
        cn = {x.slug: x.name for x in lr.concepts()}
        return Page('After the talk', *ui.After(t, r, recap(t, r, cn), names, cn),
                    on='Learn', crumbs=[('Learn', '/learn'), (f"{t.title}, as a talk", Routes.of(Routes.one, tid=tid))], extra=ui.assets(), wide=True)

    def name_of(s):
        "The name of the idea of slide `s`, else its title."
        return (lr.concept(s.get('concept') or '') or {}).get('name') or s.get('title') or ''

    def recap_file(tid:str, run:str='', look:str=''):
        "The recap of a run as one HTML file: a download, or with `look=1` a look at it first (no script can run in it)."
        t, r = run_of(tid, run)
        if not t or not r: return Response('No such run.', status_code=404)
        body = recap_html(t, r, asset_resolver(lr))
        how = 'inline' if look == '1' else f'attachment; filename="{re.sub(r"[^a-z0-9-]", "", t.id)[:48] or "talk"}-recap.html"'
        return Response(body, media_type='text/html; charset=utf-8',
                        headers={'Content-Disposition': how, 'Content-Security-Policy': "default-src 'none'; img-src data:; style-src 'unsafe-inline'"})

    def follow(tid:str, run:str=''):
        "A follow-up walk on the ideas where the room was unsure: the goal is \"Review: <names>\"."
        t, r = run_of(tid, run)
        if not t or not r or not run: return Response('No such run.', status_code=404)
        by = {s['id']: s for s in t['slides']}
        cn = {x.slug: x.name for x in lr.concepts()}
        ns = list(dict.fromkeys(cn.get(w['beside'], w['beside']) if w.get('beside') else name_of(by[w['slide']]) for w in recap(t, r, cn).unsure))
        if not ns: return text('The room was sure on each idea. No follow-up walk is needed.')
        try: j = walk_from_topic(lr, ctx.ask, goal='Review: ' + ', '.join(ns), sources=ctx.sources)
        except Exception: return Response('The tutor could not make the walk. Try again.', status_code=502, media_type='text/plain')
        run_hook('walk_made', j)   # the walk block looks for web sources on the pool
        return RedirectResponse(f'/w/{j.id}', status_code=303)

    @hook('walk_actions')
    def present(j, quiet=False, row=False):
        """On a walk (its plan, its step, its last page) and on its path page: make a talk from the walk, or open the one made before.
        On a path (a walk with no source): the same from the path. `quiet` gives a quiet button, for a page that has its own main button.
        `row` gives one quiet control for its row in a list: Present, or Open the talk."""
        if j.get('mode') == 'walk':
            if not j.steps or j.get('depth') or for_talk(j): return None
            t = walk_talk(lr, j.id)
            return ui.RowPresent(j.id, t) if row else ui.PresentWalk(j.id, t, quiet)
        if not plain(j): return None
        w = journey_walk(lr, j.id)
        t = w and walk_talk(lr, w.id)
        return ui.RowPresent(j.id, t, path=True) if row else ui.PresentJourney(j.id, t)

    @hook('learn_talks')
    def your_talks():
        "Your talks, in Learn after your walks."
        return ui.YourTalks(ts) if (ts := lr.talks()) else None

    app.post(Routes.new)(new)
    app.post(Routes.journey)(from_journey)
    app.get(Routes.job)(job)
    app.get(Routes.one)(one)
    app.post(Routes.slide)(slide)
    app.post(Routes.undo)(undo)
    app.get(Routes.history)(history)
    app.post(Routes.restore)(restore)
    app.post(Routes.slot)(slot)
    app.post(Routes.fill)(fill)
    app.post(Routes.start)(start)
    app.get(Routes.present)(presenter)
    app.get(Routes.audience)(audience)
    app.get(Routes.img)(img)
    app.post(Routes.at)(at)
    app.post(Routes.ask)(ask_)
    app.post(Routes.beside)(beside)
    app.post(Routes.end)(end)
    app.get(Routes.after)(after)
    app.get(Routes.recap)(recap_file); app.router.routes.insert(0, app.router.routes.pop())   # before fast_app's static route for `.html`
    app.post(Routes.follow)(follow)
