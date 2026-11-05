"""The pieces of the builder, as the design says: the brief fold, the thread of turns (your message, one row for each tool call with its view
from `RENDER`, then one line and the openable What I read and What changed), and the box. The builder is a page in the side pane at the right;
the walk or the talk is the page at the left. Each piece is small, with the `.bd-*` classes of build.css."""
import json, re
from fasthtml.common import *
from rupaka.render import Demo, version
from abhyasa.core import Primary, Secondary, Quiet, Md, JobStop, Pill, Empty, n_of
from abhyasa.core.pane import pane_link
from abhyasa.show import ROLES
from .cfg import Routes

FIRST = 'Tell me what to make: a walk to learn a topic, or a talk for a group. Add files, folders or links, and say how to use them.'
SAY_EMPTY, SAY_AFTER = 'Say what you want, or what to change', 'What should change? For example: slide 3 has too much code.'
NO_SOURCES, NO_AIM = 'No sources yet. abhyasa uses the web.', 'No aim yet. Say one, for example: make them technical.'
RUNNING = 'The talk is running. You can change it after the talk.'
TRY = ('Make a talk from my notebook for managers, 20 minutes.', 'Make me a walk on attention in transformers.', 'Make a 10 minute talk on how attention picks its values, with a demo.')
EARLIER = 3   # the newest turns that show open; the older ones fold into "N earlier requests"

def at(r, bid): return Routes.of(r, bid=bid)

def askable(on:bool) -> dict:
    "`askable` for a rupaka `Demo`, when this rupaka has it (rk-ask); else nothing, so an older rupaka shows no ask control."
    from inspect import signature
    return {'askable': on} if 'askable' in signature(Demo).parameters else {}

def rupaka_assets():
    "The rupaka runtime that the demo block serves, for a live demo in the thread."
    v = version()
    return Link(rel='stylesheet', href=f'/rupaka/rupaka.css?v={v}'), Script(src=f'/rupaka/rupaka.js?v={v}')

# --- one row for each tool call -------------------------------------------------------------------------------------

def _name(ref): return str(ref or '').split(':', 1)[-1].rstrip('/').split('/')[-1] or str(ref)

LINES = dict(add_source=lambda a: f"Adding {_name(a.get('ref'))}", set_source=lambda a: f"Making {_name(a.get('ref'))} {a.get('role')}",
             set_brief=lambda a: 'Changing the brief', keep=lambda a: f"Keeping {a.get('items')} as they are", free=lambda a: f"Letting {a.get('items')} change",
             show=lambda a: 'Reading the walk or the talk', make_talk=lambda a: 'Making the talk', make_walk=lambda a: 'Making the walk',
             change_talk=lambda a: f"Changing slide {a['slides']}" if a.get('slides') else 'Making the talk again',
             restyle_talk=lambda a: f"Changing the words of slide {a['slides']}" if a.get('slides') else 'Changing the words of the talk',
             edit_slide=lambda a: f"Changing slide {a.get('slide')}", set_poll=lambda a: 'Changing the poll',
             make_demo=lambda a: f"Making the demo for slide {a.get('slide')}", change_walk=lambda a: 'Changing the walk',
             research=lambda a: f"Looking on the web for {a.get('query')}", undo=lambda a: 'Taking back the last change',
             passages=lambda a: f"Reading your sources on {a.get('query')}", note_conflict=lambda a: 'Noting a conflict between your sources')

def line(name, args) -> str:
    "The short line of the call of tool `name` with `args`."
    try: return LINES[name](args or {})
    except Exception: return name.replace('_', ' ').capitalize()

def failed(x) -> bool: return x['status'] == 'done' and str(x['result']).startswith('It did not work')

_NO_CHANGE = re.compile(r"\bnothing (changed|to change|new to change|to undo)\b|^(A talk exists|The walk has a step on this already|There is no walk or talk yet)", re.I)

