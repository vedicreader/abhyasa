"""The builder: make a walk or a talk by talking, and see it change beside the conversation (docs/builder-plan.md).

Each conversation has one ramabana agent (`ramabana_lead`, with no web tools), kept in memory by conversation id, and the builder tools
below. Each tool is a thin wrapper over an engine function or a hook of the talk block. A turn runs as a pool job (`build:<id>`), so the
activity chip, Stop and the event stream of the jobs block work as for any job. The conversation keeps its events (`events.py`) and the brief,
and the brief is copied to the walk or the talk that it made. When the app starts again, the next turn gets a short recap of the conversation."""
import ast, json, logging, re, threading, time
from collections import defaultdict
from copy import deepcopy
from functools import wraps
from inspect import signature
from pathlib import Path
from urllib.parse import urlencode
from fasthtml.common import *
from starlette.responses import RedirectResponse
from abhyasa.core import hook, run as run_hook, asset_css, asset_js, Page, n_of, page_req
from abhyasa.core.pane import pane_link
from abhyasa.learner import track, job_said, prompt, profile_text
from abhyasa.models import ramabana_lead, safe_query, ask_json
from abhyasa.sources import named_sources, web_search, VaultSource
from abhyasa.path import (walk_for_talk, file_chip, file_link, chip_state, move_step, edit_lock, edit_walk, undo_walk, lock_step, propose, improve_walk, chip_docs)
from abhyasa.show import (GONE, fit_slides, code_piece, SOURCE_KEYS, fill_slides, talk_minutes, talk_from_walk, talk_again, talk_fresh, with_state, new_brief, shape_free, brief_chips, brief_asks, make_demo as demo_maker, ROLES)
from .events import Emit, fold, new_id
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask', 'pool', 'sources')
log = logging.getLogger(__name__)
_P = Path(__file__).parent
TURN = dict(minutes=5, max_calls=40, max_steps=40, max_cost=2.)   # the caps of one turn of the builder
SAY_MOST = 2000      # the most characters of one request
FOUND_MOST = 6       # the most items of one research
RECAP = 12           # the most earlier messages in the recap of a conversation that the app opens again
CODE_DOCS, CODE_CHARS, CODE_SECS = 40, 120_000, 60   # the documents, the characters of each and the seconds that the search for code pieces may take
TURN_SECS = 15 * 60   # the most seconds of one turn: then it stops, and what it finished stays
WAIT_FINDS = 'The owner keeps or drops the finds of research first. Do not call more tools; end the turn.'
FIELDS = ('kind', 'goal', 'rules', 'aim', 'audience', 'minutes')   # the text fields of the brief that a tool or the pane can set
CHANGERS = ('make_talk', 'make_walk', 'change_talk', 'change_walk', 'edit_slide', 'set_poll', 'make_demo', 'undo')   # the tools that change the walk or the talk

def nums(s) -> list:
    "The whole numbers in `s`, in order, each once."
    return list(dict.fromkeys(int(x) for x in re.findall(r'\d+', str(s or ''))))

def parts(s) -> list:
    "The parts of `s`, split at a new line or a semicolon."
    return [x.strip() for x in re.split(r'[\n;]', str(s or '')) if x.strip()]

def onoff(v):
    "True for on, False for off, None for anything else."
    v = str(v).strip().lower()
    return True if v in ('on', 'true', 'yes', '1') else False if v in ('off', 'false', 'no', '0') else None

NO_SOURCE = "abhyasa's words, no source"

def src_label(read) -> str:
    "The source label of a passage `read` (a walk step's `read`): Research and the site, Your source and the title, or abhyasa's words."
    r = read or {}
    if not (r.get('text') or '').strip(): return NO_SOURCE
    return f"Research · {r.get('site') or r.get('title') or 'the web'}" if r.get('src') == 'web' else f"Your source · {r.get('title') or 'your file'}"

def slide_view(s) -> dict:
    "What a change of slide `s` shows: its title, its points, its notes, its passage (when it shows), its demo and the label of its source."
    sh = s.get('show') or {}
    shown = 'passage' in (s.get('beats') or [])
    src = sh.get('src') or {}
    label = (f"Research · {src.get('site') or src.get('title')}" if src.get('src') == 'web' else f"Your source · {src.get('title') or 'your file'}") if shown and sh.get('passage') else NO_SOURCE
    return dict(title=s.get('title') or '', body=list(sh.get('body') or []), notes=s.get('notes') or '', passage=sh.get('passage') or '' if shown else '', demo=sh.get('demo'), src=label)

def page_title(t) -> str:
    "The title of a web page from a search result, with no breadcrumb: `www.x.org › nlp › self-attention-in-nlpSelf - Attention in NLP` gives `Self - Attention in NLP`."
    t = ' '.join(str(t or '').split())
    if '›' in t: t = t.split('›')[-1].strip()
    t = re.sub(r'^[a-z0-9]+(?:-[a-z0-9]+)+(?=[A-Z])', '', t)   # the slug of the last crumb, glued to the title
    return t[:120]

def slot_line(t) -> str:
    "The real minutes of talk `t` against its slot, as the editor counts them."
    n, slot = talk_minutes(t), t.get('minutes') or 0
    return f"It is about {n} minutes for a slot of {slot} minutes." + ('' if not slot or n <= slot else f" That is {n_of(n - slot, 'minute')} over the slot.")

class Counting:
    "The model `ask`, which calls `on_slide(k)` before the k-th call of the slide writer, so a long make can say which slide it writes. kosha shows no hook for this in ramabana or abhyasa."
    def __init__(self, ask, on_slide, task=None): self.ask, self.on_slide, self.task, self.n, self.lock = ask, on_slide, task, [0], threading.Lock()
    def for_(self, task):
        c = Counting(self.ask, self.on_slide, task); c.n, c.lock = self.n, self.lock
        return c
    def __call__(self, p, sp='', *a, **kw):
        if 'You write one slide of a talk' in str(sp):
            with self.lock: self.n[0] += 1; k = self.n[0]
            try: self.on_slide(k)
            except Exception: pass
        f = (self.ask.for_(self.task) if self.task and hasattr(self.ask, 'for_') else self.ask)
        return f(p, sp, *a, **kw)
    def __getattr__(self, k): return getattr(self.ask, k)

_CODE = re.compile(r'^```(?:python|py)\n(.*?)\n```', re.S | re.M)   # a fenced block with its language, from the start of a line, as `code_piece` reads it: never the prose between two fences
_ASKS_CODE = re.compile(r'\b(show (the )?code|code|technical|python|programmers?|developers?|engineers?)\b', re.I)

def wants_code(br) -> bool:
    "Whether brief `br` asks for code on the slides: its aim, rules, goal or audience says code or technical, and no code is off."
    return not br.get('no_code') and bool(_ASKS_CODE.search(' '.join(str(br.get(k) or '') for k in ('aim', 'rules', 'goal', 'audience'))))

def good_code(code:str) -> bool:
    "Whether `code` teaches: it parses (`ast.parse`), it is not a shim (`sys.modules`, `__import__`), and it is more than imports, comments and a doc string."
    if 'sys.modules' in code or '__import__' in code: return False
    try: tree = ast.parse(code)
    except SyntaxError: return False
    return any(not isinstance(n, (ast.Import, ast.ImportFrom)) and not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)) for n in tree.body)

def junk_path(u) -> bool:
    "Whether the path or link `u` is in a hidden or `_` folder, such as `_leela_agent_sessions` or `.ipynb_checkpoints`: never a source of code."
    return any(x.startswith(('.', '_')) and x not in ('.', '..') for x in str(u or '').split('/')[:-1])

def pick_code(text, name, near='', strict=False) -> str:
    """The code piece (`code_piece`) for the idea `name` from the source text `text`. Only a block that teaches (`good_code`), whose piece parses too.
    First a block in the section of the passage `near`; else the block that names most words of the idea. With `strict`, only a block that names the idea."""
    blocks = [(m.start(), m.group(1)) for m in _CODE.finditer(text or '') if good_code(m.group(1))]
    if not blocks: return ''
    piece = lambda code: (p if good_code(p.removeprefix('```python\n').removesuffix('\n```')) else '') if (p := code_piece(f'```python\n{code}\n```')) else ''
    at = (text or '').find(near[:80]) if near else -1
    if at >= 0:   # the step's own section: from its passage to the next heading
        end = m.start() if (m := re.compile(r'^#{1,3} ', re.M).search(text, at + len(near[:80]))) else len(text)
        for k, code in blocks:
            if at <= k < end and (p := piece(code)): return p
    ws = [w for w in re.findall(r'[a-z]{4,}', name.lower())]
    score = lambda b: sum(w in b.lower() for w in ws)
    for k, code in sorted(blocks, key=lambda x: -score(x[1])):
        if strict and not score(code): break
        if (p := piece(code)): return p
    return ''

LINK_PAGES = 3   # the pages that a kept web find files: the page itself, and at most two pages beside it on the same topic

def on_topic(d, topic:str) -> bool:
    """Whether the filed page `d` is on `topic`: its title names a main word of the topic (5 letters or more). Only the title counts: the start of
    a page is often the menu of the site, which names each tool of the site ("Frequency Calculator" beside "Fourier Series Calculator")."""
    ws = {w for w in re.findall(r'[a-z]{5,}', topic.lower())}
    return not ws or any(w in str(d.title or '').lower() for w in ws)

_FIXED = re.compile(r'(?<![{\w.])(\d+(?:\.\d+)?)\s*(?:°|%|degrees?\b)')   # a number with a unit in static text: it can disagree with the sliders
_NOT_TEXT = {'id', 'bind', 'expr', 'fn', 'type', 'kind', 'src', 'fmt', 'show', 'valuetext', 'min', 'max', 'step', 'x', 'y'}

