"""The talk: a walk made into slides for a group. "Present this walk" makes the talk on the pool, and the editor changes its slides.
A change to the talk never changes the walk. Each change runs `check_talk`, and a talk with a problem is not saved."""
import math, random
from copy import deepcopy
from fasthtml.common import *
from abhyasa.core import Page, hook
from abhyasa.llm import for_task
from abhyasa.settings import val
from abhyasa.talk import check_talk, talk_from_walk, ask_for_concept, slide_minutes, ASK_KINDS, WORDS_MOST, QUESTIONS_MIN
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask', 'pool', 'sources')
NO_TALK = 'abhyasa could not make the talk.'
PARTS = ('passage', 'figure', 'demo')   # the parts that a slide can show, in the order of their beats
PAUSE = 'Talk to your neighbour.'
SLOT = (5, 240)                         # the most and the least minutes of a slot
SECS = (10, 1800)                       # the time of a pause
Q_MOST, OPT_MOST, NOTE_MOST = 500, 200, 5000   # as the `ask` message of the stage allows

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
    if kind == 'choice':
        if not 2 <= len(opts) <= 6: raise Bad('A choice needs 2 to 6 options, one on each line.')
        n = number(ans, 0, len(opts) - 1, 'Give the right option as its number, from 0.') if ans else old.get('answer') if same else None
        if n is None: raise Bad('Give the right option as its number, from 0.')
        return dict(a, options=opts, answer=n)
    if not 3 <= len(opts) <= 6: raise Bad('An order needs 3 to 6 options, one on each line.')
    if ans:
        try: order = [int(x) for x in ans.split(',')]
        except ValueError: raise Bad('Give the right order as the numbers of the options, with commas.')
        return dict(a, options=opts, answer=order)
    if 'options' not in f and same: return dict(a, options=opts, answer=old.get('answer'))
    at = mixed(len(opts))   # the options are in the right order: the room sees them mixed
    shown = [None] * len(opts)
    for k, p in enumerate(at): shown[p] = opts[k]
    return dict(a, options=shown, answer=at)