def refused(x) -> bool:
    "Whether a done call of a tool that changes the walk or the talk changed nothing: it refused (the walk has that step already), or it had nothing to do."
    return x['status'] == 'done' and bool(_NO_CHANGE.search(str(x['result'])))

def Call(x, view='', cls='', open_=False):
    "One tool call: a quiet line that opens, with its state as a dot and as words, and its view."
    now = x['stages'][-1] if x['status'] == 'running' and x['stages'] else ''
    t = line(x['name'], x['args']) + (f' · {now}' if now else '…' if x['status'] == 'running' else '')
    body = view or (P(x['result'], cls='mute') if x['status'] == 'done' and x['result'] else '')
    body = tuple(body) if isinstance(body, (list, tuple)) else (body,)
    sec = x.get('secs')
    return Li(Details(Summary(Span(t, cls='t'), Span(f'{sec:.0f}s' if isinstance(sec, (int, float)) and sec >= 1 else '', cls='secs')), Div(*body, cls='bd-view') if any(body) else '',
                      cls=' '.join(c for c in ('bd-call', 'failed' if failed(x) else x['status'], cls) if c), open=open_ or None))

def Plain(x, b): return Call(x)

def _act(bid, url, role, label, key, btn, **vals):
    return btn(label, ' ', Kbd(key), type='button', hx_post=at(Routes.item, bid), hx_vals=json.dumps(dict(url=url, role=role, **vals)), hx_target='#build-live',
               hx_swap='outerHTML', data_key=key, **({'small': True} if btn is Quiet else {}))

def Found(x, b):
    "Research: each find with Keep (F) and Drop (X). Nothing goes into the walk or the talk until you keep it. The one raised card while a find waits."
    roles = {f.get('url'): f for f in b.brief.get('found') or []}
    urls = (x.get('data') or {}).get('items') or []
    if not urls: return Call(x)
    def item(u):
        f = roles.get(u) or dict(url=u, title=u)
        r = f.get('role') or ''
        acts = Pill('Kept') if r == 'extra' else Pill('Dropped') if r == 'dropped' else (_act(b.id, u, 'extra', 'Keep', 'F', Secondary), _act(b.id, u, 'dropped', 'Drop', 'X', Quiet))
        site = u.split('/')[2] if '//' in u else u
        return Li(Span(f.get('title') or u, cls='ttl'), Div(Pill('Research'), ' ', A(site, href=u, target='_blank', rel='noopener'), cls='src-line'),
                  P(f.get('body') or '', cls='why mute'), Div(acts, cls='acts'), cls=f'find {r}'.strip(), tabindex='0')
    left = sum(1 for u in urls if not (roles.get(u) or {}).get('role'))
    foot = Div(Span(f"{left} of {len(urls)} {'is' if left == 1 else 'are'} open. The builder adds only what you keep." if left else 'You decided each find.', cls='mute'),
               *((_act(b.id, '*', 'extra', 'Keep all', '⇧F', Quiet, urls=' '.join(urls)), _act(b.id, '*', 'dropped', 'Drop all', '⇧X', Quiet, urls=' '.join(urls))) if left else ()),
               cls='bd-finds-foot')
    return Call(x, (Ul(*map(item, urls), cls='bd-finds'), foot), cls='ask' if left else '', open_=bool(left))

def Side(v, label):
    "One side of a change: the title, the points, the question, the notes and the code or passage of a slide, in words that you can read."
    code = (v.get('passage') or '').strip()
    return Div(Span(label, cls='lbl'), B(v.get('title') or ''), Ul(*[Li(p) for p in v.get('body') or []]) if v.get('body') else '',
               P(v['ask'], cls='bd-ask') if v.get('ask') else '', P(v['notes'], cls='bd-notes mute') if v.get('notes') else '',
               Md(code, cls='bd-code') if code else '', P(Span(v['src'].split(' · ')[0], cls='pill'), ' ', ' · '.join(v['src'].split(' · ')[1:]), cls='src-line mute') if v.get('src') else '',
               cls='bd-side')