def _state_nums(st) -> set:
    "The numbers that the state of a demo starts with, and the sum and the gap of each two (a gap of 90° from 130° and 40°): the values that a static text can copy."
    vs = [float(v) for v in ((x.get('value', x.get('init')) if isinstance(x, dict) else x) for x in (st or {}).values()) if isinstance(v, (int, float)) and not isinstance(v, bool)]
    out = set(vs)
    for a in vs:
        for b in vs: out |= {abs(a - b), a + b, (a - b) % 360}
    return out - ({0.0, 360.0} - set(vs))   # a full circle or zero is a fact, unless the state starts there

def fixed_numbers(spec) -> list:
    """The static texts of rupaka demo `spec` that write, outside a `{slot}`, a number with a unit (°, %) that the state starts with or makes (`_state_nums`).
    Such a number disagrees with the sliders once they move ("the Moon is 90° ahead" at 160°). rupaka fills `{name}` from the state, so the text must use a slot.
    A fact such as "a circle has 360°" or "slices of 12°" stays."""
    if not (spec or {}).get('state'): return []
    nums, out = _state_nums(spec['state']), []
    def walk(v, k=''):
        if isinstance(v, dict): [walk(x, kk) for kk, x in v.items() if kk not in _NOT_TEXT]
        elif isinstance(v, list): [walk(x, k) for x in v]
        elif isinstance(v, str) and any(float(m.group(1)) in nums for m in _FIXED.finditer(re.sub(r'\{[^{}]*\}', '', v))): out.append(v)
    walk({k: v for k, v in spec.items() if k != 'state'})
    return out

def _stems(t) -> set: return {w[:5] for w in re.findall(r'[a-z]{4,}', str(t).lower())} - {'which', 'their', 'about', 'there', 'these', 'thing'}