def edit(s, f):
    "Change slide `s` with the fields that the form `f` sends, and only those."
    if 'notes' in f:
        if len(f['notes']) > NOTE_MOST: raise Bad(f'Write the note in at most {NOTE_MOST} characters.')
        s['notes'] = f['notes'].strip()
    if 'beats' in f: s['beats'] = lines(f['beats'])
    for p in PARTS:
        if (v := f.get(f'show_{p}')) is not None: s['beats'] = with_part(s.get('beats') or [], p, v == 'on')
    if not {'kind', 'q', 'options', 'answer'} & set(f): return s
    old, a = s.get('ask'), new_ask(s.get('ask'), f)
    if a and old and all(a.get(k) == old.get(k) for k in ('kind', 'q', 'options', 'answer')) and 'src' in old: a['src'] = old['src']
    if bool(a) != bool(old and old.get('kind') != 'none'):   # a question takes its minutes, and gives them back when it goes
        s['mins'] = max(1, (s.get('mins') or 0) + (val('talks.ask_min') if a else -val('talks.ask_min')))
    s['ask'] = a
    return s

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
        if not (job := jobs.get(jid)) or job.done(): jobs[jid] = ctx.pool.submit(lambda: talk_from_walk(lr, ask(), jid).id)
        return ui.Pending(jid)

    def job(jid:str=''):
        "The state of the talk from walk `jid`: the pending card, a redirect to the editor, or a message."
        if not (j := jobs.get(jid.strip())): return P('No talk is being made from this walk. Try again.', cls='req-err')
        if not j.done(): return ui.Pending(jid.strip())
        if j.exception(): return P(NO_TALK, cls='req-err')   # never the words of a library
        return Response(headers={'HX-Redirect': Routes.of(Routes.one, tid=j.result())})

    def one(req, tid:str):
        if not (t := lr.talk(tid)): return Response('No such talk.', status_code=404)
        j = lr.journey((t.get('src') or {}).get('walk') or '')
        page = Page(f'{t.title}, as a talk', *ui.Editor(t, j), crumbs=[('Today', '/'), ('Journeys', '/journeys'), *([(j.title, f'/w/{j.id}')] if j else [])],
                    extra=ui.assets(), wide=True)
        req.htmlkw['class'] = ' '.join(x for x in (req.htmlkw.get('class'), 'talk') if x)   # the editor keys (talk.js) work only here
        return page

    def change(t, ss):
        "Save the slides `ss` when the talk has no problem, and give the slides part; else 400 with the first problem."
        if (ps := check_talk({**t, 'slides': ss})): return text(ps[0])
        return ui.Deck(lr.put_talk({**t, 'slides': ss}))

    async def slide(req, tid:str):
        if not (t := lr.talk(tid)): return Response('No such talk.', status_code=404)
        f = {k: v for k, v in (await req.form()).items() if isinstance(v, str)}
        ss = deepcopy(list(t.slides))
        if (i := next((k for k, s in enumerate(ss) if s.get('id') == f.get('sid')), None)) is None: return Response('No such slide.', status_code=404)
        act = f.get('act', '')
        try:
            if act in ('up', 'down'):
                k = i - 1 if act == 'up' else i + 1
                if 0 <= k < len(ss): ss[i], ss[k] = ss[k], ss[i]
            elif act == 'drop': ss.pop(i)
            elif act == 'edit': ss[i] = edit(ss[i], f)
            elif act == 'pause':
                prompt = f.get('prompt', '').strip() or PAUSE
                if len(prompt) > OPT_MOST: raise Bad(f'Write the prompt in at most {OPT_MOST} characters.')
                secs = number(f.get('secs') or 120, *SECS, f'A pause is {SECS[0]} to {SECS[1]} seconds.')
                ss.insert(i + 1, blank(new_id(ss), 'pause', 'Pause', math.ceil(secs / 60), prompt=prompt, secs=secs))
            elif act == 'questions': ss.insert(i + 1, blank(new_id(ss), 'questions', 'Questions', QUESTIONS_MIN))
            elif act == 'primer':
                if not (c := lr.concept(f.get('slug', ''))): raise Bad('No such idea.')
                a, p = ask_for_concept(lr, ask(), c.slug), c.get('statement') or ''
                ss.insert(i, dict(id=new_id(ss), kind='primer', concept=c.slug, title=c.name, section=ss[i].get('section') or '',
                                  show=dict(passage=p, figure=None, demo=None), beats=['passage'] if p else [], notes='', ask=a,
                                  mins=slide_minutes(dict(read=dict(text=p)), a)))
            else: return text(f'Unknown change: {act}.')
        except Bad as e: return text(str(e))
        return change(t, ss)

    def slot(tid:str, minutes:str=None, phones:str=None):
        "The minutes of the slot (5 to 240), and room phones (`on` or `off`); each only when the form sends it."
        if not (t := lr.talk(tid)): return Response('No such talk.', status_code=404)
        t = {**t}
        if minutes is not None:
            try: t['minutes'] = number(minutes, *SLOT, f'A slot is {SLOT[0]} to {SLOT[1]} minutes.')
            except Bad as e: return text(str(e))
        if phones is not None: t['phones'] = phones == 'on'
        return ui.Deck(lr.put_talk(t))

    @hook('walk_actions')
    def present(j):
        "On the plan of a walk and on its journey page: make a talk from the walk."
        return ui.PresentWalk(j.id) if j.get('mode') == 'walk' and j.steps else None

    @hook('learning_end')
    def your_talks():
        "Your talks, at the end of Your learning."
        return ui.YourTalks(ts) if (ts := lr.talks()) else None

    app.post(Routes.new)(new)
    app.get(Routes.job)(job)
    app.get(Routes.one)(one)
    app.post(Routes.slide)(slide)
    app.post(Routes.slot)(slot)