def Changed(x, b):
    "change_talk, edit_slide and change_walk: before and after for each changed slide, then the lines that changed."
    d = x.get('data') or {}
    if x['status'] != 'done' or not d: return Call(x)
    if 'changed' in d:
        if not d['changed']: return Call(x)
        view = [Div(B(f"Slide {c.get('n')}", cls='bd-n'), Side(c.get('before') or {}, 'Before'), Side(c.get('after') or {}, 'After'), cls='bd-diff') for c in d['changed']]
    else:
        was, now = d.get('before') or [], d.get('after') or []
        view = [Ul(*[Li(Del(s)) for s in was if s not in now], *[Li(Ins(s)) for s in now if s not in was], cls='bd-lines')]
    return Call(x, view, open_=True)

def Outline(x, b):
    "make_talk and make_walk: the outline as soon as the plan is made, and a line that says what is written now."
    o = (x.get('data') or {}).get('outline') or []
    if not o: return Call(x)
    run, labels, cut = x['status'] == 'running', (x.get('data') or {}).get('labels') or [], (x.get('data') or {}).get('cut') or []
    return Call(x, (Ol(*[Li(s, ' ', Span(labels[k], cls='mute src') if k < len(labels) else '') for k, s in enumerate(o)],
                       *([Li(Span(x['stages'][-1] if x['stages'] else 'writing the slides', cls='mute'), cls='now')] if run else []), cls='bd-outline'),
                    P(f"Left out to fit the slot: {', '.join(cut)}", cls='mute') if cut else ''), open_=True)

def ADemo(x, b):
    "make_demo: the demo, live, in a sunken well, as the room sees it on the slide. Ask about this demo puts a message in the box."
    d = x.get('data') or {}
    if x['status'] != 'done' or not d.get('spec'): return Call(x)
    return Call(x, Div(Div(Demo(d['spec'], data_demo=d.get('demo'), **askable(True)), cls='frame'), P(f"On slide {d.get('slide')}", cls='mute'),
                       cls='bd-demo', data_slide=str(d.get('slide') or '')), open_=True)

RENDER = dict(research=Found, change_talk=Changed, restyle_talk=Changed, change_walk=Changed, edit_slide=Changed, make_talk=Outline, make_walk=Outline, make_demo=ADemo)   # tool name -> its view

# --- turns ----------------------------------------------------------------------------------------------------------

def turns(items) -> list:
    "The items in turns: each turn is your message (or None), its tool calls, its notes, the replies of the builder and how the run ended."
    out, cur = [], None
    for x in items:
        if x['kind'] == 'user' or cur is None:
            cur = dict(me=x if x['kind'] == 'user' else None, calls=[], said=[], notes=[], run=None); out.append(cur)
            if x['kind'] == 'user': continue
        if x['kind'] == 'tool':
            cur['calls'].append(x)
            if x['name'] == 'undo': cur['undo_at'] = len(cur['said'])   # the words of the builder so far are from before this Undo
        elif x['kind'] == 'assistant' and x['text'].strip(): cur['said'].append(x['text'].strip())
        elif x['kind'] == 'note': cur['notes'].append(x['text'])
        elif x['kind'] == 'run': cur['run'] = x
    return out

BRIEF_TOOLS = ('add_source', 'set_source', 'set_brief', 'keep', 'free')
CLAIM = re.compile(r"\b(changed|made|rewrote|added|removed|dropped|put|moved|shortened|simplified|hid)\b", re.I)

def Conflict(d):
    "One conflict that the builder found: both quotes word for word, each with its source, and the source that won."
    q = lambda x: Div(Blockquote(x.get('quote') or ''), P(Span(x.get('role') or '', cls='pill'), ' ', A(x.get('title') or '', href=x.get('href')) if x.get('href') else x.get('title') or '', cls='src-line mute'))
    return Li(q(d.get('main') or {}), q(d.get('extra') or {}), P(d.get('won') or '', cls='mute'), cls='bd-conflict')