def same_idea(a:str, b:str) -> bool:
    "Whether the step names `a` and `b` are nearly the same idea: half or more of the main words of the shorter name are in the other (`alliances` and `alliance system`)."
    x, y = _stems(a), _stems(b)
    return bool(x and y) and len(x & y) >= max(1, (min(len(x), len(y)) + 1) // 2)

def topic_of(words:str) -> str:
    "What a step that `words` asks for is about: `add a step on the alliance system before ...` gives `alliance system`; '' when it names none."
    m = re.search(r'\b(?:step|idea)s?\s+(?:on|about|for|that covers)\s+(?:the\s+)?(.+?)(?=\s+(?:before|after|at|as)\b|[.,;!?]|$)', str(words), re.I)
    return m.group(1).strip() if m else ''

def anchor_of(words:str) -> str:
    "The step that `words` names with before or after: `... before the assassination` gives `assassination`."
    m = re.search(r'\b(?:before|after)\s+(?:the\s+)?(.+?)(?:[.,;!?]|$)', str(words), re.I)
    return m.group(1).strip() if m else ''

def place_of(words:str, steps, slug) -> int|None:
    "The index that `words` asks for the step on `slug`: before or after a named step, first or last; None when it names no place."
    w = str(words).lower(); names = [(k, s['slug']) for k, s in enumerate(steps) if s['slug'] != slug]
    if re.search(r'\b(at the start|first step|as the first|at the beginning)\b', w): return 0
    if re.search(r'\b(at the end|last step|as the last)\b', w): return len(steps) - 1
    if (m := re.search(r'\b(before|after)\s+(?:the\s+)?(.+?)(?:[.,;!?]|$)', w)):
        hit = max(names, key=lambda x: len(_stems(m.group(2)) & _stems(x[1].replace('-', ' '))), default=None)
        if hit and _stems(m.group(2)) & _stems(hit[1].replace('-', ' ')):
            k = hit[0] - (1 if [s['slug'] for s in steps].index(slug) < hit[0] else 0)   # its index once the new step leaves its place
            return max(0, min(len(steps) - 1, k if m.group(1) == 'before' else k + 1))
    return None

RETITLE_SP = ('You give the slide titles of a talk words for its audience. Keep each idea, the order and the count. Use plain words that the audience uses, '
              'at most 7 words, and no code names when there is no code. Write in ASD-STE100 Simplified Technical English. Return JSON: {"titles": ["..."]}')

def goal_of(br) -> str:
    """The goal that goes to the planner. With sources and research off, none: the walk then reads only those sources (a notebook as it is, or the
    documents in their order), and does not look for passages in the rest of the vault. The goal still goes to the writers in `brief_asks`."""
    return '' if brief_chips(br) and br.get('research') is False else br.get('goal') or ''

def connect(app, ctx):
    lr = ctx.learning
    locks, agents, jobs = defaultdict(threading.RLock), {}, {}
    key = lambda bid: f'build:{bid}'
    name_of = lambda slug: (lr.concept(slug) or {}).get('name') or slug
    def sourced_line(j) -> str:
        "How many steps of walk `j` have a passage, and from which sources: the real counts, for the summary of the turn."
        r = [s_.get('read') or {} for s_ in j.steps]
        have, web = sum(bool(x.get('text')) for x in r), sum(bool(x.get('text')) and x.get('src') == 'web' for x in r)
        if not have and not j.get('chips'): return ("This walk has no sources yet: each step has abhyasa's words, with no source. "
                             "Say “research the material” to look for sources, or add a file, a folder or a link.")
        return f"{have} of {n_of(len(r), 'step')} {'has' if have == 1 else 'have'} a passage from a source" + (f", {web} from the web" if web else '') + '.'
    def filed(chips, bid=None) -> list:
        """The chips with each `link:` filed first and named by its documents (`doc:`), so the planner and the passage search read a kept web page
        as a source. A link that abhyasa cannot read is left out, and its source in the brief of conversation `bid` becomes dropped, so no make fails on it.
        `filed.why` keeps the real reason of each link that failed, for the record of the walk (`record`)."""
        out, bad = [], {}
        br = lr.build(bid).brief if bid else {}
        for c in chips:
            if not str(c).startswith('link:'): out.append(c); continue
            try: ds = list(file_link(lr, c[5:], max_pages=LINK_PAGES))   # the page and at most a few pages beside it, never the whole site
            except Exception as e: log.warning('builder: could not file %s: %r', c, e); ds, bad[c] = [], f'abhyasa could not file {c[5:]}. {e}'.strip()
            name = next((x.get('name') or '' for x in br.get('sources') or [] if x['id'] == c), '')
            ds = [d for k, d in enumerate(ds) if k == 0 or on_topic(d, br.get('goal') or name)]   # the goal, not the name of the site page, which names the site too   # a page beside it that is off the topic goes
            if ds: out += [f'doc:{d.doc_id}' for d in ds]
            else: bad.setdefault(c, f'abhyasa could not file {c[5:]}: it has no text to read.')
        filed.why = bad
        if bad and bid:
            ss = [{**x, 'role': 'dropped'} if x['id'] in bad else x for x in lr.build(bid).brief.get('sources') or []]
            put_brief(bid, sources=ss)
            Emit(lambda e: emit(bid, e)).ev('CUSTOM', name='note', value=f"abhyasa could not read {n_of(len(bad), 'link')}, so it left them out: {', '.join(x[5:] for x in bad)}")
        return list(dict.fromkeys(out))
    filed.why = {}

    def record(jid, chips):
        "Keep on walk `jid` the count of documents of each chip and the real reason of each link that failed, as the Start job does, so its Sources rows are true."
        counts = {c: s.count for c in chips if (s := chip_state(lr, c))}
        lr.merge_journey(jid, chip_counts=counts, notes=[*filed.why.values()])

    def outline_of(j): return dict(outline=[name_of(s['slug']) for s in j.steps], labels=[src_label(s.get('read')) for s in j.steps])

    # --- the conversation and the brief --------------------------------------------------------------------------

    def emit(bid, e):
        "Keep event `e` in conversation `bid`."
        with locks[bid]:
            b = lr.build(bid)
            lr.put_build({**b, 'events': [*(b.get('events') or []), e]})

    def load(bid):
        "Conversation `bid`, with `keep` of its brief from the walk or the talk: the Keep toggles of those pages write there."
        b = lr.build(bid)
        if not b: return b
        k, i = target(b)
        if k == 'talk' and (t := lr.talk(i)) and 'keep' in (t.get('brief') or {}): b = AttrDict({**b, 'brief': {**b.brief, 'keep': list(t.brief['keep'])}})
        elif k == 'walk' and (j := lr.journey(i)): b = AttrDict({**b, 'brief': {**b.brief, 'keep': [s['slug'] for s in j.steps if s.get('locked')]}})
        return b

    def target(b):
        "`(kind, id)` of the walk or the talk of conversation `b`, or `('', '')`."
        k, _, i = str((b or {}).get('target') or '').partition(':')
        return k, i

    def thing(b):
        "The talk or the walk of conversation `b`, or None."
        k, i = target(b)
        return lr.talk(i) if k == 'talk' else lr.journey(i) if k == 'walk' else None

    def copy_brief(b, brief):
        "Keep `brief` on the walk or the talk of conversation `b` too."
        k, i = target(b)
        if k == 'talk':
            with edit_lock('talk', i):
                if (t := lr.talk(i)): lr.put_talk({**t, 'brief': brief, 'build': b['id']})
        elif k == 'walk' and lr.journey(i): lr.merge_journey(i, brief=brief, build=b['id'])

    def said_of(old, new) -> str:
        "The short note of what changed from brief `old` to brief `new`, as the agent reads it."
        out = [f"{k} = {new[k] or 'none'}" for k in (*FIELDS, ) if new.get(k) != old.get(k)]
        if new.get('research') != old.get('research'): out.append(f"research {'on' if new.get('research') else 'off'}")
        if new.get('no_code') != old.get('no_code'): out.append(f"no code {'on' if new.get('no_code') else 'off'}")
        was = {s['id']: s.get('role') for s in old.get('sources') or []}
        out += [f"{s.get('name') or s['id']} is {s.get('role')}" for s in new.get('sources') or [] if was.get(s['id']) != s.get('role')]
        gone = {f.get('url'): f.get('role') for f in old.get('found') or []}
        out += [f"{'kept' if f.get('role') == 'extra' else 'dropped'} {f.get('title') or f.get('url')}" for f in new.get('found') or [] if f.get('role') and gone.get(f.get('url')) != f.get('role')]
        return '; '.join(out)

    def put_brief(bid, by='agent', **kw):
        """The one writer of the brief of conversation `bid`, for the tools and for the brief box: merge `kw`, keep a snapshot event, and copy
        the brief to the walk or the talk. A change by the owner also leaves a note for the next turn of the agent. Return the brief."""
        with locks[bid]:
            b = lr.build(bid)
            old = b.brief; new = {**old, **kw}
            if new == old: return new
            ev = dict(type='STATE_SNAPSHOT', at=time.time(), snapshot=new)
            note = (b.get('note') or '') + (('; ' if b.get('note') else '') + said_of(old, new) if by == 'owner' else '')
            lr.put_build({**b, 'brief': new, 'note': note, 'events': [*(b.get('events') or []), ev]})
        if new.get('research') is False and old.get('research') is not False: dropped_web(b)
        copy_brief(b, new)
        return new

    def dropped_web(b):
        "Research went off: a walk of conversation `b` loses each passage from the web, as one change with an Undo."
        k, i = target(b)
        j = lr.journey(i) if k == 'walk' else lr.journey(((lr.talk(i) or {}).get('src') or {}).get('walk') or '') if k == 'talk' else None
        if not j or not any((s.get('read') or {}).get('src') == 'web' for s in j.steps): return
        def op(ss): return [{**s, 'read': None} if (s.get('read') or {}).get('src') == 'web' else s for s in ss]
        edit_walk(lr, j.id, op, 'Dropped the passages from the web.', who='tutor')

    def new_build(target_='', brief=None, title='') -> str:
        bid = new_id()
        lr.put_build(dict(id=bid, title=title, target=target_, brief=brief or new_brief(), events=[], note=''))
        return bid

    def for_talk(t):
        "The conversation of talk `t`, or a new one with a brief from the talk."
        if (bid := t.get('build')) and lr.build(bid): return bid
        j = lr.journey((t.get('src') or {}).get('walk') or '') or {}
        srcs = [dict(id=c, name=c.split(':', 1)[-1].rstrip('/').split('/')[-1], role='main') for c in j.get('chips') or ()]
        br = t.get('brief') or new_brief(kind='talk', goal=j.get('goal') or '', audience=t.get('audience') or '', no_code=bool(t.get('no_code')), minutes=t.get('minutes') or 0, sources=srcs)
        bid = new_build(f"talk:{t['id']}", br, t['title'])
        with edit_lock('talk', t['id']): lr.put_talk({**lr.talk(t['id']), 'build': bid})
        return bid

    def for_walk(j):
        "The conversation of walk `j`, or a new one with a brief from the walk."
        if (bid := j.get('build')) and lr.build(bid): return bid
        srcs = [dict(id=c, name=c.split(':', 1)[-1].rstrip('/').split('/')[-1], role='main') for c in j.get('chips') or ()]
        br = j.get('brief') or new_brief(kind='walk', goal=j.get('goal') or '', audience=j.get('audience') or '', no_code=bool(j.get('no_code')), sources=srcs)
        bid = new_build(f"walk:{j['id']}", br, j['title'])
        lr.merge_journey(j['id'], build=bid)
        return bid

    # --- the tools -----------------------------------------------------------------------------------------------

    def tools(bid, st):
        "The builder tools of conversation `bid`. `st` has the events of the turn now (`em`) and the call that runs (`cur`)."
        rec = lambda: load(bid)
        def stage(x): st.em.stage(st.cur, x); job_said(lr, key(bid), x)
        def need(kind):
            b = rec(); k, _ = target(b)
            if k != kind or not (x := thing(b)): raise ValueError(f'There is no {kind} yet. Make one first.')
            if kind == 'talk' and x.get('live') and (r := lr.run(x['live'])) and not r.get('ended'): raise ValueError(ui.RUNNING)   # the room sees the talk now
            return x
        def slide_ids(t, ns): return [t.slides[n - 1]['id'] for n in ns if 1 <= n <= len(t.slides)]
        def at_n(t, sid): return next((k + 1 for k, s in enumerate(t.slides) if s.get('id') == sid), None)

        def add_source(ref:str,       # a path to a file or a folder, a link, a GitHub repo, or a chip id such as file:/a/b.ipynb
                       role:str='main', # main, or extra: an extra source adds to the main sources
                       ) -> str:
            "Add a source to the brief, with its role."
            if role not in ROLES[:2]: raise ValueError('The role is main or extra.')
            cs = named_sources(ref) or ([dict(id=ref.strip(), name=ref.split(':', 1)[-1].rstrip('/').split('/')[-1])] if re.match(r'(file|folder|repo|gh|link|doc|vault):\S', ref.strip()) else [])
            if not cs: raise ValueError(f'abhyasa does not know this source: {ref}. Give a path, a link or a repo.')
            ss = [s for s in rec().brief.get('sources') or [] if s['id'] not in {c['id'] for c in cs}]
            put_brief(bid, sources=[*ss, *[dict(id=c['id'], name=c.get('name') or c['id'], role=role) for c in cs]])
            return f"Added {', '.join(c.get('name') or c['id'] for c in cs)} as {role}."

        def set_source(ref:str,  # the name or the chip id of a source in the brief
                       role:str,  # main, extra or dropped
                       ) -> str:
            "Change the role of a source in the brief, or drop it."
            if role not in ROLES: raise ValueError('The role is main, extra or dropped.')
            ss = deepcopy(rec().brief.get('sources') or [])
            hit = [s for s in ss if ref in (s['id'], s.get('name')) or ref.lower() in (s.get('name') or '').lower()]
            if not hit: raise ValueError(f"No source in the brief is {ref}. The sources: {', '.join(s.get('name') or s['id'] for s in ss) or 'none'}.")
            for s in hit: s['role'] = role
            put_brief(bid, sources=ss)
            return f"{', '.join(s.get('name') or s['id'] for s in hit)} is {role} now."

        def set_brief(kind:str='',      # walk or talk
                      goal:str='',      # the topic or the goal, in the owner's words
                      aim:str='',       # the tone or the goal of the walk or the talk, such as "become technical"
                      audience:str='',  # who it is for, such as "managers"
                      rules:str='',     # the owner's own rules about the sources, such as "where they conflict, use the notebook"
                      research:str='',  # on or off; off means use only the owner's sources
                      no_code:str='',   # on or off
                      minutes:int=0,    # the minutes of a talk
                      ) -> str:
            "Change the brief. An empty field stays as it is."
            kw = {k: ' '.join(v.split()) for k, v in dict(kind=kind, goal=goal, aim=aim, audience=audience, rules=rules).items() if v.strip()}
            if re.search(r'\b(slide|step|idea)s? \d', kw.get('rules', ''), re.I): raise ValueError('A rule covers the whole walk or talk. For one slide or step, use change_talk or change_walk with its number.')
            if kw.get('kind') not in (None, 'walk', 'talk'): raise ValueError('The kind is walk or talk.')
            if minutes: kw['minutes'] = int(minutes)
            for k, v in dict(research=research, no_code=no_code).items():
                if (x := onoff(v)) is not None: kw[k] = x
            if kw.get('research') is False:   # use only my sources: the items that research found and the owner kept go
                kw['found'] = [{**f, 'role': 'dropped'} if f.get('role') == 'extra' else f for f in rec().brief.get('found') or []]
                urls = {f"link:{f['url']}" for f in kw['found']}
                kw['sources'] = [{**s, 'role': 'dropped'} if s['id'] in urls else s for s in rec().brief.get('sources') or []]
            put_brief(bid, **kw)
            k, i = target(rec())
            if kw.get('no_code') and k == 'walk' and (j := lr.journey(i)) and any((x.get('check') or {}).get('kind') in ('notebook', 'code') for x in j.steps):
                n = sum((x.get('check') or {}).get('kind') in ('notebook', 'code') for x in j.steps)   # no code now: each hands-on check of the walk is a short answer
                edit_walk(lr, i, lambda ss: [{**x, 'check': {'way': 'words', 'kind': 'short', 'depth': (x.get('check') or {}).get('depth', 2), 'why': ''}}
                                             if (x.get('check') or {}).get('kind') in ('notebook', 'code') else x for x in ss], f'No code: {n_of(n, "check")} became short answers.', who='tutor')
                return f'The brief is changed. No code: {n_of(n, "check")} of the walk became short answers, and the steps stay.'
            return 'The brief is changed.' if kw else 'Nothing to change.'

        def keep(items:str,  # the numbers of the slides or the steps, such as "2, 4"
                 ) -> str:
            "Leave these slides or steps as they are when the walk or the talk changes."
            b = rec(); k, i = target(b); x = thing(b)
            if not x: raise ValueError('There is no walk or talk yet.')
            ns = nums(items)
            if k == 'talk': ids = slide_ids(x, ns)
            else:
                ids = [x.steps[n - 1]['slug'] for n in ns if 1 <= n <= len(x.steps)]
                for s in ids: edit_walk(lr, i, lambda ss, s=s: lock_step(ss, s), f'Kept step {s}.', who='tutor')
            put_brief(bid, keep=list(dict.fromkeys([*(b.brief.get('keep') or []), *ids])))
            return f"Kept {', '.join(map(str, ns))} as they are."

        def free(items:str,  # the numbers of the slides or the steps, such as "2, 4"
                 ) -> str:
            "Let these slides or steps change again."
            b = rec(); k, i = target(b); x = thing(b)
            if not x: raise ValueError('There is no walk or talk yet.')
            ns = nums(items)
            ids = slide_ids(x, ns) if k == 'talk' else [x.steps[n - 1]['slug'] for n in ns if 1 <= n <= len(x.steps)]
            if k == 'walk':
                for s in ids: edit_walk(lr, i, lambda ss, s=s: lock_step(ss, s, False), f'Let step {s} change again.', who='tutor')
            put_brief(bid, keep=[x_ for x_ in b.brief.get('keep') or [] if x_ not in ids])
            return f"{', '.join(map(str, ns))} can change now."

        def show() -> str:
            "A short outline of the walk or the talk as it is now."
            b = rec(); k, _ = target(b); x = thing(b)
            if not x: return 'There is no walk or talk yet.'
            kept = set(b.brief.get('keep') or [])
            if k == 'talk':
                def line(n, s):
                    sh = s.get('show') or {}
                    bits = [f"{n}. [{s.get('kind')}] {s.get('title')}"]
                    if (s.get('ask') or {}).get('q'): bits.append(f"question: {s['ask']['q']}" + (f" ({'; '.join(s['ask'].get('options') or [])})" if s['ask'].get('options') else ''))
                    if sh.get('body'): bits.append('points: ' + ' | '.join(sh['body']))
                    if '```' in (sh.get('passage') or '') and 'passage' in (s.get('beats') or []): bits.append(f"shows {len(sh['passage'].splitlines()) - 2} lines of code")
                    elif sh.get('passage') and 'passage' in (s.get('beats') or []): bits.append('shows a passage')
                    if sh.get('demo'): bits.append('has a live demo')
                    if s['id'] in kept: bits.append('KEPT')
                    return ' · '.join(bits)
                return f"The talk “{x.title}”, a slot of {x.get('minutes')} minutes:\n" + '\n'.join(line(n, s) for n, s in enumerate(x.slides, 1))
            name = lambda s: (lr.concept(s['slug']) or {}).get('name') or s['slug']
            src = lambda s: ('from the web' if (s.get('read') or {}).get('src') == 'web' else f"from {(s.get('read') or {}).get('title') or 'your source'}") if (s.get('read') or {}).get('text') else 'no passage'
            return f"The walk “{x.title}”:\n" + '\n'.join(f"{n}. {name(s)} · {src(s)}" + (' · KEPT' if s.get('locked') or s['slug'] in kept else '') for n, s in enumerate(x.steps, 1))

        def with_code(tid) -> int:
            """For a brief that asks for code: each idea slide whose passage has no code shows a short code piece from the source document of its step,
            as a slide of a notebook section does: 2 to 4 points first, then the code piece as a later beat. A slide with no points gets them from the slide
            writer (`fill_slide`), which reads the old passage. The piece is word for word from the source. The count of slides that got code."""
            if not wants_code(br := rec().brief): return 0
            t = lr.talk(tid); j = lr.journey((t.get('src') or {}).get('walk') or '') or {}
            others = [d for _, ds in chip_docs(lr, j.get('chips') or ()) for d in ds if not junk_path(d.url)][:CODE_DOCS]
            texts, end = {}, time.monotonic() + CODE_SECS
            def text_of(shelf, doc_id):
                "The text of a document, read one time for the whole talk; '' after the time for the search of code is over."
                if not doc_id or (doc_id not in texts and time.monotonic() > end): return ''
                if doc_id not in texts:
                    try: texts[doc_id] = (lr.doc_shelf(shelf) or lr.vault).document(doc_id, max_chars=CODE_CHARS, disk=False).text
                    except Exception: texts[doc_id] = ''
                return texts[doc_id]
            by = {x['slug']: x.get('read') or {} for x in j.get('steps') or ()}
            new = {}
            for x in t.slides:
                sh, r = x.get('show') or {}, by.get(x.get('concept') or '') or {}
                if x.get('kind') != 'idea' or '```' in (sh.get('passage') or ''): continue
                piece, src = ('' if junk_path(r.get('url')) else pick_code(text_of(r.get('shelf'), r.get('doc_id')), x.get('title') or '', r.get('text') or '')), r
                for d in ([] if piece else others):   # the step's own document has no code: a document of the sources that has code on the idea
                    if (piece := pick_code(text_of(d.shelf, d.doc_id), x.get('title') or '', strict=True)):
                        src = dict(src='vault:' + d.shelf, shelf=d.shelf, doc_id=d.doc_id, ref=d.doc_id, title=d.title, url=d.url, text=piece); break
                if not piece: continue
                y = deepcopy(x); prose = sh.get('passage') or r.get('text') or ''
                y['show'] = {**sh, 'passage': piece, 'src': {k: v for k in SOURCE_KEYS if (v := src.get(k) if k != 'src' else src.get(k) or 'doc') not in (None, '')}}
                y['beats'] = [*[b_ for b_ in y.get('beats') or [] if b_ != 'passage'], 'passage']
                new[x['id']] = y if y['show'].get('body') else {**y, '_read': prose}   # the code never takes the place of the words: the writer makes points from the old passage
            need = [y for y in new.values() if '_read' in y]
            if need:
                stage(f"Writing the points of {n_of(len(need), 'slide')} with code")
                for y in fill_slides(lr, ctx.ask, need, ctx.sources, br.get('audience') or '', False, brief_asks(br, slides=True)):   # 4 at a time
                    y = {k: v for k, v in y.items() if k != '_read'}
                    if (y.get('show') or {}).get('body'): new[y['id']] = y
                    else: new.pop(y['id'], None)   # no points from the writer: the slide keeps its words and gets no code
            if not new: return 0
            with edit_lock('talk', tid):
                t = lr.talk(tid)
                lr.put_talk({**t, 'slides': [new.get(x['id'], x) for x in t.slides]})
            return len(new)

        def fit_to_slot(tid) -> list:
            """Make talk `tid` fit its slot after its slides are written (`fit_slides`): shorten each idea, then merge neighbours, then cut ideas only at the end.
            A kept slide never changes. It is part of the make or the remake, so its Undo takes it back too. The lines that say what it did."""
            with edit_lock('talk', tid):
                t = lr.talk(tid)
                ss, said = fit_slides(t.slides, t.get('minutes') or 0, set(rec().brief.get('keep') or []))
                if ss != list(t.slides): lr.put_talk({**t, 'slides': ss})
            return said

        def make_talk(minutes:int=0,  # the minutes of the slot; 0 keeps the brief
                      new:bool=False,  # true makes a new talk when one exists
                      ) -> str:
            "Make the talk from the brief: file its sources, plan its ideas, then write its slides."
            b = rec(); br = b.brief
            if target(b)[0] == 'talk' and thing(b) and not new: return 'A talk exists. Use change_talk to change it.'
            if not (chips := filed(brief_chips(br), bid)) and not br.get('goal'): raise ValueError('The brief has no source and no goal. Add a source, or set the goal.')
            j = walk_for_talk(lr, ctx.ask, chips, goal_of(br), br.get('audience') or '', bool(br.get('no_code')), ctx.sources, said=stage, owner=brief_asks(br), near=not chips)   # with sources, no idea from other content of the vault
            record(j.id, chips); lr.merge_journey(j.id, change=brief_asks(br, slides=True) or None, build=bid)   # the writer of each slide gets no rule about the shape of the talk
            mins = int(minutes or br.get('minutes') or 0)
            j = lr.journey(j.id)
            outline = [name_of(s['slug']) for s in j.steps if s.get('status') != 'skip']
            st.em.data(st.cur, dict(outline=outline))
            stage(f'Writing {n_of(len(outline), "slide")}')
            try: t = talk_from_walk(lr, Counting(ctx.ask, lambda k: stage(f'Writing slide {k} of {len(outline)}')), j.id, sources=ctx.sources)
            except BaseException: lr.drop_journey(j.id); raise
            t = lr.put_talk({**t, **({'minutes': mins} if mins else {}), 'brief': {**br, 'kind': 'talk', 'minutes': mins or t.minutes}, 'build': bid})
            coded = with_code(t.id)
            fit = fit_to_slot(t.id)
            t = lr.talk(t.id)
            with locks[bid]: lr.put_build({**rec(), 'target': f'talk:{t.id}', 'title': t.title})
            put_brief(bid, kind='talk', minutes=t.minutes)
            run_hook('concepts_added')
            return (f"Made the talk “{t.title}”: {n_of(len([x for x in t.slides if x.get('section') != GONE]), 'slide')}. {slot_line(t)} {' '.join(fit)}".strip()
                    + (f" {n_of(coded, 'slide')} show a code piece from the source." if coded else ''),
                    dict(outline=outline, fit=fit, slides=[s.get('title') for s in t.slides]))

        def make_walk(new:bool=False,  # true makes a new walk when one exists
                      ) -> str:
            "Make the walk from the brief. When a walk exists, plan it again from the brief, as one change with an Undo."
            b = rec(); br = b.brief
            chips, goal, owner = filed(brief_chips(br), bid), br.get('goal') or '', brief_asks(br)
            if target(b)[0] == 'walk' and (j := thing(b)) and not new:
                stage('Planning the walk again')
                # the walk again from the brief: the chips are filed (a kept find too), and the steps take the place of the old ones, as one change with an Undo
                tmp = walk_for_talk(lr, ctx.ask, chips, goal_of(br), br.get('audience') or '', bool(br.get('no_code')), ctx.sources, said=stage, owner=owner, near=not chips)
                try: j2, h = edit_walk(lr, j.id, lambda ss: deepcopy(tmp.steps), 'Made the walk again from the brief.', who='tutor',
                                       fields=dict(chips=chips, source=tmp.get('source'), notebook=tmp.get('notebook')))
                finally: lr.drop_journey(tmp.id)
                record(j.id, chips)
                if h is None: return 'The walk from the brief is the same as the walk now. Nothing changed.'
                put_brief(bid, kind='walk')
                return f"Made the walk again from the brief: {len(j2.steps)} steps. {sourced_line(j2)}", outline_of(j2)
            if not chips and not goal: raise ValueError('The brief has no source and no goal. Add a source, or set the goal.')
            j = walk_for_talk(lr, ctx.ask, chips, goal_of(br), br.get('audience') or '', bool(br.get('no_code')), ctx.sources, said=stage, owner=owner, near=not chips)
            j = lr.merge_journey(j.id, parent=None, brief={**br, 'kind': 'walk'}, build=bid)
            record(j.id, chips)
            with locks[bid]: lr.put_build({**rec(), 'target': f'walk:{j.id}', 'title': j.title})
            put_brief(bid, kind='walk')
            run_hook('concepts_added')
            line = sourced_line(j)
            return (f"{line} Made the walk “{j.title}”: {len(j.steps)} steps." if line.startswith('This walk has no sources') else f"Made the walk “{j.title}”: {len(j.steps)} steps. {line}"), outline_of(j)

        def change_talk(instruction:str,  # what to change, in the owner's words
                        slides:str='',    # the numbers of the slides to change, such as "3"; empty makes the whole talk again
                        fresh:bool=False, # true makes the talk again from scratch, with no edits
                        ) -> str:
            "Change the talk: only the slides named, or the whole talk again. The slides in keep never change."
            t = need('talk'); br = rec().brief; kept = set(br.get('keep') or [])
            if (ns := nums(slides)):
                if (bad := [n for n in ns if 1 <= n <= len(t.slides) and t.slides[n - 1]['id'] in kept]): raise ValueError(f"Slide {', '.join(map(str, bad))} is kept. Use free first.")
                before = {n: slide_view(t.slides[n - 1]) for n in ns if 1 <= n <= len(t.slides)}
                out = []
                for n in before:
                    stage(f'Writing slide {n}')
                    out.append(first(run_hook('talk_rewrite', t.id, n, instruction)))
                t2 = lr.talk(t.id)
                return ' '.join(out), dict(changed=[dict(n=n, before=v, after=slide_view(t2.slides[n - 1])) for n, v in before.items()])
            stage('Writing the talk again')
            wid = (t.get('src') or {}).get('walk') or ''
            who = dict(audience=br.get('audience') or '', no_code=bool(br.get('no_code')))
            new_who = (t.get('audience') or '') != who['audience'] or bool(t.get('no_code')) != who['no_code']
            if lr.journey(wid): lr.merge_journey(wid, **who, **({'goal': br['goal']} if br.get('goal') else {}))
            with edit_lock('talk', t.id): lr.put_talk({**lr.talk(t.id), **who})   # the remake writes for the audience of the brief
            was = {s['id']: deepcopy(s) for s in t.slides}
            (talk_fresh if fresh else talk_again)(lr, ctx.ask, t.id, ctx.sources, change=' '.join(x for x in (brief_asks(br, slides=True), shape_free(instruction)) if x))   # no rule on the poll or the last slide goes to each slide
            with edit_lock('talk', t.id):   # the kept slides stay word for word: the change of the remake keeps them, and one Undo takes all of it back
                t2 = lr.talk(t.id)
                ss = [deepcopy(was[s['id']]) if s['id'] in kept and s['id'] in was else s for s in t2.slides]
                old_poll = next((x for x in was.values() if x.get('kind') == 'poll'), None)
                if old_poll and 'poll' not in (st.get('said') or instruction).lower():   # your poll stays, unless your words of this turn ask to change it
                    if any(x.get('kind') == 'poll' for x in ss): ss = [{**x, 'ask': deepcopy(old_poll.get('ask'))} if x.get('kind') == 'poll' else x for x in ss]
                    else: ss = [deepcopy(old_poll), *ss]
                if ss != t2.slides: t2 = lr.put_talk({**t2, 'slides': ss})
            if (fresh or new_who) and who['audience']: retitle(t.id, who, kept)   # set_brief copies the audience to the talk first, so a fresh remake retitles too
            with_code(t.id); fit = fit_to_slot(t.id); t2 = lr.talk(t.id)
            ch = [dict(n=n, before=slide_view(was[s['id']]), after=slide_view(s)) for n, s in enumerate(t2.slides, 1) if s['id'] in was and slide_view(was[s['id']]) != slide_view(s)]
            return (f"Made the talk again. {len(ch)} slides changed; {len(kept)} kept. {slot_line(t2)} {' '.join(fit)}".strip(),
                    dict(changed=ch))

        def retitle(tid, who, kept=()):
            "Give the idea slides of talk `tid` titles for the audience of `who` (one model call). The ideas, their order and the kept slides stay."
            t = lr.talk(tid); ss = [x for x in t.slides if x.get('kind') == 'idea' and x['id'] not in kept]
            if not ss: return
            ask = f"The audience: {who['audience']}" + (' (no code)' if who.get('no_code') else '') + '\n\nThe titles, in order:\n' + '\n'.join(f"{k}. {x['title']}" for k, x in enumerate(ss, 1))
            try: r = ask_json(ctx.ask, ask, RETITLE_SP)
            except Exception: return
            ts = [' '.join(str(x).split()) for x in (r.get('titles') if isinstance(r, dict) else None) or []]
            if len(ts) != len(ss) or not all(ts): return   # a wrong count keeps the titles
            by = {x['id']: re.sub(r'^\s*\d+\.\s*', '', tt)[:80] for x, tt in zip(ss, ts)}
            with edit_lock('talk', tid):
                now = lr.talk(tid)
                lr.put_talk({**now, 'slides': [{**x, 'title': (re.match(r'^\s*\d+\.\s*', x['title']) or [''])[0] + by[x['id']]} if x['id'] in by else x for x in now.slides]})

        def edit_slide(slide:int,        # the number of the slide
                       title:str='',     # a new title
                       points:str='',    # new points, split by semicolons
                       notes:str='',     # new speaker notes
                       show_code:str='', # off hides the code or the passage of the slide; on shows it
                       ) -> str:
            "Change the fields of one slide by hand."
            t = need('talk'); f = {}
            if 1 <= slide <= len(t.slides) and t.slides[slide - 1]['id'] in set(rec().brief.get('keep') or []): raise ValueError(f'Slide {slide} is kept. Use free first.')
            if title.strip(): f['title'] = title
            if points.strip(): f['body'] = '\n'.join(parts(points))
            if notes.strip(): f['notes'] = notes
            if (v := onoff(show_code)) is not None: f['show_passage'] = 'on' if v else 'off'
            if not f: return 'Nothing to change.'
            before = slide_view(t.slides[slide - 1]) if 1 <= slide <= len(t.slides) else None
            said = first(run_hook('talk_edit', t.id, slide, f)) or 'Nothing changed.'
            return said, dict(changed=[dict(n=slide, before=before, after=slide_view(lr.talk(t.id).slides[slide - 1]))]) if before else None

        def set_poll(q:str,        # the question for the room
                     options:str,  # 2 to 5 options, split by semicolons
                     ) -> str:
            "Change the poll at the start of the talk."
            t = need('talk')
            if not (n := next((k for k, s in enumerate(t.slides, 1) if s.get('kind') == 'poll'), None)): raise ValueError('This talk has no poll.')
            return first(run_hook('talk_edit', t.id, n, dict(kind='choice', q=q, options='\n'.join(parts(options))))) or 'Nothing changed.'

        def make_checked(slug, what):
            """A demo from the demo maker that passed its checks, and whose static text has no number that the sliders change (`fixed_numbers`).
            One more try with the rule said plainly; then a `ValueError` that names the text."""
            said = ' '.join(what.split())[:300]
            for k in range(2):
                d = demo_maker(lr, ctx.ask, slug, said=said if not k else f'{said} Write no fixed number in the text: put each value that the reader changes in a {{name}} slot of the state.')
                if d is None: raise ValueError('abhyasa could not make a demo that passed its checks. Try other words.')
                if not (bad := fixed_numbers(d.spec)): return d
            raise ValueError(f'The demo writes a fixed number that the sliders change: “{bad[0][:80]}”. abhyasa did not use it.')

        def make_demo(slide:int,          # the number of the slide, or of the step of a walk
                      what:str,           # what the demo shows, in the owner's words, such as "move the temperature and see the probabilities change"
                      replace:bool=False, # true changes the demo that the slide shows; false puts a second demo on a new slide after it
                      ) -> str:
            "Make an interactive demo from the owner's words, for a slide of the talk or a step of the walk, and show it there."
            b = rec(); k, _ = target(b); x = thing(b)
            if not x: raise ValueError('There is no walk or talk yet. Make one first.')
            if k == 'walk':
                if not 1 <= slide <= len(x.steps): raise ValueError(f'The walk has {n_of(len(x.steps), "step")}.')
                slug = x.steps[slide - 1]['slug']
                stage(f'Writing the demo for step {slide}')
                d = make_checked(slug, what)
                d = lr.put_demo(d.spec, slug)   # the plain demo of the idea, so the step shows it
                edit_walk(lr, x.id, lambda ss: [{**s_, 'check': {**(s_.get('check') or {}), 'kind': 'demo', 'way': 'demo'}} if s_['slug'] == slug else s_ for s_ in ss],
                          f'Put a live demo on step {slide}.', who='tutor')
                return f'Put a live demo on step {slide}.', dict(slide=slide, demo=d.slug, spec=d.spec, step=True)
            t = need('talk')
            if not 1 <= slide <= len(t.slides) or not (slug := t.slides[slide - 1].get('concept')): raise ValueError(f'Slide {slide} has no idea, so it cannot show a demo.')
            stage(f'Writing the demo for slide {slide}')
            d = make_checked(slug, what)
            said = first(run_hook('talk_demo', t.id, slide, d.slug, replace=replace))
            at = slide + 1 if 'new slide' in said else slide
            return said, dict(slide=at, demo=d.slug, spec=d.spec)

        def change_walk(instruction:str,  # what to change, in the owner's words
                        steps:str='',     # the numbers of the steps to change; empty lets the tutor pick
                        ) -> str:
            "Change the walk as the owner asks. A kept step never changes."
            j = need('walk')
            olds = [(n, s_['slug'], name_of(s_['slug'])) for n, s_ in enumerate(j.steps, 1)]
            if re.search(r'\b(add|insert|include|new)\b', instruction, re.I) and (tp := topic_of(instruction)) and not re.search(r'\b(anyway|second|another|also)\b', instruction, re.I) and (o := first(o for o in olds if same_idea(o[2], tp))):
                return f"The walk has a step on this already: step {o[0]}, “{o[2]}”. Nothing changed. Say “add it anyway” for a second step."
            words = instruction + (f" Change only steps {', '.join(map(str, nums(steps)))}." if nums(steps) else '')
            names = lambda w: [(lr.concept(s['slug']) or {}).get('name') or s['slug'] for s in w.steps]
            stage('The tutor reads what you asked')
            cs = propose(ctx.ask, j, {s_['slug']: name_of(s_['slug']) for s_ in j.steps}, words)   # only the ideas of this walk: no idea from other content of the vault
            dup = [(c, near) for c in cs if c.op == 'add' and (near := first(o for o in olds if o[1] == (c.get('slug') or '') or same_idea(o[2], c.get('name') or '')))]
            cs = [c for c in cs if c not in [d for d, _ in dup]]   # a step that the walk has already, or nearly, is not added again
            said_dup = ' '.join(f"The walk has a step on this already: step {o[0]}, “{o[2]}”." for _, o in dup)
            if not cs: return ('The tutor found nothing new to change. ' + said_dup).strip()
            stage('The tutor changes the walk')
            j2, _ = improve_walk(lr, ctx.ask, j.id, cs, ctx.sources, {})
            run_hook('concepts_added')
            out = [f"Changed the walk: {n_of(len(cs), 'change')}."]
            new = [s_['slug'] for s_ in j2.steps if s_['slug'] not in {o[1] for o in olds}]
            if new and (want := place_of(instruction, j2.steps, new[0])) is not None:   # before, after, first or last: the new step goes there
                j2, _ = edit_walk(lr, j.id, lambda ss: move_step(ss, new[0], want), f'Moved “{name_of(new[0])}” to step {want + 1}.', who='tutor')
            for slug in new:   # the place that the walk has now, never the place that was asked for
                k = [s_['slug'] for s_ in j2.steps].index(slug)
                nb = (f", before “{name_of(j2.steps[k + 1]['slug'])}”" if k + 1 < len(j2.steps) else ', at the end')
                out.append(f"Added “{name_of(slug)}” as step {k + 1}{nb}.")
            if new and (an := anchor_of(instruction)) and place_of(instruction, j2.steps, new[0]) is None:
                out.append(f"No step names “{an}”, so the new step stays where it is.")
            return ' '.join([*out, said_dup]).strip(), dict(before=names(j), after=names(j2))

        def research(query:str,  # what to look for on the web
                     ) -> str:
            "Find extra material on the web. The owner keeps or drops each item in the pane; nothing is kept until the owner keeps it."
            br = rec().brief
            if not br.get('research', True): raise ValueError('Research is off in the brief. Use only the owner\'s sources.')
            rs = web_search(safe_query(query), FOUND_MOST)
            have = {f.get('url') for f in br.get('found') or []}
            items = [dict(url=r.get('href'), title=page_title(r.get('title') or r.get('href')), body=' '.join(str(r.get('body') or '').split())[:240], role='')
                     for r in rs if r.get('href') and r.get('href') not in have][:FOUND_MOST]
            put_brief(bid, found=[*(br.get('found') or []), *items])
            if not items: return 'Research found nothing new.'
            return (f"Research found {len(items)} items. The owner keeps or drops each one in the pane. End your turn now, and ask the owner to keep or drop them.",
                    dict(items=[i['url'] for i in items]))

        def docs_by_role():
            "The filed documents of the sources of the brief, by role: `{role: [(source name, doc)]}`."
            out = {}
            for src in rec().brief.get('sources') or []:
                if src.get('role') in ('main', 'extra'):
                    for _, ds in chip_docs(lr, [src['id']]): out.setdefault(src['role'], []).extend((src.get('name') or src['id'], d) for d in ds)
            return out

        def passages(query:str,  # what to look for in the sources of the brief
                     ) -> str:
            "Passages, word for word, from the main and the extra sources of the brief, so that you can compare what they say."
            out = []
            for role, ds in docs_by_role().items():
                for p in VaultSource(lr).search(query, 8):
                    hit = next(((n, d) for n, d in ds if p.get('title') == d.title), None)
                    if hit: out.append(f"[{role}] {hit[0]} · {hit[1].title}:\n{p.text[:700]}")
            return '\n\n'.join(out[:6]) or 'No passage of your sources names this.'

        def note_conflict(main_quote:str,  # the words of the main source, copied word for word
                          extra_quote:str, # the words of the extra source that say something else, word for word
                          ) -> str:
            "Note a conflict: a main source and an extra source say different things. The main source wins. The owner sees both quotes."
            def find(role, q):
                q = ' '.join(q.split())
                for n, d in docs_by_role().get(role) or []:
                    try: text = ' '.join((lr.doc_shelf(d.shelf) or lr.vault).document(d.doc_id, max_chars=400000, disk=False).text.split())   # a file is on its own shelf
                    except Exception: continue
                    if q and q in text: return dict(quote=q, title=d.title, role=f'{role} source', href=f'/v/{d.shelf}/{d.doc_id}')
            m, x = find('main', main_quote), find('extra', extra_quote)
            if not m or not x: raise ValueError('Both quotes must be word for word from a main and an extra source. Use passages to copy them.')
            rule = rec().brief.get('rules') or ''
            won = f"I used the main source{' (your rule: ' + rule + ')' if rule else ''}."
            return f"Conflict noted: {m['title']} against {x['title']}. {won}", dict(main=m, extra=x, won=won)

        def undo() -> str:
            "Take back the last change of the walk or the talk."
            return undo_of(rec(), 1)

        return [add_source, set_source, set_brief, keep, free, show, make_talk, make_walk, change_talk, edit_slide, set_poll, make_demo, change_walk, research, passages, note_conflict, undo]

    def edits_of(b) -> int:
        "The count of the changes in the history of the walk or the talk of conversation `b`."
        k, i = target(b)
        return len(lr.edits(k, i)) if k in ('talk', 'walk') and i else 0

    def undo_of(b, n=None) -> str:
        """Take back the changes of the walk or the talk of conversation `b`, as the Undo of its editor does: with no `n`, each change of the last turn,
        in one step (a turn that changed many slides comes back whole); else the `n` newest changes."""
        k, i = target(b)
        lt = b.get('last_turn') or {}
        n = n or (lt.get('n') if lt.get('target') == b.get('target') and lt.get('n') else 1)
        whats = []
        for _ in range(n):
            if k == 'talk':
                with edit_lock('talk', i):
                    if not lr.talk(i): raise ValueError('There is no talk.')
                    e = lr.pop_edit('talk', i, None, apply=lambda e: lr.put_talk(with_state(lr.talk(i), e.before)))
            elif k == 'walk': e, _ = undo_walk(lr, i)
            else: return 'There is nothing to undo.'
            if not e: break
            whats.append(e.what)
        with locks[b['id']]: lr.put_build({**lr.build(b['id']), 'last_turn': {}})
        return f"Undone: {'; '.join(whats)}" if whats else 'Nothing to undo.'

    def tooled(bid, st, f):
        "Tool `f` of conversation `bid`, with its events: a start with its arguments, its stages, its data and its result. An error goes back to the model as text."
        names = list(signature(f).parameters)
        @wraps(f)
        def g(*a, **kw):
            args = {**dict(zip(names, a)), **kw}
            if st.get('waiting'): return WAIT_FINDS
            if st.stop.is_set(): return 'The owner pressed Stop. Do not call more tools.'
            st.cur = st.em.tool_start(f.__name__, args)
            job_said(lr, key(bid), ui.line(f.__name__, args))
            try: r = f(*a, **kw)
            except (ValueError, KeyError) as e: r = f'It did not work: {e}'
            except Exception as e:
                log.warning('builder: the tool %s failed: %r', f.__name__, e)
                r = 'It did not work. abhyasa had an error.'
            text, data = r if isinstance(r, tuple) else (r, None)
            if data is not None: st.em.data(st.cur, data)
            st.em.tool_end(st.cur, str(text))
            if f.__name__ == 'research' and (data or {}).get('items'): st.waiting = len(data['items']); st.stop.set()   # the turn ends: the owner keeps or drops each find first
            job_said(lr, key(bid), ui.line(f.__name__, args) + ': done')
            return str(text)
        return g

    def agent_of(bid):
        "The agent of conversation `bid`: one for each conversation, made at its first turn."
        if (x := agents.get(bid)): return x
        st = AttrDict(stop=threading.Event(), em=None, cur=None, fresh=True, run=None)
        fs = tools(bid, st)
        a, host = ramabana_lead((), [f.__name__ for f in fs], sp=prompt('build.agent'), minutes=TURN['minutes'], max_calls=TURN['max_calls'],
                                max_steps=TURN['max_steps'], max_cost=TURN['max_cost'], web=False)
        for f in fs: a.add_tool(tooled(bid, st, f))
        st.native = hasattr(a, 'events')   # a ramabana that gives AG-UI events itself
        agents[bid] = x = AttrDict(a=a, host=host, st=st)
        return x

    # --- a turn --------------------------------------------------------------------------------------------------

    def now_line(b) -> str:
        k, _ = target(b)
        if not (x := thing(b)): return 'There is no walk or talk yet.'
        return f"the talk “{x.title}”, with {len(x.slides)} slides. Use show to see it." if k == 'talk' else f"the walk “{x.title}”, with {len(x.steps)} steps. Use show to see it."

    def ask_of(b, text, recap) -> str:
        "The prompt of one turn: the note of the owner's changes to the brief, the brief, the walk or the talk, the recap when the agent is new, and the request."
        br = {k: v for k, v in b.brief.items() if k != 'found'}
        br['found'] = [dict(title=f.get('title'), url=f.get('url'), role=f.get('role') or 'waits for the owner') for f in b.brief.get('found') or []]
        out = [f'The owner changed: {b.note}.'] if b.get('note') else []
        out += [f'The brief now: {json.dumps(br)}', f'The walk or the talk now: {now_line(b)}']
        earlier = [i for i in fold(b.get('events'))[:-1] if i['kind'] in ('user', 'assistant')][-RECAP:]
        if recap and earlier: out.append('Earlier in this conversation:\n' + '\n'.join(f"{'The owner' if i['kind'] == 'user' else 'You'}: {i['text'][:300]}" for i in earlier))
        return '\n\n'.join(out + [f'The owner says:\n{text}'])

    def turn(bid, text):
        "One turn of the agent of conversation `bid` on the request `text`, on the pool."
        x = agent_of(bid); st = x.st
        st.said = text; st.stop.clear(); st.run = None; st.waiting = 0; st.late = False; st.em = em = Emit(lambda e: emit(bid, e), x.a if st.native else None)
        with locks[bid]:
            b = lr.build(bid); p = ask_of(b, text, st.fresh)
            lr.put_build({**b, 'note': ''})
        st.fresh = False
        n0 = edits_of(b)
        try: return turn_body(bid, x, st, em, p)
        finally:   # the changes of this turn, so one Undo takes back all of them
            with locks[bid]:
                b2 = lr.build(bid)
                lr.put_build({**b2, 'last_turn': dict(target=b2.get('target'), n=edits_of(b2) - (n0 if b2.get('target') == b.get('target') else 0))})

    def turn_body(bid, x, st, em, p):
        "The body of a turn: the events of a ramabana that gives them, or the ask of an older ramabana."
        if st.native: return native(bid, x, p)
        em.ev('RUN_STARTED', runId=new_id())
        try: r = x.a.ask(p, result=True, stop=st.stop, deadline=TURN_SECS)   # a turn that hangs ends
        except Exception as e:
            log.warning('builder: the turn of %s failed: %r', bid, e)
            em.ev('RUN_ERROR', state='failed', message='The builder could not finish. Try again.'); raise
        if st.waiting: return wait_end(em, st)
        if r.state == 'cancelled' and not st.stop.is_set(): return late_end(bid)   # the deadline of the turn
        if st.stop.is_set(): close_open(bid, 'You stopped it before it finished.'); em.ev('RUN_FINISHED', state='stopped', message='You stopped it.'); return
        if (reply := (r.reply or '').strip()): em.text('assistant', reply)
        em.ev('RUN_FINISHED', state='done' if r.state == 'complete' else r.state, message='' if r.state == 'complete' else f'The turn ended early ({r.state}).')

    def native(bid, x, p):
        "A turn of a ramabana that gives AG-UI events: keep each event, and one text event for each message, not one for each piece."
        st, buf = x.st, {}
        gen = x.a.events(p, on_registered=lambda run: st.__setitem__('run', run))
        try:
            t0 = time.monotonic()
            for e in gen:
                if time.monotonic() - t0 > TURN_SECS:   # a turn that hangs ends: ramabana cancels it, and the job row ends
                    st.late = True
                    if st.get('run') is not None:
                        try: x.a.cancel(st.run.id)
                        except Exception: pass
                    break
                if e.get('timestamp') is None and e.get('at') is None: e = {**e, 'timestamp': int(time.time() * 1000)}   # each saved event keeps its time
                t = e.get('type')
                if t == 'TEXT_MESSAGE_CONTENT':   # one event for the whole message, with the time of its first piece
                    m = e.get('messageId'); txt, ts = buf.get(m, ('', e.get('timestamp') or int(time.time() * 1000)))
                    buf[m] = (txt + (e.get('delta') or ''), ts); continue
                if t == 'TEXT_MESSAGE_END' and (m := e.get('messageId')) in buf:
                    txt, ts = buf.pop(m); emit(bid, dict(type='TEXT_MESSAGE_CONTENT', messageId=m, delta=txt, timestamp=ts))
                emit(bid, e)
                if st.stop.is_set(): break
        finally: gen.close()
        if st.get('late'): return late_end(bid)
        if st.waiting: return wait_end(Emit(lambda e: emit(bid, e)), st, bid)
        if st.stop.is_set(): Emit(lambda e: emit(bid, e)).ev('RUN_FINISHED', state='stopped', message='You stopped it.')

    def close_open(bid, why) -> list:
        "Close each tool call of the last turn that did not finish, with `why`: a row never stays running after its turn. The lines of the calls that it closed."
        items = fold(lr.build(bid).events)
        k = max((n for n, x in enumerate(items) if x['kind'] == 'user'), default=0)
        open_ = [x for x in items[k:] if x['kind'] == 'tool' and x['status'] == 'running']
        em = Emit(lambda e: emit(bid, e))
        for x in open_: em.ev('TOOL_CALL_RESULT', toolCallId=x['id'], content=f'Not finished: {why}')
        return [ui.line(x['name'], x['args']) for x in open_]

    def late_end(bid):
        "The end of a turn that ran out of time: each open call says that it did not finish, and one line says what is done and what is not. The box is free again."
        items = fold(lr.build(bid).events); k = max((n for n, x in enumerate(items) if x['kind'] == 'user'), default=0)
        done = [x['result'] for x in items[k:] if x['kind'] == 'tool' and x['status'] == 'done' and x['name'] in CHANGERS and not str(x['result']).startswith('It did not work')]
        left = close_open(bid, 'the turn ran out of time.')
        Emit(lambda e: emit(bid, e)).ev('RUN_ERROR', state='failed', message=' '.join(x for x in (
            f"The builder took more than {TURN_SECS // 60} minutes, so it stopped.", f"Done: {' '.join(done)}" if done else 'Nothing changed.',
            f"Not done: {'; '.join(left)}." if left else '', 'Ask again for what is not done.') if x))

    def wait_end(em, st, bid=None):
        "The end of a turn after research: the result of the research call (the turn stopped before ramabana sent it), one line, then the turn ends and waits for Keep or Drop."
        if bid and (open_ := [x for x in fold(lr.build(bid).events) if x['kind'] == 'tool' and x['name'] == 'research' and x['status'] == 'running']):
            em.ev('TOOL_CALL_RESULT', toolCallId=open_[-1]['id'], content=f"Research found {n_of(st.waiting, 'item')}. They wait for your Keep or Drop.")
        em.text('assistant', f"I found {n_of(st.waiting, 'item')}. Keep or drop each one, then tell me what to do next.")
        em.ev('RUN_FINISHED', state='done')

    def busy(bid) -> bool: return bool((j := jobs.get(bid)) and not j.done())

    @hook('job_stop')
    def stop(r):
        "Stop on a builder job: the turn of the agent ends at once, and its tools refuse."
        if r.get('kind') != 'build' or not (x := agents.get(str(r.key)[6:])): return None
        x.st.stop.set()
        if x.st.get('run') is not None:
            try: x.a.cancel(x.st.run.id)   # a turn of `Agent.events`: ramabana cancels it and its tools
            except Exception as e: log.warning('builder: could not cancel the turn: %r', e)

    # --- the pages: the builder is a page in the side pane at the right; the walk or the talk is the page at the left ----------------

    def href_of(b) -> str:
        "The page of the walk or the talk of conversation `b`, or ''."
        k, i = target(b)
        return f'/t/{i}' if k == 'talk' and lr.talk(i) else f'/w/{i}' if k == 'walk' and lr.journey(i) else ''

    def host_url(bid, say='') -> str:
        "The page at the left with the builder open in the side pane: the walk or the talk, or the empty Build page."
        pane = Routes.of(Routes.one, bid=bid) + (f'?{urlencode(dict(say=say))}' if say else '')
        return (href_of(lr.build(bid)) or Routes.of(Routes.one, bid=bid)) + '?' + urlencode(dict(rh=pane))

    def live(bid:str):
        "The builder column as it is now."
        b = load(bid)
        return ui.Column(b, fold(b.get('events')), lr.job(key(bid)) if busy(bid) else None, CHANGERS, href_of(b))

    def one(req, bid:str, say:str=''):
        "In the side pane (`pane=1`): the builder. Else the page at the left: the walk or the talk with the builder open, or the empty Build page."
        if not (b := lr.build(bid)): return Response('No such conversation.', status_code=404)
        q = req.query_params
        if q.get('solo') == '1':   # a narrow window: the builder as one page, with the tabs Builder and Result
            return Page('Builder', ui.Tabs(Routes.of(Routes.one, bid=bid) + '?solo=1', href_of(b) or host_url(bid), 'Builder'), live(bid), on='Home', crumbs=[('Home', '/')],
                        extra=(asset_css(_P/'build.css'), asset_js(_P/'build.js'), *ui.rupaka_assets()))
        if q.get('pane') == '1':
            c = live(bid)
            if say: c = ui.Column(b, fold(b.get('events')), lr.job(key(bid)) if busy(bid) else None, CHANGERS, href_of(b), say)
            return Page('Builder', c, extra=(asset_css(_P/'build.css'), asset_js(_P/'build.js'), *ui.rupaka_assets()))
        if href_of(b) or not q.get('rh'): return RedirectResponse(host_url(bid, say), status_code=303)
        return Page('Build', ui.Tabs(Routes.of(Routes.one, bid=bid) + '?solo=1', host_url(bid), 'Result'), *ui.Host('Build a walk or a talk'), on='Home', crumbs=[('Home', '/')],
                    extra=(asset_css(_P/'build.css'), asset_js(_P/'build.js')))

    def base(): return RedirectResponse(host_url(new_build()), status_code=303)

    def opened(req, talk:str='', walk:str='', say:str='', send:str='', solo:str=''):
        """The conversation of a talk or a walk; a new one when it has none. In the side pane, the builder; else the page with the builder open.
        With `send`, `say` is sent at once (the change box of the walk page, and Change this slide). With `solo`, the builder as a page of its own (a narrow window)."""
        if talk and (t := lr.talk(talk)): bid = for_talk(t)
        elif walk and (j := lr.journey(walk)): bid = for_walk(j)
        else: return Response('No such walk or talk.', status_code=404)
        if send and say.strip(): start_turn(bid, ' '.join(say.split())[:SAY_MOST]); say = ''
        if solo: return RedirectResponse(Routes.of(Routes.one, bid=bid) + '?solo=1', status_code=303)
        if req.query_params.get('pane') == '1': return RedirectResponse(Routes.of(Routes.one, bid=bid) + '?' + urlencode(dict(pane='1', **({'say': say} if say else {}))), status_code=303)
        return RedirectResponse(host_url(bid, say), status_code=303)

    def start_turn(bid, text):
        "Keep your message and start the turn of the agent on the pool, unless one runs."
        if busy(bid): return False
        Emit(lambda e: emit(bid, e)).text('user', text)
        b = lr.build(bid)
        jobs[bid] = track(lr, key(bid), lambda: ctx.pool.submit(turn, bid, text), 'build', title=f"Builder: {b.get('title') or 'a new walk or talk'}", said='Thinking',
                          url=host_url(bid), obj=key(bid), ok=lambda _: dict(said='Ready.'), why=lambda e: 'The builder could not finish.')
        return True

    async def say(req, bid:str):
        if not lr.build(bid): return Response('No such conversation.', status_code=404)
        text = ' '.join(str((await req.form()).get('text') or '').split())[:SAY_MOST]
        if text: start_turn(bid, text)
        return live(bid)

    async def start(req):
        """Start and Make a talk in the Start box: a new conversation with the chips as `main` sources, and the typed text as its first message.
        The job starts at once, and the answer is the page with the builder open. A box with no text and no chip is refused, so the Start box does its own work."""
        f = await req.form()
        q, ids = ' '.join(str(f.get('q') or '').split())[:SAY_MOST], [x for x in f.getlist('sources') if isinstance(x, str) and x.strip()]
        if not q and not ids: return JSONResponse(dict(url=''), status_code=422)
        kind = 'talk' if f.get('talk') else 'walk'
        srcs = [dict(id=c, name=c.split(':', 1)[-1].rstrip('/').split('/')[-1], role='main') for c in ids]
        br = new_brief(kind=kind, sources=srcs, audience=' '.join(str(f.get('audience') or '').split()), no_code=bool(f.get('no_code')))
        bid = new_build(brief=br)
        start_turn(bid, q or f'Make a {kind} from these sources.')
        return JSONResponse(dict(url=host_url(bid)))

    async def brief(req, bid:str):
        "A change to the brief by hand: a field, or the role of one source. The thread says it, and the agent reads a note of it at its next turn."
        if not (b := lr.build(bid)): return Response('No such conversation.', status_code=404)
        f = {k: v for k, v in (await req.form()).items() if isinstance(v, str)}
        kw = {k: ' '.join(f[k].split()) for k in FIELDS if k in f and k != 'minutes'}
        if 'minutes' in f: kw['minutes'] = int(f['minutes']) if f['minutes'].strip().isdecimal() else 0
        for k in ('research', 'no_code'):
            if k in f: kw[k] = onoff(f[k]) is True
        if f.get('src') and f.get('role') in ROLES: kw['sources'] = [{**s, 'role': f['role']} if s['id'] == f['src'] else s for s in b.brief.get('sources') or []]
        if (said := said_of(b.brief, {**b.brief, **kw})): Emit(lambda e: emit(bid, e)).ev('CUSTOM', name='note', value=f'You changed the brief: {said}.')
        put_brief(bid, by='owner', **kw)
        return live(bid)

    def item(bid:str, url:str='', role:str='', urls:str=''):
        "Keep (`extra`) or Drop (`dropped`) one find of research, or each open one (`url='*'`): its role goes in the brief at once, and a kept find is an extra source."
        if not (b := lr.build(bid)) or role not in ('extra', 'dropped'): return Response('No such find.', status_code=404)
        pick = set(urls.split()) if url == '*' else {url}
        found = [{**x, 'role': role} if x.get('url') in pick and (url != '*' or not x.get('role')) else x for x in b.brief.get('found') or []]
        if found == (b.brief.get('found') or []): return live(bid)
        now = {x['url']: x for x in found}
        ss = [s for s in b.brief.get('sources') or [] if s['id'][5:] not in pick or not s.get('found')]
        ss += [dict(id=f'link:{u}', name=now[u].get('title') or u, role='extra', found=True) for u in now if u in pick and now[u].get('role') == 'extra']
        put_brief(bid, by='owner', found=found, sources=ss)
        if not any(not x.get('role') for x in found) and (k := sum(x.get('role') == 'extra' for x in found if x.get('url') in now)):   # each find is decided: the builder uses the kept ones now
            d = sum(x.get('role') == 'dropped' for x in found)
            start_turn(bid, f"I kept {n_of(k, 'find')} and dropped {d}. Use the kept finds now: make the {lr.build(bid).brief.get('kind') or 'walk'} again with them.")
        return live(bid)

    def undo(bid:str):
        "Undo of the builder (⌘Z): the last change of the walk or the talk, as one line in the thread. The page at the left loads again."
        if not (b := lr.build(bid)): return Response('No such conversation.', status_code=404)
        em = Emit(lambda e: emit(bid, e))
        t = em.tool_start('undo', {})
        try: said = undo_of(b)
        except (ValueError, KeyError) as e: said = f'It did not work: {e}'
        em.tool_end(t, said)
        return live(bid)

    @hook('hand_edit')
    def hand_edit(kind, tid, said):
        "A change by hand on the talk editor or the walk page: a quiet line in the conversation of that talk or walk, which the next turn reads."
        x = lr.talk(tid) if kind == 'talk' else lr.journey(tid)
        if not x or not (bid := x.get('build')) or not lr.build(bid): return None
        Emit(lambda e: emit(bid, e)).ev('CUSTOM', name='note', value=f'You changed it by hand: {said}')
        with locks[bid]:
            b = lr.build(bid); lr.put_build({**b, 'note': '; '.join(x for x in (b.get('note'), f'by hand: {said}') if x)})

    @hook('learn_start')
    def start_link(): return ui.StartLink(Routes.base), asset_js(_P/'build.js')

    def in_pane() -> bool:
        "Whether the page is drawn in the side pane: it has no builder of its own there."
        return (r := page_req()) is not None and r.query_params.get('pane') == '1'

    @hook('talk_editor')
    def beside_talk(t):
        "On the talk editor: Change with the builder, in the side pane (⌥E)."
        if in_pane(): return None
        u = f"{Routes.open}?talk={t['id']}"
        return ui.Tabs(u + '&solo=1', f"/t/{t['id']}", 'Result'), asset_css(_P/'build.css'), asset_js(_P/'build.js')

    @hook('talk_head')
    def head_talk(t):
        "Change with the builder, in the head of the talk editor, beside its menu (⌥E)."
        return None if in_pane() else ui.Beside(f"{Routes.open}?talk={t['id']}")

    @hook('walk_actions')
    def beside_walk(j, quiet=False, row=False):
        "On the walk page: Change with the builder, in the side pane (⌥E). Not on a row in a list, and not on a hidden walk of a talk."
        if row or (j.get('parent') or {}).get('for') == 'talk' or j.get('mode') != 'walk' or in_pane(): return None
        u = f"{Routes.open}?walk={j['id']}"
        return ui.Tabs(u + '&solo=1', f"/w/{j['id']}", 'Result'), ui.Beside(u), asset_css(_P/'build.css'), asset_js(_P/'build.js')

    @hook('pane_title')
    def title(url):
        if url.startswith('/build'): return 'Builder'

    app.get(Routes.base)(base)
    app.get(Routes.open)(opened)
    app.post(Routes.start)(start)
    app.get(Routes.one)(one)
    app.post(Routes.say)(say)
    app.get(Routes.chat)(live)
    app.post(Routes.brief)(brief)
    app.post(Routes.item)(item)
    app.post(Routes.undo)(undo)
