"""The talk: a walk made into slides for a group. "Present this walk" makes the talk on the pool, and the editor changes its slides.
"Present this journey" on a plain journey first makes a walk for the talk from its steps, in their order, and a second press opens
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
from abhyasa.core import Page, hook, n_of, pane_url
from abhyasa.journey import needs, pick_way_down, detour, walk_from_topic, for_talk, journey_walk, journey_changed
from abhyasa.llm import for_task
from abhyasa.settings import val
from abhyasa.talk import (check_talk, talk_from_walk, talk_from_journey, walk_talk, ask_for_concept, slide_minutes, ASK_KINDS, WORDS_MOST, QUESTIONS_MIN,
                          public_deck, public_ask, asset_resolver, BODY_MOST, POINT_MOST, new_run, log_go, log_main, end_run, log_beside,
                          recap, recap_html)
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask', 'pool', 'sources')
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

def edit(s, f):
    "Change slide `s` with the fields that the form `f` sends, and only those."
    if 'notes' in f:
        if len(f['notes']) > NOTE_MOST: raise Bad(f'Write the note in at most {NOTE_MOST} characters.')
        s['notes'] = f['notes'].strip()
    if 'beats' in f: s['beats'] = lines(f['beats'])
    if 'body' in f:   # the points: a new list shows with its beat, and no points take the beat out
        pts, had = lines(f['body']), bool((s.get('show') or {}).get('body'))
        if len(pts) > BODY_MOST or any(len(p) > POINT_MOST for p in pts): raise Bad(f'Write at most {BODY_MOST} points, each in at most {POINT_MOST} characters.')
        s['show'] = {**(s.get('show') or {}), 'body': pts}
        if not pts or not had: s['beats'] = with_part(s.get('beats') or [], 'body', bool(pts))
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

def room_spec(spec):
    "A copy of a demo spec for the audience window: no gate has its `answer`, so the HTML has no answer before the presenter shows it."
    def strip(x):
        if isinstance(x, list): return [strip(v) for v in x]
        if not isinstance(x, dict): return x
        return {k: strip(v) for k, v in x.items() if not (k == 'answer' and x.get('type') == 'gate')}
    return strip(deepcopy(spec))

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

    def plain(j): return bool(j and j.get('mode') != 'walk' and not for_talk(j) and j.steps)   # a journey that is not a walk

    def from_journey(jid:str='', again:str=''):
        "Start the pool job that makes a talk from plain journey `jid`, or finds the one made before. `again` makes a new walk and a new talk."
        if not plain(lr.journey(jid := jid.strip())): return P('No such journey.', cls='req-err')
        if not (job := jobs.get(jid)) or job.done(): jobs[jid] = ctx.pool.submit(lambda: talk_from_journey(lr, ask(), jid, ctx.sources, again=bool(again)).id)
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
        pj = lr.journey(((j or {}).get('parent') or {}).get('journey') or '') if for_talk(j) else None
        up = [(pj.title, f'/j/{pj.id}')] if pj else [(j.title, f'/w/{j.id}')] if j else []
        page = Page(f'{t.title}, as a talk', *ui.Editor(t, j, pj, pj and journey_changed(lr, j)), crumbs=[('Today', '/'), ('Journeys', '/journeys'), *up],
                    extra=ui.assets(), wide=True)
        req.htmlkw['class'] = ' '.join(x for x in (req.htmlkw.get('class'), 'talk') if x)   # the editor keys (talk.js) work only here
        return page

    def change(t, ss):
        "Save the slides `ss` when the talk has no problem, and give the slides part; else 400 with the first problem."
        if (ps := check_talk({**t, 'slides': ss})): return text(ps[0])
        return ui.Deck(lr.put_talk({**t, 'slides': ss}))

    async def slide(req, tid:str):
        if not (t := lr.talk(tid)): return Response('No such talk.', status_code=404)
        form = await req.form()
        f = {k: v for k, v in form.items() if isinstance(v, str)}
        try: f = rows(f, form.getlist('options'))
        except Bad as e: return text(str(e))
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
        out = change(t, ss)
        if f.get('from') == 'after' and not isinstance(out, Response): return ui.Added(t['id'], ss[i]['title'])   # from After the talk
        return out

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
        return ui.Deck(lr.put_talk(t))

    # --- the run: the presenter window, the audience window, the place and the questions ----------------------------------

    def live(tid):
        "Talk `tid` and its open run (None when no run is open)."
        if not (t := lr.talk(tid)): return None, None
        r = lr.run(t.get('live') or '') if t.get('live') else None
        return t, (dict(r) if r and not r.get('ended') else None)

    def slide_of(t, sid): return next((s for s in t['slides'] if s.get('id') == sid), None)

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
                    crumbs=[('Journeys', '/journeys'), (f"{t.title}, as a talk", Routes.of(Routes.one, tid=tid))], extra=ui.assets(), wide=True)

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
        return RedirectResponse(f'/w/{j.id}', status_code=303)

    @hook('walk_actions')
    def present(j):
        "On the plan of a walk and on its journey page: make a talk from the walk. On a plain journey: make a talk from it, or open the one made before."
        if j.get('mode') == 'walk': return ui.PresentWalk(j.id) if j.steps else None
        if not plain(j): return None
        w = journey_walk(lr, j.id)
        return ui.PresentJourney(j.id, w and walk_talk(lr, w.id))

    @hook('learning_end')
    def your_talks():
        "Your talks, at the end of Your learning."
        return ui.YourTalks(ts) if (ts := lr.talks()) else None

    app.post(Routes.new)(new)
    app.post(Routes.journey)(from_journey)
    app.get(Routes.job)(job)
    app.get(Routes.one)(one)
    app.post(Routes.slide)(slide)
    app.post(Routes.slot)(slot)
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