_JUNK = re.compile(r'^\s*(</?[a-z_:]+[^>]*>|(wait, )?i must use the correct format\.?|record the brief first\.?|keep slides? [\d, and]+ first\.?)\s*$', re.I | re.M)

def clean_said(x:str) -> str:
    "The words of the model with no stray tool tags (`</invoke>`) and no notes to itself, such as \"Record the brief first.\""
    return re.sub(r'\n{3,}', '\n\n', _JUNK.sub('', str(x or ''))).strip()

def Turn(t, b, changers, last=False, href=''):
    """One turn: your message, the tool calls, then one line built from what the tools did (never from the words of the model), with Undo,
    and the openable parts: What I read, Conflicts, What changed, What the builder said, and the log of the calls that did not work."""
    calls, said = t['calls'], [x for x in map(clean_said, t['said']) if x]
    ok = lambda x: x['status'] == 'done' and not failed(x)
    shown = [x for x in calls if x['name'] in LINES and x['name'] != 'note_conflict' and not failed(x)]
    hidden = [x for x in calls if x not in shown and (x['name'] != 'note_conflict' or failed(x))]
    changed = [x for x in calls if x['name'] in changers and ok(x) and not refused(x)]   # a refused step is not a change: it has no Undo and no See it
    facts = [x['result'] for x in calls if ok(x) and x['name'] in (*changers, *BRIEF_TOOLS)]
    conflicts = [x['data'] for x in calls if x['name'] == 'note_conflict' and ok(x) and x.get('data')]
    undo = Quiet('Undo', ' ', Kbd('⌘Z'), type='button', small=True, hx_post=at(Routes.undo, b.id), hx_target='#build-live', hx_swap='outerHTML', data_undo='1') if last and changed else ''
    reply = said[-1] if said else ''
    # only the last words of the turn show, as the earlier ones can say the opposite; words from before an Undo that worked say so
    undone = any(x['name'] == 'undo' and ok(x) and not refused(x) for x in calls) and t.get('undo_at') is not None
    before_undo = undone and bool(said) and len([x for x in map(clean_said, t['said'][:t['undo_at']]) if x]) == len(said)
    if facts: line = Div(P(' '.join(facts)), undo, cls='bd-said')
    elif reply: line = Div(Md(reply), *([P('Nothing changed in the walk or the talk in this turn.', cls='mute')] if CLAIM.search(reply) and not t.get('run') else []), cls='bd-said')
    else: line = ''
    read = [Li(f"{s.get('name') or s['id']} ({s.get('role')})") for s in b.brief.get('sources') or [] if s.get('role') != 'dropped']
    more = (*((Details(Summary('What I read'), Ul(*read) if read else P(NO_SOURCES, cls='mute'), cls='bd-more'),) if changed else ()),
            *((Details(Summary('Conflicts'), Ul(*map(Conflict, conflicts), cls='plain'), cls='bd-more', open=True),) if conflicts else ()),
            *((Details(Summary('What changed'), Ul(*[Li(x['result'], ' ', A('See it', href=href) if href else '') for x in changed]), cls='bd-more'),) if changed else ()),
            *((Details(Summary('What the builder said'), *([P('Before the Undo:', cls='mute')] if before_undo else []), Md(said[-1]), cls='bd-more'),) if said and facts else ()),
            *((Details(Summary('What did not work'), Ul(*[Li(line_(x), ': ', x['result']) for x in hidden]), cls='bd-more'),) if hidden else ()))
    run = t.get('run')
    end = (P(Span('Not done: ', cls='k'), run['text'], cls='bd-said no') if run['state'] != 'stopped' else P(run['text'], cls='bd-said mute')) if run else ''
    steps = Details(Summary('What I did'), Ul(*[Li(x) for x in said[:-1]]), cls='bd-more') if len(said) > 1 and not facts else ''
    body = (Ol(*[RENDER.get(x['name'], Plain)(x, b) for x in shown], cls='bd-calls') if shown else '', line, end, steps, *more)
    return (Li(P(t['me']['text']), cls='bd-me') if t['me'] else '', *[Li(n, cls='bd-note') for n in t['notes']],
            Li(*body, cls='bd-turn') if calls or said or run else '')

def line_(x): return line(x['name'], x['args'])

# --- the brief ------------------------------------------------------------------------------------------------------

def _post(bid): return dict(hx_post=at(Routes.brief, bid), hx_target='#build-live', hx_swap='outerHTML')

def _text(bid, name, v, ph=''):
    return Input(type='text', name=name, value=v or '', placeholder=ph, hx_trigger='change', aria_label=name, **_post(bid))

def _pick(bid, name, v, opts, **vals):
    return Select(*[Option(o, value=o, selected=o == v) for o in opts], name=name, hx_trigger='change', hx_vals=json.dumps(vals) if vals else None, aria_label=name, **_post(bid))

def summary(br) -> str:
    "The brief in one line, for the closed fold."
    srcs = [f"{s.get('name') or s['id']} ({s.get('role')})" for s in br.get('sources') or [] if s.get('role') != 'dropped']
    return ' · '.join(x for x in (br.get('kind') or '', br.get('goal') or '', *srcs, 'your material only' if br.get('research') is False else 'web research on',
                                  f"for {br['audience']}" if br.get('audience') else '', f"{br['minutes']} min" if br.get('minutes') else '',
                                  'no code' if br.get('no_code') else '', f"keep {len(br['keep'])}" if br.get('keep') else '') if x)

def Brief(b, open_=None):
    "Your brief: one line when closed (⌥A opens it); open, each field, which you can change here too. The builder gets a note of each change at its next turn."
    br, bid = b.brief, b.id
    both = {s.get('role') for s in br.get('sources') or []} >= {'main', 'extra'}
    src = [Li(B(s.get('name') or s['id'], title=s['id']), Span(s['id'].split(':', 1)[0], cls='k'), Span('wins a conflict', cls='wins') if both and s.get('role') == 'main' else '',
              _pick(bid, 'role', s.get('role'), ROLES, src=s['id']), cls=s.get('role')) for s in br.get('sources') or []]
    dl = Dl(Dt('Sources'), Dd(Ul(*src, cls='bd-srcs') if src else Span(NO_SOURCES, cls='mute')),
            Dt('Kind'), Dd(_pick(bid, 'kind', br.get('kind') or '', ('', 'walk', 'talk'))),
            Dt('Goal'), Dd(_text(bid, 'goal', br.get('goal'), 'The topic or the goal')),
            Dt('Web research'), Dd(_pick(bid, 'research', 'On' if br.get('research') else 'Off', ('On', 'Off'))),
            Dt('Aim'), Dd(_text(bid, 'aim', br.get('aim'), NO_AIM)),
            Dt('For'), Dd(_text(bid, 'audience', br.get('audience'), 'Who it is for')),
            Dt('Minutes'), Dd(_text(bid, 'minutes', str(br.get('minutes') or ''), 'The minutes of a talk')),
            Dt('No code'), Dd(_pick(bid, 'no_code', 'On' if br.get('no_code') else 'Off', ('Off', 'On'))),
            Dt('Rules'), Dd(P(br['rules'], cls='bd-rule') if br.get('rules') else '', _text(bid, 'rules', br.get('rules'), 'Your rules about the sources')),
            *((Dt('Kept'), Dd(Div(*[Pill(k) for k in br['keep']], cls='bd-keep'))) if br.get('keep') else ()))
    first = not (br.get('sources') or br.get('goal'))
    return Details(Summary(Span('Your brief', cls='lbl'), Span(summary(br) or 'Nothing yet', cls='bd-sum'), Kbd('⌥A')), dl,
                   cls='bd-brief', id='bd-brief', open=(first if open_ is None else open_) or None)

# --- the builder column ---------------------------------------------------------------------------------------------

def changes(items, changers) -> int:
    "The count of the tool calls that changed the walk or the talk and are done: the page at the left loads again when it goes up."
    return sum(1 for x in items if x['kind'] == 'tool' and x['status'] == 'done' and x['name'] in changers and not refused(x))

def Composer(bid, row, text='', after=False):
    "The box: voice as the Start box (⌥D), Send (⌥S), and Stop (⌥X) while a turn runs. The text stays when the column loads again."
    run = row is not None and row.state == 'running'
    return Form(Textarea(text, name='text', id='build-say', rows=2, data_mic='label', placeholder=SAY_AFTER if after else SAY_EMPTY, aria_label='Your request', hx_preserve='true'),
                Div(Span(((row.get('said') or 'Thinking') + '…') if run else '', cls='left mute'), Span(cls='grow'),
                    *([JobStop(row)] if run else []), Primary('Send', type='submit', disabled=run or None), cls='row bar'),
                hx_post=at(Routes.say, bid), hx_target='#build-live', hx_swap='outerHTML', hx_on__before_send="this.querySelector('textarea').value = ''", cls='composer')

def Column(b, items, row, changers, href='', say=''):
    """The builder: the brief, the thread and the box, in one column of the side pane. It loads again on each event of its job (`build:<id>`),
    and every 3 seconds while a turn runs. `data-changes` counts the changes, so the page at the left loads again when it goes up."""
    run = row is not None and row.state == 'running'
    ts = turns(items)
    old, new = (ts[:-EARLIER], ts[-EARLIER:]) if len(ts) > EARLIER else ([], ts)
    hello = [Li(P(FIRST), Ul(*[Li(Button(x, type='button', data_try=x)) for x in TRY], cls='bd-try'), cls='bd-said')] if not items else []
    early = [Li(Details(Summary(n_of(len(old), 'earlier request')), Ol(*[y for t in old for y in Turn(t, b, changers, href=href)], cls='bd-thread')), cls='bd-earlier')] if old else []
    thread = Ol(*early, *hello, *[y for k, t in enumerate(new) for y in Turn(t, b, changers, last=k == len(new) - 1, href=href)],
                cls='bd-thread', id='build-log', aria_label='The conversation')
    return Div(Brief(b), thread, Composer(b.id, row, say, after=bool(b.get('target'))), id='build-live', cls='bd', data_build=b.id, data_job=f'build:{b.id}',
               data_changes=str(changes(items, changers)), data_landed=landed(items) or None, data_busy='1' if run else None,
               hx_get=at(Routes.chat, b.id), hx_trigger='job, every 3s' if run else 'job', hx_swap='outerHTML')

def landed(items) -> str:
    "The numbers of the slides that the last change of the builder touched, for the `.landed` mark on the page at the left."
    for x in reversed(items):
        if x['kind'] == 'tool' and x['status'] == 'done' and (d := x.get('data')):
            ns = [c.get('n') for c in d.get('changed') or []] + ([d['slide']] if d.get('slide') else [])
            if ns: return ','.join(str(n) for n in ns if n)
        if x['kind'] == 'user': break
    return ''

def Tabs(builder, result, on):
    "The narrow window has no side pane: two tabs, Builder (⌥1) and Result (⌥2). A wide window does not show them (build.css)."
    return Nav(A('Builder', href=builder, cls='on' if on == 'Builder' else None, title='⌥1'), A('Result', href=result, cls='on' if on == 'Result' else None, title='⌥2'),
               cls='subtabs bd-tabs', aria_label='Builder or result')

def Host(title):
    "The page at the left of Build before the builder made anything."
    return H1(title), Empty('The walk or the talk that you make shows here.')

def StartLink(href):
    return P(A('Make a walk or a talk by talking', href=href), cls='build-start mute')

def Beside(href):
    "Change with the builder: it opens the builder beside the page, in the side pane (⌥E)."
    return pane_link('Change with the builder', href, 'Builder', cls='btn quiet build-beside')
